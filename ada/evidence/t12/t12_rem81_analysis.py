#!/usr/bin/env python3
"""T1.2 remaining81 paired rung analysis (campaign-spec fina_run.md §3 rules 3-4;
the spec was removed during final packaging 2026-09-18 — rules in bench/RUN_REGISTRY.md).

Candidate: targets/ada @ HEAD (T1.2 bundle, gates default ON, DOD off) — fresh run.
Reference: the stored T0.4 fresh control (run_id 20260910T0728Z-t04ctrl, commit 6672af8,
24/81 pass, 0 timeouts, 1544 turns) — same-build same-day-style control per the spec's
pairing definition (planner guidance: reuse the stored control, do not re-run).

Mechanism metrics for §3 rule 4 (predicted direction: both DOWN on the candidate):
  - watchdog interrupts: count of 'hard-deadline' banner lines in each arm's log
  - early-stop-with-unused-budget: tasks where the agent stopped well before the
    task timeout (duration < 60% of the 480 s budget) yet failed — wasted budget
"""
from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path("/home/azureuser/adaAgent")
RUN_ID = (ROOT / "bench/t12_rem81_runid.txt").read_text().strip().split("=", 1)[1]
CAND = ROOT / f"bench/diagnostics/{RUN_ID}/rem81_t12_candidate.json"  # archived 2026-09-18
CTRL = ROOT / "bench/diagnostics/20260910T0728Z-t04ctrl/0.json"  # archived 2026-09-18
CAND_LOG = ROOT / "bench/t12_rem81_candidate.log"
CTRL_LOG = ROOT / "bench/t04_control_run.log"

cand = json.loads(CAND.read_text())
ctrl = json.loads(CTRL.read_text())

cand_rows = {r["task_id"]: r for r in cand["results"]}
ctrl_rows = {r["task_id"]: r for r in ctrl["results"]}
assert set(cand_rows) == set(ctrl_rows), f"task sets differ: {set(cand_rows) ^ set(ctrl_rows)}"

n = len(cand_rows)
both = cand_only = ctrl_only = neither = 0
flip_table = []
per_task = []
for tid in sorted(cand_rows):
    c, g = cand_rows[tid], ctrl_rows[tid]
    cp, gp = bool(c["passed"]), bool(g["passed"])
    if cp and gp:
        both += 1
    elif cp and not gp:
        cand_only += 1
        flip_table.append({"task_id": tid, "flip": "control-fail -> candidate-pass"})
    elif gp and not cp:
        ctrl_only += 1
        flip_table.append({"task_id": tid, "flip": "candidate-fail -> control-pass"})
    else:
        neither += 1
    per_task.append({
        "task_id": tid, "candidate_pass": cp, "control_pass": gp,
        "candidate_turns": c["turns"], "control_turns": g["turns"],
        "candidate_timed_out": c["timed_out"], "control_timed_out": g["timed_out"],
        "candidate_duration_s": round(c["duration_seconds"], 1),
        "control_duration_s": round(g["duration_seconds"], 1),
    })

b, c = ctrl_only, cand_only  # b = control-only (regressions), c = candidate-only (conversions)
nn = b + c
if nn == 0:
    p = 1.0
else:
    tail = sum(math.comb(nn, k) for k in range(0, min(b, c) + 1)) / (2 ** nn)
    p = min(1.0, 2 * tail)

def wilson(k, m, z=1.959963985):
    if m == 0:
        return (0.0, 0.0, 0.0)
    phat = k / m
    denom = 1 + z * z / m
    centre = (phat + z * z / (2 * m)) / denom
    half = z * math.sqrt(phat * (1 - phat) / m + z * z / (4 * m * m)) / denom
    return (phat, centre - half, centre + half)

p1, l1, u1 = wilson(cand_only + both, n)
p2, l2, u2 = wilson(ctrl_only + both, n)
diff = p1 - p2
low = diff - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
high = diff + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)

cand_pass = sum(bool(r["passed"]) for r in cand_rows.values())
ctrl_pass = sum(bool(r["passed"]) for r in ctrl_rows.values())
cand_turns = sum(r["turns"] for r in cand_rows.values())
ctrl_turns = sum(r["turns"] for r in ctrl_rows.values())
cand_timeouts = sum(1 for r in cand_rows.values() if r["timed_out"])
ctrl_timeouts = sum(1 for r in ctrl_rows.values() if r["timed_out"])
cand_wall = sum(r["duration_seconds"] for r in cand_rows.values())
ctrl_wall = sum(r["duration_seconds"] for r in ctrl_rows.values())
cand_claimed_failed = sum(
    1 for r in cand_rows.values()
    if r["terminal_result"] and not r["agent_is_error"] and not r["timed_out"] and not r["passed"]
)
ctrl_claimed_failed = sum(
    1 for r in ctrl_rows.values()
    if r["terminal_result"] and not r["agent_is_error"] and not r["timed_out"] and not r["passed"]
)

# mechanism metrics
cand_interrupts = CAND_LOG.read_text().count("hard-deadline") if CAND_LOG.exists() else None
ctrl_interrupts = CTRL_LOG.read_text().count("hard-deadline") if CTRL_LOG.exists() else None
# early-stop-with-unused-budget: failed AND finished in < 60% of the 480s task budget
def early_stop_unused(rows):
    return sum(
        1 for r in rows.values()
        if not r["passed"] and not r["timed_out"] and r["duration_seconds"] < 0.6 * 480
    )
cand_early = early_stop_unused(cand_rows)
ctrl_early = early_stop_unused(ctrl_rows)

analysis = {
    "protocol": "T1.2 remaining81 paired rung (fina_run.md §3 rules 3-4)",
    "date": "2026-09-11",
    "candidate": {
        "arm": "T1.2 time-awareness bundle (ADA_TIME_HINTS + ADA_BASH_CLAMP_REMAINING default ON, ADA_PROMPT_DOD default OFF)",
        "workspace": "targets/ada",
        "commit": cand["workspace_commit"],
        "diagnostics": f"bench/diagnostics/{RUN_ID}/rem81_t12_candidate.json",
        "log": "bench/t12_rem81_candidate.log",
    },
    "control": {
        "arm": "T0.4 fresh control (T0.1 build @ 6672af8, run 2026-09-10)",
        "workspace": "targets/ada",
        "commit": ctrl["workspace_commit"],
        "diagnostics": "bench/diagnostics/20260910T0728Z-t04ctrl/0.json",
        "log": "bench/t04_control_run.log",
        "note": "stored fresh control reused per spec pairing definition (planner-approved); "
                "cross-day pairing (2026-09-10 control vs 2026-09-11 candidate) — flagged per E11",
    },
    "conditions": {
        "suite": "remaining81", "task_timeout_seconds": 480, "grader_timeout_seconds": 600,
        "concurrency": 4, "seed": 20260907, "model": "z-ai/glm-5.3-flash",
        "node": "v24.19.0", "run_id": RUN_ID,
    },
    "summary": {
        "candidate_pass": cand_pass, "control_pass": ctrl_pass, "n": n,
        "both_pass": both, "candidate_only": cand_only, "control_only": ctrl_only,
        "neither": neither,
        "candidate_turns": cand_turns, "control_turns": ctrl_turns,
        "candidate_timeouts": cand_timeouts, "control_timeouts": ctrl_timeouts,
        "candidate_wall_seconds_sum": round(cand_wall, 1),
        "control_wall_seconds_sum": round(ctrl_wall, 1),
        "candidate_claimed_verified_but_grader_failed": cand_claimed_failed,
        "control_claimed_verified_but_grader_failed": ctrl_claimed_failed,
        "api_seconds_and_thinking_tokens": "not obtainable from SetupBench diagnostics "
            "(token fields are 0 per known harness limitation); wall seconds reported instead",
    },
    "statistics": {
        "exact_mcnemar_b": b, "exact_mcnemar_c": c, "exact_mcnemar_p": p,
        "newcombe_95ci_diff": [round(low, 4), round(high, 4)],
        "note": f"b={b} (regressions), c={c} (conversions), discordant={nn}, "
                f"two-sided exact p={p:.4f}",
    },
    "mechanism_metrics": {
        "watchdog_interrupts_candidate": cand_interrupts,
        "watchdog_interrupts_control": ctrl_interrupts,
        "predicted_direction": "down",
        "early_stop_with_unused_budget_candidate": cand_early,
        "early_stop_with_unused_budget_control": ctrl_early,
        "predicted_direction_early_stop": "down",
    },
    "flip_table": flip_table,
    "per_task": per_task,
    "decision": {},
}

net = cand_only - ctrl_only
no_sig_regression = b <= 2 or p < 0.05  # significant regression = McNemar-significant excess of regressions
mechanism_moved = (
    (cand_interrupts is not None and ctrl_interrupts is not None and cand_interrupts < ctrl_interrupts)
    or (cand_early < ctrl_early)
)
promote = no_sig_regression and (net >= 3 or mechanism_moved)
analysis["decision"] = {
    "rung": "remaining81 paired (final rung)",
    "net_conversions": net,
    "rule_4_no_significant_regression": no_sig_regression,
    "rule_4_net_conversions_ge_3": net >= 3,
    "rule_4_mechanism_metric_moved_as_predicted": mechanism_moved,
    "promote": promote,
    "verdict": "PROMOTED" if promote else "NOT PROMOTED (HOLD)",
}

out = ROOT / "bench/T12_REM81_PAIRED_ANALYSIS.json"
out.write_text(json.dumps(analysis, indent=2) + "\n")
print(json.dumps(analysis["summary"], indent=2))
print(json.dumps(analysis["statistics"], indent=2))
print("mechanism:", json.dumps(analysis["mechanism_metrics"], indent=1))
print("flips:", json.dumps(flip_table, indent=1))
print("DECISION:", json.dumps(analysis["decision"], indent=1))
print(f"written: {out}")
