# Dev-loop X1r decision — verify-once repackage (trimmed + bounded + output-cap composition)

Job: `dev-x1r` · Arm: `dev-x1r` · Lever: `ADA_VERIFY_ONCE_TRIMMED=1` +
`ADA_HOOK_OUTPUT_CAP=3000` (env-gated `verifyOnceTrimmedGuidance` in
`ada/agent/lever-guidance.ts`, wired into `systemPromptAppend` in `index.ts`;
output-cap via the proven H2 hook seam in `claude/agent.ts`) · Model:
`anthropic/claude-haiku-4-5` · Dataset: `terminal-bench@2.0`, 10 dev tasks ×
k=4 = 40 trials · Run: Sep 5, 1h07m52s foreground (no timeout) · Results:
`eval/results/dev-x1r.jsonl` (40 records, arm=`dev-x1r`, 39 cost-bearing,
1 AgentTimeoutError on large-scale-text-editing) · Analysis:
`eval/analysis/analyze_dev_x1r.py`

Reference arm: FRESH `dev-baseline` (`eval/results/dev-baseline.jsonl`,
24/40 = 0.600, graded 0.7842, mean cost $0.0879). Comparisons are
position-based within task (the `trial` field is not comparable across arms).

## Hypothesis (pre-registered, ledger.md)

X1 is the campaign's only statistically significant graded effect
(+0.122, Wilcoxon p=0.016) — killed on COST (1.386× = $0.1218/trial vs the
$0.0967 gate). X1r re-delivers the same verify-once mechanism inside the gate
by attacking the three measured cost drivers: (a) an ALREADY-EXECUTED
EXEMPTION ("if you have ALREADY run the deliverable during this session and
observed it working, finish immediately — do not re-verify") kills the
redundant re-verification on already-solving tasks (fix-code-vulnerability
+15.7 turns, $0.069/trial, zero gain); (b) a HARD RUN BUDGET ("at most 2
verification runs — fix once, re-run once") kills the regex-log fix-loop
cascade (2→19 turns, +$0.608); (c) `ADA_HOOK_OUTPUT_CAP=3000` cuts the
turn-driven cache-read re-feed. Driver (c) of X1 — cancel-async-tasks
(2.8→9.0 turns, 0/4→0/4) — was pre-accepted as residual waste. Projected cost
$0.09–0.105 (TIGHT vs $0.0967); projected graded Δ ≈ +0.095.

## Results vs pre-registered FROZEN criteria (ledger.md)

| Criterion | Baseline | X1r | Result |
|---|---|---|---|
| Graded paired mean (40 pairs) | 0.7842 | **0.8400** | Δ **+0.0558** |
| Graded kill (a): Δ ≥ +0.05 | — | +0.0558 | **PASS** on magnitude |
| Graded kill (a): Wilcoxon two-sided p < 0.05 | — | **p = 0.3601** (stat 44.0) | **FAIL** |
| Binary pass | 24/40 = 0.600 | **29/40 = 0.725** | Δ +0.125 (≥ 24/40 PASS) |
| Position-based McNemar | — | 19 both-pass, 6 both-fail, 5 base-only, **10 X1r-only** | two-sided exact p = 0.3018 (not significant) |
| Guards (fix-code-vulnerability, git-leak-recovery) | 8/8 | **7/8** | **FAIL** (fix-code-vulnerability 4/4 → 3/4) |
| Mean cost (suite cost-bearing) | $0.0879 (n=38) | **$0.1005 (n=39)** | ratio **1.144** → > $0.0967 **FAIL** |
| Mean cost (9 tasks, excl. large-scale-text-editing — both arms timeout-prone) | $0.0794 (n=36) | $0.0891 (n=36) | ratio 1.122 → > 1.10×$0.0794 = $0.0873 **FAIL** (transparency) |
| Treatment reach (directive marker in bridge logs) | — | **40/40 = 100%** | PASS (≥ 95%) |
| Mechanism firing | — | 716 `[hook:cap] PostToolUse` lines; **46 truncations at cap=3000** across 13/40 trials | PASS |

## Per-task breakdown

| Task | Base | X1r | Conv (B-only/X1r-only) | costB | costX | ratio | gradB | gradX |
|---|---|---|---|---|---|---|---|---|
| cancel-async-tasks | 0/4 | 2/4 | 0/2 | $0.0221 | $0.0462 | 2.09 | 0.8333 | 0.9167 |
| fix-code-vulnerability | 4/4 | 3/4 | 1/0 | $0.1849 | $0.1359 | 0.74 | 1.0000 | 0.9583 |
| fix-git | 2/4 | 2/4 | 0/0 | $0.0285 | $0.0294 | 1.03 | 0.6250 | 0.6250 |
| git-leak-recovery | 4/4 | 4/4 | 0/0 | $0.0278 | $0.0342 | 1.23 | 1.0000 | 1.0000 |
| git-multibranch | 3/4 | 4/4 | 0/1 | $0.1336 | $0.1964 | 1.47 | 0.7500 | 1.0000 |
| large-scale-text-editing | 2/4 | 3/4 | 0/1 | $0.2398 | $0.2374 | 0.99 | 0.8000 | 0.9000 |
| log-summary-date-ranges | 3/4 | 4/4 | 0/1 | $0.0300 | $0.0322 | 1.07 | 0.8750 | 1.0000 |
| openssl-selfsigned-cert | 3/4 | 4/4 | 0/1 | $0.0439 | $0.0642 | 1.46 | 0.9583 | 1.0000 |
| regex-log | 2/4 | 2/4 | 0/0 | $0.1233 | $0.1418 | 1.15 | 0.5000 | 0.5000 |
| sanitize-git-repo | 1/4 | 1/4 | 0/0 | $0.1209 | $0.1218 | 1.01 | 0.5000 | 0.5000 |

## Mechanism evidence (treatment reach + behavior change)

- **Treatment reach: 40/40 (100%)** bridge logs contain the distinctive X1r
  marker `ALREADY run the deliverable` (0 miss) → genuinely treated. (The
  ≤$0.25 reach probe on fix-code-vulnerability ran first — job
  `dev-x1r-probe`, cost $0.1220665, reward 1.0 — with the marker plus 31
  `[hook:cap]` fires and 3 truncations at cap=3000 in its bridge log; the
  40-trial arm's logs retro-verify the same markers.)
- **Output-cap mechanism fired throughout the arm**: 716 `[hook:cap]
  PostToolUse` lines and 46 truncations at cap=3000 across 13/40 trial logs.
- **Cost drivers attacked — measured outcome**:
  (a) fix-code-vulnerability cost FELL 0.74× ($0.1849 → $0.1359) — the
  exemption killed the redundant re-verify loop as designed — BUT one guard
  pass was lost (4/4 → 3/4): the exemption + cap composition
  over-suppressed verification on the guard task, and this single trial is a
  pre-registered kill.
  (b) regex-log did NOT cascade (turns bounded; cost 1.15×, not 2.23×) but
  also did NOT convert (+0 passes, graded 0.5000 → 0.5000) — the harder run
  budget suppressed the exact iteration that produced X1's +1 there.
  (c) cancel-async-tasks still cost 2.09× with NO residual-waste exemption
  hit ($0.0221 → $0.0462); pass improved 0/4 → 2/4 on graded-similar trials
  (graded 0.8333 → 0.9167) but the two converted trials are not the 4-trial
  story X1 told.
- **Cost repackage verdict**: X1 1.386× → X1r 1.144× (suite cost-bearing);
  also 1.122× on the 9-task transparency set. Improved, but did NOT clear the
  1.10× gate under either convention.
- **Graded effect verdict**: X1 +0.122 (p=0.016) → X1r +0.0558 (p=0.3601).
  The magnitude survived at half-strength but the significance did not — the
  trimmed+bounded+capped delivery diluted the very turns that carried X1's
  graded signal while failing to reclaim enough cost.

## VERDICT: NOT PROMOTED (honest null) — KILL on three independent criteria

Per the pre-registered frozen gate, ANY miss kills. Three criteria fail:

1. **(a) Wilcoxon p = 0.3601 ≥ 0.05** — graded Δ +0.0558 meets the magnitude
   bar but is not statistically distinguishable from noise at n=40.
2. **(c) guards 7/8** — fix-code-vulnerability regressed 4/4 → 3/4 (the
   exemption's own target task); pre-registered "any guard loss" kill.
3. **(d) mean cost $0.1005 (n=39) > $0.0967** — ratio 1.144×; fails the
   suite cost-bearing convention used for every prior decision (X1, H1, H2).
   Fails the 9-task transparency convention too ($0.0891 vs $0.0873).

Passing: binary 29/40 ≥ 24/40 (Δ +0.125, 5-trial net conversion; McNemar
p=0.3018 not significant), reach 40/40 ≥ 95%.

**Phase 2 validation sweep (15 tasks × k=8 × 2 arms, ~$28) MUST NOT run.**
Zero validation spend. No gate relaxation.

**Learning (drives queue):**
1. The verify-once mechanism's cost is NOT fixed by text trimming + output
   capping alone: the turns that carry its graded signal ARE its cost. X1r
   halved the graded effect (+0.122 → +0.0558) and only cut cost 1.386× →
   1.144× — both sides moved, neither crossed its bar.
2. The exemption clause works exactly where X1 wasted money (fix-code-
   vulnerability cost 0.74×) but the guard-pass loss proves the same clause
   can suppress needed verification on the same task — a fix that costs a
   guard pass is a kill regardless of the $ saved.
3. The 2-run budget prevents the regex-log cascade (cost 2.23× → 1.15×) but
   also forfeits the conversion that cascade produced in X1 (regex-log +1
   pass, graded +0.25) — bounding iteration bounds both waste AND repair.
4. cancel-async-tasks remains the clearest uncaptured pool (2.09× cost,
   pass up but McNemar-weak): a lever that adds run-verification ONLY when
   the artifact is runnable-and-unverified, without a repair mandate, has not
   been tried and is the natural successor hypothesis.
5. Campaign-level: every quality lever tested on claude-haiku-4-5 — prompt-
   directive (5 arms) or deterministic hook (H1–H3) or repackaged composite
   (X1r) — fails either significance (all p ≥ 0.30 at n=40 except X1's
   p=0.016) or a hard cost/guard gate. The pass rate on this dev set is
   capability-bound, not process-bound.

Spend: dev-x1r probe ~$0.122 + arm 39 × $0.1005 ≈ $3.92 → **~$4.0 total**.
Cumulative campaign ≈ $70–71 of the $150 cap.

## Provenance (commands + raw counts)

Corrected paired analysis (fix for the x1r-graded-mean indexing bug; x1r row is
pairs index 3 — `for _, _, _, xs in pairs`):
`source venv/bin/activate && python3 eval/analysis/analyze_dev_x1r.py` →
```
Loaded base 40 / x1r 40; paired 40 (10 tasks x 4)
Suite pass: base 24/40=0.600 | x1r 29/40=0.725 | delta +0.125
Graded paired mean: base 0.7842, x1r 0.8400, delta +0.0558
Wilcoxon signed-rank two-sided p = 0.3601 (stat=44.0)
McNemar ... two-sided exact p = 0.3018
Guards: base 8/8, x1r 7/8
Suite cost-bearing mean: base $0.0879 (n=38), x1r $0.1005 (n=39) ratio 1.144
[transparency] 9-task excl. large-scale-text-editing: base $0.0794 (n=36), x1r $0.0891 (n=36) ratio 1.122
>>> PROMOTED: False <<<
```

Treatment-reach grep over all 40 dev-x1r bridge logs
(`eval/jobs/dev-x1r/*/agent/ada-bridge.log`, direct grep):
```
grep -l "ALREADY run the deliverable" eval/jobs/dev-x1r/*/agent/ada-bridge.log | wc -l   -> 40
ls -d eval/jobs/dev-x1r/*/ | wc -l                                                       -> 40
grep -l "truncated (cap 3000)" eval/jobs/dev-x1r/*/agent/ada-bridge.log | wc -l          -> 13
grep -h "\[hook:cap\] PostToolUse" eval/jobs/dev-x1r/*/agent/ada-bridge.log | wc -l      -> 716
grep -h "truncated (cap 3000)" eval/jobs/dev-x1r/*/agent/ada-bridge.log | wc -l          -> 46
```
Reach = 40/40 = 100% ≥ 95% (directive marker in every trial log; cap mechanism
fired in 13/40 trials with 46 truncations).

Reach-probe log (`eval/jobs/dev-x1r-probe/fix-code-vulnerability__D94m5yC/
agent/ada-bridge.log`): marker 1 hit, `[hook:cap] PostToolUse` 31 hits,
`truncated (cap 3000)` 3 hits; job cost $0.1220665 ≤ $0.25 (result.json),
reward 1.0 → probe hard gate PASSED (mechanism fired before the paid arm).
