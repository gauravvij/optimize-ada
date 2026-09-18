#!/usr/bin/env bash
# P3 candidate paired gate run (Phase C, 2026-09-16): shipped best vs P3
# (late wrap-up: time hints default ON, ADA_WRAP_UP_MS default 96,000 ms
# remaining = fire after ~80% of the 480 s budget is consumed).
#
#   shipped   targets/ada     tag ada-best-61pct-20260916 (agent tree dab704d)
#   p3        targets/ada-p3  branch p3-late-wrapup (commit 9f2e34d)
#
# Pool: the 25 consistently-failing tasks (bench/FAILING25.txt), standard
# task budget 480 s (the shipped config — the candidate must earn passes
# INSIDE the shipped budget, not a bigger one), concurrency 1 per arm (the
# machine is shared with the Pi_cloudOps worker), both arms of a replicate
# run concurrently minute-for-minute, REPS replicates back to back.
#
# PRE-REGISTERED RULE (fixed before any spend):
#   keep P3 only if ALL of:
#     1. every replicate completes with both diagnostics files
#     2. pooled net (p3 - shipped) >= +5 tasks over the paired pool
#     3. no replicate has a negative net
#   Anything else = revert (P3 does not ship).
#
# Usage: REPS=2 ./run_p3_paired.sh   (DRY_RUN=1 for preflight only)
set -uo pipefail
ROOT=/home/azureuser/adaAgent; B=$ROOT/bench
REPS=${REPS:-2}
CONC=${CONC:-1}
DRY_RUN=${DRY_RUN:-0}
OURS='name=^setupbench-ada-'
TS="$(date -u +%Y%m%dT%H%MZ)"
STATUS=$B/p3_paired_STATUS; MEMLOG=$B/p3_paired_${TS}_memory.log
exec > >(tee -a "$B/p3_paired_${TS}_driver.log") 2>&1

pgrep -f 'python[0-9.]* [^ ]*setupbench_ada_domain_eval[.]py' >/dev/null && { echo "REFUSING: an eval is already running"; exit 1; }
[ -n "$(docker ps -aq --filter "$OURS")" ] && { echo "REFUSING: setupbench-ada containers are up"; exit 1; }

cd "$ROOT/autoresearcher"
set -a; . ./.env; set +a
export ANTHROPIC_AUTH_TOKEN="${ANTHROPIC_AUTH_TOKEN:-$OPENROUTER_API_KEY}"
: "${ANTHROPIC_AUTH_TOKEN:?no API key}"

ok=1
# Shipped arm: the tagged best, agent tree pinned, agent/ clean.
tree=$(git -C targets/ada rev-parse HEAD:agent); dirty=$(git -C targets/ada status --porcelain -- agent)
if [ "$tree" = "dab704de524a7b31203f0b53374ec539cbb7089d" ] && [ -z "$dirty" ]; then
  echo "PREFLIGHT OK   targets/ada agent tree ${tree:0:12} clean"
else echo "PREFLIGHT FAIL targets/ada tree=${tree:0:12} dirty=[$dirty]"; ok=0; fi
# P3 arm: branch p3-late-wrapup, agent tree pinned to the P3 commit, agent/ clean.
p3head=$(git -C targets/ada-p3 rev-parse --short HEAD)
tree=$(git -C targets/ada-p3 rev-parse HEAD:agent); dirty=$(git -C targets/ada-p3 status --porcelain -- agent)
p3tree_expect=$(git -C targets/ada-p3 rev-parse p3-late-wrapup:agent)
if [ "$tree" = "$p3tree_expect" ] && [ "$p3head" = "9f2e34d" ] && [ -z "$dirty" ]; then
  echo "PREFLIGHT OK   targets/ada-p3 ($p3head) agent tree ${tree:0:12} clean"
else echo "PREFLIGHT FAIL targets/ada-p3 head=$p3head tree=${tree:0:12} expect=${p3tree_expect:0:12} dirty=[$dirty]"; ok=0; fi
# Shipped build must still have hints default OFF; P3 must have them default ON.
grep -q '(process.env.ADA_TIME_HINTS ?? "0") === "1"' targets/ada/agent/claude/agent.ts \
  || { echo "PREFLIGHT FAIL shipped build no longer has hints default off"; ok=0; }
grep -q '(process.env.ADA_TIME_HINTS ?? "1") === "1"' targets/ada-p3/agent/claude/agent.ts \
  || { echo "PREFLIGHT FAIL p3 build does not have hints default on"; ok=0; }
grep -q 'ADA_WRAP_UP_MS ?? 96_000' targets/ada-p3/agent/claude/agent.ts \
  || { echo "PREFLIGHT FAIL p3 build missing 96s wrap-up default"; ok=0; }
.venv/bin/python -c "
import sys; sys.path.insert(0,'examples')
from pathlib import Path
from setupbench_ada_domain_eval import enforce_mutation_boundary as e
[e(Path(w).resolve()) for w in ('targets/ada','targets/ada-p3')]; print('PREFLIGHT OK   mutation boundary')" || ok=0
[ $ok = 1 ] || exit 1
[ "$DRY_RUN" = 1 ] && { echo "DRY_RUN: preflight passed, nothing launched"; exit 0; }

echo "=== preparing task cache + images once (arms then only read it) ==="
.venv/bin/python examples/setupbench_ada_domain_eval.py --tasks-file "$B/FAILING25.txt" --prepare-only | tail -1 || exit 1

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
    .venv/bin/python examples/setupbench_ada_domain_eval.py \
      --tasks-file "$B/FAILING25.txt" --workspace "$1" \
      --task-timeout-seconds 480 --grader-timeout-seconds 600 \
      --concurrency "$CONC" > "$3" 2>&1
}
for r in $(seq 1 "$REPS"); do
  echo "=== REPLICATE $r/$REPS both arms concurrently === $(date -u)"
  arm targets/ada     r$r-shipped "$B/p3_paired_${TS}_r${r}_shipped.log" & P1=$!
  arm targets/ada-p3  r$r-p3      "$B/p3_paired_${TS}_r${r}_p3.log"      & P2=$!
  wait $P1; R1=$?; wait $P2; R2=$?
  echo "REPLICATE $r DONE shipped exit=$R1 p3 exit=$R2 $(date -u)"
  echo "REP_${r}_DONE shipped=$R1 p3=$R2 $(date -u)" >> "$STATUS"
done
kill $GUARD 2>/dev/null
echo "=== analysis ==="
python3 "$B/p3_paired_analysis.py" "$TS" "$REPS"
echo "COMPLETE ts=$TS $(date -u)" > "$STATUS"
