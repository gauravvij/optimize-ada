#!/usr/bin/env bash
# Finish the DeepSeek V4.1 Flash series without anyone watching:
#   wait for the 41-task run -> re-run harness errors (both builds, only those tasks) -> merge the runs into one 81-task view
#   -> summary -> model-vs-code comparison -> write readme3.md and ada/results3.md.
#
#   setsid nohup bash bench/finish_v41_series.sh > /dev/null 2>&1 < /dev/null &
#   cat ada/runs/deepseek-v4.1-flash/finish.STATUS      # where it is; the full log is finish.log next to it
#
# Test knobs (used only to test this script on old data): D SET_A SET_B RETRY ALL SKIP_RETRY=1 README_OUT RESULTS_OUT
set -uo pipefail
ROOT=/home/azureuser/adaAgent; cd "$ROOT"
D=${D:-$ROOT/ada/runs/deepseek-v4.1-flash}
SET_A=${SET_A:-$D/r1}; SET_B=${SET_B:-$D/r1_set41}; RETRY=${RETRY:-$D/r1_retry}; ALL=${ALL:-$D/r1_all}
V4=$ROOT/ada/runs/deepseek-v4-flash/r1
LOG=$D/finish.log; ST=$D/finish.STATUS
exec >> "$LOG" 2>&1
say () { echo "$1 $(date -u +%H:%M:%SZ)" | tee "$ST"; }

say "WAITING for $(basename "$SET_B") to finish"
until head -c 9 "$SET_B/run.STATUS" 2>/dev/null | grep -qE 'COMPLETE|ABORTED|SECRET'; do sleep 30; done
head -c 8 "$SET_B/run.STATUS" | grep -q '^COMPLETE' || { say "STOPPED: $(basename "$SET_B") did not complete: $(head -c 160 "$SET_B/run.STATUS")"; exit 1; }
say "set B complete; looking for harness errors"

# tasks with no valid attempt for some build in either run -> re-run both builds on just those tasks
python3 - "$SET_A" "$SET_B" > "$D/tasks.retry.txt" <<'PYEND'
import glob, json, sys
ok = {"baseline": set(), "best": set()}; seen = set()
for src in sys.argv[1:]:
    for arm in ok:
        for f in glob.glob(f"{src}/{arm}/*/result.json"):
            t = f.split("/")[-2]; seen.add(t)
            if json.load(open(f))["valid"]: ok[arm].add(t)
for t in sorted(t for t in seen if t not in ok["baseline"] or t not in ok["best"]): print(t)
PYEND
NRETRY=$(grep -c . "$D/tasks.retry.txt")
echo "harness-error tasks to retry: $NRETRY: $(tr '\n' ' ' < "$D/tasks.retry.txt")"

SRC=("$SET_A" "$SET_B")
if [ "$NRETRY" -gt 0 ] && [ "${SKIP_RETRY:-0}" != 1 ]; then
  if [ -z "$(docker ps -q --filter name=setupbench-ada)" ]; then docker rm -f $(docker ps -aq --filter name=setupbench-ada) 2>/dev/null; fi   # a container stuck in state Created blocks the driver
  say "retry run on $NRETRY task(s)"
  MODEL=deepseek/deepseek-v4.1-flash TASKS_FILE="$D/tasks.retry.txt" EVIDENCE_DIR="$RETRY" CONC=3 bash "$ROOT/bench/run_pair.sh" > "$D/$(basename "$RETRY").driver.log" 2>&1
  if head -c 8 "$RETRY/run.STATUS" 2>/dev/null | grep -q '^COMPLETE'; then SRC+=("$RETRY"); else echo "retry run did not complete: $(head -c 200 "$RETRY/run.STATUS" 2>/dev/null); merging without it"; fi
fi

say "merging"
python3 bench/merge_runs.py "$ALL" "${SRC[@]}" || { say "STOPPED: merge failed"; exit 1; }
say "summary + comparison"
python3 bench/deepseek_summary.py "$ALL" > "$ALL/summary.stdout.txt" 2>&1 || { say "STOPPED: summary failed"; exit 1; }
python3 bench/compare_runs.py "$V4" "$ALL" > "$ALL/comparison.stdout.txt" 2>&1 || { say "STOPPED: comparison failed"; exit 1; }
say "writing readme3.md and results3.md"
python3 bench/make_report_v41.py "$ALL" "$ALL/comparison_vs_deepseek-v4-flash_r1.json" ${README_OUT:+--out-readme="$README_OUT"} ${RESULTS_OUT:+--out-results="$RESULTS_OUT"} || { say "STOPPED: report generation failed"; exit 1; }
# nothing secret may land in the evidence or the docs
if grep -rlE 'sk-or-[A-Za-z0-9_-]{16,}' "$D" "$ROOT/readme3.md" "$ROOT/ada/results3.md" >/dev/null 2>&1; then say "SECRET-SCAN FAIL: a key-like string appears in the evidence or docs"; exit 3; fi
say "COMPLETE: results in $ALL/summary.md, docs readme3.md and ada/results3.md (review the wording; regenerate with bench/make_report_v41.py)"
