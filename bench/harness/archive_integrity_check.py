#!/usr/bin/env /usr/bin/python3
"""Integrity check for the archived raw run evidence in bench/diagnostics/.

For every archived run directory this script verifies, from the on-disk JSON
only:
  * every *.json diagnostic parses,
  * row counts and pass counts are internally consistent
    (summary.passed == count of results rows with passed=true),
  * the recorded agent_tree matches the build the run registry says it is.

Expected values are encoded from bench/RUN_REGISTRY.md (R1-R10, budget probe,
P3 runs). Exit code is non-zero if any check fails.

Usage: /usr/bin/python3 bench/harness/archive_integrity_check.py [--diagnostics DIR]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# agent trees, verified via `git -C ada rev-parse <commit>:agent`
TREE_BASELINE_DF0C537 = "6ec0446cfc7daca5bb9e8a60168e3ec5853a4cdf"
TREE_T01_6672AF8 = "7958654244eb60c04177006ff29299f791fbf3e7"
TREE_T12_2E495BB = "4267fee64dccb5958479eca433a44cf346b9720e"
TREE_SHIPPED_DAB704D = "dab704de524a7b31203f0b53374ec539cbb7089d"
TREE_P3_9F2E34D = "811a16e4a67e95ad5b8fe37dee8963e593457b65"

# run_id -> (registry label, expected passed, expected total rows, expected agent_tree)
# None = not asserted (partial/voided runs keep whatever rows they have).
EXPECTED = {
    # R3/R4 predate the agent_tree field; their workspace_commit pins the build.
    "20260910T0728Z-t04ctrl": ("R3 (withdrawn)", 24, 81, "commit:6672af854dd9be6d3290d3959c74b95808d54eec"),
    "20260911T1540Z-t12rem81": ("R4 (withdrawn)", 52, 81, "commit:2e495bb9817bf47ca2a082660ce58b0dfa4d7bbf"),
    "20260915T0825Z-r1-best": ("R9b (shipped r1)", 47, 81, TREE_SHIPPED_DAB704D),
    "20260915T0825Z-r2-best": ("R10b (shipped r2)", 52, 81, TREE_SHIPPED_DAB704D),
    "20260916T1340Z-r1-shipped": ("P3-void (shipped arm)", None, None, None),
    "20260917T0602Z-r1-shipped": ("P3-r1 shipped arm", None, None, TREE_SHIPPED_DAB704D),
    "20260917T0602Z-r2-shipped": ("P3-r2 shipped arm", None, None, TREE_SHIPPED_DAB704D),
    "budget-probe-20260916T0730Z": ("BP budget probe", 7, 25, TREE_SHIPPED_DAB704D),
    # Baseline-arm and T0.1-control runs, archived under the group dirs
    # ada-baseline/ and ada-t01gateoff/. Keys are paths relative to the
    # diagnostics root because the dev12/val12 run names also exist at top
    # level for the candidate arm. These runs predate the agent_tree field;
    # their workspace_commit pins the build (417a8f1 is the mirror-only
    # runner-shim commit on top of df0c537 — historical pin, the mirror was
    # removed 2026-09-18).
    "ada-baseline/20260912T1031Z-frem81base": ("R5 (baseline)", 34, 81, "commit:df0c537b7bcfadc385144e030bb169b5b31cda89"),
    "ada-baseline/20260915T0825Z-r1-base": ("R9a (baseline r1)", 32, 81, "commit:417a8f15ccd4291bcb7eb4d36ecefa63642bb012"),
    "ada-baseline/20260915T0825Z-r2-base": ("R10a (baseline r2)", 36, 81, "commit:417a8f15ccd4291bcb7eb4d36ecefa63642bb012"),
    "ada-baseline/20260912T0625Z-fdev12base": ("dev12 baseline arm", 7, 12, "commit:df0c537b7bcfadc385144e030bb169b5b31cda89"),
    "ada-t01gateoff/20260912T1603Z-t04ctrl2": ("R7 (T0.1 control)", 54, 81, "commit:6672af854dd9be6d3290d3959c74b95808d54eec"),
    "ada-t01gateoff/20260911T1045Z-t11dev12": ("dev12 T0.1 arm (t11)", 3, 12, "commit:6672af854dd9be6d3290d3959c74b95808d54eec"),
    "ada-t01gateoff/20260911T1348Z-t12dev12": ("dev12 T0.1 arm (t12)", 5, 12, "commit:6672af854dd9be6d3290d3959c74b95808d54eec"),
    "ada-t01gateoff/20260911T1442Z-t12val12": ("val12 T0.1 arm", 6, 12, "commit:6672af854dd9be6d3290d3959c74b95808d54eec"),
}

# per-file expectations for dirs that hold several heterogeneous JSONs
FILE_EXPECTED = {
    "ada-baseline/manual/remaining81_baseline.json": ("R1 (baseline origin)", 27, 81, "commit:df0c537b7bcfadc385144e030bb169b5b31cda89"),
}


def check_dir(run_dir, key=None):
    problems = []
    label, exp_pass, exp_rows, exp_tree = EXPECTED.get(key or run_dir.name, (None, None, None, None))
    jsons = sorted(run_dir.glob("*.json"))
    if not jsons:
        partials = sorted(run_dir.glob("*.partial.jsonl"))
        if partials:
            # voided run: killed mid-flight, only incremental partial rows remain
            for pf in partials:
                rows = [line for line in pf.read_text().splitlines() if line.strip()]
                print("  %s/%s: partial rows=%d (voided run, no final JSON)" % (run_dir.name, pf.name, len(rows)))
            return []
        return ["%s: no diagnostic JSON files" % run_dir.name]
    for jf in jsons:
        try:
            report = json.loads(jf.read_text())
        except json.JSONDecodeError as exc:
            problems.append("%s/%s: unparsable JSON: %s" % (run_dir.name, jf.name, exc))
            continue
        results = report.get("results", [])
        summary = report.get("summary", {})
        if "passed" in summary and summary["passed"] != sum(1 for r in results if r.get("passed")):
            problems.append("%s/%s: summary.passed=%s != row count %d" % (
                run_dir.name, jf.name, summary["passed"], sum(1 for r in results if r.get("passed"))))
        if "total" in summary and summary["total"] != len(results):
            problems.append("%s/%s: summary.total=%s != %d rows" % (
                run_dir.name, jf.name, summary["total"], len(results)))
        if exp_rows is not None and len(results) != exp_rows:
            problems.append("%s/%s: %d rows, expected %s" % (run_dir.name, jf.name, len(results), exp_rows))
        if exp_pass is not None and summary.get("passed") != exp_pass:
            problems.append("%s/%s: passed=%s, expected %s" % (
                run_dir.name, jf.name, summary.get("passed"), exp_pass))
        tree = report.get("agent_tree")
        if exp_tree is not None:
            if isinstance(exp_tree, str) and exp_tree.startswith("commit:"):
                actual = report.get("workspace_commit")
                kind = "workspace_commit"
                exp_tree = exp_tree[len("commit:"):]
            else:
                actual = tree
                kind = "agent_tree"
            if actual != exp_tree:
                problems.append("%s/%s: %s=%s, expected %s" % (run_dir.name, jf.name, kind, actual, exp_tree))
        print("  %s/%s: rows=%d passed=%s agent_tree=%s" % (
            run_dir.name, jf.name, len(results), summary.get("passed"), str(tree)[:12]))
    return problems


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--diagnostics",
                        default=str(Path(__file__).resolve().parents[1] / "diagnostics"))
    args = parser.parse_args()
    root = Path(args.diagnostics).resolve()
    if not root.is_dir():
        print("diagnostics dir not found: %s" % root)
        return 1
    all_problems = []
    for run_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        print("%s:" % run_dir.name)
        if run_dir.name in ("ada-baseline", "ada-t01gateoff"):
            # group dirs: one sub-directory per run, keyed "group/run" in EXPECTED
            for sub in sorted(p for p in run_dir.iterdir() if p.is_dir()):
                print("%s/%s:" % (run_dir.name, sub.name))
                all_problems.extend(check_dir(sub, "%s/%s" % (run_dir.name, sub.name)))
            continue
        all_problems.extend(check_dir(run_dir))
    p3 = root.parent / "p3_evidence"
    if p3.is_dir():
        print("p3_evidence:")
        for run_dir in sorted(p for p in p3.iterdir() if p.is_dir()):
            print("%s:" % run_dir.name)
            all_problems.extend(check_dir(run_dir))
    if all_problems:
        print("\nFAILURES:")
        for problem in all_problems:
            print("  - %s" % problem)
        return 1
    print("\nALL ARCHIVE INTEGRITY CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
