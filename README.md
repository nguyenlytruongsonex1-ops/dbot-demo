# D-Bot Demo: bảng theo dõi sự cố PostgreSQL có AI hỗ trợ

Đây là bản demo để học, dựng lại ở mức nhẹ ý tưởng của bài báo D-Bot
(arXiv 2312.01454). Hệ thống gây sự cố thật trên PostgreSQL, phát hiện bất thường,
rồi nhờ một LLM chạy trên máy bạn phân tích nguyên nhân và đề xuất cách xử lý.

AI chỉ đề xuất. AI không tự chạy lệnh sửa lỗi trên database.

## Thành phần

| Container | Việc làm |
|---|---|
| postgres | PostgreSQL 16, bật pg_stat_statements, chứa dữ liệu TPC-H trong schema tpch |
| tpch-seed | Chạy một lần: build dbgen, sinh dữ liệu TPC-H SF 0.1 rồi nạp vào PostgreSQL |
| monitor | Cứ 10 giây đọc thống kê của PostgreSQL, tạo alert, tự đóng alert khi hết sự cố |
| backend | FastAPI, phục vụ trang web, API, WebSocket, chạy và dừng kịch bản |
| dbot-worker | D-Bot dùng CrewAI với 2 agent: Chẩn đoán và Báo cáo |

Ollama không chạy trong Docker. Ollama chạy trực tiếp trên máy bạn.

## Dữ liệu demo: TPC-H scale factor 0.1

Demo dùng bộ dữ liệu chuẩn TPC-H với scale factor 0.1 (khoảng 100 MB).
Có 8 bảng: region, nation, part, supplier, partsupp, customer, orders, lineitem.
Bảng lớn nhất là lineitem với khoảng 600 nghìn dòng.

Dữ liệu không nằm trong repo. Khi chạy `docker compose up`, container tpch-seed sẽ:

1. Tải và build công cụ dbgen từ https://github.com/gregrahn/tpch-kit.
2. Chạy `dbgen -s 0.1` để sinh các file .tbl.
3. Nạp các file vào PostgreSQL bằng lệnh COPY, rồi chạy ANALYZE.

Các bảng chỉ có khóa chính. Cố ý không có index phụ như l_partkey hay o_custkey,
để kịch bản thiếu index có tác dụng. Nếu dữ liệu đã có, tpch-seed sẽ bỏ qua bước nạp.
Muốn đổi kích thước, sửa `TPCH_SF` trong file .env trước khi chạy lần đầu.

## 1. Chuẩn bị

1. Cài Docker Desktop (Windows, macOS) hoặc Docker Engine có Compose (Linux).
2. Cài Ollama tại https://ollama.com.
3. Tải model. Lệnh này tải khoảng 4,7 GB:

```bash
ollama pull qwen2.5:7b
```

4. Kiểm tra Ollama đang chạy:

```bash
curl http://localhost:11434/api/tags
```

Trên Linux, Ollama mặc định chỉ nghe ở 127.0.0.1. Container không gọi tới được.
Hãy cho Ollama nghe ở mọi địa chỉ:

```bash
sudo systemctl edit ollama
# thêm 2 dòng sau rồi lưu:
# [Service]
# Environment="OLLAMA_HOST=0.0.0.0"
sudo systemctl restart ollama
```

## 2. Chạy hệ thống

```bash
git clone -b feature/dbot-demo https://github.com/nguyenlytruongsonex1-ops/dbot-demo.git
cd dbot-demo
cp .env.example .env
docker compose up --build -d
```

Lần đầu mất vài phút vì phải tải image và cài CrewAI.
Bước sinh và nạp dữ liệu TPC-H mất khoảng 10 đến 30 giây. Xem tiến độ: `docker compose logs tpch-seed`.

Mở trình duyệt: http://localhost:8000

Xem log nếu cần:

```bash
docker compose logs -f monitor dbot-worker
```

## 3. Chạy thử một kịch bản

1. Ở cột "Kịch bản sự cố", bấm Chạy ở dòng missing_index.
2. Chờ 10 đến 20 giây. Một alert mới hiện ra ở bảng bên trái.
3. Bấm "Nhờ AI phân tích". Trạng thái chuyển sang "đang phân tích".
4. Khi xong, bấm vào tên alert để xem chi tiết: tóm tắt, các bước suy luận, nguyên nhân, phương án xử lý.
5. Bấm Dừng ở kịch bản. Sau 3 lần quét không còn dấu hiệu (khoảng 30 đến 40 giây), alert tự chuyển sang "đã giải quyết".

## 4. Các kịch bản có sẵn

| Kịch bản | Sự cố | Ghi chú |
|---|---|---|
| cpu_high | Truy vấn tổng hợp kiểu TPC-H Q1 lặp 50 lần trên lineitem, CPU cao | Chạy 1 đến 3 phút |
| missing_index | Tìm lineitem theo l_partkey (không có index) 10000 lần | Chạy vài phút |
| lock_holder | Giữ khóa đơn hàng o_orderkey = 1 trong 120 giây | Chạy trước lock_waiter |
| lock_waiter | Cập nhật cùng dòng, bị kẹt | Chạy sau lock_holder |
| idle_in_transaction | Transaction mở 90 giây không commit | |
| table_bloat | Tắt autovacuum, update toàn bảng lineitem 3 lần | Alert chỉ hết sau khi chạy fix_vacuum |
| fix_vacuum | Dọn dẹp sau table_bloat | Không phải sự cố |

Mỗi file trong thư mục scenarios/ có phần comment đầu file giải thích sự cố,
dấu hiệu mong đợi và cách xử lý.

## 5. Thêm kịch bản mới

Cách 1: trên trang web, ở mục "Thêm kịch bản", nhập tên (chữ thường, số, dấu gạch dưới)
và chọn file .sql rồi bấm Tải lên.

Cách 2: chép file .sql vào thư mục scenarios/. Trang web sẽ thấy ngay.

Lưu ý:
- Mỗi kịch bản chạy một lần, trên một kết nối, từng câu lệnh theo thứ tự.
- Kịch bản chạy bằng user scenario_runner, chỉ có quyền trên schema tpch.
- Mỗi câu lệnh bị giới hạn 10 phút.
- Nên viết vài dòng comment bắt đầu bằng -- ở đầu file để mô tả kịch bản.

## 6. Đổi model hoặc dùng API khác

Sửa file .env rồi chạy lại `docker compose up -d`:

- Đổi model Ollama: `OLLAMA_MODEL=llama3.1:8b`
- Dùng API tương thích OpenAI: `LLM_PROVIDER=openai`, điền `OPENAI_API_KEY`.
- Thử luồng mà không cần LLM: `LLM_PROVIDER=mock`. D-Bot vẫn gọi công cụ thật trên DB
  nhưng kết luận theo luật viết sẵn.

## 7. Xử lý sự cố thường gặp

| Hiện tượng | Cách xử lý |
|---|---|
| Phân tích báo lỗi Connection error | Kiểm tra Ollama đang chạy và nghe ở 0.0.0.0 (xem mục 1) |
| Phân tích rất lâu | Model 7B trên CPU mất 1 đến 3 phút. Thử model nhỏ hơn như qwen2.5:3b |
| Cổng 5432 hoặc 8000 bị chiếm | Tắt PostgreSQL cũ trên máy, hoặc đổi APP_PORT trong .env |
| Không thấy alert | Chờ ít nhất 2 lần quét (20 giây). Xem `docker compose logs monitor` |
| tpch-seed báo lỗi khi build | Kiểm tra mạng (cần tải tpch-kit từ GitHub), rồi chạy lại `docker compose up --build -d` |
| Muốn làm lại từ đầu | `docker compose down -v` rồi `docker compose up --build -d` |

## 8. Cấu trúc thư mục

```
app/            mã nguồn: monitor, backend, worker, D-Bot, giao diện web
db/init/        SQL tạo schema TPC-H và user cho kịch bản
seed/           Dockerfile và script sinh, nạp dữ liệu TPC-H
scenarios/      các file kịch bản sự cố
knowledge/      tri thức chẩn đoán dạng markdown cho D-Bot tra cứu
docs/           báo cáo tổng hợp (docx) và hình kiến trúc
tests/          kiểm thử nhỏ
```

## Tham khảo

- Zhou và cộng sự, D-Bot: Database Diagnosis System using Large Language Models, arXiv 2312.01454.
- TPC-H Benchmark: https://www.tpc.org/tpch/
- tpch-kit (dbgen): https://github.com/gregrahn/tpch-kit
- Repo gốc: https://github.com/TsinghuaDatabaseGroup/DB-GPT
