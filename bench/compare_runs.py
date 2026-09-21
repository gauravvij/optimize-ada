#!/usr/bin/env python3
"""Model-versus-code table across two runs of the same two builds (plain Python, no dependencies).

  python3 bench/compare_runs.py <EARLIER_RUN_DIR> <NEW_RUN_DIR>
  e.g. python3 bench/compare_runs.py ada/runs/deepseek-v4-flash/r1 ada/runs/deepseek-v4.1-flash/r1

Both directories must already hold summary.json (run `python3 bench/deepseek_summary.py <dir>` first). Only tasks present in
BOTH runs are compared, so a 40-task run is compared with the same 40 tasks of an 81-task run. Writes
comparison_vs_<earlier>.md and .json into the NEW run's directory. One attempt per task per cell: descriptive only.
"""
import json, math, sys
from pathlib import Path

A_DIR, B_DIR = Path(sys.argv[1]), Path(sys.argv[2])
A, B = json.load(open(A_DIR / "summary.json")), json.load(open(B_DIR / "summary.json"))
mA, mB = A["baseline"]["protocol"]["model"], B["baseline"]["protocol"]["model"]
tasks = sorted(set(A["baseline"]["tasks"]) & set(B["baseline"]["tasks"]) & set(A["best"]["tasks"]) & set(B["best"]["tasks"]))
cells = {(m, arm): src[arm]["tasks"] for m, src in ((mA, A), (mB, B)) for arm in ("baseline", "best")}


def mcnemar(g, l):
    n = g + l
    return 1.0 if n == 0 else min(1.0, 2 * sum(math.comb(n, k) for k in range(min(g, l) + 1)) / 2 ** n)


def pair(x, y):
    """y against x on tasks valid in both: gained = only y passed, lost = only x passed."""
    ok = [t for t in tasks if x[t]["valid"] and y[t]["valid"]]
    g = sum(1 for t in ok if y[t]["passed"] and not x[t]["passed"]); l = sum(1 for t in ok if x[t]["passed"] and not y[t]["passed"])
    return {"pairs": len(ok), "x_passed": sum(x[t]["passed"] for t in ok), "y_passed": sum(y[t]["passed"] for t in ok), "gained": g, "lost": l, "p": round(mcnemar(g, l), 4)}


def cell(d):
    v = [d[t] for t in tasks]
    return {"attempts": len(v), "passed": sum(x["passed"] for x in v), "timed_out": sum(x["timed_out"] for x in v),
            "interrupted": sum(x["watchdog_stopped"] for x in v), "turns_mean": round(sum(x["turns"] for x in v) / len(v), 1),
            "cost_usd": round(sum(x["cost_usd"] for x in v), 4)}


out = {"tasks": len(tasks), "models": [mA, mB], "cells": {f"{m} / {arm}": cell(d) for (m, arm), d in cells.items()}, "paired": {}}
for m in (mA, mB):
    out["paired"][f"{m}: best vs baseline"] = pair(cells[(m, "baseline")], cells[(m, "best")])
for arm in ("baseline", "best"):
    out["paired"][f"{arm}: {mB} vs {mA}"] = pair(cells[(mA, arm)], cells[(mB, arm)])

L = [f"# {mB} against {mA}: the same two builds on the same {len(tasks)} tasks", "",
     "One attempt per task per cell, so this is descriptive. It separates 'the model' (compare the two models with the same build) "
     "from 'the code' (compare the two builds with the same model).", "",
     "| Model / build | Attempts | Passed | Timed out | Interrupted by watchdog | Turns (mean) | Cost $ |", "|---|---:|---:|---:|---:|---:|---:|"]
for k, c in out["cells"].items():
    L.append(f"| {k} | {c['attempts']} | {c['passed']} | {c['timed_out']} | {c['interrupted']} | {c['turns_mean']} | {c['cost_usd']} |")
L += ["", "## Paired comparisons (gained = only the second passed, lost = only the first passed)", "",
      "| Comparison | Pairs | First passed | Second passed | Gained | Lost | exact McNemar p |", "|---|---:|---:|---:|---:|---:|---:|"]
for k, p in out["paired"].items():
    L.append(f"| {k} | {p['pairs']} | {p['x_passed']} | {p['y_passed']} | {p['gained']} | {p['lost']} | {p['p']} |")
gain_a = out["paired"][f"{mA}: best vs baseline"]; gain_b = out["paired"][f"{mB}: best vs baseline"]
L += ["", f"Effect of the best build's changes (best minus baseline passes): {gain_a['y_passed'] - gain_a['x_passed']:+d} on {mA}, "
      f"{gain_b['y_passed'] - gain_b['x_passed']:+d} on {mB}."]
md = "\n".join(L) + "\n"
tag = A_DIR.parent.name + "_" + A_DIR.name
(B_DIR / f"comparison_vs_{tag}.md").write_text(md); (B_DIR / f"comparison_vs_{tag}.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
print(md)
