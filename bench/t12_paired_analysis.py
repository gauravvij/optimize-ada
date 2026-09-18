#!/usr/bin/env python3
"""T1.2 paired-rung analysis (campaign-spec fina_run.md §3 rules 2-3; the spec was
removed during final packaging 2026-09-18 — rules recorded in bench/RUN_REGISTRY.md).

Candidate: targets/ada @ HEAD (T1.2 bundle, gates ADA_TIME_HINTS + ADA_BASH_CLAMP_REMAINING
default ON per E13, ADA_PROMPT_DOD default OFF after non-positive T1.1).
Reference: targets/ada-t01gateoff @ 6672af8 (T0.1 build — no T1.2 hooks exist structurally).

Usage: t12_paired_analysis.py <rung>   # rung in {dev12, val12}
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path("/home/azureuser/adaAgent")
RUNG = sys.argv[1] if len(sys.argv) > 1 else "dev12"
assert RUNG in ("dev12", "val12"), f"unknown rung {RUNG}"
RUN_ID = (ROOT / f"bench/t12_{RUNG}_runid.txt").read_text().strip().split("=", 1)[1]
CAND = ROOT / f"bench/diagnostics/{RUN_ID}/{RUNG}_t12_candidate.json"  # archived 2026-09-18
GATE = ROOT / f"bench/diagnostics/ada-t01gateoff/{RUN_ID}/{RUNG}_t01_gateoff.json"  # archived

cand = json.loads(CAND.read_text())
gate = json.loads(GATE.read_text())

cand_rows = {r["task_id"]: r for r in cand["results"]}
gate_rows = {r["task_id"]: r for r in gate["results"]}
assert set(cand_rows) == set(gate_rows), "task sets differ between arms"

n = len(cand_rows)
both = cand_only = gate_only = neither = 0
flip_table = []
per_task = []
for tid in sorted(cand_rows):
    c, g = cand_rows[tid], gate_rows[tid]
    cp, gp = bool(c["passed"]), bool(g["passed"])
    if cp and gp:
        both += 1
    elif cp and not gp:
        cand_only += 1
        flip_table.append({"task_id": tid, "flip": "gateoff-fail -> candidate-pass"})
    elif gp and not cp:
        gate_only += 1
        flip_table.append({"task_id": tid, "flip": "candidate-fail -> gateoff-pass"})
    else:
        neither += 1
    per_task.append({
        "task_id": tid, "candidate_pass": cp, "gateoff_pass": gp,
        "candidate_turns": c["turns"], "gateoff_turns": g["turns"],
        "candidate_timed_out": c["timed_out"], "gateoff_timed_out": g["timed_out"],
        "candidate_duration_s": round(c["duration_seconds"], 1),
        "gateoff_duration_s": round(g["duration_seconds"], 1),
        "candidate_agent_is_error": c["agent_is_error"],
        "gateoff_agent_is_error": g["agent_is_error"],
    })

b, c = gate_only, cand_only  # b = gateoff-only (candidate regressed), c = cand-only (converted)
# exact two-sided McNemar (binomial on discordant pairs)
nn = b + c
if nn == 0:
    p = 1.0
else:
    # two-sided exact: 2 * one-tail, capped at 1
    tail = sum(math.comb(nn, k) for k in range(0, min(b, c) + 1)) / (2 ** nn)
    p = min(1.0, 2 * tail)

# Newcombe method 10 (hybrid score) CI for difference in paired proportions
def wilson(k, m, z=1.959963985):
    if m == 0:
        return (0.0, 0.0, 0.0)
    phat = k / m
    denom = 1 + z * z / m
    centre = (phat + z * z / (2 * m)) / denom
    half = z * math.sqrt(phat * (1 - phat) / m + z * z / (4 * m * m)) / denom
    return (phat, centre - half, centre + half)

p1, l1, u1 = wilson(cand_only + both, n)
p2, l2, u2 = wilson(gate_only + both, n)
diff = p1 - p2
low = diff - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
high = diff + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)

cand_pass = sum(bool(r["passed"]) for r in cand_rows.values())
gate_pass = sum(bool(r["passed"]) for r in gate_rows.values())
cand_turns = sum(r["turns"] for r in cand_rows.values())
gate_turns = sum(r["turns"] for r in gate_rows.values())
cand_timeouts = sum(1 for r in cand_rows.values() if r["timed_out"])
gate_timeouts = sum(1 for r in gate_rows.values() if r["timed_out"])
cand_wall = sum(r["duration_seconds"] for r in cand_rows.values())
gate_wall = sum(r["duration_seconds"] for r in gate_rows.values())
# 'claimed verified but grader failed' = agent reported a terminal result (not error/timeout)
# but the grader failed the task
cand_claimed_failed = sum(
    1 for r in cand_rows.values()
    if r["terminal_result"] and not r["agent_is_error"] and not r["timed_out"] and not r["passed"]
)
gate_claimed_failed = sum(
    1 for r in gate_rows.values()
    if r["terminal_result"] and not r["agent_is_error"] and not r["timed_out"] and not r["passed"]
)

analysis = {
    "protocol": f"T1.2 {RUNG} paired rung (fina_run.md §3 rules 2-3)",
    "date": "2026-09-11",
    "candidate": {
        "arm": "T1.2 time-awareness bundle (ADA_TIME_HINTS + ADA_BASH_CLAMP_REMAINING default ON, ADA_PROMPT_DOD default OFF)",
        "workspace": "targets/ada",
        "commit": cand["workspace_commit"],
        "diagnostics": f"bench/diagnostics/{RUN_ID}/{RUNG}_t12_candidate.json",
        "log": f"bench/t12_{RUNG}_candidate.log",
    },
    "gateoff": {
        "arm": "T0.1 build (pre-T1.2; no time hooks exist structurally)",
        "workspace": "targets/ada-t01gateoff (git worktree @ 6672af8)",
        "commit": gate["workspace_commit"],
        "diagnostics": f"bench/diagnostics/ada-t01gateoff/{RUN_ID}/{RUNG}_t01_gateoff.json",
        "log": f"bench/t12_{RUNG}_gateoff.log",
    },
    "conditions": {
        "suite": RUNG + "-12", "task_timeout_seconds": 480, "grader_timeout_seconds": 600,
        "concurrency": 4, "seed": 20260907, "model": "z-ai/glm-5.3-flash",
        "node": "v24.19.0", "same_day": True, "sequential_arms": True,
        "run_id": RUN_ID,
    },
    "summary": {
        "candidate_pass": cand_pass, "gateoff_pass": gate_pass, "n": n,
        "both_pass": both, "candidate_only": cand_only, "gateoff_only": gate_only,
        "neither": neither,
        "candidate_turns": cand_turns, "gateoff_turns": gate_turns,
        "candidate_timeouts": cand_timeouts, "gateoff_timeouts": gate_timeouts,
        "candidate_wall_seconds_sum": round(cand_wall, 1),
        "gateoff_wall_seconds_sum": round(gate_wall, 1),
        "candidate_claimed_verified_but_grader_failed": cand_claimed_failed,
        "gateoff_claimed_verified_but_grader_failed": gate_claimed_failed,
    },
    "statistics": {
        "exact_mcnemar_b": b, "exact_mcnemar_c": c, "exact_mcnemar_p": p,
        "newcombe_95ci_diff": [round(low, 4), round(high, 4)],
        "note": f"b={b} (regressions), c={c} (conversions), discordant={nn}, two-sided exact p={p:.4f}; "
                "E11: anything smaller than ±3 on n=12 is noise.",
    },
    "flip_table": flip_table,
    "per_task": per_task,
    "decision": {},
}

# §3 rule 2: rung 1 non-positive -> early stop. Positive -> continue to validation-12.
net = cand_only - gate_only
positive = cand_pass > gate_pass and net > 0
analysis["decision"] = {
    "rung": RUNG + " paired",
    "net_conversions": net,
    "rung_1_positive": positive,
    "rule_2_early_stop": not positive,
    "next_step": (
        "proceed to validation-12 paired rung (§3 rule 3)" if RUNG == "dev12" else "proceed to remaining81 vs the T0.4 fresh control (§3 rule 3)"
        if positive else
        "EARLY STOP (§3 rule 2): rung 1 non-positive — skip validation-12 and remaining81; verdict HOLD"
    ),
}

out = ROOT / f"bench/T12_{RUNG.upper()}_PAIRED_ANALYSIS.json"
out.write_text(json.dumps(analysis, indent=2) + "\n")
print(json.dumps(analysis["summary"], indent=2))
print(json.dumps(analysis["statistics"], indent=2))
print("flips:", json.dumps(flip_table, indent=1))
print("DECISION:", json.dumps(analysis["decision"], indent=1))
print(f"written: {out}")
