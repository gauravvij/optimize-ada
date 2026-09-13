# Ada Harness A/B Baseline Report

_Fixed model: claude-haiku-4-5 · Claude Code CLI 2.1.258 · Dataset terminal-bench@2.0 · 15 tasks × 2 arms × k=4 = 120 runs._

_Generated from eval/results/baseline-armA.jsonl + baseline-armB.jsonl (60+60 trials)._

## 1. Overall results

| Arm | Trials | Pass | Fail | Pass rate | Wilson 95% CI | Mean cost | Mean wall dur |
|---|---|---|---|---|---|---|---|
| A (claude-code (reference)) | 60 | 27 | 33 | 0.450 | [0.331, 0.575] | $0.1159 (0.0874–0.1445) | 296s (230–362) |
| B (ada-bridge (treatment)) | 60 | 33 | 27 | 0.550 | [0.425, 0.669] | $0.1042 (0.0780–0.1304) | 187s (113–260) |

**Trial pass-rate delta (B − A): +10.0 points.**

## 2. Data quality

- Trials collected: **120/120** (A 60, B 60).
- Trials with usage/cost: A 60/60, B 59/60.
- Missing usage in arm B (1): ['large-scale-text-editing'] — AgentTimeoutError @1200s on large-scale-text-editing; counted as a fail trial but EXCLUDED from arm-B cost/duration means for that task.
  - Error: large-scale-text-editing/large-scale-text-editing__dxrv8bH: {'exception_type': 'AgentTimeoutError', 'exception_message': 'Agent execution ti

Paired cost/duration statistics below use only task-pairs with usable trials in both arms (per-task means over the available repeats); no run was dropped silently.

## 3. Per-task breakdown (pass counts of 4 attempts)

| Task | A pass | B pass | A cost | B cost | A wall(s) | B wall(s) | A→B solved |
|---|---|---|---|---|---|---|---|
| fix-git | 3/4 | 4/4 | $0.0411 | $0.0394 | 158 | 52 | = |
| git-leak-recovery | 4/4 | 4/4 | $0.0304 | $0.0314 | 177 | 59 | = |
| git-multibranch | 3/4 | 3/4 | $0.2121 | $0.1181 | 279 | 132 | = |
| sanitize-git-repo | 0/4 | 2/4 | $0.1277 | $0.1207 | 175 | 81 | → |
| db-wal-recovery | 0/4 | 0/4 | $0.2056 | $0.1846 | 262 | 168 | = |
| regex-log | 2/4 | 3/4 | $0.1048 | $0.1066 | 245 | 140 | = |
| log-summary-date-ranges | 1/4 | 4/4 | $0.0376 | $0.0330 | 154 | 46 | = |
| filter-js-from-html | 0/4 | 0/4 | $0.0414 | $0.0536 | 861 | 500 | = |
| fix-code-vulnerability | 4/4 | 4/4 | $0.2831 | $0.1635 | 215 | 95 | = |
| vulnerable-secret | 4/4 | 4/4 | $0.0933 | $0.0870 | 186 | 90 | = |
| configure-git-webserver | 0/4 | 0/4 | $0.0102 | $0.0092 | 153 | 42 | = |
| openssl-selfsigned-cert | 4/4 | 3/4 | $0.0716 | $0.0489 | 169 | 58 | = |
| password-recovery | 0/4 | 0/4 | $0.1429 | $0.2363 | 255 | 279 | = |
| large-scale-text-editing | 1/4 | 0/4 | $0.3170 | $0.3679 | 954 | 990 | ← |
| cancel-async-tasks | 1/4 | 2/4 | $0.0203 | $0.0286 | 197 | 70 | = |

## 4. Harness-delta significance (pre-registered decision rule)

- Per-task solved (≥1 pass of 4): A 10/15, B 10/15. Discordant pairs: A-only 1, B-only 1.
- McNemar (exact) p = 1.0000 (NOT significant at α=0.05).
- Per-task pass counts A [0, 0, 0, 0, 0, 1, 1, 1, 2, 3, 3, 4, 4, 4, 4], B [0, 0, 0, 0, 0, 2, 2, 3, 3, 3, 4, 4, 4, 4, 4]: mean A 1.80/4, B 2.20/4. (Wilcoxon signed-rank p=0.1605)
- Paired per-task cost delta (B−A, per-task means): mean **$-0.0074** [$-0.0350, $+0.0203] → NOT significant at 95%.
- Paired per-task wall-duration delta (B−A): mean **-109.2s** [-157.1s, -61.3s] → significant at 95%.

## 5. Verdict

Pre-registered accept rule: an optimization/harness change is accepted only if (cost OR latency paired delta is statistically significant) AND pass-rate delta is within the noise band from the variance probe. The BASELINE itself is not an optimization — this section states the harness-contribution delta of wrapping claude-code inside the Ada bridge.

- Trial pass rate: A 0.450 vs B 0.550 → **Ada wrapper +10.0 points (6 trials)**.
- Pass-rate significance (McNemar, per-task solved): p=1.000 → fail to reject H0 of no harness effect on task solve rate.
- Cost: paired per-task delta -0.0074 (NOT significant).
- Wall duration: paired per-task delta -109.2s (significant). NOTE: this is wall-clock per trial (container lifecycle), not model-run time; Ada-native TTFT/duration_ms are captured on arm B only and not comparable across arms.

**Interpretation:** Ada's wrapper shows a significant cost/latency difference vs the bare reference arm on the same model, and the pass-rate direction favors the Ada arm (+10.0 points) though not statistically significant at the per-task level with 15 tasks. Baseline established — optimization experiments E1+ compare against these numbers with the same decision rule.**
