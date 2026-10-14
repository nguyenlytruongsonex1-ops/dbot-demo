from app.knowledge.retriever import retrieve
from app.diagnosis.orchestrator import _mock_diagnosis
from app.schemas import Evidence

def test_clear_incidents_empties_the_list(tmp_path, monkeypatch):
    path = tmp_path / "incidents.json"
    monkeypatch.setattr("app.incident_store._path", lambda: path)
    from app.incident_store import clear_incidents, list_incidents, upsert
    upsert({"incident_id": "a", "scenario": "slow_query"})
    upsert({"incident_id": "b", "scenario": "lock_contention"})
    assert clear_incidents() == 2
    assert list_incidents() == []

def test_retriever_finds_lock_knowledge():
    names = [x["name"] for x in retrieve("blocked waiting lock sessions")]
    assert "lock_contention" in names

def test_mock_report_has_safe_recommendation():
    report = _mock_diagnosis("slow_query", [Evidence(source="explain", summary="sequential scan")], "mock")
    assert report.root_causes[0].name == "missing_index_or_expensive_plan"
    assert report.recommendations[0].requires_approval is True

def test_real_mode_report_uses_crew_finding():
    from app.diagnosis.orchestrator import _report_from_crew
    report = _report_from_crew("lock_contention", [Evidence(source="get_locks", summary="one blocker")], {
        "root_causes": [{"name": "blocking_update", "confidence": 91, "evidence": ["pg_locks"]}],
        "recommendations": [{"action": "Inspect the blocking session", "rationale": "An open update holds the row."}],
        "summary": "The lock is held by an uncommitted update.",
    })
    assert report.mode == "crewai"
    assert report.root_causes[0].name == "blocking_update"
    assert report.root_causes[0].confidence == 0.91
    assert report.recommendations[0].action == "Inspect the blocking session"
    assert report.recommendations[0].requires_approval is True
    assert report.summary == "The lock is held by an uncommitted update."

def test_openai_mode_keeps_crew_fields(monkeypatch, tmp_path):
    from app.diagnosis.orchestrator import diagnose
    class Settings:
        llm_mode = "openai"
        openai_api_key = "test-key"
    class Result:
        pydantic = type("Finding", (), {"model_dump": lambda self: {
            "root_causes": [{"name": "blocking_update", "confidence": 0.9, "evidence": ["pg_locks"]}],
            "recommendations": [{"action": "Inspect the blocker", "rationale": "Row lock is held."}],
            "summary": "Crew found a blocking update.",
        }})()
        json_dict = None
        tasks_output = []
    monkeypatch.setattr("app.diagnosis.orchestrator.get_settings", lambda: Settings())
    monkeypatch.setattr("app.diagnosis.orchestrator.retrieve", lambda query: [{"name": "lock_contention", "content": "waiting sessions"}])
    monkeypatch.setattr("app.diagnosis.orchestrator._call", lambda name: ({"ok": True}, "ok"))
    monkeypatch.setattr("app.diagnosis.orchestrator.REPORT_DIR", tmp_path)
    monkeypatch.setattr("app.agents.crew.build_crew", lambda scenario, context="": type("Crew", (), {"kickoff": lambda self: Result()})())
    report = diagnose("lock_contention", "alert fired")
    assert report.mode == "crewai"
    assert report.root_causes[0].name == "blocking_update"
    assert report.root_causes[0].name != "lock_contention"
