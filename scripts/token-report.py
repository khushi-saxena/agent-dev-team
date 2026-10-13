#!/usr/bin/env python3
# builds logs/token-report.md from logs/trace.jsonl + hermes insights.
# openclaw usage comes from --json, split into fresh input / output / cache reads.
import json, re, subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
rows = [json.loads(l) for l in (ROOT / "logs/trace.jsonl").read_text().splitlines() if l.strip()]
done = [r for r in rows if r.get("event") == "agent_done"]
RUNTIME = {"orchestrator": "hermes", "reviewer": "hermes"}

def split(u):
    if not isinstance(u, dict):
        return None
    i = u.get("input") or u.get("input_tokens") or 0
    o = u.get("output") or u.get("output_tokens") or 0
    c = u.get("cacheRead") or u.get("cache_read_tokens") or 0
    t = u.get("total") or u.get("total_tokens") or (i + o + c)
    return i, o, c, t

def hermes(p):
    try:
        txt = subprocess.run(["hermes", "-p", p, "insights"], capture_output=True, text=True, timeout=60).stdout
    except Exception:
        return None
    num = lambda k: int((re.search(k + r":\s+([\d,]+)", txt) or [0, "0"])[1].replace(",", ""))
    return {"sessions": num("Sessions"), "input": num("Input tokens"),
            "output": num("Output tokens"), "total": num("Total tokens")}

agg = defaultdict(lambda: dict(calls=0, measured=0, i=0, o=0, c=0, t=0, secs=0))
tick = defaultdict(lambda: dict(calls=0, t=0, retries=0))
for r in done:
    a = agg[(r["agent"], r.get("model"), r["phase"])]
    a["calls"] += 1
    a["secs"] += r.get("secs", 0)
    k = tick[r.get("ticket")]
    k["calls"] += 1
    k["retries"] += r["phase"] == "retry"
    s = split(r.get("usage"))
    if s:
        a["measured"] += 1
        for key, v in zip("ioct", s):
            a[key] += v
        k["t"] += s[3]

M = lambda n: f"{n/1e6:.2f}M" if n >= 1e5 else f"{n/1e3:.1f}k"
out = ["# Token & model report", "",
       "OpenClaw rows are measured per call (`openclaw agent --json`). Hermes does not return usage per",
       "oneshot call, so its rows come from `hermes -p <profile> insights` (whole-profile totals).", "",
       "## Per agent / model / phase", "",
       "| agent | runtime | model | phase | calls | fresh in | out | cache read | total | secs |",
       "|---|---|---|---|---|---|---|---|---|---|"]
phase = defaultdict(lambda: [0, 0])
for (agent, model, ph), a in sorted(agg.items()):
    if agent in RUNTIME:
        continue
    out.append(f"| {agent} | openclaw | {model} | {ph} | {a['calls']} | {M(a['i'])} | {M(a['o'])} | "
               f"{M(a['c'])} | {M(a['t'])} | {a['secs']} |")
    phase[ph][0] += a["i"] + a["o"]
    phase[ph][1] += a["t"]
for p, ph in (("orchestrator", "planning"), ("reviewer", "review")):
    h = hermes(p)
    calls = sum(a["calls"] for (ag, _, _), a in agg.items() if ag == p)
    secs = sum(a["secs"] for (ag, _, _), a in agg.items() if ag == p)
    if h:
        cache = max(h["total"] - h["input"] - h["output"], 0)
        out.append(f"| {p} | hermes | gpt-oss:120b | {ph} | {calls} | {M(h['input'])} | {M(h['output'])} | "
                   f"{M(cache)} | {M(h['total'])} | {secs} |")
        phase[ph][0] += h["input"] + h["output"]
        phase[ph][1] += h["total"]

out += ["", "## By phase", "", "| phase | fresh (in+out) | total incl. cache |", "|---|---|---|"]
out += [f"| {p} | {M(f)} | {M(t)} |" for p, (f, t) in sorted(phase.items())]
f_all, t_all = sum(v[0] for v in phase.values()), sum(v[1] for v in phase.values())
out += [f"| **all** | **{M(f_all)}** | **{M(t_all)}** |"]

out += ["", "## OpenClaw tokens per ticket", "", "| ticket | calls | retries | total |", "|---|---|---|---|"]
out += [f"| #{t} | {k['calls']} | {k['retries']} | {M(k['t'])} |"
        for t, k in sorted(tick.items(), key=lambda x: -x[1]["t"]) if t]

ev = defaultdict(int)
for r in rows:
    ev[r.get("event")] += 1
out += ["", "## Flow counts", ""] + [f"- {k}: {v}" for k, v in sorted(ev.items())]
out += ["", "Not in the trace: the three hand-started builder-ingest calls that finished #17",
        "(sessions manual-17a/b/c, run outside the dispatcher)."]

(ROOT / "logs/token-report.md").write_text("\n".join(out) + "\n")
print("\n".join(out))
