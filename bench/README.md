# `bench/` — file guide

Every scored run in the campaign left the same set of files, so they are listed here by
family rather than one by one. Run IDs (R1–R10, BP, P3) are defined in
[`RUN_REGISTRY.md`](RUN_REGISTRY.md).

## Start here

| File | What it is |
|---|---|
| `RUN_REGISTRY.md` | Every scored SetupBench run, by ID. Read its re-check banner first. |
| `verify_docs.py` | Checks every result stated in `../blog.md` and `../README.md`, sentence by sentence, against the raw rows or the file it cites. |
| `baseline_vs_best_verify.py`, `ctrl_vs_t12_verify.py`, `fresh_rem81_verify.py` | Re-derive the confirmation run, the same-day ladder and the R5/R6 morning run from the raw rows. |
| `harness/archive_integrity_check.py` | Row counts, pass counts and recorded build of every archived run. |
| `confirmation_table.py` | Prints the full R9/R10 baseline-vs-shipped table. |
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
| R9/R10, the confirmation | `run_baseline_vs_best.sh` (the pre-registered rule is at its top), `run_bvb_rep2_parallel.sh`, `baseline_vs_best_*` | `baseline_vs_best_analysis.py` → `BASELINE_VS_BEST_20260915T0825Z.json` | `../ada/RESULTS.md` |
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
are from an earlier exploratory evaluation (6 and 4 tasks, a 600 s budget, Ada at commit
`0c5e1da`, which is not in the bundle); no result in this campaign uses them. The SetupBench
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
