#!/bin/bash
# Budget probe driver: 25 consistently-failing SetupBench tasks at 960 s,
# concurrency 1, shipped build (targets/ada @ c6f917e, tagged ada-best-61pct-20260916).
# Pre-registered decision rule (fixed before spend, applied by bench/budget_probe_analysis.py):
#   >=12/25 pass = SLOW; 4-11 = MIXED; <=3 = HARD.
# Shared box: concurrency 1 + periodic free -m logging (do not touch other workers).
set -u
cd /home/azureuser/adaAgent/autoresearcher

TS=20260916T0730Z
OUT=/home/azureuser/adaAgent/bench/BUDGET_PROBE_$TS
mkdir -p "$OUT"
DRIVER_LOG="$OUT/driver.log"
MEMORY_LOG="$OUT/memory.log"

echo "=== budget probe start $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" >> "$DRIVER_LOG"
echo "run_id: budget-probe-$TS" >> "$DRIVER_LOG"
echo "tasks: 25 (bench/FAILING25.txt), timeout 960s, concurrency 1, shipped build" >> "$DRIVER_LOG"
echo "workspace commit: $(git -C targets/ada rev-parse HEAD)" >> "$DRIVER_LOG"
echo "agent tree: $(git -C targets/ada rev-parse HEAD:agent)" >> "$DRIVER_LOG"

# Periodic memory/load snapshots (shared box caveat), every 60 s.
(
  while true; do
    echo "--- $(date -u +%Y-%m-%dT%H:%M:%SZ) ---" >> "$MEMORY_LOG"
    free -m >> "$MEMORY_LOG"
    uptime >> "$MEMORY_LOG"
    sleep 60
  done
) &
MEM_PID=$!
trap "kill $MEM_PID 2>/dev/null" EXIT

set -a; . ./.env; set +a
AUTORESEARCH_RUN_ID=budget-probe-$TS \
AUTORESEARCH_EXPERIMENT_NUMBER=0 \
.venv/bin/python examples/setupbench_ada_domain_eval.py \
  --tasks-file /home/azureuser/adaAgent/bench/FAILING25.txt \
  --workspace targets/ada \
  --task-timeout-seconds 960 \
  --grader-timeout-seconds 600 \
  --concurrency 1 \
  --seed 20260907 >> "$DRIVER_LOG" 2>&1
RC=$?

echo "=== eval exit code: $RC $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" >> "$DRIVER_LOG"
# Copy diagnostics into the probe output dir for a self-contained record.
cp -r targets/ada/.autoresearch/diagnostics/budget-probe-$TS "$OUT/" 2>/dev/null
echo "=== budget probe end $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" >> "$DRIVER_LOG"
exit $RC
