# Fresh same-day paired remaining81 — 2026-09-12

Run `20260912T1031Z`, driver `run_rem81.sh`, both arms on one machine on one day.
Every number below is reproducible with `python3 bench/fresh_rem81_analysis.py`,
which reads the two run logs and three diagnostics files and writes
[`FRESH_REM81_PAIRED_ANALYSIS.json`](FRESH_REM81_PAIRED_ANALYSIS.json).

**In one line:** the run converts 15 tasks, but **all 15 come out of tasks where the
baseline hung with zero turns**, so it measures the `08a8d5d` watchdog and not the
promoted T1.2 change; it also measures the noise floor for the first time (**the
identical build scores 46/74 then 43/74 on consecutive days, flipping 15 of 74**);
and — the finding that matters most — it shows **the T0.4 control behind the promoted
52/81 vs 24/81 (now withdrawn) is beaten 18–0 by a strictly older build on tasks
neither one hangs on**, so that control is a depressed anchor and the promoted effect size is inflated
by an unknown amount.


---

## Addendum — three of this report's findings are now settled (2026-09-13)

This document is left exactly as written. The run it describes (**R5** and **R6** in
[`RUN_REGISTRY.md`](RUN_REGISTRY.md)) posed three questions it could not answer. The
same-day control run of 2026-09-12 evening — **R7** and **R8**, reported in
[`CTRL_VS_T12_REPORT.md`](CTRL_VS_T12_REPORT.md) — answers all three.

| in this document | what the same-day control run found |
|---|---|
| §6: the T0.4 control `6672af8` is "beaten 18–0 by its own ancestor" on the 33 tasks neither hangs on, so it may carry a defect T1.2 masked | **No defect. That control (R3) simply had a bad day.** Re-run on 2026-09-12, the identical `6672af8` tree scores **54/81 against R3's 24/81 — 30 gained, 0 lost, p = 1.863e-09**, with turns 0.6% apart and zero timeouts both days. Against that normal-day control, the same non-hang subset reads 34/35 → 33/35: a wash, not 18–0. |
| §7: "T1.2's effect size is unmeasured and should not be quoted" | **Now measured.** Same-day, T1.2 as the sole variable: **54/81 → 50/81, net −4, 9 lost / 5 gained, p = 0.424.** The pre-registered promotion bar (≥ +3 net conversions) is not met and **the promotion has been withdrawn.** It is not evidence of harm — 14 discordant on n=81 is inside the noise floor. |
| §5: the noise floor is "20% per-task churn on identical code" (15 of 74 flipping) | Refined across four same-build pairs: ordinary churn is **10–13 discordant of ~80** with the aggregate unchanged. R3 → R7's **30 discordant, all one-way** is not churn — it is a day-level outlier, and the only one in the campaign. |
| §4: all 15 conversions come out of baseline hangs, so this run measures the watchdog, not T1.2 | **Confirmed and strengthened on the full n=81 same-day pair.** R5 → R7: on the 46 tasks `df0c537` hung on, **0/46 → 21/46** (p = 9.5e-07); on the 35 it ran, 34/35 → 33/35. The watchdog is the campaign's result and is worth **+20, p = 1.097e-05**. |

Nothing in the body below is retracted; the readings above supersede its open questions.

---

## 1. What was actually run

| arm | build | workspace | artifact |
|---|---|---|---|
| 1 | `df0c537` — campaign-origin baseline | `ada-baseline` worktree (removed 2026-09-18; archived to `bench/diagnostics/ada-baseline/`) | `fresh_rem81_baseline.log`, diagnostics `20260912T1031Z-frem81base/0.json` |
| 2 | `2e495bb` — T1.2 time-awareness bundle | `ada` worktree (former mirror, removed 2026-09-18; archived to `bench/diagnostics/`) | `fresh_rem81_best.log`, **no diagnostics** (see §2) |

Protocol: suite `remaining81`, concurrency 4, task timeout 480 s, grader timeout
600 s, seed 20260907, model `z-ai/glm-5.3-flash`. Arm 1 ran 10:31–12:51 UTC, arm 2
12:51–14:59 UTC.

**This is not the pairing behind the promoted claim.** The control for `RESULTS.md`'s
52/81 vs 24/81 (withdrawn — see the addendum) is `6672af8` (T0.4). Arm 1 here is
`df0c537`, nine commits older, which
predates `08a8d5d` — the container-anchored hard deadline and stall-retry watchdog.
That single fact governs the whole reading of §4.

## 2. Arm 2 wrote no diagnostics, and 7 tasks are unevaluable

Arm 2 returned exit 2. Seven of its 81 rows came back `valid=0`, and
`setupbench_ada_domain_eval.py:257` returns 2 without writing the report when any row
is invalid. The failures are docker infrastructure, not the agent:

```
docker exec … test -f /testbed/.ada-exit   timed out after 10 s   (×3)
docker run  … ubuntu:22.04 …               timed out after 60 s   (×4)
```

They cluster at the run's peak memory pressure — minimum available 1917 MB and swap
2557 MB at 14:19 UTC, against the driver guard's 1200 MB abort floor, which never
tripped. Prior runs of this suite recorded 0 MB swap.

Excluded under the **T0.5 / E10 unevaluable policy** already used by
`FINAL40_PAIRED_ANALYSIS.json`: a row invalid in either arm is dropped from both.
Seven out, **n = 74**.

`beautify-web-js-beautify-6de9268`, `bgsetup-autossh-logging`,
`bgsetup-autossh-reverse-tunnel`, `bgsetup-gunicorn-systemd-socket`,
`deps-ultimate-frontrunning-bot-449d6`, `hoodiehq-hoodie-bd1354f`, `monero-8468549`.

All seven were invalid in arm 2 only; arm 1 had zero invalid rows. The exclusion is
applied symmetrically anyway.

Consequence for what can be reported: arm 2 has no `duration_seconds`,
`terminal_result`, `agent_stop_reason` or `grader_returncode`. The wall-clock and
"claimed verified but grader failed" metrics quoted for earlier rungs **cannot be
computed for this run**, and are omitted rather than estimated.

## 3. The headline contrast

74 paired tasks, exact McNemar, Newcombe Method 10 95% CI:

| contrast | pass | difference (95% CI) | gained / lost | p |
|---|---|---|---|---|
| `df0c537` → `2e495bb` (T1.2) | 31/74 → **43/74** | **+16.22pp** [0.14, 31.16] | 15 / 3 | **0.0075** |

Taken alone that reads as a clear win. It is not what it looks like.

## 4. Every conversion is a baseline hang

41 of the baseline's 74 rows are timeouts, and **all 41 have `turns=0`** — the agent
never emitted a single turn before the 480 s cap. T1.2 timed out on none.

Split the same 74 tasks on whether the baseline actually ran:

| subset | n | `df0c537` | T1.2 | difference | gained / lost | p |
|---|---:|---:|---:|---|---|---|
| baseline **hung** (zero-turn timeout) | 41 | 0/41 | **15/41** | **+36.59pp** [21.02, 51.88] | 15 / 0 | **6.1e-05** |
| baseline **ran** | 33 | **31/33** | 28/33 | −9.09pp [−25.46, 6.90] | 0 / 3 | 0.25 |

**15 of 15 conversions sit in the hung subset. Zero conversions sit in the subset the
baseline actually ran** — there, T1.2 is three tasks behind, which at p = 0.25 is not
a significant regression but is certainly not a gain.

`df0c537` predates `08a8d5d`. A zero-turn 480 s timeout is that build stalling with no
deadline to cut it off. So the entire +16.22pp is attributable to the hard deadline and
watchdog, and **none of it is evidence for the T1.2 time hints.**

The honest headline for §3 is *"the watchdog converts 15 tasks the pre-watchdog build
hung on; on tasks both builds could run, the two are indistinguishable"* — not
"T1.2 is +16pp".

### By task type

| task type | n | `df0c537` | T1.2 | difference |
|---|---:|---:|---:|---:|
| `reposetup` | 44 | 16 (36%) | 25 (57%) | +20.4pp |
| `dependency_resolution` | 13 | 1 (8%) | 4 (31%) | +23.1pp |
| `dbsetup` | 13 | 10 (77%) | 10 (77%) | 0.0pp |
| `bgsetup` | 4 | 4 (100%) | 4 (100%) | 0.0pp |

The two types that move are the two where the baseline hung; `dbsetup` and `bgsetup`
are flat because the baseline completed them.

Turns on the paired set: 708 baseline vs 1284 T1.2 — the baseline's number is deflated
by the 41 runs that produced no turns at all, so it is not a comparable efficiency
figure and no efficiency claim is made from it.

## 5. The noise floor, measured properly for the first time

The same build `2e495bb` ran this suite on 2026-09-11 and again on 2026-09-12.
Restricted to the same 74 tasks:

| contrast | pass | difference (95% CI) | gained / lost | p |
|---|---|---|---|---|
| T1.2 Sep-11 → T1.2 Sep-12 (**identical build**) | 46/74 → 43/74 | −4.05pp [−19.32, 11.48] | 6 / 9 | 0.61 |

The aggregate is stable. The per-task behaviour is not: **15 of 74 tasks — 20% —
change verdict between two runs of byte-identical code.** Nine tasks that passed on
Sep-11 failed on Sep-12; six did the reverse.

This upgrades the campaign roadmap's **E11** estimate (`fina_run.md`, working doc
removed during final packaging 2026-09-18) from "±2–3 tasks on n=12" to a measured 20%
per-task flip rate on n=74, and it sets the bar any future rung has to clear.

## 6. The control behind the promoted claim does not hold up

Restricting the published comparison to the same 74 tasks, it looks robust:

| contrast | pass | difference (95% CI) | gained / lost | p |
|---|---|---|---|---|
| T0.4 control `6672af8` → T1.2 `2e495bb`, both stored | 22/74 → 46/74 | +32.43pp [16.46, 46.16] | 27 / 3 | 8e-06 |

27 against 3 is far outside the 15-discordant noise floor of §5, and asymmetric where
noise is symmetric. On its own anchor the promoted result is statistically solid.

**The anchor is the problem.** `6672af8` is `df0c537` *plus* the watchdog work — a strict
superset. On tasks where neither build hangs it cannot legitimately be much worse than its
own ancestor. Test it on the 33 tasks `df0c537` ran, zero timeouts on either side:

| build | run date | pass on those 33 |
|---|---|---:|
| `df0c537` — pre-watchdog, **oldest build in the campaign** | 2026-09-12 | **31/33** |
| `6672af8` — T0.4 control, **the anchor for the withdrawn 52/81 vs 24/81** | 2026-09-10 | **13/33** |
| `2e495bb` — T1.2 | 2026-09-12 | 28/33 |

| contrast | pass | gained / lost | p |
|---|---|---|---|
| `6672af8` (Sep-10) → `df0c537` (Sep-12), 33 tasks | 13/33 → **31/33** | 18 / 0 | **7.6e-06** |

**The control loses 18 tasks to its own ancestor and wins none.** Both arms had zero
timeouts on this subset, so the deficit is grader failures, not hangs. A build cannot be
beaten 18–0 by the code it was built on top of.

Two readings, and nothing on disk separates them:

1. The 2026-09-10 run was executed on a badly degraded day.
2. `6672af8` carried a real defect that T1.2 later masked.

The campaign roadmap (`fina_run.md` §6, removed 2026-09-18) already recorded this run as anomalous — 24/81 against the Sep-9
incumbent's 50/81 on nearly the same lineage — called it "E11 writ large", and then made
it the anchor for everything after, on the grounds that it was fresh. Freshness is not
soundness. `df0c537`'s healthy 31/33 on Sep-12 is consistent with the Sep-9 incumbent and
inconsistent with the control, which makes reading (1) the more likely of the two and
makes the control an outlier low either way.

**Consequence.** The promoted "+28 conversions, p = 7.66e-07" is measured against a
depressed control. Its *direction* is probably real. Its *magnitude* is inflated, and the
size of the inflation is not estimable from any run on disk.

## 7. Claims this run supports — and does not

**Supported**

- The `08a8d5d` watchdog converts 15 of 41 tasks that the pre-watchdog build hung on,
  with zero regressions in that subset (p = 6.1e-05).
- The identical build flips 20% of tasks day to day while its aggregate holds
  (46/74 vs 43/74, p = 0.61).
- The promoted T1.2 comparison is statistically robust *on its own anchor* (27/3,
  p = 8e-06) — which is a statement about the arithmetic, not about the effect size.

**Not supported**

- This run says **nothing** about the T1.2 time hints. Its control is the wrong build,
  and on the subset where the control was functional T1.2 is three tasks behind.
- No efficiency claim: arm 2 has no durations, and the baseline's turn count is
  deflated by 41 zero-turn runs.
- Nothing about the 7 excluded tasks; they were not re-run.
- **The promoted +28 conversions is not supported as an effect size.** Its control is
  beaten 18–0 by a strictly older build (§6). Nothing here says how much of the +28 is
  T1.2 and how much is a depressed anchor.

## 8. What would actually answer the open question

A same-day paired run of `2e495bb` against the **T0.4 control `6672af8`**, both arms fresh.
This was worth doing for hygiene before §6; now it is required. It settles both open
questions at once — whether the control's 13/33 was a bad day or a real defect, and what
T1.2 is actually worth against a sound anchor. Until it runs, the defensible summary of
the campaign is:

- the watchdog (`08a8d5d`) removes a large, real failure mode — 41 zero-turn hangs → 0;
- T1.2's effect on top of that is **unmeasured**, and the one same-day comparison available
  has it 3 tasks behind on the non-hanging subset (p = 0.25).

## Artifacts

| item | path |
|---|---|
| Analysis JSON (all contrasts, 74 per-task rows) | `bench/FRESH_REM81_PAIRED_ANALYSIS.json` |
| Script that produced it | `bench/fresh_rem81_analysis.py` |
| Arm 1 log / diagnostics | `bench/fresh_rem81_baseline.log`, `bench/diagnostics/ada-baseline/20260912T1031Z-frem81base/0.json` |
| Arm 2 log (no diagnostics) | `bench/fresh_rem81_best.log` |
| Memory guard trace | `bench/fresh_rem81_memory.log` |
| Driver + status | `run_rem81.sh` (session scratchpad), `bench/fresh_rem81_STATUS`, `bench/fresh_rem81_driver.log` |
| Stored comparators | `bench/diagnostics/20260911T1540Z-t12rem81/rem81_t12_candidate.json`, `bench/diagnostics/20260910T0728Z-t04ctrl/0.json` |
