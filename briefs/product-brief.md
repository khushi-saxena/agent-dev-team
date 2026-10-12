# Product brief: Daily Briefing

## The need
The team wants a small scheduled briefing. Each run checks one public source and
publishes only what changed since the last run, on a public page with a history
of every run.

## Must have
1. **Pull on a schedule.** Each run reads one source. Use the synthetic feed
   (below) as the default so tests are deterministic; a real RSS feed URL can be
   swapped in through the `FEED_URL` env var.
2. **Store every run.** When it ran, whether it succeeded, the items it saw.
   Failed runs are stored too, with the error.
3. **What's new.** Each item gets a stable ID: the feed's own guid/id, else a
   sha256 of its link. New = IDs never stored before. Plain code, no model.
   The first run has nothing to compare against: everything is new, and the page
   says "first run".
4. **Public page, no login.** Top: latest briefing: date, "N new since the last
   run", one short line + link per new item. When 0 new, one friendly line
   instead of an empty list. Below: run history, one row per run: time, ✓/✗,
   new count.
5. **Run now.** A button on the page and a documented CLI command. The button is
   rate-limited (at most once per 2 minutes, globally) and says so when limited.
6. **Optional summaries.** If a model is used for a one-line summary per item, it
   is behind a flag, and any HTTP 402/429 or error falls back to the plain title.
   Never block a run on the model.

## Technical constraints (decided by the engineer)
- Runs on a 2 OCPU / 12 GB Arm Ubuntu 24.04 VM that also hosts the agents. Keep it light.
- Python 3.12 standard library + `feedparser` is fine. No frameworks heavier than
  that. SQLite file for storage under `data/` (git-ignored). One process serves
  the page and the run-now endpoint, bound to 127.0.0.1:8080. A cloudflared quick
  tunnel exposes it.
- Schedule: system cron calling the CLI. (A Hermes cron job is a nice extra, not required.)
- Synthetic feed: a small script that writes a valid RSS file, adding 2-4 made-up
  items per call with stable guids, so tests can run "fetch, fetch again, expect 0 new".
- Code lives in `app/`, tests in `tests/` and runnable with `python3 -m pytest -q`.
- Ops: one idempotent script `scripts/deploy.sh` that installs deps, installs the
  cron entry, and runs the server + tunnel as systemd services.

## Out of scope
Auth, multiple users, styling beyond readable, more than one source (unless the
core is merged and green).

## Definition of done for the whole thing
Public URL loads. History shows several real runs including one with 0 new.
Pressing Run now adds a row. Every merged PR passed the reviewer and the tester.
