"""dbot-worker: lấy alert đang chờ phân tích trong SQLite, chạy D-Bot, lưu báo cáo."""
import json
import logging
import time

from app.common import alert_to_dict, bump_version, store
from app.dbot.crew import diagnose

log = logging.getLogger("worker")


def once():
    with store() as con:
        r = con.execute("SELECT * FROM alerts WHERE analysis_status='analyzing' ORDER BY updated_at LIMIT 1").fetchone()
    if not r:
        return False
    alert = alert_to_dict(r)
    log.info("Phân tích alert %s (%s)", alert["id"], alert["type"])
    started = time.time()
    try:
        report = diagnose(alert)
        status = "done"
    except Exception as e:  # noqa: BLE001
        log.exception("Lỗi khi phân tích")
        report = {"summary": f"Lỗi khi phân tích: {e}", "steps": [], "root_cause": "", "remediation": []}
        status = "error"
    report["elapsed_sec"] = round(time.time() - started, 1)
    with store() as con:
        con.execute("UPDATE alerts SET analysis_status=?, report=?, updated_at=? WHERE id=?",
                    (status, json.dumps(report, ensure_ascii=False, default=str), time.time(), alert["id"]))
        bump_version(con)
    return True


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    while True:
        try:
            if not once():
                time.sleep(2)
        except Exception as e:  # noqa: BLE001
            log.warning("Lỗi worker: %s", e)
            time.sleep(5)


if __name__ == "__main__":
    main()
