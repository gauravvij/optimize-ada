#!/usr/bin/env python3
"""Machine verification of the 2026-09-15 confirmation run (R9/R10).

Re-derives every figure from the four raw diagnostics files rather than trusting
BASELINE_VS_BEST_20260915T0825Z.json or the prose, recomputes exact McNemar
independently, re-applies the pre-registered rule, and asserts that the documents
quote the derived numbers. Exit 0 = all green.

    python3 bench/baseline_vs_best_verify.py
"""
from __future__ import annotations
import json, sys
from math import comb
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "bench/diagnostics").is_dir())  # repo root, wherever it is cloned
T = ROOT / "bench/diagnostics"  # archived 2026-09-18 from the former autoresearcher workspaces
TS = "20260915T0825Z"
PINS = {"baseline": "df8a18c092787af91ff143f711091e752b62c268",
        "best": "dab704de524a7b31203f0b53374ec539cbb7089d"}
fails: list[str] = []


def ck(label: str, cond: bool) -> None:
    print(("PASS  " if cond else "FAIL  ") + label)
    if not cond:
        fails.append(label)


def mcnemar(b: int, c: int) -> float:
    """Two-sided exact McNemar on the discordant pairs."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


def load(workspace: str, run: str) -> tuple[dict, dict]:
    # archived layout: ada runs at bench/diagnostics/<run>/, ada-baseline at
    # bench/diagnostics/ada-baseline/<run>/ (final packaging, 2026-09-18)
    sub = {"ada": "", "ada-baseline": "ada-baseline"}[workspace]
    doc = json.loads((T / sub / f"{TS}-{run}" / "0.json").read_text())
    return doc, {r["task_id"]: r for r in doc["results"]}


pooled_b = pooled_c = pooled_n = pooled_base = pooled_best = 0
reps: list[dict] = []
for rep, (brun, crun) in enumerate([("r1-base", "r1-best"), ("r2-base", "r2-best")], 1):
    bdoc, base = load("ada-baseline", brun)
    cdoc, best = load("ada", crun)
    ck(f"rep {rep}: both arms scored all 81 tasks", len(base) == len(best) == 81)
    ck(f"rep {rep}: same task set in both arms", set(base) == set(best))
    ck(f"rep {rep}: baseline arm is the pinned df0c537 tree", bdoc.get("agent_tree") == PINS["baseline"])
    ck(f"rep {rep}: best arm is the pinned shipped tree", cdoc.get("agent_tree") == PINS["best"])
    ck(f"rep {rep}: protocol unchanged (remaining81, 480 s task, 600 s grader, same model)",
       all(bdoc["protocol"][k] == cdoc["protocol"][k] == v for k, v in
           [("suite", "remaining81"), ("task_timeout_seconds", 480),
            ("grader_timeout_seconds", 600), ("model", "z-ai/glm-5.3-flash")]))
    ck(f"rep {rep}: both arms ran the same runner, grader and task selection",
       all(bdoc["protocol"][k] == cdoc["protocol"][k] for k in
           ("runner_sha256", "evaluator_sha256", "selection_seed", "setupbench_commit", "tasks")))

    ev = [t for t in base if base[t]["valid"] and best[t]["valid"]]
    b = sum(base[t]["passed"] and not best[t]["passed"] for t in ev)
    c = sum(best[t]["passed"] and not base[t]["passed"] for t in ev)
    p = mcnemar(b, c)
    inval = {"baseline": sum(not r["valid"] for r in base.values()),
             "best": sum(not r["valid"] for r in best.values())}
    reps.append({"n": len(ev), "baseline": sum(base[t]["passed"] for t in ev),
                 "best": sum(best[t]["passed"] for t in ev), "b": b, "c": c, "p": p, "invalid": inval})
    pooled_b += b; pooled_c += c; pooled_n += len(ev)
    pooled_base += reps[-1]["baseline"]; pooled_best += reps[-1]["best"]

    ck(f"rep {rep}: the shipped build never timed out", sum(r["timed_out"] for r in best.values()) == 0)
    ck(f"rep {rep}: the baseline timed out on the tasks it hung on",
       sum(r["timed_out"] for r in base.values()) >= 40)
    ck(f"rep {rep}: rule 3 — at most 3 invalid rows per arm", max(inval.values()) <= 3)
    ck(f"rep {rep}: rule 2 — net >= +10 (got {c - b:+d})", c - b >= 10)

pooled_p = mcnemar(pooled_b, pooled_c)
ck(f"pooled: {pooled_base}/{pooled_n} -> {pooled_best}/{pooled_n}, net {pooled_c - pooled_b:+d}",
   (pooled_n, pooled_base, pooled_best) == (157, 67, 98) and pooled_c - pooled_b == 31)
ck(f"pooled: rule 4 — exact McNemar p < 0.001 (got {pooled_p:.3g})", pooled_p < 0.001)

# --- the gain is the hang conversion, not new capability -------------------
hung_n = hung_gain = ran_n = ran_base = ran_best = 0
for rep, (brun, crun) in enumerate([("r1-base", "r1-best"), ("r2-base", "r2-best")], 1):
    _, base = load("ada-baseline", brun)
    _, best = load("ada", crun)
    for t in base:
        if not (base[t]["valid"] and best[t]["valid"]):
            continue
        if base[t]["turns"] == 0:
            hung_n += 1
            hung_gain += bool(best[t]["passed"])
        else:
            ran_n += 1
            ran_base += bool(base[t]["passed"])
            ran_best += bool(best[t]["passed"])
ck(f"decomposition: where the baseline hung with zero turns, 0/{hung_n} -> {hung_gain}/{hung_n}",
   hung_n > 0 and hung_gain == 28)
ck(f"decomposition: where the baseline ran, {ran_base}/{ran_n} -> {ran_best}/{ran_n} (no capability claim)",
   ran_best - ran_base <= 3)

# --- the analysis artifact agrees with this independent derivation ----------
art = json.loads((ROOT / f"bench/BASELINE_VS_BEST_{TS}.json").read_text())
ck("artifact: pooled contrast matches the re-derived numbers",
   art["pooled"]["contrast"]["n"] == pooled_n
   and art["pooled"]["contrast"]["baseline_pass"] == pooled_base
   and art["pooled"]["contrast"]["best_pass"] == pooled_best
   and abs(art["pooled"]["contrast"]["p"] - pooled_p) < 1e-12)
ck("artifact: verdict HOLDS with all four pre-registered conditions met",
   art["verdict"] == "HOLDS" and all(art["rule"].values()))

# --- the documents quote what was derived ----------------------------------
for rel, must in [
    ("bench/RUN_REGISTRY.md", ["R9a", "R9b", "R10a", "R10b", "67/157 → 98/157", "p = 7.92e-09"]),
    ("ada/RESULTS.md", ["67/157", "98/157", "p = 7.92e-09", "HOLDS"]),
    ("README.md", ["67/157", "98/157"]),
    ("blog.md", ["67/157", "98/157"]),
]:
    text = (ROOT / rel).read_text()
    ck(f"{rel}: quotes the confirmation run", all(m in text for m in must))
    ck(f"{rel}: does not call the shipped build unmeasured on SetupBench",
       "has not itself been run on SetupBench" not in text)

print(f"\n{'ALL PASS' if not fails else str(len(fails)) + ' FAILED'}: "
      f"{len(fails)} failures")
sys.exit(1 if fails else 0)
