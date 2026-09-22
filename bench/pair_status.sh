#!/usr/bin/env bash
# Where is a pair run (bench/run_pair.sh)? No Claude needed.
#   bash bench/pair_status.sh [EVIDENCE_DIR]        (default: the newest run under ada/runs/*/*)
# Shows: state, live processes, containers, machine load, progress per arm, API health, key counter, last finished tasks.
EV=${1:-$(ls -dt /home/azureuser/adaAgent/ada/runs/*/r*/ 2>/dev/null | head -1)}
EV=${EV%/}; [ -f "$EV/run.STATUS" ] || { echo "no run.STATUS in '$EV' (pass the evidence dir, e.g. ada/runs/deepseek-v4.1-flash/r1)"; exit 1; }
echo "== $EV"; echo "state :"; head -6 "$EV/run.STATUS" | cut -c1-220 | sed 's/^/        /'   # 1st line RUNNING/COMPLETE/ABORTED; later lines = post-run steps
echo "procs : evals=$(pgrep -fc 'setupbench_ada_domain_eval[.]py') proxies=$(pgrep -fc 'openrouter_proxy[.]py serve') driver=$(pgrep -fc 'bench/run_pair[.]sh')   containers up: $(docker ps -q --filter name=setupbench-ada | wc -l)"
echo "machine: $(tail -1 "$EV/resources.log" 2>/dev/null)   load: $(cut -d' ' -f1-3 /proc/loadavg)"
python3 - "$EV" <<'PY'
import collections, glob, json, os, sys, time
ev = sys.argv[1]
total = sum(1 for l in open(f"{ev}/tasks.txt") if l.strip()) if os.path.exists(f"{ev}/tasks.txt") else 0
t0 = None
try: t0 = os.path.getmtime(f"{ev}/tasks.txt")
except OSError: pass
for arm in ("baseline", "best"):
    rs = []
    for f in glob.glob(f"{ev}/{arm}/*/result.json"):
        try: rs.append((os.path.getmtime(f), json.load(open(f))))
        except Exception: pass
    rs.sort(key=lambda x: x[0])
    p = sum(1 for _, r in rs if r["passed"]); to = sum(1 for _, r in rs if r["timed_out"]); inv = sum(1 for _, r in rs if not r["valid"])
    nt = sum(1 for _, r in rs if not r.get("turns_from_trace") and not r["timed_out"])
    try: calls = [json.loads(l) for l in open(f"{ev}/proxy.{arm}/calls.jsonl")]
    except FileNotFoundError: calls = []
    bad = dict(collections.Counter(c.get("status") for c in calls if c.get("status") != 200 and "count_tokens" not in c.get("path", "")))
    empty = sum(1 for c in calls if c.get("tools") and c.get("blocks") == [] and not c.get("client_disconnected"))
    eta = ""
    if t0 and rs and total:
        el = time.time() - t0; eta = f" | elapsed {el/60:.0f} min, rough time left {el/len(rs)*(total-len(rs))/60:.0f} min"
    flag = "   <<< look at this" if (inv or nt or bad) else ""
    print(f"{arm:<9}: {len(rs)}/{total} done | passed {p} | timed out {to} | harness errors {inv} | no-trace {nt} | api calls {len(calls)} bad {bad} empty {empty}{eta}{flag}")
    for _, r in rs[-3:]:
        print(f"           last: {r['task_id']:<42} {'PASS' if r['passed'] else ('TIMEOUT' if r['timed_out'] else 'fail'):<8} {r['duration_seconds']:.0f}s turns {r['turns'] or r.get('turns_from_trace')}")
try:
    k = [l.split(" ", 1)[1] for l in open(f"{ev}/keyusage.log") if " {" in l]
    a, b = json.loads(k[0])["usage"], json.loads(k[-1])["usage"]
    print(f"key counter: +${b-a:.4f} since start (shared key: also counts anyone else's use; real cost is computed at the end)")
except Exception: pass
PY
[ -f "$EV/summary.md" ] && echo "RESULTS READY: $EV/summary.md" || echo "results will appear in $EV/summary.md when the state says COMPLETE"
