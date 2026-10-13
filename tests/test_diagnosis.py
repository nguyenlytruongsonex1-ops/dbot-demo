from app.knowledge.retriever import retrieve
from app.diagnosis.orchestrator import _mock_diagnosis
from app.schemas import Evidence

def test_retriever_finds_lock_knowledge():
    names = [x["name"] for x in retrieve("blocked waiting lock sessions")]
    assert "lock_contention" in names

def test_mock_report_has_safe_recommendation():
    report = _mock_diagnosis("slow_query", [Evidence(source="explain", summary="sequential scan")], "mock")
    assert report.root_causes[0].name == "missing_index_or_expensive_plan"
    assert report.recommendations[0].requires_approval is True
