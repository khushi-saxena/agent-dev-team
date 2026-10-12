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

from .storage import DB_PATH, init_db

HOST = "127.0.0.1"
PORT = 8080


def _fetch_runs() -> list[tuple[str, int, int]]:
    """Return a list of ``(timestamp, success, new_count)`` tuples.

    The rows are sorted by timestamp ascending so that the HTML table
    lines up chronologically.
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cur = conn.execute(
        "SELECT timestamp, success, new_count FROM runs ORDER BY timestamp ASC"
    )
    rows = [(r[0], r[1], r[2]) for r in cur.fetchall()]
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
        for ts, success, new_cnt in runs:
            success_mark = "✓" if success else "✗"
            rows_html += f"<tr><td>{html.escape(ts)}</td><td>{success_mark}</td><td>{new_cnt}</td></tr>\n"
        # Header row for the table; tests rely on presence of three
        # <tr> tags – one header, two data rows.
        header_html = "<tr><th>Timestamp</th><th>Status</th><th>New Items</th></tr>\n"
        table_html = f"<table border=1>{header_html}{rows_html}</table>"

        latest_part = ""
        if latest:
            ts, success, new_cnt = latest
            success_mark = "✓" if success else "✗"
            message = "No new items" if new_cnt == 0 else f"{new_cnt} new items"
            latest_part = (
                f"<h2>Latest run</h2>\n"
                f"<p>Time: {html.escape(ts)}</p>\n"
                f"<p>Status: {success_mark}</p>\n"
                f"<p>{html.escape(message)}</p>\n"
            )
        else:
            latest_part = "<p>No runs yet.</p>"

        html_page = (
            "<html><head><title>Briefing</title></head><body>"
            f"{latest_part}"
            "<h2>Run history</h2>"
            f"{table_html}"
            "</body></html>"
        )
        self._html_response(html_page)


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

