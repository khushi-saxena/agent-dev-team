"""SQLite persistence for the daily briefing ingest.

This module implements a very small schema that is sufficient for the
builder‑ingest agent to record runs and the feed items that were processed
in those runs.

Schema
------
``runs``
    * ``id`` – autoincrement primary key (internal usage only)
    * ``timestamp`` – TEXT, stored in ISO format or any string
    * ``success`` – INTEGER (0 or 1)
    * ``error`` – TEXT, nullable

``items``
    * ``stable_id`` – TEXT primary key, unique stable identifier for the
      feed item
    * ``title`` – TEXT
    * ``link`` – TEXT
    * ``summary`` – TEXT, nullable

The module offers a tiny API used by unit tests and the ingest
logic:

``init_db()``
    Ensure :data:`data/briefing.db` exists and contains the tables.

``save_run(timestamp, success, error, items)``
    Persist a new run and the list of items associated with that run.

``get_all_ids()``
    Return a set of all stable IDs stored in the ``items`` table.

All functions work with the same database file and no external
configuration is required.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from typing import Iterable, List, Mapping, Optional, Set

DB_PATH = os.path.join("data", "briefing.db")


def _ensure_dir() -> None:
    """Create the directory that will hold the SQLite file.

    The database is created lazily in :func:`init_db`.  This helper
    guarantees that the parent directory exists for subsequent
    ``sqlite3.connect`` calls.
    """
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


def _get_connection() -> sqlite3.Connection:
    """Return a new connection to the persistent database.

    The connection is opened with ``check_same_thread=False`` so it can be
    used safely across the few threads that may exist in tests.
    """
    _ensure_dir()
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Create the schema if it does not yet exist.

    The tables are created with ``IF NOT EXISTS`` so running the function
    repeatedly is idempotent.
    """
    conn = _get_connection()
    with conn:
        # ``runs`` now stores an integer ``new_count`` column that tracks
        # how many items were inserted by that particular run.  The
        # associated ingestion logic will provide this value.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                success INTEGER NOT NULL,
                error TEXT,
                new_count INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
                stable_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                link TEXT NOT NULL,
                summary TEXT
            );
            """
        )
    conn.close()


def save_run(
    timestamp: str | datetime,
    success: bool,
    error: Optional[str],
    items: Iterable[Mapping[str, str | None]] | None = None,
    new_count: int | None = None,
):
    """Persist a run and its related items.

    Parameters
    ----------
    timestamp:
        The time the run occurred.  It is converted to ``str``; callers may
        provide a ``datetime``.
    success:
        Boolean success flag.
    error:
        Optional error message.
    items:
        Iterable of dictionaries with keys ``stable_id``, ``title``,
        ``link`` and optional ``summary``.
    """
    if isinstance(timestamp, datetime):
        ts_str = timestamp.isoformat()
    else:
        ts_str = str(timestamp)
    conn = _get_connection()
    # ``conn`` is a context manager that automatically commits or rolls
    # back on exception, so wrap all writes in a single ``with`` block.
    with conn:
        conn.execute(
            "INSERT INTO runs (timestamp, success, error, new_count) VALUES (?, ?, ?, ?)",
            (ts_str, int(bool(success)), error, int(new_count or 0)),
        )
        if items:
            for itm in items:
                conn.execute(
                    "INSERT OR IGNORE INTO items (stable_id, title, link, summary) VALUES (?, ?, ?, ?)",
                    (
                        itm.get("stable_id"),
                        itm.get("title"),
                        itm.get("link"),
                        itm.get("summary"),
                    ),
                )
    conn.close()


def get_all_ids() -> Set[str]:
    """Return a set of all stable item ids stored in the database."""
    conn = _get_connection()
    cursor = conn.execute("SELECT stable_id FROM items")
    ids = {row[0] for row in cursor.fetchall()}
    conn.close()
    return ids

