# E-opt1 re-test (v2) — treatment-reach provenance

Job: `e-opt1-arm-v2` · Arm: `e-opt1-v2` · Model: `anthropic/claude-haiku-4-5`
Dataset: `terminal-bench@2.0` · 15 tasks × k=4 = 60 trials
Started: 2026-09-03T16:56:22.911883Z · Finished: 2026-09-03T18:34:14.991915Z
(1h37m52s) · Jobs dir: `/root/optimize_ada/eval/jobs/e-opt1-arm-v2`

This file documents that the treated arm actually received the treatment
(concision guidance via the `systemPromptAppend` seam) — the guarantee that
was missing from the invalidated v1 run (`e-opt1-arm`, Sep 2, which ran
through the kwargs-swallowing adapter defect and was an untreated baseline
re-run with 0 treatment markers).

## 1. Launch configuration (treatment enabled)

Harbor invocation (foreground, no timeout):

```
harbor run --dataset terminal-bench@2.0 \
  --agent eval.ada-agent.ada_agent:AdaBridgeAgent \
  --model anthropic/claude-haiku-4-5 \
  --ak concision_guidance=1 --ak lever_debug=1 \
  --include-task-name <all 15 canonical TB2 tasks> \
  -k 4 -n 2 \
  --mounts '[{"type":"bind","source":"/root/optimize_ada/eval/ada-runtime","target":"/ada-runtime"}]' \
  --jobs-dir /root/optimize_ada/eval/jobs --job-name e-opt1-arm-v2 --yes
```

`--ak concision_guidance=1` → `AdaBridgeAgent.__init__` (eval/ada-agent/
ada_agent.py, explicit binding added to fix the kwargs-swallowing defect)
stores `concision_guidance=True` → `_bridge_env()` sets
`ADA_CONCISION_GUIDANCE=1` in the bridge process env. `--ak lever_debug=1` →
`ADA_LEVER_DEBUG=1` (emits `[lever-debug]` lines proving the seam ran).

## 2. Zero-cost pre-flight evidence (before any paid spend)

1. **Importlib kwargs-binding test** (host, 0 API cost): instantiating
   `AdaBridgeAgent(logs_dir, concision_guidance=True, lever_debug=True)`
   produced `_bridge_env()` containing `ADA_CONCISION_GUIDANCE=1` and
   `ADA_LEVER_DEBUG=1`; the default instance had neither key (gate OFF by
   default). Output marker: `KWARGS BINDING VERIFIED`.
2. **md5 parity** (source vs runtime trees, verified 2026-09-03):
   - `ada/agent/concision-guidance.ts` ==
     `eval/ada-runtime/ada/agent/concision-guidance.ts` →
     `024e4b492a75774e6ddb4b026806b01a`
   - `ada/agent/index.ts` == `eval/ada-runtime/ada/agent/index.ts` →
     `37fd53b1c7e8dc15c61eb166910661d1` (post-L1L2 state; the original E-opt1
     README recorded index.ts as `18ea37b1`, which predates the L1L2 wiring)
   - `ada/agent/lever-guidance.ts` ==
     `eval/ada-runtime/ada/agent/lever-guidance.ts` →
     `ccadffd92bfb5cfad02ccf2dd1fae277` (present but NOT active in this arm —
     its env gates `ADA_SELF_VERIFY`/`ADA_ADAPTIVE_CONCISION` were unset)
3. **In-container probe `e-opt1-probe-v2`** (2 tasks × k=1: fix-git,
   log-summary-date-ranges, same `--ak` flags): 2/2 trials, 0 exceptions,
   $0.0895, 3m16s. Both bridge logs contained:
   - marker text `Operating-efficiency guidance`
   - `[lever-debug] systemPromptAppend (2 part(s), 477+1018 chars)`
     → the seam composed github guidance + concision guidance (2 parts) into
     the system prompt.

Pre-flight PASSED → paid run launched.

## 3. Per-trial treatment reach (post-run, all 60 trials)

Method: python glob over `eval/jobs/e-opt1-arm-v2/*/result.json` → check
`<trial>/agent/ada-bridge.log` for the marker text
`Operating-efficiency guidance` (the first line of the concision-guidance
module's returned string).

Result: **60/60 bridge logs contain the marker; 0 misses; 0 absent logs.**

Per-task trial-dir counts (4 per task, all 15 canonical tasks):
cancel-async-tasks 4, configure-git-webserver 4, db-wal-recovery 4,
filter-js-from-html 4, fix-code-vulnerability 4, fix-git 4,
git-leak-recovery 4, git-multibranch 4, large-scale-text-editing 4,
log-summary-date-ranges 4, openssl-selfsigned-cert 4, password-recovery 4,
regex-log 4, sanitize-git-repo 4, vulnerable-secret 4.

Representative log excerpt (from a trial dir under
`eval/jobs/e-opt1-arm-v2/`):

```
[lever-debug] systemPromptAppend (2 part(s), 477+1018 chars)
... Operating-efficiency guidance for this run (eval harness): ...
```

(The lever-debug line proves the `systemPromptAppend` seam executed and
composed exactly 2 guidance parts — the E-opt1 module is the only
1018-char part.)

## 4. Run integrity

- 60/60 trials completed; 1 exception:
  `large-scale-text-editing__DtVpMmX` `AgentTimeoutError` @1200s (no usage
  recorded). This mirrors arm B's known exception on the same task (arm B also
  has only 3 usable costs there), so the cost-pairing exclusion of
  `large-scale-text-editing` (14 paired tasks) carries over from the original
  methodology unchanged.
- Results exported: `eval/results/e-opt1-arm-v2.jsonl` — 60 records, arm
  `e-opt1-v2` 60/60, 59 with cost, total spend **$6.0042** (probe $0.0895
  additional). Schema keys identical to `eval/results/baseline-armB.jsonl`.

## 5. Artifacts

- `eval/results/e-opt1-arm-v2.jsonl` (treated results)
- `eval/experiments/E-opt1/decision-v2.json` (structured decision, includes
  `treatment_reach` 60/60)
- `eval/analysis/analyze_eopt1_v2.py` (analysis script)
- Jobs: `eval/jobs/e-opt1-arm-v2/` (60 trials + job result),
  `eval/jobs/e-opt1-probe-v2/` (2-trial probe)
