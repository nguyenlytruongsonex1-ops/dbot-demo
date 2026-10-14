import json
import threading
from pathlib import Path
from typing import Any
from app.config import get_settings

_lock = threading.Lock()

def _path() -> Path:
    path = Path(get_settings().incident_store_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path

def _read() -> list[dict[str, Any]]:
    path = _path()
    if not path.exists(): return []
    try: return json.loads(path.read_text())
    except Exception: return []

def _write(items: list[dict[str, Any]]) -> None:
    _path().write_text(json.dumps(items[:100], default=str, indent=2))

def list_incidents() -> list[dict[str, Any]]:
    with _lock: return _read()

def get_incident(incident_id: str) -> dict[str, Any] | None:
    return next((x for x in list_incidents() if x.get("incident_id") == incident_id), None)

def upsert(item: dict[str, Any]) -> dict[str, Any]:
    with _lock:
        items = _read()
        items = [x for x in items if x.get("incident_id") != item.get("incident_id")]
        items.insert(0, item)
        _write(items)
    return item

def append_chat(incident_id: str, role: str, content: str) -> dict[str, Any] | None:
    with _lock:
        items = _read()
        for item in items:
            if item.get("incident_id") == incident_id:
                item.setdefault("chat", []).append({"role": role, "content": content})
                _write(items)
                return item
    return None
