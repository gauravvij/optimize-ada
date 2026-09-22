#!/usr/bin/env bash
# One arm of the DeepSeek V4 Flash SetupBench run, with FULL per-attempt evidence.
#
#   bash bench/run_deepseek_v4_flash.sh baseline     # then, only after it finishes:
#   bash bench/run_deepseek_v4_flash.sh best
#
# Env (all optional): CONC=6  REPLICATE=1  TASKS_FILE=<file>  EVIDENCE_DIR=<dir>  DRY_RUN=1  KEY_FILE=<.env path>
#   arms are run one after the other; tasks inside an arm run CONC at a time (same seed => same order for both arms).
#
# Evidence per attempt: <EVIDENCE_DIR>/<arm>/<task>/{trace.jsonl,agent.log,result.json}; per arm: diagnostics.json,
# PROTOCOL.<arm>.json, resources.<arm>.log, driver.<arm>.log. The model is fixed below and asserted; there is no fallback.
set -uo pipefail
MODEL=deepseek/deepseek-v4-flash
ARM=${1:-}
ROOT=/home/azureuser/adaAgent; B=$ROOT/bench; H=$B/harness
case $ARM in
  baseline) WS=$H/worktrees/ada-baseline; WANT_HEAD=05c243e; WANT_TREE=7c88c8270e3b; BASE=df0c537 ;;  # df0c537 + pass-through shim
  best)     WS=$H/worktrees/ada-best;     WANT_HEAD=5f4c5c0; WANT_TREE=dab704de524a; BASE=5f4c5c0 ;;
  *) echo "usage: $0 baseline|best"; exit 2 ;;
esac
CONC=${CONC:-6}; REP=${REPLICATE:-1}; SEED=20260907
PORT=${PROXY_PORT:-8765}; IGNORE=${PROVIDER_IGNORE:-StreamLake}   # StreamLake returns empty completions for Ada's requests
EV=${EVIDENCE_DIR:-$ROOT/ada/runs/deepseek-v4-flash/r$REP}
KEY_FILE=${KEY_FILE:-/home/azureuser/GLM5_2/.env}
if [ -n "${TASKS_FILE:-}" ]; then SUITE=(--tasks-file "$TASKS_FILE"); PREP=(--tasks-file "$TASKS_FILE"); else SUITE=(remaining81); PREP=(remaining81); fi
TS=$(date -u +%Y%m%dT%H%MZ); RUN_ID=deepseek-v4-flash-r$REP-$ARM-$TS
[ "$MODEL" = "deepseek/deepseek-v4-flash" ] || { echo "REFUSING: model must be deepseek/deepseek-v4-flash"; exit 1; }

pgrep -f 'python[0-9.]* [^ ]*setupbench_ada_domain_eval[.]py' >/dev/null && { echo "REFUSING: an eval is already running"; exit 1; }
OURS='name=^setupbench-ada-'
[ -n "$(docker ps -aq --filter "$OURS")" ] && { echo "REFUSING: setupbench-ada containers are up"; exit 1; }
if [ -e "$EV/$ARM" ] && [ -n "$(ls -A "$EV/$ARM" 2>/dev/null)" ]; then echo "REFUSING: $EV/$ARM already has content (move it or set EVIDENCE_DIR)"; exit 1; fi

# key: read only OPENROUTER_API_KEY from the file, never print it
KEY=$(grep -E '^OPENROUTER_API_KEY=' "$KEY_FILE" | head -1 | cut -d= -f2- | tr -d "\"' ")
[[ $KEY == sk-or-* ]] || { echo "no OpenRouter key in $KEY_FILE"; exit 1; }
export OPENROUTER_API_KEY=$KEY ANTHROPIC_AUTH_TOKEN=$KEY; unset KEY

ok=1
head=$(git -C "$WS" rev-parse HEAD); tree=$(git -C "$WS" rev-parse --short=12 HEAD:agent); dirty=$(git -C "$WS" status --porcelain -- agent)
if [[ $head == $WANT_HEAD* && $tree == $WANT_TREE && -z $dirty ]]; then echo "PREFLIGHT OK   $ARM ${head:0:7} agent tree $tree clean"
else echo "PREFLIGHT FAIL $ARM head=${head:0:7} tree=$tree want=$WANT_HEAD/$WANT_TREE dirty=[$dirty]"; ok=0; fi
# the ONLY difference from the base commit may be the baseline's pass-through shim
changed=$(git -C "$WS" diff --name-only $BASE HEAD | tr '\n' ' ')
if [ $ARM = baseline ] && [ "$changed" != "agent/system-guidance.ts " ]; then echo "PREFLIGHT FAIL baseline differs from $BASE by: $changed"; ok=0
elif [ $ARM = best ] && [ -n "$changed" ]; then echo "PREFLIGHT FAIL best differs from $BASE by: $changed"; ok=0
else echo "PREFLIGHT OK   diff vs $BASE: ${changed:-none}"; fi
( cd "$H" && python3 -c "
from pathlib import Path
from setupbench_ada_domain_eval import enforce_mutation_boundary as e
e(Path('$WS').resolve()); print('PREFLIGHT OK   mutation boundary')" ) || ok=0
[ $ARM = best ] && { grep -q '(process.env.ADA_TIME_HINTS ?? "0")' "$WS/agent/claude/agent.ts" && echo "PREFLIGHT OK   time hints default off" || { echo "PREFLIGHT FAIL best build has time hints on"; ok=0; }; }
mkdir -p "$EV"
# model must exist on OpenRouter; snapshot its pricing once
python3 - "$MODEL" "$EV/pricing_snapshot.json" <<'PY' || ok=0
import json, sys, urllib.request, pathlib, time
model, out = sys.argv[1], pathlib.Path(sys.argv[2])
if not out.exists():
    data = json.load(urllib.request.urlopen("https://openrouter.ai/api/v1/models", timeout=30))["data"]
    hit = [m for m in data if m["id"] == model]
    if not hit: sys.exit(f"PREFLIGHT FAIL model {model} not listed on OpenRouter")
    out.write_text(json.dumps({"fetched_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "model": hit[0]}, indent=2) + "\n")
print("PREFLIGHT OK   pricing snapshot for", model)
PY
key_usage () { python3 - <<'PY'
import json, os, time, urllib.request
r = urllib.request.Request("https://openrouter.ai/api/v1/key", headers={"Authorization": "Bearer " + os.environ["OPENROUTER_API_KEY"]})
d = json.load(urllib.request.urlopen(r, timeout=30))["data"]
print(json.dumps({"at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **{k: d.get(k) for k in ("usage", "usage_daily", "limit", "limit_remaining")}}))
PY
}
settled_key_usage () { local a b; a=$(key_usage); for _ in $(seq 12); do sleep 10; b=$(key_usage); [ "$(echo "$a" | python3 -c 'import sys,json;print(json.load(sys.stdin)["usage"])')" = "$(echo "$b" | python3 -c 'import sys,json;print(json.load(sys.stdin)["usage"])')" ] && break; a=$b; done; echo "$b"; }
KU0=$(settled_key_usage) && echo "PREFLIGHT OK   key valid; usage before: $KU0" || { echo "PREFLIGHT FAIL key check"; ok=0; }
[ $ok = 1 ] || exit 1
[ "${DRY_RUN:-0}" = 1 ] && { echo "DRY_RUN: preflight passed, nothing launched"; exit 0; }

mkdir -p "$EV/$ARM"
git -C "$WS" diff $BASE HEAD > "$EV/$ARM.build.patch"
echo "=== preparing task cache + images (cached ones are quick) ==="
( cd "$H" && python3 setupbench_ada_domain_eval.py "${PREP[@]}" --prepare-only | tail -1 ) || exit 1

RES=$EV/resources.$ARM.log; STATUS=$EV/$ARM.STATUS
echo "RUNNING $RUN_ID conc=$CONC started=$(date -u)" > "$STATUS"
( n=0; while true; do
    n=$((n+1)); [ $((n % 3)) = 1 ] && echo "$(date -u +%T) $(key_usage 2>/dev/null)" >> "$EV/keyusage.$ARM.log"
    A=$(free -m | awk 'NR==2{print $7}'); W=$(free -m | awk 'NR==3{print $3}'); D=$(df -BG --output=avail / | tail -1 | tr -dc 0-9)
    echo "$(date -u +%H:%M:%S) mem_avail=${A}M swap_used=${W}M disk_free=${D}G ours=$(docker ps -q --filter "$OURS" | wc -l)" >> "$RES"
    if [ "$A" -lt 1200 ] || [ "$W" -gt 6144 ] || [ "$D" -lt 5 ]; then
      echo "ABORTED-resource-guard avail=${A}M swap=${W}M disk=${D}G $(date -u)" > "$STATUS"
      pkill -f 'python[0-9.]* [^ ]*setupbench_ada_domain_eval[.]py'; docker rm -f $(docker ps -aq --filter "$OURS") 2>/dev/null; exit 1
    fi; sleep 20; done ) & GUARD=$!
trap 'kill $GUARD 2>/dev/null' EXIT

# proxy: injects provider.ignore (Claude Code cannot) and logs one line per API call
GW=$(docker network inspect bridge -f '{{(index .IPAM.Config 0).Gateway}}')
(ss -ltn | grep -q ":$PORT ") && { echo "REFUSING: port $PORT is busy"; kill $GUARD 2>/dev/null; exit 1; }
python3 "$H/openrouter_proxy.py" serve --port "$PORT" --log-dir "$EV/proxy.$ARM" --ignore "$IGNORE" > "$EV/proxy.$ARM.log" 2>&1 & PROXY=$!
trap 'kill $GUARD $PROXY 2>/dev/null' EXIT
sleep 1; kill -0 $PROXY 2>/dev/null && [ "$(curl -s -o /dev/null -w '%{http_code}' -X POST "http://127.0.0.1:$PORT/api/v1/messages" -d '{}' -H 'content-type: application/json' -H 'x-api-key: x')" != 000 ] \
  || { echo "REFUSING: proxy did not start"; kill $GUARD 2>/dev/null; exit 1; }
rm -f "$EV/proxy.$ARM/calls.jsonl"; echo "proxy up on $GW:$PORT, provider.ignore=$IGNORE"

T0=$(date -u +%Y-%m-%dT%H:%M:%SZ); LOAD0=$(cat /proc/loadavg)
( cd "$H" && ADA_EVAL_BASE_URL=http://$GW:$PORT/api AUTORESEARCH_RUN_ID=$RUN_ID AUTORESEARCH_EXPERIMENT_NUMBER=0 ADA_WORKSPACE=$ROOT/ada \
    ADA_EVAL_MODEL=$MODEL ADA_EVAL_ARM=$ARM ADA_EVAL_EVIDENCE_DIR=$EV ADA_EVAL_RUNNER=$H/setupbench_ada_runner_ts.ts \
    python3 setupbench_ada_domain_eval.py "${SUITE[@]}" --workspace "$WS" --concurrency "$CONC" --seed $SEED ) > "$EV/driver.$ARM.log" 2>&1
RC=$?
T1=$(date -u +%Y-%m-%dT%H:%M:%SZ); kill $GUARD 2>/dev/null
# a model call from a container killed at the time limit can still be in flight (and billed): let it finish and be logged
DRAIN=${PROXY_DRAIN_SECONDS:-60}; sleep "$DRAIN"; kill $PROXY 2>/dev/null
python3 "$H/openrouter_proxy.py" fetch "$EV/proxy.$ARM" | tee -a "$EV/driver.$ARM.log"
KU1=$(settled_key_usage || echo '{}')
cp "$WS/.autoresearch/diagnostics/$RUN_ID/0.json" "$EV/$ARM/diagnostics.json" 2>/dev/null || echo "NOTE: no diagnostics.json (run aborted?)"

python3 - "$EV/PROTOCOL.$ARM.json" <<PY
import hashlib, json, os, sys, pathlib
h = pathlib.Path("$H"); sha = lambda p: hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
json.dump({
  "model": "$MODEL", "arm": "$ARM", "run_id": "$RUN_ID", "replicate": $REP, "exit_code": $RC,
  "workspace_commit": "$head", "base_commit": "$BASE", "build_patch": "$ARM.build.patch", "agent_tree": "$tree", "started_utc": "$T0", "finished_utc": "$T1",
  "concurrency": $CONC, "seed": $SEED, "provider_ignore": "$IGNORE".split(","), "proxy_drain_seconds": $DRAIN, "proxy": "openrouter_proxy.py", "proxy_sha256": sha(h / "openrouter_proxy.py"), "task_timeout_seconds": 480, "grader_timeout_seconds": 600,
  "suite": "${TASKS_FILE:-remaining81}",
  "runner": "setupbench_ada_runner_ts.ts", "runner_sha256": sha(h / "setupbench_ada_runner_ts.ts"),
  "original_runner_sha256": sha(h / "setupbench_ada_runner.ts"),
  "evaluator_sha256": sha(h / "setupbench_ada_domain_eval.py"), "harness_sha256": sha(h / "setupbench_ada_eval.py"),
  "openrouter_key_usage_before": json.loads('''$KU0'''), "openrouter_key_usage_after": json.loads('''$KU1'''),
  "host": {"cpus": os.cpu_count(), "loadavg_start": "$LOAD0", "loadavg_end": open("/proc/loadavg").read().strip()}, "pricing_snapshot": "pricing_snapshot.json",
  "note": "baseline = df0c537 + pass-through systemPromptGuidance shim (see build_patch); R9/R10 ran 417a8f1, whose exact bytes are unrecoverable; original R1-R10 runner is setupbench_ada_runner.ts",
}, open(sys.argv[1], "w"), indent=2); open(sys.argv[1], "a").write("\n")
PY
# nothing secret may land in the evidence
if grep -rlE 'sk-or-[A-Za-z0-9_-]{16,}' "$EV" >/dev/null 2>&1 || grep -rlF "$OPENROUTER_API_KEY" "$EV" >/dev/null 2>&1; then
  echo "SECRET-SCAN FAIL: a key appears in $EV" | tee -a "$STATUS"; exit 3; fi
NOTRACE=$(python3 - "$EV/$ARM" <<'PY'
import json, pathlib, sys
bad = [p.parent.name for p in pathlib.Path(sys.argv[1]).glob("*/result.json") if not json.loads(p.read_text()).get("turns_from_trace")]
print(len(bad), " ".join(bad[:8]))
PY
)
python3 - "$EV/proxy.$ARM/generations.jsonl" "$IGNORE" <<'PY' | tee -a "$STATUS"
import collections, json, sys
rows = [json.loads(l) for l in open(sys.argv[1])]; ign = set(sys.argv[2].split(","))
msgs = [r for r in rows if r.get("path", "").split("?")[0].endswith("/v1/messages")]  # model calls; count_tokens (404) is not one
injected = sum(1 for r in msgs if r.get("provider_ignore"))
print("requests with provider.ignore injected:", injected, "of", len(msgs), "" if injected == len(msgs) else "  <<< INJECTION FAILED")
prov = collections.Counter((r.get("generation") or {}).get("provider_name") for r in msgs)
empty = sum(1 for r in rows if r.get("status") == 200 and r.get("blocks") == [] and r.get("tools"))
print("provider mix:", dict(prov), "| calls from an ignored provider:", sum(n for p, n in prov.items() if p in ign),
      "| empty agent replies:", empty, "of", sum(1 for r in rows if r.get("tools")), "agent calls")
PY
echo "attempts with NO trace turns (agent crashed before its first turn, or capture failed): $NOTRACE" | tee -a "$STATUS"
echo "COMPLETE $RUN_ID exit=$RC finished=$T1 secret-scan=clean" | tee "$STATUS"
exit $RC
