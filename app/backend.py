"""Backend FastAPI (API nội bộ cho Streamlit): danh sách alert, cài đặt,
chạy và dừng kịch bản, tải kịch bản lên, xếp hàng phân tích cho dbot-worker."""
import os
import re
import threading
import time

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile

from app.common import (PG_SCENARIO_PASSWORD, PG_SCENARIO_USER, SCENARIO_DIR, alert_to_dict,
                        bump_version, get_setting, get_version, pg_connect, scenario_header,
                        set_setting, split_sql, store)
from app import common

app = FastAPI(title="D-Bot Demo API")
SETTINGS = {"auto_analyze": "1", "monitor_paused": "0", "default_llm": common.LLM_PROVIDER}
NAME_RE = re.compile(r"^[a-z0-9_]{2,40}$")

runs = {}  # tên kịch bản -> trạng thái lần chạy gần nhất
runs_lock = threading.Lock()


def touch():
    with store() as con:
        bump_version(con)


@app.get("/health")
def health():
    return {"ok": True}


# ---------------- Cài đặt ----------------
@app.get("/api/settings")
def get_settings():
    with store() as con:
        out = {k: get_setting(con, k, d) for k, d in SETTINGS.items()}
        hb = get_setting(con, "monitor_heartbeat", "")
        out["version"] = get_version(con)
    ts, _, status = hb.partition("|")
    out["monitor_status"] = status or "unknown"
    out["monitor_last_scan_sec"] = round(time.time() - float(ts), 1) if ts else None
    return out


@app.put("/api/settings")
def put_settings(values: dict = Body(...)):
    with store() as con:
        for k, v in values.items():
            if k not in SETTINGS:
                raise HTTPException(400, f"Không có cài đặt {k}")
            set_setting(con, k, v)
        bump_version(con)
    return get_settings()


# ---------------- Alert ----------------
@app.get("/api/alerts")
def list_alerts(limit: int = 100):
    with store() as con:
        rs = con.execute("SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [alert_to_dict(r) for r in rs]


@app.get("/api/alerts/{alert_id}")
def get_alert(alert_id: int):
    with store() as con:
        r = con.execute("SELECT * FROM alerts WHERE id=?", (alert_id,)).fetchone()
    if not r:
        raise HTTPException(404, "Không tìm thấy alert")
    return alert_to_dict(r)


@app.post("/api/alerts/{alert_id}/analyze")
def analyze(alert_id: int, provider: str = ""):
    """Xếp hàng phân tích (lần đầu hoặc phân tích lại), có thể chọn nguồn LLM."""
    if provider and provider not in ("claude", "gemini", "openai", "ollama", "mock"):
        raise HTTPException(400, "Nguồn LLM không hợp lệ")
    with store() as con:
        r = con.execute("SELECT analysis_status FROM alerts WHERE id=?", (alert_id,)).fetchone()
        if not r:
            raise HTTPException(404, "Không tìm thấy alert")
        if r["analysis_status"] in ("analyzing", "queued"):
            return {"status": r["analysis_status"]}
        con.execute("UPDATE alerts SET analysis_status='queued', llm_provider=COALESCE(NULLIF(?, ''), llm_provider), "
                    "updated_at=? WHERE id=?", (provider, time.time(), alert_id))
        bump_version(con)
    return {"status": "queued"}


@app.delete("/api/alerts")
def clear_alerts():
    """Xóa lịch sử alert (dùng khi bắt đầu một buổi demo mới)."""
    with store() as con:
        n = con.execute("DELETE FROM alerts").rowcount
        bump_version(con)
    return {"deleted": n}


# ---------------- Kịch bản ----------------
def scenario_path(name):
    if not NAME_RE.match(name):
        raise HTTPException(400, "Tên kịch bản chỉ gồm chữ thường, số và dấu gạch dưới")
    return os.path.join(SCENARIO_DIR, f"{name}.sql")


@app.get("/api/scenarios")
def list_scenarios():
    out = []
    for fn in sorted(os.listdir(SCENARIO_DIR)):
        if fn.endswith(".sql"):
            name = fn[:-4]
            with runs_lock:
                st = dict(runs.get(name, {"status": "idle"}))
            out.append({"name": name, "description": scenario_header(os.path.join(SCENARIO_DIR, fn)), **st})
    return out


def _run(name, sql):
    try:
        conn = pg_connect(PG_SCENARIO_USER, PG_SCENARIO_PASSWORD, app_name=f"scenario:{name}")
    except Exception as e:  # noqa: BLE001
        with runs_lock:
            runs[name] = {"status": "error", "message": str(e), "finished_at": time.time()}
        touch(); return
    with runs_lock:
        runs[name].update(pid=conn.info.backend_pid)
    touch()
    status, msg = "finished", ""
    try:
        with conn.cursor() as cur:
            for stmt in split_sql(sql):
                with runs_lock:
                    if runs[name].get("stop"):
                        break
                cur.execute(stmt)
    except Exception as e:  # noqa: BLE001
        status, msg = "error", str(e).strip().splitlines()[0]
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass
    with runs_lock:
        if runs[name].get("stop"):
            status, msg = "stopped", "Đã dừng theo yêu cầu"
        runs[name].update(status=status, message=msg, finished_at=time.time())
    touch()


@app.post("/api/scenarios/{name}/run")
def run_scenario(name: str):
    path = scenario_path(name)
    if not os.path.exists(path):
        raise HTTPException(404, "Không có kịch bản này")
    with runs_lock:
        if runs.get(name, {}).get("status") == "running":
            raise HTTPException(409, "Kịch bản đang chạy")
        runs[name] = {"status": "running", "started_at": time.time(), "message": ""}
    with open(path, encoding="utf-8") as f:
        sql = f.read()
    threading.Thread(target=_run, args=(name, sql), daemon=True).start()
    return {"status": "running"}


@app.post("/api/scenarios/{name}/stop")
def stop_scenario(name: str):
    with runs_lock:
        st = runs.get(name)
        if not st or st.get("status") != "running":
            return {"status": st.get("status") if st else "idle"}
        st["stop"] = True
        pid = st.get("pid")
    if pid:
        with pg_connect(app_name="dbot-backend") as c:
            c.execute("SELECT pg_terminate_backend(%s)", (pid,))
    return {"status": "stopping"}


@app.post("/api/scenarios/upload")
async def upload_scenario(name: str = Form(...), file: UploadFile = File(...)):
    path = scenario_path(name)
    if not (file.filename or "").endswith(".sql"):
        raise HTTPException(400, "Chỉ nhận file .sql")
    data = await file.read()
    if len(data) > 200_000:
        raise HTTPException(400, "File quá lớn (tối đa 200 KB)")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(400, "File phải mã hóa UTF-8")
    if not split_sql(text):
        raise HTTPException(400, "File không có câu lệnh SQL nào")
    if not text.lstrip().startswith("--"):
        text = f"-- Kịch bản: {name} (người dùng tải lên)\n" + text
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    touch()
    return {"name": name, "saved": True}
