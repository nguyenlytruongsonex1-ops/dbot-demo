# D-Bot Light — realtime database diagnosis with CrewAI

D-Bot Light là bản demo một máy lấy cảm hứng từ paper **LLM As DBA / D-Bot** và repo `TsinghuaDatabaseGroup/DB-GPT`. Nó minh họa hai luồng:

```text
Realtime: scenario/workload → PostgreSQL → Prometheus → Alertmanager → D-Bot webhook
User chat: incident → hỏi tự nhiên → D-Bot dùng incident context để giải thích/điều tra thêm
```

D-Bot không tự sửa database. Các action như tạo index, VACUUM hoặc terminate session chỉ là recommendation và luôn yêu cầu human approval.

## Chạy nhanh nhất

### Bước 1 — Chuẩn bị

Cài Docker Desktop hoặc Docker Engine + Compose v2. Không cần Python và không cần API key nếu dùng mock mode.

```bash
git clone https://github.com/nguyenlytruongsonex1-ops/dbot-demo.git
cd dbot-demo
cp .env.example .env
```

### Bước 2 — Khởi động

```bash
docker compose up --build -d
```

Chờ khoảng 30–60 giây, sau đó mở:

- D-Bot UI: <http://localhost:8000>
- Prometheus: <http://localhost:9090>
- Alertmanager: <http://localhost:9093>

Kiểm tra service:

```bash
curl http://localhost:8000/health
```

### Bước 3 — Test realtime + chat

1. Mở <http://localhost:8000>.
2. Ở cột **Trigger demo workload**, bấm `lock_contention` hoặc `slow_query`.
3. Prometheus sẽ evaluate rule sau vài giây.
4. Alertmanager gửi alert tới D-Bot webhook.
5. Incident xuất hiện trong UI.
6. Chọn incident và hỏi:

```text
Session nào đang block?
Có chắc là do thiếu index không?
Có nên terminate blocker không?
```

7. Bấm **Clear all scenarios** để dọn trạng thái demo.

### Bước 4 — Xem log realtime

```bash
docker compose logs -f dbot alertmanager prometheus
```

### Dừng và reset

```bash
docker compose down
```

Xóa cả database/metrics volumes để chạy lại từ đầu:

```bash
docker compose down -v
```

## Các scenario

| Scenario | Trigger | Alert | D-Bot tools chính |
|---|---|---|---|
| `slow_query` | Tạo tín hiệu latency cao và reset query stats | `PostgresHighQueryLatency` | `get_slow_queries`, `get_indexes`, `get_active_sessions` |
| `lock_contention` | Session A giữ lock trên `accounts.id=1` | `PostgresBlockedSessions` | `get_locks`, `get_active_sessions` |
| `workload_contention` | Tạo tín hiệu 12 active sessions | `PostgresWorkloadContention` | `get_active_sessions`, `get_system_metrics`, `get_slow_queries` |
| `table_bloat` | Update nhiều rows rồi `ANALYZE` | `PostgresDeadTupleRatioHigh` | `get_table_statistics` |
| `execution_error` | Chạy query tham chiếu cột không tồn tại | `PostgresExecutionErrors` | evidence từ incident + sessions |

Các trigger là workload/anomaly **chỉ dành cho database demo**. Trong môi trường thật, application workload tạo anomaly và D-Bot chỉ quan sát/chẩn đoán.

## Chạy bằng CLI

Trigger scenario:

```bash
docker compose exec dbot python -m scenarios.run trigger lock_contention
```

Xem state:

```bash
docker compose exec dbot python -m scenarios.run state
```

Clear:

```bash
docker compose exec dbot python -m scenarios.run clear
```

Chạy diagnosis thủ công, không cần chờ alert:

```bash
curl -X POST http://localhost:8000/api/diagnose \
  -H 'content-type: application/json' \
  -d '{"scenario":"slow_query","prepare":true}'
```

Xem incidents:

```bash
curl http://localhost:8000/api/incidents
```

Gửi user chat vào incident:

```bash
curl -X POST http://localhost:8000/api/incidents/<INCIDENT_ID>/chat \
  -H 'content-type: application/json' \
  -d '{"message":"Có chắc là do thiếu index không?"}'
```

## CrewAI và LLM mode

### Mock mode mặc định

`.env` mặc định:

```dotenv
LLM_MODE=mock
```

Mock mode vẫn chạy đủ topology:

- Chief DBA;
- CPU/Workload Agent;
- Memory/Database Agent;
- database tools;
- diagnosis report;
- realtime webhook;
- user chat.

Phần kết luận dùng evidence rules để demo nhanh, tái lập và không tốn API cost.

### OpenAI-compatible mode

Để dùng CrewAI và LLM chat thật:

```dotenv
LLM_MODE=openai
OPENAI_API_KEY=your-key
OPENAI_MODEL_NAME=gpt-4o-mini
```

Nếu dùng local OpenAI-compatible server:

```dotenv
OPENAI_API_BASE=http://host.docker.internal:1234/v1
```

Khởi động lại:

```bash
docker compose up --build -d
```

## Kiến trúc

```text
┌──────────────┐     ┌──────────────┐     ┌───────────────┐
│ PostgreSQL   │────►│ D-Bot /metrics│────►│ Prometheus    │
└──────┬───────┘     └──────┬───────┘     └──────┬────────┘
       │                    │                    ▼
       │                    │             ┌───────────────┐
       │                    └────────────►│ Alertmanager  │
       │                                  └──────┬────────┘
       │                                         │ webhook
       ▼                                         ▼
┌─────────────────────────────────────────────────────────┐
│ D-Bot FastAPI                                           │
│ incident store → CrewAI agents → evidence report → chat │
└─────────────────────────────────────────────────────────┘
```

### Services

- `postgres`: database demo, `pg_stat_statements`, sample tables.
- `dbot`: FastAPI, UI, Prometheus exporter, CrewAI, tools, incident store.
- `prometheus`: scrape `/metrics` và evaluate alert rules.
- `alertmanager`: group/deduplicate `firing/resolved` alerts và POST webhook.

## API chính

- `GET /health`
- `GET /metrics`
- `GET /api/scenarios`
- `POST /api/scenarios/{name}/trigger`
- `POST /api/scenarios/clear`
- `POST /api/diagnose`
- `GET /api/incidents`
- `GET /api/incidents/{id}`
- `POST /api/incidents/{id}/chat`
- `POST /webhooks/alertmanager`
- `GET /api/tools`

## Test local source

Nếu máy đã có Python:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
pytest -q
python -m compileall -q app scenarios tests
```

Test container:

```bash
docker compose config
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:8000/metrics
```

## Safety

Chỉ chạy artifact với database demo. D-Bot Light mặc định dùng read-only diagnostic tools. Scenario runner có thể tạo lock, update rows và trạng thái demo. Không trỏ Compose này vào database production.

## Giới hạn có chủ ý

Đây là **minimal D-Bot reconstruction**, không phải production DBA. Bản Light chưa có vector database, Kubernetes, fine-tuning, distributed tracing, hoặc auto-remediation. Realtime detection dùng Prometheus rules; D-Bot vẫn cần database tools để xác minh root cause.

## Tài liệu

- `docs/d-bot-paper-notes.md` — mapping với paper.
- `docs/testing.md` — test và demo flow.
- `docs/light-version.md` — kiến trúc light version.
- `data/experiences.json` — maintenance experience seed.

## License

MIT.
