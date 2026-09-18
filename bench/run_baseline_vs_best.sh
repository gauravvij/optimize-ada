#!/usr/bin/env bash
# Confirmation run: campaign baseline vs the shipped best build, remaining81.
#
#   baseline  targets/ada-baseline  417a8f1  (df0c537 + committed runner shim; = R1/R5)
#   best      targets/ada           3e0645f  (T0.1 watchdog; T1.2 gates default off; = R7 behaviour)
#
# Design fixes from the 2026-09-10..12 lessons:
#   * Arms run CONCURRENTLY at concurrency 2 each (total load 4, as before), same seed and
#     task order, so both see identical provider conditions minute-for-minute. No day effect.
#   * Replicates (REPS, default 2) back to back, so "the result holds" is measured, not assumed.
#   * Preflight pins the agent TREE hash of each workspace and refuses a dirty agent/.
#   * Diagnostics are written even with invalid rows; analysis runs automatically at the end.
#
# PRE-REGISTERED RULE (fixed before any spend) — the result HOLDS only if all of:
#   1. every replicate completes with both diagnostics files
#   2. every replicate: best - baseline net >= +10 tasks
#   3. every replicate: <= 3 invalid rows per arm
#   4. pooled paired McNemar over all replicates: best > baseline, p < 0.001
# Anything else is reported as DOES NOT HOLD, with the numbers.
set -uo pipefail
ROOT=/home/azureuser/adaAgent; B=$ROOT/bench
REPS=${REPS:-2}
CONC=${CONC:-2}   # per arm; the machine is shared, so CONC=1 keeps load and memory low and steady
OURS='name=^setupbench-ada-'   # only ever look at / remove this eval's containers
TS="$(date -u +%Y%m%dT%H%MZ)"
STATUS=$B/baseline_vs_best_STATUS; MEMLOG=$B/baseline_vs_best_${TS}_memory.log
exec > >(tee -a "$B/baseline_vs_best_${TS}_driver.log") 2>&1

pgrep -f 'python[0-9.]* [^ ]*setupbench_ada_domain_eval[.]py' >/dev/null && { echo "REFUSING: an eval is already running"; exit 1; }
[ -n "$(docker ps -aq --filter "$OURS")" ] && { echo "REFUSING: setupbench-ada containers are up"; exit 1; }

cd "$ROOT/autoresearcher"
set -a; . ./.env; set +a
export ANTHROPIC_AUTH_TOKEN="${ANTHROPIC_AUTH_TOKEN:-$OPENROUTER_API_KEY}"
: "${ANTHROPIC_AUTH_TOKEN:?no API key}"

ok=1
for spec in "targets/ada-baseline df8a18c092787af91ff143f711091e752b62c268" \
            "targets/ada dab704de524a7b31203f0b53374ec539cbb7089d"; do
  set -- $spec
  tree=$(git -C "$1" rev-parse HEAD:agent); dirty=$(git -C "$1" status --porcelain -- agent)
  if [ "$tree" = "$2" ] && [ -z "$dirty" ]; then echo "PREFLIGHT OK   $1 agent tree ${tree:0:12} clean"
  else echo "PREFLIGHT FAIL $1 tree=${tree:0:12} want=${2:0:12} dirty=[$dirty]"; ok=0; fi
done
.venv/bin/python -c "
import sys; sys.path.insert(0,'examples')
from pathlib import Path
from setupbench_ada_domain_eval import enforce_mutation_boundary as e
[e(Path(w).resolve()) for w in ('targets/ada-baseline','targets/ada')]; print('PREFLIGHT OK   mutation boundary')" || ok=0
grep -q '(process.env.ADA_TIME_HINTS ?? "0")' targets/ada/agent/claude/agent.ts || { echo "PREFLIGHT FAIL best build has time hints on"; ok=0; }
[ $ok = 1 ] || exit 1
[ "${DRY_RUN:-0}" = 1 ] && { echo "DRY_RUN: preflight passed, nothing launched"; exit 0; }

echo "=== preparing task cache + images once (arms then only read it) ==="
.venv/bin/python examples/setupbench_ada_domain_eval.py remaining81 --prepare-only | tail -1 || exit 1

echo "RUNNING ts=$TS reps=$REPS started=$(date -u)" > "$STATUS"
( while true; do
    A=$(free -m | awk 'NR==2{print $7}'); W=$(free -m | awk 'NR==3{print $3}')
    D=$(df -BG --output=avail / | tail -1 | tr -dc 0-9)
    echo "$(date -u +%H:%M:%S) mem_avail=${A}M swap_used=${W}M disk_free=${D}G ours=$(docker ps -q --filter "$OURS" | wc -l) all=$(docker ps -q | wc -l)" >> "$MEMLOG"
    if [ "$A" -lt 1200 ] || [ "$W" -gt 6144 ] || [ "$D" -lt 5 ]; then
      echo "ABORTED-resource-guard avail=${A}M swap=${W}M disk=${D}G $(date -u)" > "$STATUS"
      pkill -f 'python[0-9.]* [^ ]*setupbench_ada_domain_eval[.]py'; docker rm -f $(docker ps -aq --filter "$OURS") 2>/dev/null; exit 1
    fi; sleep 20; done ) & GUARD=$!
trap 'kill $GUARD 2>/dev/null' EXIT

arm () {  # $1 workspace  $2 run-id suffix  $3 log
  AUTORESEARCH_RUN_ID=${TS}-$2 AUTORESEARCH_EXPERIMENT_NUMBER=0 \
    .venv/bin/python examples/setupbench_ada_domain_eval.py remaining81 --workspace "$1" --concurrency "$CONC" > "$3" 2>&1
}
for r in $(seq 1 "$REPS"); do
  echo "=== REPLICATE $r/$REPS both arms concurrently === $(date -u)"
  arm targets/ada-baseline r$r-base "$B/baseline_vs_best_${TS}_r${r}_baseline.log" & P1=$!
  arm targets/ada          r$r-best "$B/baseline_vs_best_${TS}_r${r}_best.log" & P2=$!
  wait $P1; R1=$?; wait $P2; R2=$?
  echo "REPLICATE $r DONE baseline exit=$R1 best exit=$R2 $(date -u)"
  echo "REP_${r}_DONE base=$R1 best=$R2 $(date -u)" >> "$STATUS"
done
kill $GUARD 2>/dev/null
echo "=== analysis ==="
python3 "$B/baseline_vs_best_analysis.py" "$TS" "$REPS"
echo "COMPLETE ts=$TS $(date -u)" > "$STATUS"
