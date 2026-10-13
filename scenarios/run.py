import argparse
import json
import sys
import time
from app.db import execute, fetch_all

SCENARIOS = ["slow_query", "lock_contention", "workload_contention", "table_bloat", "execution_error"]

def prepare(name: str) -> dict:
    if name == "slow_query":
        rows = fetch_all("SELECT count(*) AS rows, min(created_at) AS oldest FROM orders WHERE status = 'paid'")
        return {"scenario": name, "prepared": True, "hint": "Run diagnosis; use EXPLAIN on a query filtering customer_id and created_at", "seed": rows}
    if name == "lock_contention":
        execute("UPDATE accounts SET balance = balance WHERE id = 1")
        return {"scenario": name, "prepared": True, "hint": "Use two terminals: run scripts/lock_holder.sql then scripts/lock_waiter.sql"}
    if name == "workload_contention":
        return {"scenario": name, "prepared": True, "hint": "The diagnosis inspects current active sessions; run several pg_sleep sessions for a visible signal"}
    if name == "table_bloat":
        execute("UPDATE orders SET status = status WHERE id <= 20000")
        execute("DELETE FROM orders WHERE id > 99990")
        return {"scenario": name, "prepared": True, "hint": "Dead tuples should be visible in pg_stat_user_tables after stats refresh"}
    if name == "execution_error":
        return {"scenario": name, "prepared": True, "hint": "The probe deliberately runs a missing-column query and classifies the error"}
    raise ValueError(f"Unknown scenario: {name}")

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", nargs="?")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()
    if args.list:
        print("\n".join(SCENARIOS)); return
    if not args.scenario:
        parser.error("provide a scenario or --list")
    print(json.dumps(prepare(args.scenario), default=str, indent=2))

if __name__ == "__main__":
    main()
