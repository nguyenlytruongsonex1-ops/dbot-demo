from datetime import date
from pathlib import Path
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

OUT = Path(__file__).parent / "DBot_Light_Bao_cao_tong_hop.docx"


def shade(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = tcPr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tcPr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_text(cell, text, bold=False, color=None):
    cell.text = ""
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run(str(text))
    r.bold = bold
    r.font.size = Pt(9.5)
    if color:
        r.font.color.rgb = RGBColor.from_string(color)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


def add_table(doc, headers, rows, widths=None):
    table = doc.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Table Grid"
    for i, header in enumerate(headers):
        set_cell_text(table.rows[0].cells[i], header, bold=True, color="FFFFFF")
        shade(table.rows[0].cells[i], "1F4E79")
    for row in rows:
        cells = table.add_row().cells
        for i, value in enumerate(row):
            set_cell_text(cells[i], value)
            if len(table.rows) % 2 == 0:
                shade(cells[i], "EAF2F8")
    if widths:
        for row in table.rows:
            for i, width in enumerate(widths):
                row.cells[i].width = Inches(width)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return table


def add_page_field(paragraph):
    run = paragraph.add_run("Trang ")
    run.font.size = Pt(9)
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), "PAGE")
    run._r.addnext(fld)


def setup(doc):
    sec = doc.sections[0]
    sec.top_margin = Inches(0.7)
    sec.bottom_margin = Inches(0.65)
    sec.left_margin = Inches(0.8)
    sec.right_margin = Inches(0.8)
    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = "Arial"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")
    normal.font.size = Pt(10.5)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.12
    for name, size, color in [("Title", 24, "1F4E79"), ("Heading 1", 16, "1F4E79"), ("Heading 2", 12.5, "2F5597")]:
        style = styles[name]
        style.font.name = "Arial"
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")
        style.font.size = Pt(size)
        style.font.color.rgb = RGBColor.from_string(color)
        style.font.bold = True
    footer = sec.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_page_field(footer)


def p(doc, text="", bold_prefix=None):
    para = doc.add_paragraph()
    if bold_prefix and text.startswith(bold_prefix):
        para.add_run(bold_prefix).bold = True
        para.add_run(text[len(bold_prefix):])
    else:
        para.add_run(text)
    return para


def bullets(doc, items):
    for item in items:
        para = doc.add_paragraph(style="List Bullet")
        para.add_run(item)


def main():
    doc = Document()
    setup(doc)

    title = doc.add_paragraph(style="Title")
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.add_run("BÁO CÁO TỔNG HỢP\nTÁI DỰNG D-BOT LIGHT")
    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = sub.add_run("Realtime database diagnosis với CrewAI, Prometheus và PostgreSQL")
    r.font.size = Pt(14)
    r.font.color.rgb = RGBColor.from_string("4F6B8A")
    doc.add_paragraph()
    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    meta.add_run("Phiên bản demo: 0.2.0\n").bold = True
    meta.add_run("Ngày lập báo cáo: 14/10/2026. Cập nhật vận hành cùng ngày.\n")
    meta.add_run("Repository: github.com/nguyenlytruongsonex1-ops/dbot-demo")
    doc.add_paragraph()
    callout = doc.add_table(rows=1, cols=1)
    callout.style = "Table Grid"
    cell = callout.cell(0, 0)
    shade(cell, "EAF2F8")
    set_cell_text(cell, "Kết luận: Bản tái dựng chạy được trên một máy với alert realtime, webhook, chat theo incident và điều khiển demo trên UI. Mock mode giữ báo cáo giả. Mode API thật lấy root cause và recommendation từ CrewAI. Đây vẫn là proof-of-concept, chưa phải hệ thống DBA production.", bold=True)
    doc.add_page_break()

    doc.add_heading("1. Mục tiêu và phạm vi", level=1)
    p(doc, "Mục tiêu của bản tái dựng là tạo một phiên bản gọn, dễ chạy trên máy cá nhân nhưng vẫn giữ các ý tưởng quan trọng của D-Bot trong paper LLM As DBA và repository DB-GPT của nhóm Tsinghua.")
    p(doc, "Bản Light tập trung vào hai luồng bổ trợ. Luồng realtime nhận biết tín hiệu bất thường và tạo incident. Luồng user chat cho phép người dùng hỏi sâu, yêu cầu kiểm tra thêm, hiểu rủi ro và phê duyệt hành động.")
    add_table(doc, ["Trong phạm vi", "Ngoài phạm vi bản Light"], [
        ("PostgreSQL 16, Prometheus, Alertmanager, FastAPI, CrewAI", "Kubernetes, Kafka, distributed tracing"),
        ("5 scenario anomaly có thể tái lập", "Fine-tuning và local LLM nhiều GB"),
        ("Read-only evidence tools và report JSON", "Tự động sửa database production"),
        ("Mock mode không cần API key; OpenAI-compatible mode tùy chọn", "Triển khai HA hoặc multi-cluster")
    ], [3.1, 3.1])

    doc.add_heading("2. Repo gốc và cơ sở tái dựng", level=1)
    p(doc, "Paper LLM As DBA mô tả D-Bot gồm hai giai đoạn. Giai đoạn chuẩn bị chuyển tài liệu thành maintenance experience và tạo prompt template. Giai đoạn bảo trì nhận anomaly, thu thập metrics, chọn tool, phân tích root cause bằng tree-of-thought và phối hợp nhiều LLM agent.")
    p(doc, "Repository gốc TsinghuaDatabaseGroup/DB-GPT phát triển các ý tưởng này thành một hệ thống lớn hơn với knowledge base, document-to-knowledge, multiagents, anomaly triggers, Prometheus/Alertmanager, diagnostic files, web UI và user feedback.")
    add_table(doc, ["Ý tưởng repo gốc", "Cách tái dựng trong bản Light"], [
        ("Prometheus + Alertmanager", "Giữ nguyên mô hình; dùng 4 container chính"),
        ("Anomaly trigger scripts", "Có API/UI/CLI trigger scenario an toàn cho database demo"),
        ("Multi-agent diagnosis", "CrewAI Chief DBA, Workload Agent, Memory/Database Agent"),
        ("Knowledge base", "Experience JSON + retrieval nhẹ; không dùng vector DB riêng"),
        ("Diagnostic files/reports", "Incident store JSON và report history"),
        ("Frontend diagnosis", "Dashboard local có incident list, evidence và chat")
    ], [3.1, 3.1])

    doc.add_heading("3. Kiến trúc bản tái dựng", level=1)
    p(doc, "Kiến trúc được thiết kế để mỗi thành phần có một trách nhiệm rõ ràng. Scenario runner chỉ tạo sự cố phục vụ demo. PostgreSQL là nơi phát sinh trạng thái. Prometheus scrape metrics và đánh giá rule. Alertmanager gửi webhook. D-Bot thu thập evidence và điều phối CrewAI.")
    doc.add_paragraph("Scenario/API → PostgreSQL → D-Bot /metrics → Prometheus → Alertmanager → D-Bot /webhooks/alertmanager → Incident store → CrewAI → Report + User chat", style="Intense Quote")
    add_table(doc, ["Service/module", "Chức năng"], [
        ("postgres", "Database demo, sample tables, pg_stat_statements và system views"),
        ("dbot", "FastAPI, UI, metrics exporter, incident store, CrewAI và read-only tools"),
        ("prometheus", "Scrape /metrics mỗi 5 giây và đánh giá alert rules"),
        ("alertmanager", "Group/deduplicate alert firing/resolved và POST webhook"),
        ("scenario runner", "Trigger/clear anomaly phục vụ kiểm thử local; không dùng cho production")
    ], [1.6, 4.6])
    p(doc, "User chat được gắn với từng incident. Người dùng không cần biết SQL; UI hiển thị summary, evidence, root cause và các câu hỏi tự nhiên như ‘Có chắc là do thiếu index không?’ hoặc ‘Session nào đang block?’. Ô chat giữ nguyên chữ đang gõ khi trang tự làm mới mỗi 5 giây.")

    doc.add_heading("4. Bộ kịch bản kiểm thử", level=1)
    add_table(doc, ["ID", "Scenario", "Realtime trigger", "Tool/evidence chính", "Kết quả mong đợi"], [
        ("RT-01", "Slow query / missing index", "Latency signal > 500 ms", "pg_stat_statements, EXPLAIN, pg_indexes", "Nhận diện Seq Scan và đề xuất candidate index"),
        ("RT-02", "Lock contention", "Blocked session > 0", "pg_locks, pg_stat_activity", "Xác định blocker/waiter và yêu cầu approval"),
        ("RT-03", "CPU/workload contention", "Active-session signal > 8", "Sessions, system metrics, slow queries", "Phân biệt workload, CPU và lock pressure"),
        ("RT-04", "Table bloat", "Dead tuple ratio > 0.02", "pg_stat_user_tables", "Đề xuất VACUUM/ANALYZE và maintenance window"),
        ("RT-05", "Execution error", "Error signal > 0", "Incident context và database state", "Phân loại lỗi và đề xuất sửa an toàn")
    ], [0.45, 1.35, 1.55, 1.65, 1.8])
    p(doc, "Trong môi trường thật, application workload hoặc batch job tạo anomaly. Scenario runner chỉ tồn tại để tạo tín hiệu lặp lại trong demo. D-Bot không tự tạo workload production.")

    doc.add_heading("5. Luồng realtime và user chat", level=1)
    p(doc, "Realtime detection và user chat không thay thế nhau. Realtime trả lời ‘có vấn đề gì và bắt đầu lúc nào’. Chat trả lời ‘vì sao, cần kiểm tra gì thêm, rủi ro ra sao và có nên thực hiện action không’.")
    add_table(doc, ["Bước", "Realtime", "User chat"], [
        ("1", "Prometheus phát hiện metric vượt rule", "—"),
        ("2", "Alertmanager gửi webhook", "—"),
        ("3", "D-Bot chạy diagnosis sơ bộ", "—"),
        ("4", "Incident hiển thị summary/evidence", "User mở incident"),
        ("5", "—", "User hỏi tự nhiên hoặc chọn câu hỏi gợi ý"),
        ("6", "—", "D-Bot gọi thêm logic/evidence phù hợp"),
        ("7", "—", "User approve/reject recommendation"),
        ("8", "D-Bot ghi report resolved/firing", "D-Bot validation sau xử lý")
    ], [0.5, 3.0, 2.7])

    doc.add_heading("6. Kết quả đạt được", level=1)
    bullets(doc, [
        "Đã tích hợp UI local cho trigger scenario, danh sách incident, incident detail, evidence và chat.",
        "Mỗi workload đang chạy có nút Dừng. Nút này gọi POST /api/scenarios/{name}/clear và chỉ tắt scenario đó.",
        "Danh sách Incidents có nút Clear. Sau khi xác nhận, POST /api/incidents/clear xóa incident trên trang. Workload, knowledge và database không bị xóa.",
        "Ô chat không bị xóa khi trang poll lại mỗi 5 giây, kể cả khi incident đang được cập nhật và ô đang được focus.",
        "Đã có Prometheus metrics endpoint và 5 alert rules tương ứng với 5 scenario.",
        "Đã có Alertmanager webhook nhận alert firing/resolved tại /webhooks/alertmanager.",
        "Đã có incident store dạng JSON để lưu lịch sử incident và chat trên volume local.",
        "Đã giữ CrewAI topology gồm Chief DBA, CPU/Workload Agent và Memory/Database Agent.",
        "Mock mode vẫn trả báo cáo giả, không cần API key.",
        "Mode API thật yêu cầu chief agent trả CrewFinding. Root cause, confidence, recommendation và summary lấy từ kết quả crew. Recommendation luôn requires_approval. Nếu crew lỗi, báo cáo ghi rõ mock-fallback.",
        "LLM tương thích OpenAI, gồm Gemini qua https://generativelanguage.googleapis.com/v1beta/openai/, được trỏ bằng OPENAI_API_BASE. CrewAI nhận provider openai và base URL này, không gửi key Gemini sang api.openai.com.",
        "Knowledge vẫn là data/experiences.json. Sửa file có hiệu lực ở lần chẩn đoán sau, không cần build lại image vì thư mục data được mount. Câu root cause của mock mode không đọc file này."
    ])
    add_table(doc, ["Hạng mục kiểm tra", "Kết quả"], [
        ("Unit tests", "8 passed trong container dbot"),
        ("Mock diagnosis", "Đạt; root cause vẫn lấy từ bảng mapping"),
        ("Báo cáo mode API", "Đạt bằng crew finding giả lập; không gọi API tính phí trong test"),
        ("Nút Dừng và giữ chữ ô chat", "Đạt trên Chrome headless với API giả"),
        ("Nút Clear incident", "Đạt: POST /api/incidents/clear trả cleared và danh sách rỗng"),
        ("Docker trên máy phát triển", "Đạt: Docker Desktop, postgres healthy, dbot healthy"),
        ("Gemini end-to-end", "Đã sửa đường gọi. Chưa ghi một diagnosis Gemini thành công trong báo cáo này")
    ], [3.2, 2.8])

    doc.add_heading("7. Hướng dẫn chạy nhanh", level=1)
    p(doc, "Yêu cầu duy nhất là Docker Desktop hoặc Docker Engine có Compose v2. Không cần cài Python và không cần API key nếu dùng mock mode.")
    steps = [
        "Clone repository: git clone https://github.com/nguyenlytruongsonex1-ops/dbot-demo.git",
        "Vào thư mục: cd dbot-demo",
        "Tạo cấu hình: cp .env.example .env",
        "Khởi động: docker compose up --build -d",
        "Mở UI: http://localhost:8000",
        "Bấm lock_contention hoặc slow_query trong phần Trigger demo workload",
        "Workload đang chạy hiện nút Dừng. Bấm Dừng để tắt riêng scenario đó",
        "Chờ khoảng 30–60 giây để Prometheus và Alertmanager gửi incident",
        "Chọn incident và hỏi trong chat. Chữ đang gõ không bị trang tự làm mới xóa",
        "Bấm Clear ở khung Incidents để xóa danh sách sau khi xác nhận",
        "Dọn workload: bấm Clear all scenarios hoặc chạy docker compose down"
    ]
    for i, step in enumerate(steps, 1):
        para = doc.add_paragraph(style="List Number")
        para.add_run(step)
    p(doc, "Đổi LLM trong .env rồi chạy docker compose up -d. Không cần build lại image. Container dbot được tạo lại để đọc biến mới. Tải lại trang không đủ.")
    p(doc, "Ví dụ Gemini, key lấy từ Google AI Studio:")
    p(doc, "LLM_MODE=openai")
    p(doc, "OPENAI_API_KEY=<gemini-api-key>")
    p(doc, "OPENAI_MODEL_NAME=<model id trong AI Studio, ví dụ gemini-2.5-flash>")
    p(doc, "OPENAI_API_BASE=https://generativelanguage.googleapis.com/v1beta/openai/")
    p(doc, "Xóa sạch dữ liệu demo rồi khởi động lại: docker compose down -v; xóa data/incidents.json và thư mục reports; sau đó docker compose up --build -d. Lệnh down -v xóa volume Postgres, Prometheus và Alertmanager. experiences.json và .env được giữ.")

    doc.add_heading("8. Giới hạn và hướng phát triển", level=1)
    p(doc, "Bản Light là proof-of-concept. Một số tín hiệu scenario được điều khiển qua trạng thái demo để bảo đảm alert có thể tái lập trên laptop; diagnosis vẫn đọc database tools để tạo evidence. Vì vậy đây chưa phải benchmark production hay hệ thống DBA tự động hoàn toàn.")
    add_table(doc, ["Hiện tại", "Hướng phát triển"], [
        ("Experience JSON chỉ đưa tên vào evidence mock; mode API đưa content vào context của crew", "Ingest Markdown/PDF, chunking và extraction tự động"),
        ("Retrieval nhẹ theo token", "BM25/embedding retrieval có reference"),
        ("State flow bounded", "Tree search/backtracking sâu hơn"),
        ("Khuyến nghị chưa auto-apply", "Approval workflow có audit và validation"),
        ("Một database demo", "Adapter PostgreSQL/MySQL và nhiều database target")
    ], [3.1, 3.1])

    doc.add_heading("9. Kết luận", level=1)
    p(doc, "Bản tái dựng đã đạt mục tiêu tạo một D-Bot Light dễ chạy, có realtime alert flow, user chat và các nút điều khiển demo. Mock mode dùng để trình diễn không cần API. Mode API thật dùng kết quả có cấu trúc của CrewAI cho root cause và recommendation. Kiến trúc giữ thông điệp cốt lõi của D-Bot: kết luận phải dựa trên maintenance experience, metrics, system views, query plan và tool evidence.")
    p(doc, "Phiên bản hiện tại phù hợp cho demo, học tập và phát triển tiếp. Để tiến gần repo gốc hơn, ưu tiên tiếp theo là document-to-knowledge pipeline, dynamic tool selection, diagnosis trace/backtracking và approval workflow đầy đủ.")

    doc.add_heading("Tài liệu tham khảo", level=1)
    refs = [
        "Zhou, X., Li, G., Liu, Z. LLM As DBA. arXiv:2308.05481v2.",
        "TsinghuaDatabaseGroup/DB-GPT: https://github.com/TsinghuaDatabaseGroup/DB-GPT",
        "Prometheus Alertmanager configuration: https://prometheus.io/docs/alerting/latest/configuration/",
        "CrewAI documentation: https://docs.crewai.com/"
    ]
    for ref in refs:
        para = doc.add_paragraph(style="List Bullet")
        para.add_run(ref)

    doc.save(OUT)
    print(OUT)

if __name__ == "__main__":
    main()
