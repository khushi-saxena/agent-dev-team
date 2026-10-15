st () 
{ 
    echo "=== last 6 events (PDT):";
    tail -6 ~/briefing/logs/trace.jsonl | python3 -c "
import sys,json,datetime
for l in sys.stdin:
    e=json.loads(l); t=datetime.datetime.fromisoformat(e['ts'])-datetime.timedelta(hours=7)
    r=e.get('result'); v=r.get('verdict') or r.get('status') if isinstance(r,dict) else (r or '')
    print(t.strftime('%H:%M'), e['event'], e.get('agent') or e.get('to') or e.get('by') or '', '#'+str(e.get('ticket','')), v, (e.get('reason') or '')[:90])";
    echo "=== ready to merge:";
    gh issue list --label status:ready-to-merge --json number,title --jq '.[]|"#\(.number) \(.title)"';
    echo "=== blocked:";
    gh issue list --label status:blocked --json number,title --jq '.[]|"#\(.number) \(.title)"';
    echo "=== agent running now:";
    ps -eo etime,cmd | grep --color=auto -E "openclaw agent|hermes -p" | grep --color=auto -v grep | sed -E 's/--message .*//' | cut -c1-110
}
