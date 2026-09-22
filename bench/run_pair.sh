#!/usr/bin/env bash
# Baseline and best, side by side (at the same time), on ONE task list, with full per-attempt evidence.
#
#   MODEL=deepseek/deepseek-v4.1-flash TASKS_FILE=ada/runs/deepseek-v4.1-flash/tasks.set40.txt \
#   EVIDENCE_DIR=ada/runs/deepseek-v4.1-flash/r1 bash bench/run_pair.sh
#
# Required env : MODEL  TASKS_FILE  EVIDENCE_DIR          (there is no default model: it must be named)
# Optional env : CONC=3            tasks at once PER ARM (both arms run together, so total load = 2 x CONC)
#                PROVIDER_IGNORE   comma list added as provider.ignore on every request (default StreamLake, "" = none)
#                COMPARE_TO=<dir>  an earlier run's evidence dir; adds a model-vs-code table at the end
#                KEY_FILE          .env file holding the key (default: OPENROUTER_API_KEY in /home/azureuser/GLM5_2/.env,
#                                  or ANTHROPIC_API_KEY in ada/.env when DIRECT=1)
#                DIRECT=1          talk straight to https://api.anthropic.com with ANTHROPIC_API_KEY: no proxy,
#                                  no provider setting, cost from CLI usage x list prices (see bench/haiku_summary.py)
#                PROXY_PORT_BASE=8765 (baseline) and +1 (best)
#                DRY_RUN=1  preflight only
# When it finishes, <EVIDENCE_DIR>/summary.md holds the results. Progress: bash bench/pair_status.sh <EVIDENCE_DIR>
set -uo pipefail
: "${MODEL:?set MODEL, e.g. deepseek/deepseek-v4.1-flash}" "${TASKS_FILE:?set TASKS_FILE}" "${EVIDENCE_DIR:?set EVIDENCE_DIR}"
ROOT=/home/azureuser/adaAgent; B=$ROOT/bench; H=$B/harness
CONC=${CONC:-3}; SEED=20260907; PORT0=${PROXY_PORT_BASE:-8765}; IGNORE=${PROVIDER_IGNORE-StreamLake}
DIRECT=${DIRECT:-0}
if [ "$DIRECT" = 1 ]; then KEY_FILE=${KEY_FILE:-$ROOT/ada/.env}; IGNORE=""
else KEY_FILE=${KEY_FILE:-/home/azureuser/GLM5_2/.env}; fi
TASKS_FILE=$(realpath "$TASKS_FILE"); mkdir -p "$EVIDENCE_DIR"; EV=$(realpath "$EVIDENCE_DIR")
[ -s "$TASKS_FILE" ] || { echo "no tasks in $TASKS_FILE"; exit 1; }; NTASKS=$(grep -c . "$TASKS_FILE")
TS=$(date -u +%Y%m%dT%H%MZ); TAG=$(echo "$MODEL" | tr '/.' '--')
ARMS=(baseline best)
declare -A WS WANT_HEAD WANT_TREE BASE PORT
WS[baseline]=$H/worktrees/ada-baseline; WANT_HEAD[baseline]=05c243e; WANT_TREE[baseline]=7c88c8270e3b; BASE[baseline]=df0c537  # df0c537 + pass-through shim
WS[best]=$H/worktrees/ada-best;         WANT_HEAD[best]=5f4c5c0;     WANT_TREE[best]=dab704de524a;     BASE[best]=5f4c5c0
PORT[baseline]=$PORT0; PORT[best]=$((PORT0+1))
OURS='name=^setupbench-ada-'
STATUS=$EV/run.STATUS

pgrep -f 'python[0-9.]* [^ ]*setupbench_ada_domain_eval[.]py' >/dev/null && { echo "REFUSING: an eval is already running"; exit 1; }
[ -n "$(docker ps -aq --filter "$OURS")" ] && { echo "REFUSING: setupbench-ada containers are up"; exit 1; }
for a in "${ARMS[@]}"; do
  if [ -n "$(ls -A "$EV/$a" 2>/dev/null)" ]; then echo "REFUSING: $EV/$a already has content (use a new EVIDENCE_DIR)"; exit 1; fi
  (ss -ltn | grep -q ":${PORT[$a]} ") && { echo "REFUSING: port ${PORT[$a]} is busy"; exit 1; }
done

# key: read only the key from the file, never print it
if [ "$DIRECT" = 1 ]; then
  KEY=$(grep -E '^ANTHROPIC_API_KEY=' "$KEY_FILE" | head -1 | cut -d= -f2- | tr -d "\"' ")
  [[ $KEY == sk-ant-* ]] || { echo "no Anthropic key in $KEY_FILE"; exit 1; }
  export ANTHROPIC_API_KEY=$KEY ANTHROPIC_AUTH_TOKEN=$KEY; unset KEY
  export ADA_EVAL_BASE_URL=https://api.anthropic.com ADA_EVAL_DIRECT=1
else
  KEY=$(grep -E '^OPENROUTER_API_KEY=' "$KEY_FILE" | head -1 | cut -d= -f2- | tr -d "\"' ")
  [[ $KEY == sk-or-* ]] || { echo "no OpenRouter key in $KEY_FILE"; exit 1; }
  export OPENROUTER_API_KEY=$KEY ANTHROPIC_AUTH_TOKEN=$KEY; unset KEY
fi

ok=1
for a in "${ARMS[@]}"; do
  ws=${WS[$a]}; head=$(git -C "$ws" rev-parse HEAD); tree=$(git -C "$ws" rev-parse --short=12 HEAD:agent); dirty=$(git -C "$ws" status --porcelain -- agent)
  if [[ $head == ${WANT_HEAD[$a]}* && $tree == ${WANT_TREE[$a]} && -z $dirty ]]; then echo "PREFLIGHT OK   $a ${head:0:7} agent tree $tree clean"
  else echo "PREFLIGHT FAIL $a head=${head:0:7} tree=$tree want=${WANT_HEAD[$a]}/${WANT_TREE[$a]} dirty=[$dirty]"; ok=0; fi
  changed=$(git -C "$ws" diff --name-only "${BASE[$a]}" HEAD | tr '\n' ' ')  # only the baseline's pass-through shim may differ from its base
  if [ $a = baseline ] && [ "$changed" != "agent/system-guidance.ts " ]; then echo "PREFLIGHT FAIL baseline differs from ${BASE[$a]} by: $changed"; ok=0
  elif [ $a = best ] && [ -n "$changed" ]; then echo "PREFLIGHT FAIL best differs from ${BASE[$a]} by: $changed"; ok=0
  else echo "PREFLIGHT OK   $a diff vs ${BASE[$a]}: ${changed:-none}"; fi
  ( cd "$H" && python3 -c "
from pathlib import Path
from setupbench_ada_domain_eval import enforce_mutation_boundary as e
e(Path('$ws').resolve())" ) || { echo "PREFLIGHT FAIL mutation boundary $a"; ok=0; }
done
grep -q '(process.env.ADA_TIME_HINTS ?? "0")' "${WS[best]}/agent/claude/agent.ts" && echo "PREFLIGHT OK   best: time hints default off" || { echo "PREFLIGHT FAIL best has time hints on"; ok=0; }
if [ "$DIRECT" = 1 ]; then
python3 - "$MODEL" "$EV/pricing_snapshot.json" <<'PY' || ok=0
import json, sys, time, pathlib
model, out = sys.argv[1], pathlib.Path(sys.argv[2])
if not out.exists():
    out.write_text(json.dumps({"fetched_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": "https://platform.claude.com/docs/en/about-claude/pricing",
        "model": model, "usd_per_mtok": {"input": 1.0, "output": 5.0, "cache_write_5m": 1.25, "cache_read": 0.10}}, indent=2) + "\n")
print("PREFLIGHT OK   Anthropic list-price snapshot saved:", model)
PY
else
python3 - "$MODEL" "$EV/pricing_snapshot.json" <<'PY' || ok=0
import json, sys, urllib.request, pathlib, time
model, out = sys.argv[1], pathlib.Path(sys.argv[2])
if not out.exists():
    data = json.load(urllib.request.urlopen("https://openrouter.ai/api/v1/models", timeout=30))["data"]
    hit = [m for m in data if m["id"] == model]
    if not hit: sys.exit(f"PREFLIGHT FAIL model {model} not listed on OpenRouter")
    out.write_text(json.dumps({"fetched_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "model": hit[0]}, indent=2) + "\n")
print("PREFLIGHT OK   model listed on OpenRouter, pricing snapshot saved:", model)
PY
fi
key_usage () { python3 - <<'PY'
import json, os, time, urllib.request
r = urllib.request.Request("https://openrouter.ai/api/v1/key", headers={"Authorization": "Bearer " + os.environ["OPENROUTER_API_KEY"]})
d = json.load(urllib.request.urlopen(r, timeout=30))["data"]
print(json.dumps({"at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **{k: d.get(k) for k in ("usage", "usage_daily", "limit", "limit_remaining")}}))
PY
}
usage_of () { python3 -c 'import sys,json;print(json.load(sys.stdin)["usage"])'; }
settled_key_usage () { local a b; a=$(key_usage); for _ in $(seq 12); do sleep 10; b=$(key_usage); [ "$(echo "$a" | usage_of)" = "$(echo "$b" | usage_of)" ] && break; a=$b; done; echo "$b"; }
if [ "$DIRECT" = 1 ]; then
python3 - <<'PY' || { echo "PREFLIGHT FAIL key check"; ok=0; }
import json, os, sys, urllib.request
req = urllib.request.Request("https://api.anthropic.com/v1/models?limit=100",
    headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"})
ids = [m["id"] for m in json.load(urllib.request.urlopen(req, timeout=30))["data"]]
model = os.environ["MODEL"]
if model not in ids and not model.startswith("claude-haiku-4-5"):
    sys.exit(f"PREFLIGHT FAIL model {model} not listed on the Anthropic API")
print("PREFLIGHT OK   Anthropic key valid; model available:", model)
PY
KU0=null
else
KU0=$(settled_key_usage) && echo "PREFLIGHT OK   key valid" || { echo "PREFLIGHT FAIL key check"; ok=0; }
fi
echo "PREFLIGHT OK   $NTASKS tasks in $TASKS_FILE"
[ $ok = 1 ] || exit 1
[ "${DRY_RUN:-0}" = 1 ] && { echo "DRY_RUN: preflight passed, nothing launched"; exit 0; }

for a in "${ARMS[@]}"; do mkdir -p "$EV/$a"; git -C "${WS[$a]}" diff "${BASE[$a]}" HEAD > "$EV/$a.build.patch"; done
cp "$TASKS_FILE" "$EV/tasks.txt"
echo "=== preparing task cache + images (cached ones are quick) ==="
( cd "$H" && python3 setupbench_ada_domain_eval.py --tasks-file "$TASKS_FILE" --prepare-only | tail -1 ) || exit 1

echo "RUNNING pair-$TAG-$TS model=$MODEL tasks=$NTASKS conc_per_arm=$CONC started=$(date -u)" > "$STATUS"
# resource guard + key-counter log (one for both arms); it aborts the whole run if the machine runs short
( n=0; while true; do
    n=$((n+1)); [ $((n % 3)) = 1 ] && [ "$DIRECT" != 1 ] && echo "$(date -u +%T) $(key_usage 2>/dev/null)" >> "$EV/keyusage.log"
    A=$(free -m | awk 'NR==2{print $7}'); W=$(free -m | awk 'NR==3{print $3}'); D=$(df -BG --output=avail / | tail -1 | tr -dc 0-9)
    echo "$(date -u +%H:%M:%S) mem_avail=${A}M swap_used=${W}M disk_free=${D}G ours=$(docker ps -q --filter "$OURS" | wc -l)" >> "$EV/resources.log"
    if [ "$A" -lt 1200 ] || [ "$W" -gt 6144 ] || [ "$D" -lt 5 ]; then
      echo "ABORTED-resource-guard avail=${A}M swap=${W}M disk=${D}G $(date -u)" > "$STATUS"
      pkill -f 'python[0-9.]* [^ ]*setupbench_ada_domain_eval[.]py'; docker rm -f $(docker ps -aq --filter "$OURS") 2>/dev/null; exit 1
    fi; sleep 20; done ) & GUARD=$!

# one proxy per arm in OpenRouter mode (adds provider.ignore and logs every API call);
# in DIRECT mode the containers talk straight to https://api.anthropic.com, no proxy
GW=$(docker network inspect bridge -f '{{(index .IPAM.Config 0).Gateway}}')
PROXIES=()
if [ "$DIRECT" = 1 ]; then
  echo "direct mode: no proxies; containers talk to https://api.anthropic.com"
else
for a in "${ARMS[@]}"; do
  python3 "$H/openrouter_proxy.py" serve --port "${PORT[$a]}" --log-dir "$EV/proxy.$a" --ignore "$IGNORE" > "$EV/proxy.$a.log" 2>&1 & PROXIES+=($!)
done
fi
trap 'kill $GUARD "${PROXIES[@]}" 2>/dev/null' EXIT
sleep 1
if [ "$DIRECT" != 1 ]; then
for a in "${ARMS[@]}"; do
  [ "$(curl -s -o /dev/null -w '%{http_code}' -X POST "http://127.0.0.1:${PORT[$a]}/api/v1/messages" -d '{}' -H 'content-type: application/json' -H 'x-api-key: x')" != 000 ] \
    || { echo "REFUSING: proxy for $a did not start"; kill $GUARD 2>/dev/null; exit 1; }
  rm -f "$EV/proxy.$a/calls.jsonl"
done
echo "proxies up on $GW:${PORT[baseline]} and $GW:${PORT[best]}, provider.ignore=[$IGNORE]"
fi

T0=$(date -u +%Y-%m-%dT%H:%M:%SZ); LOAD0=$(cat /proc/loadavg)
declare -A RUNID
for a in "${ARMS[@]}"; do
  RUNID[$a]=pair-$TAG-$TS-$a
  ( cd "$H" && AUTORESEARCH_RUN_ID=${RUNID[$a]} AUTORESEARCH_EXPERIMENT_NUMBER=0 ADA_WORKSPACE=$ROOT/ada \
      ADA_EVAL_MODEL=$MODEL ADA_EVAL_ARM=$a ADA_EVAL_EVIDENCE_DIR=$EV ADA_EVAL_RUNNER=$H/setupbench_ada_runner_ts.ts \
      ADA_EVAL_BASE_URL=http://$GW:${PORT[$a]}/api \
      python3 setupbench_ada_domain_eval.py --tasks-file "$TASKS_FILE" --workspace "${WS[$a]}" --concurrency "$CONC" --seed $SEED \
      > "$EV/driver.$a.log" 2>&1; echo $? > "$EV/$a.exit" ) &
done
# both arms run at the same time; each writes <arm>.exit when its eval process ends
until [ -e "$EV/baseline.exit" ] && [ -e "$EV/best.exit" ]; do sleep 5; done
T1=$(date -u +%Y-%m-%dT%H:%M:%SZ); kill $GUARD 2>/dev/null
if [ "$DIRECT" = 1 ]; then
  echo "eval finished; no proxy calls to drain (direct API)" >> "$STATUS"
  KU1=null
else
echo "eval finished; letting in-flight calls drain, then collecting costs..." >> "$STATUS"
DRAIN=${PROXY_DRAIN_SECONDS:-60}; sleep "$DRAIN"; kill "${PROXIES[@]}" 2>/dev/null
for a in "${ARMS[@]}"; do python3 "$H/openrouter_proxy.py" fetch "$EV/proxy.$a" | tee -a "$EV/driver.$a.log"; done
KU1=$(settled_key_usage || echo '{}')
fi
for a in "${ARMS[@]}"; do cp "${WS[$a]}/.autoresearch/diagnostics/${RUNID[$a]}/0.json" "$EV/$a/diagnostics.json" 2>/dev/null || echo "NOTE: no diagnostics.json for $a"; done

for a in "${ARMS[@]}"; do
if [ "$DIRECT" = 1 ]; then
python3 - "$EV/PROTOCOL.$a.json" <<PY
import hashlib, json, os, sys, pathlib
h = pathlib.Path("$H"); sha = lambda p: hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
json.dump({
  "model": "$MODEL", "arm": "$a", "run_id": "${RUNID[$a]}", "exit_code": int(open("$EV/$a.exit").read()),
  "workspace_commit": "$(git -C "${WS[$a]}" rev-parse HEAD)", "base_commit": "${BASE[$a]}", "build_patch": "$a.build.patch",
  "agent_tree": "$(git -C "${WS[$a]}" rev-parse --short=12 HEAD:agent)", "started_utc": "$T0", "finished_utc": "$T1",
  "concurrency": $CONC, "arms_run_at_the_same_time": True, "seed": $SEED, "task_timeout_seconds": 480, "grader_timeout_seconds": 600,
  "tasks_file": "tasks.txt", "tasks": $NTASKS, "provider_ignore": [],
  "proxy": "none (direct api.anthropic.com)", "direct": True,
  "runner": "setupbench_ada_runner_ts.ts", "runner_sha256": sha(h / "setupbench_ada_runner_ts.ts"),
  "evaluator_sha256": sha(h / "setupbench_ada_domain_eval.py"), "harness_sha256": sha(h / "setupbench_ada_eval.py"),
  "pricing_snapshot": "pricing_snapshot.json",
}, open(sys.argv[1], "w"), indent=2); open(sys.argv[1], "a").write("\n")
PY
else
python3 - "$EV/PROTOCOL.$a.json" <<PY
import hashlib, json, os, sys, pathlib
h = pathlib.Path("$H"); sha = lambda p: hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
json.dump({
  "model": "$MODEL", "arm": "$a", "run_id": "${RUNID[$a]}", "exit_code": int(open("$EV/$a.exit").read()),
  "workspace_commit": "$(git -C "${WS[$a]}" rev-parse HEAD)", "base_commit": "${BASE[$a]}", "build_patch": "$a.build.patch",
  "agent_tree": "$(git -C "${WS[$a]}" rev-parse --short=12 HEAD:agent)", "started_utc": "$T0", "finished_utc": "$T1",
  "concurrency": $CONC, "arms_run_at_the_same_time": True, "seed": $SEED, "task_timeout_seconds": 480, "grader_timeout_seconds": 600,
  "tasks_file": "tasks.txt", "tasks": $NTASKS, "provider_ignore": [p for p in "$IGNORE".split(",") if p],
  "proxy": "openrouter_proxy.py", "proxy_sha256": sha(h / "openrouter_proxy.py"), "proxy_drain_seconds": $DRAIN,
  "runner": "setupbench_ada_runner_ts.ts", "runner_sha256": sha(h / "setupbench_ada_runner_ts.ts"),
  "evaluator_sha256": sha(h / "setupbench_ada_domain_eval.py"), "harness_sha256": sha(h / "setupbench_ada_eval.py"),
  "pricing_snapshot": "pricing_snapshot.json",
}, open(sys.argv[1], "w"), indent=2); open(sys.argv[1], "a").write("\n")
PY
fi
done
python3 - "$EV/PROTOCOL.run.json" <<PY
import json, os, sys
if "$DIRECT" == "1":
    ku_note = "direct Anthropic key: no usage-counter endpoint; cost comes from CLI token usage x list prices"
    ku_before, ku_after = None, None
else:
    ku_note = "one key shared by both arms and possibly by other users: the counter is a rough cross-check only; cost comes from proxy.<arm>/generations.jsonl"
    ku_before, ku_after = json.loads('''$KU0'''), json.loads('''$KU1''')
json.dump({"model": "$MODEL", "tag": "$TAG", "started_utc": "$T0", "finished_utc": "$T1", "cpus": os.cpu_count(),
  "loadavg_start": "$LOAD0", "loadavg_end": open("/proc/loadavg").read().strip(),
  "direct": "$DIRECT" == "1",
  "openrouter_key_usage_before": ku_before, "openrouter_key_usage_after": ku_after,
  "note": ku_note},
  open(sys.argv[1], "w"), indent=2); open(sys.argv[1], "a").write("\n")
PY

# post-run checks, appended to the status file
if [ "$DIRECT" = 1 ]; then
for a in "${ARMS[@]}"; do
python3 - "$a" "$EV/$a" <<'PY' | tee -a "$STATUS"
import collections, glob, json, sys
rs = [json.load(open(p)) for p in glob.glob(sys.argv[2] + "/*/result.json")]
notrace = [r["task_id"] for r in rs if not r.get("turns_from_trace") and not r["timed_out"]]
models = dict(collections.Counter(m for r in rs for m in r.get("models_seen", [])))
nousage = [r["task_id"] for r in rs if not r.get("terminal_result") and not r["timed_out"]]
print(f"[{sys.argv[1]}] attempts {len(rs)} | models billed {models} | attempts with no trace turns {len(notrace)} {notrace[:5]} | finished with no usage record {len(nousage)} {nousage[:5]}")
PY
done
else
for a in "${ARMS[@]}"; do
python3 - "$EV/proxy.$a/generations.jsonl" "$IGNORE" "$a" "$EV/$a" <<'PY' | tee -a "$STATUS"
import collections, glob, json, sys
rows = [json.loads(l) for l in open(sys.argv[1])]; ign = {p for p in sys.argv[2].split(",") if p}
msgs = [r for r in rows if r.get("path", "").split("?")[0].endswith("/v1/messages")]
inj = sum(1 for r in msgs if r.get("provider_ignore"))
prov = collections.Counter((r.get("generation") or {}).get("provider_name") for r in msgs)
empty = sum(1 for r in msgs if r.get("tools") and r.get("blocks") == [] and r.get("status") == 200 and not r.get("client_disconnected"))
notrace = [p.split("/")[-2] for p in glob.glob(sys.argv[4] + "/*/result.json") if not json.load(open(p)).get("turns_from_trace") and not json.load(open(p))["timed_out"]]
print(f"[{sys.argv[3]}] model calls {len(msgs)} | provider.ignore injected {inj}" + ("" if not ign or inj == len(msgs) else "  <<< INJECTION FAILED") +
      f" | from ignored provider {sum(n for p, n in prov.items() if p in ign)} | empty replies {empty} | attempts with no trace turns {len(notrace)} {notrace[:5]}")
PY
done
fi
if [ "$DIRECT" = 1 ]; then
if grep -rlE 'sk-ant-[A-Za-z0-9_-]{16,}' "$EV" >/dev/null 2>&1 || grep -rlF "$ANTHROPIC_API_KEY" "$EV" >/dev/null 2>&1; then
  echo "SECRET-SCAN FAIL: a key appears in $EV" | tee -a "$STATUS"; exit 3; fi
else
if grep -rlE 'sk-or-[A-Za-z0-9_-]{16,}' "$EV" >/dev/null 2>&1 || grep -rlF "$OPENROUTER_API_KEY" "$EV" >/dev/null 2>&1; then
  echo "SECRET-SCAN FAIL: a key appears in $EV" | tee -a "$STATUS"; exit 3; fi
fi
if [ "$DIRECT" = 1 ]; then SUMSCRIPT=haiku_summary.py; else SUMSCRIPT=deepseek_summary.py; fi
python3 "$B/$SUMSCRIPT" "$EV" > "$EV/summary.stdout.txt" 2>&1 || echo "NOTE: summary script failed, see summary.stdout.txt" | tee -a "$STATUS"
[ -n "${COMPARE_TO:-}" ] && { python3 "$B/compare_runs.py" "$COMPARE_TO" "$EV" > "$EV/comparison.stdout.txt" 2>&1 || echo "NOTE: compare script failed, see comparison.stdout.txt" | tee -a "$STATUS"; }
echo "COMPLETE pair-$TAG-$TS exit baseline=$(cat "$EV/baseline.exit") best=$(cat "$EV/best.exit") finished=$T1 secret-scan=clean results=$EV/summary.md" | tee "$STATUS"
