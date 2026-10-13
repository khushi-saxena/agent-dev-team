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

gh repo fork khushi-saxena/confer-daily-briefing --clone && cd confer-daily-briefing   # or clone your own copy

```

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
# fill from the Oracle config preview. compartment_ocid = same as tenancy_ocid
terraform init
terraform apply                     # type yes
terraform output ssh
```
"Out of host capacity" is common for A1 in a single-AD region. Retry in a loop, or try `ocpus=1 memory_gb=6`.
What worked here: upgrading the Oracle account to Pay As You Go (still Always Free; set a $1 budget alert), after
which the retry loop got a VM within the hour.

Branch protection on `main` (repo Settings → Branches, or `gh api` from an admin token): require the status
checks **gates** and **tests**. The VM token doesn't have admin rights, so do this from your laptop.

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
```

Install everything (node, gh from cli.github.com, cloudflared, OpenClaw, Hermes, python3-pytest/feedparser,
labels, and the dispatcher cron in `/etc/cron.d`):
```bash
./scripts/install.sh
exec $SHELL -l                      # pick up the new PATH
```

## 4. Point the agents at the models

OpenClaw (builders + tester). Onboarding may default to a model that isn't on the free plan, so pick
`gpt-oss:20b` under "Browse all models":
```bash
openclaw onboard --auth-choice ollama-cloud --ollama-cloud-api-key "$OLLAMA_API_KEY"
./scripts/setup-agents.sh           # creates builder-ingest, builder-page, tester + the 2 hermes profiles
./scripts/setup-workspaces.sh       # each openclaw agent's workspace becomes a git worktree of this repo
```
`agents/runtime/openclaw.json` is what the live config ended up as. builder-ingest was moved to
`gpt-oss:120b` during ticket #17; everything else stayed on 20b.

Hermes (orchestrator + reviewer): set the default profile to Ollama Cloud `gpt-oss:120b` with `hermes model`,
and `setup-agents.sh` clones the two profiles from it. The live settings are in `agents/runtime/hermes-*.yaml`.

Smoke test all five. Every one must print a `RESULT` line:
```bash
for a in builder-ingest builder-page tester; do
  openclaw agent --agent $a --session-id smoke-$a --message 'Reply only with: RESULT: {"ok": true}' --json \
    | grep -o 'RESULT[^"]*'
done
for p in orchestrator reviewer; do
  hermes -p $p chat --oneshot -Q -q 'Reply only with: RESULT: {"ok": true}'
done
```

## 5. Start the team

```bash
python3 orchestration/dispatcher.py --dry-run
python3 orchestration/dispatcher.py               # orchestrator plans; issues appear on GitHub
```
From here cron runs it every 3 minutes, one action per tick. For a quick status (last events in local time,
tickets ready to merge or blocked, the agent running now):
```bash
echo 'source ~/briefing/scripts/st.sh' >> ~/.bashrc && source ~/.bashrc
st
```

Day to day:
```bash
st                                                  # what's happening
gh pr checks <N>                                    # both gates and tests must be green
gh pr merge <N> --merge                             # --merge keeps the agents' commits as authored
```
`status:blocked` means an agent hit 3 send-backs. Read its transcript in `logs/runs/`, comment on the issue with
what to change, then reset and requeue. Reset under the dispatcher's lock so a running tick can't overwrite it:
```bash
flock logs/.lock python3 -c "import json;p='logs/state.json';s=json.load(open(p));s['attempts']['<N>']=0;json.dump(s,open(p,'w'),indent=2)"
gh issue edit <N> --remove-label status:blocked --add-label status:ready
```
If a ticket keeps failing, split it into one-instruction jobs and run them by hand with
`openclaw agent --agent <builder> --session-id manual-<N>a --message '...'` (that's how #17 landed).

If the model provider returns 429, the dispatcher writes `logs/backoff_until` and pauses for 20 minutes.

## 6. Ship

```bash
cd ~/briefing && ./scripts/deploy-manual.sh
```
This keeps a separate clone in `~/briefing-live` serving `main`, installs systemd units `briefing-web` and
`briefing-tunnel` (cloudflared quick tunnel), adds `/etc/cron.d/briefing-ingest` (every 6 h), and prints the
public URL. Re-run it after each merge. It restarts only the web app, so the URL stays the same.

Evidence:
```bash
python3 scripts/token-report.py      # writes logs/token-report.md
git add logs/trace.jsonl logs/token-report.md && git commit -m "trace and token report" && git push
```
