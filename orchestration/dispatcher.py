#!/usr/bin/env python3
"""Ticket dispatcher. Runs from cron, does ONE agent action per tick.

Tickets are GitHub issues; their state is a status:* label and their owner
is an agent:* label. The dispatcher spends no tokens. It reads the board,
decides whose turn it is, hands that agent the ticket, then moves the
labels from the agent's RESULT line. Every handoff goes to logs/trace.jsonl.

    python3 orchestration/dispatcher.py            # one tick
    python3 orchestration/dispatcher.py --dry-run  # say what would run
    python3 orchestration/dispatcher.py --loop     # tick until idle
"""
import fcntl, json, os, re, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOGS = ROOT / "logs"; LOGS.mkdir(exist_ok=True)
TRACE = LOGS / "trace.jsonl"
STATE = LOGS / "state.json"
WT = ROOT / ".worktrees"
MAX_ATTEMPTS = 3
AGENT_TIMEOUT = 1800
DRY = "--dry-run" in sys.argv


def load_env():
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.split("#")[0].strip())

load_env()
REPO = os.environ.get("GH_REPO", "")

AGENTS = {
    "orchestrator":   {"runtime": "hermes",   "model": os.environ.get("STRONG_MODEL"), "fallback": os.environ.get("FALLBACK_STRONG")},
    "reviewer":       {"runtime": "hermes",   "model": os.environ.get("STRONG_MODEL"), "fallback": os.environ.get("FALLBACK_STRONG")},
    "builder-ingest": {"runtime": "openclaw", "model": os.environ.get("CHEAP_MODEL")},
    "builder-page":   {"runtime": "openclaw", "model": os.environ.get("CHEAP_MODEL")},
    "builder-ops":    {"runtime": "openclaw", "model": os.environ.get("CHEAP_MODEL"), "as": "builder-page"},
    "tester":         {"runtime": "openclaw", "model": os.environ.get("CHEAP_MODEL")},
}
BUILDERS = [a for a in AGENTS if a.startswith("builder-")]


# ---------- small helpers ----------

def sh(*cmd, cwd=None, check=True, timeout=120, inp=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, input=inp)
    if check and r.returncode:
        raise RuntimeError(f"{' '.join(cmd[:4])}... failed: {r.stderr.strip()[:500]}")
    return r.stdout.strip()

def gh(*args, **kw):
    return sh("gh", *args, "--repo", REPO, **kw) if args[0] in ("issue", "pr", "label") else sh("gh", *args, **kw)

def ghj(*args):
    out = gh(*args)
    return json.loads(out) if out else []

def trace(**ev):
    ev = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), **ev}
    with TRACE.open("a") as f:
        f.write(json.dumps(ev) + "\n")
    print(json.dumps(ev))

def state():
    return json.loads(STATE.read_text()) if STATE.exists() else {}

def save_state(s):
    STATE.write_text(json.dumps(s, indent=2))

def labels_of(item):
    return {l["name"] for l in item.get("labels", [])}

def relabel(kind, num, add=(), remove=()):
    """kind = issue | pr. only removes labels that are actually there."""
    cur = labels_of(ghj(kind, "view", str(num), "--json", "labels"))
    args = []
    for a in add:
        args += ["--add-label", a]
    for r in remove:
        if r in cur:
            args += ["--remove-label", r]
    if args and not DRY:
        gh(kind, "edit", str(num), *args)

def set_status(num, new):
    cur = labels_of(ghj("issue", "view", str(num), "--json", "labels"))
    relabel("issue", num, add=[f"status:{new}"],
            remove=[l for l in cur if l.startswith("status:") and l != f"status:{new}"])

def comment(kind, num, agent, body):
    a = AGENTS.get(agent, {})
    head = f"**[{agent} · {a.get('runtime', 'dispatcher')} · {a.get('model', '-')}]**"
    if not DRY:
        gh(kind, "comment", str(num), "--body", f"{head}\n\n{body}")

def issues(*labels, state_="open"):
    args = ["issue", "list", "--state", state_, "--limit", "200",
            "--json", "number,title,body,labels,state"]
    for l in labels:
        args += ["--label", l]
    return ghj(*args)

def owner(issue):
    for l in labels_of(issue):
        if l.startswith("agent:"):
            return l.split(":", 1)[1]

def pr_for(num):
    prs = ghj("pr", "list", "--head", f"ticket-{num}", "--state", "open", "--json", "number,labels,url")
    return prs[0] if prs else None

def parse_result(text):
    """agents end with a line: RESULT: {...json...}"""
    for line in reversed(text.splitlines()):
        m = re.search(r"RESULT:\s*(\{.*\})\s*$", line.strip())
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
    return None


# ---------- running an agent ----------

def run_agent(agent, prompt, cwd, phase, ticket=None):
    a = AGENTS[agent]
    started = time.time()
    trace(event="handoff", to=agent, runtime=a["runtime"], model=a["model"], phase=phase, ticket=ticket)
    if DRY:
        return {"verdict": "dry-run"}, ""

    usage = None
    if a["runtime"] == "openclaw":
        oc_id = a.get("as", agent)
        cmd = ["openclaw", "agent", "--agent", oc_id, "--message", prompt, "--json"]
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=AGENT_TIMEOUT)
        out = r.stdout
        try:
            j = json.loads(out)
            usage = j.get("usage") or j.get("meta", {}).get("usage")
            out = j.get("reply") or j.get("text") or j.get("output") or out
            if isinstance(out, list):
                out = "\n".join(map(str, out))
        except (json.JSONDecodeError, AttributeError):
            pass
        model_used = a["model"]
    else:
        def hermes(model):
            # primary = whatever `hermes -p <agent> model` was set to (ollama cloud).
            # fallback = openrouter, passed explicitly
            cmd = ["hermes", "-p", agent, "chat", "--oneshot", "-Q", "--yolo"]
            if model.startswith("openrouter/"):
                cmd += ["--provider", "openrouter", "-m", model.split("/", 1)[1]]
            return subprocess.run(cmd + ["-q", prompt], cwd=cwd, capture_output=True, text=True, timeout=AGENT_TIMEOUT)
        model_used = a["model"]
        r = hermes(model_used)
        out = r.stdout
        if r.returncode and re.search(r"\b(402|429)\b|quota|rate.?limit", r.stdout + r.stderr, re.I) and a.get("fallback"):
            trace(event="model_fallback", agent=agent, frm=model_used, to=a["fallback"], reason=(r.stderr or r.stdout)[-200:])
            model_used = a["fallback"]
            r = hermes(model_used)
            out = r.stdout

    (LOGS / "runs").mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    (LOGS / "runs" / f"{stamp}-{agent}-{ticket}.log").write_text(
        f"$ {agent} ({phase}) exit={r.returncode}\n--- prompt ---\n{prompt}\n--- out ---\n{out}\n--- err ---\n{r.stderr}")

    res = parse_result(out or "")
    trace(event="agent_done", agent=agent, model=model_used, phase=phase, ticket=ticket,
          exit=r.returncode, secs=round(time.time() - started), usage=usage,
          result=res if res else "NO_RESULT_LINE")
    return res, out


def worktree(num, agent=None):
    """per-ticket worktree on branch ticket-<n>; git author = the agent."""
    path = WT / f"ticket-{num}"
    branch = f"ticket-{num}"
    sh("git", "fetch", "origin", "--prune", cwd=ROOT)
    if not path.exists():
        remote = sh("git", "ls-remote", "--heads", "origin", branch, cwd=ROOT)
        if remote:
            sh("git", "worktree", "add", "-B", branch, str(path), f"origin/{branch}", cwd=ROOT)
        else:
            sh("git", "worktree", "add", "-b", branch, str(path), "origin/main", cwd=ROOT)
    else:
        sh("git", "checkout", branch, cwd=path)
        if sh("git", "ls-remote", "--heads", "origin", branch, cwd=ROOT):
            sh("git", "reset", "--hard", f"origin/{branch}", cwd=path)
    if agent:
        sh("git", "config", "extensions.worktreeConfig", "true", cwd=ROOT)
        rt = AGENTS[agent]["runtime"]
        sh("git", "config", "--worktree", "user.name", f"{agent} ({rt} agent)", cwd=path)
        sh("git", "config", "--worktree", "user.email", f"{agent}@agents.confer-briefing.invalid", cwd=path)
    return path


# ---------- the steps ----------

def bump(s, num, why):
    k = str(num)
    s.setdefault("attempts", {})[k] = s.get("attempts", {}).get(k, 0) + 1
    n = s["attempts"][k]
    if n >= MAX_ATTEMPTS:
        set_status(num, "blocked")
        comment("issue", num, "dispatcher",
                f"Sent back {n} times (last: {why}). Parking this for a human. @{os.environ.get('HUMAN_GH', 'khushi-saxena')}")
        trace(event="escalated", ticket=num, attempts=n, why=why)
    return n


def step_build(issue, s):
    num, agent = issue["number"], owner(issue)
    retry = "status:changes-requested" in labels_of(issue)
    path = worktree(num, agent)
    base = sh("git", "rev-parse", "HEAD", cwd=path)

    feedback = ""
    if retry:
        cs = ghj("issue", "view", str(num), "--json", "comments")["comments"]
        pr = pr_for(num)
        if pr:
            cs += ghj("pr", "view", str(pr["number"]), "--json", "comments")["comments"]
        sent_back = [c["body"] for c in cs if "[reviewer" in c["body"] or "[tester" in c["body"]]
        feedback = "\n\n## Why it came back\n" + "\n---\n".join(sent_back[-2:])

    set_status(num, "in-progress")
    prompt = (f"You are {agent}. Read PROTOCOL.md in your workspace first.\n"
              f"Ticket #{num}: {issue['title']}\n\n{issue['body']}{feedback}\n\n"
              f"Work ONLY inside this git worktree: {path}\n"
              f"Commit your changes there (git add + git commit, message: '#{num} <what you did>'). Do not push.\n"
              f"End with one line: RESULT: {{\"status\": \"done\"|\"stuck\", \"summary\": \"...\", \"how_to_test\": \"...\"}}")
    res, _ = run_agent(agent, prompt, path, "retry" if retry else "coding", num)
    if DRY:
        return

    head = sh("git", "rev-parse", "HEAD", cwd=path)
    if not res or res.get("status") != "done" or head == base:
        why = "no commits" if head == base else (res or {}).get("summary", "no RESULT line")
        comment("issue", num, "dispatcher", f"{agent} finished without a usable change: {why}")
        set_status(num, "changes-requested" if retry else "ready")
        bump(s, num, why)
        return

    sh("git", "push", "-u", "origin", f"ticket-{num}", "--force-with-lease", cwd=path)
    pr = pr_for(num)
    body = (f"Closes #{num}\n" + "".join(f"Closes #{b}\n" for b in s.get("bugs", {}).get(str(num), [])) +
            f"\n**Builder:** {agent} ({AGENTS[agent]['runtime']}, {AGENTS[agent]['model']})\n\n"
            f"{res.get('summary', '')}\n\n**How to test:** {res.get('how_to_test', '')}")
    if pr:
        gh("pr", "edit", str(pr["number"]), "--body", body)
        relabel("pr", pr["number"], remove=["review:approved", "review:changes-requested", "test:passed", "test:failed"])
        comment("pr", pr["number"], agent, f"Pushed a fix.\n\n{res.get('summary', '')}")
        prn = pr["number"]
    else:
        url = gh("pr", "create", "--head", f"ticket-{num}", "--base", "main",
                 "--title", f"[{agent}] #{num} {issue['title']}", "--body", body)
        prn = int(url.rstrip("/").split("/")[-1])
    set_status(num, "in-review")
    trace(event="handoff", frm=agent, to="reviewer", ticket=num, pr=prn)


def step_review(issue, s):
    num = issue["number"]
    pr = pr_for(num)
    if not pr:
        set_status(num, "ready"); return
    path = worktree(num)
    diff = gh("pr", "diff", str(pr["number"]))[:60000]
    prompt = (f"Review PR #{pr['number']} against its ticket. Use your delivery skill.\n\n"
              f"## Ticket #{num}: {issue['title']}\n{issue['body']}\n\n"
              f"## Diff\n```diff\n{diff}\n```\n\n"
              f"The branch is checked out at {path}; you may read and run it.\n"
              f"End with one line: RESULT: {{\"verdict\": \"approve\"|\"reject\", \"reason\": \"one sentence\", \"notes\": [\"...\"]}}")
    res, _ = run_agent("reviewer", prompt, path, "review", num)
    if DRY:
        return
    if not res or res.get("verdict") not in ("approve", "reject"):
        trace(event="review_unparseable", ticket=num); return

    notes = "\n".join(f"- {n}" for n in res.get("notes", []))
    if res["verdict"] == "approve":
        comment("pr", pr["number"], "reviewer", f"✅ APPROVED: {res.get('reason', '')}\n\n{notes}")
        relabel("pr", pr["number"], add=["review:approved"], remove=["review:changes-requested"])
        set_status(num, "in-test")
        trace(event="handoff", frm="reviewer", to="tester", ticket=num, pr=pr["number"])
    else:
        comment("pr", pr["number"], "reviewer", f"❌ REJECTED: {res.get('reason', '')}\n\n{notes}")
        relabel("pr", pr["number"], add=["review:changes-requested"], remove=["review:approved"])
        set_status(num, "changes-requested")
        trace(event="rejected", by="reviewer", ticket=num, pr=pr["number"], reason=res.get("reason"))
        bump(s, num, res.get("reason", ""))


def step_test(issue, s):
    num = issue["number"]
    pr = pr_for(num)
    if not pr:
        set_status(num, "ready"); return
    path = worktree(num)
    prompt = (f"Test PR #{pr['number']} for ticket #{num}: {issue['title']}\n\n{issue['body']}\n\n"
              f"Code is checked out at {path}. Follow the test protocol in AGENTS.md. "
              f"Use a scratch data dir under {path}/.testdata, never the live data.\n"
              f"End with one line: RESULT: {{\"verdict\": \"pass\"|\"fail\", \"evidence\": \"commands + key output\", "
              f"\"bug\": {{\"title\": \"...\", \"body\": \"steps, expected, actual\"}} }}")
    res, _ = run_agent("tester", prompt, path, "test", num)
    if DRY:
        return
    if not res or res.get("verdict") not in ("pass", "fail"):
        trace(event="test_unparseable", ticket=num); return

    if res["verdict"] == "pass":
        comment("pr", pr["number"], "tester", f"✅ TESTS PASS\n\n```\n{res.get('evidence', '')[:3000]}\n```")
        relabel("pr", pr["number"], add=["test:passed"], remove=["test:failed"])
        set_status(num, "ready-to-merge")
        trace(event="handoff", frm="tester", to="human-merge", ticket=num, pr=pr["number"])
    else:
        bug = res.get("bug") or {}
        body = (f"Found while testing PR #{pr['number']} (ticket #{num}).\n\n{bug.get('body', '')}\n\n"
                f"**Evidence**\n```\n{res.get('evidence', '')[:3000]}\n```")
        url = gh("issue", "create", "--title", f"[bug] {bug.get('title', 'test failure on #' + str(num))}",
                 "--body", body, "--label", "type:bug", "--label", "needs-triage")
        bug_n = int(url.rstrip("/").split("/")[-1])
        s.setdefault("bugs", {}).setdefault(str(num), []).append(bug_n)
        comment("pr", pr["number"], "tester", f"❌ TESTS FAIL → opened #{bug_n}\n\n```\n{res.get('evidence', '')[:2000]}\n```")
        relabel("pr", pr["number"], add=["test:failed"], remove=["test:passed"])
        set_status(num, "changes-requested")
        trace(event="rejected", by="tester", ticket=num, pr=pr["number"], bug=bug_n)
        bump(s, num, f"test failure #{bug_n}")


def step_plan(s):
    brief = (ROOT / "briefs" / "product-brief.md").read_text()
    builders = ", ".join(BUILDERS)
    prompt = (f"{brief}\n\n---\nSplit this into 6-8 tickets for the team. Use your delivery skill for the ticket format.\n"
              f"Assignable agents: {builders}. Order them so dependencies come first.\n"
              f"End with one line: RESULT: {{\"tickets\": [{{\"key\": \"T1\", \"title\": \"...\", \"agent\": \"builder-ingest\", "
              f"\"depends_on\": [], \"body\": \"goal, acceptance criteria as a checklist, out of scope\"}}]}}")
    res, _ = run_agent("orchestrator", prompt, ROOT, "planning")
    if DRY or not res or not res.get("tickets"):
        return
    keymap = {}
    for t in res["tickets"]:
        deps = [keymap[d] for d in t.get("depends_on", []) if d in keymap]
        agent = t.get("agent") if t.get("agent") in BUILDERS else "builder-ingest"
        body = t["body"] + (f"\n\nDepends on: {', '.join('#' + str(d) for d in deps)}" if deps else "")
        url = gh("issue", "create", "--title", t["title"], "--body", body,
                 "--label", f"agent:{agent}", "--label", "status:backlog" if deps else "status:ready",
                 "--label", "planned")
        keymap[t["key"]] = int(url.rstrip("/").split("/")[-1])
        trace(event="ticket_created", by="orchestrator", ticket=keymap[t["key"]], to=agent, title=t["title"])
    s["planned"] = True


def step_triage(bug, s):
    open_t = issues("planned")
    board = "\n".join(f"#{i['number']} [{','.join(sorted(labels_of(i)))}] {i['title']}" for i in open_t)
    prompt = (f"A bug came in. Decide what happens to it. Use your delivery skill.\n\n"
              f"## #{bug['number']} {bug['title']}\n{bug['body']}\n\n## Open board\n{board}\n\n"
              f"End with one line: RESULT: {{\"action\": \"attach\"|\"new\"|\"close\", \"ticket\": <n if attach>, "
              f"\"agent\": \"<builder if new>\", \"title\": \"...\", \"body\": \"...\", \"reason\": \"...\"}}")
    res, _ = run_agent("orchestrator", prompt, ROOT, "planning", bug["number"])
    if DRY or not res:
        return
    n = bug["number"]
    if res.get("action") == "attach":
        comment("issue", n, "orchestrator", f"Being fixed under #{res['ticket']}: {res.get('reason', '')}")
        relabel("issue", n, add=["triaged"], remove=["needs-triage"])
    elif res.get("action") == "new":
        agent = res.get("agent") if res.get("agent") in BUILDERS else "builder-ingest"
        comment("issue", n, "orchestrator", f"Re-queued to {agent}: {res.get('reason', '')}")
        relabel("issue", n, add=["triaged", "planned", f"agent:{agent}", "status:ready"], remove=["needs-triage"])
    else:
        comment("issue", n, "orchestrator", f"Closing: {res.get('reason', '')}")
        gh("issue", "close", str(n))
    trace(event="triaged", by="orchestrator", ticket=n, action=res.get("action"), into=res.get("ticket"))


def promote_backlog():
    closed = {i["number"] for i in issues(state_="closed")}
    for i in issues("status:backlog"):
        deps = [int(d) for d in re.findall(r"#(\d+)", (re.search(r"Depends on:(.*)", i["body"] or "") or [None, ""])[1])]
        if all(d in closed for d in deps):
            set_status(i["number"], "ready")
            trace(event="unblocked", ticket=i["number"], deps=deps)


def tick():
    s = state()
    promote_backlog()
    order = [
        ("status:in-review", step_review),
        ("status:in-test", step_test),
    ]
    for label, fn in order:
        for i in issues(label):
            fn(i, s); save_state(s); return True
    for label in ("status:changes-requested", "status:ready"):
        for i in sorted(issues(label), key=lambda x: x["number"]):
            if owner(i) in BUILDERS:
                step_build(i, s); save_state(s); return True
    for b in issues("needs-triage"):
        step_triage(b, s); save_state(s); return True
    if not s.get("planned") and not issues("planned", state_="all"):
        step_plan(s); save_state(s); return True
    return False


if __name__ == "__main__":
    if not REPO:
        sys.exit("GH_REPO not set")
    lock = open(LOGS / ".lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit(0)  # previous tick still running, ollama free tier = 1 concurrent call
    if "--loop" in sys.argv:
        while tick():
            pass
    else:
        tick() or print("idle")
