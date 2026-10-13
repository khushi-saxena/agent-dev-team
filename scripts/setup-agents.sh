#!/usr/bin/env bash
# creates the 5 agents: 3 on openclaw, 2 on hermes, and copies their prompts in.
# re-runnable.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a
ROOT=$PWD

# ---- openclaw: builder-ingest, builder-page, tester ----
for a in builder-ingest builder-page tester; do
  ws="$HOME/.openclaw/workspace-$a"
  openclaw agents list 2>/dev/null | grep -q "^$a\b" || \
    openclaw agents add "$a" --workspace "$ws" --non-interactive
  mkdir -p "$ws"
  cp agents/$a/SOUL.md   "$ws/SOUL.md"
  cp agents/$a/AGENTS.md "$ws/AGENTS.md"
  cp agents/shared/PROTOCOL.md "$ws/PROTOCOL.md"
done

# per-agent models live in openclaw.json. merge our fragment in.
python3 - <<'PY'
import json, os, re, pathlib
cfg_path = pathlib.Path.home()/".openclaw/openclaw.json"
cfg = json.loads(cfg_path.read_text()) if cfg_path.exists() else {}
frag = pathlib.Path("agents/openclaw.agents.json").read_text()
frag = re.sub(r"\$\{(\w+)\}", lambda m: os.environ.get(m.group(1), ""), frag)
frag = json.loads(frag)
agents = cfg.setdefault("agents", {})
agents.setdefault("defaults", {}).update(frag["defaults"])
by_id = {a["id"]: a for a in agents.get("list", [])}
for a in frag["list"]:
    by_id.setdefault(a["id"], {}).update(a)
agents["list"] = list(by_id.values())
cfg_path.write_text(json.dumps(cfg, indent=2))
print("openclaw config updated")
PY
openclaw gateway restart || true

# ---- hermes: orchestrator, reviewer ----
for p in orchestrator reviewer; do
  hermes profile list 2>/dev/null | grep -q "\b$p\b" || \
    hermes profile create "$p" --clone   # copies the default profile's model + provider
  pdir="$HOME/.hermes/profiles/$p"
  cp agents/$p/SOUL.md "$pdir/SOUL.md"
  mkdir -p "$pdir/skills/delivery"
  cp agents/shared/PROTOCOL.md "$pdir/skills/delivery/SKILL.md"
  # keys per profile, so `hermes -p X insights` attributes tokens per agent
  {
    echo "OLLAMA_API_KEY=$OLLAMA_API_KEY"
    echo "OPENROUTER_API_KEY=${OPENROUTER_KEY_HERMES:-$OPENROUTER_API_KEY}"
  } > "$pdir/.env"
  chmod 600 "$pdir/.env"
done

openclaw agents list --bindings
hermes profile list
