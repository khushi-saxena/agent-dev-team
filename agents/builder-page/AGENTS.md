# How you work

1. Read PROTOCOL.md once per ticket.
2. Your workspace IS the git repo, already on the ticket's branch. Use relative paths. Read the existing code first,
   especially whatever the ingest side exposes for runs and items. Use it, don't duplicate it.
3. Make the change. Server binds 127.0.0.1:8080. Stdlib `http.server` is fine.
4. Add or update a test in `tests/` (start the server on a free port, request the page, check the content).
   Run `python3 -m pytest -q`.
5. For ops tickets: scripts must be idempotent (safe to run twice) and use `sudo` only where needed.
6. `git add -A && git commit -m "#<ticket> <what you did>"`, then check `git log -1`. Don't push.
7. On a retry, fix the specific feedback in the ticket text and say how.

Last line: `RESULT: {"status": "done"|"stuck", "summary": "...", "how_to_test": "..."}`
