"""Logic cho các tab trình diễn từng bước (tab 1 đến 4) trên PostgreSQL và TPC-H.

Chuyển từ demo_core.py của Nhóm 3 (dự án "LLM As DBA", bản gốc dùng MySQL 8):
- Kịch bản 1 thiếu index, kịch bản 2 truy vấn con tương quan, kịch bản 3 tranh chấp khóa.
- Prompt A (chỉ có triệu chứng) và prompt B (kiểu D-Bot: thẻ kinh nghiệm và số đo thật).
- Chấm điểm tự động bằng biểu thức chính quy.
- Mini lambda-Tune: AI đề xuất cấu hình, chỉ chạy lệnh trong danh sách cho phép, rồi đo thật.
"""
import re
import threading
import time

import psycopg

from app.common import pg_connect

# =====================================================================
# Tiện ích
# =====================================================================
def query(conn, sql, args=None):
    with conn.cursor() as cur:
        cur.execute(sql, args)
        if not cur.description:
            return []
        cols = [c.name for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def timed(conn, sql, args=None):
    t0 = time.perf_counter()
    rows = query(conn, sql, args)
    return time.perf_counter() - t0, rows


def explain(conn, sql):
    return [r["QUERY PLAN"] for r in query(conn, "EXPLAIN " + sql)]


def fmt_rows(rows, cols=None):
    if not rows:
        return "(rỗng)"
    cols = cols or list(rows[0].keys())
    return "\n".join("  " + ", ".join(f"{c}={r.get(c)}" for c in cols) for r in rows)


def connect(app="dbot-streamlit"):
    # Tên ứng dụng bắt đầu bằng dbot- để monitor bỏ qua các truy vấn đo của chính demo.
    return pg_connect(app_name=app)


def data_status():
    with connect() as c:
        rows = query(c, """SELECT relname AS bang, n_live_tup AS so_dong,
                                  pg_size_pretty(pg_total_relation_size(relid)) AS kich_thuoc
                           FROM pg_stat_user_tables WHERE schemaname = 'tpch' ORDER BY n_live_tup DESC""")
        ext = query(c, "SELECT extname FROM pg_extension WHERE extname = 'pg_stat_statements'")
        ver = query(c, "SHOW server_version")[0]["server_version"]
    return {"tables": rows, "pg_stat_statements": bool(ext), "version": ver}


def secondary_indexes(conn, tables=("lineitem", "orders", "customer", "part")):
    return query(conn, """SELECT indexname, tablename FROM pg_indexes
                          WHERE schemaname = 'tpch' AND tablename = ANY(%s) AND indexname NOT LIKE '%%_pkey'""",
                 (list(tables),))


def drop_secondary_indexes(conn, tables=("lineitem", "orders", "customer", "part")):
    idx = secondary_indexes(conn, tables)
    for r in idx:
        query(conn, f'DROP INDEX IF EXISTS tpch."{r["indexname"]}"')
    return [r["indexname"] for r in idx]


# =====================================================================
# Kịch bản 1: thiếu index
# =====================================================================
KB1_SQL = "SELECT count(*) AS so_dong, avg(l_extendedprice) AS gia_tb FROM tpch.lineitem WHERE l_partkey = %s"
KB1_EXPLAIN = "SELECT count(*), avg(l_extendedprice) FROM tpch.lineitem WHERE l_partkey = 42"
KB1_FIX = "CREATE INDEX idx_l_partkey ON tpch.lineitem(l_partkey)"
KB1_N = 50


def kb1_break():
    with connect() as c:
        query(c, "DROP INDEX IF EXISTS tpch.idx_l_partkey")
        query(c, "SELECT pg_stat_statements_reset()")


def kb1_workload(n=KB1_N):
    with connect() as c:
        t0 = time.perf_counter()
        for i in range(1, n + 1):
            query(c, KB1_SQL, (i * 37,))
        return time.perf_counter() - t0


def kb1_tools():
    with connect() as c:
        plan = explain(c, KB1_EXPLAIN)
        stmts = query(c, """SELECT left(query, 120) AS query, calls, round(mean_exec_time::numeric, 2) AS mean_ms,
                                   shared_blks_hit + shared_blks_read AS blocks
                            FROM pg_stat_statements WHERE query ILIKE '%%l_partkey%%'
                            ORDER BY calls DESC LIMIT 3""")
        tbl = query(c, """SELECT seq_scan, idx_scan, n_live_tup FROM pg_stat_user_tables
                          WHERE schemaname = 'tpch' AND relname = 'lineitem'""")
        locks = query(c, "SELECT count(*) AS n FROM pg_locks WHERE NOT granted")[0]["n"]
    return {"explain": plan, "statements": stmts, "table": tbl, "lock_waits": locks}


def kb1_fix():
    with connect() as c:
        t, _ = timed(c, KB1_FIX)
        return t, explain(c, KB1_EXPLAIN)


# =====================================================================
# Kịch bản 2: truy vấn con tương quan
# =====================================================================
KB2_LIMIT = 8000
KB2_SLOW = f"""SELECT count(*) AS so_don FROM tpch.orders o
WHERE o.o_orderkey <= {KB2_LIMIT}
  AND o.o_totalprice > (SELECT avg(o2.o_totalprice) FROM tpch.orders o2 WHERE o2.o_custkey = o.o_custkey)"""
KB2_FAST = f"""SELECT count(*) AS so_don FROM tpch.orders o
JOIN (SELECT o_custkey, avg(o_totalprice) AS a FROM tpch.orders GROUP BY o_custkey) d ON o.o_custkey = d.o_custkey
WHERE o.o_orderkey <= {KB2_LIMIT} AND o.o_totalprice > d.a"""


def kb2_run(sql):
    with connect() as c:
        query(c, "SET statement_timeout = '120s'")
        t, rows = timed(c, sql)
        return t, rows[0]["so_don"], explain(c, sql)


# =====================================================================
# Kịch bản 3: tranh chấp khóa (A giữ khóa, B bị chặn, C quan sát)
# =====================================================================
LOCK_TOOL_SQL = """
SELECT w.pid AS waiting_pid, left(w.query, 100) AS waiting_query,
       round(extract(epoch FROM now() - w.query_start)::numeric, 1) AS wait_sec,
       pg_blocking_pids(w.pid) AS blocked_by, b.state AS blocking_state,
       left(b.query, 100) AS blocking_query,
       'SELECT pg_terminate_backend(' || b.pid || ')' AS sql_kill_blocking
FROM pg_stat_activity w
JOIN pg_stat_activity b ON b.pid = ANY(pg_blocking_pids(w.pid))
WHERE w.wait_event_type = 'Lock'"""


class LockScenario:
    def __init__(self, wait_timeout=20):
        self.wait_timeout = wait_timeout
        self.conn_a = None
        self.b_result = {"status": "chưa chạy"}
        self.b_thread = None

    def start_a(self):
        """Phiên A: BEGIN và UPDATE, không COMMIT, nên giữ khóa dòng o_orderkey = 1."""
        self.conn_a = pg_connect(app_name="demo-kb3-A", autocommit=False)
        query(self.conn_a, "UPDATE tpch.orders SET o_totalprice = o_totalprice + 1 WHERE o_orderkey = 1")
        return query(self.conn_a, "SELECT pg_backend_pid() AS pid")[0]["pid"]

    def start_b(self):
        """Phiên B chạy nền: UPDATE cùng dòng, bị chặn cho tới khi A nhả khóa."""
        def run():
            with pg_connect(app_name="demo-kb3-B") as conn:
                query(conn, f"SET lock_timeout = '{self.wait_timeout}s'")
                self.b_result = {"status": "đang chờ khóa"}
                t0 = time.perf_counter()
                try:
                    query(conn, "UPDATE tpch.orders SET o_totalprice = o_totalprice - 1 WHERE o_orderkey = 1")
                    self.b_result = {"status": "xong", "seconds": time.perf_counter() - t0}
                except psycopg.Error as e:
                    self.b_result = {"status": "lỗi", "seconds": time.perf_counter() - t0,
                                     "error": str(e).splitlines()[0]}
        self.b_thread = threading.Thread(target=run, daemon=True)
        self.b_thread.start()
        time.sleep(1.5)

    def tools(self):
        with connect() as c:
            return query(c, LOCK_TOOL_SQL)

    def fix(self):
        """Sửa: phiên A ROLLBACK để nhả khóa, phiên B chạy xong."""
        if self.conn_a:
            self.conn_a.rollback()
            self.conn_a.close()
            self.conn_a = None
        if self.b_thread:
            self.b_thread.join(timeout=self.wait_timeout + 5)
        return self.b_result


# =====================================================================
# Thẻ kinh nghiệm và prompt (theo dạng name/content/metrics/steps của D-Bot)
# =====================================================================
EXPERIENCE = """[THẺ KINH NGHIỆM 1]
name: missing_index
content: Truy vấn lọc theo cột không có index phải quét toàn bảng, làm tăng I/O và CPU.
metrics: pg_stat_statements (calls, blocks), pg_stat_user_tables.seq_scan, EXPLAIN
steps: Chạy EXPLAIN; nếu thấy Seq Scan kèm Filter trên bảng lớn thì đó là nguyên nhân; đề xuất CREATE INDEX trên cột trong WHERE.

[THẺ KINH NGHIỆM 2]
name: lock_contention
content: Transaction giữ khóa lâu (chưa COMMIT) làm các transaction khác phải chờ.
metrics: pg_locks (granted = false), pg_blocking_pids(), wait_event_type = Lock
steps: Nếu có phiên chờ khóa và pg_blocking_pids trả về pid thì đó là nguyên nhân; xử lý phiên chặn (COMMIT, ROLLBACK hoặc pg_terminate_backend) và rút ngắn transaction.

[THẺ KINH NGHIỆM 3]
name: correlated_subquery
content: Truy vấn con tương quan bị chạy lại cho từng dòng của truy vấn ngoài.
metrics: EXPLAIN (SubPlan)
steps: Nếu EXPLAIN có SubPlan nằm trong Filter thì đó là nguyên nhân; viết lại bằng JOIN với bảng tạm GROUP BY (unnesting)."""

ANSWER_RULE = ("Trả lời bằng tiếng Việt, tối đa 150 từ, theo dạng: 'Nguyên nhân: ...' rồi 'Cách sửa: ...' "
               "(kèm lệnh SQL nếu có).")


def prompt_a(symptom):
    return f"Database PostgreSQL 16 của tôi gặp vấn đề sau:\n{symptom}\nNguyên nhân là gì và tôi nên sửa thế nào?\n{ANSWER_RULE}"


def prompt_b(symptom, tool_text):
    return (f"Bạn là DBA. Sự cố: {symptom}\n\n"
            "Hãy chẩn đoán nguyên nhân gốc theo quy trình: đối chiếu từng thẻ kinh nghiệm với kết quả công cụ, "
            "chỉ kết luận khi có bằng chứng trong kết quả công cụ.\n\n"
            f"{EXPERIENCE}\n\n[KẾT QUẢ CÔNG CỤ THẬT]\n{tool_text}\n\n{ANSWER_RULE}")


GRADING = {
    "kb1": [r"index|chỉ mục|chi muc", r"l_partkey"],
    "kb2": [r"subquery|subplan|truy vấn con|truy van con|tương quan|tuong quan|correlat",
            r"join|group by|unnest|bảng tạm|bang tam"],
    "kb3": [r"lock|khóa|khoá|khoa", r"commit|rollback|terminate|kill"],
}


def auto_grade(kb, answer):
    """Đúng nguyên nhân khi khớp mọi nhóm từ khóa; cụ thể khi có lệnh SQL."""
    a = (answer or "").lower()
    correct = all(re.search(p, a) for p in GRADING[kb])
    specific = bool(re.search(r"create index|select |rollback|commit|pg_terminate_backend|join ", a))
    return correct, specific


# =====================================================================
# Mini lambda-Tune cho PostgreSQL
# =====================================================================
LT_WORKLOAD = [
    ("Q1 tổng hợp theo cờ trả hàng",
     "SELECT l_returnflag, l_linestatus, sum(l_quantity), avg(l_extendedprice) FROM tpch.lineitem "
     "WHERE l_shipdate <= date '1998-09-01' GROUP BY 1, 2"),
    ("Q2 JOIN orders và lineitem",
     "SELECT o_orderpriority, count(*) FROM tpch.orders JOIN tpch.lineitem ON l_orderkey = o_orderkey "
     "WHERE o_orderdate >= date '1995-01-01' AND o_orderdate < date '1995-04-01' GROUP BY 1 ORDER BY 1"),
    ("Q3 lọc theo khoảng ngày giao",
     "SELECT count(*), sum(l_extendedprice * l_discount) FROM tpch.lineitem "
     "WHERE l_shipdate >= date '1994-01-01' AND l_shipdate < date '1994-01-15' AND l_quantity < 24"),
]

PRESETS = {
    "C1 tăng work_mem": ["SET work_mem = '64MB'"],
    "C2 index l_shipdate": ["CREATE INDEX lt_l_shipdate ON tpch.lineitem(l_shipdate)"],
    "C3 index và tắt song song": ["SET max_parallel_workers_per_gather = 0",
                                  "CREATE INDEX lt_o_orderdate ON tpch.orders(o_orderdate)",
                                  "CREATE INDEX lt_l_shipdate ON tpch.lineitem(l_shipdate)"],
}

LT_PROMPT = """Recommend some configuration parameters for PostgreSQL 16 to optimize the system's performance.
Parameters might include system-level configurations, like memory, query optimizer or physical design configurations, like index recommendations.
Each row in the following list has the following format:
{a join key A}:{all the joins with A in the workload}
lineitem.l_orderkey: orders.o_orderkey
Other predicates in the workload: lineitem.l_shipdate range; orders.o_orderdate range; lineitem.l_quantity < constant
Aggregates used: SUM, AVG, COUNT, GROUP BY l_returnflag, l_linestatus, o_orderpriority
Table sizes: lineitem 600,000 rows; orders 150,000 rows.
The workload runs on a system with the following specs:
memory: {mem}
cores: {cores}
Return ONLY executable SQL statements, one per line, each ending with ';'.
Allowed statement types: SET <parameter> = <value>; (session level) and CREATE INDEX <name> ON tpch.<table>(<columns>);
Allowed parameters: work_mem, hash_mem_multiplier, random_page_cost, effective_cache_size, max_parallel_workers_per_gather, jit, enable_seqscan."""

# Chỉ cho phép lệnh an toàn ở mức phiên (giống bước DBA phê duyệt).
# shared_buffers cần khởi động lại máy chủ nên không đưa vào danh sách.
SAFE_SQL = re.compile(
    r"^(SET\s+(work_mem|hash_mem_multiplier|random_page_cost|effective_cache_size|"
    r"max_parallel_workers_per_gather|jit|enable_seqscan)\s*(=|TO)\s*'?[\w.]+'?"
    r"|CREATE\s+INDEX\s+\w+\s+ON\s+(tpch\.)?(lineitem|orders|customer|part)\s*\([\w\s,]+\))$", re.I)


def parse_config(text):
    text = re.sub(r"```\w*", "", text or "")
    ok, rejected = [], []
    for stmt in text.split(";"):
        s = " ".join(l.strip() for l in stmt.strip().splitlines()
                     if l.strip() and not l.strip().startswith("--")).strip()
        if not s:
            continue
        (ok if SAFE_SQL.match(s) else rejected).append(s)
    return ok, rejected


def normalize(stmt):
    """Thêm schema tpch cho CREATE INDEX nếu AI quên ghi."""
    return re.sub(r"(?i)(\bON\s+)(lineitem|orders|customer|part)\b", r"\1tpch.\2", stmt)


def run_config(name, statements, timeout_ms=20000):
    """Áp dụng một cấu hình trên một phiên mới, chạy workload có giới hạn thời gian."""
    with connect("dbot-lambda-tune") as c:
        drop_secondary_indexes(c)
        query(c, "SELECT pg_stat_reset()")
        t_apply, applied, errors = 0.0, [], []
        for s in statements:
            s = normalize(s)
            try:
                dt, _ = timed(c, s)
                t_apply += dt
                applied.append(s)
            except psycopg.Error as e:
                errors.append(f"{s}: {str(e).splitlines()[0]}")
        query(c, "ANALYZE tpch.lineitem")
        query(c, "ANALYZE tpch.orders")
        query(c, f"SET statement_timeout = {int(timeout_ms)}")
        total, detail, timed_out = 0.0, [], False
        for qname, q in LT_WORKLOAD:
            try:
                dt, _ = timed(c, q)
            except psycopg.errors.QueryCanceled:
                dt, timed_out = timeout_ms / 1000, True
            total += dt
            detail.append({"truy_van": qname, "giay": round(dt, 3)})
        drop_secondary_indexes(c)
    return {"cau_hinh": name, "giay_workload": round(total, 3), "giay_ap_dung": round(t_apply, 2),
            "bi_timeout": timed_out, "lenh": applied, "loi": errors, "chi_tiet": detail}
