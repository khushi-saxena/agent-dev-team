---
name: delivery
description: How tickets move through the team and the format every agent must end with. Read before any ticket work.
---
# Delivery protocol

Tickets are GitHub issues. A dispatcher (plain script, no model) hands you one
ticket at a time and moves the labels based on your RESULT line. You do not
touch labels, push, open PRs or merge. Humans merge.

```
orchestrator ──creates──> status:ready ──> builder ──commit──> PR (status:in-review)
                                              ^                     │
                                              │ reject              v
                         status:changes-requested <──────── reviewer
                                              ^                     │ approve
                                              │ fail + bug issue    v
                                              └────────────────── tester ──pass──> human merge
```

After 3 send-backs a ticket is parked as status:blocked for a human.

## Rules for everyone
- Your final line MUST be `RESULT: {json}` on a single line. No RESULT line = your run is wasted.
- Stay inside the ticket. If you notice something else, mention it in your RESULT summary/notes, don't fix it.
- Never commit secrets, `.env`, or anything under `data/`.
- Be brief. Every token comes out of a small free allowance shared by the whole team.

## Ticket format (orchestrator writes these)
```
**Goal:** one sentence.
**Acceptance criteria**
- [ ] checkable statement
- [ ] checkable statement
**Out of scope:** ...
**Files likely touched:** ...
```
Each ticket fits in one PR a cheap model can write in one go. Acceptance
criteria must be things the tester can check by running a command.
