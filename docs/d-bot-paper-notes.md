# D-Bot paper notes and implementation mapping

The reference paper describes an LLM-based database administrator with two broad stages:

1. Preparation: documents become maintenance experience, and diagnosis examples become prompt templates.
2. Maintenance: the system retrieves tools, interacts with database metrics/views, reasons over possible root causes, and lets specialized agents collaborate.

This repository maps those ideas as follows:

| Paper idea | Demo implementation |
|---|---|
| Documents -> experience | `data/experiences.json` and `app/knowledge/retriever.py` |
| Observation tools | `app/tools/postgres_tools.py` and `app/tools/system_tools.py` |
| Tool retrieval | Lightweight token-overlap retrieval |
| Tree-of-thought diagnosis | Bounded evidence collection/state path in `orchestrator.py` |
| Collaborative diagnosis | CrewAI Chief DBA, CPU/Workload and Memory/Database roles |
| Metrics and views | PostgreSQL `pg_stat_activity`, `pg_locks`, `pg_stat_statements`, `pg_stat_user_tables`, `pg_indexes` |
| Optimization advice | Advisory recommendations only; mutations are never auto-executed |

The MVP intentionally replaces the paper's larger preparation pipeline and full UCT search with deterministic components. This makes the demo reproducible on one laptop and provides a stable baseline before adding more complex retrieval, prompt optimization, or model debate.

## Expected limits

- The mock mode is not an LLM benchmark. It validates the end-to-end plumbing and safety boundaries.
- PostgreSQL metrics depend on workload size and local hardware, so timing values are not fixed.
- A real LLM may produce a better narrative, but its output is still wrapped by the same read-only tools and should be reviewed by a human.
