#!/usr/bin/env python3
"""Original vs best optimized version: every attempt across both GLM rounds, from raw rows.

Reads the four per-task diagnostics of run 20260915T0825Z and prints the "every attempt"
table in the README and blog. Definitions, as the README states them:

  attempt        one build on one task in one replicate (81 tasks x 2 replicates = 162)
  timed out      `timed_out`: the harness stopped Ada at 480 s; the check never ran
  watchdog stop  `agent_is_error`: the watchdog stopped Ada at 450 s; the check then ran
  harness error  `valid` is false: the attempt has no result and is left out

Standard library only:  python3 bench/confirmation_table.py
"""
import json
from pathlib import Path

D = Path(__file__).resolve().parent / "diagnostics"
RUNS = {
    "base": [D / "ada-baseline/20260915T0825Z-r1-base/0.json", D / "ada-baseline/20260915T0825Z-r2-base/0.json"],
    "best": [D / "20260915T0825Z-r1-best/0.json", D / "20260915T0825Z-r2-best/0.json"],
}
arm = {k: [{r["task_id"]: r for r in json.loads(p.read_text())["results"]} for p in v] for k, v in RUNS.items()}
flat = {k: [r for rep in v for r in rep.values()] for k, v in arm.items()}


def count(k, f):
    return sum(bool(f(r)) for r in flat[k])


n = len(flat["base"])
passed = {k: count(k, lambda r: r["passed"]) for k in arm}
timed_out = {k: count(k, lambda r: r["timed_out"]) for k in arm}
stopped = {k: count(k, lambda r: r["agent_is_error"] and r["grader_returncode"] is not None) for k in arm}
stopped_passed = count("best", lambda r: r["agent_is_error"] and r["passed"])
errors = {k: count(k, lambda r: not r.get("valid", True)) for k in arm}
pct = lambda x: f"{100 * x / n:.1f}%"

print("| Every attempt across both rounds | Original version | Best optimized version |")
print("|---|---:|---:|")
print(f"| Passed, out of {n} | {passed['base']} ({pct(passed['base'])}) | **{passed['best']} ({pct(passed['best'])})** |")
print(f"| Timed out, so never checked | {timed_out['base']} | **{timed_out['best']}** |")
print(f"| Stopped by the watchdog, then checked | {stopped['base']} | {stopped['best']} ({stopped_passed} passed) |")
print(f"| Harness errors, excluded from matched pairs | {errors['base']} | {errors['best']} |")
