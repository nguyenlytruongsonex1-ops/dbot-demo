"""Monitor: cứ MONITOR_INTERVAL giây đọc các view thống kê của PostgreSQL,
so với ngưỡng, tạo alert và tự đánh dấu alert đã giải quyết."""
import json
import logging
import os
import re
import time

from app.common import (MONITOR_INTERVAL, RESOLVE_AFTER_SCANS, bump_version, get_setting,
                        pg_connect, set_setting, store)

log = logging.getLogger("monitor")

LONG_QUERY_SEC = float(os.getenv("TH_LONG_QUERY_SEC", "5"))
LOCK_WAIT_SEC = float(os.getenv("TH_LOCK_WAIT_SEC", "3"))
IDLE_TX_SEC = float(os.getenv("TH_IDLE_TX_SEC", "10"))
SEQ_SCAN_DELTA = int(os.getenv("TH_SEQ_SCAN_DELTA", "20"))
STMT_CALLS_DELTA = int(os.getenv("TH_STMT_CALLS_DELTA", "20"))
STMT_BLOCKS_PER_CALL = int(os.getenv("TH_STMT_BLOCKS_PER_CALL", "1000"))
DEAD_TUP_MIN = int(os.getenv("TH_DEAD_TUP_MIN", "100000"))
DEAD_RATIO = float(os.getenv("TH_DEAD_RATIO", "0.2"))
CONN_RATIO = float(os.getenv("TH_CONN_RATIO", "0.8"))

OWN_APPS = ("dbot-monitor", "dbot-worker", "dbot-backend")

ACTIVITY_SQL = """
SELECT pid, usename, application_name, state, wait_event_type, wait_event,
       left(query, 500) AS query,
       extract(epoch FROM now() - query_start) AS query_sec,
       extract(epoch FROM now() - xact_start) AS xact_sec,
       extract(epoch FROM now() - state_change) AS state_sec,
       pg_blocking_pids(pid) AS blocked_by,
       (xact_start < query_start) AS earlier_stmts
FROM pg_stat_activity
WHERE backend_type = 'client backend' AND pid <> pg_backend_pid()
  AND application_name NOT LIKE 'dbot-%%' AND application_name <> ALL(%s)
"""

TABLES_SQL = """
SELECT schemaname || '.' || relname AS tbl, seq_scan, idx_scan, n_live_tup, n_dead_tup,
       pg_total_relation_size(relid) AS size_bytes
FROM pg_stat_user_tables
"""

TOP_STMTS_SQL = """
SELECT left(query, 300) AS query, calls, round(mean_exec_time::numeric, 2) AS mean_ms,
       round(total_exec_time::numeric, 0) AS total_ms
FROM pg_stat_statements ORDER BY total_exec_time DESC LIMIT 5
"""


STMT_SQL = """
SELECT queryid, left(query, 300) AS query, calls,
       shared_blks_hit + shared_blks_read AS blocks,
       round(mean_exec_time::numeric, 2) AS mean_ms
FROM pg_stat_statements
WHERE query ILIKE 'select%%' AND query NOT ILIKE '%%pg_stat%%'
"""


def rows(cur, sql, params=None):
    cur.execute(sql, params)
    cols = [c.name for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def clean(v):
    if isinstance(v, float):
        return round(v, 1)
    if hasattr(v, "__float__") and not isinstance(v, (int, bool)):
        return round(float(v), 1)
    return v


def detect(cur, prev):
    """Trả về (dict key -> signal, trạng thái để so sánh ở lần quét sau)."""
    signals = {}
    prev_tables = prev.get("tables", {})
    prev_stmts = prev.get("stmts", {})
    try:
        stmts = {r["queryid"]: r for r in rows(cur, STMT_SQL)}
    except Exception:
        stmts = {}
    acts = rows(cur, ACTIVITY_SQL, (list(OWN_APPS),))
    tables = {t["tbl"]: t for t in rows(cur, TABLES_SQL)}
    try:
        top = rows(cur, TOP_STMTS_SQL)
    except Exception:
        top = []
    top = [{k: clean(v) for k, v in t.items()} for t in top]

    for a in acts:
        a = {k: clean(v) for k, v in a.items()}
        if a["state"] == "active" and a["wait_event_type"] == "Lock" and (a["query_sec"] or 0) >= LOCK_WAIT_SEC:
            signals["lock_wait"] = dict(
                type="lock_wait", severity="critical",
                title="Phiên bị chặn vì chờ khóa",
                details={"waiting_pid": a["pid"], "blocked_by": a["blocked_by"],
                         "wait_sec": a["query_sec"], "query": a["query"]})
        elif a["state"] == "active" and (a["query_sec"] or 0) >= LONG_QUERY_SEC and a["wait_event_type"] != "Lock" \
                and a["wait_event"] != "PgSleep":
            on_cpu = a["wait_event_type"] in (None, "")
            sev = "critical" if a["query_sec"] >= 30 else "warning"
            prev = signals.get("long_query")
            if not prev or prev["details"]["duration_sec"] < a["query_sec"]:
                signals["long_query"] = dict(
                    type="long_query", severity=sev,
                    title="Query chạy lâu" + (" và đang dùng CPU" if on_cpu else ""),
                    details={"pid": a["pid"], "user": a["usename"], "duration_sec": a["query_sec"],
                             "wait_event": f"{a['wait_event_type']}:{a['wait_event']}" if not on_cpu else "CPU",
                             "query": a["query"], "top_statements": top})
        if a["state"] in ("idle in transaction", "idle in transaction (aborted)") and (a["state_sec"] or 0) >= IDLE_TX_SEC:
            signals["idle_in_transaction"] = dict(
                type="idle_in_transaction", severity="warning",
                title="Transaction mở nhưng không hoạt động",
                details={"pid": a["pid"], "idle_sec": a["state_sec"], "xact_sec": a["xact_sec"], "query": a["query"]})
        if a["state"] == "active" and "pg_sleep" in (a["query"] or "") and (a["xact_sec"] or 0) >= IDLE_TX_SEC \
                and a["earlier_stmts"]:
            # Transaction đã ghi dữ liệu rồi ngủ: mô phỏng ứng dụng quên commit.
            signals["idle_in_transaction"] = dict(
                type="idle_in_transaction", severity="warning",
                title="Transaction mở lâu, giữ khóa mà không làm gì",
                details={"pid": a["pid"], "xact_sec": a["xact_sec"], "query": a["query"]})

    max_conn = int(rows(cur, "SHOW max_connections")[0]["max_connections"])
    if len(acts) >= CONN_RATIO * max_conn:
        signals["too_many_connections"] = dict(
            type="too_many_connections", severity="critical",
            title="Số kết nối gần chạm giới hạn",
            details={"connections": len(acts), "max_connections": max_conn})

    for name, t in tables.items():
        p = prev_tables.get(name)
        if p and t["n_live_tup"] >= 10000:
            delta = (t["seq_scan"] or 0) - (p["seq_scan"] or 0)
            if delta >= SEQ_SCAN_DELTA:
                signals[f"missing_index:{name}"] = dict(
                    type="missing_index", severity="warning",
                    title=f"Quét toàn bảng liên tục trên {name}",
                    details={"table": name, "seq_scans_last_interval": delta,
                             "n_live_tup": t["n_live_tup"], "top_statements": top})
        dead, live = t["n_dead_tup"] or 0, t["n_live_tup"] or 0
        if dead >= DEAD_TUP_MIN and dead >= DEAD_RATIO * max(live, 1):
            signals[f"table_bloat:{name}"] = dict(
                type="table_bloat", severity="warning",
                title=f"Bảng {name} có nhiều dòng chết",
                details={"table": name, "n_dead_tup": dead, "n_live_tup": live,
                         "size_mb": round(t["size_bytes"] / 1048576, 1)})
    # pg_stat_statements cập nhật ngay cả khi câu lệnh nằm trong một khối DO đang chạy,
    # còn pg_stat_user_tables chỉ cập nhật khi transaction kết thúc.
    for qid, st in stmts.items():
        p = prev_stmts.get(qid)
        if not p:
            continue
        dc, db = st["calls"] - p["calls"], st["blocks"] - p["blocks"]
        if dc >= STMT_CALLS_DELTA and db / dc >= STMT_BLOCKS_PER_CALL and " where " in st["query"].lower().replace("\n", " "):
            m = re.search(r"\bfrom\s+([\w.]+)", st["query"], re.I)
            name = m.group(1) if m else "unknown"
            if "." not in name:
                name = "tpch." + name
            signals[f"missing_index:{name}"] = dict(
                type="missing_index", severity="warning",
                title=f"Query lặp lại quét toàn bảng {name} (nghi thiếu index)",
                details={"table": name, "query": st["query"], "calls_last_interval": dc,
                         "blocks_per_call": round(db / dc), "mean_ms": float(st["mean_ms"])})
    return signals, {"tables": tables, "stmts": stmts}


def apply(signals):
    now = time.time()
    changed = False
    with store() as con:
        open_alerts = {r["key"]: r for r in con.execute("SELECT * FROM alerts WHERE status='open'")}
        for key, s in signals.items():
            if key in open_alerts:
                con.execute("UPDATE alerts SET details=?, severity=?, missed_scans=0, updated_at=? WHERE id=?",
                            (json.dumps(s["details"], default=str), s["severity"], now, open_alerts[key]["id"]))
            else:
                con.execute("INSERT INTO alerts(key,type,title,severity,status,details,created_at,updated_at) "
                            "VALUES(?,?,?,?, 'open', ?, ?, ?)",
                            (key, s["type"], s["title"], s["severity"], json.dumps(s["details"], default=str), now, now))
                log.info("Alert mới: %s", key)
            changed = True
        for key, r in open_alerts.items():
            if key in signals:
                continue
            missed = r["missed_scans"] + 1
            if missed >= RESOLVE_AFTER_SCANS:
                con.execute("UPDATE alerts SET status='resolved', missed_scans=?, resolved_at=?, updated_at=? WHERE id=?",
                            (missed, now, now, r["id"]))
                log.info("Đã giải quyết: %s", key)
            else:
                con.execute("UPDATE alerts SET missed_scans=? WHERE id=?", (missed, r["id"]))
            changed = True
        if changed:
            bump_version(con)


def paused():
    """Monitor tạm dừng khi tab Mini lambda-Tune đang đo, để không báo nhầm."""
    with store() as con:
        return get_setting(con, "monitor_paused", "0") == "1"


def heartbeat(status):
    with store() as con:
        set_setting(con, "monitor_heartbeat", f"{time.time()}|{status}")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    state = {}
    conn = None
    while True:
        try:
            if paused():
                heartbeat("paused")
                state = {}  # bỏ số liệu cũ để lần quét sau không tính chênh lệch sai
                time.sleep(MONITOR_INTERVAL)
                continue
            heartbeat("running")
            if conn is None or conn.closed:
                conn = pg_connect(app_name="dbot-monitor")
            with conn.cursor() as cur:
                signals, state = detect(cur, state)
            apply(signals)
        except Exception as e:  # noqa: BLE001
            log.warning("Lỗi khi quét: %s", e)
            conn = None
        time.sleep(MONITOR_INTERVAL)


if __name__ == "__main__":
    main()
