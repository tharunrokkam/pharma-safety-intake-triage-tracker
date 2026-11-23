"""SQLite connection management: WAL, foreign keys, schema migration, explicit transactions."""
from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

_SCHEMA_PATH = Path(__file__).with_name("schema.sql")
_initialised: set[str] = set()
_init_lock = threading.Lock()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path: Path | str) -> sqlite3.Connection:
    """Open a connection (autocommit mode; callers use ``transaction``). Applies schema once per path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), isolation_level=None, timeout=15, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    key = str(path.resolve())
    if key not in _initialised:
        with _init_lock:
            if key not in _initialised:
                conn.execute("PRAGMA journal_mode = WAL")
                conn.executescript(_SCHEMA_PATH.read_text(encoding="utf-8"))
                _initialised.add(key)
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """BEGIN IMMEDIATE ... COMMIT, rolling back on any exception."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")
