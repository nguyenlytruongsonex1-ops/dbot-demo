# Testing D-Bot Light

## Fast smoke test

```bash
docker compose up --build -d
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:8000/metrics
curl -fsS http://localhost:9090/-/ready
curl -fsS http://localhost:9093/-/ready
```

Open `http://localhost:8000`, trigger `lock_contention`, wait 10–20 seconds, then select the incident and send a chat message.

## API-only realtime test

```bash
curl -X POST http://localhost:8000/api/scenarios/lock_contention/trigger
sleep 15
curl http://localhost:8000/api/incidents
```

The incident should have `source: alertmanager` and `status: firing`.

Then ask a question using the incident ID returned by `/api/incidents`:

```bash
curl -X POST http://localhost:8000/api/incidents/<INCIDENT_ID>/chat \
  -H 'content-type: application/json' \
  -d '{"message":"Session nào đang block và có nên terminate không?"}'
```

Clear demo state:

```bash
curl -X POST http://localhost:8000/api/scenarios/clear
```

## Scenario matrix

| Scenario | Realtime signal | Evidence expected |
|---|---|---|
| slow_query | `dbot_demo_query_latency_ms > 500` | slow queries, indexes, active sessions |
| lock_contention | `dbot_demo_lock_waiters > 0` | blocked and blocking sessions |
| workload_contention | `dbot_demo_active_sessions > 8` | sessions, system metrics, slow queries |
| table_bloat | `dbot_demo_dead_tuple_ratio > 0.02` | live/dead tuples and vacuum timestamps |
| execution_error | `dbot_demo_execution_errors > 0` | incident error context |

## Python tests

```bash
pip install -e .
pytest -q
python -m compileall -q app scenarios tests
```

## Troubleshooting

If an alert does not appear, inspect:

```bash
docker compose logs -f prometheus alertmanager dbot
```

Check the target at `http://localhost:9090/targets` and query the metric directly:

```promql
dbot_demo_lock_waiters
dbot_demo_query_latency_ms
dbot_demo_active_sessions
dbot_demo_dead_tuple_ratio
dbot_demo_execution_errors
```

If the database volume already existed before a schema change, reset it:

```bash
docker compose down -v
docker compose up --build -d
```
