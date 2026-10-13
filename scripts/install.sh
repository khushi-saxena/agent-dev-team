#!/usr/bin/env bash
# run once on a fresh VM after `terraform apply`:
#   git clone <repo> ~/briefing && cd ~/briefing && ./scripts/install.sh
# installs the agent runtimes and tooling. the product's own install/cron
# is an ops ticket the agents do, not this script.
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f .env ] || { echo "copy .env.example to .env and fill it in first"; exit 1; }
set -a; source .env; set +a

# node 24 (openclaw needs 24.16+)
if ! node -v 2>/dev/null | grep -qE '^v(2[4-9]|[3-9][0-9])'; then
  curl -fsSL https://deb.nodesource.com/setup_24.x | sudo -E bash -
  sudo apt-get install -y nodejs
fi

# gh cli
if ! command -v gh >/dev/null; then
  sudo mkdir -p -m 755 /etc/apt/keyrings
  curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
    | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg >/dev/null
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
    | sudo tee /etc/apt/sources.list.d/github-cli.list >/dev/null
  sudo apt-get update && sudo apt-get install -y gh
fi

# cloudflared for the free trycloudflare.com url
if ! command -v cloudflared >/dev/null; then
  curl -fsSL -o /tmp/cloudflared.deb \
    https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb
  sudo dpkg -i /tmp/cloudflared.deb
fi

# agent runtimes
command -v openclaw >/dev/null || curl -fsSL https://openclaw.ai/install.sh | bash
command -v hermes   >/dev/null || curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash -s -- --skip-browser
export PATH="$HOME/.local/bin:$HOME/.npm-global/bin:$PATH"

# gh auth with the repo-scoped token from .env
echo "$GH_TOKEN" | gh auth login --with-token
gh auth setup-git

./scripts/setup-agents.sh
./orchestration/labels.sh

# python deps for the product and its tests (PEP 668 blocks pip, use apt)
sudo apt-get install -y python3-pytest python3-feedparser jq

# dispatcher every 3 min, in /etc/cron.d so an agent's `crontab -` can't remove it
# (that happened twice, see DELIVERY.md). flock inside keeps it to one model call at a time.
echo "*/3 * * * * $USER cd $PWD && PATH=$HOME/.npm-global/bin:$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin /usr/bin/python3 orchestration/dispatcher.py >> logs/dispatcher.log 2>&1" \
  | sudo tee /etc/cron.d/confer-dispatcher >/dev/null
sudo chmod 644 /etc/cron.d/confer-dispatcher

echo "done. dashboards: ssh -L 18789:localhost:18789 -L 9119:localhost:9119 ubuntu@<ip>"
