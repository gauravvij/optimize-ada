#!/usr/bin/env python3
"""Baseline vs shipped, head to head: the confirmation run (R9 + R10) from raw rows.

Reads the four per-task diagnostics of run 20260915T0825Z and prints every row of the
comparison table in the README and blog. Paired figures come from the pairing rule in
baseline_vs_best_analysis.py: a task counts only when both arms returned a valid row.
Standard library only:  python3 bench/confirmation_table.py
"""
import json
from math import comb
from pathlib import Path
from statistics import mean, median

D = Path(__file__).resolve().parent / "diagnostics"
RUNS = {
    "base": [D / "ada-baseline/20260915T0825Z-r1-base/0.json", D / "ada-baseline/20260915T0825Z-r2-base/0.json"],
    "best": [D / "20260915T0825Z-r1-best/0.json", D / "20260915T0825Z-r2-best/0.json"],
}


def rows(path):
    return json.loads(path.read_text())["results"]


def mcnemar(b, c):
    n = b + c
    return min(1.0, 2 * sum(comb(n, k) for k in range(min(b, c) + 1)) / 2 ** n) if n else 1.0


def paired(base_rows, best_rows):
    a = {r["task_id"]: r for r in base_rows if r.get("valid", True)}
    b = {r["task_id"]: r for r in best_rows if r.get("valid", True)}
    ids = sorted(a.keys() & b.keys())
    gained = sum(not a[t]["passed"] and b[t]["passed"] for t in ids)
    lost = sum(a[t]["passed"] and not b[t]["passed"] for t in ids)
    return len(ids), sum(a[t]["passed"] for t in ids), sum(b[t]["passed"] for t in ids), gained, lost


arm = {k: [rows(p) for p in v] for k, v in RUNS.items()}
flat = {k: [r for rep in v for r in rep] for k, v in arm.items()}


def stats(k):
    r = flat[k]
    dur = [x["duration_seconds"] for x in r]
    passed_dur = [x["duration_seconds"] for x in r if x["passed"]]
    return {
        "n": len(r),
        "passed": sum(x["passed"] for x in r),
        "per_rep": [sum(x["passed"] for x in rep) for rep in arm[k]],
        "zero_turn": sum((x["turns"] or 0) == 0 for x in r),
        "timed_out": sum(bool(x["timed_out"]) for x in r),
        "interrupted_graded": sum(x.get("agent_stop_reason") == "tool_use" and not x["timed_out"]
                                  and x.get("grader_returncode") is not None for x in r),
        "turns": sum(x["turns"] or 0 for x in r),
        "turns_median": median(x["turns"] or 0 for x in r),
        "lat_mean": mean(dur), "lat_median": median(dur),
        "pass_lat_mean": mean(passed_dur), "pass_lat_median": median(passed_dur),
        "wall_h": sum(dur) / 3600,
        "invalid": sum(not x.get("valid", True) for x in r),
    }


b, s = stats("base"), stats("best")
reps = [paired(arm["base"][i], arm["best"][i]) for i in range(2)]
pool = [sum(x[j] for x in reps) for j in range(5)]
pct = lambda x, n: f"{100 * x / n:.1f}%"


def out(line):
    print(line.replace("| -", "| \u2212"))  # typographic minus in table cells

rel = lambda x, y: f"{100 * (y - x) / x:+.0f}%"

out("| Metric | Baseline `df0c537` | Shipped `5f4c5c0` | Change |")
out("|---|---:|---:|---|")
out(f"| Tasks passed ({b['n']} runs) | {b['passed']} ({pct(b['passed'], b['n'])}) | **{s['passed']} ({pct(s['passed'], s['n'])})** "
      f"| +{s['passed'] - b['passed']} tasks, +{100 * (s['passed'] - b['passed']) / b['n']:.1f} pts, {rel(b['passed'], s['passed'])} relative |")
out(f"| Paired result, evaluable runs | {pool[1]}/{pool[0]} | **{pool[2]}/{pool[0]}** "
      f"| net +{pool[3] - pool[4]}, {pool[3]} gained / {pool[4]} lost, exact McNemar p = {mcnemar(pool[3], pool[4]):.2e} |")
out(f"| Per replicate (R9, R10) | {b['per_rep'][0]}/81, {b['per_rep'][1]}/81 | {s['per_rep'][0]}/81, {s['per_rep'][1]}/81 "
      f"| paired +{reps[0][3] - reps[0][4]} (p = {mcnemar(reps[0][3], reps[0][4]):.2e}), +{reps[1][3] - reps[1][4]} (p = {mcnemar(reps[1][3], reps[1][4]):.2e}) |")
out(f"| **Timed out**: killed by the harness, never graded | {b['timed_out']} | **{s['timed_out']}** | {s['timed_out'] - b['timed_out']}: this is the mechanism |")
out(f"| Runs recorded with zero turns | {b['zero_turn']} | {s['zero_turn']} | {s['zero_turn'] - b['zero_turn']} (mostly the timeouts above) |")
out(f"| Interrupted by the watchdog, then graded | {b['interrupted_graded']} | {s['interrupted_graded']} | the partial work now counts |")
out(f"| Turns, total | {b['turns']:,} | {s['turns']:,} | {rel(b['turns'], s['turns'])}: the agent actually gets to work |")
out(f"| Turns, median per task | {b['turns_median']:g} | {s['turns_median']:g} | the baseline's median run never took a turn |")
out(f"| Latency, mean per task | {b['lat_mean']:.0f} s | **{s['lat_mean']:.0f} s** | {rel(b['lat_mean'], s['lat_mean'])} |")
out(f"| Latency, median per task | {b['lat_median']:.0f} s | {s['lat_median']:.0f} s | {rel(b['lat_median'], s['lat_median'])} |")
out(f"| Latency on tasks that passed | {b['pass_lat_mean']:.0f} s mean / {b['pass_lat_median']:.0f} s median "
      f"| {s['pass_lat_mean']:.0f} s mean / {s['pass_lat_median']:.0f} s median | {rel(b['pass_lat_mean'], s['pass_lat_mean'])}: passing takes slightly longer |")
out(f"| Total wall time ({b['n']} runs) | {b['wall_h']:.1f} h | **{s['wall_h']:.1f} h** | {rel(b['wall_h'], s['wall_h'])} |")
out(f"| Invalid rows (excluded from pairing) | {b['invalid']} | {s['invalid']} | {s['invalid'] - b['invalid']} |")
out(f"| Tasks still failing | {b['n'] - b['passed']}/{b['n']} | {s['n'] - s['passed']}/{s['n']} | {(s['n'] - s['passed']) - (b['n'] - b['passed'])} |")
out("| Cost | not captured | not captured | the R9/R10 diagnostics record no tokens or spend |")
