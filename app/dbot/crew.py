"""D-Bot: chẩn đoán alert bằng CrewAI (2 agent) hoặc chế độ mock (luật cứng).

AI chỉ đề xuất. Không có công cụ nào được phép sửa dữ liệu hay cấu hình DB.
"""
import json
import re

from app import common, llm
from app.dbot.tools import ToolBox

REPORT_KEYS = ("summary", "steps", "root_cause", "remediation")


def diagnose(alert: dict, provider: str = None) -> dict:
    """Chẩn đoán một alert. Nếu nguồn LLM đã chọn không có key hoặc lỗi thì chuyển sang Ollama."""
    provider = provider or common.LLM_PROVIDER
    tb = ToolBox()
    notes = []
    try:
        if provider == "mock":
            report, used = mock_diagnose(alert, tb), "mock"
        else:
            order = [provider] if provider == "ollama" else [provider, "ollama"]
            report, used = None, None
            for p in order:
                if not llm.available(p):
                    notes.append(f"Không có API key cho {llm.LABELS[p]}, chuyển sang Ollama.")
                    continue
                try:
                    tb.calls.clear()
                    report, used = crew_diagnose(alert, tb, p), p
                    break
                except Exception as e:  # noqa: BLE001
                    notes.append(f"{llm.LABELS[p]} lỗi: {str(e)[:200]}")
            if report is None:
                raise RuntimeError(" ".join(notes) or "Không gọi được LLM nào")
        report["tool_calls"] = tb.calls
        report["provider"] = used
        report["model"] = llm.model_of(used)
        report["provider_requested"] = provider
        report["fallback_notes"] = notes
        return report
    finally:
        tb.close()


# ---------------- CrewAI ----------------
def _llm(provider):
    from crewai import LLM
    if provider == "claude":
        return LLM(model=f"anthropic/{common.CLAUDE_MODEL}", api_key=llm.api_key("claude"), max_tokens=2000)
    if provider == "gemini":
        return LLM(model=f"gemini/{common.GEMINI_MODEL}", api_key=llm.api_key("gemini"))
    if provider == "openai":
        return LLM(model=f"openai/{common.OPENAI_MODEL}", base_url=common.OPENAI_BASE_URL,
                   api_key=llm.api_key("openai"), temperature=0.1)
    return LLM(model=f"ollama/{common.OLLAMA_MODEL}", base_url=common.OLLAMA_BASE_URL, temperature=0.1)


def _make_tools(tb: ToolBox):
    from crewai.tools import tool

    @tool("explain_query")
    def explain_query(sql: str) -> str:
        """Chạy EXPLAIN (không ANALYZE) cho một câu SELECT để xem kế hoạch thực thi."""
        return tb.explain_query(sql)

    @tool("get_locks")
    def get_locks() -> str:
        """Liệt kê phiên đang chặn hoặc bị chặn, và số khóa chưa được cấp."""
        return tb.get_locks()

    @tool("get_activity")
    def get_activity() -> str:
        """Xem các phiên đang chạy trong pg_stat_activity."""
        return tb.get_activity()

    @tool("get_table_stats")
    def get_table_stats(table: str) -> str:
        """Thống kê bảng (seq_scan, idx_scan, dòng chết, kích thước), danh sách index, reloptions. Tham số: schema.table"""
        return tb.get_table_stats(table)

    @tool("get_top_statements")
    def get_top_statements() -> str:
        """Top 5 câu lệnh tốn thời gian nhất theo pg_stat_statements."""
        return tb.get_top_statements()

    @tool("search_knowledge")
    def search_knowledge(query: str) -> str:
        """Tra tri thức chẩn đoán (file markdown) theo từ khóa, ví dụ 'lock', 'missing index', 'bloat'."""
        return tb.search_knowledge(query)

    return [explain_query, get_locks, get_activity, get_table_stats, get_top_statements, search_knowledge]


def crew_diagnose(alert: dict, tb: ToolBox, provider: str) -> dict:
    from crewai import Agent, Crew, Process, Task
    model = _llm(provider)
    alert_text = json.dumps({k: alert[k] for k in ("type", "title", "severity", "details")},
                            ensure_ascii=False, default=str)
    diag = Agent(
        role="Chuyên gia chẩn đoán PostgreSQL",
        goal="Tìm nguyên nhân gốc của alert bằng dữ liệu thật từ công cụ",
        backstory="Bạn là DBA giàu kinh nghiệm. Bạn chỉ kết luận dựa trên dữ liệu công cụ trả về. "
                  "Bạn không bao giờ sửa database.",
        tools=_make_tools(tb), llm=model, max_iter=8, verbose=False, allow_delegation=False)
    reporter = Agent(
        role="Người viết báo cáo sự cố",
        goal="Viết báo cáo ngắn gọn, rõ ràng bằng tiếng Việt, đúng định dạng JSON",
        backstory="Bạn tổng hợp kết quả chẩn đoán cho DBA. Bạn chỉ đề xuất, không thực thi.",
        llm=model, verbose=False, allow_delegation=False)
    t1 = Task(
        description=f"Alert từ monitor:\n{alert_text}\n\n"
                    "Hãy dùng công cụ để điều tra (ít nhất: tra tri thức, và 1-3 công cụ dữ liệu phù hợp). "
                    "Với mỗi bước ghi rõ: công cụ đã gọi, dữ liệu quan sát được, kết luận rút ra.",
        expected_output="Danh sách các bước điều tra và nguyên nhân gốc có bằng chứng.",
        agent=diag)
    t2 = Task(
        description="Dựa vào kết quả chẩn đoán, trả về DUY NHẤT một JSON hợp lệ, tiếng Việt, dạng:\n"
                    '{"summary": "...", "steps": [{"tool": "...", "observation": "...", "conclusion": "..."}], '
                    '"root_cause": "...", "remediation": [{"action": "...", "sql": "...", "risk": "..."}]}\n'
                    "Không thêm chữ nào ngoài JSON.",
        expected_output="Một đối tượng JSON.", agent=reporter, context=[t1])
    out = Crew(agents=[diag, reporter], tasks=[t1, t2], process=Process.sequential, verbose=False).kickoff()
    return parse_report(str(out), tb)


def parse_report(text: str, tb: ToolBox) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    data = {}
    if m:
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            data = {}
    if not data:
        data = {"summary": text[:1500], "root_cause": "Không đọc được JSON từ LLM, xem phần tóm tắt.",
                "remediation": []}
    if not data.get("steps"):
        data["steps"] = [{"tool": c["tool"], "observation": c["observation"][:600], "conclusion": ""}
                         for c in tb.calls]
    for k in REPORT_KEYS:
        data.setdefault(k, [] if k in ("steps", "remediation") else "")
    return data


# ---------------- Mock (không cần LLM) ----------------
def mock_diagnose(alert: dict, tb: ToolBox) -> dict:
    """Chẩn đoán bằng luật cứng nhưng vẫn gọi công cụ thật trên DB.
    Dùng để kiểm thử luồng khi máy chưa có Ollama."""
    t, d = alert["type"], alert["details"]
    steps = []

    def step(tool_out, conclusion):
        c = tb.calls[-1]
        steps.append({"tool": c["tool"], "observation": c["observation"][:600], "conclusion": conclusion})

    tb.search_knowledge(t.replace("_", " "))
    step(None, f"Tìm thấy tri thức cho loại sự cố {t}.")
    table = d.get("table", "tpch.lineitem")
    if t == "long_query":
        tb.get_activity(); step(None, f"Phiên {d.get('pid')} chạy {d.get('duration_sec')} giây, trạng thái chờ: {d.get('wait_event')}.")
        plan = tb.explain_query(d.get("query", ""))
        if "SubPlan" in plan:
            step(None, "Kế hoạch có SubPlan trong Filter: truy vấn con tương quan chạy lại cho từng dòng của truy vấn ngoài.")
            root = "Truy vấn con tương quan bị thực thi lặp lại cho mỗi dòng, mỗi lần lại quét toàn bảng."
            rem = [{"action": "Viết lại bằng JOIN với bảng tạm GROUP BY (unnesting)",
                    "sql": "SELECT count(*) FROM tpch.orders o JOIN (SELECT o_custkey, avg(o_totalprice) AS a "
                           "FROM tpch.orders GROUP BY o_custkey) d ON o.o_custkey = d.o_custkey WHERE o.o_totalprice > d.a;",
                    "risk": "Cần kiểm tra kết quả giống bản cũ"},
                   {"action": "Hoặc tạo index cho cột tương quan", "sql": "CREATE INDEX CONCURRENTLY idx_o_custkey ON tpch.orders(o_custkey);",
                    "risk": "Tốn I/O khi tạo"},
                   {"action": "Hủy query đang chạy nếu ảnh hưởng hệ thống", "sql": f"SELECT pg_cancel_backend({d.get('pid')});", "risk": "Thấp"}]
            return {"summary": f"[Chế độ mock, không dùng LLM] {alert['title']}. {root}",
                    "steps": steps, "root_cause": root, "remediation": rem}
        step(None, "Kế hoạch có Seq Scan trên bảng lớn." if "Seq Scan" in plan else "Đã xem kế hoạch thực thi.")
        root = "Một query tính toán nặng quét toàn bộ bảng nhiều lần, chiếm CPU lâu."
        rem = [{"action": "Hủy query đang chạy nếu ảnh hưởng hệ thống", "sql": f"SELECT pg_cancel_backend({d.get('pid')});", "risk": "Thấp, chỉ hủy câu lệnh hiện tại"},
               {"action": "Giới hạn thời gian chạy cho user ứng dụng", "sql": "ALTER ROLE scenario_runner SET statement_timeout = '30s';", "risk": "Query hợp lệ chạy lâu cũng bị hủy"}]
    elif t == "missing_index":
        tb.get_table_stats(table); step(None, f"Bảng {table} bị quét toàn bảng {d.get('calls_last_interval') or d.get('seq_scans_last_interval')} lần trong một chu kỳ, không có index trên cột lọc.")
        tb.get_top_statements(); step(None, "Một câu SELECT lọc theo cột không có index được gọi rất nhiều lần.")
        plan = tb.explain_query(d.get("query", "").replace("$1", "1").replace("$2", "1")); step(None, "EXPLAIN cho thấy Seq Scan kèm Filter, không dùng index." if "Seq Scan" in plan else "Đã xem kế hoạch thực thi.")
        col = (re.search(r"where\s+(\w+)\s*=", d.get("query", ""), re.I) or [None, "cot_loc"])[1]
        root = f"Cột {col} của {table} không có index, mỗi lần tìm phải quét toàn bảng."
        rem = [{"action": f"Tạo index trên {col}", "sql": f"CREATE INDEX CONCURRENTLY idx_{col} ON {table}({col});", "risk": "Tốn I/O khi tạo, không khóa ghi"}]
    elif t in ("lock_wait", "idle_in_transaction"):
        tb.get_locks(); step(None, f"Có phiên giữ transaction lâu. Phiên chặn: {d.get('blocked_by') or d.get('pid')}.")
        blocker = (d.get("blocked_by") or [d.get("pid")])[0]
        root = "Một transaction cập nhật dòng rồi không commit, giữ khóa làm phiên khác phải chờ."
        rem = [{"action": "Kết thúc phiên đang giữ khóa (sau khi xác nhận)", "sql": f"SELECT pg_terminate_backend({blocker});", "risk": "Transaction đó bị rollback"},
               {"action": "Tự động cắt transaction bỏ quên", "sql": "ALTER DATABASE dbot_demo SET idle_in_transaction_session_timeout = '60s';", "risk": "Thấp"}]
    elif t == "table_bloat":
        tb.get_table_stats(table); step(None, f"Bảng có {d.get('n_dead_tup')} dòng chết, autovacuum có thể đang bị tắt.")
        root = "UPDATE hàng loạt tạo nhiều dòng chết trong khi autovacuum bị tắt."
        rem = [{"action": "Dọn dòng chết", "sql": f"VACUUM (ANALYZE) {table};", "risk": "Tốn I/O"},
               {"action": "Bật lại autovacuum", "sql": f"ALTER TABLE {table} RESET (autovacuum_enabled);", "risk": "Thấp"}]
    else:
        tb.get_activity(); step(None, "Đã xem các phiên hiện tại.")
        root = "Chưa có luật cho loại alert này."
        rem = []
    return {"summary": f"[Chế độ mock, không dùng LLM] {alert['title']}. {root}",
            "steps": steps, "root_cause": root, "remediation": rem}
