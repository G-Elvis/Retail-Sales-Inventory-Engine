"""Database connection and lifecycle management."""

import os
import sqlite3
from pathlib import Path
from typing import Generator
from contextlib import contextmanager

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB_PATH = BASE_DIR / "data" / "retail_engine.db"


def get_db_path() -> Path:
    """Return configured database path (allows override via env var for testing)."""
    env_path = os.getenv("RETAIL_DB_PATH")
    if env_path:
        return Path(env_path)
    DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return DEFAULT_DB_PATH


def create_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    """
    Create and configure a connection to SQLite database.
    
    Enforces:
    1. Foreign key constraints (PRAGMA foreign_keys = ON).
    2. Row factory for dict-like column access.
    """
    if db_path is not None:
        path = Path(db_path)
    else:
        path = get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def get_db_cursor(db_path: Path | None = None) -> Generator[tuple[sqlite3.Connection, sqlite3.Cursor], None, None]:
    """
    Context manager providing connection and cursor.
    Does not automatically commit so callers can manage transaction boundaries explicitly.
    """
    conn = create_connection(db_path)
    cursor = conn.cursor()
    try:
        yield conn, cursor
    finally:
        cursor.close()
        conn.close()
