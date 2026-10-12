#!/usr/bin/env bash
# creates the labels the dispatcher uses as the ticket state machine
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a

mk() { gh label create "$1" --color "$2" --description "$3" --repo "$GH_REPO" --force >/dev/null; echo "  $1"; }

mk status:backlog            cccccc "waiting on dependencies"
mk status:ready              0e8a16 "builder can pick it up"
mk status:in-progress        fbca04 "builder working"
mk status:in-review          1d76db "reviewer's turn"
mk status:in-test            5319e7 "tester's turn"
mk status:changes-requested  d93f0b "sent back to builder"
mk status:ready-to-merge     0e8a16 "human merges"
mk status:blocked            b60205 "hit retry cap, needs a human"

mk agent:orchestrator   000000 "hermes, strong model"
mk agent:reviewer       000000 "hermes, strong model"
mk agent:builder-ingest 444444 "openclaw, cheap model"
mk agent:builder-page   444444 "openclaw, cheap model"
mk agent:builder-ops    444444 "openclaw, cheap model"
mk agent:tester         444444 "openclaw, cheap model"

mk review:approved            0e8a16 "reviewer gate passed"
mk review:changes-requested   d93f0b "reviewer gate failed"
mk test:passed                0e8a16 "test gate passed"
mk test:failed                d93f0b "test gate failed"

mk planned       c5def5 "created by the orchestrator"
mk type:bug      d73a4a "opened by the tester"
mk needs-triage  fef2c0 "orchestrator decides"
mk triaged       c5def5 ""
