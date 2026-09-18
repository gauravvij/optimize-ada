# Ada Agent — Optimization Results

> **Re-check — 2026-09-18.** This record is left as written below. Checked against the raw rows,
> some statements in it do not hold or cannot be confirmed. The date of the withdrawn control R3 is uncertain: its run ID
> says 2026-09-10, but the commit it records is dated 2026-09-11. Phase C's "zero 480 s clock-outs" means no harness
> kills; the watchdog still interrupted 28 of the shipped build's 41 P3 failures. P2 was only ever
> measured inside the T1.2 bundle. The evidence for each point is in the repository README, under "Re-checked against the raw data".

> **Campaign record — last updated 2026-09-16**
>
> This file records what was changed, what was measured, and what the measurements do and
> do not support, for the optimization of **Ada**, a TypeScript coding agent
> (`ada/`, the canonical repository) running `z-ai/glm-5.3-flash` through
> OpenRouter on `@anthropic-ai/claude-agent-sdk`, graded by official task checkers in
> Docker on **SetupBench** (81 software-setup tasks) and **Terminal-Bench 2.0** (40 public
> tasks).
>
> Every number below traces to an artifact on disk. The narrative companion to this file is
> [`REPORT.md`](REPORT.md). The working roadmap (`fina_run.md`) that governed the campaign
> was removed during final packaging (2026-09-18); its rules and verdicts are recorded in
> this file, [`REPORT.md`](REPORT.md), and `../bench/RUN_REGISTRY.md`.

---

## Versions — the canonical lineage

This repository is the single canonical tree since 2026-09-18 (the former byte-identical
mirror was removed then; both pointed at agent tree `dab704de524a`). Every build below
resolves in this repo via `git rev-parse`.

| Role | Commit | Agent tree (`git rev-parse <c>:agent`) | Same-day score | Disposition |
|---|---|---|---|---|
| Campaign origin (baseline) | `df0c537` | `6ec0446cfc7d` | 34/81 (R5) | measured anchor |
| + T0.1 watchdog | `6672af8` | `7958654244eb` | **54/81** (R7) | kept — the evidence-supported mechanism |
| + T1.2 time-awareness bundle | `2e495bb` | `4267fee64dcc` | 50/81 (R8) | **promotion withdrawn** — ships default off |
| **Shipped build** (= tag `ada-best-61pct-20260916` → this repo @ `32f4754`) | `5f4c5c0` | `dab704de524a` | **98/157 pooled** (R9+R10) | **SHIPPED** |
| P3 late wrap-up (rejected candidate) | branch `p3-late-wrapup` @ `9f2e34d` | `811a16e4a67e` | +2 pooled on FAILING25, p = 0.6875 | **REJECTED — REVERT**; branch preserved in this repo |

The shipped build is `2e495bb` with both T1.2 gates flipped default off, so its runtime
behaviour is `6672af8`'s; it was measured under its own name in R9/R10.

## Baseline vs shipped build — head to head

Everything in this table comes from the 2026-09-15 confirmation run (**R9 + R10**): the same
81 SetupBench tasks, run twice per build, both arms of a replicate running concurrently on one
machine — **162 task-runs per build**. Nothing but the build differs.

| Metric | Baseline `df0c537` | **Shipped `5f4c5c0`** | Change |
|---|---:|---:|---|
| **Tasks passed** (162 runs) | 68 (42.0%) | **99 (61.1%)** | **+31 tasks, +19.1 pts, +46% relative** |
| Paired result, evaluable runs | 67/157 | **98/157** | **net +31**, 32 gained / 1 lost, exact McNemar **p = 7.92e-09** |
| Per replicate (R9, R10) | 32/81, 36/81 | **47/81, 52/81** | +16 (p = 1.45e-04), +15 (p = 6.10e-05) |
| **Killed before grading** (zero turns) | 86 | **3** | **−83** — this is the entire mechanism |
| Timed out | 84 | **0** | −84 |
| Interrupted at the deadline, then graded | — (killed instead) | 69 | the partial work now counts |
| **Turns, total** | 1,386 | 2,825 | +104% — the agent actually gets to work |
| Turns, median per task | 0 | 17 | the baseline's median run never took a turn |
| **Latency, mean per task** | 406 s | **383 s** | −6% |
| Latency, median per task | 485 s | 417 s | −14% |
| Latency on tasks that passed | 313 s mean / 299 s median | 333 s mean / 313 s median | +6% — passing takes slightly longer |
| **Total wall time** (162 runs) | 18.3 h | **17.2 h** | −6% |
| Invalid rows (excluded from pairing) | 3 | 2 | — |
| Tasks still failing | 94/162 | 63/162 | −31 |
| **Cost** | *not captured* | *not captured* | the harness records no tokens or spend; see below |

**Where the +31 comes from.** Split the 157 paired evaluable runs by what the baseline did:

| Baseline behaviour | n | Baseline passed | Shipped passed | Verdict |
|---|---:|---:|---:|---|
| **Hung with zero turns**, hard-killed before grading | 82 | 0 | **28** | the whole gain, p = 7.45e-09 |
| Ran normally | 75 | 67 | 70 | no real difference, p = 0.375 |

So the shipped build is **not a more capable agent**. It stops being killed mid-flight, its
partial work reaches the grader, and that alone is worth 46% more passed tasks — at slightly
*less* wall time than the baseline spends dying.

**On cost.** The eval harness writes no token counts and no spend into its diagnostics, so no
per-run cost exists for R9/R10 — the `≈ $9.5` and `≈ $7.5` figures below were read off the
OpenRouter dashboard by hand at the time. To have it next time, record the account balance
either side of a run, or add usage capture to `setupbench_ada_eval.py`.

## The confirmed result — read this before anything below it

**The shipped build is worth +31 tasks over the campaign-origin build, confirmed on
2026-09-15 by a two-replicate run that was pre-registered before it was spent**
(`../bench/RUN_REGISTRY.md` runs **R9 / R10**, artifact
`../bench/BASELINE_VS_BEST_20260915T0825Z.json`, machine check
`../bench/baseline_vs_best_verify.py`):

| Replicate | n evaluable | `df0c537` | shipped build | Gained / lost | Exact McNemar |
|---|---:|---:|---:|---:|---|
| R9 (08:25 UTC) | 79 | 31 | **47** | 17 / 1 | p = 1.45e-04 |
| R10 (12:11 UTC) | 78 | 36 | **51** | 15 / 0 | p = 6.10e-05 |
| **Pooled** | **157** | **67** | **98** | **32 / 1** | **p = 7.92e-09** |

The rule, fixed before any spend: every replicate completes with both diagnostics; each
replicate net ≥ +10; ≤ 3 invalid rows per arm per replicate; pooled exact McNemar p < 0.001.
All four are met — **VERDICT: HOLDS**. Both arms of each replicate ran concurrently on one
machine with the same runner, grader, task list, 480 s task budget and model, so nothing but
the build differs.

**This is the build that ships**, `5f4c5c0` — the T0.1 watchdog with both T1.2 gates default
off — measured under its own name rather than inferred from `6672af8`.

**The 2026-09-12 same-day ladder still stands** and is consistent with this
(`../bench/CTRL_VS_T12_REPORT.md`, runs **R5 / R7 / R8**):

| Build | What it adds | Pass | Paired against the row above |
|---|---|---:|---|
| `df0c537` | campaign origin, no watchdog | 34/81 | — |
| `6672af8` | **+ T0.1** watchdog, container-anchored deadline, clean exit | **54/81** | **+20 net**, 21 gained / 1 lost, **p = 1.097e-05**, CI [+9.36, +38.46] |
| `2e495bb` | **+ T1.2** time hints, wrap-up instruction, Bash clamp | 50/81 | **−4 net**, 5 gained / 9 lost, **p = 0.424**, CI [−19.26, +9.67] |

`2e495bb` is `6672af8` plus T1.2 and nothing else, so the third row is the only measurement
ever made in which the time-awareness bundle is the sole variable. It does not meet its
pre-registered bar of ≥ +3 net conversions, so **T1.2 was not promoted and ships default off**.
It is not evidence of harm either: 14 discordant on n=81 is inside the noise floor. T1.2's own
mechanism metrics all moved as designed — runs interrupted at the deadline **34 → 7**, turns
**−10.6%**, wall time −5.0% — which is an **efficiency result** and is reported as one,
separately, because blending it with an accuracy claim is what produced the retraction below.

## Phase C (2026-09-16 → 09-17) — budget probe and targeted candidates: nothing promoted

Phase C asked the question the confirmation run left open: **are the 25 consistently-failing
tasks slow, or hard?** The answer, from measured runs only: **mostly hard.** No candidate
cleared its pre-registered gate; the shipped build is unchanged.

| Step | Verdict | Measured evidence |
|---|---|---|
| **Budget probe** (P1) — the 25 consistent failures at 960 s, shipped build | **MIXED — 7/25 pass** | `budget-probe-20260916T0730Z`: 7 pass / 25 rows (24 valid, 0 timeouts), 5 h 05 m. Pre-registered rule: ≥12 SLOW / 4–11 MIXED / ≤3 HARD. Report: `../bench/BUDGET_PROBE_REPORT.md` |
| **P3** late wrap-up (time hints default ON, `ADA_WRAP_UP_MS` = 96 s remaining) | **TESTED AND REJECTED — REVERT** | Paired 2-replicate run `20260917T0602Z` vs shipped, 480 s, FAILING25 pool: pooled net **+2** (6/46 → 8/46), rep 1 **−1** (p = 1.0), rep 2 +3 (p = 0.25), exact McNemar p = 0.6875. Pre-registered gate (pooled net ≥ +5 AND no negative replicate) failed on both clauses. Zero 480 s clock-outs in either arm, either replicate. Report: `../bench/P3_PAIRED_REPORT.md` |
| **P2** Bash timeout clamp alone | **DROPPED — no spend** | The paired diagnostics show zero 480 s clock-outs on this pool in both arms and both replicates, and the probe showed most failures are grader-fails, not clock-outs. No clock-out population remains for the clamp to save. |
| **P4** install-cheapening PreToolUse hook | **DROPPED — no spend** | Same zero-clock-out evidence: seconds saved on installs do not convert into passes on this pool. The pre-registered smoke bar (≥ 30 s/task saved) is moot. |
| **P5** verification stop-hook | **DEFERRED** | Per plan, only after the clock pool is exhausted; never reached this phase, no spend made. |

A first P3 attempt (`20260916T1340Z`) was **voided by a host reboot** (~14:49 UTC Sep 16,
killed mid-replicate-1 at 8/25 partial rows) — that data is excluded and must not be quoted.

**Disposition.** The shipped best is unchanged: tag `ada-best-61pct-20260916`
(this repository @ `32f4754`, agent tree `dab704de524a`, clean; the byte-identical former
mirror — historical pin `c6f917e` — was removed 2026-09-18). Doubling the
budget converts only 7/25 of the failure pool, and the one mechanism-level candidate that
targeted the interrupted population moved +2 — inside the noise floor (p = 0.69). The
remaining gap on this model is capability, not scaffolding. Full ledger with run IDs:
`../bench/PHASE_C_SUMMARY.md`; run rows in `../bench/RUN_REGISTRY.md` (Phase C section).

## Retracted numbers — do not quote

Three figures this project published and then withdrew. They are listed here so the record
shows what was claimed, and nowhere else in this document as live results. The T1.2
time-awareness bundle was promoted on the first of them. **That promotion is withdrawn.**

| Figure | Why it is void |
|---|---|
| ~~52/81 vs 24/81~~, ~~net +28, p = 7.66e-07~~ (T1.2 promoted) | **WITHDRAWN** 2026-09-13. Its control (R3) was a depressed run: the same build scores 54/81 two days later, 30 gained / 0 lost, **p = 1.863e-09**. The pairing measured the day, not the change. Re-measured same-day, T1.2 is −4. |
| 59/81 (73%) Phase A headline | **superseded** — assembled from 50 carried-over scores plus 31 fresh ones, not a single fresh run; it **should not be quoted** as one. Run whole, the lineage measures 54/81 against 34/81. |
| 26/40 vs 28/40 Terminal-Bench | corrected to 26/38 vs 26/38 (p = 1.0) after two trials were identified as verifier-infrastructure failures, not agent failures. |

Cross-day pairing is inadmissible on this harness; it produced both retractions. Every
headline above comes from arms run together, on one machine, under one driver.

---

## Executive result

Two campaigns ran. The first fixed how the agent uses time; the second fixed how the agent
*knows* about time. Only the first produced a gain, and that gain is now confirmed on a
second day by a pre-registered two-replicate run. Every row below is a live result measured
from arms run together; the figures this project retracted are listed above, once, and are
not repeated here.

| Comparison | Runs | Baseline | Final | Statistics |
|---|---|---:|---:|---|
| **Confirmation, shipped build** — `df0c537` → `5f4c5c0` | **R9 + R10**, 2026-09-15 | 67/157 (42.7%) | **98/157 (62.4%)** | net **+31**, 32 gained / 1 lost, exact McNemar **p = 7.92e-09**; per replicate +16 (p = 1.45e-04) and +15 (p = 6.10e-05) — pre-registered rule **HOLDS** |
| **Same-day paired, watchdog** — `df0c537` → `6672af8` | R5 → R7 | 34/81 (42.0%) | **54/81 (66.7%)** | net **+20**, 21 gained / 1 lost, exact McNemar **p = 1.097e-05**, Newcombe 95% CI **[+9.36, +38.46]** |
| **Same-day paired, time hints** — `6672af8` → `2e495bb` | R7 → R8 | 54/81 (66.7%) | 50/81 (61.7%) | net **−4**, 5 gained / 9 lost, **p = 0.424**, CI **[−19.26, +9.67]** — promotion bar not met |
| Same-day paired, both changes — `df0c537` → `2e495bb` | R5 → R8 | 34/81 | 50/81 | net +16, p = 0.001544, CI [+4.37, +33.88] |
| External Terminal-Bench (n=38 evaluable) | — | 26/38 (68%) | 26/38 (68%) | p = 1.0 — pass-rate gain did **not** reproduce externally |

Supporting measurements on the settled same-day pair (R7 → R8): total turns **1554 → 1389**
(−10.6%), summed wall time **29,353 s → 27,881 s** (−5.0%), runs interrupted at the deadline
**34 → 7**, timeouts **0 → 0**, invalid rows **0 → 0**.

## What the change was

The Phase B change (**T1.2, "time-awareness bundle"**; promoted, then withdrawn) adds three env-gated mechanisms to
`agent/claude/agent.ts`:

1. **Time hints.** Before every model request, a `PostToolBatch` hook injects
   `⏱ N s of M s remain.` (~20 tokens). The budget string previously existed only at
   t=0; the model ran the whole task blind to the clock.
2. **A wrap-up instruction.** When remaining time drops below a threshold
   (default `min(150 s, max(60 s, 0.2 × budget))` — 96 s on a 480 s task), the hint
   becomes: stop exploring, make the stated success command pass now, reply and stop. It
   also states that an interrupted tool call is the time budget ending — not a user
   refusal.
3. **Bash timeout clamping.** A `PreToolUse` hook caps any Bash call's timeout at
   `max(5 s, remaining − 20 s)`, so a `sleep 300` can never silently consume the budget.

Gates: `ADA_TIME_HINTS`, `ADA_BASH_CLAMP_REMAINING` (default **on** in `2e495bb`,
**off** since `5f4c5c0` — the shipped build is opt-in), `ADA_DEADLINE_ANCHOR`, `ADA_WRAP_UP_MS`, `ADA_BASH_CLAMP_MARGIN_MS`. The earlier
T1.1 prompt gate `ADA_PROMPT_DOD` ships default **off** (see below).

## Build lineage

Historically the build lived in two byte-identical trees; the mirror was removed on
2026-09-18 and this repository (`ada/`) is canonical. Commits below are listed as
`ada / former-mirror`.

| Commit(s) | What | Verdict |
|---|---|---|
| `df0c537` | Baseline surface: system-guidance + eval runner | — |
| `08a8d5d` (tag `ada-final-59of81`) | Phase A final: watchdog, container-anchored clock, thinking cap | hybrid 59/81; superseded as a comparison anchor |
| `6672af8` / `174ae4d` | T0.1: clean exit after watchdog interrupt (bug fix) | kept — fixes force-kill and turns=0 artifacts |
| `97a65ca` / `61f0f50` | T1.1: definition-of-done prompt, default on | **NOT PROMOTED** |
| `fe4bf39` / `154e713` | T1.1 default flipped **off** | kept |
| `6672af8` / `174ae4d` — measured alone as run **R7** | the build the evidence supports | **54/81 same-day** |
| `a0c36ed` + `2e495bb` / `30efd16` + `571fd2d` | **T1.2: time-awareness bundle** | ~~PROMOTED~~ → **PROMOTION WITHDRAWN** 2026-09-13 |
| `3e0645f` / `5f4c5c0` | T1.2 gates flipped **default off** — shipped default ≡ `6672af8` behaviour | kept |
| `df4f878` / `9934a93` | T1.2 evidence committed (`evidence/t12/`, 10 files) | — |

## The paired evaluation ladder (T1.2), as run — and as it now reads

Protocol (campaign spec §3, `fina_run.md` — removed 2026-09-18): paired arms, identical conditions (480 s task / 600 s grader,
concurrency 4, seed 20260907), exact McNemar on the flip table, Newcombe 95% CI, early stop
if a rung is negative, promotion only on **no significant regression AND ≥ +3 net conversions
on remaining81**. Control arm: the T0.1 build @ `6672af8`.

| Rung | Runs | Candidate | Control | Regressions (b) | Conversions (c) | Exact McNemar p | Newcombe 95% CI |
|---|---|---:|---:|---:|---:|---:|---|
| dev-12 | — | 6/12 | 5/12 | 0 | 1 | 1.0 | [−0.278, +0.416] |
| validation-12 | — | 8/12 | 6/12 | 1 | 3 | 0.625 | [−0.203, +0.481] |
| ~~remaining81, cross-day~~ | ~~R3 → R4~~ | ~~52/81~~ | ~~24/81~~ | ~~3~~ | ~~31~~ | ~~7.66e-07~~ | ~~[+0.193, +0.476]~~ |
| **remaining81, same-day** | **R7 → R8** | **50/81** | **54/81** | **9** | **5** | **0.424** | **[−0.193, +0.097]** |

The struck row is the measurement that promoted the change. It compared a candidate run on
2026-09-11 against a control run on 2026-09-10, and the control was depressed: the same
`6672af8` tree scores 54/81 on 2026-09-12 (30 gained, 0 lost, p = 1.863e-09). The bottom row
replaces it — same day, one driver, one machine, T1.2 the sole variable.

**Rule-4 check, restated on the sound measurement:** no significant regression ✅ (p = 0.424);
≥ +3 net conversions ❌ (**−4**). → **not promoted.**

The n=12 rungs were non-negative but ±2–3 tasks is noise on n=12, so neither ever carried the
decision. Flip-table detail for the withdrawn cross-day run is preserved unchanged in
[`evidence/t12/T12_REM81_PAIRED_ANALYSIS.json`](evidence/t12/T12_REM81_PAIRED_ANALYSIS.json);
it is an accurate record of two runs that should not have been paired.

## What was tried and not promoted

Negative results are recorded, not buried:

| Candidate | Result | Verdict |
|---|---|---|
| **T1.1** definition-of-done prompt (grading-contract instructions) | E3 smoke 0/10 conversions; dev-12 **2/12 vs 3/12** (b=0, c=1, p=1.0) | **HOLD** — provably delivered (byte-identity tests) but behaviorally inert on this model; default off |
| **T1.3** thinking suppression | Probe: no SDK-layer option suppresses reasoning below ~274–452 tokens; the gateway 400s on `thinking: disabled`; raw-layer `budget_tokens` works (41→7 tokens) but is unreachable through the SDK path | **NO-GO** — dropped before any eval spend |
| **Stall-retry** (auto-retry stalled thinking streams, default-on) | dev-12 5/12 vs prior 6/12; detector cannot fire on the observed failures anyway | **REVERTED** — made opt-in, default off |
| **T1.4** resume after transient provider error | not started | pending |

The lesson both negatives point to: **prompt-only interventions are inert on
`z-ai/glm-5.3-flash`**; the levers that move results act through the SDK hook surface.

## Honest caveats — and how each one turned out

The first three were recorded when T1.2 was promoted. Two of them are the reason it is no
longer promoted.

1. **Silent injection.** `PostToolBatch` `additionalContext` never surfaces as a trace
   `user` event — that half of the smoke criterion is unachievable by SDK design. Delivery
   is proven behaviorally instead: the model quoted the hint verbatim in its final text
   ([`evidence/t12/T12_SMOKE_RESULTS.json`](evidence/t12/T12_SMOKE_RESULTS.json)).
   *Status: stands. The mechanism is delivered; that was never the problem.*
2. **Sequential arms.** ⚠️ **This one was fatal.** The control was a stored run from the
   previous day. The cost was flagged as ~20% per-task churn; the actual cost was larger and
   directional — the same build measures 24/81 and 54/81 on two days (30 gained, 0 lost,
   p = 1.863e-09). Cross-day pairing is now inadmissible on this harness, and the promoted
   result was withdrawn on exactly this ground.
3. **One mechanism metric moved opposite.** ⚠️ **This one was the signal.** Early-stop-with-
   unused-budget went up (6 candidate tasks vs 0 control) and was recorded as a tolerable
   side effect of a large win. With the win gone, it is the effect: on the same-day pair, the
   47 tasks where the control finished cleanly with budget left go **42/47 → 37/47**, and
   three of the nine lost tasks ended with >40% of budget unused. `ADA_WRAP_UP_MS` is the
   knob, and premature give-up is not a footnote on this change — it is its measured cost.
4. **Verification discipline is the biggest remaining gap, and T1.2 widens it.** On the
   same-day pair, **25 of the candidate's 31 failures** ended with the agent finishing
   cleanly — believing it was done — while the grader's command failed; the control's figure
   is **5 of 27**. This replicates the 26-of-29 measured on the withdrawn run. T1.2 does not
   make Ada finish more tasks; it makes Ada *declare* more tasks finished. This is the
   largest remaining pool of headroom in the campaign.
5. **31/81 tasks still fail** on `2e495bb`, 27/81 on `6672af8`, and 34/81 then 29/81 on the
   shipped build in the two confirmation replicates. Nothing measured here makes Ada more
   capable: where the baseline could run at all, the shipped build is 70/75 against 67/75
   (p = 0.375).
6. **The shipped build is now measured directly** (R9/R10, 2026-09-15): 47/81 and 52/81
   against the origin build's 32/81 and 36/81. Until then its equivalence to `6672af8` rested
   on the code path and the 25/25 unit tests; it no longer does.

## Claims this evidence supports — and does not

**Supported:**
- **The shipped build is worth +31 tasks against the campaign origin**, pre-registered,
  two replicates, same day, 67/157 → 98/157, p = 7.92e-09 (R9/R10). All of it is hang
  conversion: 0/82 → 28/82 where the baseline produced zero turns, and 67/75 → 70/75
  (p = 0.375) where it ran.
- **The T0.1 watchdog is worth +20 tasks** on remaining81, same-day paired (34/81 → 54/81,
  21 gained / 1 lost, p = 1.097e-05), and all of it comes from removing 46 zero-turn hangs:
  0/46 → 21/46, p = 9.5e-07.
- **T1.2 delivers its mechanism**: interrupted runs 34 → 7, turns −10.6%, wall time −5.0%;
  reproducible in smoke (hint quoted verbatim; clamp landed at 20,000 ms against a requested
  300,000 ms); protected by 25/25 unit tests.
- Phase A's efficiency gains carried to the external benchmark: −39% turns, −35% execution
  time on the whole n=38 run; −36% time and −12% cost on the 23 jointly-passed tasks.
- Cross-day pairing is not viable on this harness. Same build, two days: 24/81 and 54/81.

**Not supported:**
- **T1.2 does not improve pass rate.** Same-day, it is −4 (p = 0.424, CI [−19.3, +9.7]).
  The pre-registered promotion bar of ≥ +3 net conversions is not met.
- **The withdrawn `52/81 vs 24/81, +28, p = 7.66e-07` must not be quoted.** Its control is a
  depressed run.
- **T1.2 is not shown to be harmful either.** 14 discordant on n=81 is inside the noise floor.
- No external pass-rate gain: Terminal-Bench was a dead tie (26/38 vs 26/38, p = 1.0), and it
  measured `08a8d5d` — no build since has been run outside SetupBench.
- The historical 59/81 (73%) figure is **not** a fresh measurement and should not be quoted
  as one.
- Nothing here claims the agent is more *capable*. On the 35 tasks the pre-watchdog build
  could run at all, it scores 34/35 and no later build has beaten that.

## Measurement hygiene (what makes these numbers trustworthy)

- **Same-day paired arms only.** Every headline in this document now comes from two arms run
  by one driver on one machine on one day. Cross-day pairing produced both of this campaign's
  retracted numbers and is no longer admissible.
- **One canonical run index.** Eight full 81-task runs exist across five days and three
  builds; `../bench/RUN_REGISTRY.md` lists all of them with their build, date, score and
  artifact, and states which pairings are legitimate. No document names "the control" without
  naming a run ID.
- **Paired statistics everywhere**: exact McNemar and Newcombe CI on every comparison; no
  decision on n=12 rungs (±2–3 tasks is noise there).
- **A measured noise floor.** Identical code, consecutive runs: 10–13 discordant tasks on
  n≈80 with the aggregate unchanged. Anything at or below that cannot carry a decision.
- **Two headlines have been retracted by this project, unprompted** — the Phase A 59/81
  (assembled from carried scores) and the Phase B +28 (measured against a depressed control).
  Both are left visible and marked rather than deleted.
- **Unevaluable trials excluded**: the external endpoint was corrected from 26/40 vs 28/40
  to **26/38 vs 26/38** after two qemu trials were identified as verifier-infrastructure
  failures (apt 404 / missing curl), not agent failures.
- **Machine-checked reporting**: `../bench/ctrl_vs_t12_verify.py` re-derives every figure in
  the settled result and the run registry from the raw diagnostics, recomputes exact McNemar
  independently, and asserts that the withdrawn numbers are not quoted live in this document
  or any other. `../bench/harness/archive_integrity_check.py` covers the archived runs
  (it supersedes the former `final_verify_final81.py`, removed during packaging).
- **Security**: all five shipped tarballs were rebuilt without `./.env` (a live API key was
  previously shipped into every task container); 0 `.env` entries verified in each.

## Cost

- Phase B cycle (T0.4 control + T1.1 + T1.2 ladders): **≈ $9.5 metered**.
- Phase A: ≈ $7.5 API for SetupBench work; ≈ $37 agent-reported for the external
  Terminal-Bench run (agent-reported figures are ~67× inflated vs metered on this
  gateway; the metered number is authoritative where both exist).

## Audit checklist

- [x] The headline is a **pre-registered, two-replicate confirmation run** whose rule was
      fixed before spend and re-applied mechanically (`../bench/baseline_vs_best_verify.py`).
- [x] Every comparison is paired, same-conditions, with exact McNemar + Newcombe CI.
- [x] The pre-registered promotion rule was re-applied to the sound measurement, and the
      promotion **lapsed** rather than being defended (−4 against a bar of ≥ +3).
- [x] The withdrawn `52/81 vs 24/81 / +28 / p = 7.66e-07` is struck through and labelled
      everywhere it appears, not silently deleted.
- [x] The stale 59/81 headline explicitly superseded, not silently dropped.
- [x] Negative results (T1.1, T1.3, stall-retry) recorded with their evidence.
- [x] Efficiency results and accuracy results reported separately, never blended.
- [x] Every run named by an ID from `../bench/RUN_REGISTRY.md`.
- [x] Both trees byte-identical; evidence committed in both with mirror messages.
- [x] `../bench/ctrl_vs_t12_verify.py` and `../bench/harness/archive_integrity_check.py` both green.
- [x] Known deviations from protocol recorded rather than buried — and the one that mattered
      (cross-day arms) is now the stated reason the promotion was withdrawn.

## Primary artifact paths

**In this repository** — these can be opened directly, and every number in the sections
above is derivable from them:

| Item | Path |
|---|---|
| **The confirmation run** (R9/R10, per-task rows, pooled contrast and decomposition) | [`evidence/confirm/BASELINE_VS_BEST_20260915T0825Z.json`](evidence/confirm/BASELINE_VS_BEST_20260915T0825Z.json) |
| Its machine verification (re-derives every figure from the raw diagnostics; exit 0) | [`evidence/confirm/baseline_vs_best_verify.py`](evidence/confirm/baseline_vs_best_verify.py) |
| The analysis script that produced it | [`evidence/confirm/baseline_vs_best_analysis.py`](evidence/confirm/baseline_vs_best_analysis.py) |
| **The settled same-day result** (R7 vs R8, 81 per-task rows both arms) | [`evidence/t12/CTRL_VS_T12_PAIRED_ANALYSIS.json`](evidence/t12/CTRL_VS_T12_PAIRED_ANALYSIS.json) |
| Its machine verification (re-derives every figure; exit 0) | [`evidence/t12/ctrl_vs_t12_verify.py`](evidence/t12/ctrl_vs_t12_verify.py) |
| ~~Withdrawn~~ cross-day paired analysis, kept as a record of what was claimed | [`evidence/t12/T12_REM81_PAIRED_ANALYSIS.json`](evidence/t12/T12_REM81_PAIRED_ANALYSIS.json) |
| dev-12 / validation-12 rung analyses | [`evidence/t12/T12_DEV12_PAIRED_ANALYSIS.json`](evidence/t12/T12_DEV12_PAIRED_ANALYSIS.json), [`evidence/t12/T12_VAL12_PAIRED_ANALYSIS.json`](evidence/t12/T12_VAL12_PAIRED_ANALYSIS.json) |
| Smoke evidence (hint quoted verbatim; clamp landed at 20,000 ms) | [`evidence/t12/T12_SMOKE_RESULTS.json`](evidence/t12/T12_SMOKE_RESULTS.json), [`evidence/t12/T12_SMOKE_B2_RESULTS.json`](evidence/t12/T12_SMOKE_B2_RESULTS.json) |
| Analysis scripts that produced them | [`evidence/t12/t12_rem81_analysis.py`](evidence/t12/t12_rem81_analysis.py), [`evidence/t12/t12_paired_analysis.py`](evidence/t12/t12_paired_analysis.py) |
| Smoke run logs | `evidence/t12/t12_smoke_a1_log.txt`, `_a2_`, `_b_` |
| The T1.2 change itself (opt-in, not promoted) | `agent/claude/agent.ts` (gates `ADA_TIME_HINTS`, `ADA_BASH_CLAMP_REMAINING`, `ADA_DEADLINE_ANCHOR`) |
| Its unit tests (25/25) | `agent/claude/agent.test.ts` |

The files under `evidence/t12/` and `evidence/confirm/` are byte-identical copies of the
campaign's `bench/` originals, so this repository is self-contained for every claim about T1.2 — including the
same-day result that withdrew its promotion.

**At the campaign root, one level above this tree** — the harness and raw run artifacts,
which are not part of this repository:

| Item | Path |
|---|---|
| Working roadmap (removed 2026-09-18; rules recorded in `../bench/RUN_REGISTRY.md` and this file) | — |
| R9/R10 raw diagnostics, baseline arms | `../bench/diagnostics/ada-baseline/20260915T0825Z-r{1,2}-base/0.json` |
| R9/R10 raw diagnostics, shipped arms | `../bench/diagnostics/20260915T0825Z-r{1,2}-best/0.json` |
| **Index of all eight runs, and which pairings are legitimate** | `../bench/RUN_REGISTRY.md` |
| **The settled comparison, in full** | `../bench/CTRL_VS_T12_REPORT.md` |
| R7 control `6672af8`, raw diagnostics | `../bench/diagnostics/ada-t01gateoff/20260912T1603Z-t04ctrl2/0.json` |
| R8 candidate `2e495bb`, raw diagnostics | `../bench/diagnostics/20260912T1603Z-t12cand2/0.json` |
| R5 baseline `df0c537`, raw diagnostics | `../bench/diagnostics/ada-baseline/20260912T1031Z-frem81base/0.json` |
| R3, the depressed control behind the withdrawn +28 | `../bench/diagnostics/20260910T0728Z-t04ctrl/0.json` |
| R4, the withdrawn promoted candidate | `../bench/diagnostics/20260911T1540Z-t12rem81/rem81_t12_candidate.json` |
| T1.1 negative-result analysis | `../bench/T11_DEV12_PAIRED_ANALYSIS.json` |
| The 2026-09-12 morning run, R5/R6 (noise floor, confounded baseline) | `../bench/FRESH_REM81_REPORT.md`, `../bench/FRESH_REM81_PAIRED_ANALYSIS.json` |
| Its analysis + machine verification (55/55, exit 0) | `../bench/fresh_rem81_analysis.py`, `../bench/fresh_rem81_verify.py` |
| External Terminal-Bench analysis (n=38) | `../bench/FINAL40_PAIRED_ANALYSIS.json` |
| Machine verification of the settled result + run registry (exit 0) | `../bench/ctrl_vs_t12_verify.py` |
| Machine verification of the archived runs (exit 0) | `../bench/harness/archive_integrity_check.py` |
| Superseded Phase A reports | removed during final packaging (2026-09-18); superseded by this file and `../bench/` reports |
| Narrative companion | `REPORT.md` |