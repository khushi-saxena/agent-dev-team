#!/usr/bin/env bash
set -euo pipefail

# Ensure Python dependencies are present. Feedparser is the only
# third‑party package required by the application.
/usr/bin/python3 -m pip install --quiet --upgrade pip
/usr/bin/python3 -m pip install --quiet feedparser

# ---------------------------------------------------------------------
# Cron job: run ingest once daily at 09:00 UTC.
# ---------------------------------------------------------------------
CRON_CMD="0 9 * * * /usr/bin/python3 -m app.ingest"
# Add the job only if it is not already present.  ``crontab -l`` will
# fail with a non‑zero exit status on a fresh crontab; we therefore
# redirect stderr to /dev/null.
(crontab -l 2>/dev/null | grep -qx "$CRON_CMD" || echo "$CRON_CMD") | crontab -

# ---------------------------------------------------------------------
# Systemd service files – user‑level.  The directory is based on the
# XDG spec, falling back to ``$HOME/.config`` when ``XDG_CONFIG_HOME`` is
# unset.
# ---------------------------------------------------------------------
SYSTEMD_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
mkdir -p "$SYSTEMD_DIR"

cat > "$SYSTEMD_DIR/briefing-server.service" <<'EOF'
[Unit]
Description=Briefing HTTP Server
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 -m app.server
Restart=on-failure
RestartSec=5
User=$USER
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
EOF

cat > "$SYSTEMD_DIR/briefing-tunnel.service" <<'EOF'
[Unit]
Description=Cloudflare Tunnel to Briefing Server
After=network.target briefing-server.service

[Service]
Type=simple
ExecStart=/usr/bin/cloudflared tunnel --url http://127.0.0.1:8080
Restart=on-failure
RestartSec=5
User=$USER
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
EOF

# Reload unit files and enable the services.
# The ``--user`` flag ensures that the services are started in the
# current user namespace.
systemctl --user daemon-reload
systemctl --user enable --now briefing-server.service
systemctl --user enable --now briefing-tunnel.service

exit 0
