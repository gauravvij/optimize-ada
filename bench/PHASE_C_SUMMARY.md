# Phase C Summary — Campaign Ledger (2026-09-16 → 2026-09-17)

> **Re-check — 2026-09-18.** This summary is left as written below. Its "zero 480 s clock-outs"
> means that the harness killed no run. The watchdog still interrupted 28 of the shipped build's 41
> failures in the P3 run, and 8 of the budget probe's 17 valid failures, which are the "17 hard
> clock-outs" below. P2 was only ever measured inside the T1.2 bundle (R7 → R8) and P4 never ran,
> so "dropped" means untested. The evidence for each point is in `bench/README.md`, under "Corrections to the campaign's records".

**Phase C asked one question:** are the 25 consistently-failing SetupBench tasks
(`bench/FAILING25.txt`, failed in both R9/R10 replicates on the shipped arm) **slow or
hard**? The measured answer: **mostly hard.** No candidate cleared its pre-registered
gate, nothing was promoted, and the shipped best is unchanged.

Every figure below is measured and machine-derived from the artifacts named alongside it.
No number in this ledger is projected or estimated.

## 1. Shipped baseline (pinned, untouched throughout)

| Item | Value |
|---|---|
| Tag (canonical tree `ada/`) | `ada-best-61pct-20260916` |
| Former mirror commit (historical pin; mirror removed 2026-09-18) | `c6f917e` |
| Agent tree (`agent/`) | `dab704de524a` — clean for the entire phase |
| What it is | the R9/R10-confirmed build: T0.1 watchdog, both T1.2 gates default off (98/157 vs baseline 67/157, p = 7.92e-09) |

The tag was verified present in both repositories and pointing at the pinned commits
before and after every experiment. The shipped tree was never modified; all candidate
edits lived in separate worktrees.

## 2. Budget probe (P1) — VERDICT: MIXED

- **Run:** `budget-probe-20260916T0730Z`, started 2026-09-16 07:15 UTC, 5 h 05 m,
  shipped build, one arm, concurrency 1, 960 s task budget (double the standard 480 s),
  600 s grader, seed 20260907.
- **Result:** **7 / 25 rows passed** (24 valid, 0 timeouts; 1 invalid row excluded).
- **Pre-registered rule** (fixed in the campaign plan before spend; `plans/plan.md` was
  removed during final packaging 2026-09-18 — the rule is recorded here and in
  `bench/P3_P2_PREREGISTRATION.md`): >= 12 pass -> SLOW;
  4-11 pass -> MIXED; <= 3 pass -> HARD. 7 falls in 4-11 -> **MIXED**.
- **Reading:** doubling the budget converts only 7 of 25 consistent failures. The pool is
  not merely time-starved; most of it is hard for this model at any budget tested.
- **Artifacts:** `bench/BUDGET_PROBE_REPORT.md` (per-task table),
  `bench/diagnostics/budget-probe-20260916T0730Z/`.

Per the MIXED branch of the rule, efficiency work proceeded for the converting subset —
P3 was run; P2 and P4 were subsequently dropped on evidence (§4).

## 3. P3 — late wrap-up: TESTED AND REJECTED (REVERT)

**Candidate.** Two code-default flips in `agent/claude/agent.ts` (env overrides
preserved): `ADA_TIME_HINTS` default ON and `ADA_WRAP_UP_MS` default 96,000 ms — the
wrap-up directive fires only at ~80% of a 480 s budget consumed, so it structurally
cannot touch tasks that finish early. Branch `p3-late-wrapup`, commit `9f2e34d`
(agent tree `811a16e4a67e`; worktree removed 2026-09-18, branch preserved). Unit tests 18/18; no new
`tsc` errors. Pre-registration: `bench/P3_P2_PREREGISTRATION.md` (including the
pre-spend units correction from 384,000 ms elapsed to 96,000 ms remaining).

**Run.** `20260917T0602Z`, launched 2026-09-17 06:02 UTC, completed 12:35:58 UTC
(~6.5 h). Two replicates, both arms of each replicate concurrent, one driver, one
machine; 25 tasks from `bench/FAILING25.txt`; 480 s task / 600 s grader; concurrency 1
per arm; seed 20260907. Shipped arm = tag `ada-best-61pct-20260916` (agent tree
`dab704de524a`).

**Results (exact McNemar, paired, same-day):**

| Rep | n (valid pairs) | shipped pass | p3 pass | net | gained | lost | p |
|-----|----|----|----|----|----|----|----|
| 1 | 25 | 4 | 3 | **-1** | 1 | 2 | 1.0 |
| 2 | 21 | 2 | 5 | **+3** | 3 | 0 | 0.25 |
| **Pooled** | 46 | 6 | 8 | **+2** | 4 | 2 | 0.6875 |

Invalid rows excluded from pairing: rep-2 shipped arm 3, p3 arm 1. **Zero 480 s task
timeouts in either arm, either replicate** — no clock-outs anywhere.

**Pre-registered gate** (fixed in `bench/P3_P2_PREREGISTRATION.md` before spend): keep
only if ALL of — every replicate completes (PASS), pooled net >= +5 (FAIL, +2), no
negative replicate (FAIL, rep 1 = -1). Applied mechanically:

### VERDICT: REVERT — P3 does not ship

- The pooled +2 is below both the gate (+5) and the noise floor; p = 0.6875 means the
  sign itself is unresolvable at this n.
- `networkx-networkx-c107d25` flips **both directions** across replicates — noise-floor
  behavior, no causal content. The only consistent gain was `hackmdio-codimd-f00df50`
  (both reps, though the rep-2 pair was excluded as shipped-row invalid).
- No efficiency claim either: P3 did not observably reduce turns or clock-outs, and
  both arms produced zero 480 s timeouts.
- The `ada-p3` worktree was removed 2026-09-18 after its diagnostics were archived to
  `bench/p3_evidence/`; branch `p3-late-wrapup` @ `9f2e34d` is preserved in the repo as
  the un-promoted experiment record. No defaults from it propagate. The shipped tree is untouched.

**Artifacts:** `bench/P3_PAIRED_REPORT.md` (full close-out),
`bench/P3_PAIRED_20260917T0602Z.json` (machine analysis of record),
`bench/p3_paired_20260917T0602Z_{driver,memory,r1_shipped,r1_p3,r2_shipped,r2_p3}.log`,
diagnostics under `bench/diagnostics/20260917T0602Z-r{1,2}-shipped/`
and (P3 arm, archived 2026-09-18) `bench/p3_evidence/20260917T0602Z-r{1,2}-p3/`.

### Voided run (do not quote)

The first P3 attempt (`20260916T1340Z`, launched 13:40 UTC Sep 16) was killed by a host
reboot at ~14:49 UTC with replicate 1 at 8/25 partial rows. That data is **void** and is
excluded from every figure above. Recorded in `bench/RUN_REGISTRY.md` as **P3-void**.

## 4. P2 and P4 — DROPPED without spend (evidence-based, pre-registered logic)

Both candidates share one theory of change: **save wall-clock so time-starved tasks
finish inside 480 s.** The fresh Phase C measurements refute the premise:

1. **Zero 480 s clock-outs** in both arms and both replicates of the P3 paired run on
   FAILING25 — the pool is not dying on the clock at the standard budget.
2. The budget probe at 960 s: 0 timeouts, and most non-converting failures are
   grader-fails on genuinely unfinished setups, not clock-outs.
3. P3 — the one mechanism-level candidate aimed at the interrupted population — moved
   +2 pooled (p = 0.69), inside the noise floor.

| Candidate | Drop condition (pre-registered) | Evidence that triggered it |
|---|---|---|
| **P2** Bash timeout clamp (`ADA_BASH_CLAMP_REMAINING`) | no clock-out population left to save | zero 480 s clock-outs paired; probe failures are grader-fails, not clock-outs |
| **P4** install-cheapening PreToolUse hook | smoke bar >= 30 s/task saved is moot if saved seconds cannot convert | pool not dying on the clock at 480 s; probe MIXED with 0 timeouts at 960 s |

These are **evidence-based drops under the pre-registered efficiency logic** (spend only
where the mechanism has a population to act on), not silent drops and not negative
results — neither candidate consumed eval spend.

## 5. P5 — verification stop-hook: DEFERRED

Per the campaign plan (`plans/plan.md`, removed during final packaging 2026-09-18),
P5 runs only if the clock pool is exhausted AND the declare-done
pool (4 tasks) is the largest remaining. The clock pool is now measured as mostly hard
(probe MIXED 7/25), which puts P5's 4-task pool next in line, but it was never reached
this phase. **No spend was made; no decision was taken beyond deferral.**

## 6. Final disposition

- **Nothing promoted. Nothing shipped.** The shipped best remains tag
  `ada-best-61pct-20260916` (`targets/ada` @ `c6f917e`, agent tree `dab704de524a`,
  clean) — the R9/R10-confirmed build worth +31 tasks over the campaign origin.
- **The slow-vs-hard question is answered: mostly hard.** Doubling the budget converts
  7/25; at 480 s there are no clock-outs left on this pool; the targeted wrap-up
  mechanism is inert (+2, p = 0.69). The remaining gap on `z-ai/glm-5.3-flash` is
  capability, not scaffolding — consistent with the campaign's durable lesson that
  prompt-level changes are inert and the one shipped gain came from fixing the harness's
  treatment of the agent.
- **Honest ceiling, revised:** the 17 hard clock-outs are not reachable by scaffolding
  on this model at any budget tested; the §9 ceiling estimate in the campaign headroom analysis
  (`improvements.md`, removed during final packaging 2026-09-18)
  drops accordingly.

## 7. Ledger of record

| Run | Date (UTC) | What | Verdict | Registry row |
|---|---|---|---|---|
| `budget-probe-20260916T0730Z` | 2026-09-16 07:15 | 25 consistent failures at 960 s, shipped build | **MIXED — 7/25** | BP |
| `20260916T1340Z` | 2026-09-16 13:40 | first P3 paired attempt | **VOID** — host reboot ~14:49, 8/25 partial rows | P3-void |
| `20260917T0602Z` | 2026-09-17 06:02 | P3 paired, 2 replicates vs shipped, 480 s | **REVERT — pooled net +2, gate failed** | P3-r1/r2 |

Cross-references: run index and legitimate pairings — `bench/RUN_REGISTRY.md` (Phase C
section); probe detail — `bench/BUDGET_PROBE_REPORT.md`; P3 close-out —
`bench/P3_PAIRED_REPORT.md`; pre-registrations — `bench/P3_P2_PREREGISTRATION.md` (the campaign
plan and headroom working docs were removed during final packaging 2026-09-18);
campaign record — `ada/RESULTS.md` (Phase C section).
