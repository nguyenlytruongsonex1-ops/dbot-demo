"""Tạo báo cáo docs/bao-cao-dbot-demo.docx bằng python-docx.
Chạy: python docs/build_report.py"""
import os
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = "https://github.com/nguyenlytruongsonex1-ops/dbot-demo/tree/feature/dbot-demo"

doc = Document()
for s in doc.sections:
    s.top_margin = s.bottom_margin = Cm(2)
    s.left_margin, s.right_margin = Cm(3), Cm(2)

st = doc.styles["Normal"]
st.font.name = "Times New Roman"; st.font.size = Pt(13)
st.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
st.paragraph_format.space_after = Pt(6); st.paragraph_format.line_spacing = 1.3
for name, size in (("Title", 18), ("Heading 1", 15), ("Heading 2", 13)):
    h = doc.styles[name]; h.font.name = "Times New Roman"; h.font.size = Pt(size)
    h.font.bold = name != "Title"; h.font.color.rgb = None
    h.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    h.element.rPr.rFonts.set(qn("w:ascii"), "Times New Roman")
    h.element.rPr.rFonts.set(qn("w:hAnsi"), "Times New Roman")

def p(text, align=None, italic=False):
    para = doc.add_paragraph()
    r = para.add_run(text); r.italic = italic
    if align: para.alignment = align
    else: para.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    return para

def bullet(text):
    doc.add_paragraph(text, style="List Bullet")

def caption(text):
    p(text, WD_ALIGN_PARAGRAPH.CENTER, italic=True)

def table(header, rows, cap, widths=None):
    caption(cap)
    t = doc.add_table(rows=1, cols=len(header)); t.style = "Table Grid"
    for i, h in enumerate(header):
        t.rows[0].cells[i].text = h
    for r in rows:
        cells = t.add_row().cells
        for i, v in enumerate(r):
            cells[i].text = v
    for row in t.rows:
        for i, c in enumerate(row.cells):
            for para in c.paragraphs:
                para.paragraph_format.space_after = Pt(2)
                for run in para.runs: run.font.size = Pt(11)
            if widths: c.width = Cm(widths[i])
    doc.add_paragraph()

H = doc.add_heading
p("Mã nguồn: " + REPO, WD_ALIGN_PARAGRAPH.LEFT)
doc.add_paragraph("Báo cáo tổng hợp: Demo hệ thống chẩn đoán sự cố cơ sở dữ liệu dựa trên D-Bot", style="Title").alignment = WD_ALIGN_PARAGRAPH.CENTER
p("Tài liệu học tập. Thực hiện: Nguyễn Lý Trường Sơn. Ngày 15/10/2026.", WD_ALIGN_PARAGRAPH.CENTER)

H("1. Giới thiệu và mục tiêu", 1)
p("Quản trị cơ sở dữ liệu cần nhiều kinh nghiệm. Khi có sự cố, người quản trị (DBA) phải đọc nhiều số liệu, đoán nguyên nhân và chọn cách xử lý. Bài báo D-Bot đề xuất dùng mô hình ngôn ngữ lớn (LLM) để hỗ trợ việc này.")
p("Báo cáo này trình bày một bản demo nhỏ, dựng lại ý tưởng của D-Bot ở mức nhẹ. Mục tiêu là học cách một hệ thống như vậy hoạt động. Đây không phải công trình nghiên cứu và không nhằm so sánh với kết quả của bài báo.")
p("Bản demo có bốn mục tiêu cụ thể:")
bullet("Gây ra các sự cố thật trên PostgreSQL bằng các file SQL kịch bản.")
bullet("Tự phát hiện bất thường và hiện cảnh báo (alert) theo thời gian thực trên một trang web.")
bullet("Cho phép DBA bấm nút để AI phân tích, xem từng bước suy luận và phương án xử lý.")
bullet("Chạy được trên máy cá nhân bằng Docker, dùng LLM chạy cục bộ qua Ollama.")

H("2. Tóm tắt bài báo gốc", 1)
p("Bài báo D-Bot: Database Diagnosis System using Large Language Models (Zhou và cộng sự, arXiv 2312.01454, nhóm Cơ sở dữ liệu Đại học Thanh Hoa) xây dựng một hệ thống chẩn đoán sự cố cho PostgreSQL. Hệ thống gồm các phần chính sau.")
bullet("Trích xuất tri thức chẩn đoán từ tài liệu kỹ thuật, lưu thành các mẩu tri thức có cấu trúc.")
bullet("Bộ công cụ cho LLM gọi, ví dụ xem số liệu giám sát, xem câu lệnh chậm, gợi ý index.")
bullet("Suy luận theo cây (tree search) để thử nhiều hướng và quay lui khi hướng hiện tại không hợp lý.")
bullet("Nhiều agent chuyên môn phối hợp, mỗi agent phụ trách một nhóm sự cố như CPU, bộ nhớ, khóa.")
p("Bài báo dùng GPT-4 và một hệ thống giám sát đầy đủ với Prometheus. Theo bài báo, D-Bot cho kết quả chẩn đoán tốt hơn các phương pháp dựa trên luật và các LLM không có công cụ. Hệ thống gốc khá nặng để dựng lại trên máy cá nhân, nên bản demo chỉ giữ lại ý tưởng chính.")

H("3. Kiến trúc hệ thống", 1)
p("Hệ thống gồm năm container trong Docker Compose và một dịch vụ Ollama chạy trên máy người dùng. Hình 1 mô tả các thành phần và luồng dữ liệu.")
doc.add_picture(os.path.join(HERE, "kien-truc.png"), width=Cm(16))
doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
caption("Hình 1. Kiến trúc tổng thể của bản demo")
p("So với bài báo gốc, bản demo đơn giản hóa như sau. Monitor đọc thẳng các view thống kê của PostgreSQL thay vì dùng Prometheus. Chỉ có hai agent thay vì nhiều agent chuyên môn. Tri thức để trong vài file văn bản, tìm theo từ khóa. LLM là một mô hình nhỏ chạy cục bộ thay cho GPT-4.")

H("4. Các thành phần", 1)
H("4.1. Cơ sở dữ liệu và dữ liệu TPC-H", 2)
p("Cơ sở dữ liệu là PostgreSQL 16, bật extension pg_stat_statements để theo dõi thống kê câu lệnh. Đây cũng là hệ quản trị mà bài báo gốc sử dụng.")
p("Dữ liệu demo là bộ TPC-H với scale factor 0.1, khoảng 100 MB. TPC-H là bộ benchmark chuẩn cho truy vấn phân tích. Bộ dữ liệu gồm 8 bảng: region, nation, part, supplier, partsupp, customer, orders và lineitem. Bảng lớn nhất là lineitem, khoảng 600 nghìn dòng.")
p("Dữ liệu không được lưu trong repo mà được sinh khi cài đặt. Container tpch-seed tải và build công cụ dbgen của tpch-kit, chạy lệnh dbgen -s 0.1 để sinh các file .tbl, rồi nạp vào PostgreSQL bằng lệnh COPY và chạy ANALYZE. Các bảng chỉ có khóa chính. Tác giả cố ý không tạo index phụ trên các cột như l_partkey hay o_custkey để kịch bản thiếu index có tác dụng.")
p("Kịch bản chạy bằng một user riêng tên scenario_runner. User này chỉ có quyền trên schema tpch, và mỗi câu lệnh bị giới hạn 10 phút.")
H("4.2. Monitor", 2)
p("Monitor là một vòng lặp Python, cứ 10 giây đọc các view pg_stat_activity, pg_locks (qua hàm pg_blocking_pids), pg_stat_statements và pg_stat_user_tables. Mỗi loại dấu hiệu được so với một ngưỡng đơn giản, trình bày ở Bảng 1.")
table(["Loại alert", "Điều kiện phát hiện"], [
    ["long_query", "Phiên đang chạy một câu lệnh quá 5 giây, không phải chờ khóa"],
    ["lock_wait", "Phiên chờ khóa (wait_event_type là Lock) quá 3 giây"],
    ["idle_in_transaction", "Transaction mở quá 10 giây mà không làm việc"],
    ["missing_index", "Một câu SELECT có điều kiện lọc được gọi từ 20 lần trở lên trong một chu kỳ, mỗi lần đọc từ 1000 block trở lên"],
    ["table_bloat", "Bảng có từ 100 nghìn dòng chết và số dòng chết từ 20% số dòng sống"],
    ["too_many_connections", "Số kết nối từ 80% max_connections"],
], "Bảng 1. Các loại alert và điều kiện phát hiện", [4, 11])
p("Nếu một alert không còn dấu hiệu trong 3 lần quét liên tiếp, monitor tự chuyển alert sang trạng thái đã giải quyết.")
p("Khi làm demo, tác giả nhận thấy pg_stat_user_tables chỉ cập nhật khi transaction kết thúc. Vì vậy một vòng lặp dài trong khối DO không làm số lần quét bảng thay đổi. Ngược lại, pg_stat_statements cập nhật ngay sau mỗi câu lệnh con. Do đó luật thiếu index dựa trên pg_stat_statements.")
H("4.3. Backend và giao diện", 2)
p("Backend viết bằng FastAPI. Backend cung cấp API đọc alert, API chạy, dừng và tải lên kịch bản, API yêu cầu AI phân tích, và một kênh WebSocket để báo cho trình duyệt mỗi khi dữ liệu thay đổi. Alert và báo cáo được lưu trong SQLite.")
p("Mỗi kịch bản là một file SQL. Khi bấm Chạy, backend mở một kết nối và chạy lần lượt từng câu lệnh trong file. Khi bấm Dừng, backend kết thúc kết nối đó bằng pg_terminate_backend.")
p("Giao diện là trang HTML dùng Alpine.js. Trang chính có bảng alert với mức độ và trạng thái, nút Nhờ AI phân tích, và khung kịch bản có nút Chạy, Dừng cùng form tải lên. Trang chi tiết hiện tóm tắt, nguyên nhân gốc, các bước suy luận có thể mở ra hoặc thu gọn, và phương án xử lý kèm câu SQL đề xuất.")
H("4.4. D-Bot worker", 2)
p("Worker dùng CrewAI với hai agent. Agent Chẩn đoán gọi các công cụ: explain_query, get_locks, get_activity, get_table_stats, get_top_statements và search_knowledge. Agent Báo cáo tổng hợp kết quả thành JSON gồm tóm tắt, các bước suy luận, nguyên nhân gốc và phương án xử lý.")
p("Kết nối của worker được đặt ở chế độ chỉ đọc. Vì vậy AI không thể tự sửa dữ liệu hay cấu hình. DBA đọc đề xuất và tự quyết định có chạy hay không.")
p("LLM mặc định là qwen2.5:7b chạy qua Ollama trên máy người dùng, container gọi tới địa chỉ host.docker.internal:11434. Ngoài ra có thể chọn API tương thích OpenAI, hoặc chế độ mock không cần LLM. Chế độ mock vẫn gọi công cụ thật trên cơ sở dữ liệu nhưng kết luận theo luật viết sẵn, dùng để thử luồng hệ thống.")

H("5. Các kịch bản sự cố", 1)
p("Bảng 2 liệt kê các kịch bản có sẵn trong thư mục scenarios. Mỗi file có phần chú thích ở đầu, nêu sự cố, dấu hiệu mong đợi và cách xử lý.")
table(["Kịch bản", "Mô tả", "Cách xử lý mong đợi"], [
    ["cpu_high", "Lặp 50 lần truy vấn tổng hợp kiểu TPC-H Q1 trên lineitem", "Hủy query, đặt statement_timeout, dùng bảng tổng hợp"],
    ["missing_index", "Tìm lineitem theo l_partkey 10000 lần, cột không có index", "Tạo index trên l_partkey"],
    ["lock_holder", "Cập nhật đơn hàng o_orderkey = 1 rồi chờ 120 giây mới commit", "Tìm và kết thúc phiên giữ khóa"],
    ["lock_waiter", "Cập nhật cùng đơn hàng, bị chặn", "Đặt lock_timeout"],
    ["idle_in_transaction", "Mở transaction 90 giây không commit", "Đặt idle_in_transaction_session_timeout"],
    ["table_bloat", "Tắt autovacuum, cập nhật toàn bảng lineitem 3 lần", "VACUUM và bật lại autovacuum"],
    ["fix_vacuum", "Dọn dẹp sau table_bloat, không phải sự cố", "Không áp dụng"],
], "Bảng 2. Các kịch bản sự cố có sẵn", [3.5, 6.5, 5])

H("6. Luồng xử lý từ alert đến báo cáo", 1)
p("Luồng xử lý gồm các bước sau.")
for i, t in enumerate([
    "DBA bấm Chạy một kịch bản. Backend chạy file SQL trên một kết nối riêng.",
    "Monitor quét các view thống kê. Khi vượt ngưỡng, monitor ghi một alert vào SQLite.",
    "Backend thấy dữ liệu thay đổi và gửi thông báo qua WebSocket. Trình duyệt tải lại danh sách alert.",
    "DBA bấm Nhờ AI phân tích. Alert chuyển sang trạng thái đang phân tích.",
    "Worker nhận alert, gọi công cụ để lấy thêm dữ liệu, tra tri thức, rồi viết báo cáo JSON.",
    "DBA mở trang chi tiết để đọc từng bước suy luận và phương án xử lý.",
    "Khi sự cố hết, sau 3 lần quét không còn dấu hiệu, alert tự chuyển sang đã giải quyết.",
], 1):
    p(f"Bước {i}. {t}", WD_ALIGN_PARAGRAPH.LEFT)

H("7. Hướng dẫn chạy", 1)
p("Máy cần có Docker và Ollama. Các bước chạy như sau.")
for t in [
    "Tải model: ollama pull qwen2.5:7b. Trên Linux cần cho Ollama nghe ở địa chỉ 0.0.0.0.",
    "Tải mã nguồn: git clone -b feature/dbot-demo " + REPO.split("/tree")[0] + ".git",
    "Vào thư mục dbot-demo, sao chép file .env.example thành .env.",
    "Chạy docker compose up --build -d. Lần đầu mất vài phút để build và sinh dữ liệu TPC-H.",
    "Mở trình duyệt tại địa chỉ http://localhost:8000.",
]:
    bullet(t)
p("File README trong repo có hướng dẫn chi tiết hơn, gồm cách thêm kịch bản và cách xử lý lỗi thường gặp.")

H("8. Kết quả kiểm thử", 1)
p("Máy kiểm thử không có Docker và không có Ollama. Vì vậy tác giả kiểm thử theo cách sau: chạy PostgreSQL 17 cài trực tiếp trên máy, sinh dữ liệu bằng chính script seed.sh, chạy monitor, backend và worker bằng Python, và dùng chế độ mock cho phần AI. Bảng 3 ghi lại kết quả quan sát được.")
table(["Nội dung", "Kết quả quan sát"], [
    ["Sinh và nạp TPC-H SF 0.1", "dbgen chạy khoảng 5 giây. Toàn bộ sinh và nạp mất khoảng 8 giây. Bảng lineitem có 600.572 dòng"],
    ["missing_index", "Alert xuất hiện khoảng 17 giây sau khi chạy. Câu SELECT trên lineitem được gọi 225 lần trong một chu kỳ"],
    ["cpu_high", "Alert long_query xuất hiện sau khoảng 7 giây, trạng thái chờ là CPU, mức critical khi quá 30 giây"],
    ["lock_holder và lock_waiter", "Alert lock_wait xuất hiện sau khoảng 5 giây, chỉ đúng pid của phiên chặn"],
    ["idle_in_transaction", "Alert xuất hiện sau khoảng 15 giây"],
    ["table_bloat", "Alert xuất hiện sau khoảng 7 giây, với khoảng 1,8 triệu dòng chết"],
    ["Tự giải quyết", "Sau khi bấm Dừng, các alert chuyển sang đã giải quyết sau 30 đến 40 giây. Alert bloat hết sau khi chạy fix_vacuum"],
    ["Phân tích ở chế độ mock", "Worker gọi công cụ thật, mỗi alert xong trong vài giây. Ví dụ với missing_index, kết luận là cột l_partkey không có index và đề xuất CREATE INDEX CONCURRENTLY"],
    ["Tải lên kịch bản", "File hợp lệ được lưu và chạy được. Tên kịch bản sai quy tắc bị từ chối"],
    ["WebSocket và trang web", "Trang chính trả về đúng HTML. Kênh WebSocket gửi thông báo thay đổi"],
], "Bảng 3. Kết quả kiểm thử thực tế", [4.5, 10.5])
p("Các phần chưa được kiểm thử:")
bullet("Chưa chạy docker compose, các Dockerfile và container tpch-seed, vì máy kiểm thử không có Docker.")
bullet("Chưa chạy với LLM thật. CrewAI phiên bản 1.15 đã được cài và gọi thử, nhưng báo lỗi kết nối vì máy không có Ollama. Chất lượng báo cáo của qwen2.5:7b chưa được đánh giá.")
bullet("Chưa thử thao tác bấm nút trong trình duyệt thật. Các API phía sau nút đã được gọi trực tiếp và hoạt động.")
bullet("Kiểm thử dùng PostgreSQL 17 thay vì 16 như trong Docker.")

H("9. Hạn chế", 1)
bullet("Luật phát hiện còn đơn giản, dựa trên ngưỡng cố định. Một số trường hợp có thể bị báo trùng, ví dụ kịch bản giữ khóa cũng tạo alert transaction mở lâu.")
bullet("Monitor không đo trực tiếp CPU của máy. Alert CPU được suy ra từ việc phiên đang chạy mà không chờ gì.")
bullet("Tri thức chẩn đoán ít và tìm theo từ khóa, chưa dùng tìm kiếm ngữ nghĩa.")
bullet("Mô hình 7B chạy trên CPU khá chậm, có thể trả JSON sai định dạng. Khi đó hệ thống hiện văn bản gốc và nhật ký công cụ.")
bullet("Bản demo không có suy luận theo cây và không có nhiều agent chuyên môn như bài báo gốc.")

H("10. Kết luận", 1)
p("Bản demo đã dựng lại được luồng chính của D-Bot ở mức nhẹ: gây sự cố thật trên dữ liệu TPC-H, phát hiện bất thường, đẩy alert lên giao diện theo thời gian thực, và cho AI phân tích theo từng bước. Toàn bộ chạy trên máy cá nhân, không cần GPU hay API trả phí. Hướng mở rộng gồm thêm kịch bản, thêm công cụ như gợi ý index bằng hypopg, và so sánh chất lượng báo cáo giữa các mô hình.")

H("Tài liệu tham khảo", 1)
for r in [
    "[1] X. Zhou, G. Li, Z. Sun và cộng sự, D-Bot: Database Diagnosis System using Large Language Models, arXiv:2312.01454, 2023.",
    "[2] TsinghuaDatabaseGroup, DB-GPT, https://github.com/TsinghuaDatabaseGroup/DB-GPT.",
    "[3] Transaction Processing Performance Council, TPC-H Benchmark, https://www.tpc.org/tpch/.",
    "[4] G. Rahn, tpch-kit, https://github.com/gregrahn/tpch-kit.",
    "[5] PostgreSQL Global Development Group, The Statistics Collector và pg_stat_statements, tài liệu PostgreSQL 16.",
    "[6] CrewAI, https://docs.crewai.com.",
]:
    p(r, WD_ALIGN_PARAGRAPH.LEFT)

doc.save(os.path.join(HERE, "bao-cao-dbot-demo.docx"))
print("saved")
