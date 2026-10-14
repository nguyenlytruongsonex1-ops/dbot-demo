import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from app.config import get_settings
from app.db import fetch_all
from app.knowledge.retriever import retrieve
from app.schemas import DiagnosisReport, Evidence, Recommendation, RootCause
from app.tools.registry import tool_registry

REPORT_DIR = Path(__file__).parents[2] / "reports"

SCENARIO_QUERIES = {
    "slow_query": "slow query missing index join performance explain",
    "lock_contention": "lock contention blocked waiting sessions",
    "workload_contention": "workload contention active sessions CPU",
    "table_bloat": "table bloat dead tuples vacuum",
    "execution_error": "execution error PostgreSQL query",
}

def _call(name: str) -> tuple[object, str]:
    for tool in tool_registry():
        if tool.name == name:
            try:
                raw = tool._run()
                try: return json.loads(raw), "ok"
                except Exception: return raw, "ok"
            except Exception as exc:
                return {"error": str(exc)}, "error"
    return {"error": f"tool {name} not found"}, "error"

def _mock_diagnosis(scenario: str, evidence: list[Evidence], mode: str) -> DiagnosisReport:
    mapping = {
        "slow_query": ("missing_index_or_expensive_plan", 0.82, "Inspect EXPLAIN and add a candidate index after review", "Run EXPLAIN on the slow SELECT; consider a composite index on filter/order columns."),
        "lock_contention": ("lock_contention", 0.95, "Review the blocking transaction", "Inspect the blocking PID and transaction lifecycle; terminate only with human approval."),
        "workload_contention": ("workload_contention", 0.78, "Reduce or schedule concurrent workload", "Review active sessions, wait events, connection limits, and long-running queries."),
        "table_bloat": ("table_bloat_or_delayed_vacuum", 0.86, "Vacuum and analyze during a suitable window", "Run VACUUM/ANALYZE after confirming the maintenance window; review autovacuum settings."),
        "execution_error": ("query_or_schema_execution_error", 0.97, "Fix the query or schema contract", "Classify the PostgreSQL error and correct the application/query; do not change schema automatically."),
    }
    name, confidence, action, rationale = mapping[scenario]
    cause_evidence = [e.source for e in evidence[:3]] or ["scenario definition"]
    return DiagnosisReport(
        incident_id=str(uuid.uuid4()), scenario=scenario, status="completed",
        root_causes=[RootCause(name=name, confidence=confidence, evidence=cause_evidence)],
        evidence=evidence,
        recommendations=[Recommendation(action=action, rationale=rationale, requires_approval=True)],
        summary=f"Likely root cause: {name}. This is a safe demo diagnosis based on collected evidence; remediation was not executed.",
        mode=mode,
    )

def _confidence(value: object) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.5
    if number > 1:
        number = number / 100
    return max(0.0, min(1.0, number))

def _finding_from_result(result: object) -> dict:
    data = getattr(result, "pydantic", None)
    if data is not None:
        return data.model_dump() if hasattr(data, "model_dump") else dict(data)
    data = getattr(result, "json_dict", None)
    if isinstance(data, dict) and (data.get("root_causes") or data.get("summary")):
        return data
    raw = str(getattr(result, "raw", result)).strip()
    raise ValueError(f"no structured diagnosis in crew output: {raw[:500]}")

def _trace_from_result(result: object) -> list[dict]:
    trace = []
    for item in getattr(result, "tasks_output", []) or []:
        agent = getattr(item, "agent", "") or "crew-task"
        text = getattr(item, "summary", None) or getattr(item, "raw", "")
        trace.append({"agent": str(agent), "status": "completed", "summary": str(text)[:500]})
    return trace or [{"crew": "Chief DBA + CPU/Workload + Memory/Database", "status": "completed"}]

def _report_from_crew(scenario: str, evidence: list[Evidence], finding: dict, trace: list[dict] | None = None) -> DiagnosisReport:
    causes = finding.get("root_causes") or []
    actions = finding.get("recommendations") or []
    if not causes or not actions or not str(finding.get("summary") or "").strip():
        raise ValueError("crew finding is missing root causes, recommendations, or summary")
    collected = [e.source for e in evidence[:3]] or ["scenario definition"]
    return DiagnosisReport(
        incident_id=str(uuid.uuid4()),
        scenario=scenario,
        status="completed",
        root_causes=[
            RootCause(
                name=str(item.get("name") or "unspecified"),
                confidence=_confidence(item.get("confidence")),
                evidence=list(item.get("evidence") or collected),
            )
            for item in causes
        ],
        evidence=evidence,
        recommendations=[
            Recommendation(
                action=str(item.get("action") or "Review the evidence"),
                rationale=str(item.get("rationale") or ""),
                requires_approval=True,
            )
            for item in actions
        ],
        agent_trace=trace or [],
        summary=str(finding["summary"]).strip(),
        mode="crewai",
    )

def diagnose(scenario: str, user_context: str = "", prepare: bool = False) -> DiagnosisReport:
    settings = get_settings()
    retrieved = retrieve(SCENARIO_QUERIES.get(scenario, scenario))
    evidence: list[Evidence] = [Evidence(source="experience_retrieval", summary="Retrieved relevant maintenance experiences", data=[x["name"] for x in retrieved])]
    calls = {
        "slow_query": ["get_slow_queries", "get_indexes", "get_active_sessions"],
        "lock_contention": ["get_locks", "get_active_sessions"],
        "workload_contention": ["get_active_sessions", "get_system_metrics", "get_slow_queries"],
        "table_bloat": ["get_table_statistics"],
        "execution_error": ["get_active_sessions"],
    }.get(scenario, ["get_active_sessions"])
    for name in calls:
        data, status = _call(name)
        evidence.append(Evidence(source=name, summary=f"Read-only tool result ({status})", data=data))
    mode = settings.llm_mode.lower()
    if mode == "openai" and settings.openai_api_key:
        try:
            from app.agents.crew import build_crew
            knowledge = "\n".join(f"- {item.get('name')}: {item.get('content', '')}" for item in retrieved)
            context = "\n".join(part for part in (user_context, f"Retrieved maintenance experience:\n{knowledge}" if knowledge else "") if part)
            result = build_crew(scenario, context).kickoff()
            report = _report_from_crew(scenario, evidence, _finding_from_result(result), _trace_from_result(result))
        except Exception as exc:
            report = _mock_diagnosis(scenario, evidence, mode="mock-fallback")
            report.summary = f"{report.summary} CrewAI did not return a structured diagnosis, so this report is the deterministic fallback: {exc}"
            report.agent_trace = [{"crew": "failed", "error": str(exc), "fallback": "deterministic evidence mode"}]
    else:
        report = _mock_diagnosis(scenario, evidence, mode="mock")
        report.agent_trace = [{"crew": "simulated CrewAI roles", "status": "completed"}]
    REPORT_DIR.mkdir(exist_ok=True)
    (REPORT_DIR / f"{report.incident_id}.json").write_text(report.model_dump_json(indent=2))
    return report

def list_reports() -> list[dict]:
    REPORT_DIR.mkdir(exist_ok=True)
    out = []
    for path in sorted(REPORT_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:20]:
        try: out.append(json.loads(path.read_text()))
        except Exception: pass
    return out
