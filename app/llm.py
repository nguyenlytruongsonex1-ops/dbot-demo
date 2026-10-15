"""Gọi LLM qua REST: Claude, Gemini, OpenAI và Ollama, có tự chuyển sang Ollama.

Quy tắc dự phòng: nếu nguồn đã chọn không có API key hoặc gọi lỗi
(sau vài lần thử lại khi máy chủ quá tải), hàm ask() gọi Ollama trên máy người dùng.
Chế độ mock không gọi LLM, chỉ dùng để kiểm thử luồng.
Phần gọi Claude và Gemini dựa trên demo_core.py của Nhóm 3.
"""
import os
import time

import requests

from app import common

PROVIDERS = ["claude", "gemini", "openai", "ollama", "mock"]
LABELS = {"claude": "Claude", "gemini": "Gemini", "openai": "OpenAI", "ollama": "Ollama (máy cục bộ)",
          "mock": "Mock (không dùng LLM)"}
KEY_ENV = {"claude": "ANTHROPIC_API_KEY", "gemini": "GEMINI_API_KEY", "openai": "OPENAI_API_KEY"}
RETRY_CODES = (429, 500, 502, 503, 504, 529)


class LLMError(RuntimeError):
    pass


def api_key(provider):
    return os.getenv(KEY_ENV.get(provider, ""), "") if provider in KEY_ENV else ""


def model_of(provider):
    return {"claude": common.CLAUDE_MODEL, "gemini": common.GEMINI_MODEL, "openai": common.OPENAI_MODEL,
            "ollama": common.OLLAMA_MODEL, "mock": "mock"}.get(provider, "")


def available(provider):
    """Nguồn có dùng được không (chỉ kiểm tra cấu hình, không gọi mạng)."""
    if provider in KEY_ENV:
        return bool(api_key(provider))
    return provider in ("ollama", "mock")


def ollama_ok(timeout=2):
    try:
        return requests.get(f"{common.OLLAMA_BASE_URL}/api/tags", timeout=timeout).status_code == 200
    except requests.RequestException:
        return False


def _post(url, headers, payload, timeout):
    r = requests.post(url, headers=headers, json=payload, timeout=timeout)
    if r.status_code != 200:
        raise LLMError(f"HTTP {r.status_code}: {r.text[:300]}")
    return r.json()


def _call(provider, prompt, temperature, timeout):
    model = model_of(provider)
    if provider == "claude":
        data = _post("https://api.anthropic.com/v1/messages",
                     {"x-api-key": api_key("claude"), "anthropic-version": "2023-06-01",
                      "content-type": "application/json"},
                     {"model": model, "max_tokens": 1500, "messages": [{"role": "user", "content": prompt}]},
                     timeout)
        return "".join(b.get("text", "") for b in data.get("content", []))
    if provider == "gemini":
        # Gemini 3 trở đi không nhận tham số temperature, nên không gửi.
        data = _post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                     {"x-goog-api-key": api_key("gemini"), "content-type": "application/json"},
                     {"contents": [{"parts": [{"text": prompt}]}]}, timeout)
        cands = data.get("candidates", [])
        return "".join(p.get("text", "") for p in cands[0]["content"].get("parts", [])) if cands else ""
    if provider == "openai":
        data = _post(f"{common.OPENAI_BASE_URL}/chat/completions",
                     {"Authorization": f"Bearer {api_key('openai')}", "content-type": "application/json"},
                     {"model": model, "temperature": temperature,
                      "messages": [{"role": "user", "content": prompt}]}, timeout)
        return data["choices"][0]["message"]["content"]
    if provider == "ollama":
        data = _post(f"{common.OLLAMA_BASE_URL}/api/chat", {"content-type": "application/json"},
                     {"model": model, "stream": False, "options": {"temperature": temperature},
                      "messages": [{"role": "user", "content": prompt}]}, max(timeout, 300))
        return data["message"]["content"]
    if provider == "mock":
        return mock_answer(prompt)
    raise LLMError(f"Nguồn LLM không hợp lệ: {provider}")


def _with_retry(provider, prompt, temperature, timeout):
    last = None
    for wait in (0, 3, 8):
        if wait:
            time.sleep(wait)
        try:
            return _call(provider, prompt, temperature, timeout)
        except LLMError as e:
            last = e
            if not any(f"HTTP {c}" in str(e) for c in RETRY_CODES):
                break
        except requests.RequestException as e:
            last = e
            break
    raise LLMError(f"{LABELS.get(provider, provider)} lỗi: {last}")


def ask(prompt, provider=None, temperature=0.3, timeout=90):
    """Trả về (câu trả lời, nguồn thực tế đã dùng, ghi chú)."""
    provider = provider or common.LLM_PROVIDER
    note = ""
    if provider not in ("ollama", "mock"):
        if not available(provider):
            note = f"Không có API key cho {LABELS[provider]}, đã chuyển sang Ollama."
        else:
            try:
                return _with_retry(provider, prompt, temperature, timeout), provider, ""
            except LLMError as e:
                note = f"{e}. Đã chuyển sang Ollama."
        provider = "ollama"
    try:
        return _with_retry(provider, prompt, temperature, timeout), provider, note
    except LLMError as e:
        raise LLMError((note + " " if note else "") + str(e)) from e


def mock_answer(prompt):
    """Câu trả lời giả lập theo từ khóa trong prompt, để thử luồng khi không có LLM."""
    p = prompt.lower()
    if "[kết quả công cụ thật]" in p:
        p = p.split("[kết quả công cụ thật]", 1)[1]
        if "subplan" in p:
            return ("Nguyên nhân: truy vấn con tương quan (SubPlan) chạy lại cho từng dòng của truy vấn ngoài.\n"
                    "Cách sửa: viết lại bằng JOIN với bảng tạm GROUP BY o_custkey.")
        if "pg_blocking_pids" in p and "blocked_by" in p:
            return ("Nguyên nhân: một transaction giữ khóa dòng (lock) chưa COMMIT, phiên khác phải chờ.\n"
                    "Cách sửa: ROLLBACK hoặc SELECT pg_terminate_backend(pid) cho phiên chặn.")
        if "seq scan" in p:
            return ("Nguyên nhân: thiếu index trên cột l_partkey nên mỗi truy vấn quét toàn bảng.\n"
                    "Cách sửa: CREATE INDEX idx_l_partkey ON tpch.lineitem(l_partkey);")
    if "recommend some configuration" in p:
        return "SET work_mem = '64MB';\nCREATE INDEX lt_l_shipdate ON tpch.lineitem(l_shipdate);"
    return "Nguyên nhân: có thể do tải cao hoặc cấu hình chưa phù hợp. Cách sửa: kiểm tra thêm số liệu."
