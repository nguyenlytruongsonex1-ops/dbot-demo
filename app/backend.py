"""Backend FastAPI: API alert, WebSocket real time, chạy/dừng kịch bản, upload,
và nút nhờ AI phân tích (giao việc cho dbot-worker qua SQLite)."""
import asyncio
import os
import re
import threading
import time

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.common import (PG_SCENARIO_PASSWORD, PG_SCENARIO_USER, SCENARIO_DIR, alert_to_dict,
                        bump_version, get_version, pg_connect, scenario_header, split_sql, store)

app = FastAPI(title="D-Bot Demo")
STATIC = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=STATIC), name="static")
NAME_RE = re.compile(r"^[a-z0-9_]{2,40}$")

runs = {}  # tên kịch bản -> trạng thái lần chạy gần nhất
runs_lock = threading.Lock()


def touch():
    with store() as con:
        bump_version(con)


# ---------------- Trang web ----------------
@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC, "index.html"))


@app.get("/alert/{alert_id}")
def alert_page(alert_id: int):
    return FileResponse(os.path.join(STATIC, "detail.html"))


@app.get("/health")
def health():
    return {"ok": True}


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
def analyze(alert_id: int):
    with store() as con:
        r = con.execute("SELECT analysis_status FROM alerts WHERE id=?", (alert_id,)).fetchone()
        if not r:
            raise HTTPException(404, "Không tìm thấy alert")
        if r["analysis_status"] == "analyzing":
            return {"status": "analyzing"}
        con.execute("UPDATE alerts SET analysis_status='analyzing', report=NULL, updated_at=? WHERE id=?",
                    (time.time(), alert_id))
        bump_version(con)
    return {"status": "analyzing"}


@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    last = None
    try:
        while True:
            with store() as con:
                v = get_version(con)
            if v != last:
                last = v
                await websocket.send_json({"type": "changed", "version": v})
            await asyncio.sleep(1)
    except (WebSocketDisconnect, RuntimeError):
        pass


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
