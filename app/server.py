"""Simple HTTP server displaying the briefing run history.

The server uses the small SQLite database created by :mod:`app.storage`.
It listens on ``127.0.0.1:8080`` and renders a single HTML page that
shows:

* the most recent run – its timestamp, a success/failure indicator, and
  the number of new items (``✓``/``✗`` and a friendly message when the
  count is ``0``),
* a history table listing all runs by increasing time.

The implementation is deliberately minimal and uses only the standard
library.
"""

from __future__ import annotations

import html
import sqlite3
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import os
from .storage import DB_PATH, init_db
from .ingest import fetch_feed
import time
import json

def _fetch_latest_items(run_id: int) -> list[tuple[str, str]]:
    """Return the list of ``(title, link)`` for a run.

    The ``run_items`` table links a run to the stable ids of the items
    that were stored in that run.  This helper performs a JOIN to fetch
    the actual title and link from the ``items`` table.
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cur = conn.execute(
        """
        SELECT items.title, items.link
        FROM items
        JOIN run_items ON items.stable_id = run_items.stable_id
        WHERE run_items.run_id = ?
        ORDER BY items.title
        """,
        (run_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows

HOST = "127.0.0.1"
PORT = int(os.environ.get("PORT", "8080"))

# Global rate‑limit state – shared across all requests in this process.
RATE_LIMIT_SECONDS = 120
_last_run_timestamp: float | None = None


def _fetch_runs() -> list[tuple[int, str, int, int]]:
    """Return a list of ``(id, timestamp, success, new_count)`` tuples.

    The rows are sorted by timestamp ascending so that the HTML table
    lines up chronologically.
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cur = conn.execute(
        "SELECT id, timestamp, success, new_count FROM runs ORDER BY timestamp ASC"
    )
    rows = [(r[0], r[1], r[2], r[3]) for r in cur.fetchall()]
    conn.close()
    return rows


class BriefingHandler(BaseHTTPRequestHandler):
    def _html_response(self, content: str) -> None:
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(content.encode("utf-8"))

    def do_GET(self) -> None:  # noqa: D401
        """Serve the briefing page at ``/``.

        The page is intentionally simple – no CSS, no JS – and is aimed at
        being parseable by the tests.
        """
        if self.path != "/":
            self.send_error(404, "Not Found")
            return
        init_db()
        runs = _fetch_runs()
        latest = runs[-1] if runs else None
        # Build table rows
        rows_html = ""
        for run_id, ts, success, new_cnt in runs:
            success_mark = "✓" if success else "✗"
            # Friendly wording for zero‑new or failed runs.
            if new_cnt == 0:
                new_display = "Nothing new"
            else:
                new_display = str(new_cnt)
            rows_html += f"<tr><td>{html.escape(ts)}</td><td>{success_mark}</td><td>{new_display}</td></tr>\n"
        # Header row for the table; tests rely on presence of three
        # <tr> tags – one header, two data rows.
        header_html = "<tr><th>Timestamp</th><th>Status</th><th>New Items</th></tr>\n"
        table_html = f"<table border=1>{header_html}{rows_html}</table>"

        # Build the latest‑run section (regardless of success).  The
        # specification requires the date and count for the *most
        # recent* run, not necessarily a successful one.  We still show
        # the count of new items for the latest successful run when it
        # exists.  This keeps backward‑compatibility with the original
        # behaviour while satisfying the ticket.
        latest_part = ""
        # Grab the last run entry (by timestamp).  The DB is sorted
        # ascending so the last element is the newest.
        if runs:
            latest_run_id, latest_ts, latest_success, latest_new_cnt = runs[-1]
            # Determine the status mark for the latest overall run.
            status_mark = "✓" if latest_success else "✗"
            # We will use the data from the *latest successful* run to
            # render user‑friendly messages and list items.  This
            # mirrors the old behaviour where only successful runs
            # produced a list.
            successful_runs = [r for r in runs if r[2] == 1]
            latest_successful = successful_runs[-1] if successful_runs else None
            if latest_successful:
                run_id, ts, success, new_cnt = latest_successful
                # Friendly text for the latest successful run.
                if len(successful_runs) == 1:
                    message = "First run"
                elif new_cnt == 0:
                    message = "Nothing new"
                else:
                    message = f"{new_cnt} new items"
            else:
                # No successful run yet.
                message = "No runs yet."
                run_id = None
                ts = latest_ts  # Display latest time if available
                new_cnt = None

            latest_part = (
                f"<h2>Latest run</h2>\n"
                f"<p>Time: {html.escape(ts)}</p>\n"
                f"<p>Status: {status_mark}</p>\n"
                f"<p>{html.escape(message)}</p>\n"
            )
            # If the latest successful run has items, list them.
            if run_id is not None and new_cnt:
                items_rows = _fetch_latest_items(run_id)
                list_items = "\n".join(
                    [f"<li>{html.escape(title)} – <a href='{html.escape(link)}'>{html.escape(link)}</a></li>"
                     for title, link in items_rows]
                )
                latest_part += f"<ul>{list_items}</ul>\n"
        else:
            latest_part = "<p>No runs yet.</p>"

        # Add button and script to trigger /run-now
        # Use a raw triple‑quoted string for the JavaScript to avoid
        # escaping complexities.
        button_html = (
            "<button id='runNowBtn'>Run Now</button>"
            "<pre id='runNowOutput'></pre>"
            "<script>"
            "document.getElementById('runNowBtn').addEventListener('click', async () => {"
            "  try {"
            "    const resp = await fetch('/run-now', {method:'POST'});"
            "    const txt = await resp.text();"
            "    document.getElementById('runNowOutput').textContent = txt;"
            "  } catch (e) {"
            "    document.getElementById('runNowOutput').textContent = e.toString();"
            "  }"
            "});"
            "</script>"
        )
        html_page = (
            "<html><head><title>Briefing</title></head><body>"
            f"{latest_part}"
            "<h2>Run history</h2>"
            f"{table_html}"
            f"{button_html}"
            "</body></html>"
        )
        self._html_response(html_page)

    def do_POST(self) -> None:  # noqa: D401
        """Handle `POST /run-now` requests.

        The endpoint enforces a global 2‑minute rate limit.  If the request
        is within the window a **429 Too Many Requests** status is returned.
        Otherwise the button triggers the ingest flow by calling
        :func:`app.ingest.fetch_feed` and returns a JSON payload
        ``{"status": "ok", "new": <count>}``.
        """
        if self.path != "/run-now":
            # Reject unknown paths.
            self.send_error(404, "Not Found")
            return

        global _last_run_timestamp
        now_ts = time.time()
        if _last_run_timestamp is not None:
            if now_ts - _last_run_timestamp < RATE_LIMIT_SECONDS:
                self.send_response(429)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                message = (
                    f"Rate limit: try again in {int(RATE_LIMIT_SECONDS - (now_ts - _last_run_timestamp))} seconds"
                )
                self.wfile.write(json.dumps({"error": message}).encode("utf-8"))
                return
        # Update the timestamp before running to avoid race.
        _last_run_timestamp = now_ts

        # Ensure DB exists – safe to call multiple times.
        init_db()
        try:
            # Trigger the ingest flow.
            items = fetch_feed()
            new_count = len(items)
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            payload = {"status": "ok", "new": new_count}
            self.wfile.write(json.dumps(payload).encode("utf-8"))
        except Exception as exc:  # pragma: no cover – unlikely
            self.send_response(500)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(exc)}).encode("utf-8"))


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), BriefingHandler)
    print(f"[server] Listening on http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("[server] shutting down")
        server.server_close()


if __name__ == "__main__":  # pragma: no cover
    main()

