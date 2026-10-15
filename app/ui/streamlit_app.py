"""Giao diện Streamlit duy nhất của demo D-Bot trên PostgreSQL.

Chạy: streamlit run app/ui/streamlit_app.py
Tab 1 đến 4 giữ luồng trình diễn từng bước của dự án "LLM As DBA" (Nhóm 3),
tab 5 là giám sát realtime chạy tự động.
"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pandas as pd  # noqa: E402
import requests  # noqa: E402
import streamlit as st  # noqa: E402

from app import common, core_demo as core, llm  # noqa: E402

API = common.BACKEND_URL
st.set_page_config(page_title="D-Bot Demo trên PostgreSQL", page_icon="🩺", layout="wide")
ss = st.session_state
for k, v in {"res": {}, "answers": {}, "lock": None, "tune": [], "ai_cfgs": {}, "sel_alert": None}.items():
    ss.setdefault(k, v)


def api(method, path, **kw):
    r = requests.request(method, API + path, timeout=15, **kw)
    r.raise_for_status()
    return r.json()


# =====================================================================
# Thanh bên: nguồn LLM
# =====================================================================
with st.sidebar:
    st.header("Cấu hình")
    st.caption(f"PostgreSQL: {common.PG_HOST}:{common.PG_PORT}/{common.PG_DB}")
    names = llm.PROVIDERS
    default = common.LLM_PROVIDER if common.LLM_PROVIDER in names else "ollama"
    provider = st.radio("Nguồn LLM cho tab 1 đến 4", names, index=names.index(default),
                        format_func=lambda p: llm.LABELS[p] + ("" if llm.available(p) else " (chưa có key)"))
    st.caption(f"Model: {llm.model_of(provider)}. Nếu thiếu key hoặc gọi lỗi, hệ thống tự chuyển sang Ollama.")
    st.caption("API key đọc từ file .env, không hiện trên giao diện.")


def ask(prompt, temperature=0.3):
    text, used, note = llm.ask(prompt, provider, temperature=temperature)
    if note:
        st.info(note)
    return f"(Nguồn: {llm.LABELS[used]})\n\n{text}"


def ai_box(kb, label, prompt, key):
    with st.expander(f"Xem prompt {label}"):
        st.code(prompt, language="text")
    ans_key = f"{kb}_{key}"
    if st.button(f"Hỏi AI, prompt {label}", key=f"btn_{ans_key}"):
        with st.spinner("Đang hỏi AI..."):
            try:
                ss.answers[ans_key] = ask(prompt)
            except Exception as e:  # noqa: BLE001
                st.error(str(e))
    ans = ss.answers.get(ans_key)
    if ans:
        st.markdown(ans)
        ok, spec = core.auto_grade(kb, ans)
        c1, c2 = st.columns(2)
        ok = c1.checkbox("Đúng nguyên nhân", ok, key=f"ok_{ans_key}")
        spec = c2.checkbox("Có lệnh sửa cụ thể", spec, key=f"sp_{ans_key}")
        ss.res.setdefault("grades", {})[ans_key] = (ok, spec)


def compare_chart(before, after):
    st.bar_chart(pd.DataFrame({"giây": [before, after]}, index=["Trước khi sửa", "Sau khi sửa"]), y="giây")


def two_prompts(kb, symptom, tool_text):
    st.markdown("**Bước 3. Hỏi AI theo hai cách**")
    a, b = st.columns(2)
    with a:
        st.markdown("Prompt A: chỉ có triệu chứng")
        ai_box(kb, "A", core.prompt_a(symptom), "A")
    with b:
        st.markdown("Prompt B: kiểu D-Bot, có thẻ kinh nghiệm và số đo")
        ai_box(kb, "B", core.prompt_b(symptom, tool_text), "B")


st.title("D-Bot Demo: AI chẩn đoán và tối ưu PostgreSQL")
st.caption("Dữ liệu TPC-H SF 0.1. Tab 1 đến 4 chuyển từ dự án \"LLM As DBA\" của Nhóm 3 (bản gốc MySQL và Streamlit).")

tabs = st.tabs(["0. Chuẩn bị", "1. Thiếu index", "2. Truy vấn con", "3. Tranh chấp khóa",
                "4. Mini λ-Tune", "5. Giám sát realtime", "6. Tổng kết"])

# ---------------- TAB 0 ----------------
with tabs[0]:
    st.subheader("Bước 0. Kiểm tra kết nối và dữ liệu")
    if st.button("Kiểm tra"):
        try:
            s = core.data_status()
            st.success(f"Kết nối PostgreSQL {s['version']} thành công. "
                       f"pg_stat_statements: {'đã bật' if s['pg_stat_statements'] else 'chưa bật'}.")
            st.dataframe(pd.DataFrame(s["tables"]), width="stretch")
        except Exception as e:  # noqa: BLE001
            st.error(f"Không kết nối được PostgreSQL: {e}")
        try:
            api("GET", "/health")
            st.success("Backend nội bộ đang chạy.")
        except Exception as e:  # noqa: BLE001
            st.warning(f"Không gọi được backend ({API}): {e}")
        st.write({llm.LABELS[p]: ("có key" if llm.available(p) else "chưa có key") for p in ("claude", "gemini", "openai")})
        st.write(f"Ollama ({common.OLLAMA_BASE_URL}): {'đang chạy' if llm.ollama_ok() else 'không kết nối được'}")

# ---------------- TAB 1 ----------------
with tabs[1]:
    st.subheader("Kịch bản 1. Thiếu index")
    st.markdown(f"Bước 1. Xóa index rồi chạy {core.KB1_N} truy vấn lọc theo cột l_partkey trên bảng lineitem.")
    st.code(core.KB1_SQL.replace("%s", "?"), language="sql")
    if st.button("Chạy workload (chưa có index)", key="kb1_run"):
        with st.spinner("Đang chạy..."):
            core.kb1_break()
            ss.res["kb1_before"] = core.kb1_workload()
            ss.res.pop("kb1_after", None)
    if "kb1_before" in ss.res:
        st.metric(f"Thời gian {core.KB1_N} truy vấn", f"{ss.res['kb1_before']:.2f} giây")
        st.markdown("Bước 2. Công cụ đo kiểu D-Bot: EXPLAIN, pg_stat_statements, pg_stat_user_tables, pg_locks.")
        if st.button("Thu thập số đo", key="kb1_tool"):
            ss.res["kb1_tools"] = core.kb1_tools()
    if "kb1_tools" in ss.res:
        t = ss.res["kb1_tools"]
        st.code("\n".join(t["explain"]), language="text")
        st.dataframe(pd.DataFrame(t["statements"]), width="stretch")
        st.dataframe(pd.DataFrame(t["table"]), width="stretch")
        st.write(f"Số khóa đang chờ trong pg_locks: {t['lock_waits']}")
        symptom = (f"Một chức năng báo cáo gọi {core.KB1_N} truy vấn liên tiếp mất {ss.res['kb1_before']:.1f} giây, "
                   "CPU máy chủ tăng cao. Bảng lineitem có khoảng 600.000 dòng.")
        tool_text = (f"EXPLAIN {core.KB1_EXPLAIN}:\n" + "\n".join(t["explain"]) +
                     f"\npg_stat_statements:\n{core.fmt_rows(t['statements'])}\n"
                     f"pg_stat_user_tables (lineitem):\n{core.fmt_rows(t['table'])}\n"
                     f"pg_locks chưa cấp: {t['lock_waits']}")
        two_prompts("kb1", symptom, tool_text)
        st.markdown("Bước 4. Sửa theo đề xuất rồi chạy lại.")
        st.code(core.KB1_FIX, language="sql")
        if st.button("Tạo index và chạy lại", key="kb1_fix"):
            with st.spinner("Đang tạo index..."):
                _, exp2 = core.kb1_fix()
                ss.res["kb1_after"] = core.kb1_workload()
                ss.res["kb1_exp2"] = exp2
    if "kb1_after" in ss.res:
        st.code("\n".join(ss.res["kb1_exp2"]), language="text")
        compare_chart(ss.res["kb1_before"], ss.res["kb1_after"])
        st.success(f"{ss.res['kb1_before']:.2f} giây xuống {ss.res['kb1_after']:.2f} giây "
                   f"(nhanh hơn {ss.res['kb1_before'] / max(ss.res['kb1_after'], 1e-4):.1f} lần)")

# ---------------- TAB 2 ----------------
with tabs[2]:
    st.subheader("Kịch bản 2. Truy vấn con tương quan")
    st.markdown("Bước 1. Đếm đơn hàng có giá trị cao hơn trung bình của chính khách hàng đó.")
    st.code(core.KB2_SLOW, language="sql")
    if st.button("Chạy truy vấn chậm", key="kb2_run"):
        with st.spinner("Đang chạy, có thể mất 5 đến 30 giây..."):
            ss.res["kb2_before"] = core.kb2_run(core.KB2_SLOW)
            ss.res.pop("kb2_after", None)
    if "kb2_before" in ss.res:
        t, n, exp = ss.res["kb2_before"]
        st.metric("Thời gian", f"{t:.2f} giây", help=f"Kết quả count = {n}")
        st.markdown("Bước 2. Công cụ đo: EXPLAIN")
        st.code("\n".join(exp), language="text")
        symptom = f"Một báo cáo đơn hàng chạy mất {t:.1f} giây dù chỉ xét vài nghìn đơn, CPU cao."
        tool_text = f"Câu SQL:\n{core.KB2_SLOW}\nEXPLAIN:\n" + "\n".join(exp) + "\npg_locks chưa cấp: 0"
        two_prompts("kb2", symptom, tool_text)
        st.markdown("Bước 4. Sửa bằng cách viết lại (unnesting).")
        st.code(core.KB2_FAST, language="sql")
        if st.button("Chạy bản viết lại", key="kb2_fix"):
            ss.res["kb2_after"] = core.kb2_run(core.KB2_FAST)
    if "kb2_after" in ss.res:
        t2, n2, exp2 = ss.res["kb2_after"]
        st.code("\n".join(exp2), language="text")
        compare_chart(ss.res["kb2_before"][0], t2)
        st.success(f"{ss.res['kb2_before'][0]:.2f} giây xuống {t2:.3f} giây, cùng kết quả count = {n2}")

# ---------------- TAB 3 ----------------
with tabs[3]:
    st.subheader("Kịch bản 3. Tranh chấp khóa")
    st.markdown("Ba kết nối: A giữ khóa (chưa COMMIT), B cập nhật cùng dòng nên bị chặn, C quan sát pg_locks.")
    c1, c2 = st.columns(2)
    if c1.button("Bước 1. Phiên A: BEGIN và UPDATE (chưa commit)", key="kb3_a"):
        if ss.lock:
            ss.lock.fix()
        ss.lock = core.LockScenario()
        ss.res["kb3_pid"] = ss.lock.start_a()
        ss.res.pop("kb3_after", None)
    if ss.lock and c2.button("Bước 1b. Phiên B: UPDATE cùng dòng", key="kb3_b"):
        ss.lock.start_b()
    if ss.lock:
        st.info(f"Phiên A (pid {ss.res.get('kb3_pid')}) đang giữ khóa. Phiên B: {ss.lock.b_result.get('status')}")
        if st.button("Bước 2. Thu thập số đo (phiên C)", key="kb3_tool"):
            ss.res["kb3_tools"] = ss.lock.tools()
    if "kb3_tools" in ss.res:
        st.dataframe(pd.DataFrame(ss.res["kb3_tools"]), width="stretch")
        symptom = ("Một lệnh UPDATE rất đơn giản (UPDATE tpch.orders SET o_totalprice = o_totalprice - 1 "
                   "WHERE o_orderkey = 1) bị treo, sau một lúc báo lỗi 'canceling statement due to lock timeout'. "
                   "CPU và disk đều thấp.")
        tool_text = f"Kết quả truy vấn pg_stat_activity, pg_blocking_pids:\n{core.fmt_rows(ss.res['kb3_tools'])}"
        two_prompts("kb3", symptom, tool_text)
    if ss.lock and st.button("Bước 4. Sửa: phiên A ROLLBACK", key="kb3_fix"):
        ss.res["kb3_after"] = ss.lock.fix()
        ss.lock = None
    if "kb3_after" in ss.res:
        r = ss.res["kb3_after"]
        st.success(f"Phiên B: {r.get('status')} sau {r.get('seconds', 0):.1f} giây chờ khóa {r.get('error', '')}")

# ---------------- TAB 4 ----------------
with tabs[4]:
    st.subheader("Mini λ-Tune: AI đề xuất cấu hình, hệ thống đo thật rồi chọn")
    st.markdown("Workload gồm 3 truy vấn trên TPC-H, mỗi truy vấn có giới hạn statement_timeout. "
                "Chỉ chạy các lệnh SET ở mức phiên và CREATE INDEX nằm trong danh sách cho phép. "
                "Trong lúc đo, monitor realtime được tạm dừng để không báo nhầm.")
    st.dataframe(pd.DataFrame([{"truy_van": n, "sql": q} for n, q in core.LT_WORKLOAD]), width="stretch")
    c1, c2, c3 = st.columns(3)
    mem = c1.text_input("RAM máy (đưa vào prompt)", "8GB")
    cores_ = c2.text_input("Số CPU", "4")
    k = c3.number_input("Số cấu hình xin AI (k)", 1, 5, 2)
    prompt = core.LT_PROMPT.replace("{mem}", mem).replace("{cores}", cores_)
    with st.expander("Prompt theo mẫu Listing 1 của λ-Tune"):
        st.code(prompt, language="text")
    if st.button(f"Xin AI {k} cấu hình", key="lt_ask"):
        ss.ai_cfgs = {}
        for i in range(int(k)):
            with st.spinner(f"Cấu hình AI-{i + 1}..."):
                try:
                    txt, used, note = llm.ask(prompt, provider, temperature=1.0)
                    ok, bad = core.parse_config(txt)
                    ss.ai_cfgs[f"AI-{i + 1}"] = {"ok": ok, "bad": bad, "nguon": used}
                except Exception as e:  # noqa: BLE001
                    st.error(str(e))
                    break
    for name, c in ss.ai_cfgs.items():
        st.markdown(f"{name} ({llm.LABELS[c['nguon']]}), lệnh được chạy:")
        st.code(";\n".join(c["ok"]) or "(không có lệnh hợp lệ)", language="sql")
        if c["bad"]:
            st.warning(f"Đã chặn {len(c['bad'])} lệnh không nằm trong danh sách cho phép: {c['bad']}")
    use_presets = st.checkbox("Thêm 3 cấu hình mẫu (C1 đến C3) để đối chiếu", value=True)
    if st.button("Chạy thật và đo tất cả cấu hình", type="primary", key="lt_run"):
        configs = {"C0 mặc định": []}
        if use_presets:
            configs.update(core.PRESETS)
        configs.update({n: c["ok"] for n, c in ss.ai_cfgs.items()})
        ss.tune = []
        try:
            api("PUT", "/api/settings", json={"monitor_paused": "1"})
        except Exception:  # noqa: BLE001
            st.warning("Không tạm dừng được monitor (backend chưa chạy).")
        bar = st.progress(0.0)
        try:
            for i, (n, stmts) in enumerate(configs.items()):
                with st.spinner(f"Đang đo {n}..."):
                    ss.tune.append(core.run_config(n, stmts))
                bar.progress((i + 1) / len(configs))
        finally:
            try:
                api("PUT", "/api/settings", json={"monitor_paused": "0"})
            except Exception:  # noqa: BLE001
                pass
    if ss.tune:
        df = pd.DataFrame([{k2: v for k2, v in r.items() if k2 in ("cau_hinh", "giay_workload", "giay_ap_dung", "bi_timeout")}
                           for r in ss.tune])
        st.bar_chart(df.set_index("cau_hinh"), y="giay_workload")
        st.dataframe(df, width="stretch")
        best = min(ss.tune, key=lambda r: r["giay_workload"])
        worst = max(ss.tune, key=lambda r: r["giay_workload"])
        st.success(f"Chọn {best['cau_hinh']}: {best['giay_workload']} giây. Tệ nhất: {worst['cau_hinh']} "
                   f"({worst['giay_workload']} giây). Vì vậy λ-Tune phải đo thật chứ không tin lời AI.")
        for r in ss.tune:
            if r.get("loi"):
                st.warning(f"{r['cau_hinh']}: lệnh lỗi khi áp dụng {r['loi']}")

# ---------------- TAB 5 ----------------
STATUS_LABEL = {"none": "chờ phân tích", "queued": "trong hàng đợi", "analyzing": "đang phân tích",
                "done": "đã có báo cáo", "error": "lỗi phân tích"}
SEV_ICON = {"critical": "🔴", "warning": "🟠"}


def fmt_time(ts):
    return dt.datetime.fromtimestamp(ts).strftime("%H:%M:%S") if ts else ""


def show_report(a):
    rep = a.get("report")
    if a["analysis_status"] in ("queued", "analyzing"):
        st.info("D-Bot đang phân tích alert này...")
    if not rep:
        return
    used = rep.get("provider")
    st.markdown(f"**Tóm tắt.** {rep.get('summary', '')}")
    st.caption(f"Nguồn LLM: {llm.LABELS.get(used, used)} ({rep.get('model', '')}), "
               f"thời gian phân tích {rep.get('elapsed_sec')} giây")
    for n in rep.get("fallback_notes") or []:
        st.caption(n)
    st.markdown("**Các bước suy luận**")
    for i, s in enumerate(rep.get("steps") or [], 1):
        with st.expander(f"Bước {i}: {s.get('tool', '')}"):
            st.markdown("Quan sát:")
            st.code(str(s.get("observation", ""))[:1500], language="text")
            st.markdown(f"Kết luận: {s.get('conclusion', '')}")
    st.markdown(f"**Nguyên nhân gốc.** {rep.get('root_cause', '')}")
    st.markdown("**Phương án xử lý** (AI chỉ đề xuất, DBA tự quyết định chạy)")
    for r in rep.get("remediation") or []:
        st.markdown(f"- {r.get('action', '')} (rủi ro: {r.get('risk', '')})")
        if r.get("sql"):
            st.code(r["sql"], language="sql")


@st.fragment(run_every=3)
def realtime_panel():
    try:
        settings = api("GET", "/api/settings")
        alerts = api("GET", "/api/alerts")
        scenarios = api("GET", "/api/scenarios")
    except Exception as e:  # noqa: BLE001
        st.error(f"Không gọi được backend ({API}): {e}")
        return
    ms = settings.get("monitor_status")
    last = settings.get("monitor_last_scan_sec")
    st.caption(f"Monitor: {ms}, lần quét cuối cách đây {last} giây. Trang tự làm mới mỗi 3 giây. "
               f"Cập nhật lúc {dt.datetime.now().strftime('%H:%M:%S')}.")

    left, right = st.columns([2, 3])
    with left:
        st.markdown("**Kịch bản sự cố**")
        for s in scenarios:
            c1, c2, c3 = st.columns([3, 1, 1])
            status = s.get("status", "idle")
            c1.markdown(f"`{s['name']}` ({status})", help=s.get("description"))
            if c2.button("Chạy", key=f"run_{s['name']}", disabled=status == "running"):
                try:
                    api("POST", f"/api/scenarios/{s['name']}/run")
                except Exception as e:  # noqa: BLE001
                    st.error(str(e))
            if c3.button("Dừng", key=f"stop_{s['name']}", disabled=status != "running"):
                api("POST", f"/api/scenarios/{s['name']}/stop")
    with right:
        st.markdown("**Alert**")
        if not alerts:
            st.info("Chưa có alert. Hãy chạy một kịch bản ở bên trái.")
        rows = [{"id": a["id"], "": SEV_ICON.get(a["severity"], ""), "tiêu đề": a["title"],
                 "trạng thái": "đã giải quyết" if a["status"] == "resolved" else "đang mở",
                 "phân tích": STATUS_LABEL.get(a["analysis_status"], a["analysis_status"]),
                 "tạo lúc": fmt_time(a["created_at"]), "giải quyết lúc": fmt_time(a.get("resolved_at"))}
                for a in alerts]
        if rows:
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
            ids = [a["id"] for a in alerts]
            cur = ss.sel_alert if ss.sel_alert in ids else ids[0]
            ss.sel_alert = st.selectbox("Xem chi tiết alert", ids, index=ids.index(cur),
                                        format_func=lambda i: f"#{i} " + next(a["title"] for a in alerts if a["id"] == i))
            a = next(x for x in alerts if x["id"] == ss.sel_alert)
            with st.container(border=True):
                st.markdown(f"**#{a['id']} {a['title']}** ({a['type']}, {a['severity']})")
                with st.expander("Số liệu monitor ghi nhận"):
                    st.json(a["details"])
                c1, c2 = st.columns([2, 1])
                choice = c1.selectbox("Nguồn LLM khi phân tích", llm.PROVIDERS, key=f"llm_{a['id']}",
                                      index=llm.PROVIDERS.index(settings.get("default_llm", "ollama"))
                                      if settings.get("default_llm") in llm.PROVIDERS else 3,
                                      format_func=lambda p: llm.LABELS[p])
                label = "Phân tích" if a["analysis_status"] == "none" else "Phân tích lại"
                if c2.button(label, key=f"an_{a['id']}", disabled=a["analysis_status"] in ("queued", "analyzing")):
                    api("POST", f"/api/alerts/{a['id']}/analyze", params={"provider": choice})
                show_report(a)


with tabs[5]:
    st.subheader("Giám sát realtime: phát hiện và phân tích tự động")
    st.markdown("Monitor quét PostgreSQL mỗi vài giây và tạo alert khi vượt ngưỡng. "
                f"Nếu bật tự động phân tích, sau khoảng {int(common.ANALYZE_DEBOUNCE_SEC)} giây mà dấu hiệu vẫn còn, "
                "D-Bot tự nhận alert và viết báo cáo. Alert tự chuyển sang đã giải quyết sau 3 lần quét không còn dấu hiệu.")
    try:
        cfg = api("GET", "/api/settings")
        c1, c2, c3 = st.columns([1, 1, 1])
        auto = c1.toggle("Tự động phân tích", value=cfg.get("auto_analyze", "1") == "1")
        if auto != (cfg.get("auto_analyze", "1") == "1"):
            api("PUT", "/api/settings", json={"auto_analyze": "1" if auto else "0"})
        cur = cfg.get("default_llm") if cfg.get("default_llm") in llm.PROVIDERS else "ollama"
        dl = c2.selectbox("Nguồn LLM mặc định cho tự động phân tích", llm.PROVIDERS,
                          index=llm.PROVIDERS.index(cur), format_func=lambda p: llm.LABELS[p])
        if dl != cur:
            api("PUT", "/api/settings", json={"default_llm": dl})
        if c3.button("Xóa lịch sử alert"):
            api("DELETE", "/api/alerts")
    except Exception as e:  # noqa: BLE001
        st.error(f"Không gọi được backend ({API}): {e}")
    with st.expander("Thêm kịch bản bằng file .sql"):
        name = st.text_input("Tên kịch bản (chữ thường, số, dấu gạch dưới)", key="up_name")
        f = st.file_uploader("File .sql", type=["sql"], key="up_file")
        if st.button("Tải lên", disabled=not (name and f)):
            try:
                r = requests.post(API + "/api/scenarios/upload", data={"name": name},
                                  files={"file": (f.name, f.getvalue(), "text/plain")}, timeout=15)
                if r.status_code == 200:
                    st.success(f"Đã thêm kịch bản {name}.")
                else:
                    st.error(r.json().get("detail", r.text))
            except Exception as e:  # noqa: BLE001
                st.error(str(e))
    realtime_panel()

# ---------------- TAB 6 ----------------
with tabs[6]:
    st.subheader("Tổng kết: bảng chấm AI và hiệu năng")
    g = ss.res.get("grades", {})
    rows = []
    for kb, name in (("kb1", "Thiếu index"), ("kb2", "Truy vấn con tương quan"), ("kb3", "Tranh chấp khóa")):
        row = {"Sự cố": name}
        for p in ("A", "B"):
            ok, spec = g.get(f"{kb}_{p}", (None, None))
            row[f"Prompt {p}: đúng nguyên nhân"] = "chưa chạy" if ok is None else ("đúng" if ok else "sai")
            row[f"Prompt {p}: có lệnh cụ thể"] = "chưa chạy" if spec is None else ("có" if spec else "không")
        rows.append(row)
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    perf = []
    if "kb1_after" in ss.res:
        perf.append({"Kịch bản": "Thiếu index", "Trước (giây)": round(ss.res["kb1_before"], 3),
                     "Sau (giây)": round(ss.res["kb1_after"], 3)})
    if "kb2_after" in ss.res:
        perf.append({"Kịch bản": "Truy vấn con", "Trước (giây)": round(ss.res["kb2_before"][0], 3),
                     "Sau (giây)": round(ss.res["kb2_after"][0], 3)})
    if perf:
        st.dataframe(pd.DataFrame(perf), width="stretch", hide_index=True)
    try:
        alerts = api("GET", "/api/alerts")
        if alerts:
            st.markdown("Thống kê alert realtime")
            st.write({"tổng số": len(alerts),
                      "đã giải quyết": sum(a["status"] == "resolved" for a in alerts),
                      "đã có báo cáo": sum(a["analysis_status"] == "done" for a in alerts)})
    except Exception:  # noqa: BLE001
        pass
    if ss.answers:
        export = "\n\n".join(f"===== {k} =====\n{v}" for k, v in ss.answers.items() if v)
        st.download_button("Tải toàn bộ câu trả lời AI (.txt)", export, file_name="ai_answers.txt")
    st.caption("Mỗi prompt nên chạy 3 lần và ghi cả 3 kết quả vào báo cáo.")
