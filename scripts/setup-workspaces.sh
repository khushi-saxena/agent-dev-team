#!/usr/bin/env bash
# makes each openclaw agent's workspace a git worktree of this repo, so files
# the agent writes with relative paths land in the repo instead of beside it.
# safe to re-run.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD

git fetch origin --prune
git config extensions.worktreeConfig true

# persona files sit in the worktree but must never be committed
excl="$(git rev-parse --git-common-dir)/info/exclude"
mkdir -p "$(dirname "$excl")"
for f in /AGENTS.md /SOUL.md /IDENTITY.md /USER.md /PROTOCOL.md /TOOLS.md \
         /HEARTBEAT.md /BOOTSTRAP.md /MEMORY.md /memory/ /.openclaw/ /.testdata/; do
  grep -qxF "$f" "$excl" 2>/dev/null || echo "$f" >> "$excl"
done

# old per-ticket worktrees hold the ticket-N branches, free them
for old in .worktrees/ticket-*; do
  [ -e "$old" ] && git worktree remove --force "$old"
done
git worktree prune

for a in builder-ingest builder-page tester; do
  wt="$ROOT/.worktrees/$a"
  [ -e "$wt/.git" ] || git worktree add --detach "$wt" origin/main
  old="$HOME/.openclaw/workspace-$a"
  [ -d "$old" ] && cp "$old"/*.md "$wt/" 2>/dev/null || true
  cp agents/$a/SOUL.md agents/$a/AGENTS.md agents/shared/PROTOCOL.md "$wt/"
  echo "worktree ready: $wt"
done

# point the agents at their new workspaces
python3 - "$ROOT" <<'PY'
import json, sys, shutil
from pathlib import Path
root = sys.argv[1]
cfg = Path.home() / ".openclaw" / "openclaw.json"
data = json.loads(cfg.read_text())
shutil.copy(cfg, str(cfg) + ".pre-worktree")
ids = ("builder-ingest", "builder-page", "tester")
n = 0
def walk(node):
    # agents are keyed by id in some versions, a list with "id" in others
    global n
    if isinstance(node, dict):
        for k, v in node.items():
            aid = k if k in ids else (v.get("id") if isinstance(v, dict) else None)
            if isinstance(v, dict) and aid in ids and "workspace" in v:
                v["workspace"] = f"{root}/.worktrees/{aid}"
                n += 1
            else:
                walk(v)
    elif isinstance(node, list):
        for v in node:
            if isinstance(v, dict) and v.get("id") in ids and "workspace" in v:
                v["workspace"] = f"{root}/.worktrees/{v['id']}"
                n += 1
            else:
                walk(v)
walk(data)
cfg.write_text(json.dumps(data, indent=2))
print(f"updated {n} agents in {cfg}")
PY

openclaw gateway restart
sleep 3
openclaw agents list | grep -E "^- |Workspace"
