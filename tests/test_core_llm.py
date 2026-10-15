"""Kiểm thử không cần DB: chấm điểm, lọc lệnh lambda-Tune, dự phòng LLM."""
import os

from app import core_demo as core, llm


def test_auto_grade():
    assert core.auto_grade("kb1", "Nguyên nhân: thiếu index trên l_partkey. CREATE INDEX ...") == (True, True)
    assert core.auto_grade("kb2", "Do truy vấn con tương quan, viết lại bằng JOIN ") == (True, True)
    assert core.auto_grade("kb3", "Khóa bị giữ, hãy ROLLBACK") == (True, True)
    assert core.auto_grade("kb1", "Tăng RAM") == (False, False)


def test_parse_config_allowlist():
    ok, bad = core.parse_config("```sql\nSET work_mem = '64MB';\nCREATE INDEX i1 ON lineitem(l_shipdate);\n"
                                "ALTER SYSTEM SET shared_buffers = '4GB';\nDROP TABLE tpch.orders;\n```")
    assert ok == ["SET work_mem = '64MB'", "CREATE INDEX i1 ON lineitem(l_shipdate)"]
    assert len(bad) == 2
    assert core.normalize(ok[1]) == "CREATE INDEX i1 ON tpch.lineitem(l_shipdate)"


def test_fallback_to_ollama_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    calls = []

    def fake(provider, prompt, temperature, timeout):
        calls.append(provider)
        return "ok"
    monkeypatch.setattr(llm, "_call", fake)
    text, used, note = llm.ask("hi", "claude")
    assert (text, used) == ("ok", "ollama") and calls == ["ollama"] and "API key" in note


def test_fallback_on_error(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "x")

    def fake(provider, prompt, temperature, timeout):
        if provider == "gemini":
            raise llm.LLMError("HTTP 400: bad")
        return "ok"
    monkeypatch.setattr(llm, "_call", fake)
    text, used, note = llm.ask("hi", "gemini")
    assert used == "ollama" and "Gemini" in note


def test_mock_answer_prompt_b():
    p = core.prompt_b("chậm", "EXPLAIN: Seq Scan on lineitem")
    assert core.auto_grade("kb1", llm.mock_answer(p))[0]
