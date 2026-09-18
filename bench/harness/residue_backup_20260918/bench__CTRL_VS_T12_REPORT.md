# Control vs T1.2 — the same-day paired run, 2026-09-12

Run `20260912T1603Z`, driver [`run_ctrl_vs_t12.sh`](run_ctrl_vs_t12.sh), both arms on one
machine on one day. Runs **R7** and **R8** in [`RUN_REGISTRY.md`](RUN_REGISTRY.md).
Every number below is reproducible with `python3 bench/ctrl_vs_t12_analysis.py`, which reads
three run logs and three diagnostics files and writes
[`CTRL_VS_T12_PAIRED_ANALYSIS.json`](CTRL_VS_T12_PAIRED_ANALYSIS.json), and independently
machine-checked by `python3 bench/ctrl_vs_t12_verify.py` (94 assertions, exit 0).

**In one line:** this is the run [`fina_run.md`](../fina_run.md) §7 marked REQUIRED, and it
settles the campaign's headline in the downward direction — against a control run on the
**same day**, the promoted T1.2 time-awareness bundle scores **50/81 against 54/81, a net of
−4 at p = 0.42**, not the **+28 at p = 7.66e-07** that was published and is hereby withdrawn.
That +28 was measured against `6672af8` on 2026-09-10; the same build on the same tasks
scored 54/81 on 2026-09-12, 30 tasks better with 0 worse. What survives intact is the layer
underneath: same-day, the T0.1 watchdog takes `df0c537` from **34/81 to 54/81 (+20,
p = 1.1e-05)**, and every one of those conversions is a task the old build hung on with
zero turns.

---

## 1. The result, on one page

Three builds, all measured on 2026-09-12, all 81 tasks, identical protocol:

| Build | What it is | Run | Pass | Timeouts | Turns |
|---|---|---|---:|---:|---:|
| `df0c537` | campaign origin, no watchdog | R5 | 34/81 | 45 | 750 |
| `6672af8` | **+ T0.1** watchdog / clean exit | R7 | **54/81** | 0 | 1554 |
| `2e495bb` | **+ T1.2** time-awareness bundle | R8 | 50/81 | 0 | 1389 |

Paired, exact McNemar, Newcombe 95% CI:

| Contrast | n | pass → pass | net | lost / gained | p | 95% CI |
|---|---:|---|---:|---|---|---|
| **R5 → R7** — what the watchdog is worth | 81 | 34 → 54 | **+20** | 1 / 21 | **1.097e-05** | [+9.36, +38.46] |
| **R7 → R8** — what the time hints are worth | 81 | 54 → 50 | **−4** | 9 / 5 | **0.424** | [−19.26, +9.67] |
| R5 → R8 — both changes together | 81 | 34 → 50 | +16 | 4 / 20 | 0.001544 | [+4.37, +33.88] |

**R7 → R8 is the whole point of this run.** `2e495bb` is `6672af8` plus the T1.2 bundle and
nothing else, both arms scored the same day under one driver, so the time hints are the sole
variable. The pre-registered promotion rule (`fina_run.md` §3 rule 4) was *no significant
regression **and** ≥ +3 net conversions on remaining81*. The measurement is **−4**.

> **Verdict: the T1.2 promotion is withdrawn.** Not because the change is harmful — 14
> discordant tasks on n=81 is inside the measured noise floor and p = 0.42 excludes nothing —
> but because the evidence that promoted it does not exist. T1.2's effect on pass rate is
> indistinguishable from zero, and the only sound measurement of it points the wrong way.

## 2. Why the published +28 was wrong

The promoted claim paired **R4** (`2e495bb`, 2026-09-11, 52/81) against **R3** (`6672af8`,
2026-09-10, 24/81). Both numbers are real. The pairing is not, because R3 is a depressed run:

| Same build `6672af8`, same 81 tasks, same protocol | Turns | Timeouts | Pass |
|---|---:|---:|---:|
| R3 — 2026-09-10 | 1544 | 0 | **24/81** |
| R7 — 2026-09-12 | 1554 | 0 | **54/81** |

**30 tasks gained, 0 lost, p = 1.863e-09.** Turn counts are 0.6% apart and neither run timed
out once, so the agent did the same amount of work on both days and simply succeeded far more
often. That is upstream model or provider quality, not agent behaviour, and no cross-day
pairing survives it.

Everything anchored to R3 inherits the defect: the +28, the "24/81 is the only valid
comparison anchor" rule, and — noted in [`FRESH_REM81_REPORT.md`](FRESH_REM81_REPORT.md) §6 —
the alarming finding that `6672af8` was "beaten 18–0 by its own ancestor". That last one is
now explained rather than open: `df0c537` beat R3 because R3 had a bad day, and against a
normal day (R7) the same subset reads 34/35 → 33/35, a wash. There is no defect in `6672af8`.

## 3. Where the +20 comes from: the baseline was hanging, and now it doesn't

R5 → R7, split by whether `df0c537` produced any turns at all on that task:

| Subset | n | `df0c537` | `6672af8` | net | p |
|---|---:|---:|---:|---:|---|
| baseline hung — `turns = 0`, killed at 480 s | 46 | 0/46 | **21/46** | **+21** | 9.537e-07 |
| baseline ran — `turns > 0` | 35 | 34/35 | 33/35 | −1 | 1.0 |
| **all** | **81** | **34** | **54** | **+20** | **1.097e-05** |

The entire measured gain of this campaign is *the agent no longer gets hard-killed before it
produces a single turn*. On the 35 tasks the old build could actually run, it scores 34/35 and
nothing since has improved on that. That subset is selected-easy by construction — it is the
set of tasks that finish fast — so it is near its ceiling and cannot show much. It is still
worth stating plainly: **no change in this campaign has been shown to make Ada better at a
task it was already able to attempt.**

## 4. Where the −4 comes from: the hints fire on tasks that had time to spare

R7 → R8, split by whether the control hit the deadline. This conditions on the control's own
behaviour, so it is a descriptive decomposition, not a pre-registered contrast:

| Subset | n | `6672af8` | `2e495bb` | net |
|---|---:|---:|---:|---:|
| control was interrupted at the deadline | 34 | 12/34 | 13/34 | **+1** |
| control finished cleanly with budget left | 47 | 42/47 | **37/47** | **−5** |
| **all** | **81** | **54** | **50** | **−4** |

**T1.2 changes nothing where the clock binds and loses five tasks where it never did.** The
wrap-up instruction is reaching tasks that were going to finish comfortably and telling them
to stop exploring. By task type the loss is concentrated in exactly the places where a setup
needs a verification pass at the end:

| Task type | n | `6672af8` | `2e495bb` | net |
|---|---:|---:|---:|---:|
| `dbsetup` | 13 | 11 | 8 | **−3** |
| `dependency_resolution` | 14 | 6 | 4 | **−2** |
| `bgsetup` | 7 | 6 | 6 | 0 |
| `reposetup` | 47 | 31 | 32 | +1 |

Three of the nine lost tasks (`dbsetup-postgresql-2`, `dbsetup-postgresql-3`,
`dbsetup-mysql-2`) ended with more than 40% of the budget unused. This is the premature
give-up mode already recorded as a caveat on the promoted result; it is now localised.

## 5. T1.2 does what it was designed to do — it just isn't worth pass rate

The mechanism is not in doubt. Every metric the change targets moved, and moved hard:

| Metric | `6672af8` (R7) | `2e495bb` (R8) | Δ |
|---|---:|---:|---|
| Runs interrupted at the deadline | 34 | **7** | **−79%** |
| Total turns | 1554 | 1389 | −10.6% |
| Summed wall time | 29,353 s | 27,881 s | −5.0% |
| Timeouts | 0 | 0 | — |
| Invalid rows | 0 | 0 | — |
| **Tasks passed** | **54/81** | **50/81** | **−4** |

Reported separately, because they are separate results: **the time hints buy a large,
reliable reduction in interrupted runs and about 11% fewer turns, and they do not buy pass
rate.** An efficiency result and an accuracy result are different claims, and blending them
is what produced the withdrawn headline.

The cost of converting interrupts into clean finishes shows up in one more number. Counting
failures where the agent ended cleanly — it believed it was done — and the grader disagreed:

| | failures | of which "agent said done, grader failed" |
|---|---:|---:|
| `6672af8` (R7) | 27 | **5** |
| `2e495bb` (R8) | 31 | **25** |

This replicates the same measurement on the promoted run (26 of 29). T1.2 does not make Ada
finish more tasks; it makes Ada **declare** more tasks finished. Verification discipline, not
pacing, is where the remaining headroom is.

## 6. Run integrity

The run itself is clean. Independently of the analysis script, from the logs and diagnostics:

| Check | Result |
|---|---|
| 81 rows per arm, no duplicates, identical task sets | ✅ |
| `valid=1` on all 162 rows; 0 timeouts either arm | ✅ |
| driver log rows match diagnostics rows per task, both arms | ✅ |
| pass 54 / 50 and turns 1554 / 1389 agree across log summary and diagnostics summary | ✅ |
| exact McNemar recomputed independently via `scipy.stats.binomtest` | ✅ p = 0.424 |
| preflight: `targets/ada-t01gateoff` `agent/` == `6672af8`, `targets/ada` `agent/` == `2e495bb` | ✅ in driver log |
| resource guard: peak swap 899 M, min available 3115 M, worst `docker ps` 375 ms | ✅ no contention |
| `terminal_result` present on all 162 rows; zero `turns=0` rows | ✅ T0.1 holding |

Two things that look like defects and are not:

- **`grader_returncode` disagrees with `passed` on ~26 rows per arm.** Grading is
  `"Setup successful" in grader_output` for every task type except `dependency_resolution`,
  which uses `returncode == 0` (`setupbench_ada_eval.py:265-270`). Same rule both arms.
- **Two candidate rows report `turns=2`.** `hackmdio-codimd-f00df50` and
  `deps-amazon-cognito-saml-idp-c076c` ran 476 s and 544 s — one long tool call each, not an
  early stop.

**One real defect, in the analysis and not in the run.** `CTRL_VS_T12_PAIRED_ANALYSIS.json`
sat on disk from 2026-09-12 18:24 until 2026-09-13 02:21 carrying
`"status": "PARTIAL — candidate arm still running"` and `"primary": null`. It had been
generated 1 h 47 m before arm 2 finished, and nothing re-ran it when the run completed. The
run had been complete and unread for eight hours. `bench/ctrl_vs_t12_verify.py` now fails if
`status` is not `COMPLETE` or `primary` is null.

## 7. What this run supports — and what it does not

**Supported:**

- The T0.1 watchdog is worth **+20 tasks** on `remaining81`, same-day paired, p = 1.1e-05,
  and all of it comes from removing 46 zero-turn hangs.
- The published **+28 for T1.2 is void**. Its control is a run that scores 30 tasks lower
  than the same build on the same tasks two days later.
- Measured properly, **T1.2 is −4 (p = 0.42)** and does not meet its pre-registered promotion
  bar. Its promotion is withdrawn.
- T1.2's mechanism works: interrupted runs 34 → 7, turns −10.6%, wall time −5.0%.
- Cross-day pairing on this harness is not viable. Same code, two days: 24/81 and 54/81.

**Not supported:**

- **This run does not show T1.2 is harmful.** 14 discordant tasks on n=81 is inside the noise
  floor (10–13 on identical code); p = 0.42; the CI spans −19.3 to +9.7 points. The honest
  statement is *no measured benefit*, not *measured harm*.
- **It does not measure the T1.2 sub-gates separately.** Time hints, the wrap-up instruction
  and the Bash clamp shipped as one bundle and moved as one bundle. §4 points at the wrap-up
  instruction; that is a hypothesis this run cannot test.
- **The §3 and §4 subsets are conditioned post-hoc** on one arm's behaviour. They explain
  where the aggregate came from; they are not independent contrasts.
- **The `df0c537` → `6672af8` arms were not interleaved** — R5 ran 10:31–12:51 and R7 ran
  16:03–18:10. The intra-day stability check that licenses this (R6 43/74 → R8 44/74,
  p = 1.0) is in [`RUN_REGISTRY.md`](RUN_REGISTRY.md).
- **Nothing here touches Terminal-Bench.** That endpoint remains a dead tie at 26/38, measured
  on `08a8d5d`, and no build after it has ever been run outside SetupBench.

## 8. What would move the needle next

1. ✅ *Done 2026-09-13: gates flipped default off.* **Ship the watchdog, stop shipping the hints as a proven win.** `6672af8` is the build with
   evidence behind it. Either flip `ADA_TIME_HINTS` and `ADA_BASH_CLAMP_REMAINING` back to
   default off, or keep them and state in the shipped documents that they are carried on an
   efficiency result with no pass-rate support. Doing neither is how the +28 happened.
2. **Verification discipline is the whole remaining gap.** 25 of the candidate's 31 failures
   are the agent claiming success against a grader that disagrees. That is a larger pool than
   anything pacing can reach.
3. **The wrap-up threshold is the one T1.2 knob worth a run.** §4 predicts that raising
   `ADA_WRAP_UP_MS` — or firing the wrap-up only when the task has actually consumed most of
   its budget — recovers the 5 lost clean-finish tasks without giving back the 34 → 7
   interrupt reduction. That is a same-day paired A/B against `6672af8`, ≈$6.
4. **Budget for two arms on one day, always.** Every wrong number in this campaign came from
   a control measured on a different day.

## Artifacts

| Item | Path |
|---|---|
| Driver, status, resource log | [`run_ctrl_vs_t12.sh`](run_ctrl_vs_t12.sh), `ctrl_vs_t12_STATUS`, `ctrl_vs_t12_driver.log`, `ctrl_vs_t12_memory.log` |
| Per-task logs, both arms | `ctrl_vs_t12_control.log`, `ctrl_vs_t12_candidate.log` |
| Raw diagnostics, control R7 | `../autoresearcher/targets/ada-t01gateoff/.autoresearch/diagnostics/20260912T1603Z-t04ctrl2/0.json` |
| Raw diagnostics, candidate R8 | `../autoresearcher/targets/ada/.autoresearch/diagnostics/20260912T1603Z-t12cand2/0.json` |
| Analysis → JSON | [`ctrl_vs_t12_analysis.py`](ctrl_vs_t12_analysis.py) → [`CTRL_VS_T12_PAIRED_ANALYSIS.json`](CTRL_VS_T12_PAIRED_ANALYSIS.json) |
| Machine verification of this document | [`ctrl_vs_t12_verify.py`](ctrl_vs_t12_verify.py) |
| Canonical index of all eight runs | [`RUN_REGISTRY.md`](RUN_REGISTRY.md) |
