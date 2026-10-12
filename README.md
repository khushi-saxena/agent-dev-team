# Confer take-home 3: Daily Briefing, delivered by an agent team

The product (a scheduled "what's new" briefing page) is built by five agents,
3 on OpenClaw and 2 on Hermes Agent, passing GitHub issues and PRs between them.
I wrote the infra and the agent setup. The agents write everything in `app/`, `tests/` and `scripts/deploy.sh`.

```
infra/            terraform: one always-free A1 VM (2 OCPU / 12 GB), SSH only
scripts/          install.sh (runtimes + agents), setup-agents.sh, token-report.py
agents/           each agent's prompts + openclaw config fragment
orchestration/    dispatcher.py (ticket router, no model), labels.sh
briefs/           product-brief.md: what the orchestrator plans from
.github/          agent-gates check: no merge without review:approved + test:passed
logs/             trace.jsonl (handoffs), runs/ (full agent transcripts, git-ignored)
DELIVERY.md       write-up, filled in at the end
```

## Runbook

**Day 1: infra + runtimes**
1. Oracle Always Free account → API key → `infra/terraform.tfvars` → `terraform apply`.
   "Out of host capacity" → bump `ad_index`, or try `ocpus=1 memory_gb=6`.
2. New GitHub machine account for the agents, fine-grained PAT on this repo only.
   Public repo, branch protection on `main` requiring the `gates` check.
3. Ollama Cloud key + an OpenRouter key. Check model names with the curl in `.env.example`.
4. On the VM: clone, fill `.env`, `./scripts/install.sh`.
5. Smoke test each agent by hand:
   `openclaw agent --agent tester --message "say hi, then RESULT: {\"ok\":true}"` and
   `hermes -p reviewer chat --oneshot -Q -q "say hi"`. Fix flags against `--help` if your versions differ.

**Day 2-3: let it run**
- `python3 orchestration/dispatcher.py --dry-run` first, then let cron take over.
- Watch the board on GitHub. Merge PRs that reach `status:ready-to-merge` (`gh pr merge N --squash`).
- `status:blocked` = an agent hit 3 send-backs. Read the run log in `logs/runs/`, tweak that agent's
  prompt or split the ticket, relabel it `status:ready`. **Write down every time you do this**,
  it's the best material for DELIVERY.md.
- Don't fix the product code yourself. If you must steer, comment on the issue; the builder sees it on its next try.

**Day 4: ship + evidence**
- After the ops ticket merges, `./scripts/deploy.sh`, grab the trycloudflare URL.
- Trigger a few runs (CLI + button) so history has ✓, ✗ and a 0-new row.
- `python3 scripts/token-report.py`, commit `logs/trace.jsonl` + `logs/token-report.md`.
- Fill DELIVERY.md. Record a 3-5 min screen capture of a ticket going through the pipeline.

## Things to verify on your versions
The CLI flags here came from the Oct 2026 docs. Check these before you trust them:
- `openclaw agent --agent <id> --message ... --json`: output shape (dispatcher reads `reply`/`text` and `usage`).
- `openclaw.json` per-agent `model.primary` / `fallbacks` keys, and the `ollama-cloud/` provider prefix.
- `hermes chat --provider ollama-cloud`: provider id name.
- OpenClaw's gateway runs tools in its own cwd; that's why prompts pass the absolute worktree path.
