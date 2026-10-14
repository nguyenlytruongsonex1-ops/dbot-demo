import json
from app.config import get_settings

def answer(incident: dict, message: str) -> str:
    settings = get_settings()
    if settings.llm_mode.lower() == "openai" and settings.openai_api_key:
        try:
            from openai import OpenAI
            client_kwargs = {"api_key": settings.openai_api_key}
            if settings.openai_api_base: client_kwargs["base_url"] = settings.openai_api_base
            client = OpenAI(**client_kwargs)
            context = json.dumps({
                "scenario": incident.get("scenario"),
                "summary": incident.get("summary"),
                "root_causes": incident.get("root_causes"),
                "evidence": incident.get("evidence", [])[:5],
                "recommendations": incident.get("recommendations"),
            }, default=str)
            response = client.chat.completions.create(
                model=settings.openai_model_name,
                messages=[
                    {"role": "system", "content": "You are a careful database administrator. Answer in Vietnamese. Use only incident evidence. Do not claim to have executed mutations. Suggest read-only investigation or human approval."},
                    {"role": "user", "content": f"Incident context:\n{context}\n\nQuestion:\n{message}"},
                ],
                max_completion_tokens=700,
            )
            return response.choices[0].message.content or "Không có câu trả lời từ LLM."
        except Exception as exc:
            return f"LLM chat tạm thời lỗi, chuyển sang chế độ evidence-only: {exc}"
    return mock_answer(incident, message)

def mock_answer(incident: dict, message: str) -> str:
    scenario = incident.get("scenario", "unknown")
    text = message.lower()
    evidence = incident.get("evidence", [])
    if scenario == "lock_contention" or "lock" in text or "block" in text:
        return "Dựa trên incident này, hãy kiểm tra blocked_pid/blocking_pid trong pg_locks và query của transaction đang giữ lock. Không nên terminate ngay; cần xác nhận transaction owner và tác động dữ liệu trước khi approve."
    if scenario == "slow_query" or "index" in text or "chậm" in text:
        return "Diagnosis sơ bộ liên kết slow_query với EXPLAIN và index evidence. Hãy xem Seq Scan, số rows đọc và index hiện tại. Candidate index chỉ là recommendation; chưa được thực thi và cần kiểm tra ảnh hưởng tới INSERT/UPDATE."
    if scenario == "table_bloat" or "vacuum" in text:
        return "Hãy kiểm tra n_dead_tup, n_live_tup, dead_ratio và last_autovacuum. VACUUM/ANALYZE thường an toàn hơn VACUUM FULL; chọn maintenance window trước khi thay đổi."
    if scenario == "workload_contention" or "cpu" in text or "connection" in text:
        return "Cần phân biệt CPU pressure với lock wait và nhiều active sessions. Hãy xem active sessions, wait events và slow queries trước khi tăng connection limit."
    return f"Incident {scenario} đã có diagnosis sơ bộ. Bạn có thể hỏi về root cause, evidence, rủi ro remediation hoặc yêu cầu kiểm tra thêm lock/query plan. Evidence hiện có: {len(evidence)} mục."
