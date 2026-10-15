"""Các công cụ chẩn đoán. Tất cả chỉ đọc: kết nối được đặt read-only."""
import json
import os
import re

from app.common import KNOWLEDGE_DIR, pg_connect


class ToolBox:
    def __init__(self):
        self.conn = pg_connect(app_name="dbot-worker")
        self.conn.execute("SET default_transaction_read_only = on")
        self.conn.execute("SET statement_timeout = '15s'")
        self.calls = []  # nhật ký: công cụ, đầu vào, quan sát

    def close(self):
        self.conn.close()

    def _q(self, sql, params=None):
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            cols = [c.name for c in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]

    def _log(self, tool, inp, out):
        text = out if isinstance(out, str) else json.dumps(out, ensure_ascii=False, default=str)
        self.calls.append({"tool": tool, "input": inp, "observation": text[:2000]})
        return text[:4000]

    # --- công cụ ---
    def explain_query(self, sql: str) -> str:
        s = re.sub(r"\bperform\b", "SELECT", (sql or "").strip().rstrip(";"), flags=re.I)
        m = re.search(r"(select\s.+?)(?:;|\bend\s+loop\b)", s, re.I | re.S)
        if s.lower().startswith("do") and m:
            s = m.group(1)  # lấy câu SELECT bên trong khối DO
        s = re.sub(r"\binto\s+\w+\s+", " ", s, flags=re.I)
        if not re.match(r"^(select|with)\s", s, re.I):
            return self._log("explain_query", sql, "Chỉ EXPLAIN câu SELECT. Không có câu SELECT để phân tích.")
        try:
            plan = "\n".join(r["QUERY PLAN"] for r in self._q("EXPLAIN " + s))
        except Exception as e:  # noqa: BLE001
            plan = f"EXPLAIN lỗi: {e}"
        return self._log("explain_query", s, plan)

    def get_locks(self) -> str:
        r = self._q("""
            SELECT a.pid, a.application_name, a.state, a.wait_event_type,
                   pg_blocking_pids(a.pid) AS blocked_by,
                   round(extract(epoch FROM now() - a.xact_start)::numeric, 1) AS xact_sec,
                   left(a.query, 200) AS query
            FROM pg_stat_activity a
            WHERE a.backend_type = 'client backend' AND a.application_name NOT LIKE 'dbot-%'
              AND (cardinality(pg_blocking_pids(a.pid)) > 0
                   OR a.pid IN (SELECT unnest(pg_blocking_pids(pid)) FROM pg_stat_activity)
                   OR a.xact_start < now() - interval '5 seconds')""")
        ungranted = self._q("SELECT count(*) AS n FROM pg_locks WHERE NOT granted")[0]["n"]
        return self._log("get_locks", "", {"sessions": r, "ungranted_locks": ungranted})

    def get_activity(self) -> str:
        r = self._q("""
            SELECT pid, usename, application_name, state, wait_event_type, wait_event,
                   round(extract(epoch FROM now() - query_start)::numeric, 1) AS query_sec,
                   left(query, 200) AS query
            FROM pg_stat_activity
            WHERE backend_type = 'client backend' AND application_name NOT LIKE 'dbot-%'
            ORDER BY query_start NULLS LAST LIMIT 20""")
        return self._log("get_activity", "", r)

    def get_table_stats(self, table: str = "tpch.lineitem") -> str:
        schema, _, name = table.rpartition(".")
        schema = schema or "tpch"
        st = self._q("""
            SELECT seq_scan, idx_scan, n_live_tup, n_dead_tup, last_autovacuum, last_vacuum,
                   pg_size_pretty(pg_total_relation_size(relid)) AS total_size
            FROM pg_stat_user_tables WHERE schemaname=%s AND relname=%s""", (schema, name))
        idx = self._q("SELECT indexname, indexdef FROM pg_indexes WHERE schemaname=%s AND tablename=%s",
                      (schema, name))
        opts = self._q("""SELECT c.reloptions FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                          WHERE n.nspname=%s AND c.relname=%s""", (schema, name))
        return self._log("get_table_stats", table, {"stats": st, "indexes": idx,
                                                     "reloptions": opts[0]["reloptions"] if opts else None})

    def get_top_statements(self) -> str:
        r = self._q("""SELECT left(query, 200) AS query, calls, round(mean_exec_time::numeric, 2) AS mean_ms,
                              round(total_exec_time::numeric) AS total_ms
                       FROM pg_stat_statements ORDER BY total_exec_time DESC LIMIT 5""")
        return self._log("get_top_statements", "", r)

    def search_knowledge(self, query: str) -> str:
        words = set(re.findall(r"\w+", (query or "").lower()))
        best = []
        for fn in sorted(os.listdir(KNOWLEDGE_DIR)):
            if fn.endswith(".md"):
                text = open(os.path.join(KNOWLEDGE_DIR, fn), encoding="utf-8").read()
                score = sum(text.lower().count(w) for w in words if len(w) > 2)
                score += 20 * sum(1 for w in words if w in fn)
                best.append((score, fn, text))
        best.sort(reverse=True)
        out = "\n\n".join(f"[{fn}]\n{text}" for s, fn, text in best[:2] if s > 0) or "Không tìm thấy tri thức phù hợp."
        return self._log("search_knowledge", query, out)
