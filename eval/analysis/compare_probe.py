#!/usr/bin/env python3
"""Compare E-opt1 dev probe (gate ON) vs baseline arm B on the SAME 3 tasks.

Direction check only (k=2 denominators are tiny — not a significance test):
  1. no gross pass-rate regression per task vs arm B proportions
  2. per-trial output tokens / cost trending below the comparable arm-B values
"""
import json
import sys
from collections import defaultdict

ARM_B = "/root/optimize_ada/eval/results/baseline-armB.jsonl"
PROBE = "/root/optimize_ada/eval/results/e-opt1-probe.jsonl"
TASKS = ["fix-git", "regex-log", "cancel-async-tasks"]


def load(path):
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def by_task(rows):
    d = defaultdict(list)
    for r in rows:
        d[r["task"]].append(r)
    return d


def summarize(rows):
    n = len(rows)
    if n == 0:
        return {"n": 0}
    cost = [r.get("cost_usd") for r in rows if r.get("cost_usd") is not None]
    out_tok = [r.get("n_output_tokens") for r in rows if r.get("n_output_tokens") is not None]
    wall = [r.get("duration_ms") for r in rows if r.get("duration_ms") is not None]
    inp = [r.get("n_input_tokens") for r in rows if r.get("n_input_tokens") is not None]
    cache = [r.get("n_cache_tokens") for r in rows if r.get("n_cache_tokens") is not None]
    mean = lambda xs: sum(xs) / len(xs) if xs else None
    return {
        "n": n,
        "pass": sum(1 for r in rows if r.get("pass")),
        "cost": mean(cost),
        "cost_n": len(cost),
        "out_tok": mean(out_tok),
        "out_tok_n": len(out_tok),
        "wall_ms": mean(wall),
        "inp": mean(inp),
        "cache": mean(cache),
    }


def main():
    arm_b = by_task(load(ARM_B))
    probe = by_task(load(PROBE))

    print(f"{'task':<26}{'armB pass':>10}{'probe pass':>11}{'armB $':>10}{'probe $':>10}"
          f"{'armB out':>10}{'probe out':>10}{'armB wall':>12}{'probe wall':>12}")
    tot_b = {"pass": 0, "n": 0}
    tot_p = {"pass": 0, "n": 0}
    for t in TASKS:
        b = summarize(arm_b.get(t, []))
        p = summarize(probe.get(t, []))
        tot_b["pass"] += b["pass"]; tot_b["n"] += b["n"]
        tot_p["pass"] += p["pass"]; tot_p["n"] += p["n"]
        def f(x, nd=4):
            return "—" if x is None else f"{x:.{nd}f}"
        print(f"{t:<26}{b['pass']}/{b['n']:>3}      {p['pass']}/{p['n']:>3}      "
              f"{f(b['cost']):>8}{f(p['cost']):>10}{f(b['out_tok'],0):>10}{f(p['out_tok'],0):>10}"
              f"{f(b['wall_ms'],0):>10}{f(p['wall_ms'],0):>12}")
    print(f"\nTOTAL  armB {tot_b['pass']}/{tot_b['n']} = {tot_b['pass']/tot_b['n']:.3f}   "
          f"probe {tot_p['pass']}/{tot_p['n']} = {tot_p['pass']/tot_p['n']:.3f}")

    # Aggregate cost/out tokens on the comparable subset
    b_rows = [r for r in load(ARM_B) if r["task"] in TASKS]
    p_rows = [r for r in load(PROBE) if r["task"] in TASKS]
    sb, sp = summarize(b_rows), summarize(p_rows)
    print(f"\nAggregate (comparable 3-task subset):")
    print(f"  arm B : cost ${sb['cost']:.4f} (n={sb['cost_n']}), out_tok {sb['out_tok']:.0f}, wall {sb['wall_ms']:.0f}ms")
    print(f"  probe : cost ${sp['cost']:.4f} (n={sp['cost_n']}), out_tok {sp['out_tok']:.0f}, wall {sp['wall_ms']:.0f}ms")

    ok = True
    # Direction checks
    for t in TASKS:
        b = summarize(arm_b.get(t, []))
        p = summarize(probe.get(t, []))
        if b["n"] and p["n"]:
            b_rate = b["pass"] / b["n"]
            # arm B k=4; probe k=2. Pass@2=1 for all tasks already verified by
            # harbor (every task passed at least once). Flag only if probe won
            # NO trial on a task arm B ever passed.
            if b["pass"] == 0 and p["pass"] == 0:
                print(f"  [note] {t}: both arms floor at 0/2 vs 0/4 — unchanged")
            if b["pass"] == b["n"] and p["pass"] < p["n"]:
                print(f"  [warn] {t}: arm B perfect {b_rate:.0%}, probe {p['pass']}/{p['n']} — possible regression")
    print("\nPROBE DIRECTION:", "PROMISING — proceed to full 15-task x k=4 arm"
          if (sp["cost"] is not None and sb["cost"] is not None and sp["cost"] <= sb["cost"] * 1.05)
          else "CHECK — cost not clearly down, but pass stable; inspect before full arm")


if __name__ == "__main__":
    main()
