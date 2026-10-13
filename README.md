# D-Bot Demo — CrewAI Database Administrator

A lightweight, single-machine demo inspired by the paper **LLM As DBA / D-Bot**. It uses PostgreSQL, CrewAI roles, read-only diagnostic tools, a small experience knowledge base, and reproducible anomaly scenarios.

## What is included

- PostgreSQL 16 in Docker Compose.
- FastAPI service with a small browser UI.
- CrewAI `Chief DBA`, `CPU/Workload Agent`, and `Memory/Database Agent` roles.
- Read-only tools for sessions, locks, slow queries, table statistics, indexes, and `EXPLAIN`.
- Deterministic `mock` mode: works without an LLM API key.
- Optional `openai` mode for real CrewAI reasoning.
- Scenarios for slow query, lock contention, workload contention, table bloat, and execution errors.
- Pytest tests and structured JSON diagnosis reports.

## Prerequisites

- Docker Desktop or Docker Engine + Docker Compose v2.
- 4 GB RAM recommended.
- For real LLM mode: an OpenAI-compatible API key.

The repository can be run entirely in `mock` mode first. No API key is required for the smoke demo.

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

Open <http://localhost:8000>.

Health check:

```bash
curl http://localhost:8000/health
```

Run a diagnosis through the API:

```bash
curl -X POST http://localhost:8000/api/diagnose \
  -H 'content-type: application/json' \
  -d '{"scenario":"slow_query"}'
```

Run a scenario directly inside the container:

```bash
docker compose exec dbot python -m scenarios.run slow_query
```

List scenarios:

```bash
docker compose exec dbot python -m scenarios.run --list
```

## Real LLM mode

Edit `.env`:

```dotenv
LLM_MODE=openai
OPENAI_API_KEY=your-key
OPENAI_MODEL_NAME=gpt-4o-mini
```

For an OpenAI-compatible local server, set `OPENAI_API_BASE` to its `/v1` endpoint and make sure the container can reach it. On Docker Desktop, a host service is commonly reachable as `http://host.docker.internal:PORT/v1`.

Then restart:

```bash
docker compose up --build -d
docker compose logs -f dbot
```

CrewAI is used in the real mode. In mock mode the same agent/tool topology is retained, but the final decision is produced by deterministic evidence rules so the demo remains reproducible and free of API costs.

## Scenarios

| Scenario | Command | Expected finding |
|---|---|---|
| Slow query | `slow_query` | Missing index or expensive plan |
| Lock contention | `lock_contention` | Blocking and waiting sessions |
| Workload contention | `workload_contention` | High active sessions / long-running workload |
| Table bloat | `table_bloat` | Dead tuples and vacuum recommendation |
| Execution error | `execution_error` | PostgreSQL error classification |

The scenario scripts are safe for a disposable demo database. They do not automatically create indexes, terminate sessions, or mutate production systems.

## Local development without Docker

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
cp .env.example .env
# Set DB_* to a local PostgreSQL instance
uvicorn app.api.server:app --reload
pytest -q
```

## Useful API endpoints

- `GET /health` — service and database health.
- `GET /api/scenarios` — available scenarios.
- `GET /api/tools` — registered diagnostic tools.
- `POST /api/scenarios/{name}/prepare` — create the selected anomaly.
- `POST /api/diagnose` — diagnose an anomaly.
- `GET /api/reports` — recent JSON reports.

## Reset everything

```bash
docker compose down -v
```

The `-v` flag removes the demo database volume. Start again with `docker compose up --build` to run the initialization scripts from scratch.

## Safety

All diagnostic tools are read-only. Recommendations are returned as text and are never applied automatically. Do not point this demo at a production database. Use a disposable PostgreSQL instance.

## Architecture

```text
Browser/CLI -> FastAPI -> Diagnosis Orchestrator -> CrewAI roles
                                      |              |
                                      |              +-- Chief DBA
                                      |              +-- CPU/Workload Agent
                                      |              +-- Memory/Database Agent
                                      |
                                      +-> PostgreSQL read-only tools
                                      +-> Experience JSON / BM25-like retrieval
```

## References

- D-Bot paper: `docs/d-bot-paper-notes.md`.
- CrewAI official docs: <https://docs.crewai.com/>.
- Docker Compose service reference: <https://docs.docker.com/reference/compose-file/services/>.
