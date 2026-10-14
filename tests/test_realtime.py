from app.chat import mock_answer
from app.metrics import render_metrics

def test_metrics_endpoint_has_prometheus_names(monkeypatch):
    monkeypatch.setattr("app.metrics.fetch_all", lambda sql: [])
    text = render_metrics()
    assert "dbot_demo_query_latency_ms" in text
    assert "dbot_demo_lock_waiters" in text
    assert text.endswith("\n")

def test_chat_is_bound_to_incident_context():
    answer = mock_answer({"scenario": "lock_contention", "evidence": [{"source": "pg_locks"}]}, "Ai đang block?")
    assert "blocking" in answer.lower() or "lock" in answer.lower()
