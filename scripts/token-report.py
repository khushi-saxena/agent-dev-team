#!/usr/bin/env python3
"""Builds logs/token-report.md from logs/trace.jsonl plus whatever the runtimes report.

Phases come from the dispatcher: planning, coding, review, test, retry.
OpenClaw calls carry real usage when --json returns it. Hermes calls are
filled from `hermes -p <profile> insights`. Anything missing is marked as an estimate.
"""
import json, subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
rows = [json.loads(l) for l in (ROOT / "logs/trace.jsonl").read_text().splitlines() if l.strip()]
done = [r for r in rows if r.get("event") == "agent_done"]

def tok(u):
    if not isinstance(u, dict):
        return None
    for k in ("total_tokens", "totalTokens", "total"):
        if k in u:
            return u[k]
    i = u.get("input_tokens") or u.get("input") or 0
    o = u.get("output_tokens") or u.get("output") or 0
    return (i + o) or None

agg = defaultdict(lambda: {"calls": 0, "tokens": 0, "measured": 0, "secs": 0})
for r in done:
    k = (r["agent"], r.get("model"), r["phase"])
    a = agg[k]
    a["calls"] += 1
    a["secs"] += r.get("secs", 0)
    t = tok(r.get("usage"))
    if t:
        a["tokens"] += t
        a["measured"] += 1

phase_tot = defaultdict(int)
out = ["# Token & model report", "",
       "| agent | model | phase | calls | tokens | measured calls | wall secs |",
       "|---|---|---|---|---|---|---|"]
for (agent, model, phase), a in sorted(agg.items()):
    est = "" if a["measured"] == a["calls"] else " (partial)"
    out.append(f"| {agent} | {model} | {phase} | {a['calls']} | {a['tokens']}{est} | {a['measured']} | {a['secs']} |")
    phase_tot[phase] += a["tokens"]

out += ["", "## By phase (measured)", ""]
out += [f"- **{p}**: {t}" for p, t in sorted(phase_tot.items())]

ev = defaultdict(int)
for r in rows:
    ev[r.get("event")] += 1
out += ["", "## Flow counts", ""] + [f"- {k}: {v}" for k, v in sorted(ev.items())]

out += ["", "## Hermes insights (orchestrator, reviewer)", ""]
for p in ("orchestrator", "reviewer"):
    try:
        txt = subprocess.run(["hermes", "-p", p, "insights"], capture_output=True, text=True, timeout=60).stdout
    except Exception as e:
        txt = f"(not available: {e})"
    out += [f"### {p}", "```", txt.strip()[:3000], "```"]

(ROOT / "logs/token-report.md").write_text("\n".join(out) + "\n")
print("\n".join(out))
