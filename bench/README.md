# `bench/` — file guide

Every scored run in the campaign left the same set of files, so they are listed here by
family rather than one by one. Run IDs (R1–R10, BP, P3) are defined in
[`RUN_REGISTRY.md`](RUN_REGISTRY.md).

## Start here

| File | What it is |
|---|---|
| `RUN_REGISTRY.md` | Every scored SetupBench run, by ID. Read its re-check banner first. |
| `verify_docs.py` | Checks every result stated in `../README.md`, `../blog.md` and this guide, sentence by sentence, against the raw rows or the file it cites. |
| `baseline_vs_best_verify.py`, `ctrl_vs_t12_verify.py`, `fresh_rem81_verify.py` | Re-derive the confirmation run, the same-day ladder and the R5/R6 morning run from the raw rows. `ctrl_vs_t12_verify.py` also fails if a withdrawn number appears anywhere without being marked as withdrawn. |
| `harness/archive_integrity_check.py` | Row counts, pass counts and recorded build of every archived run. |
| `confirmation_table.py` | Prints the README's "every attempt" table of the confirmation run (R9/R10). |
| `verify_builds.sh` | Recovers the campaign's git history from `ada-campaign.bundle` and checks every build's agent tree (needs git and network). |

## Raw evidence

| Path | What it is |
|---|---|
| `diagnostics/` | Per-task results of every scored run: one row per task with `passed`, `timed_out`, `turns`, `duration_seconds`, `agent_is_error`, `grader_returncode`, plus the run's `protocol` (model, budget, concurrency, SetupBench commit, harness hashes). Baseline arms are in `ada-baseline/`, watchdog-only arms in `ada-t01gateoff/`, Phase A's hand-run sets in `manual/`. |
| `p3_evidence/` | The P3 candidate arms, including the voided first attempt (partial rows only). |
| `results-*/` | Terminal-Bench trial output from Harbor, one folder per arm. |
| `ada-campaign.bundle` | The campaign's git history, on top of `rabbah/ada` at `ebaeb9a`. |

## Run families

Each run has a driver script (`run_*.sh`), logs (`*_driver.log`, `*_memory.log`, one log per
arm), a `*_STATUS` file, an analysis script (`*_analysis.py`) that writes a result JSON, and a
report.

| Runs | Driver and logs | Analysis → result | Report |
|---|---|---|---|
| R9/R10, the confirmation | `run_baseline_vs_best.sh` (the pass rule is at its top), `run_bvb_rep2_parallel.sh`, `baseline_vs_best_*` | `baseline_vs_best_analysis.py` → `BASELINE_VS_BEST_20260915T0825Z.json` | `../ada/RESULTS.md` |
| R7/R8, the same-day ladder | `run_ctrl_vs_t12.sh`, `ctrl_vs_t12_*` | `ctrl_vs_t12_analysis.py` → `CTRL_VS_T12_PAIRED_ANALYSIS.json` | `CTRL_VS_T12_REPORT.md` |
| R5/R6, the morning run | `fresh_rem81_*` (driver script removed in packaging) | `fresh_rem81_analysis.py` → `FRESH_REM81_PAIRED_ANALYSIS.json` | `FRESH_REM81_REPORT.md` |
| T1.2 ladder: dev-12, val-12, R3/R4 (withdrawn) | `t12_*_runid.txt`, `t04_control_run.log` (R3), `t12_rem81_candidate.log` (R4) | `t12_paired_analysis.py`, `t12_rem81_analysis.py` → `T12_*_PAIRED_ANALYSIS.json` | `../ada/RESULTS.md` |
| T1.1 dev-12 | — | `T11_DEV12_PAIRED_ANALYSIS.json` | `../ada/RESULTS.md` |
| Time-hint smoke tests | — | `T12_SMOKE_RESULTS.json`, `T12_SMOKE_B2_RESULTS.json`; logs in `../ada/evidence/t12/` | — |
| Phase C: budget probe (BP) | `budget_probe_driver.sh` | `budget_probe_analysis.py` | `BUDGET_PROBE_REPORT.md` |
| Phase C: P3 | `run_p3_paired.sh`, `p3_paired_*`, `P3_P2_PREREGISTRATION.md`, `FAILING25.txt` (the task pool) | `p3_paired_analysis.py` → `P3_PAIRED_20260917T0602Z.json` | `P3_PAIRED_REPORT.md`, `PHASE_C_SUMMARY.md` |
| Phase A archive (R1/R2 and the withdrawn 59/81) | — | `harness/FINAL81_*`, `harness/POOLED81_*`, `harness/VALIDATION12_*` | `STALL_DIAGNOSIS_FINAL.md` |
| Terminal-Bench 2.0 | `ada_agent.py` (the Harbor adapter; `__init__.py` makes `bench` importable), `select_tasks.py` and `task-selection*.md` (task choice), `parse_results.py` (Harbor output → table) | `final40_paired_analysis.py` → `FINAL40_PAIRED_ANALYSIS.json`; `tb20_paired_analysis.py` → `TB20_PAIRED_ANALYSIS.json` | `TB_REPORT_40.md`, `TB_REPORT.md` (10 tasks) |

## Harness

`harness/setupbench_ada_runner.ts` launches Ada inside each task's container and is
byte-identical to the runner every run recorded. `harness/setupbench_ada_domain_eval.py`
drives a run and calls the grader. It matches no `evaluator_sha256` that a run recorded; the exact
versions that scored the runs were not kept.
`harness/setupbench_ada_eval.py` is the matched two-arm evaluator. `harness/smoke1.txt` is a
single-task smoke list. `harness/SETUPBENCH_ADA_RAW.json` and `harness/ADA_HOLDOUT_5X_RAW.json`
are from an earlier exploratory evaluation of Ada at commit `0c5e1da` (not in the bundle), with
a 600 s limit; no result in this campaign uses them. The SetupBench
checkout itself (`microsoft/SetupBench` at `041a412`) is not included.

## Other tooling

`t12_apply_edits.py` and `t12_append_tests.py` applied the T1.2 code change and its tests to
`../ada/agent/`. `figures/` holds the blog's charts. Each SVG states its values in its
`<desc>`, and `verify_docs.py` checks them.

## Packaging record (2026-09-18)

`packaging-20260918/` holds the four scripts that archived the evidence when the working
tree was packaged, and `changes.diff`, which shows every file those scripts changed, before
and after. The changes were file paths, regenerated analysis JSONs with identical numbers,
and the Versions table in `../ada/RESULTS.md`. The one raw file packaging had touched has been
restored to its original bytes. The scripts keep the paths of the machine they ran on.

## Builds

`../ada/` is a snapshot of tag `ada-best-61pct-20260916` (commit `32f4754`, the shipped build
`5f4c5c0` plus documentation). No agent code differs from that tag. Nine files do:

- `../ada/RESULTS.md`, and five scripts in `../ada/evidence/`, edited during packaging on
  2026-09-18 to point at the archived evidence. `RESULTS.md` also carries a dated note at the
  top. The two verify scripts among them also check the repository README and blog.
- `../ada/evidence/t12/CTRL_VS_T12_PAIRED_ANALYSIS.json`, regenerated from the archived results
  during packaging. Only its timestamp and file paths changed; every number is identical.
- `../ada/REPORT.md`, which carries a dated note at the top; the text below it is unchanged.
- `../ada/scripts/probe-thinking.ts`, a thinking-budget probe, which was never committed.

The campaign's git history (its commits, the three build branches and both tags the records
cite) is in `ada-campaign.bundle`, on top of upstream `rabbah/ada` at `ebaeb9a`. From the
repository root:

```bash
git clone https://github.com/rabbah/ada ada-history && cd ada-history
git fetch ../bench/ada-campaign.bundle 'refs/heads/*:refs/remotes/campaign/*' 'refs/tags/*:refs/tags/*'
git rev-parse --short=12 5f4c5c0:agent     # dab704de524a, the shipped agent code
```

`bash bench/verify_builds.sh` runs this recipe and checks every build the records name. The
records name the shipped build by four commits with the same agent code (tree `dab704de524a`):
`5f4c5c0` (the build), `1d82e56` (as measured in R9/R10, with later documentation), `32f4754`
(the tag) and `c6f917e` (committed in a mirror workspace that packaging removed; it is in the
bundle on branch `p3-late-wrapup`).

One build cannot be rebuilt from history. The origin arm of R9/R10 ran as `417a8f1`, which the
records describe as `df0c537` with its runner shim committed. R1 and R5 ran `df0c537` with one
uncommitted file, `agent/system-guidance.ts`; R9/R10 record `417a8f1` with none. Its agent tree,
`df8a18c09278`, is recorded in the results and asserted by `baseline_vs_best_verify.py`, but the
commit itself is not in the bundle, so the shim cannot be compared byte for byte.

## Re-running an evaluation

Packaging on 2026-09-18 removed regenerable bulk: the SetupBench task-input cache, the variant
tarballs, and the local SetupBench checkout. Re-running an evaluation needs
[microsoft/SetupBench](https://github.com/microsoft/SetupBench) at `041a412` in
`harness/setupbench/`, Docker, and an OpenRouter key. The driver scripts (`run_*.sh` and
friends) are the record of how each run was launched, and keep the absolute paths of the
machine they ran on.

## Corrections to the campaign's records

Before publication, every claim in the repository README and the blog was checked against the
raw per-task results. Nine statements in the campaign's own records do not hold or cannot be
confirmed. The records (`../ada/RESULTS.md`, `../ada/REPORT.md`, `RUN_REGISTRY.md`,
`PHASE_C_SUMMARY.md` and `CTRL_VS_T12_REPORT.md`) keep their original text, with a dated note
at the top of each that points here.

| The record says | The raw data shows |
|---|---|
| The watchdog (T0.1) is "the entire mechanism" of the gain (`../ada/RESULTS.md`) | The step from `df0c537` to `6672af8` carries all four default-on changes, and no run separates them. Of the 29 passes recovered where the origin build timed out, 18 came after a watchdog stop and 11 did not involve the watchdog. |
| R3, the withdrawn control, ran on 2026-09-10 (its run ID is `20260910T0728Z`), so the +28 compared runs from different days | R3 records commit `6672af8`, whose commit time in `ada-campaign.bundle` is 07:24 UTC on **2026-09-11**, the day after the date in its run ID. Which day R3 ran is therefore uncertain. The comparison stays withdrawn either way: its arms were not run together, and the same build scored 54/81 on 2026-09-12. |
| R3 and R7 did "identical work" | Almost the same number of turns, or model responses (1,544 against 1,554), but the watchdog stopped 63 of R3's attempts against 34, and R3 took 23% longer in total. |
| Phase C found "zero 480 s clock-outs", so the Bash cap (P2) and install hook (P4) had nothing to fix | The harness stopped no attempt, but the watchdog stopped 28 of the shipped build's 41 failed attempts in the P3 run, and 8 of 17 failed attempts at 960 s. P2 was only ever measured inside the time-reminders bundle (T1.2), and P4 never ran; neither has been tested alone. |
| Phase C's "17 hard clock-outs" (`PHASE_C_SUMMARY.md`) | These are the 960-second run's 17 failed attempts without a harness error: the watchdog stopped 8 of them, and 9 finished and failed their check. |
| R2's 43 zero-turn attempts came from the watchdog stop | They were a reporting bug: 41 were checked and 19 passed. Only 2 were stopped by the harness (commit `6672af8`'s message). |
| R10a had 40 zero-turn attempts (`RUN_REGISTRY.md`) | 41, in both the raw results and `BASELINE_VS_BEST_20260915T0825Z.json`. |
| Terminal-Bench compared the two builds under one protocol | The origin build ran on 2026-09-07 and `08a8d5d` on 2026-09-10. |
| Packaging (2026-09-18) only moved and repointed files | It also rewrote one path field, `incumbent_source`, in the raw file `diagnostics/manual/remaining81_final_failures31.json`. That file is restored to its original bytes; every other packaging change is listed in `packaging-20260918/changes.diff`. |

`RUN_REGISTRY.md` also cites a footnote ⁴ for `417a8f1` that it never defines; "Builds" above
says what is known about that build.
