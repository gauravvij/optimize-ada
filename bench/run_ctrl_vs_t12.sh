#!/usr/bin/env bash
# The run fina_run.md §7 marks REQUIRED: same-day paired remaining81,
# T0.4 control 6672af8 vs candidate 2e495bb (T1.2).
#
# Why: the promoted "52/81 vs 24/81" is anchored on a 2026-09-10 run of 6672af8
# that scores 13/33 where its own ancestor df0c537 scores 31/33 (18-0, p=7.6e-06,
# zero timeouts either side). Either that day was degraded or 6672af8 carried a
# defect T1.2 masked. Only a same-day pairing separates the two, and only it
# measures what T1.2 is actually worth.
#
# Arms (identical harness, identical protocol, one machine, one day):
#   arm 1  control    6672af8  targets/ada-t01gateoff  (worktree, agent/ == 6672af8)
#   arm 2  candidate  2e495bb  targets/ada             (agent/ == 2e495bb; HEAD adds docs only)
# Arm order is control-first deliberately: if the day degrades as it goes, the
# second arm is penalised, which makes a candidate win the conservative outcome.
#
# Protocol EXACT and unchanged from every prior rung -- conc 4 / 480 s task /
# 600 s grader / seed 20260907 / z-ai/glm-5.3-flash. Concurrency stays at 4 even
# though the 2026-09-12 run lost 7 tasks to docker timeouts at conc 4: today's
# control number has to be comparable to the 2026-09-10 control number, and
# changing conditions would confound exactly the question being asked.
#
# Free drift check built in: T1.2 has already been measured twice on this suite
# (46/74 Sep-11, 43/74 Sep-12). If arm 2 lands in that band the day is normal and
# arm 1's number can be trusted against the stored 2026-09-10 control.
set -uo pipefail
ROOT=/home/azureuser/adaAgent
B=$ROOT/bench
TS="$(date -u +%Y%m%dT%H%MZ)"
STATUS=$B/ctrl_vs_t12_STATUS
MEMLOG=$B/ctrl_vs_t12_memory.log
DRIVERLOG=$B/ctrl_vs_t12_driver.log

exec > >(tee -a "$DRIVERLOG") 2>&1

# --- refuse to contend ------------------------------------------------------
if pgrep -f 'examples/setupbench_ada_domain_eval' >/dev/null; then
  echo "REFUSING: a setupbench eval is already running"; exit 1
fi
if [ -n "$(docker ps -q)" ]; then
  echo "REFUSING: docker containers are already up:"; docker ps --format '  {{.Names}}'; exit 1
fi

cd "$ROOT/autoresearcher"
set -a; . ./.env; set +a
export ANTHROPIC_AUTH_TOKEN="${ANTHROPIC_AUTH_TOKEN:-$OPENROUTER_API_KEY}"
: "${ANTHROPIC_AUTH_TOKEN:?no API key}"

# --- both workspaces must be inside the mutation boundary before we spend 4.5h
python3 - <<'PY' || exit 1
import sys; sys.path.insert(0, "examples")
from pathlib import Path
from setupbench_ada_domain_eval import enforce_mutation_boundary
import subprocess
ok = True
for w, want in (("targets/ada-t01gateoff", "6672af8"), ("targets/ada", "2e495bb")):
    try:
        enforce_mutation_boundary(Path(w).resolve())
    except RuntimeError as e:
        print(f"PREFLIGHT FAIL {w}: {e}"); ok = False; continue
    sha = subprocess.run(["git", "-C", w, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    d = subprocess.run(["git", "-C", w, "diff", "--stat", want, "HEAD", "--", "agent"],
                       capture_output=True, text=True).stdout.strip()
    if d:
        print(f"PREFLIGHT FAIL {w}: agent/ differs from {want}:\n{d}"); ok = False
    else:
        print(f"PREFLIGHT OK   {w}  HEAD={sha[:7]}  agent/ == {want}")
sys.exit(0 if ok else 1)
PY

echo "RUNNING pid=$$ ts=$TS started=$(date -u)" > "$STATUS"
echo "=== ctrl-vs-t12 paired run, ts=$TS, started $(date -u) ==="

# --- guard: OOM abort, plus docker-daemon responsiveness instrumentation.
# The 2026-09-12 run lost 7 tasks to `docker exec` timing out at 10 s while the
# OOM guard sat well above its floor. Timing `docker ps` every 20 s turns a
# repeat of that from a mystery into a measurement.
( while true; do
    A=$(free -m | awk 'NR==2{print $7}'); W=$(free -m | awk 'NR==3{print $3}')
    T0=$(date +%s%N); timeout 15 docker ps -q >/dev/null 2>&1; DRC=$?; T1=$(date +%s%N)
    DMS=$(( (T1 - T0) / 1000000 ))
    NC=$(docker ps -q 2>/dev/null | wc -l)
    echo "$(date -u +%H:%M:%S) mem_avail=${A}M swap_used=${W}M disk_free=$(df --output=avail -BG / | tail -1 | tr -d ' ') containers=${NC} docker_ps_ms=${DMS} docker_rc=${DRC}" >> "$MEMLOG"
    if [ "$A" -lt 1200 ] || [ "$W" -gt 6144 ]; then
      echo "GUARD TRIPPED avail=${A}M swap=${W}M $(date -u)" >> "$MEMLOG"
      echo "ABORTED-memory-guard avail=${A}M swap=${W}M $(date -u)" > "$STATUS"
      pkill -f 'examples/setupbench_ada_domain_eval'; docker rm -f $(docker ps -aq) 2>/dev/null; exit 1
    fi
    sleep 20
  done ) & GUARD=$!
trap 'kill $GUARD 2>/dev/null' EXIT

run_arm () {  # $1=label  $2=workspace  $3=runid-suffix  $4=logfile
  echo "=== ARM $1 === $(date -u)"
  AUTORESEARCH_RUN_ID=${TS}-$3 AUTORESEARCH_EXPERIMENT_NUMBER=0 \
    .venv/bin/python examples/setupbench_ada_domain_eval.py remaining81 --workspace "$2" \
    > "$4" 2>&1
  local rc=$?
  echo "ARM $1 DONE exit=$rc $(date -u) | $(grep -c '^task=' "$4") rows, $(grep -c 'valid=0' "$4") invalid, $(tail -2 "$4" | head -1)"
  echo "ARM_$1_DONE exit=$rc $(date -u)" >> "$STATUS"
  return $rc
}

run_arm "1of2-CONTROL-6672af8"   targets/ada-t01gateoff t04ctrl2 "$B/ctrl_vs_t12_control.log"
run_arm "2of2-CANDIDATE-2e495bb" targets/ada            t12cand2 "$B/ctrl_vs_t12_candidate.log"

kill $GUARD 2>/dev/null
echo "=== peak swap / min avail / worst docker_ps latency ==="
awk '{for(i=1;i<=NF;i++){
        if($i~/^swap_used=/){gsub(/[^0-9]/,"",$i); if($i+0>s)s=$i+0}
        if($i~/^mem_avail=/){gsub(/[^0-9]/,"",$i); if(m==""||$i+0<m)m=$i+0}
        if($i~/^docker_ps_ms=/){gsub(/[^0-9]/,"",$i); if($i+0>d)d=$i+0}}}
     END{print "peak_swap="s"M min_avail="m"M worst_docker_ps="d"ms"}' "$MEMLOG"
echo "=== diagnostics ==="
for p in "targets/ada-t01gateoff/.autoresearch/diagnostics/${TS}-t04ctrl2/0.json" \
         "targets/ada/.autoresearch/diagnostics/${TS}-t12cand2/0.json"; do
  [ -f "$p" ] && echo "  $p -> $(python3 -c "import json,sys;print(json.load(open('$p'))['summary'])")" \
              || echo "  $p -> MISSING (arm returned non-zero; per-task data is in its log)"
done
echo "COMPLETE ts=$TS $(date -u)" > "$STATUS"
echo "=== COMPLETE $(date -u) ==="
