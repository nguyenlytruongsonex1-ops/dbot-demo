import json
from pathlib import Path
from app.config import get_settings

DATA_PATH = Path(__file__).parents[2] / "data" / "experiences.json"

def load_experiences() -> list[dict]:
    return json.loads(DATA_PATH.read_text())

def retrieve(query: str, limit: int = 3) -> list[dict]:
    terms = set(query.lower().replace("_", " ").split())
    scored = []
    for item in load_experiences():
        haystack = " ".join([item["name"], item["content"], " ".join(item["metrics"])])
        score = sum(1 for term in terms if term in haystack.lower())
        scored.append((score, item))
    return [item for score, item in sorted(scored, key=lambda x: x[0], reverse=True)[:limit] if score > 0] or load_experiences()[:limit]
