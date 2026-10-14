import json
import uuid
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from app.chat import answer as chat_answer
from app.config import get_settings
from app.db import fetch_one
from app.diagnosis.orchestrator import diagnose, list_reports
from app.incident_store import append_chat, clear_incidents, get_incident, list_incidents, upsert
from app.metrics import render_metrics
from app.scenarios import SCENARIOS, clear, state, trigger
from app.schemas import ChatRequest, DiagnoseRequest
from app.tools.registry import tool_metadata

app = FastAPI(title="D-Bot Light", version="0.2.0")

@app.get("/health")
def health():
    try:
        row = fetch_one("SELECT 1 AS ok")
        return {"status": "ok", "database": row is not None, "llm_mode": get_settings().llm_mode, "monitoring": "prometheus"}
    except Exception as exc:
        return {"status": "degraded", "database": False, "error": str(exc), "llm_mode": get_settings().llm_mode}

@app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    return render_metrics()

@app.get("/api/scenarios")
def scenarios():
    return {"scenarios": SCENARIOS, "state": state()}

@app.post("/api/scenarios/{name}/trigger")
def trigger_scenario(name: str):
    try: return trigger(name)
    except ValueError as exc: raise HTTPException(404, str(exc))
    except Exception as exc: raise HTTPException(500, str(exc))

@app.post("/api/scenarios/clear")
def clear_scenarios():
    try: return clear()
    except Exception as exc: raise HTTPException(500, str(exc))

@app.post("/api/scenarios/{name}/clear")
def clear_scenario(name: str):
    try: return clear(name)
    except ValueError as exc: raise HTTPException(404, str(exc))
    except Exception as exc: raise HTTPException(500, str(exc))

@app.get("/api/tools")
def tools(): return {"tools": tool_metadata()}

@app.post("/api/diagnose")
def run_diagnosis(request: DiagnoseRequest):
    try:
        if request.prepare: trigger(request.scenario)
        report = diagnose(request.scenario, request.user_context)
        item = report.model_dump()
        item.update({"created_at": datetime.now(timezone.utc).isoformat(), "source": "user", "chat": []})
        upsert(item)
        return item
    except Exception as exc:
        raise HTTPException(500, str(exc))

@app.get("/api/incidents")
def incidents(): return {"incidents": list_incidents()}

@app.post("/api/incidents/clear")
def clear_incident_list():
    return {"cleared": clear_incidents()}

@app.get("/api/incidents/{incident_id}")
def incident(incident_id: str):
    item = get_incident(incident_id)
    if not item: raise HTTPException(404, "incident not found")
    return item

@app.post("/api/incidents/{incident_id}/chat")
def chat(incident_id: str, request: ChatRequest):
    item = get_incident(incident_id)
    if not item: raise HTTPException(404, "incident not found")
    response = chat_answer(item, request.message)
    append_chat(incident_id, "user", request.message)
    append_chat(incident_id, "assistant", response)
    return {"incident_id": incident_id, "answer": response}

@app.post("/webhooks/alertmanager")
async def alertmanager_webhook(request: Request):
    payload = await request.json()
    alerts = payload.get("alerts", [])
    created = []
    for alert in alerts:
        labels = alert.get("labels", {})
        anomaly = labels.get("anomaly_type", "workload_contention")
        if anomaly not in SCENARIOS: anomaly = "workload_contention"
        fingerprint = alert.get("fingerprint") or str(uuid.uuid4())
        incident_id = f"alert-{fingerprint}"
        status = alert.get("status", payload.get("status", "firing"))
        if status == "resolved":
            existing = get_incident(incident_id)
            if existing:
                existing["status"] = "resolved"
                existing["resolved_at"] = datetime.now(timezone.utc).isoformat()
                upsert(existing)
                created.append(existing)
            continue
        report = diagnose(anomaly, user_context=alert.get("annotations", {}).get("description", ""), prepare=False)
        item = report.model_dump()
        item.update({
            "incident_id": incident_id,
            "status": "firing",
            "source": "alertmanager",
            "fingerprint": fingerprint,
            "alert": alert,
            "received_at": datetime.now(timezone.utc).isoformat(),
            "chat": [],
        })
        upsert(item)
        created.append(item)
    return {"received": True, "status": payload.get("status"), "incidents": [x.get("incident_id") for x in created]}

@app.get("/api/reports")
def reports(): return {"reports": list_reports()}

@app.get("/", response_class=HTMLResponse)
def index():
    return """<!doctype html>
<html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>D-Bot Light</title>
<style>
:root{--bg:#0b1020;--panel:#131b31;--line:#2b3858;--ink:#edf3ff;--muted:#9eaccb;--accent:#55d6be;--warn:#ffbd69;--danger:#ff7188}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 10% 0,#19264a 0,#0b1020 42%);color:var(--ink);font:14px/1.5 Inter,system-ui,sans-serif}header{padding:28px 32px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center}h1{margin:0;font-size:25px;letter-spacing:-.03em}h2{font-size:16px;margin:0 0 12px}.tag{color:var(--accent);font-size:12px;letter-spacing:.12em;text-transform:uppercase}.layout{display:grid;grid-template-columns:300px 1fr;min-height:calc(100vh - 90px)}aside{padding:22px;border-right:1px solid var(--line)}main{padding:24px;max-width:1200px;width:100%}.panel{background:rgba(19,27,49,.86);border:1px solid var(--line);border-radius:14px;padding:18px;margin-bottom:16px;box-shadow:0 14px 40px rgba(0,0,0,.15)}button{border:1px solid #3d5078;background:#1a2949;color:var(--ink);padding:9px 11px;border-radius:8px;cursor:pointer;margin:3px 0;width:100%;text-align:left}button:hover{border-color:var(--accent)}button.primary{background:var(--accent);color:#07151a;border-color:var(--accent);font-weight:700}.scenario{display:flex;gap:8px;align-items:center}.scenario button{flex:1}.scenario button.stop{flex:0 0 auto;width:auto;color:#ffb4c0;border-color:#7a3148}.dot{width:8px;height:8px;border-radius:99px;background:#66738f}.dot.active{background:var(--danger);box-shadow:0 0 9px var(--danger)}.muted{color:var(--muted)}.rowhead{display:flex;justify-content:space-between;align-items:center;gap:8px}.rowhead h2{margin:0}.rowhead button{width:auto;text-align:center;color:#ffb4c0;border-color:#7a3148}.incident{padding:13px;border:1px solid var(--line);border-radius:10px;margin:8px 0;cursor:pointer}.incident.selected{border-color:var(--accent)}.incident strong{display:block}.pill{display:inline-block;padding:2px 7px;border-radius:99px;font-size:11px;margin-top:5px;background:#263455;color:var(--muted)}.pill.firing{background:#51263a;color:#ff9fb0}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.kv{display:grid;grid-template-columns:140px 1fr;gap:5px;color:var(--muted)}.kv b{color:var(--ink)}pre{white-space:pre-wrap;word-break:break-word;background:#0a0f1d;border:1px solid var(--line);border-radius:9px;padding:12px;max-height:300px;overflow:auto;font-size:12px}.chat{min-height:190px;max-height:320px;overflow:auto;border:1px solid var(--line);padding:12px;border-radius:9px;background:#0b1224}.msg{padding:8px 10px;border-radius:9px;margin:7px 0;max-width:88%}.msg.user{margin-left:auto;background:#1d4160}.msg.assistant{background:#1d2941}.chatrow{display:flex;gap:8px;margin-top:10px}.chatrow input{flex:1;background:#0b1224;border:1px solid var(--line);border-radius:8px;color:var(--ink);padding:10px}.chatrow button{width:auto;text-align:center}.empty{padding:36px;text-align:center;color:var(--muted)}@media(max-width:800px){.layout{grid-template-columns:1fr}aside{border-right:0;border-bottom:1px solid var(--line)}.grid{grid-template-columns:1fr}}
</style></head>
<body><header><div><div class='tag'>Alert-driven database diagnosis</div><h1>D-Bot Light</h1></div><div id='health' class='muted'>checking health...</div></header>
<div class='layout'><aside><div class='panel'><h2>Trigger demo workload</h2><p class='muted'>Tạo anomaly có kiểm soát. Prometheus sẽ phát hiện rồi gửi alert vào D-Bot. Workload đang chạy có nút Dừng.</p><div id='scenarios'></div><button onclick='clearAll()'>Clear all scenarios</button></div><div class='panel'><h2>Flow</h2><div class='muted'>Scenario → PostgreSQL → Prometheus → Alertmanager → D-Bot → CrewAI → Chat</div></div></aside>
<main><div class='grid'><section class='panel'><div class='rowhead'><h2>Incidents</h2><button onclick='clearIncidents()'>Clear</button></div><div id='incidents'><div class='empty'>Chưa có incident. Trigger một scenario để bắt đầu.</div></div></section><section class='panel'><h2>Selected incident</h2><div id='detail'><div class='empty'>Chọn incident để xem diagnosis và chat.</div></div></section></div></main></div>
<script>
let selected=null,incidents=[],chatDrafts={},detailKey='';
const $=id=>document.getElementById(id);
async function api(url,opt){let r=await fetch(url,opt);return await r.json()}
async function loadHealth(){let d=await api('/health');$('health').textContent=(d.status==='ok'?'● healthy':'● degraded')+' · '+d.llm_mode;$('health').style.color=d.status==='ok'?'#55d6be':'#ffbd69'}
async function loadScenarios(){let d=await api('/api/scenarios');$('scenarios').innerHTML=d.scenarios.map(s=>{let st=d.state.find(x=>x.scenario===s);let active=!!(st&&st.active);return `<div class='scenario'><span class='dot ${active?'active':''}'></span><button onclick="trigger('${s}')">${s}</button>${active?`<button class='stop' onclick="stopScenario('${s}')">Dừng</button>`:''}</div>`}).join('')}
async function trigger(s){await api('/api/scenarios/'+encodeURIComponent(s)+'/trigger',{method:'POST'});await loadScenarios();setTimeout(refresh,1200)}
async function stopScenario(s){await api('/api/scenarios/'+encodeURIComponent(s)+'/clear',{method:'POST'});await loadScenarios()}
async function clearAll(){await api('/api/scenarios/clear',{method:'POST'});await loadScenarios()}
async function clearIncidents(){if(!incidents.length)return;if(!confirm('Xóa toàn bộ danh sách incident trên trang này?'))return;await api('/api/incidents/clear',{method:'POST'});incidents=[];selected=null;detailKey='';chatDrafts={};$('detail').innerHTML='<div class="empty">Chọn incident để xem diagnosis và chat.</div>';renderIncidents()}
async function refresh(){let d=await api('/api/incidents');incidents=d.incidents;renderIncidents();if(selected){let found=incidents.find(x=>x.incident_id===selected);if(found)renderDetail(found)}await loadScenarios();await loadHealth()}
function renderIncidents(){if(!incidents.length){$('incidents').innerHTML='<div class="empty">Chưa có incident. Trigger một scenario để bắt đầu.</div>';return}$('incidents').innerHTML=incidents.map(x=>`<div class="incident ${x.incident_id===selected?'selected':''}" onclick="selectIncident('${x.incident_id}')"><strong>${x.scenario}</strong><span class="muted">${x.summary||'Diagnosis pending'}</span><br><span class="pill ${x.status==='firing'?'firing':''}">${x.status||'completed'} · ${x.source||'user'}</span></div>`).join('')}
function selectIncident(id){rememberDraft();selected=id;let item=incidents.find(x=>x.incident_id===id);renderIncidents();renderDetail(item)}
function bodyHtml(x){let rc=(x.root_causes||[]).map(r=>`<li><b>${r.name}</b> · confidence ${r.confidence}<br><span class="muted">${(r.evidence||[]).join(', ')}</span></li>`).join('');let rec=(x.recommendations||[]).map(r=>`<li><b>${r.action}</b><br>${r.rationale}<br><span class="pill">requires approval</span></li>`).join('');return `<div class='kv'><b>Status</b><span>${x.status}</span><b>Mode</b><span>${x.mode}</span><b>Summary</b><span>${x.summary}</span></div><h3>Root cause</h3><ul>${rc}</ul><h3>Recommendation</h3><ul>${rec}</ul><details><summary>Evidence</summary><pre>${JSON.stringify(x.evidence||[],null,2)}</pre></details>`}
function chatHtml(x){return (x.chat||[]).map(m=>`<div class="msg ${m.role}">${m.content}</div>`).join('')||'<div class="muted">Hỏi thêm về incident này bằng ngôn ngữ tự nhiên.</div>'}
function viewKey(x){return JSON.stringify([x.incident_id,x.status,x.mode,x.summary,x.root_causes,x.recommendations,x.evidence,x.chat])}
function rememberDraft(){let input=$('chatinput');if(input&&input.dataset.incident)chatDrafts[input.dataset.incident]=input.value}
function renderDetail(x){if(!x){$('detail').innerHTML='<div class="empty">Incident không tồn tại.</div>';detailKey='';return}let key=viewKey(x);let input=$('chatinput');let same=input&&input.dataset.incident===x.incident_id;if(same&&key===detailKey)return;if(same&&document.activeElement===input&&$('detail-body')&&$('chatbox')){chatDrafts[x.incident_id]=input.value;$('detail-body').innerHTML=bodyHtml(x);let box=$('chatbox');let top=box.scrollTop;box.innerHTML=chatHtml(x);box.scrollTop=top;detailKey=key;return}let draft=chatDrafts[x.incident_id]||'';$('detail').innerHTML=`<div id='detail-body'>${bodyHtml(x)}</div><h3>DBA chat</h3><div class='chat' id='chatbox'>${chatHtml(x)}</div><div class='chatrow'><input id='chatinput' data-incident='${x.incident_id}' placeholder='Ví dụ: Có chắc do thiếu index không?'><button onclick='sendChat()'>Gửi</button></div>`;let el=$('chatinput');el.value=draft;el.addEventListener('input',()=>{chatDrafts[x.incident_id]=el.value});detailKey=key}
async function sendChat(){let input=$('chatinput');if(!input||!input.value||!selected)return;let msg=input.value;input.value='';chatDrafts[selected]='';await api('/api/incidents/'+selected+'/chat',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({message:msg})});let found=(await api('/api/incidents/'+selected));incidents=incidents.map(x=>x.incident_id===selected?found:x);renderDetail(found)}
refresh();setInterval(refresh,5000);
</script></body></html>"""
