# Confer take-home 3: Daily Briefing, delivered by an agent team

**Live:** https://var-populations-red-star.trycloudflare.com · **Write-up:** [DELIVERY.md](DELIVERY.md)

A scheduled "what's new" page for the CPython releases feed, built by five agents (3 on OpenClaw, 2 on Hermes
Agent) passing GitHub issues and PRs between them. The agents wrote everything in `app/` and `tests/`. I wrote the
infra, the agent setup and the dispatcher that routes tickets, and I reviewed and merged.

```
app/              the product (agent-written): storage, ingest, diff, server, run_now
tests/            pytest suite (agent-written)
infra/            terraform: one always-free OCI A1 VM (2 OCPU / 12 GB), SSH only
agents/           personas per agent (SOUL.md, AGENTS.md), shared PROTOCOL.md
agents/runtime/   the live openclaw + hermes configs, secrets stripped
orchestration/    dispatcher.py (ticket router, no model), labels.sh
scripts/          install, agent setup, worktrees, token report, manual deploy
briefs/           product-brief.md, what the orchestrator planned from
.github/          required checks on main: gates (agent sign-off labels) + tests (pytest on a clean runner)
logs/             trace.jsonl (every handoff and agent run), token-report.md. runs/ (full transcripts) stays on the VM
RUNBOOK.md        step-by-step setup from zero
DELIVERY.md       roster, ticket flow, what broke, token report, what I'd change
```

## Run the product locally

```bash
pip install feedparser pytest
mkdir -p data && python3 -c "from app.storage import init_db; init_db()"
FEED_URL=https://github.com/python/cpython/releases.atom python3 -m app.server   # http://127.0.0.1:8080
python3 -m pytest -q
```

Rebuilding the whole agent team on a fresh VM is in [RUNBOOK.md](RUNBOOK.md).

## How agents are told apart

Agents use my GitHub token, but every commit is authored as the agent (`builder-ingest (openclaw agent)`,
`builder-page (openclaw agent)`; the dispatcher sets this per worktree), and every comment starts with
`**[agent · runtime · model]**`. Agent code only reaches `main` through PRs that pass both required checks.
My own commits to `main` are harness and docs.
