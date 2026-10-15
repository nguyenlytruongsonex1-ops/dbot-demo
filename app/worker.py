"""dbot-worker: tự động phân tích alert mới bằng D-Bot và lưu báo cáo vào SQLite.

Luồng tự động:
1. Khi công tắc "Tự động phân tích" bật, alert đang mở, chưa phân tích, đã tồn tại
   ít nhất ANALYZE_DEBOUNCE_SEC giây và dấu hiệu vẫn còn ở lần quét gần nhất
   (missed_scans = 0) sẽ được đưa vào hàng đợi (analysis_status = 'queued').
2. Worker lấy từng alert trong hàng đợi, mỗi lần một alert, chuyển sang 'analyzing',
   chạy D-Bot rồi lưu báo cáo với trạng thái 'done' hoặc 'error'.
Người dùng cũng có thể xếp hàng thủ công qua nút "Phân tích" hoặc "Phân tích lại".
"""
import json
import logging
import time

from app import common
from app.common import alert_to_dict, bump_version, get_setting, store
from app.dbot.crew import diagnose

log = logging.getLogger("worker")


def auto_enabled(con):
    return get_setting(con, "auto_analyze", "1") == "1"


def enqueue_auto(now=None):
    """Đưa các alert đủ điều kiện vào hàng đợi. Trả về số alert vừa thêm."""
    now = now or time.time()
    with store() as con:
        if not auto_enabled(con):
            return 0
        provider = get_setting(con, "default_llm", common.LLM_PROVIDER)
        cur = con.execute(
            "UPDATE alerts SET analysis_status='queued', llm_provider=COALESCE(llm_provider, ?), updated_at=? "
            "WHERE status='open' AND analysis_status='none' AND missed_scans=0 AND created_at <= ?",
            (provider, now, now - common.ANALYZE_DEBOUNCE_SEC))
        if cur.rowcount:
            bump_version(con)
            log.info("Tự động xếp hàng %d alert", cur.rowcount)
        return cur.rowcount


def once():
    enqueue_auto()
    with store() as con:
        r = con.execute("SELECT * FROM alerts WHERE analysis_status='queued' ORDER BY updated_at LIMIT 1").fetchone()
        if not r:
            return False
        con.execute("UPDATE alerts SET analysis_status='analyzing', analysis_started_at=?, updated_at=? WHERE id=?",
                    (time.time(), time.time(), r["id"]))
        bump_version(con)
        default = get_setting(con, "default_llm", common.LLM_PROVIDER)
    alert = alert_to_dict(r)
    provider = alert.get("llm_provider") or default
    log.info("Phân tích alert %s (%s) bằng %s", alert["id"], alert["type"], provider)
    started = time.time()
    try:
        report = diagnose(alert, provider)
        status = "done"
    except Exception as e:  # noqa: BLE001
        log.exception("Lỗi khi phân tích")
        report = {"summary": f"Lỗi khi phân tích: {e}", "steps": [], "root_cause": "", "remediation": [],
                  "provider_requested": provider}
        status = "error"
    report["elapsed_sec"] = round(time.time() - started, 1)
    with store() as con:
        con.execute("UPDATE alerts SET analysis_status=?, report=?, updated_at=? WHERE id=?",
                    (status, json.dumps(report, ensure_ascii=False, default=str), time.time(), alert["id"]))
        bump_version(con)
    return True


def recover():
    """Nếu worker bị tắt giữa chừng, đưa alert đang phân tích dở về hàng đợi."""
    with store() as con:
        con.execute("UPDATE alerts SET analysis_status='queued' WHERE analysis_status='analyzing'")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    recover()
    while True:
        try:
            if not once():
                time.sleep(2)
        except Exception as e:  # noqa: BLE001
            log.warning("Lỗi worker: %s", e)
            time.sleep(5)


if __name__ == "__main__":
    main()
