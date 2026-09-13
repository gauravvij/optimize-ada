# Variance Probe — Run-to-Run Variance & Required k

**Job**: `eval/jobs/variance-probe/` — 3 tasks × 3 repeats, reference `claude-code` agent arm only, model `claude-haiku-4-5`, CLI 2.1.258, n-concurrent 2. 9/9 trials completed, 0 exceptions, 16m1s wall.

## Variance table

| task | n | cost mean ($) | cost CV | duration mean (s) | duration CV | pass (3 runs) |
|---|---|---|---|---|---|---|
| fix-git | 3 | 0.0430 | 0.161 | 161.0 | 0.045 | 0/1/1 |
| regex-log | 3 | 0.0978 | 0.080 | 247.1 | 0.024 | 0/1/1 |
| sqlite-db-truncate | 3 | 0.0833 | 0.329 | 195.2 | 0.103 | 0/0/0 |
| **mean** | | | **0.190** | | **0.058** | |

- **Cost CV** (0.08–0.33, mean 0.19) is the dominant variance source — driven by
  variable agent trajectories (turn counts differ run-to-run), not infra noise.
- **Duration CV** (0.02–0.10, mean 0.058) is small — wall-clock is stable.
- **Pass variance is real and estimable**: fix-git and regex-log flipped 0↔1
  across repeats (2/3 and 1/3 pass rates). sqlite-db-truncate floored 0/3 on
  haiku — a capability floor, consistent with the Ada-arm observation (9/10
  rows recovered but verifier requires all 10).

## Required k derivation (pre-registered formula)

For a paired A/B with per-run CV c and k repeats per arm, SE of per-task mean
≈ c·mean/√k. Detectable-effect targets: 20% cost delta, 25% duration delta.

- k_cost = (1.96 · 0.190 / 0.20)² = 3.46
- k_dur  = (1.96 · 0.058 / 0.25)² = 0.20
- **REQUIRED k = 4** (ceil of max, min 2)

Pass-rate deltas are judged at the aggregate 15-task level with McNemar's test
(paired), so per-task k=4 also gives pass-rate resolution of 0.25 per task.

## Implications for the baseline (subtask 5)

- Baseline = 15 tasks × 2 arms × 4 repeats = 120 runs.
- Estimated cost: reference-arm mean ≈ $0.075/run → 15×4×0.075 ≈ $4.5 for arm A;
  Ada-arm similar or higher (bridge adds ~$0.017/session fixed cache overhead)
  → total baseline ≈ $10–15. Well within budget.
- Wall-clock estimate: ~200 s/run ÷ 2 concurrent ≈ 120 runs × 100 s ≈ 3.3 h.
- Task selection must avoid haiku-floor tasks (like sqlite-db-truncate: 0/3
  reference, 0/1 Ada) — prefer tasks with mixed outcomes; fix-git and
  regex-log are confirmed measurable.
