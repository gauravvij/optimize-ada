# P3 / P2 Pre-Registration — Phase C candidate experiments

Written BEFORE any candidate spend. No candidate results had been observed at the
time of writing (the only completed measurement is the budget probe, whose verdict
MIXED / 7-of-25 is the trigger for this spend, per improvements.md §9 step 3).

## Measured pool

`bench/FAILING25.txt` — the 25 SetupBench tasks that failed in BOTH R9/R10
replicates on the shipped arm (derived mechanically from
`.autoresearch/diagnostics/20260915T0825Z-r{1,2}-best/0.json`, cross-checked
against improvements.md §2). Development evidence only; no generalization claim
is made from this pool. Any promotion is confirmed on remaining81 (Subtask 7).

## Budget probe verdict (the gate to this spend)

MIXED: 7/25 passed at 960 s (24 valid, 0 timeouts). Rule (pre-registered in
plans/plan.md): >=12 SLOW, 4-11 MIXED, <=3 HARD. MIXED means: take the
efficiency work for the subset that converted; still run P3 but expect a
smaller pool. Full table: `bench/BUDGET_PROBE_REPORT.md`.

## P3 — wrap-up instruction fired late (run FIRST)

**Intent (improvements.md §5 P3):** fire the wrap-up directive only after ~80%
of the budget is consumed, so it structurally cannot touch tasks that finish
early. Delivery: "no new code, only a default and a gate flip" in
`agent/claude/agent.ts`.

**Units correction (pre-spend, documented):** the plan text said
`ADA_WRAP_UP_MS ≈ 384000`. That number expresses the 80%-consumed point as
*elapsed* time (0.8 × 480 s = 384 s). The code parameter is a *remaining*-time
window: `timeHintText` fires the wrap-up when `remainingMs <= wrapUpMs`
(agent/claude/agent.ts:86), proven by unit test T1.2 in agent.test.ts
("wrap-up window forced to 200 s on a 60 s budget → remaining ~55 s is inside
the window → directive appears immediately"). Setting 384000 would fire the
wrap-up after only 20% consumed — the exact premature-surrender mode §5
forbids. The intent-faithful value is **96000 ms** (remaining ≤ 96 s of a
480 s budget = 80% consumed). Correction made before any candidate data was
seen; confirmed with the campaign planner on 2026-09-16.

**Candidate edit (both defaults in `agent/claude/agent.ts`, env still overrides):**
1. `timeHintsOn`: default `"0"` → `"1"` (the hint channel must be on for the
   wrap-up sentence to be injected at all).
2. `wrapUpMs` default: `Math.min(150_000, Math.max(60_000, Math.floor(0.2 * taskBudgetMs)))`
   → `Math.floor(0.2 * taskBudgetMs)` (pin exactly 80%-consumed at any budget;
   on 480 s this is 96000 ms).

**Gate (pre-registered, applied mechanically after):**
- Two replicates, same-day, both arms of each replicate concurrent, one driver.
- Keep only if: pooled net ≥ +5 tasks AND no replicate is negative.
- ≤ 3 invalid rows per arm per replicate.
- Report accuracy (passes) and efficiency (turns, duration) separately.

## P2 — Bash timeout clamp alone (run SECOND, only after P3 resolves)

**Candidate edit:** `bashClampOn` default `"0"` → `"1"` in
`agent/claude/agent.ts`; timeHintsOn stays at the P3-resolved default (if P3
was reverted, back to `"0"`). Everything else identical to shipped.
Same gate as P3. Watch clamp-hit counts in a smoke first if time permits.

## Delivery mechanism note

ADA_* env vars do NOT reach the eval container (docker_args in
setupbench_ada_eval.py pass only ADA_TASK / ADA_TASK_ID / ADA_RUNNER_TIMEOUT_MS),
so both candidates are delivered as code-default edits under `agent/` — inside
the mutation boundary — exactly the t12_apply_edits.py pattern. The autoresearch
loop's snapshot/rollback protects the shipped tree; the git tag
`ada-best-61pct-20260916` (both trees) is the one-command revert.

## Measurement protocol

- Config: `autoresearcher/config-ada25.toml` (evaluation mode `repeated`,
  2 baseline + 2 candidate repetitions, aggregate median).
- Measured command: domain eval with `--tasks-file bench/FAILING25.txt`,
  480 s task timeout, 600 s grader, concurrency 2, seed 20260907.
- Baseline arm = shipped build (agent tree dab704de524a, tag ada-best-61pct-20260916).
- Diagnostics land in `targets/ada/.autoresearch/diagnostics/<run_id>/` with
  attempt-number suffixes so repetitions do not overwrite each other.
- Gate decision is applied manually from the diagnostics (the loop's internal
  gate is a coarse maximize; the pre-registered pooled-net rule above governs).