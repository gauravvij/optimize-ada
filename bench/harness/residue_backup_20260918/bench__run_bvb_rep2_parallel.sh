#!/usr/bin/env bash
# Speed-up for run 20260915T0825Z (2026-09-15): start replicate 2 while replicate 1 is still
# running, instead of after it. Each replicate still runs its two arms concurrently, so the
# pairing inside a replicate is unchanged. Replicate 2 runs from git worktrees at the same
# commits (targets/ada-baseline-r2, targets/ada-r2; agent trees pinned as in
# run_baseline_vs_best.sh) so its containers can be told apart by mount source.
#
# Guards, checked every 20 s:
#   hard  avail < 1200M, swap > 6144M or disk < 5G -> stop everything of ours (as before)
#   soft  avail < 2500M while replicate 1 still runs -> kill replicate 2 only; it re-runs
#         from scratch once replicate 1 has finished. Replicate 1 and other jobs keep going.
# Usage: run_bvb_rep2_parallel.sh <rep1 baseline eval pid> <rep1 best eval pid>
set -uo pipefail
ROOT=/home/azureuser/adaAgent; B=$ROOT/bench; T=$ROOT/autoresearcher/targets
TS=20260915T0825Z
STATUS=$B/baseline_vs_best_STATUS; MEMLOG=$B/baseline_vs_best_${TS}_memory.log
OURS='name=^setupbench-ada-'
REP1_PIDS="$*"; R2_PIDS=""; SHED=0; REP1_LOGGED=0
exec >> "$B/baseline_vs_best_${TS}_driver.log" 2>&1

cd "$ROOT/autoresearcher"
set -a; . ./.env; set +a
export ANTHROPIC_AUTH_TOKEN="${ANTHROPIC_AUTH_TOKEN:-$OPENROUTER_API_KEY}"

alive () { local s; for p in "$@"; do s=$(ps -o stat= -p "$p" 2>/dev/null) && [ "${s#Z}" = "$s" ] && return 0; done; return 1; }
r2_containers () { for c in $(docker ps -aq --filter "$OURS"); do
  docker inspect -f '{{range .Mounts}}{{.Source}} {{end}}' "$c" 2>/dev/null | grep -qE 'targets/ada(-baseline)?-r2 ' && echo "$c"; done; }
launch_rep2 () {
  R2_PIDS=""
  for spec in "ada-baseline-r2 base baseline" "ada-r2 best best"; do set -- $spec
    AUTORESEARCH_RUN_ID=${TS}-r2-$2 AUTORESEARCH_EXPERIMENT_NUMBER=0 \
      .venv/bin/python examples/setupbench_ada_domain_eval.py remaining81 --workspace "targets/$1" --concurrency 1 \
      > "$B/baseline_vs_best_${TS}_r2_$3.log" 2>&1 &
    R2_PIDS="$R2_PIDS $!"
  done
  echo "=== REPLICATE 2/2 launched (pids$R2_PIDS) === $(date -u)"
  echo "REP_2_RUNNING $(date -u)" >> "$STATUS"
}

launch_rep2
while :; do
  A=$(free -m | awk 'NR==2{print $7}'); W=$(free -m | awk 'NR==3{print $3}')
  D=$(df -BG --output=avail / | tail -1 | tr -dc 0-9)
  echo "$(date -u +%H:%M:%S) mem_avail=${A}M swap_used=${W}M disk_free=${D}G ours=$(docker ps -q --filter "$OURS" | wc -l) all=$(docker ps -q | wc -l)" >> "$MEMLOG"
  if [ "$A" -lt 1200 ] || [ "$W" -gt 6144 ] || [ "$D" -lt 5 ]; then
    echo "ABORTED-resource-guard avail=${A}M swap=${W}M disk=${D}G $(date -u)" >> "$STATUS"
    pkill -f 'python[0-9.]* [^ ]*setupbench_ada_domain_eval[.]py'; docker rm -f $(docker ps -aq --filter "$OURS") >/dev/null 2>&1; exit 1
  fi
  if [ "$SHED" = 0 ] && alive $REP1_PIDS && [ "$A" -lt 2500 ]; then
    kill $R2_PIDS 2>/dev/null; sleep 3; docker rm -f $(r2_containers) >/dev/null 2>&1
    echo "REP_2_SHED avail=${A}M $(date -u) - re-runs after replicate 1" | tee -a "$STATUS"; SHED=1
  fi
  if ! alive $REP1_PIDS; then
    [ "$REP1_LOGGED" = 0 ] && { echo "REP_1_DONE $(date -u)" | tee -a "$STATUS"; REP1_LOGGED=1; }
    if [ "$SHED" = 1 ]; then launch_rep2; SHED=2
    elif ! alive $R2_PIDS; then break; fi
  fi
  sleep 20
done
wait
echo "REP_2_DONE $(date -u)" | tee -a "$STATUS"

# The analysis reads replicate diagnostics from the original workspaces.
for spec in "ada-baseline-r2 ada-baseline base" "ada-r2 ada best"; do set -- $spec
  src="$T/$1/.autoresearch/diagnostics/${TS}-r2-$3/0.json"; dst="$T/$2/.autoresearch/diagnostics/${TS}-r2-$3"
  [ -f "$src" ] && mkdir -p "$dst" && cp "$src" "$dst/0.json" || echo "MISSING $src"
done
echo "=== analysis ==="
python3 "$B/baseline_vs_best_analysis.py" "$TS" 2
echo "COMPLETE ts=$TS $(date -u)" >> "$STATUS"
