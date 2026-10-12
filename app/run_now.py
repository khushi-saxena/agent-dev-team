"""Command line entry point to trigger the ``/run-now`` workflow.

This module simply imports :func:`app.ingest.fetch_feed`, runs it and
prints the JSON response that the HTTP endpoint would return.  The logic
matches the server implementation so that the command line behaves
identically.

The script can be invoked with ``python -m app.run_now``.
"""

import json
import time
from pathlib import Path

from app.ingest import fetch_feed
from app.storage import init_db

RATE_LIMIT_SECONDS = 120
_last_run_file = Path(".run_now_ts")


def main() -> None:
    init_db()
    now_ts = time.time()
    if _last_run_file.exists():
        try:
            last_ts = float(_last_run_file.read_text())
        except Exception:
            last_ts = None
        if last_ts is not None and now_ts - last_ts < RATE_LIMIT_SECONDS:
            retry = int(RATE_LIMIT_SECONDS - (now_ts - last_ts))
            print(json.dumps({"error": f"Rate limit: try again in {retry} seconds"}))
            return
    # Run ingest
    items = fetch_feed()
    payload = {"status": "ok", "new": len(items)}
    print(json.dumps(payload))
    _last_run_file.write_text(str(now_ts))


if __name__ == "__main__":  # pragma: no cover
    main()
