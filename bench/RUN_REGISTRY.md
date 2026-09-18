# Run registry — every scored SetupBench `remaining81` run on disk

> **Re-check — 2026-09-18.** This registry is left as written below. Checked against the raw rows,
> three things in it do not hold:
>
> - R3 is dated 2026-09-10 here, but it records commit `6672af8`, which was created at 07:24 UTC on
>   2026-09-11. R3 most likely ran that morning, the same day as R4 and about eight hours before it.
>   "Only same-day pairings" would not have caught that pairing; what protects a comparison is
>   running both arms at the same time, as R9/R10 did.
> - R10a has 41 zero-turn rows, not 40.
> - Footnote ⁴, cited for `417a8f1`, is not defined. `417a8f1` is `df0c537` plus the runner shim
>   `systemPromptGuidance`, committed in the baseline workspace that packaging removed. It is not in
>   `ada-campaign.bundle`; its agent tree, `df8a18c09278`, is pinned in the R9a/R10a diagnostics.
>
> The evidence for each point is in the repository README, under "Re-checked against the raw data".

**Purpose.** Ten full 81-task runs exist across six days and four builds. Any sentence
that says "the fresh run" or "the control" without naming one of these is ambiguous, and
several published claims went wrong exactly there. Every document in this campaign refers
to runs by the **Run ID** in the first column and nothing else.

Regenerate this table from the raw artifacts:

```bash
python3 bench/ctrl_vs_t12_verify.py        # asserts the R1-R8 rows below against the JSON
python3 bench/baseline_vs_best_verify.py   # asserts the R9/R10 rows and the pooled verdict
```

---

## The three builds

| Build | What it adds | Trees |
|---|---|---|
| **`df0c537`** (committed as `417a8f1` ⁴) | campaign origin — no watchdog, no deadline anchor. `417a8f1` only commits the runner shim `systemPromptGuidance` that was uncommitted in this workspace since 2026-09-08 and present in R1 and R5. A task that overruns is **hard-killed** by the harness. | archived: `bench/diagnostics/ada-baseline/` |
| **`6672af8`** | **+ T0.1**: watchdog interrupt, container-anchored deadline, clean exit. Overruns become graded partial work instead of kills. | archived: `bench/diagnostics/ada-t01gateoff/` |
| **`2e495bb`** | **+ T1.2**: time hints before every model request, wrap-up instruction, Bash timeout clamp. | archived: `bench/diagnostics/` |
| **`5f4c5c0`** (measured as `1d82e56`) | **the shipped build**: `2e495bb` with both T1.2 gates flipped **default off**, so no hooks are registered and behaviour is `6672af8`'s. `1d82e56` is the same agent tree with later docs commits on top (`agent_tree` `dab704de524a` in both). | archived: `bench/diagnostics/` |

The build workspaces formerly under the autoresearcher tree were removed during final
packaging (2026-09-18); their run diagnostics are archived under `bench/diagnostics/`
and the builds themselves are pinned by commit in `ada/` (see `ada/RESULTS.md`
§Versions).

`2e495bb` is `6672af8` plus T1.2 and nothing else, so **`6672af8` → `2e495bb` is the only
contrast in which the time-awareness bundle is the sole variable.**

## The runs

| Run | Started (UTC) | Build | Experiment id | Pass | Timeouts | Zero-turn rows | Turns | Invalid |
|---|---|---|---|---:|---:|---:|---:|---:|
| **R1** | 2026-09-09 | `df0c537` | `manual/remaining81_baseline` | 27/81 | 53 | 53 | 556 | 0 |
| **R2** | 2026-09-09 | Phase A incumbent ¹ | `manual/remaining81_incumbent` | 50/81 | 3 | 43 | 557 | 0 |
| **R3** ⚠️ withdrawn ³ | 2026-09-10 07:28 | `6672af8` | `20260910T0728Z-t04ctrl` | 24/81 | 0 | 0 | 1544 | 0 |
| **R4** ⚠️ withdrawn ³ | 2026-09-11 15:40 | `2e495bb` | `20260911T1540Z-t12rem81` | 52/81 | 0 | 0 | 1274 | 0 |
| **R5** | 2026-09-12 10:31 | `df0c537` | `20260912T1031Z-frem81base` | 34/81 | 45 | 46 | 750 | 0 |
| **R6** | 2026-09-12 12:51 | `2e495bb` | `20260912T1031Z` arm 2 ² | 43/74 | 0 | 0 | 1284 | **7** |
| **R7** | 2026-09-12 16:03 | `6672af8` | `20260912T1603Z-t04ctrl2` | 54/81 | 0 | 0 | 1554 | 0 |
| **R8** | 2026-09-12 18:10 | `2e495bb` | `20260912T1603Z-t12cand2` | 50/81 | 0 | 0 | 1389 | 0 |
| **R9a** | 2026-09-15 08:25 | `df0c537` (`417a8f1`) | `20260915T0825Z-r1-base` | 32/81 | 44 | 45 | 664 | 1 |
| **R9b** | 2026-09-15 08:25 | **shipped** (`1d82e56`) | `20260915T0825Z-r1-best` | 47/81 | 0 | 0 | 1373 | 1 |
| **R10a** | 2026-09-15 12:11 | `df0c537` (`417a8f1`) | `20260915T0825Z-r2-base` | 36/81 | 40 | 40 | 722 | 2 |
| **R10b** | 2026-09-15 12:11 | **shipped** (`1d82e56`) | `20260915T0825Z-r2-best` | 52/81 | 0 | 0 | 1452 | 1 |

### Phase C runs (2026-09-16 → 09-17) — FAILING25 pool, not remaining81

These runs use the 25 consistently-failing tasks (`bench/FAILING25.txt`), not the
remaining81 suite, and are recorded here so every scored run on disk has a row. They do
**not** enter any remaining81 comparison.

| Run | Started (UTC) | Build | Experiment id | Result |
|---|---|---|---|---|
| **BP** | 2026-09-16 07:15 | shipped (`dab704d`) | `budget-probe-20260916T0730Z` | 960 s probe, 25 tasks: **7/25 pass → MIXED** (rule ≥12 SLOW / 4–11 MIXED / ≤3 HARD); 0 timeouts, 0 invalid; 5h05m. Report: `BUDGET_PROBE_REPORT.md` |
| **P3-void** ⚠️ | 2026-09-16 13:40 | shipped vs `9f2e34d` | `20260916T1340Z` | **VOID — host reboot ~14:49 UTC killed it mid-replicate-1 at 8/25 rows.** Partial data excluded; not quotable as evidence |
| **P3-r1/r2** | 2026-09-17 06:02 | shipped (`dab704d`) vs P3 `9f2e34d` (`811a16e`) | `20260917T0602Z` | 2 replicates, 480 s, paired: pooled net **+2** (6/46 → 8/46), rep1 −1, rep2 +3, p = 0.6875. **Gate failed (≥+5, no negative rep) → REVERT.** Report: `P3_PAIRED_REPORT.md` |

Protocol on R1–R8: suite `remaining81`, concurrency 4, task timeout 480 s, grader timeout
600 s, seed 20260907, model `z-ai/glm-5.3-flash`. **R9/R10 differ in one respect only:
concurrency 1 per arm** (the machine was shared), so each replicate ran 2 containers, and the
two replicates overlapped 12:11–17:43 for 4 containers total — the same load R1–R8 ran under.
Task budget, grader budget, seed, suite and model are unchanged, and both arms of a replicate
ran concurrently under identical conditions, which is what the pairing rests on.

¹ **R2's stored `workspace_commit` field reads `df0c537` and is wrong.** `df0c537` hard-kills
on overrun, so its timeout count and its zero-turn count are the same number (R1: 53 and 53;
R5: 45 and 46). R2 has **3 timeouts against 43 zero-turn rows** — the signature of the
watchdog interrupt path reporting `turns=0` (evidence item E5). The `manual/` runs did not
record the build reliably; R3 onward do.

³ **R3 and R4 are the withdrawn `52/81 vs 24/81, +28, p = 7.66e-07` claim.** R3 is a
depressed run — the same build scores 54/81 as R7 — so the pairing measured the day, not the
change. Both scores are real; the *pairing* is void. Neither run may anchor a claim.

² R6 wrote **no diagnostics file**. Seven of its 81 rows came back `valid=0` from docker
contention, and `setupbench_ada_domain_eval.py:257` refuses to write a report when any row is
invalid. Its only per-task artifact is the driver log `bench/fresh_rem81_best.log`. Its 7
invalid rows are excluded from every pairing that involves it, which is why it is `/74`.

## Which pairings are legitimate

**Only same-day pairings.** The same build scores 24/81 and 54/81 on two different days —
the depressed R3 against the normal R7 —
(R3 vs R7, 30 gained / 0 lost, p = 1.9e-09) while doing measurably identical work — 1544 vs
1554 turns, zero timeouts both. No cross-day comparison can survive a day effect that size.

| Pairing | Runs | Same day? | What it measures | Verdict |
|---|---|---|---|---|
| `df0c537` → `6672af8` | **R5 → R7** | ✅ 2026-09-12 | the T0.1 watchdog | **34/81 → 54/81, +20, p = 1.1e-05** |
| `6672af8` → `2e495bb` | **R7 → R8** | ✅ 2026-09-12 | the T1.2 time hints, sole variable | **54/81 → 50/81, −4, p = 0.42** |
| `df0c537` → `2e495bb` | **R5 → R8** | ✅ 2026-09-12 | both changes together | **34/81 → 50/81, +16, p = 0.0015** |
| `df0c537` → `2e495bb` | R5 → R6 | ✅ 2026-09-12 | both changes together, n=74 | 31/74 → 43/74, +12, p = 0.0075 |
| `df0c537` → **shipped** | **R9a → R9b** | ✅ 2026-09-15 | the shipped build, replicate 1 | **31/79 → 47/79, +16, p = 1.45e-04** |
| `df0c537` → **shipped** | **R10a → R10b** | ✅ 2026-09-15 | the shipped build, replicate 2 | **36/78 → 51/78, +15, p = 6.10e-05** |
| `df0c537` → **shipped** | **R9 + R10 pooled** | ✅ 2026-09-15 | the confirmation run, pre-registered rule | **67/157 → 98/157, +31, p = 7.92e-09 — HOLDS** |
| `6672af8` → `2e495bb` | R3 → R4 | ❌ 09-10 vs 09-11 | **nothing** — this is the withdrawn +28 | see [`CTRL_VS_T12_REPORT.md`](CTRL_VS_T12_REPORT.md) |
| anything → R2 | — | ❌ | Phase A hybrid lineage, build not recorded | do not use |

**Intra-day stability check.** R5/R6 ran 10:31–14:59 and R7/R8 ran 16:03–20:11, so the
same-day pairings above span two halves of one day rather than being interleaved. The same
build measured in both halves is stable: **R6 43/74 → R8 44/74 on the 74 tasks both
evaluate, 6 gained / 5 lost, p = 1.0.** Cross-half pairing on 2026-09-12 is therefore
supported by measurement, not by assumption.

## The noise floor

| Build | Runs | Days | Pass → pass | Discordant | p |
|---|---|---|---|---:|---|
| `6672af8` | R3 → R7 | 09-10 → 09-12 | 24/81 → 54/81 — **the outlier**, see ³ | 30 (30 gained, 0 lost) | **1.863e-09** |
| `2e495bb` | R4 → R8 | 09-11 → 09-12 | 52/81 → 50/81 — R4 is the withdrawn candidate, ³ | 10 (4 gained, 6 lost) | 0.7539 |
| `2e495bb` | R6 → R8 | 09-12 → 09-12 | 43/74 → 44/74 | 11 (6 gained, 5 lost) | 1.0 |
| `df0c537` | R1 → R5 | 09-09 → 09-12 | 27/81 → 34/81 | 13 (10 gained, 3 lost) | 0.09229 |

Ordinary run-to-run churn on identical code is **10–13 discordant tasks on n≈80**, aggregate
unchanged. R3 is not that: 30 discordant, all in one direction. **R3 is a depressed run, and
every claim anchored to it is void.** A contrast whose discordant count is at or below ~15 on
n≈80 is inside the noise and cannot carry a decision.

## Other suites

| Suite | Runs | Where |
|---|---|---|
| Terminal-Bench 2.0, 40 public tasks, n=38 evaluable | one paired run, build `08a8d5d` | `bench/FINAL40_PAIRED_ANALYSIS.json` |
| `dev-12` / `validation-12` rungs | screening only; ±2–3 tasks is noise on n=12, so no rung on these suites has ever carried a decision | `bench/T12_DEV12_PAIRED_ANALYSIS.json`, `bench/T12_VAL12_PAIRED_ANALYSIS.json`, `bench/T11_DEV12_PAIRED_ANALYSIS.json` |
