#!/usr/bin/env python3
"""Origin vs shipped build, head to head: the confirmation run (R9 + R10) from raw rows.

Reads the four per-task diagnostics of run 20260915T0825Z and prints the results table
in the README and blog. Definitions, as the README states them:

  attempt       one build on one task in one replicate (81 tasks x 2 replicates = 162)
  timed out     `timed_out`: the harness stopped Ada at the budget; the grader never ran
  watchdog stop `agent_is_error`: Ada's watchdog interrupted it before the budget; graded
  harness error `valid` is false: the attempt has no result and is left out of the pairs
  pair          both builds' attempts at one task in one replicate, neither a harness error

Standard library only:  python3 bench/confirmation_table.py
"""
import json
from math import comb
from pathlib import Path

D = Path(__file__).resolve().parent / "diagnostics"
RUNS = {
    "base": [D / "ada-baseline/20260915T0825Z-r1-base/0.json", D / "ada-baseline/20260915T0825Z-r2-base/0.json"],
    "best": [D / "20260915T0825Z-r1-best/0.json", D / "20260915T0825Z-r2-best/0.json"],
}
arm = {k: [{r["task_id"]: r for r in json.loads(p.read_text())["results"]} for p in v] for k, v in RUNS.items()}
flat = {k: [r for rep in v for r in rep.values()] for k, v in arm.items()}


def mcnemar(b, c):
    n = b + c
    return min(1.0, 2 * sum(comb(n, k) for k in range(min(b, c) + 1)) / 2 ** n) if n else 1.0


pairs = [(a[t], b[t]) for a, b in zip(arm["base"], arm["best"])
         for t in a if t in b and a[t].get("valid", True) and b[t].get("valid", True)]
gained = sum(not x["passed"] and y["passed"] for x, y in pairs)
lost = sum(x["passed"] and not y["passed"] for x, y in pairs)


def count(k, f):
    return sum(bool(f(r)) for r in flat[k])


n = len(flat["base"])
passed = {k: count(k, lambda r: r["passed"]) for k in arm}
timed_out = {k: count(k, lambda r: r["timed_out"]) for k in arm}
stopped = {k: count(k, lambda r: r["agent_is_error"] and r["grader_returncode"] is not None) for k in arm}
stopped_passed = count("best", lambda r: r["agent_is_error"] and r["passed"])
errors = {k: count(k, lambda r: not r.get("valid", True)) for k in arm}
pct = lambda x: f"{100 * x / n:.1f}%"

print("| Measure | Origin `df0c537` | Shipped `5f4c5c0` | Difference |")
print("|---|---:|---:|---|")
print(f"| Attempts passed, out of all {n} | {passed['base']} ({pct(passed['base'])}) | **{passed['best']} ({pct(passed['best'])})** "
      f"| +{passed['best'] - passed['base']} |")
print(f"| Pairs passed, out of {len(pairs)} pairs | {sum(x['passed'] for x, _ in pairs)} | **{sum(y['passed'] for _, y in pairs)}** "
      f"| {gained} gained, {lost} lost; exact McNemar p = {mcnemar(gained, lost):.2e} |")
print(f"| Timed out, so never graded | {timed_out['base']} | **{timed_out['best']}** | −{timed_out['base'] - timed_out['best']} |")
print(f"| Stopped by the watchdog, then graded | {stopped['base']} | {stopped['best']} | {stopped_passed} of the {stopped['best']} passed |")
print(f"| Harness errors, left out of the pairs | {errors['base']} | {errors['best']} | |")
