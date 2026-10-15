# D-Bot Demo trên PostgreSQL, giao diện Streamlit có giám sát realtime

Đây là bản demo để học, dựng lại ý tưởng của bài báo D-Bot (arXiv 2312.01454) ở mức nhẹ.
Hệ thống gây sự cố thật trên PostgreSQL, tự phát hiện bất thường, rồi tự nhờ AI phân tích.

Bản này tích hợp dự án "LLM As DBA" của Nhóm 3 (bản gốc dùng MySQL 8 và Streamlit).
Ba kịch bản trình diễn từng bước, cách hỏi AI theo prompt A và B, cách chấm điểm và Mini λ-Tune
được chuyển từ dự án đó sang PostgreSQL. Xin cảm ơn Nhóm 3.

## Hệ thống gồm gì

- `postgres`: PostgreSQL 16, bật `pg_stat_statements`.
- `tpch-seed`: sinh dữ liệu TPC-H SF 0.1 (khoảng 100 MB) bằng `dbgen` rồi nạp vào DB. Chỉ chạy một lần.
- `monitor`: quét DB mỗi 5 giây, tạo alert khi vượt ngưỡng.
- `backend`: API nội bộ (FastAPI). Chạy và dừng kịch bản, lưu cài đặt.
- `dbot-worker`: tự nhận alert mới và phân tích bằng CrewAI.
- `streamlit`: giao diện duy nhất, ở cổng 8501.

Alert và báo cáo lưu trong SQLite, nên mở lại trang vẫn còn.

## Các tab trên giao diện

- Tab 0, Chuẩn bị: kiểm tra kết nối, dữ liệu và nguồn LLM.
- Tab 1, Thiếu index: chạy 50 truy vấn theo `l_partkey`, đo, hỏi AI, tạo index, đo lại.
- Tab 2, Truy vấn con tương quan: chạy bản chậm, xem `EXPLAIN` có `SubPlan`, viết lại bằng JOIN.
- Tab 3, Tranh chấp khóa: phiên A giữ khóa, phiên B bị chặn, phiên C quan sát, rồi ROLLBACK.
- Tab 4, Mini λ-Tune: AI đề xuất cấu hình, hệ thống chỉ chạy lệnh được cho phép, rồi đo thật.
- Tab 5, Giám sát realtime: chạy kịch bản, xem alert và báo cáo. Mọi thứ chạy tự động.
- Tab 6, Tổng kết: bảng chấm điểm AI và số đo trước, sau khi sửa.

Ở tab 1 đến 3, prompt A chỉ kể triệu chứng. Prompt B làm theo kiểu D-Bot, có thẻ kinh nghiệm và số đo thật.
Câu trả lời được chấm tự động bằng từ khóa. Bạn có thể sửa điểm bằng tay.

## Luồng tự động ở tab 5

1. Bạn bấm Chạy một kịch bản, hoặc có sự cố thật trên DB.
2. Monitor thấy dấu hiệu vượt ngưỡng và tạo alert.
3. Sau khoảng 20 giây, nếu dấu hiệu vẫn còn, worker tự phân tích alert đó.
4. Mỗi alert chỉ phân tích một lần. Mỗi lúc chỉ chạy một phân tích.
5. Trang tự làm mới mỗi 3 giây. Trạng thái đi từ "chờ phân tích" sang "đang phân tích" rồi "đã có báo cáo".
6. Khi sự cố hết, sau 3 lần quét sạch, alert chuyển sang "đã giải quyết".

Công tắc "Tự động phân tích" mặc định bật. Tắt đi thì bạn tự bấm nút "Phân tích".
Nút "Phân tích lại" cho phép chọn nguồn LLM khác.

AI chỉ đề xuất. Công cụ của worker chỉ có quyền đọc. DBA tự quyết định có chạy lệnh sửa hay không.

## Cài đặt

Cần có:

- Docker Desktop (hoặc Docker Engine) có `docker compose`.
- Ollama, nếu muốn chạy LLM trên máy. Không bắt buộc nếu bạn có API key.

### Bước 1. Cài Ollama và tải model

Tải Ollama tại https://ollama.com rồi chạy:

```bash
ollama pull qwen2.5:7b
```

Trên Linux, cho Ollama nghe ở mọi địa chỉ để container gọi được:

```bash
sudo systemctl edit ollama
# thêm 2 dòng:
# [Service]
# Environment="OLLAMA_HOST=0.0.0.0"
sudo systemctl restart ollama
```

Trên Windows và macOS không cần bước này.

### Bước 2. Tải mã nguồn và tạo file .env

```bash
git clone -b feature/realtime-streamlit-pg https://github.com/nguyenlytruongsonex1-ops/dbot-demo.git
cd dbot-demo
cp .env.example .env
```

Nếu có API key, điền vào `.env`: `ANTHROPIC_API_KEY`, `GEMINI_API_KEY` hoặc `OPENAI_API_KEY`.
Chọn nguồn mặc định bằng `LLM_PROVIDER` (claude, gemini, openai, ollama, mock).
Nếu thiếu key hoặc gọi lỗi, hệ thống tự chuyển sang Ollama.
Không commit file `.env`.

### Bước 3. Chạy

```bash
docker compose up --build -d
```

Lần đầu mất vài phút để build và sinh dữ liệu. Sau đó mở http://localhost:8501.

Xem log:

```bash
docker compose logs -f monitor dbot-worker
```

Dừng hệ thống:

```bash
docker compose down        # giữ dữ liệu
docker compose down -v     # xóa cả dữ liệu
```

## Các kịch bản có sẵn

Các file nằm trong thư mục `scenarios/`. Đầu mỗi file có chú thích về sự cố và cách xử lý.

| Kịch bản | Sự cố | Cách xử lý mong đợi |
|---|---|---|
| `cpu_high` | Lặp 50 lần truy vấn tổng hợp nặng trên `lineitem` | Hủy query, đặt `statement_timeout` |
| `missing_index` | Tìm `lineitem` theo `l_partkey` 10000 lần | `CREATE INDEX` trên `l_partkey` |
| `correlated_subquery` | Truy vấn con tương quan trên `orders` | Viết lại bằng JOIN, hoặc index `o_custkey` |
| `lock_holder` | Giữ khóa dòng 120 giây | Kết thúc phiên giữ khóa |
| `lock_waiter` | Cập nhật cùng dòng, bị chặn | Đặt `lock_timeout` |
| `idle_in_transaction` | Mở transaction 90 giây không commit | Đặt `idle_in_transaction_session_timeout` |
| `table_bloat` | Tắt autovacuum, cập nhật toàn bảng 3 lần | `VACUUM`, bật lại autovacuum |
| `fix_vacuum` | Dọn sau `table_bloat`, không phải sự cố | Không áp dụng |

Kịch bản khóa: chạy `lock_holder` trước, rồi `lock_waiter`.
Kịch bản bloat: alert chỉ hết sau khi chạy `fix_vacuum`.

## Thêm kịch bản mới

Ở tab 5, mở mục "Thêm kịch bản bằng file .sql".
Nhập tên (chữ thường, số, dấu gạch dưới) và chọn file `.sql` (UTF-8, tối đa 200 KB).

Kịch bản chạy bằng user `scenario_runner`. User này chỉ có quyền trên schema `tpch`.
Mỗi câu lệnh bị giới hạn 10 phút. Mỗi câu lệnh trong file chạy lần lượt trên một kết nối.

Ví dụ:

```sql
-- Kịch bản: sort_lon (sắp xếp bảng lớn)
SELECT * FROM tpch.lineitem ORDER BY l_comment;
```

## Chạy không dùng Docker (cho người phát triển)

Cần PostgreSQL 16 trở lên có `pg_stat_statements`, và Python 3.11.

```bash
psql -U dbot -d dbot_demo -f db/init/01_init.sql
PGHOST=localhost PGUSER=dbot PGPASSWORD=dbot PGDATABASE=dbot_demo DBGEN_DIR=/duong/dan/dbgen sh seed/seed.sh
pip install -r requirements.txt -r requirements-worker.txt
export PG_HOST=localhost LLM_PROVIDER=mock SQLITE_PATH=data/dbot.sqlite
uvicorn app.backend:app --port 8000 &
python -m app.monitor &
python -m app.worker &
streamlit run app/ui/streamlit_app.py
```

## Xử lý lỗi thường gặp

- Trang báo "Không gọi được backend": chờ thêm vì `tpch-seed` có thể chưa xong. Xem `docker compose logs tpch-seed`.
- Báo cáo ghi "Ollama lỗi": kiểm tra `ollama list` có `qwen2.5:7b`. Trên Linux, kiểm tra `OLLAMA_HOST=0.0.0.0`.
- Phân tích rất chậm: model 7B trên CPU mất 1 đến 3 phút mỗi alert. Dùng API key hoặc model nhỏ hơn như `qwen2.5:3b`.
- Cổng 5432 hoặc 8501 đã bị dùng: đổi `PG_PORT_HOST` hoặc `UI_PORT` trong `.env`.
- Muốn sinh lại dữ liệu: `docker compose down -v` rồi `docker compose up --build -d`.
- Alert không tự hết sau `table_bloat`: chạy kịch bản `fix_vacuum`.
- Thử luồng mà không cần LLM: đặt `LLM_PROVIDER=mock` trong `.env`.

## Hạn chế

- Luật phát hiện dựa trên ngưỡng cố định, đôi khi báo trùng.
- Monitor không đo CPU của máy. Alert CPU được suy ra từ phiên đang chạy mà không phải chờ.
- Tab 4 chỉ chỉnh tham số ở mức phiên và tạo index. `shared_buffers` cần khởi động lại nên không đưa vào.
- Tab 4 xóa mọi index phụ trên `lineitem`, `orders`, `customer`, `part` trước và sau mỗi lần đo.

## Ghi công

- Bài báo D-Bot: Zhou và cộng sự, arXiv 2312.01454. Repo gốc: TsinghuaDatabaseGroup/DB-GPT.
- λ-Tune: Giannakouris và Trummer.
- Dự án "LLM As DBA" của Nhóm 3: luồng trình diễn tab 1 đến 4, prompt A và B, thẻ kinh nghiệm, chấm điểm tự động và Mini λ-Tune.
- Dữ liệu TPC-H sinh bằng tpch-kit (gregrahn/tpch-kit).

Báo cáo tổng hợp: `docs/bao-cao-dbot-demo.docx`.
