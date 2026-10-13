from contextlib import contextmanager
from typing import Any, Iterator
import psycopg
from psycopg.rows import dict_row
from app.config import get_settings

@contextmanager
def connection() -> Iterator[psycopg.Connection]:
    settings = get_settings()
    conn = psycopg.connect(settings.database_url, row_factory=dict_row, connect_timeout=5)
    try:
        yield conn
    finally:
        conn.close()

def fetch_all(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return list(cur.fetchall())

def fetch_one(sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    rows = fetch_all(sql, params)
    return rows[0] if rows else None

def execute(sql: str, params: tuple[Any, ...] = ()) -> None:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()
