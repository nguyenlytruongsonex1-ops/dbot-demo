# Testing and demo script

## Smoke test

```bash
docker compose up --build -d
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:8000/api/tools
curl -fsS -X POST http://localhost:8000/api/diagnose -H 'content-type: application/json' -d '{"scenario":"slow_query"}'
```

## Scenario checks

Run each scenario through the API or UI and confirm:

- the report contains at least one `root_causes` item;
- evidence includes `experience_retrieval` and at least one database tool;
- recommendation has `requires_approval: true`;
- no SQL mutation is executed by the diagnosis endpoint.

## Lock contention manual demo

Terminal A:

```bash
docker compose exec -T postgres psql -U dbot -d dbot_demo < scenarios/lock_holder.sql
```

In another terminal, before the first command finishes:

```bash
docker compose exec -T postgres psql -U dbot -d dbot_demo < scenarios/lock_waiter.sql
curl -fsS -X POST http://localhost:8000/api/diagnose -H 'content-type: application/json' -d '{"scenario":"lock_contention","prepare":false}'
```

The waiter should be visible in `pg_locks` while the holder sleeps.

## Python tests

```bash
pip install -e .
pytest -q
```
