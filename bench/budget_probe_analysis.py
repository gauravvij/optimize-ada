#!/usr/bin/env python3
"""Mechanical application of the pre-registered budget-probe decision rule.

Reads the budget probe diagnostics (final 0.json if present, else the
incremental 0.partial.jsonl sidecar) and applies the rule exactly as
pre-registered BEFORE the spend (campaign plan of 2026-09-16, since removed
    during final packaging; the rule is recorded in bench/PHASE_C_SUMMARY.md
    and bench/RUN_REGISTRY.md):

    >= 12 / 25 pass  -> SLOW  (proceed to P3, then P2; consider P4 smoke)
    4-11 / 25 pass   -> MIXED (efficiency work only for the converted subset)
    <= 3 / 25 pass   -> HARD  (stop buying time; record the finding)

Usage:
    python3 budget_probe_analysis.py <probe_diagnostics_dir_or_json> [--out REPORT.md]

The script tolerates partial (in-progress) diagnostics: it reads whatever
rows exist and reports completion status, but the verdict is only final
when all 25 expected tasks have rows.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

EXPECTED_TASKS = 25
RULE = "pre-registered: >=12 pass = SLOW; 4-11 = MIXED; <=3 = HARD"


def load_rows(source: Path) -> tuple[list[dict], bool]:
    """Return (rows, complete). Prefers the final diagnostic JSON; falls back
    to the incremental .partial.jsonl sidecar for in-progress runs."""
    if source.is_dir():
        final = source / "0.json"
        partial = source / "0.partial.jsonl"
    else:
        final = source
        partial = source.with_name("0.partial.jsonl")

    if final.is_file():
        report = json.loads(final.read_text())
        return report["results"], True

    if partial.is_file():
        rows = []
        for line in partial.read_text().splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
        return rows, False

    raise SystemExit(f"no diagnostics found at {source} (looked for {final} and {partial})")


def verdict_for(passed: int) -> str:
    if passed >= 12:
        return "SLOW"
    if passed >= 4:
        return "MIXED"
    return "HARD"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path,
                        help="probe diagnostics dir (containing 0.json / 0.partial.jsonl) or the 0.json itself")
    parser.add_argument("--out", type=Path, default=None, help="optional markdown report path")
    args = parser.parse_args()

    rows, complete = load_rows(args.source)
    n = len(rows)
    passed = sum(1 for r in rows if r.get("passed"))
    valid = sum(1 for r in rows if r.get("valid"))
    timed_out = sum(1 for r in rows if r.get("timed_out"))
    verdict = verdict_for(passed)

    print(f"rule: {RULE}")
    print(f"rows: {n}/{EXPECTED_TASKS} {'(COMPLETE)' if complete else '(PARTIAL — verdict not final)'}")
    print(f"passed: {passed}  valid: {valid}  timed_out: {timed_out}")
    print()
    print(f"| {'task_id':<45} | pass | valid | timeout | turns | duration_s |")
    print(f"|{'-' * 47}|------|-------|---------|-------|------------|")
    for r in sorted(rows, key=lambda r: r.get("task_id") or ""):
        print(f"| {str(r.get('task_id')):<45} | {int(bool(r.get('passed')))}    |"
              f" {int(bool(r.get('valid')))}     |"
              f" {int(bool(r.get('timed_out')))}       |"
              f" {str(r.get('turns')):>5} |"
              f" {str(r.get('duration_seconds')):>10} |")
    print()
    print(f"VERDICT: {verdict} (passed={passed}/{n}{' of expected ' + str(EXPECTED_TASKS) if not complete else ''})")

    if args.out:
        lines = [
            "# Budget Probe Report",
            "",
            f"- Rule ({RULE})",
            f"- Source: `{args.source}`",
            f"- Status: {'complete' if complete else 'PARTIAL'} ({n}/{EXPECTED_TASKS} rows)",
            f"- Passed: **{passed}** / {n} rows (valid={valid}, timed_out={timed_out})",
            "",
            f"## VERDICT: {verdict}" + ("" if complete else " (provisional — run incomplete)"),
            "",
            "| task_id | pass | valid | timeout | turns | duration_s |",
            "|---|---|---|---|---|---|",
        ]
        for r in sorted(rows, key=lambda r: r.get("task_id") or ""):
            lines.append(
                f"| {r.get('task_id')} | {int(bool(r.get('passed')))} | {int(bool(r.get('valid')))} |"
                f" {int(bool(r.get('timed_out')))} | {r.get('turns')} | {r.get('duration_seconds')} |"
            )
        args.out.write_text("\n".join(lines) + "\n")
        print(f"wrote {args.out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
