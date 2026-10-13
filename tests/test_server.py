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
        # Success run with 2 items. We need to insert the items and link them.
        conn.execute(
            "INSERT INTO runs (id, timestamp, success, error, new_count) VALUES (?,?,?,?,?)",
            (1, "2026-10-12T00:00:00", 1, None, 2),
        )
        conn.execute(
            "INSERT INTO items (stable_id, title, link, summary) VALUES (?,?,?,?)",
            ("id1", "First title", "http://example.com/1", "summary1"),
        )
        conn.execute(
            "INSERT INTO items (stable_id, title, link, summary) VALUES (?,?,?,?)",
            ("id2", "Second title", "http://example.com/2", "summary2"),
        )
        conn.execute(
            "INSERT INTO run_items (run_id, stable_id) VALUES (?,?)",
            (1, "id1"),
        )
        conn.execute(
            "INSERT INTO run_items (run_id, stable_id) VALUES (?,?)",
            (1, "id2"),
        )
        # Failed run with 0 items
        conn.execute(
            "INSERT INTO runs (id, timestamp, success, error, new_count) VALUES (?,?,?,?,?)",
            (2, "2026-10-13T00:00:00", 0, "oops", 0),
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
        assert "Nothing new" in data
        # First run should list items
        assert "First run" in data
        # The two titles should appear as list items with links
        assert "First title – <a href='http://example.com/1'>http://example.com/1</a>" in data
        assert "Second title – <a href='http://example.com/2'>http://example.com/2</a>" in data
        # Header row + two data rows
        assert data.count("<tr>") == 3
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
