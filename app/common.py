"""Cấu hình, kết nối PostgreSQL và kho SQLite dùng chung cho mọi thành phần."""
import json
import os
import sqlite3
import time
from contextlib import contextmanager

import psycopg

PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_DB = os.getenv("PG_DB", "dbot_demo")
PG_ADMIN_USER = os.getenv("PG_ADMIN_USER", "dbot")
PG_ADMIN_PASSWORD = os.getenv("PG_ADMIN_PASSWORD", "dbot")
PG_SCENARIO_USER = os.getenv("PG_SCENARIO_USER", "scenario_runner")
PG_SCENARIO_PASSWORD = os.getenv("PG_SCENARIO_PASSWORD", "scenario_pw")

SQLITE_PATH = os.getenv("SQLITE_PATH", "data/dbot.sqlite")
SCENARIO_DIR = os.getenv("SCENARIO_DIR", "scenarios")
KNOWLEDGE_DIR = os.getenv("KNOWLEDGE_DIR", "knowledge")

MONITOR_INTERVAL = float(os.getenv("MONITOR_INTERVAL", "10"))
RESOLVE_AFTER_SCANS = int(os.getenv("RESOLVE_AFTER_SCANS", "3"))

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")  # ollama | openai | mock
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def pg_connect(user=None, password=None, app_name="dbot-demo", autocommit=True):
    return psycopg.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB,
        user=user or PG_ADMIN_USER, password=password or PG_ADMIN_PASSWORD,
        application_name=app_name, autocommit=autocommit, connect_timeout=5,
    )


SCHEMA = """
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL,           -- open | resolved
    analysis_status TEXT NOT NULL DEFAULT 'none', -- none | analyzing | done | error
    details TEXT NOT NULL,          -- JSON: số liệu và SQL liên quan
    report TEXT,                    -- JSON: báo cáo của D-Bot
    missed_scans INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    resolved_at REAL
);
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
"""


@contextmanager
def store():
    os.makedirs(os.path.dirname(SQLITE_PATH) or ".", exist_ok=True)
    con = sqlite3.connect(SQLITE_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA journal_mode=WAL")
        con.executescript(SCHEMA)
        yield con
        con.commit()
    finally:
        con.close()


def bump_version(con):
    """Tăng số phiên bản để backend biết có thay đổi và đẩy qua WebSocket."""
    con.execute(
        "INSERT INTO meta(k, v) VALUES('version', ?) "
        "ON CONFLICT(k) DO UPDATE SET v = excluded.v",
        (str(time.time()),),
    )


def get_version(con):
    row = con.execute("SELECT v FROM meta WHERE k='version'").fetchone()
    return row["v"] if row else "0"


def alert_to_dict(row):
    d = dict(row)
    d["details"] = json.loads(d["details"] or "{}")
    d["report"] = json.loads(d["report"]) if d.get("report") else None
    return d


def split_sql(text):
    """Tách file SQL thành từng câu lệnh, tôn trọng chuỗi, comment và khối $$.

    Cần tách vì PostgreSQL chạy nhiều câu trong một lần gửi như một transaction
    ngầm, khi đó VACUUM sẽ báo lỗi.
    """
    stmts, buf, i, n = [], [], 0, len(text)
    while i < n:
        c = text[i]
        if text.startswith("--", i):
            j = text.find("\n", i)
            i = n if j < 0 else j + 1
            buf.append("\n")
            continue
        if text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        if c == "'":
            j = i + 1
            while j < n:
                if text[j] == "'" and not text.startswith("''", j):
                    break
                j += 2 if text.startswith("''", j) else 1
            buf.append(text[i:j + 1]); i = j + 1
            continue
        if c == "$":
            j = text.find("$", i + 1)
            tag = text[i:j + 1] if j > 0 else ""
            if tag and all(ch.isalnum() or ch == "_" for ch in tag[1:-1]):
                k = text.find(tag, j + 1)
                k = n if k < 0 else k + len(tag)
                buf.append(text[i:k]); i = k
                continue
        if c == ";":
            s = "".join(buf).strip()
            if s:
                stmts.append(s)
            buf = []; i += 1
            continue
        buf.append(c); i += 1
    s = "".join(buf).strip()
    if s:
        stmts.append(s)
    return stmts


def scenario_header(path):
    """Lấy các dòng comment đầu file làm mô tả kịch bản."""
    lines = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("--"):
                lines.append(line[2:].strip())
            elif line.strip():
                break
    return "\n".join(lines)
