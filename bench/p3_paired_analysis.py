#!/usr/bin/env python3
"""P3 candidate paired gate analysis: shipped best vs P3 (late wrap-up).

Usage: python3 bench/p3_paired_analysis.py <TS> <REPS>

Reads each replicate's two diagnostics files (shipped arm from bench/diagnostics — archived from the former targets/ada —
P3 arm from bench/p3_evidence — archived from targets/ada-p3), excludes a task from a replicate when it is
invalid in either arm, and applies the rule pre-registered in
run_p3_paired.sh BEFORE any spend:

    keep P3 only if:
      1. every replicate completed with both diagnostics files
      2. pooled net (p3 - shipped) >= +5 tasks over the paired pool
      3. no replicate has a negative net

Writes bench/P3_PAIRED_<TS>.json.
"""
from __future__ import annotations

import json, math, sys
from pathlib import Path

ROOT = Path("/home/azureuser/adaAgent")
DIAG = ROOT / "bench/diagnostics"  # shipped arms, archived 2026-09-18
P3E = ROOT / "bench/p3_evidence"    # P3-candidate arms, archived 2026-09-18


def load(p: Path) -> dict:
    d = json.loads(p.read_text())
    return {r["task_id"]: r for r in d["results"]}, d


def mcnemar(b: int, c: int) -> float:
    n = b + c
    return 1.0 if n == 0 else min(1.0, 2 * sum(math.comb(n, k) for k in range(min(b, c) + 1)) / 2 ** n)


def contrast(pairs: list[tuple[dict, dict]]) -> dict:
    b = sum(1 for x, y in pairs if x["passed"] and not y["passed"])
    c = sum(1 for x, y in pairs if not x["passed"] and y["passed"])
    return {"n": len(pairs), "shipped_pass": sum(x["passed"] for x, _ in pairs),
            "p3_pass": sum(y["passed"] for _, y in pairs), "net": c - b,
            "lost": b, "gained": c, "p": float(f"{mcnemar(b, c):.4g}")}


def main() -> int:
    ts, reps = sys.argv[1], int(sys.argv[2])
    out, pooled = {"run": ts, "replicates": []}, []
    for r in range(1, reps + 1):
        sp = DIAG / f"{ts}-r{r}-shipped/0.json"
        pp = P3E / f"{ts}-r{r}-p3/0.json"
        if not (sp.exists() and pp.exists()):
            out["replicates"].append({"rep": r, "status": "MISSING diagnostics", "paths": [str(sp), str(pp)]})
            continue
        (S, sd), (P, pd) = load(sp), load(pp)
        tasks = [t for t in sorted(set(S) & set(P)) if S[t]["valid"] and P[t]["valid"]]
        pairs = [(S[t], P[t]) for t in tasks]
        pooled += pairs
        out["replicates"].append({
            "rep": r, "status": "COMPLETE",
            "agent_tree": {"shipped": sd.get("agent_tree"), "p3": pd.get("agent_tree")},
            "invalid": {"shipped": sum(not x["valid"] for x in S.values()),
                        "p3": sum(not x["valid"] for x in P.values())},
            "timeouts": {"shipped": sd["summary"]["timeouts"], "p3": pd["summary"]["timeouts"]},
            "contrast": contrast(pairs)})
    done = [x for x in out["replicates"] if x["status"] == "COMPLETE"]
    out["pooled"] = {"contrast": contrast(pooled)}
    # Pre-registered in run_p3_paired.sh before any spend:
    rule = {
        "all_replicates_complete": len(done) == reps,
        "pooled_net_ge_5": out["pooled"]["contrast"]["net"] >= 5,
        "no_negative_replicate": all(x["contrast"]["net"] >= 0 for x in done) and len(done) == reps,
    }
    out["rule"] = rule
    out["verdict"] = "KEEP" if all(rule.values()) else "REVERT"
    dest = ROOT / f"bench/P3_PAIRED_{ts}.json"
    dest.write_text(json.dumps(out, indent=2) + "\n")
    for x in out["replicates"]:
        if x["status"] != "COMPLETE":
            print(f"rep {x['rep']}: {x['status']}"); continue
        c = x["contrast"]
        print(f"rep {x['rep']}: shipped {c['shipped_pass']}/{c['n']} -> p3 {c['p3_pass']}/{c['n']}  "
              f"net {c['net']:+d} ({c['gained']} gained / {c['lost']} lost) p={c['p']}  invalid={x['invalid']}")
    c = out["pooled"]["contrast"]
    print(f"POOLED: shipped {c['shipped_pass']}/{c['n']} -> p3 {c['p3_pass']}/{c['n']}  net {c['net']:+d}  p={c['p']}")
    print(f"rule: {rule}\nVERDICT: {out['verdict']}\nwrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
