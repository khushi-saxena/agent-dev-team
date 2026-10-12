# Runbook: exact steps

## 1. Sign-ups (do these first; Oracle can take a few hours to activate)

| what | where | what you need out of it |
|---|---|---|
| Oracle Cloud Always Free | https://signup.cloud.oracle.com | pick home region `US West (San Jose)`; you can't change it later. Card is identity check only |
| Ollama Cloud (main models) | https://ollama.com/signup → https://ollama.com/settings/keys | one API key. Free plan has `gpt-oss:120b` and `gpt-oss:20b` |
| OpenRouter (fallback) | https://openrouter.ai → https://openrouter.ai/settings/keys | 2 keys: `openclaw-agents`, `hermes-agents`. Free = ~50 req/day, 20/min |
| GitHub token (your own account) | https://github.com/settings/personal-access-tokens/new (fine-grained), after the repo exists | Only select repositories → `confer-daily-briefing`. Permissions: Contents, Issues, Pull requests, Workflows = Read and write. 30-day expiry |

**Oracle API key** (after the account is active): Console → profile icon (top right) → My profile → API keys → Add API key → Generate API key pair → **Download private key** → Add. Copy the "Configuration file preview" it shows (user, fingerprint, tenancy, region).

```bash
mkdir -p ~/.oci && mv ~/Downloads/*.pem ~/.oci/oci_api_key.pem && chmod 600 ~/.oci/oci_api_key.pem
```

## 2. On your Mac: repo + VM

```bash
brew install terraform gh
gh auth login                       # as YOU
ls ~/.ssh/id_ed25519.pub || ssh-keygen -t ed25519

unzip confer-daily-briefing.zip && cd confer-daily-briefing
git init -b main && git add . && git commit -m "infra and agent setup"
gh repo create confer-daily-briefing --public --source . --push

```

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
# fill from the Oracle config preview. compartment_ocid = same as tenancy_ocid
terraform init
terraform apply                     # type yes
terraform output ssh
```
"Out of host capacity" → set `ad_index = 1` (then 2), or `ocpus = 1`, `memory_gb = 6`, and apply again.

## 3. On the VM

```bash
ssh ubuntu@<public_ip>
cloud-init status --wait
git clone https://github.com/khushi-saxena/confer-daily-briefing.git ~/briefing
cd ~/briefing
cp .env.example .env && nano .env   # GH_TOKEN = the fine-grained token, OLLAMA_API_KEY, OPENROUTER keys
set -a; source .env; set +a
```

Check the model key works before anything else:
```bash
curl -s https://ollama.com/v1/models -H "Authorization: Bearer $OLLAMA_API_KEY" | jq -r '.data[].id'
curl -s https://ollama.com/v1/chat/completions -H "Authorization: Bearer $OLLAMA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-oss:20b","messages":[{"role":"user","content":"say hi"}]}' | jq -r '.choices[0].message.content'
```

Install everything:
```bash
./scripts/install.sh
exec $SHELL -l                      # pick up new PATH
```

## 4. Point the agents at the models

OpenClaw (builders + tester):
```bash
openclaw onboard --auth-choice ollama-cloud --ollama-cloud-api-key "$OLLAMA_API_KEY"
openclaw onboard --help | grep -i openrouter      # use that auth choice with $OPENROUTER_API_KEY
./scripts/setup-agents.sh                         # re-run so per-agent models get merged in
```

Hermes (orchestrator + reviewer), once per profile:
```bash
hermes -p orchestrator model
hermes -p reviewer model
```
Pick Ollama Cloud if listed. If not: More providers → Custom endpoint → `https://ollama.com/v1`, key = your Ollama key, model `gpt-oss:120b`.

Smoke test all five:
```bash
for a in builder-ingest builder-page tester; do
  openclaw agent --agent $a --message 'Reply only with: RESULT: {"ok": true}' --json
done
for p in orchestrator reviewer; do
  hermes -p $p chat --oneshot -Q -q 'Reply only with: RESULT: {"ok": true}'
done
```
Every one must print a `RESULT` line. If OpenClaw's JSON doesn't have the reply under `reply`, `text` or `output`, the dispatcher needs a one-line fix.

## 5. Start the team

```bash
python3 orchestration/dispatcher.py --dry-run
python3 orchestration/dispatcher.py               # orchestrator plans; issues appear on GitHub
tail -f logs/dispatcher.log                       # cron runs it every 3 min from here
```

After the first PR shows up: repo Settings → Branches → Add rule → `main` → Require status checks → add `gates` → Save.

Day to day, from your Mac:
```bash
gh issue list --label status:ready-to-merge
gh pr merge <N> --squash --delete-branch          # you review and merge
gh issue list --label status:blocked              # 3 send-backs; read logs/runs/ on the VM
gh issue edit <N> --add-label status:ready --remove-label status:blocked   # after you fix the prompt
```
Write down every time you step in. That's your DELIVERY.md material.

## 6. Ship

On the VM, once the ops ticket is merged:
```bash
cd ~/briefing && git pull && ./scripts/deploy.sh
# if deploy.sh doesn't start a tunnel yet:
cloudflared tunnel --url http://localhost:8080    # prints your https://*.trycloudflare.com link
```
Trigger a few runs, including one with nothing new. Then:
```bash
python3 scripts/token-report.py
git add logs/trace.jsonl logs/token-report.md && git commit -m "evidence" && git push
```
Fill DELIVERY.md, email Confer the link + repo.

## Why no bot account
Agents use your token but every commit is authored as the agent (`builder-ingest (openclaw agent)` etc., set per worktree by the dispatcher) and every comment starts with `[agent · runtime · model]`. That's the "distinct author per agent" the brief asks for. You still review and merge.
