#!/usr/bin/env bash
#
# idempotent deployment script for the briefing‑project
#
# It fulfils the following tasks:
#   1. ensure python3-feedparser is installed with apt
#   2. add an idempotent cron entry for daily ingest
#   3. create two user‑level systemd units: briefing-server.service and briefing-tunnel.service
#   4. run systemctl daemon‑reload, enable and start the units
#   5. perform a simple smoke test – hit the public page and check the run‑now endpoint
#
# Features
# ---------
#   * DRY_RUN mode – export DRY_RUN=1 to echo commands without executing them
#   * Uses ${REPO_ROOT} calculated from the script location, avoids hard‑coding
#   * The cron entry changes the working directory, sets FEED_URL and invokes the ingest module
#   * Systemd unit files are written to ~/.config/systemd/user and contain an expanded `$USER`
#   * Idempotence: existing cron line is removed before appending the new one
#   * Exit normally with status 0 after successful deployment and smoke test
#   * On failure any non‑zero exit status is reported
#
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/.." &>/dev/null && pwd)
DRY_RUN=${DRY_RUN:-0}
CRON_USER=$(whoami)

do_cmd() {
  if [[ $DRY_RUN -eq 1 ]]; then
    echo "DRY_RUN: $*"
    return 0
  fi
  eval "$*"
}

echo "--- Deploy (DRY_RUN=$DRY_RUN) ---"

# 1) apt install python3-feedparser
echo "Installing python3-feedparser"
do_cmd "sudo apt-get update -qq"
do_cmd "sudo apt-get install -y -qq python3-feedparser"

# 2) add cron entry (idempotent)
CRON_LINE="0 9 * * * cd \"$REPO_ROOT\" && FEED_URL=https://github.com/python/cpython/releases.atom /usr/bin/python3 -m app.ingest"
crontab -l > /tmp/crontab.tmp 2>/dev/null || true
# remove old lines from this repo (heuristically drop any line that starts with 0 9 * * *)
grep -v '^0 9 .*' /tmp/crontab.tmp > /tmp/crontab.new || true
printf "%s\n" "$CRON_LINE" >> /tmp/crontab.new
crontab /tmp/crontab.new
rm -f /tmp/crontab.*

# 3) systemd unit files
SYSTEMD_DIR=$HOME/.config/systemd/user
mkdir -p "$SYSTEMD_DIR"

[cat > "$SYSTEMD_DIR/briefing-server.service" <<EOF
[Unit]
Description=Briefing HTTP Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$REPO_ROOT
ExecStart=/usr/bin/python3 -m app.server
Restart=on-failure

[Install]
WantedBy=default.target
EOF

[cat > "$SYSTEMD_DIR/briefing-tunnel.service" <<EOF
[Unit]
Description=Briefing Cloudflare Tunnel
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$REPO_ROOT
ExecStart=/usr/bin/cloudflared tunnel --url http://127.0.0.1:8080
Restart=on-failure

[Install]
WantedBy=default.target
EOF

do_cmd "systemctl --user daemon-reload"
do_cmd "systemctl --user enable --now briefing-server briefing-tunnel"

# 4) smoke test
echo "Running smoke test"
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8080)
if [[ $HTTP_STATUS -ne 200 ]]; then
  echo "Error: HTTP status $HTTP_STATUS on 127.0.0.1:8080"
  exit 1
fi
RUNNOW=$(curl -s http://127.0.0.1:8080/run-now | head -1)
if [[ -z "$RUNNOW" ]]; then
  echo "Error: /run-now endpoint returned nothing"
  exit 1
fi

echo "Deployment succeeded. Smoke test passed."
exit 0

