# Token & model report

OpenClaw rows are measured per call (`openclaw agent --json`). Hermes does not return usage per
oneshot call, so its rows come from `hermes -p <profile> insights` (whole-profile totals).

## Per agent / model / phase

| agent | runtime | model | phase | calls | fresh in | out | cache read | total | secs |
|---|---|---|---|---|---|---|---|---|---|
| builder-ingest | openclaw | gpt-oss:120b | retry | 4 | 0.40M | 0.26M | 20.69M | 21.35M | 2102 |
| builder-ingest | openclaw | gpt-oss:20b | coding | 8 | 0.38M | 0.11M | 2.51M | 3.00M | 2107 |
| builder-ingest | openclaw | gpt-oss:20b | retry | 5 | 0.72M | 61.5k | 0.27M | 1.05M | 1845 |
| builder-ops | openclaw | gpt-oss:20b | coding | 1 | 36.7k | 5.0k | 0.42M | 0.46M | 75 |
| builder-ops | openclaw | gpt-oss:20b | retry | 6 | 0.33M | 48.9k | 3.54M | 3.92M | 1753 |
| builder-page | openclaw | gpt-oss:20b | coding | 5 | 0.22M | 37.6k | 2.22M | 2.48M | 554 |
| builder-page | openclaw | gpt-oss:20b | retry | 3 | 0.26M | 46.4k | 2.06M | 2.37M | 769 |
| tester | openclaw | gpt-oss:20b | test | 14 | 0.46M | 58.7k | 3.25M | 3.77M | 1503 |
| orchestrator | hermes | gpt-oss:120b | planning | 6 | 61.5k | 8.7k | 0.13M | 0.20M | 79 |
| reviewer | hermes | gpt-oss:120b | review | 24 | 0.62M | 0.12M | 12.38M | 13.12M | 1433 |

## By phase

| phase | fresh (in+out) | total incl. cache |
|---|---|---|
| coding | 0.79M | 5.95M |
| planning | 70.2k | 0.20M |
| retry | 2.12M | 28.68M |
| review | 0.74M | 13.12M |
| test | 0.52M | 3.77M |
| **all** | **4.24M** | **51.71M** |

## OpenClaw tokens per ticket

| ticket | calls | retries | total |
|---|---|---|---|
| #17 | 15 | 7 | 23.70M |
| #6 | 11 | 6 | 4.38M |
| #13 | 11 | 2 | 3.44M |
| #3 | 7 | 2 | 1.85M |
| #20 | 8 | 0 | 1.25M |
| #1 | 5 | 0 | 0.98M |
| #21 | 5 | 0 | 0.84M |
| #5 | 3 | 0 | 0.80M |
| #4 | 5 | 1 | 0.76M |
| #2 | 3 | 0 | 0.39M |
| #11 | 1 | 0 | 0.0k |
| #16 | 1 | 0 | 0.0k |

## Flow counts

- agent_done: 76
- auto_commit: 13
- escalated: 6
- handoff: 148
- nudge: 7
- rate_limited: 38
- rejected: 9
- review_unparseable: 6
- test_unparseable: 6
- ticket_created: 6
- triaged: 5
- unblocked: 5

Not in the trace: the three hand-started builder-ingest calls that finished #17
(sessions manual-17a/b/c, run outside the dispatcher).
