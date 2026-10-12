#!/usr/bin/env bash
set -euo pipefail

# Smoke test for the briefing deployment
# 1. Check that the HTTP server is up and serving a page.
if ! curl -sf http://127.0.0.1:8080 > /dev/null; then
  echo "FAIL: HTTP server not reachable"
  exit 1
fi

# 2. Trigger a run‑now via the HTTP endpoint and verify the JSON payload.
RUN_NOW_JSON=$(curl -s -X POST http://127.0.0.1:8080/run-now)
# Parse with jq if available; otherwise use grep.
if command -v jq >/dev/null 2>&1; then
  if ! echo "$RUN_NOW_JSON" | jq -e '.status=="ok"' >/dev/null; then
    echo "FAIL: /run-now did not return status ok"
    echo "Output: $RUN_NOW_JSON"
    exit 1
  fi
else
  if ! echo "$RUN_NOW_JSON" | grep -q '"status":"ok"'; then
    echo "FAIL: /run-now did not return status ok"
    echo "Output: $RUN_NOW_JSON"
    exit 1
  fi
fi

# 3. Verify that the HTTP endpoint /run-now returns the same status.
RESP_JSON=$(curl -s -XPOST http://127.0.0.1:8080/run-now)
if command -v jq >/dev/null 2>&1; then
  if ! echo "$RESP_JSON" | jq -e '.status=="ok"' >/dev/null; then
    echo "FAIL: HTTP /run-now did not return status ok"
    echo "Response: $RESP_JSON"
    exit 1
  fi
else
  if ! echo "$RESP_JSON" | grep -q '"status":"ok"'; then
    echo "FAIL: HTTP /run-now did not return status ok"
    echo "Response: $RESP_JSON"
    exit 1
  fi
fi

echo "PASS: Deployment is healthy"
exit 0
