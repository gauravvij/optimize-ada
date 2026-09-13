# Dev-loop X3 decision — effort-realism directive (KILL: cost breach)

Job: `dev-x3` · Arm: `dev-x3` · Lever: `ADA_EFFORT_REALISM=1` (env-gated
`effortRealismGuidance` in `ada/agent/lever-guidance.ts`, wired into
`systemPromptAppend` in `index.ts`) · Model: `anthropic/claude-haiku-4-5` ·
Dataset: `terminal-bench@2.0`, 10 dev tasks × k=4 = 40 trials · Results:
`eval/results/dev-x3.jsonl` (40 records, arm=`dev-x3`, 40 cost-bearing) ·
Analysis: `eval/analysis/analyze_dev_x3.py`

Reference arm: FRESH `dev-baseline` (`eval/results/dev-baseline.jsonl`,
24/40 = 0.600, mean cost $0.0879). Comparisons are position-based within
task (the `trial` field is not comparable across arms).

## Hypothesis (why X3 followed X2)
Exhaustive exploration / strategy-thrash on hard tasks (large-scale-text-
editing 2 timeouts @1200s in baseline, sanitize-git-repo 1/4). Directive:
prefer a complete working minimal solution over exhaustive exploration;
after ≤3 failed attempts on one approach, switch; no speculative reads;
when verifying, do it cheaply against the stated criteria (X2 inherited).

## Pre-registered criteria (ledger.md X3 row)
- Kill: dev pass < 24/40 (baseline) OR mean cost > 1.05 × $0.0879 =
  **$0.0923**
- Success targets: large-scale-text-editing ≥ 3/4 AND sanitize-git-repo ≥ 2/4
- Litmus watch: cancel-async-tasks (record; regression to 0/4 triggers
  review — X3's thrash mechanism is orthogonal to cancel-async-tasks'
  never-runs mechanism, so not binding)
- Promotion gate (unchanged): dev pass ≥ 28/40 AND guards 4/4 AND mean cost
  ≤ 1.10 × $0.0879 = **$0.0967** AND trace evidence (marker reach)

## Results vs pre-registered criteria

| Criterion | Baseline | X3 | Result |
|---|---|---|---|
| Suite pass | 24/40 = 0.600 | **28/40 = 0.700** | Δ +0.100 (4 trials converted) |
| Guards (fix-code-vulnerability, git-leak-recovery) | 8/8 | 8/8 | intact ✓ |
| Position-based McNemar | — | discordant base-only 3 / arm-only 7 | two-sided exact p = **0.3438** |
| Mean cost (cost-bearing) | $0.0879 (n=38) | **$0.1158 (n=40)** | ratio **1.317** — **KILL** (> $0.0923) |
| Success target large-scale-text-editing | 2/4 (2 timeouts) | **4/4** | met ✓ (0 timeouts) |
| Success target sanitize-git-repo | 1/4 | 2/4 | met ✓ |
| Litmus watch cancel-async-tasks | 0/4 | 0/4 | unchanged (mechanism orthogonal) |

## Phase-0 graded regrade (post hoc, zero API spend)

`eval/analysis/regrade_arms.py` → `regrade-report.md`:

- Graded: dev-x3 0.8458 [95% CI 0.7500, 0.9333] vs dev-baseline 0.7842
  [CI 0.6767, 0.8817]
- Paired graded delta **+0.0617** [CI −0.0575, +0.1783], Wilcoxon W=32.5,
  **p=0.3613** — inside the calibrated ±0.105 noise band; NS.
- Per-task graded gains concentrated where the mechanism hit
  (large-scale-text-editing +0.250, fix-git +0.250, git-multibranch +0.250);
  cancel-async-tasks graded −0.167 (0/4 binary both arms).

## Verdict

**KILL — cost breach.** X3 converted 4 trials (28/40) at 1.317× baseline
mean cost, blowing both the 1.05× pre-registered kill threshold ($0.0923)
and the 1.10× promotion cap ($0.0967). The graded regrade confirms the
binary +0.100 delta was NOT a real effect killed by the underpowered metric:
+0.062 graded, Wilcoxon p=0.3613, inside the noise band. X3 is not
resurrected. Cost disease is the same failure mode as prompt-L1 (1.386×) and
prompt-X2's mild +4.3%: always-on prompt directives that tell haiku-4.5 to
be cheaper make it *do more work*, not less.

Learning recorded in `ledger.md`: the one success worth keeping is
mechanism-level (large-scale-text-editing 2 timeout-fails → 4/4 with 0
timeouts under the "switch after ≤3 failed attempts / no speculative reads"
directive) but it is not payable at 1.317× on a per-trial cost basis; a
deterministic delivery (hook, fired only on detected thrash) would be the
only admissible form — this motivates the H-series (H1 Stop-gate, H3
maxTurns) in loop v2.

Superseded by: `regrade-report.md` (graded + binary side by side),
`ledger.md` (Phase-0 regrade + H-series rows).
