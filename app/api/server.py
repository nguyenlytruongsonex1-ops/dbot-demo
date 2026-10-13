from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from app.config import get_settings
from app.db import fetch_one
from app.diagnosis.orchestrator import diagnose, list_reports
from app.schemas import DiagnoseRequest
from app.tools.registry import tool_metadata
from scenarios.run import SCENARIOS, prepare

app = FastAPI(title="D-Bot Demo", version="0.1.0")

@app.get("/health")
def health():
    try:
        row = fetch_one("SELECT 1 AS ok")
        return {"status": "ok", "database": row is not None, "llm_mode": get_settings().llm_mode}
    except Exception as exc:
        return {"status": "degraded", "database": False, "error": str(exc), "llm_mode": get_settings().llm_mode}

@app.get("/api/scenarios")
def scenarios(): return {"scenarios": SCENARIOS}

@app.get("/api/tools")
def tools(): return {"tools": tool_metadata()}

@app.post("/api/scenarios/{name}/prepare")
def prepare_scenario(name: str):
    if name not in SCENARIOS: raise HTTPException(404, "unknown scenario")
    try: return prepare(name)
    except Exception as exc: raise HTTPException(500, str(exc))

@app.post("/api/diagnose")
def run_diagnosis(request: DiagnoseRequest):
    try:
        if request.prepare: prepare(request.scenario)
        return diagnose(request.scenario, request.user_context).model_dump()
    except Exception as exc:
        raise HTTPException(500, str(exc))

@app.get("/api/reports")
def reports(): return {"reports": list_reports()}

@app.get("/", response_class=HTMLResponse)
def index():
    return """<!doctype html><html><head><meta charset='utf-8'><title>D-Bot Demo</title><style>body{font-family:system-ui;max-width:960px;margin:40px auto;padding:0 20px;color:#172033}button{padding:10px 14px;margin:4px;cursor:pointer}pre{background:#f4f6f8;padding:16px;overflow:auto;border-radius:8px}.card{border:1px solid #ddd;border-radius:10px;padding:16px;margin:12px 0}</style></head><body><h1>D-Bot Demo</h1><p>CrewAI-inspired database diagnosis with read-only tools.</p><div class='card'><label>Scenario <select id='scenario'></select></label><button onclick='runDiag()'>Prepare + Diagnose</button><button onclick='health()'>Health</button></div><pre id='out'>Choose a scenario.</pre><script>async function load(){let r=await fetch('/api/scenarios');let d=await r.json();scenario.innerHTML=d.scenarios.map(x=>`<option>${x}</option>`).join('')}async function runDiag(){out.textContent='Running...';let r=await fetch('/api/diagnose',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({scenario:scenario.value,prepare:true})});out.textContent=JSON.stringify(await r.json(),null,2)}async function health(){out.textContent=JSON.stringify(await (await fetch('/health')).json(),null,2)}load()</script></body></html>"""
