# How you work

1. Read PROTOCOL.md once per ticket.
2. Your workspace IS the git repo, already on the ticket's branch. Use relative paths
   (app/..., tests/...). Look at what's there first (`ls -R app tests`, `git log --oneline -10`).
3. Make the change. Keep functions small. Stdlib + feedparser only.
4. Add or update a test in `tests/`. Run `python3 -m pytest -q` and make it pass.
5. `git add -A && git commit -m "#<ticket> <what you did>"`, then check `git log -1`. Don't push.
6. If this is a retry, the reviewer/tester feedback is in the ticket text. Fix that specifically and say how in your summary.

If you can't finish, commit nothing and return status "stuck" with why.

Last line: `RESULT: {"status": "done"|"stuck", "summary": "...", "how_to_test": "..."}`
