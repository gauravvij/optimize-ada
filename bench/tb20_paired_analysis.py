#!/usr/bin/env python3
"""TB-20 paired analysis: ada-best3 (watchdog incumbent) vs ada-baseline on
Terminal-Bench 2.0 ranks 1-20 (bench/task-selection-40.md).

Per-task flips, exact McNemar on discordant pairs, turns/wall-clock/cost on
jointly-passed tasks. Reward (verifier grade) is the pass signal.
"""

from __future__ import annotations

import json
from math import comb
from pathlib import Path
import sys

sys.path.insert(0, "/home/azureuser/adaAgent/bench")
from parse_results import parse_job_dir  # noqa: E402

BENCH = Path("/home/azureuser/adaAgent/bench")
BASE_DIR = BENCH / "results-tb20-baseline/2026-09-09__14-40-51"
BEST_DIR = BENCH / "results-tb20-best3/2026-09-09__15-54-35"
OUT = BENCH / "TB20_PAIRED_ANALYSIS.json"

TASKS = [
    "fix-git", "prove-plus-comm", "cobol-modernization", "overfull-hbox",
    "crack-7z-hash", "raman-fitting", "mteb-leaderboard", "kv-store-grpc",
    "pytorch-model-recovery", "constraints-scheduling", "mteb-retrieve",
    "hf-model-inference", "merge-diff-arc-agi-task", "nginx-request-logging",
    "openssl-selfsigned-cert", "polyglot-c-py", "vulnerable-secret",
    "break-filter-js-from-html", "count-dataset-tokens", "extract-elf",
]


def mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(comb(n, k) for k in range(0, min(b, c) + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def main() -> None:
    base_rows = {t["task"]: t for t in parse_job_dir(BASE_DIR)}
    best_rows = {t["task"]: t for t in parse_job_dir(BEST_DIR)}

    # normalize task names (parse_results returns 'terminal-bench/<task>')
    def norm(rows):
        out = {}
        for k, v in rows.items():
            out[k.split("/")[-1]] = v
        return out

    base_rows, best_rows = norm(base_rows), norm(best_rows)

    assert set(base_rows) == set(best_rows) == set(TASKS), (
        set(base_rows) ^ set(TASKS), set(best_rows) ^ set(TASKS))
    for name, rows in (("baseline", base_rows), ("best3", best_rows)):
        assert not any(t.get("exception") for t in rows.values()), name
        assert all(t.get("reward") is not None for t in rows.values()), (
            name, [t for t in rows.values() if t.get("reward") is None])

    conv, reg = [], []
    per_task = []
    for t in TASKS:
        b, s = base_rows[t], best_rows[t]
        bp, sp = b["reward"] == 1.0, s["reward"] == 1.0
        if not bp and sp:
            conv.append(t)
        elif bp and not sp:
            reg.append(t)
        per_task.append({
            "task": t,
            "baseline": {"pass": bp, "is_err": b["is_error"], "turns": b["turns"],
                         "cost_usd": b["cost_usd"], "exec_s": b["agent_exec_s"]},
            "best3": {"pass": sp, "is_err": s["is_error"], "turns": s["turns"],
                      "cost_usd": s["cost_usd"], "exec_s": s["agent_exec_s"]},
            "flip": "conversion" if t in conv else "regression" if t in reg else None,
        })

    b_pass = sum(1 for t in TASKS if base_rows[t]["reward"] == 1.0)
    s_pass = sum(1 for t in TASKS if best_rows[t]["reward"] == 1.0)
    b_err = sum(1 for t in TASKS if base_rows[t]["is_error"])
    s_err = sum(1 for t in TASKS if best_rows[t]["is_error"])
    p = mcnemar_exact(len(conv), len(reg))

    # efficiency on jointly-passed tasks (same task, both pass)
    joint = [t for t in TASKS
             if base_rows[t]["reward"] == 1.0 and best_rows[t]["reward"] == 1.0]
    joint_stats = {
        "n_jointly_passed": len(joint),
        "baseline_turns": sum(base_rows[t]["turns"] or 0 for t in joint),
        "best3_turns": sum(best_rows[t]["turns"] or 0 for t in joint),
        "baseline_cost_usd": round(sum(base_rows[t]["cost_usd"] or 0 for t in joint), 2),
        "best3_cost_usd": round(sum(best_rows[t]["cost_usd"] or 0 for t in joint), 2),
        "baseline_exec_s": round(sum(base_rows[t]["agent_exec_s"] or 0 for t in joint), 1),
        "best3_exec_s": round(sum(best_rows[t]["agent_exec_s"] or 0 for t in joint), 1),
    }

    summary = {
        "protocol": {
            "benchmark": "Terminal-Bench 2.0 (terminal-bench/terminal-bench-2) via Harbor 0.21.0",
            "tasks": "ranks 1-20 of bench/task-selection-40.md (4 easy / 16 medium)",
            "arms": {
                "baseline": "bench/ada-baseline.tgz (git commit df0c537)",
                "best3": "bench/ada-best3.tgz (targets/ada working tree: iteration-1 + iteration-2 watchdog, uncommitted diff vs df0c537)",
            },
            "conditions": "identical harness (bench/ada_agent.py), model z-ai/glm-5.3-flash via OpenRouter, node v24.19.0, -n 4, per-task agent timeout from task.toml, runner_cap_ms = (timeout-60s)*1000",
            "run_dates": "2026-09-09: baseline 14:40 UTC, best3 15:54 UTC (sequential, same day)",
            "pass_signal": "verifier reward == 1.0",
        },
        "primary": {
            "baseline_pass": b_pass,
            "best3_pass": s_pass,
            "n": 20,
            "pass_rate_difference": round((s_pass - b_pass) / 20, 4),
            "mcnemar_exact": {
                "b": len(conv), "c": len(reg), "n_discordant": len(conv) + len(reg),
                "p_value": p,
            },
        },
        "secondary": {
            "baseline_is_err": b_err,
            "best3_is_err": s_err,
            "baseline_turns_total": sum(base_rows[t]["turns"] or 0 for t in TASKS),
            "best3_turns_total": sum(best_rows[t]["turns"] or 0 for t in TASKS),
            "baseline_cost_total_usd": round(sum(base_rows[t]["cost_usd"] or 0 for t in TASKS), 2),
            "best3_cost_total_usd": round(sum(best_rows[t]["cost_usd"] or 0 for t in TASKS), 2),
            "baseline_exec_total_s": round(sum(base_rows[t]["agent_exec_s"] or 0 for t in TASKS), 1),
            "best3_exec_total_s": round(sum(best_rows[t]["agent_exec_s"] or 0 for t in TASKS), 1),
            "jointly_passed_efficiency": joint_stats,
        },
        "flip_table": {
            "conversions_baseline_fail_best3_pass": conv,
            "regressions_baseline_pass_best3_fail": reg,
        },
        "per_task": per_task,
    }

    OUT.write_text(json.dumps(summary, indent=2) + "\n")

    print("=== TB-20 paired analysis (best3 vs baseline, n=20) ===")
    print(f"  baseline: {b_pass}/20 pass, {b_err} is_err, "
          f"{summary['secondary']['baseline_turns_total']} turns, "
          f"${summary['secondary']['baseline_cost_total_usd']}, "
          f"{summary['secondary']['baseline_exec_total_s']}s exec")
    print(f"  best3:    {s_pass}/20 pass, {s_err} is_err, "
          f"{summary['secondary']['best3_turns_total']} turns, "
          f"${summary['secondary']['best3_cost_total_usd']}, "
          f"{summary['secondary']['best3_exec_total_s']}s exec")
    print(f"  exact McNemar: b={len(conv)} c={len(reg)} n={len(conv)+len(reg)} p={p:.4f}")
    for t in conv:
        print(f"    + conv  {t}")
    for t in reg:
        print(f"    - regr  {t}")
    js = joint_stats
    print(f"  jointly-passed (n={js['n_jointly_passed']}): turns "
          f"{js['baseline_turns']}->{js['best3_turns']}, cost "
          f"${js['baseline_cost_usd']}->${js['best3_cost_usd']}, exec "
          f"{js['baseline_exec_s']}s->{js['best3_exec_s']}s")
    print(f"\nsaved: {OUT}")


if __name__ == "__main__":
    main()
