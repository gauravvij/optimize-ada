#!/usr/bin/env python3
"""Baseline vs best confirmation run: per-replicate and pooled paired contrasts.

Usage: python3 bench/baseline_vs_best_analysis.py <TS> <REPS>
Reads each replicate's two diagnostics files, excludes a task from a replicate when it
is invalid in either arm, and applies the rule pre-registered in run_baseline_vs_best.sh.
Writes bench/BASELINE_VS_BEST_<TS>.json.
"""
from __future__ import annotations

import json, math, sys
from pathlib import Path

ROOT = Path("/home/azureuser/adaAgent")
DIAG = ROOT / "bench/diagnostics"  # archived 2026-09-18 from the former autoresearcher workspaces


def load(p: Path) -> dict:
    d = json.loads(p.read_text())
    return {r["task_id"]: r for r in d["results"]}, d


def mcnemar(b: int, c: int) -> float:
    n = b + c
    return 1.0 if n == 0 else min(1.0, 2 * sum(math.comb(n, k) for k in range(min(b, c) + 1)) / 2 ** n)


def contrast(pairs: list[tuple[dict, dict]]) -> dict:
    b = sum(1 for x, y in pairs if x["passed"] and not y["passed"])
    c = sum(1 for x, y in pairs if not x["passed"] and y["passed"])
    return {"n": len(pairs), "baseline_pass": sum(x["passed"] for x, _ in pairs),
            "best_pass": sum(y["passed"] for _, y in pairs), "net": c - b,
            "lost": b, "gained": c, "p": float(f"{mcnemar(b, c):.4g}")}


def main() -> int:
    ts, reps = sys.argv[1], int(sys.argv[2])
    out, pooled, hung_pooled, ran_pooled = {"run": ts, "replicates": []}, [], [], []
    for r in range(1, reps + 1):
        bp = DIAG / f"ada-baseline/{ts}-r{r}-base/0.json"
        cp = DIAG / f"{ts}-r{r}-best/0.json"
        if not (bp.exists() and cp.exists()):
            out["replicates"].append({"rep": r, "status": "MISSING diagnostics", "paths": [str(bp), str(cp)]})
            continue
        (B, bd), (C, cd) = load(bp), load(cp)
        tasks = [t for t in sorted(set(B) & set(C)) if B[t]["valid"] and C[t]["valid"]]
        pairs = [(B[t], C[t]) for t in tasks]
        hung = [(B[t], C[t]) for t in tasks if B[t]["turns"] == 0]
        ran = [(B[t], C[t]) for t in tasks if B[t]["turns"] > 0]
        pooled += pairs; hung_pooled += hung; ran_pooled += ran
        out["replicates"].append({
            "rep": r, "status": "COMPLETE",
            "agent_tree": {"baseline": bd.get("agent_tree"), "best": cd.get("agent_tree")},
            "invalid": {"baseline": sum(not x["valid"] for x in B.values()),
                        "best": sum(not x["valid"] for x in C.values())},
            "timeouts": {"baseline": bd["summary"]["timeouts"], "best": cd["summary"]["timeouts"]},
            "zero_turn": {"baseline": sum(x["turns"] == 0 for x in B.values()),
                          "best": sum(x["turns"] == 0 for x in C.values())},
            "contrast": contrast(pairs), "baseline_hung": contrast(hung), "baseline_ran": contrast(ran)})
    done = [x for x in out["replicates"] if x["status"] == "COMPLETE"]
    out["pooled"] = {"contrast": contrast(pooled), "baseline_hung": contrast(hung_pooled),
                     "baseline_ran": contrast(ran_pooled)}
    # Pre-registered in run_baseline_vs_best.sh before any spend:
    rule = {
        "all_replicates_complete": len(done) == reps,
        "each_replicate_net_ge_10": all(x["contrast"]["net"] >= 10 for x in done) and len(done) == reps,
        "each_replicate_invalid_le_3": all(max(x["invalid"].values()) <= 3 for x in done),
        "pooled_p_lt_0.001": out["pooled"]["contrast"]["p"] < 0.001 and out["pooled"]["contrast"]["net"] > 0,
    }
    out["rule"] = rule
    out["verdict"] = "HOLDS" if all(rule.values()) else "DOES NOT HOLD"
    dest = ROOT / f"bench/BASELINE_VS_BEST_{ts}.json"
    dest.write_text(json.dumps(out, indent=2) + "\n")
    for x in out["replicates"]:
        if x["status"] != "COMPLETE":
            print(f"rep {x['rep']}: {x['status']}"); continue
        c = x["contrast"]
        print(f"rep {x['rep']}: baseline {c['baseline_pass']}/{c['n']} -> best {c['best_pass']}/{c['n']}  "
              f"net {c['net']:+d} ({c['gained']} gained / {c['lost']} lost) p={c['p']}  invalid={x['invalid']}")
    c = out["pooled"]["contrast"]
    print(f"POOLED: {c['baseline_pass']}/{c['n']} -> {c['best_pass']}/{c['n']}  net {c['net']:+d}  p={c['p']}")
    print(f"rule: {rule}\nVERDICT: {out['verdict']}\nwrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
