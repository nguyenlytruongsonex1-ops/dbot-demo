# D-Bot Light architecture

## Two complementary flows

```text
Realtime:
scenario/application workload -> PostgreSQL -> /metrics -> Prometheus -> Alertmanager -> /webhooks/alertmanager

User chat:
incident context -> natural-language question -> D-Bot chat engine -> evidence-aware answer
```

Realtime answers: **what looks abnormal and when did it start?**

User chat answers: **why, what else should we check, what are the trade-offs, and should a human approve an action?**

## Service map

| Service | Responsibility |
|---|---|
| PostgreSQL | Demo database, views and `pg_stat_statements` |
| D-Bot | API, UI, tools, metrics exporter, incident store and CrewAI |
| Prometheus | Scrape and evaluate alert rules |
| Alertmanager | Group alerts and send firing/resolved webhooks |

## Trigger boundary

The `scenarios` module exists only to reproduce incidents locally. In a real deployment, application traffic, batch jobs or users create the anomaly. D-Bot should then observe, investigate and report; it should not create production workload.

## Diagnosis boundary

Prometheus tells D-Bot that a signal is abnormal. It does not prove root cause. D-Bot calls read-only database tools and combines their observations with maintenance experience before making a recommendation.

## Chat boundary

The chat endpoint is bound to an incident. It is not a generic SQL chatbot. Every answer receives incident context, root causes, evidence and recommendations. In mock mode it uses deterministic evidence-aware responses; in openai mode it can call the configured OpenAI-compatible model.
