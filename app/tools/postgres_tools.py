import json
from typing import Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from app.db import fetch_all

class EmptyInput(BaseModel):
    pass

class ExplainInput(BaseModel):
    sql: str = Field(description="A SELECT query to explain; mutation statements are rejected")

class PostgresReadTool(BaseTool):
    def _run(self, *args, **kwargs):
        raise NotImplementedError
    def json_result(self, value):
        return json.dumps(value, default=str)

class ActiveSessionsTool(PostgresReadTool):
    name: str = "get_active_sessions"
    description: str = "Read non-idle PostgreSQL sessions, wait events, query text and durations."
    args_schema: Type[BaseModel] = EmptyInput
    def _run(self) -> str:
        rows = fetch_all("""
          SELECT pid, usename, state, wait_event_type, wait_event,
                 now() - query_start AS query_age, left(query, 500) AS query
          FROM pg_stat_activity
          WHERE datname = current_database() AND pid <> pg_backend_pid()
          ORDER BY query_start NULLS LAST
        """)
        return self.json_result(rows)

class LocksTool(PostgresReadTool):
    name: str = "get_locks"
    description: str = "Find blocked and blocking PostgreSQL sessions from pg_locks and pg_stat_activity."
    args_schema: Type[BaseModel] = EmptyInput
    def _run(self) -> str:
        rows = fetch_all("""
          SELECT blocked.pid AS blocked_pid, blocking.pid AS blocking_pid,
                 blocked.wait_event_type, blocked.wait_event,
                 left(blocked.query, 300) AS blocked_query,
                 left(blocking.query, 300) AS blocking_query
          FROM pg_stat_activity blocked
          JOIN pg_locks bl ON bl.pid = blocked.pid AND NOT bl.granted
          JOIN pg_locks kl ON kl.locktype = bl.locktype
            AND kl.database IS NOT DISTINCT FROM bl.database
            AND kl.relation IS NOT DISTINCT FROM bl.relation
            AND kl.page IS NOT DISTINCT FROM bl.page
            AND kl.tuple IS NOT DISTINCT FROM bl.tuple
            AND kl.transactionid IS NOT DISTINCT FROM bl.transactionid
            AND kl.classid IS NOT DISTINCT FROM bl.classid
            AND kl.objid IS NOT DISTINCT FROM bl.objid
            AND kl.objsubid IS NOT DISTINCT FROM bl.objsubid
            AND kl.granted AND kl.pid <> bl.pid
          JOIN pg_stat_activity blocking ON blocking.pid = kl.pid
          WHERE blocked.datname = current_database()
        """)
        return self.json_result(rows)

class SlowQueriesTool(PostgresReadTool):
    name: str = "get_slow_queries"
    description: str = "Read top queries from pg_stat_statements when the extension is available."
    args_schema: Type[BaseModel] = EmptyInput
    def _run(self) -> str:
        try:
            rows = fetch_all("""
              SELECT calls, round(total_exec_time::numeric, 2) AS total_ms,
                     round(mean_exec_time::numeric, 2) AS mean_ms,
                     rows, left(query, 1000) AS query
              FROM pg_stat_statements
              ORDER BY total_exec_time DESC LIMIT 10
            """)
        except Exception as exc:
            rows = [{"error": str(exc), "hint": "pg_stat_statements is not available"}]
        return self.json_result(rows)

class TableStatsTool(PostgresReadTool):
    name: str = "get_table_statistics"
    description: str = "Read live tuples, dead tuples, table size and vacuum timestamps."
    args_schema: Type[BaseModel] = EmptyInput
    def _run(self) -> str:
        rows = fetch_all("""
          SELECT schemaname, relname, n_live_tup, n_dead_tup,
                 round((n_dead_tup::numeric / greatest(n_live_tup + n_dead_tup, 1)), 4) AS dead_ratio,
                 pg_size_pretty(pg_total_relation_size(relid)) AS total_size,
                 last_vacuum, last_autovacuum, last_analyze, last_autoanalyze
          FROM pg_stat_user_tables ORDER BY n_dead_tup DESC
        """)
        return self.json_result(rows)

class IndexesTool(PostgresReadTool):
    name: str = "get_indexes"
    description: str = "List user table indexes and definitions."
    args_schema: Type[BaseModel] = EmptyInput
    def _run(self) -> str:
        return self.json_result(fetch_all("""
          SELECT schemaname, tablename, indexname, indexdef
          FROM pg_indexes ORDER BY schemaname, tablename, indexname
        """))

class ExplainTool(PostgresReadTool):
    name: str = "explain_query"
    description: str = "Run EXPLAIN (FORMAT JSON) for a SELECT/WITH query only; never executes mutations."
    args_schema: Type[BaseModel] = ExplainInput
    def _run(self, sql: str) -> str:
        normalized = sql.strip().lower()
        if not (normalized.startswith("select") or normalized.startswith("with")):
            return self.json_result({"error": "Only SELECT or WITH queries are allowed"})
        if ";" in normalized.rstrip(";"):
            return self.json_result({"error": "Multiple statements are not allowed"})
        return self.json_result(fetch_all("EXPLAIN (FORMAT JSON) " + sql)[0])

def all_tools() -> list[BaseTool]:
    return [ActiveSessionsTool(), LocksTool(), SlowQueriesTool(), TableStatsTool(), IndexesTool(), ExplainTool()]
