from app.db import fetch_all

def _value(rows, scenario: str) -> float:
    for row in rows:
        if row["scenario"] == scenario and row["active"]:
            return float(row["metric_value"] or 0)
    return 0.0

def render_metrics() -> str:
    try:
        rows = fetch_all("SELECT scenario, active, metric_value FROM demo_scenario_state")
        sessions = fetch_all("""
          SELECT count(*)::int AS n FROM pg_stat_activity
          WHERE datname = current_database() AND state <> 'idle' AND pid <> pg_backend_pid()
        """)[0]["n"]
        lock_waiters = fetch_all("""
          SELECT count(*)::int AS n FROM pg_stat_activity
          WHERE datname = current_database() AND wait_event_type = 'Lock'
        """)[0]["n"]
    except Exception:
        rows, sessions, lock_waiters = [], 0, 0
    latency = _value(rows, "slow_query")
    active_sessions = max(_value(rows, "workload_contention"), float(sessions))
    demo_lock = _value(rows, "lock_contention")
    bloat = _value(rows, "table_bloat")
    errors = _value(rows, "execution_error")
    lines = [
        "# HELP dbot_demo_query_latency_ms Demo query latency signal.",
        "# TYPE dbot_demo_query_latency_ms gauge",
        f"dbot_demo_query_latency_ms {latency}",
        "# HELP dbot_demo_active_sessions Active database sessions or demo signal.",
        "# TYPE dbot_demo_active_sessions gauge",
        f"dbot_demo_active_sessions {active_sessions}",
        "# HELP dbot_demo_lock_waiters Blocked sessions or demo signal.",
        "# TYPE dbot_demo_lock_waiters gauge",
        f"dbot_demo_lock_waiters {max(float(lock_waiters), demo_lock)}",
        "# HELP dbot_demo_dead_tuple_ratio Demo dead tuple ratio signal.",
        "# TYPE dbot_demo_dead_tuple_ratio gauge",
        f"dbot_demo_dead_tuple_ratio {bloat}",
        "# HELP dbot_demo_execution_errors Demo execution error count.",
        "# TYPE dbot_demo_execution_errors gauge",
        f"dbot_demo_execution_errors {errors}",
    ]
    return "\n".join(lines) + "\n"
