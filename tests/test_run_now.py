"""End‑to‑end test for the run‑now rate‑limit behaviour.

The test starts the server in a subprocess, performs an initial POST to
``/run-now`` which should succeed, and then immediately performs a
second POST.  The second call is expected to receive a 429 status.
"""

from __future__ import annotations

import os
import socket
import subprocess
import time
from urllib.request import Request, urlopen


def _free_port() -> int:
    """Return an available TCP port on localhost.

    The socket is immediately closed after obtaining the port number.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_run_now_rate_limit() -> None:
    # Choose a free port and start the server with that PORT env var.
    port = _free_port()
    env = {**os.environ, "PORT": str(port)}
    proc = subprocess.Popen(
        ["python3", "-m", "app.server"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    time.sleep(1)
    try:
        # First POST should succeed
        req1 = Request(f"http://127.0.0.1:{port}/run-now", method="POST")
        resp1 = urlopen(req1)
        assert resp1.status == 200
        _ = resp1.read().decode("utf-8")
        # Second POST should hit rate limit
        try:
            req2 = Request(f"http://127.0.0.1:{port}/run-now", method="POST")
            _ = urlopen(req2)
        except Exception as exc:  # urllib.error.HTTPError expected
            from urllib.error import HTTPError

            assert isinstance(exc, HTTPError)
            assert exc.code == 429
            body = exc.read().decode("utf-8")
            assert "Rate limit" in body
        else:
            assert False, "Second run did not trigger rate limit"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
