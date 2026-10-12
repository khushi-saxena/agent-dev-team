# How you work

1. Read PROTOCOL.md once per ticket.
2. `cd` into the worktree path the ticket gives you. Read what's already there
   (`ls -R app tests`, `git log --oneline -10`) before writing anything.
3. Make the change. Keep functions small. Stdlib + feedparser only.
4. Add or update a test in `tests/`. Run `python3 -m pytest -q` and make it pass.
5. `git add -A && git commit -m "#<ticket> <what you did>"`. Don't push.
6. If this is a retry, the reviewer/tester feedback is in the ticket text. Fix that specifically and say how in your summary.

If you can't finish, commit nothing and return status "stuck" with why.

Last line: `RESULT: {"status": "done"|"stuck", "summary": "...", "how_to_test": "..."}`
