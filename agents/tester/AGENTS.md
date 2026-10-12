# Test protocol

Your workspace IS the repo, checked out at the PR's code. Use `.testdata/` in it for any
DB or feed file (set the env vars the code reads, or pass paths), never `data/`. Never commit.

## Always
1. `python3 -m pytest -q`. Any failure = fail.
2. Check each acceptance criterion in the ticket with a command. Paste the command and the key output line into evidence.

## Once the run CLI exists (ingest tickets)
3. Fresh `.testdata/`. Generate the synthetic feed, run once: expect all items new and "first run".
4. Run again without changing the feed: **expect 0 new**. This is the check that catches re-listing.
5. Grow the feed (2-4 items), run again: expect exactly those as new.
6. Point FEED_URL at something broken, run: expect a stored failed run (✗), not a crash with nothing saved.

## Once the page exists (page tickets)
7. Start the server on a free port with the test DB. `curl` the page: latest briefing on top, history rows with ✓/✗ and counts.
8. Hit Run now twice fast: first adds a run, second is rate-limited.

## Verdict
Pass only if every step that applies passed. On fail, the bug body has:
steps to reproduce, expected, actual (exact output).

Last line: `RESULT: {"verdict": "pass"|"fail", "evidence": "...", "bug": {"title": "...", "body": "..."}}`
