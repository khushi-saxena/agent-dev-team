#!/usr/bin/env bash
# human-written fallback deploy. the ops ticket (#6) failed 6 times, see DELIVERY.md
# serves main from ~/briefing-live, kept apart from the agents' checkouts
set -euo pipefail
LIVE=/home/ubuntu/briefing-live
REPO=https://github.com/khushi-saxena/confer-daily-briefing.git
FEED=${FEED_URL:-https://github.com/python/cpython/releases.atom}

if [ -d "$LIVE/.git" ]; then git -C "$LIVE" pull -q --ff-only; else git clone -q "$REPO" "$LIVE"; fi
mkdir -p "$LIVE/data"
(cd "$LIVE" && python3 -c "from app.storage import init_db; init_db()")

sudo tee /etc/systemd/system/briefing-web.service >/dev/null <<EOF
[Unit]
Description=Daily Briefing web page
After=network-online.target
[Service]
User=ubuntu
WorkingDirectory=$LIVE
Environment=FEED_URL=$FEED
ExecStart=/usr/bin/python3 -m app.server
Restart=always
[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/briefing-tunnel.service >/dev/null <<EOF
[Unit]
Description=Cloudflare quick tunnel for the briefing page
After=briefing-web.service
[Service]
ExecStart=/usr/bin/cloudflared tunnel --no-autoupdate --url http://127.0.0.1:8080
Restart=always
[Install]
WantedBy=multi-user.target
EOF

echo "0 */6 * * * ubuntu cd $LIVE && FEED_URL=$FEED /usr/bin/python3 -c 'from app.storage import init_db; init_db(); from app.ingest import fetch_feed; fetch_feed()' >> $LIVE/data/cron.log 2>&1" | sudo tee /etc/cron.d/briefing-ingest >/dev/null
sudo chmod 644 /etc/cron.d/briefing-ingest

sudo systemctl daemon-reload
sudo systemctl enable --now briefing-web briefing-tunnel
sudo systemctl restart briefing-web
sleep 10
echo "local check: HTTP $(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/)"
echo "public url:  $(sudo journalctl -u briefing-tunnel --no-pager | grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' | tail -1)"
