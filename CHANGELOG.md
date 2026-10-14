# Changelog

## 0.2.0

- Added per-scenario stop and an incident-list clear action on the dashboard.
- Kept chat input text across the five-second UI refresh.
- Used structured CrewAI findings for root cause and recommendation when LLM mode is openai. Mock mode stays deterministic.
- Sent OpenAI-compatible base URLs, including Gemini, through the CrewAI client.
- Added D-Bot Light dashboard UI.
- Added Prometheus metrics endpoint and alert rules.
- Added Alertmanager webhook receiver and incident store.
- Added scenario trigger/clear API and CLI.
- Added incident-bound DBA chat.
- Added realtime testing guide.

## 0.1.0

- Initial single-machine D-Bot demo.
- PostgreSQL 16 Compose service with sample workload.
- CrewAI multi-role factory.
- Read-only PostgreSQL/system tools.
- Deterministic mock mode and optional OpenAI-compatible mode.
- FastAPI API/UI, CLI, scenarios, tests, and documentation.
