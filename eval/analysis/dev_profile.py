#!/usr/bin/env python3
"""Dev-loop baseline profile + mining pass.

Reads the fresh dev-baseline arm (eval/results/dev-baseline.jsonl + raw trial
dirs under eval/jobs/dev-baseline) and produces:
  - eval/experiments/dev-loop/dev-baseline-profile.md (per-task profile:
    pass, cost, wall, turns, near-miss counts from ctrf.json)
  - mining signals printed to stdout (failure taxonomy, near-miss distance,
    oversized tool results, cache ratio, tool histograms) to feed the
    hypothesis queue in ledger.md

ANALYSIS ONLY: no API spend, no harbor runs, no code changes.
"""
import json
import glob
import os
from collections import Counter, defaultdict
from pathlib import Path

ROOT = "/root/optimize_ada/eval"
JOB = "dev-baseline"
JSONL = f"{ROOT}/results/{JSONL if False else 'dev-baseline'}.jsonl"
JOBS = f"{ROOT}/jobs/{JOB}"
OUT_MD = f"{ROOT}/experiments/dev-loop/dev-baseline-profile.md"

DEV_TASKS = [
    "cancel-async-tasks", "fix-git", "git-multibranch",
    "large-scale-text-editing", "log-summary-date-ranges",
    "openssl-selfsigned-cert", "regex-log", "sanitize-git-repo",
    "fix-code-vulnerability", "git-leak-recovery",
]


def load_jsonl(path):
    recs = []
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if line:
                try:
                    recs.append(json.loads(line))
                except Exception:
                    pass
    return recs


def near_miss(trial_dir):
    """Fraction of verifier tests passed in a failing trial (0..1).
    Reads verifier/ctrf.json; returns None when unavailable."""
    cf = os.path.join(trial_dir, "verifier", "ctrf.json")
    if not os.path.exists(cf):
        return None
    try:
        c = json.load(open(cf))
        tests = (c.get("results") or {}).get("tests") or []
        if not tests:
            return None
        passed = sum(1 for t in tests if t.get("status") == "passed")
        return passed / len(tests)
    except Exception:
        return None


def main():
    rows = load_jsonl(JSONL)
    print(f"Loaded {len(rows)} records from {JSONL}")
    by_task = defaultdict(list)
    for r in rows:
        by_task[r["task"]].append(r)

    # --- per-task aggregates ---
    table = []
    for t in DEV_TASKS:
        rs = by_task.get(t, [])
        if not rs:
            continue
        p = sum(1 for r in rs if r["pass"] == 1.0)
        costs = [r["cost_usd"] for r in rs if r.get("cost_usd") is not None]
        durs = [r["duration_ms"] for r in rs if r.get("duration_ms")]
        turns = [r["num_turns"] for r in rs if r.get("num_turns") is not None]
        # near-miss across failing trials
        nm = []
        for r in rs:
            if r["pass"] != 1.0 and not r.get("error"):
                trial_dir = os.path.join(JOBS, r["trial"])
                f = near_miss(trial_dir)
                if f is not None:
                    nm.append(f)
        nm_ge_half = sum(1 for x in nm if x >= 0.5)
        table.append({
            "task": t,
            "pass": p,
            "n": len(rs),
            "mean_cost": sum(costs) / len(costs) if costs else None,
            "mean_wall_s": sum(durs) / len(durs) / 1000 if durs else None,
            "mean_turns": sum(turns) / len(turns) if turns else None,
            "n_fail": len(rs) - p,
            "near_miss_fail": len(nm),
            "near_miss_ge_half": nm_ge_half,
        })

    tot_pass = sum(x["pass"] for x in table)
    tot_n = sum(x["n"] for x in table)
    all_costs = [r["cost_usd"] for r in rows if r.get("cost_usd") is not None]
    all_durs = [r["duration_ms"] for r in rows if r.get("duration_ms")]
    all_turns = [r["num_turns"] for r in rows if r.get("num_turns") is not None]
    n_exc = sum(1 for r in rows if r.get("error"))
    exc_tasks = Counter(r["task"] for r in rows if r.get("error"))

    # --- mining signals ---
    print("\n=== MINING SIGNALS (dev-baseline) ===")
    print(f"Exceptions: {n_exc} -> {dict(exc_tasks)}")

    # tool histogram + oversized results from ada-events
    tool_hist = Counter()
    n_oversized = 0
    n_results = 0
    total_result_chars = 0
    for f in sorted(glob.glob(os.path.join(JOBS, "*", "agent", "ada-events.jsonl"))):
        for line in open(f, errors="replace"):
            try:
                e = json.loads(line)
            except Exception:
                continue
            d = e.get("data") or {}
            t = d.get("type")
            if t == "TOOL_CALL_START":
                tool_hist[d.get("toolCallName") or "unknown"] += 1
            elif t == "TOOL_CALL_RESULT":
                c = d.get("content")
                n = len(c) if isinstance(c, str) else (len(json.dumps(c)) if isinstance(c, dict) else 0)
                n_results += 1
                total_result_chars += n
                if n > 10000:
                    n_oversized += 1
    print(f"Tool calls (all trials): {dict(tool_hist.most_common())}")
    print(f"Tool results: {n_results}, >10k chars: {n_oversized} "
          f"({100.0 * n_oversized / n_results:.1f}%), total chars {total_result_chars}")

    # cache ratio per trial
    cache_ratios = []
    for r in rows:
        ci = r.get("n_cache_tokens") or 0
        ii = r.get("n_input_tokens") or 0
        if ii > 0:
            cache_ratios.append(ci / ii)
    if cache_ratios:
        print(f"Cache-read ratio: mean {sum(cache_ratios) / len(cache_ratios):.3f}, "
              f"n={len(cache_ratios)}")

    # near-miss summary
    all_nm = [x["near_miss_fail"] for x in table]
    all_nmh = [x["near_miss_ge_half"] for x in table]
    print(f"Failing trials total: {sum(x['n_fail'] for x in table)}, "
          f"with ctrf near-miss data: {sum(all_nm)}, >=50% tests passed: {sum(all_nmh)}")

    # --- write profile md ---
    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    lines = []
    lines.append(f"# Dev-loop baseline profile — job `{JOB}`")
    lines.append("")
    lines.append(f"Arm: `dev-baseline` (untreated, all env gates OFF) · "
                 f"Model: `anthropic/claude-haiku-4-5` · "
                 f"Dataset: `terminal-bench@2.0` · {tot_n} trials "
                 f"(10 tasks × k=4) · {n_exc} exceptions")
    lines.append("")
    lines.append(f"**Suite pass: {tot_pass}/{tot_n} = {tot_pass / tot_n:.3f}** "
                 f"· mean cost ${sum(all_costs) / len(all_costs):.4f}/trial "
                 f"· mean wall {sum(all_durs) / len(all_durs) / 1000:.1f}s/trial")
    lines.append("")
    lines.append("## Per-task table")
    lines.append("")
    lines.append("| Task | Pass | Cost mean $ | Wall mean s | Turns mean | Fail | "
                 "Near-miss (ctrf) | ≥50% tests |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for x in sorted(table, key=lambda z: z["task"]):
        lines.append(
            f"| {x['task']} | {x['pass']}/{x['n']} | "
            f"{x['mean_cost']:.4f} | {x['mean_wall_s']:.1f} | {x['mean_turns']:.1f} | "
            f"{x['n_fail']} | {x['near_miss_fail']} | {x['near_miss_ge_half']} |"
        )
    lines.append("")
    lines.append("## Exceptions")
    lines.append("")
    for t, c in exc_tasks.items():
        lines.append(f"- {t}: {c}× AgentTimeoutError")
    lines.append("")
    lines.append("## Arm-B reference on the same 10-task subset")
    lines.append("")
    lines.append("- Sep 2 arm B: 29/40 = 0.725 (stale, pre-drift).")
    lines.append("- Fresh dev-baseline: {}/{:.0f} = {:.3f} → drift of {:.3f} confirms "
                 "the fresh-baseline requirement.".format(
                     tot_pass, tot_n, tot_pass / tot_n, tot_pass / tot_n - 0.725))
    lines.append("")
    lines.append("_Generated by `eval/analysis/dev_profile.py` (no API spend)._")
    with open(OUT_MD, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nWrote {OUT_MD}")


if __name__ == "__main__":
    main()
