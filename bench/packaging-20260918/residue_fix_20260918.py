#!/usr/bin/env python3
"""Final packaging 2026-09-18 — subtask-4 residue + subtask-5 Versions table.

Repoints every remaining stale path reference (former autoresearcher/targets/
workspaces, removed working docs, deleted tarballs / final_verify scripts) to
the archived bench/diagnostics/ layout, adds regeneration/annotation notes,
and inserts the canonical Versions lineage table into ada/RESULTS.md.

Every edit is occurrence-asserted: the script exits non-zero if any expected
string is not found. Backups are written to bench/harness/residue_backup_20260918/.
Never touches anything under ada/agent/.
"""

import shutil
import sys
from pathlib import Path

ROOT = Path("/home/azureuser/adaAgent")
BENCH = ROOT / "bench"
BACKUP = BENCH / "harness" / "residue_backup_20260918"
BACKUP.mkdir(parents=True, exist_ok=True)

EDITED = []
FAILED = []


def sub(rel, old, new, expect=None):
    """Replace all occurrences of `old` with `new` in ROOT/rel. Occurrence-asserted."""
    path = ROOT / rel
    text = path.read_text()
    n = text.count(old)
    if n == 0:
        FAILED.append(f"{rel}: NOT FOUND: {old[:90]!r}")
        return
    if expect is not None and n != expect:
        FAILED.append(f"{rel}: expected {expect} occurrence(s), found {n}: {old[:90]!r}")
        return
    if old != new:
        dst = BACKUP / rel.replace("/", "__")
        if not dst.exists():
            shutil.copy2(path, dst)
        path.write_text(text.replace(old, new))
    EDITED.append(f"{rel}: {n}x <- {new[:70]!r}")


# ---------------------------------------------------------------- generic path
# Longest-first generic mapping for the archived diagnostics layout.
GENERIC = [
    ("/home/azureuser/adaAgent/autoresearcher/targets/ada-baseline/.autoresearch/diagnostics/",
     "/home/azureuser/adaAgent/bench/diagnostics/ada-baseline/"),
    ("/home/azureuser/adaAgent/autoresearcher/targets/ada-t01gateoff/.autoresearch/diagnostics/",
     "/home/azureuser/adaAgent/bench/diagnostics/ada-t01gateoff/"),
    ("/home/azureuser/adaAgent/autoresearcher/targets/ada/.autoresearch/diagnostics/",
     "/home/azureuser/adaAgent/bench/diagnostics/"),
    ("../autoresearcher/targets/ada-baseline/.autoresearch/diagnostics/",
     "../bench/diagnostics/ada-baseline/"),
    ("../autoresearcher/targets/ada-t01gateoff/.autoresearch/diagnostics/",
     "../bench/diagnostics/ada-t01gateoff/"),
    ("../autoresearcher/targets/ada/.autoresearch/diagnostics/",
     "../bench/diagnostics/"),
    ("autoresearcher/targets/ada-baseline/.autoresearch/diagnostics/",
     "bench/diagnostics/ada-baseline/"),
    ("autoresearcher/targets/ada-t01gateoff/.autoresearch/diagnostics/",
     "bench/diagnostics/ada-t01gateoff/"),
    ("autoresearcher/targets/ada/.autoresearch/diagnostics/",
     "bench/diagnostics/"),
    ("targets/ada/.autoresearch/diagnostics/", "bench/diagnostics/"),
]

GENERIC_FILES = [
    "bench/harness/FINAL81_RESULT_SET.json",
    "bench/harness/POOLED81_PAIRED_ANALYSIS.json",
    "bench/harness/FINAL81_PAIRED_ANALYSIS.json",
    "bench/diagnostics/manual/remaining81_final_failures31.json",
    "ada/evidence/t12/CTRL_VS_T12_PAIRED_ANALYSIS.json",
    "bench/BUDGET_PROBE_REPORT.md",
    "bench/PHASE_C_SUMMARY.md",
    "bench/P3_P2_PREREGISTRATION.md",
    "bench/FRESH_REM81_REPORT.md",
    "bench/CTRL_VS_T12_REPORT.md",
    "ada/RESULTS.md",
]
for rel in GENERIC_FILES:
    path = ROOT / rel
    text = path.read_text()
    total = 0
    for old, _ in GENERIC:
        total += text.count(old)
    if total == 0:
        FAILED.append(f"{rel}: no generic path hits (expected some)")
        continue
    dst = BACKUP / rel.replace("/", "__")
    if not dst.exists():
        shutil.copy2(path, dst)
    for old, new in GENERIC:
        text = text.replace(old, new)
    path.write_text(text)
    EDITED.append(f"{rel}: {total}x generic path repoint")

# ------------------------------------------------- bench/BUDGET_PROBE_REPORT.md
sub("bench/BUDGET_PROBE_REPORT.md",
    "- Source: `bench/diagnostics/budget-probe-20260916T0730Z`",
    "- Source: `bench/diagnostics/budget-probe-20260916T0730Z` "
    "(archived 2026-09-18 from the former autoresearcher workspace)")

# ----------------------------------------------------- bench/PHASE_C_SUMMARY.md
sub("bench/PHASE_C_SUMMARY.md",
    "| Tag (both trees: `ada/` and `autoresearcher/targets/ada/`) | `ada-best-61pct-20260916` |",
    "| Tag (canonical tree `ada/`) | `ada-best-61pct-20260916` |")
sub("bench/PHASE_C_SUMMARY.md",
    "| `autoresearcher/targets/ada` commit | `c6f917e` |",
    "| Former mirror commit (historical pin; mirror removed 2026-09-18) | `c6f917e` |")
sub("bench/PHASE_C_SUMMARY.md",
    "- **Pre-registered rule** (fixed in `plans/plan.md` before spend): >= 12 pass -> SLOW;",
    "- **Pre-registered rule** (fixed in the campaign plan before spend; `plans/plan.md` was\n"
    "  removed during final packaging 2026-09-18 — the rule is recorded here and in\n"
    "  `bench/P3_P2_PREREGISTRATION.md`): >= 12 pass -> SLOW;")
sub("bench/PHASE_C_SUMMARY.md",
    "Per `plans/plan.md`, P5 runs only if",
    "Per the campaign plan (`plans/plan.md`, removed during final packaging 2026-09-18),\nP5 runs only if")
sub("bench/PHASE_C_SUMMARY.md",
    "the §9 ceiling estimate in `improvements.md`",
    "the §9 ceiling estimate in the campaign headroom analysis\n"
    "  (`improvements.md`, removed during final packaging 2026-09-18)")
sub("bench/PHASE_C_SUMMARY.md",
    "pre-registrations — `bench/P3_P2_PREREGISTRATION.md`,\n"
    "`plans/plan.md`; campaign record — `ada/RESULTS.md` (Phase C section); headroom\n"
    "analysis — `improvements.md` (§0).",
    "pre-registrations — `bench/P3_P2_PREREGISTRATION.md` (the campaign\n"
    "plan and headroom working docs were removed during final packaging 2026-09-18);\n"
    "campaign record — `ada/RESULTS.md` (Phase C section).")

# ------------------------------------------------ bench/P3_P2_PREREGISTRATION.md
sub("bench/P3_P2_PREREGISTRATION.md",
    "per improvements.md §9 step 3).",
    "per the campaign headroom analysis §9 step 3 — working doc `improvements.md`\n"
    "removed during final packaging 2026-09-18; the trigger rule is recorded in\n"
    "bench/PHASE_C_SUMMARY.md §2).")
sub("bench/P3_P2_PREREGISTRATION.md",
    "cross-checked\nagainst improvements.md §2).",
    "cross-checked\nagainst the campaign headroom analysis §2 (`improvements.md`, removed 2026-09-18)).")
sub("bench/P3_P2_PREREGISTRATION.md",
    "Rule (pre-registered in\nplans/plan.md): >=12 SLOW",
    "Rule (pre-registered in the campaign plan, `plans/plan.md`, removed 2026-09-18):\n>=12 SLOW")
sub("bench/P3_P2_PREREGISTRATION.md",
    "**Intent (improvements.md §5 P3):**",
    "**Intent (campaign headroom analysis §5 P3 — `improvements.md`, removed 2026-09-18):**")

# ------------------------------------------------------- bench/P3_PAIRED_REPORT.md
sub("bench/P3_PAIRED_REPORT.md",
    "- Shipped arm: `targets/ada` @ `ada-best-61pct-20260916` (commit `c6f917e`,",
    "- Shipped arm: `ada/` @ `ada-best-61pct-20260916` (former mirror commit `c6f917e` —\n"
    "  historical pin, mirror removed 2026-09-18;")

# ------------------------------------------------------ bench/CTRL_VS_T12_REPORT.md
sub("bench/CTRL_VS_T12_REPORT.md",
    "**In one line:** this is the run [`fina_run.md`](../fina_run.md) §7 marked REQUIRED, and it",
    "**In one line:** this is the run the campaign roadmap §7 (`fina_run.md`, working doc\n"
    "removed during final packaging 2026-09-18) marked REQUIRED, and it")
sub("bench/CTRL_VS_T12_REPORT.md",
    "The pre-registered promotion rule (`fina_run.md` §3 rule 4) was *no significant",
    "The pre-registered promotion rule (campaign spec §3 rule 4, `fina_run.md` — removed\n"
    "2026-09-18; rule restated in `RUN_REGISTRY.md` and `ada/RESULTS.md`) was *no significant")
sub("bench/CTRL_VS_T12_REPORT.md",
    "| preflight: `targets/ada-t01gateoff` `agent/` == `6672af8`, `targets/ada` `agent/` == `2e495bb` | ✅ in driver log |",
    "| preflight: control worktree `agent/` == `6672af8`, candidate worktree `agent/` == `2e495bb` "
    "(worktrees removed 2026-09-18; diagnostics archived under `bench/diagnostics/`) | ✅ in driver log |")
sub("bench/CTRL_VS_T12_REPORT.md",
    "| Raw diagnostics, control R7 | `../bench/diagnostics/ada-t01gateoff/20260912T1603Z-t04ctrl2/0.json` |",
    "| Raw diagnostics, control R7 | `diagnostics/ada-t01gateoff/20260912T1603Z-t04ctrl2/0.json` |")
sub("bench/CTRL_VS_T12_REPORT.md",
    "| Raw diagnostics, candidate R8 | `../bench/diagnostics/20260912T1603Z-t12cand2/0.json` |",
    "| Raw diagnostics, candidate R8 | `diagnostics/20260912T1603Z-t12cand2/0.json` |")

# ------------------------------------------------------ bench/FRESH_REM81_REPORT.md
sub("bench/FRESH_REM81_REPORT.md",
    "| 1 | `df0c537` — campaign-origin baseline | `targets/ada-baseline` |",
    "| 1 | `df0c537` — campaign-origin baseline | `ada-baseline` worktree (removed 2026-09-18; archived to `bench/diagnostics/ada-baseline/`) |")
sub("bench/FRESH_REM81_REPORT.md",
    "| 2 | `2e495bb` — T1.2 time-awareness bundle | `targets/ada` |",
    "| 2 | `2e495bb` — T1.2 time-awareness bundle | `ada` worktree (former mirror, removed 2026-09-18; archived to `bench/diagnostics/`) |")
sub("bench/FRESH_REM81_REPORT.md",
    "This upgrades `fina_run.md` **E11** from",
    "This upgrades the campaign roadmap's **E11** estimate (`fina_run.md`, working doc\nremoved during final packaging 2026-09-18) from")
sub("bench/FRESH_REM81_REPORT.md",
    "`fina_run.md` §6 already recorded this run as anomalous",
    "The campaign roadmap (`fina_run.md` §6, removed 2026-09-18) already recorded this run as anomalous")
sub("bench/FRESH_REM81_REPORT.md",
    "| Stored comparators | `…/diagnostics/20260911T1540Z-t12rem81/rem81_t12_candidate.json`, `…/diagnostics/20260910T0728Z-t04ctrl/0.json` |",
    "| Stored comparators | `bench/diagnostics/20260911T1540Z-t12rem81/rem81_t12_candidate.json`, `bench/diagnostics/20260910T0728Z-t04ctrl/0.json` |")

# ----------------------------------------------------------- bench/RUN_REGISTRY.md
sub("bench/RUN_REGISTRY.md",
    "| **`df0c537`** (committed as `417a8f1`) | campaign origin — no watchdog, no deadline anchor. `417a8f1` only commits the runner shim `systemPromptGuidance` that was uncommitted in this workspace since 2026-09-08 and present in R1 and R5. A task that overruns is **hard-killed** by the harness. | `targets/ada-baseline` |",
    "| **`df0c537`** (committed as `417a8f1` ⁴) | campaign origin — no watchdog, no deadline anchor. `417a8f1` only commits the runner shim `systemPromptGuidance` that was uncommitted in this workspace since 2026-09-08 and present in R1 and R5. A task that overruns is **hard-killed** by the harness. | archived: `bench/diagnostics/ada-baseline/` |")
sub("bench/RUN_REGISTRY.md",
    "| **`6672af8`** | **+ T0.1**: watchdog interrupt, container-anchored deadline, clean exit. Overruns become graded partial work instead of kills. | `targets/ada-t01gateoff` |",
    "| **`6672af8`** | **+ T0.1**: watchdog interrupt, container-anchored deadline, clean exit. Overruns become graded partial work instead of kills. | archived: `bench/diagnostics/ada-t01gateoff/` |")
sub("bench/RUN_REGISTRY.md",
    "| **`2e495bb`** | **+ T1.2**: time hints before every model request, wrap-up instruction, Bash timeout clamp. | `targets/ada` |",
    "| **`2e495bb`** | **+ T1.2**: time hints before every model request, wrap-up instruction, Bash timeout clamp. | archived: `bench/diagnostics/` |")
sub("bench/RUN_REGISTRY.md",
    "| **`5f4c5c0`** (measured as `1d82e56`) | **the shipped build**: `2e495bb` with both T1.2 gates flipped **default off**, so no hooks are registered and behaviour is `6672af8`'s. `1d82e56` is the same agent tree with later docs commits on top (`agent_tree` `dab704de524a` in both). | `targets/ada` |",
    "| **`5f4c5c0`** (measured as `1d82e56`) | **the shipped build**: `2e495bb` with both T1.2 gates flipped **default off**, so no hooks are registered and behaviour is `6672af8`'s. `1d82e56` is the same agent tree with later docs commits on top (`agent_tree` `dab704de524a` in both). | archived: `bench/diagnostics/` |")
sub("bench/RUN_REGISTRY.md",
    "`2e495bb` is `6672af8` plus T1.2 and nothing else,",
    "The build workspaces formerly under the autoresearcher tree were removed during final\n"
    "packaging (2026-09-18); their run diagnostics are archived under `bench/diagnostics/`\n"
    "and the builds themselves are pinned by commit in `ada/` (see `ada/RESULTS.md`\n"
    "§Versions).\n\n"
    "`2e495bb` is `6672af8` plus T1.2 and nothing else,")

# ------------------------------------------------- bench/t12_apply_edits.py etc.
sub("bench/t12_apply_edits.py",
    'PATH = "/home/azureuser/adaAgent/autoresearcher/targets/ada/agent/claude/agent.ts"',
    '# Historical one-shot edit script (T1.2 wiring, now committed at 2e495bb in ada/).\n'
    '# Path repointed to the canonical repo during final packaging 2026-09-18.\n'
    'PATH = "/home/azureuser/adaAgent/ada/agent/claude/agent.ts"')
sub("bench/t12_append_tests.py",
    'PATH = "/home/azureuser/adaAgent/autoresearcher/targets/ada/agent/claude/agent.test.ts"',
    '# Historical one-shot edit script (T1.2 tests, now committed at 2e495bb in ada/).\n'
    '# Path repointed to the canonical repo during final packaging 2026-09-18.\n'
    'PATH = "/home/azureuser/adaAgent/ada/agent/claude/agent.test.ts"')

# ------------------------------------------------ bench/run_bvb_rep2_parallel.sh
sub("bench/run_bvb_rep2_parallel.sh",
    "# Usage: run_bvb_rep2_parallel.sh <rep1 baseline eval pid> <rep1 best eval pid>",
    "# Usage: run_bvb_rep2_parallel.sh <rep1 baseline eval pid> <rep1 best eval pid>\n"
    "#\n"
    "# HISTORICAL RECORD (2026-09-18): this driver was executed 2026-09-15 from the\n"
    "# former autoresearcher tree, which was removed during final packaging. It is kept\n"
    "# as the as-run record of how R9/R10 replicate 2 was launched and is not\n"
    "# re-runnable as-is; the relocated harness lives in bench/harness/ (see\n"
    "# bench/REPLICATION.md). Paths below are repointed to the archived layout.")
sub("bench/run_bvb_rep2_parallel.sh",
    "ROOT=/home/azureuser/adaAgent; B=$ROOT/bench; T=$ROOT/autoresearcher/targets",
    "ROOT=/home/azureuser/adaAgent; B=$ROOT/bench; T=$ROOT/bench/diagnostics")
sub("bench/run_bvb_rep2_parallel.sh",
    'cd "$ROOT/autoresearcher"',
    'cd "$ROOT/bench/harness"  # relocated harness home (was the former autoresearcher tree)')
sub("bench/run_bvb_rep2_parallel.sh",
    '      .venv/bin/python examples/setupbench_ada_domain_eval.py remaining81 --workspace "targets/$1" --concurrency 1 \\',
    '      python3 setupbench_ada_domain_eval.py remaining81 --workspace "$ROOT/ada" --concurrency 1 \\')
sub("bench/run_bvb_rep2_parallel.sh",
    "# The analysis reads replicate diagnostics from the original workspaces.\n"
    "for spec in \"ada-baseline-r2 ada-baseline base\" \"ada-r2 ada best\"; do set -- $spec\n"
    "  src=\"$T/$1/.autoresearch/diagnostics/${TS}-r2-$3/0.json\"; dst=\"$T/$2/.autoresearch/diagnostics/${TS}-r2-$3\"\n"
    "  [ -f \"$src\" ] && mkdir -p \"$dst\" && cp \"$src\" \"$dst/0.json\" || echo \"MISSING $src\"\n"
    "done",
    "# The analysis reads replicate diagnostics from the archived layout.\n"
    "# (Post-packaging note 2026-09-18: replicate-2 diagnostics are archived at\n"
    "#  bench/diagnostics/ada-baseline/20260915T0825Z-r2-base/ and\n"
    "#  bench/diagnostics/20260915T0825Z-r2-best/ — the former worktree copy step is\n"
    "#  obsolete and removed.)")

# ------------------------------------------------------------- ada/RESULTS.md
sub("ada/RESULTS.md",
    "(`ada/`, mirrored at `autoresearcher/targets/ada/`) running `z-ai/glm-5.3-flash` through",
    "(`ada/`, the canonical repository) running `z-ai/glm-5.3-flash` through")
sub("ada/RESULTS.md",
    "> Every number below traces to an artifact on disk. The narrative companion to this file is\n"
    "> [`REPORT.md`](REPORT.md). The working roadmap with the full evidence table lives at\n"
    "> the campaign root, one level above this tree (`../fina_run.md`).",
    "> Every number below traces to an artifact on disk. The narrative companion to this file is\n"
    "> [`REPORT.md`](REPORT.md). The working roadmap (`fina_run.md`) that governed the campaign\n"
    "> was removed during final packaging (2026-09-18); its rules and verdicts are recorded in\n"
    "> this file, [`REPORT.md`](REPORT.md), and `../bench/RUN_REGISTRY.md`.")
sub("ada/RESULTS.md",
    "tag `ada-best-61pct-20260916`\n"
    "(`autoresearcher/targets/ada` @ `c6f917e`, agent tree `dab704de524a`, clean). Doubling the",
    "tag `ada-best-61pct-20260916`\n"
    "(this repository @ `32f4754`, agent tree `dab704de524a`, clean; the byte-identical former\n"
    "mirror — historical pin `c6f917e` — was removed 2026-09-18). Doubling the")
sub("ada/RESULTS.md",
    "Both trees (`ada/` and `autoresearcher/targets/ada/`) are byte-identical mirrors; commits\n"
    "listed as `targets/ada / ada`.",
    "Historically the build lived in two byte-identical trees; the mirror was removed on\n"
    "2026-09-18 and this repository (`ada/`) is canonical. Commits below are listed as\n"
    "`ada / former-mirror`.")
sub("ada/RESULTS.md",
    "Protocol (`../fina_run.md` §3): paired arms, identical conditions",
    "Protocol (campaign spec §3, `fina_run.md` — removed 2026-09-18): paired arms, identical conditions")
sub("ada/RESULTS.md",
    "  or any other. `../bench/final_verify_final81.py` covers the Phase A archive.",
    "  or any other. `../bench/harness/archive_integrity_check.py` covers the archived runs\n"
    "  (it supersedes the former `final_verify_final81.py`, removed during packaging).")
sub("ada/RESULTS.md",
    "- [x] `../bench/ctrl_vs_t12_verify.py` and `../bench/final_verify_final81.py` both green.",
    "- [x] `../bench/ctrl_vs_t12_verify.py` and `../bench/harness/archive_integrity_check.py` both green.")
sub("ada/RESULTS.md",
    "| Working roadmap + full evidence table + verdicts | `../fina_run.md` |",
    "| Working roadmap (removed 2026-09-18; rules recorded in `../bench/RUN_REGISTRY.md` and this file) | — |")
sub("ada/RESULTS.md",
    "| Machine verification of the Phase A archive (exit 0) | `../bench/final_verify_final81.py` |",
    "| Machine verification of the archived runs (exit 0) | `../bench/harness/archive_integrity_check.py` |")
sub("ada/RESULTS.md",
    "| Superseded Phase A reports, each banner-marked | `../archive/` |",
    "| Superseded Phase A reports | removed during final packaging (2026-09-18); superseded by this file and `../bench/` reports |")

# ------------------------------------------- ada/RESULTS.md — Versions section
VERSIONS = """## Versions — the canonical lineage

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

"""
sub("ada/RESULTS.md",
    "## Baseline vs shipped build — head to head",
    VERSIONS + "## Baseline vs shipped build — head to head", expect=1)

# ------------------------------------------------- TB tarball regeneration notes
sub("bench/TB_REPORT.md",
    "The two variants differ in **exactly** those two files (verified with `diff -rq`); everything else (node_modules, runner script, model, tasks, timeout policy) is identical. Run results:",
    "The two variants differ in **exactly** those two files (verified with `diff -rq`); everything else (node_modules, runner script, model, tasks, timeout policy) is identical.\n\n"
    "> **Packaging note (2026-09-18):** the variant tarballs (`bench/ada-baseline.tgz`,\n"
    "> `bench/ada-best.tgz`) were removed during final packaging. Regenerate the baseline\n"
    "> from git with `git -C ada archive df0c537 | gzip > bench/ada-baseline.tgz`;\n"
    "> `ada-best.tgz` was a working-tree snapshot whose retained changes are in the shipped\n"
    "> tag `ada-best-61pct-20260916`. The TB result directories referenced below are kept.\n\n"
    "Run results:")
sub("bench/TB_REPORT_40.md",
    "**Budget-adaptive guidance under test:**",
    "> **Packaging note (2026-09-18):** the variant tarballs (`bench/ada-baseline.tgz`,\n"
    "> `bench/ada-best.tgz`, `bench/ada-best2.tgz`) were removed during final packaging.\n"
    "> Regenerate the baseline from git with `git -C ada archive df0c537 | gzip >\n"
    "> bench/ada-baseline.tgz`; the best/best2 snapshots' retained changes are in the\n"
    "> shipped tag `ada-best-61pct-20260916`. The TB result directories referenced below\n"
    "> are kept.\n\n"
    "**Budget-adaptive guidance under test:**")
sub("bench/task-selection-40.md",
    "- **Baseline (ada-baseline.tgz, df0c537):**",
    "- **Baseline (ada-baseline.tgz [removed 2026-09-18; regenerate via `git -C ada archive df0c537 | gzip > bench/ada-baseline.tgz`], df0c537):**")
sub("bench/task-selection-40.md",
    "- **Best2 (ada-best2.tgz):**",
    "- **Best2 (ada-best2.tgz [removed 2026-09-18; regenerate from the shipped tag]):**")
sub("bench/ada_agent.py",
    "``--ak ada_tarball=/path/to.tgz`` overrides the tarball directly.\n\"\"\"",
    "``--ak ada_tarball=/path/to.tgz`` overrides the tarball directly.\n\n"
    "Packaging note (2026-09-18): the default tarballs under bench/ were removed during\n"
    "final packaging. Regenerate with `git -C ada archive <commit> | gzip > bench/ada-<variant>.tgz`\n"
    "(baseline `df0c537`, shipped `5f4c5c0`) and pass ``--ak ada_tarball=...``, or point\n"
    "DEFAULT_TARBALLS at your own builds.\n"
    "\"\"\"")

# ------------------------------------------------------------------------ report
print(f"edits applied: {len(EDITED)}")
for e in EDITED:
    print(f"  OK {e}")
if FAILED:
    print(f"\nFAILURES: {len(FAILED)}")
    for f in FAILED:
        print(f"  FAIL {f}")
    sys.exit(1)
print("ALL RESIDUE EDITS APPLIED CLEANLY")
