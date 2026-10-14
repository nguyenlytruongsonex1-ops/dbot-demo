import threading
import time
from typing import Any
from app.db import execute, fetch_all, connection

SCENARIOS = ["slow_query", "lock_contention", "workload_contention", "table_bloat", "execution_error"]
_lock_thread: threading.Thread | None = None
_waiter_thread: threading.Thread | None = None
_lock_stop = threading.Event()
_lock_conn = None
_lock_cm = None


def _set_state(name: str, active: bool, metric: float = 0, detail: str = "") -> None:
    execute("""
      INSERT INTO demo_scenario_state(scenario, active, metric_value, detail, updated_at)
      VALUES (%s, %s, %s, %s, now())
      ON CONFLICT (scenario) DO UPDATE SET active=excluded.active,
        metric_value=excluded.metric_value, detail=excluded.detail, updated_at=now()
    """, (name, active, metric, detail))


def state() -> list[dict[str, Any]]:
    return fetch_all("SELECT scenario, active, metric_value, detail, updated_at FROM demo_scenario_state ORDER BY scenario")


def trigger(name: str) -> dict[str, Any]:
    if name not in SCENARIOS:
        raise ValueError(f"unknown scenario: {name}")
    if name == "slow_query":
        # Keep this safe and deterministic: the state signal drives the alert;
        # the diagnosis still reads pg_stat_activity/pg_stat_statements/EXPLAIN.
        try:
            execute("SELECT pg_stat_statements_reset()")
        except Exception:
            pass
        _set_state(name, True, 1200, "simulated high query latency; run the UI diagnosis")
    elif name == "lock_contention":
        start_lock_holder()
        _set_state(name, True, 1, "session A holds an UPDATE lock on accounts.id=1")
    elif name == "workload_contention":
        _set_state(name, True, 12, "simulated 12 active sessions; inspect current sessions for evidence")
    elif name == "table_bloat":
        execute("UPDATE orders SET status = status WHERE id <= 20000")
        execute("ANALYZE orders")
        _set_state(name, True, 0.08, "updates created dead tuples; inspect pg_stat_user_tables")
    elif name == "execution_error":
        try:
            execute("SELECT missing_demo_column FROM orders LIMIT 1")
        except Exception as exc:
            _set_state(name, True, 1, f"captured PostgreSQL execution error: {exc}")
    return {"scenario": name, "active": True, "state": next(x for x in state() if x["scenario"] == name)}


def clear(name: str | None = None) -> dict[str, Any]:
    names = [name] if name else SCENARIOS
    for item in names:
        if item not in SCENARIOS:
            raise ValueError(f"unknown scenario: {item}")
        _set_state(item, False, 0, "cleared")
    if name in (None, "lock_contention"):
        stop_lock_holder()
    return {"cleared": names, "state": state()}


def start_lock_holder() -> None:
    global _lock_thread, _waiter_thread
    if _lock_thread and _lock_thread.is_alive():
        return
    _lock_stop.clear()
    def hold() -> None:
        global _lock_conn, _lock_cm
        try:
            _lock_cm = connection()
            _lock_conn = _lock_cm.__enter__()
            with _lock_conn.cursor() as cur:
                cur.execute("BEGIN")
                cur.execute("UPDATE accounts SET balance = balance + 1 WHERE id = 1")
                while not _lock_stop.wait(0.5):
                    pass
                cur.execute("ROLLBACK")
        except Exception:
            pass
        finally:
            if _lock_conn is not None:
                try:
                    _lock_cm.__exit__(None, None, None)
                except Exception: pass
                _lock_conn = None
                _lock_cm = None
    _lock_thread = threading.Thread(target=hold, name="dbot-lock-holder", daemon=True)
    _lock_thread.start()
    time.sleep(0.5)

    def wait() -> None:
        try:
            with connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("UPDATE accounts SET balance = balance + 2 WHERE id = 1")
                conn.commit()
        except Exception:
            pass
    _waiter_thread = threading.Thread(target=wait, name="dbot-lock-waiter", daemon=True)
    _waiter_thread.start()
    time.sleep(0.5)


def stop_lock_holder() -> None:
    global _lock_thread, _waiter_thread
    _lock_stop.set()
    if _lock_thread and _lock_thread.is_alive():
        _lock_thread.join(timeout=3)
    _lock_thread = None
    if _waiter_thread and _waiter_thread.is_alive():
        _waiter_thread.join(timeout=3)
    _waiter_thread = None
