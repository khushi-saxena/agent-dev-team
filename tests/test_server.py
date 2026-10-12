"""End‑to‑end test for the brief‑page HTTP server.

The test:

1. Initializes the SQLite database.
2. Inserts two run rows – one successful with two new items, one failed.
3. Starts the server in a background subprocess.
4. Makes an HTTP request to the root path.
5. Validates the presence of the expected HTML fragments:
   * a row for the most recent run
   * the table header
   * a friendly message "No new items" for the failing run
"""

from __future__ import annotations

import os
import subprocess
import time
import sqlite3
from pathlib import Path
from urllib.request import urlopen

DB_PATH = Path("data", "briefing.db")


def _setup_db() -> None:
    # Ensure clean state
    if DB_PATH.exists():
        DB_PATH.unlink()
    from app.storage import init_db
    init_db()

    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    with conn:
        # success run with 2 items
        conn.execute(
            "INSERT INTO runs (timestamp, success, error, new_count) VALUES (?,?,?,?)",
            ("2026-10-12T00:00:00", 1, None, 2),
        )
        # failed run with 0 items
        conn.execute(
            "INSERT INTO runs (timestamp, success, error, new_count) VALUES (?,?,?,?)",
            ("2026-10-13T00:00:00", 0, "oops", 0),
        )
    conn.close()


def test_server_generates_expected_html() -> None:
    _setup_db()
    # Launch the server process
    proc = subprocess.Popen(
        ["python3", "-m", "app.server"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # Give it a moment to start
    time.sleep(1)
    try:
        resp = urlopen("http://127.0.0.1:8080/")
        data = resp.read().decode("utf-8")
        assert "Latest run" in data
        assert "2026-10-13T00:00:00" in data
        assert "✗" in data  # failed row
        assert "✓" in data  # passed row
        assert "No new items" in data
        # Header row + two data rows
        assert data.count("<tr>") == 3
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
