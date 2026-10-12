"""End‑to‑end test for the run‑now rate‑limit behaviour.

The test starts the server in a subprocess, performs an initial POST to
``/run-now`` which should succeed, and then immediately performs a
second POST.  The second call is expected to receive a 429 status.
"""

from __future__ import annotations

import subprocess
import time
from urllib.request import Request, urlopen

SERVER_CMD = ["python3", "-m", "app.server"]


def test_run_now_rate_limit() -> None:
    # Start the server background
    proc = subprocess.Popen(
        SERVER_CMD,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(1)
    try:
        # First POST should succeed
        req1 = Request("http://127.0.0.1:8080/run-now", method="POST")
        resp1 = urlopen(req1)
        assert resp1.status == 200
        payload1 = resp1.read().decode("utf-8")
        # Second POST should hit rate limit
        try:
            req2 = Request("http://127.0.0.1:8080/run-now", method="POST")
            resp2 = urlopen(req2)
        except Exception as exc:  # urllib.error.HTTPError
            from urllib.error import HTTPError

            assert isinstance(exc, HTTPError)
            assert exc.code == 429
            body = exc.read().decode("utf-8")
            assert "Rate limit" in body
        else:
            # If we unexpectedly get 200, treat as failure
            assert False, "Second run did not trigger rate limit"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
