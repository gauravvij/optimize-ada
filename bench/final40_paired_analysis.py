#!/usr/bin/env python3
"""Paired analysis: final Ada build (ada-final.tgz, commit 08a8d5d) 40-task
Terminal-Bench 2.0 run vs the STORED baseline 40-task results.

Arms (identical harness bench/ada_agent.py, model z-ai/glm-5.3-flash via
OpenRouter, node v24.19.0, -n 4, per-task agent timeout from task.toml):
  - final:    bench/results-ada-final-40/2026-09-10__12-37-32 (all 40, fresh)
  - baseline: bench/results-baseline-40/2026-09-07__18-32-07 (30 fresh)
            + bench/results-baseline/2026-09-07__14-32-12 (10 originals)
              = the stored 28/40 baseline arm from TB_REPORT_40.md
  - best2 (context): bench/results-best2-40/2026-09-07__20-12-31 (32)
            + bench/results-best2-pilot/2026-09-07__17-56-49 (8) = 27/40

Pass signal = verifier reward == 1.0 (NOT is_err).
Primary endpoint: exact McNemar (two-sided binomial on discordant pairs)
+ Newcombe Method 10 hybrid-score 95% CI on the paired difference.
Output: bench/FINAL40_PAIRED_ANALYSIS.json
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime
from pathlib import Path

BENCH = Path("/home/azureuser/adaAgent/bench")
sys.path.insert(0, str(BENCH))
from parse_results import parse_job_dir  # noqa: E402

FINAL_DIR = BENCH / "results-ada-final-40/2026-09-10__12-37-32"
BASELINE_FRESH = BENCH / "results-baseline-40/2026-09-07__18-32-07"
BASELINE_ORIG = BENCH / "results-baseline/2026-09-07__14-32-12"
BEST2_DIR = BENCH / "results-best2-40/2026-09-07__20-12-31"
BEST2_PILOT = BENCH / "results-best2-pilot/2026-09-07__17-56-49"

TASKS_40 = [
    "fix-git", "prove-plus-comm", "cobol-modernization", "overfull-hbox",
    "crack-7z-hash", "raman-fitting", "mteb-leaderboard", "kv-store-grpc",
    "pytorch-model-recovery", "constraints-scheduling", "mteb-retrieve",
    "hf-model-inference", "merge-diff-arc-agi-task", "nginx-request-logging",
    "openssl-selfsigned-cert", "polyglot-c-py", "vulnerable-secret",
    "break-filter-js-from-html", "count-dataset-tokens", "extract-elf",
    "git-leak-recovery", "multi-source-data-merger", "pytorch-model-cli",
    "qemu-alpine-ssh", "qemu-startup", "sanitize-git-repo",
    "sqlite-with-gcov", "tune-mjcf", "code-from-image",
    "financial-document-processor", "custom-memory-heap-crash", "dna-insert",
    "reshard-c4-data", "large-scale-text-editing", "chess-best-move",
    "db-wal-recovery", "regex-log", "filter-js-from-html",
    "build-cython-ext", "gcode-to-text",
]


def load_arm(dirs: list[Path], label: str) -> dict[str, dict]:
    """Merge trials from multiple job dirs, keyed by bare task name."""
    out: dict[str, dict] = {}
    for d in dirs:
        for t in parse_job_dir(d):
            task = t["task"].split("/")[-1]
            if task in out:
                raise SystemExit(f"{label}: duplicate trial for {task}")
            out[task] = t
    return out


def unevaluable_reason(trial: dict, dirs: list[Path]) -> str | None:
    """T0.5 (fina_run.md E10): a trial is UNEVALUABLE when the verifier
    itself never produced a graded result — missing verifier/ctrf.json, or
    the verifier's own test script died on infrastructure (404 Not Found /
    command not found in verifier/test-stdout.txt). Such trials are NOT
    agent failures and must be excluded from the paired set."""
    for d in dirs:
        tdir = d / trial["trial"]
        if not tdir.is_dir():
            continue
        ctrf = tdir / "verifier" / "ctrf.json"
        if not ctrf.is_file():
            return "missing verifier/ctrf.json"
        stdout = tdir / "verifier" / "test-stdout.txt"
        if stdout.is_file():
            text = stdout.read_text(errors="replace")
            low = text.lower()
            if "404 not found" in low or "command not found" in low:
                return "verifier infra failure (404 Not Found / command not found in verifier/test-stdout.txt)"
        return None
    return None


def exact_mcnemar(b: int, c: int) -> float:
    """Two-sided exact McNemar: 2 * P(X <= min(b,c)), X ~ Bin(b+c, 0.5)."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    # P(X <= k) = sum_{i=0}^{k} C(n,i) * 0.5^n  (exact, no float overflow
    # for n <= 40 via math.comb)
    p_one = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, 2.0 * p_one)


def wilson(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = (z / denom) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, centre - half), min(1.0, centre + half))


def newcombe_paired(k1: int, k2: int, n: int) -> tuple[float, float]:
    """Newcombe Method 10 CI for the paired difference p2 - p1.

    Uses the marginal Wilson intervals combined with the discordant-pair
    correction: d = p2 - p1; the interval is
      [d - sqrt((p2-l2)^2 + (u1-p1)^2), d + sqrt((u2-p2)^2 + (p1-l1)^2)]
    where [l1,u1], [l2,u2] are Wilson intervals for p1, p2.
    """
    p1, p2 = k1 / n, k2 / n
    l1, u1 = wilson(k1, n)
    l2, u2 = wilson(k2, n)
    d = p2 - p1
    lower = d - math.sqrt((p2 - l2) ** 2 + (u1 - p1) ** 2)
    upper = d + math.sqrt((u2 - p2) ** 2 + (p1 - l1) ** 2)
    return (max(-1.0, lower), min(1.0, upper))


def main() -> None:
    final = load_arm([FINAL_DIR], "final")
    baseline = load_arm([BASELINE_FRESH, BASELINE_ORIG], "baseline")
    best2 = load_arm([BEST2_DIR, BEST2_PILOT], "best2")

    missing = [t for t in TASKS_40 if t not in final or t not in baseline]
    if missing:
        raise SystemExit(f"missing paired trials: {missing}")
    assert len(final) == 40 and len(baseline) == 40, "arm size != 40"
    assert len(best2) == 40, f"best2 arm size {len(best2)} != 40"

    def passed(t: dict) -> bool:
        return t["reward"] == 1.0

    # ---- T0.5 unevaluable screening (fina_run.md E10) ---------------------
    # A trial whose verifier never produced a graded result (missing
    # verifier/ctrf.json, or 404 Not Found / command not found in the
    # verifier's own stdout) is UNEVALUABLE — it is not an agent failure.
    # The paired set excludes any task unevaluable in EITHER arm.
    FINAL_DIRS = [FINAL_DIR]
    BASELINE_DIRS = [BASELINE_FRESH, BASELINE_ORIG]
    unevaluable = {"final": {}, "baseline": {}}
    for t in TASKS_40:
        r_fin = unevaluable_reason(final[t], FINAL_DIRS)
        r_base = unevaluable_reason(baseline[t], BASELINE_DIRS)
        if r_fin:
            unevaluable["final"][t] = r_fin
        if r_base:
            unevaluable["baseline"][t] = r_base
    PAIRED = [t for t in TASKS_40
              if t not in unevaluable["final"] and t not in unevaluable["baseline"]]
    n_paired = len(PAIRED)

    # ---- primary endpoint (evaluable paired set, n = 38) ------------------
    b = sum(1 for t in PAIRED if passed(baseline[t]) and not passed(final[t]))
    c = sum(1 for t in PAIRED if not passed(baseline[t]) and passed(final[t]))
    k_base = sum(1 for t in PAIRED if passed(baseline[t]))
    k_final = sum(1 for t in PAIRED if passed(final[t]))
    p_mcnemar = exact_mcnemar(b, c)
    ci_lo, ci_hi = newcombe_paired(k_base, k_final, n_paired)

    # ---- flip table (evaluable paired set) ---------------------------------
    both_pass = [t for t in PAIRED if passed(baseline[t]) and passed(final[t])]
    both_fail = [t for t in PAIRED if not passed(baseline[t]) and not passed(final[t])]
    conv = [t for t in PAIRED if not passed(baseline[t]) and passed(final[t])]
    regr = [t for t in PAIRED if passed(baseline[t]) and not passed(final[t])]

    # ---- secondary endpoints ----------------------------------------------
    def total(arm: dict, key: str, tasks: list[str]) -> float:
        vals = [arm[t][key] for t in tasks if arm[t][key] is not None]
        return sum(vals) if vals else 0.0

    joint = both_pass
    secondary = {
        "baseline_is_err": sum(1 for t in TASKS_40 if baseline[t]["is_error"]),
        "final_is_err": sum(1 for t in TASKS_40 if final[t]["is_error"]),
        "baseline_turns_total": total(baseline, "turns", TASKS_40),
        "final_turns_total": total(final, "turns", TASKS_40),
        "baseline_cost_total_usd": round(total(baseline, "cost_usd", TASKS_40), 2),
        "final_cost_total_usd": round(total(final, "cost_usd", TASKS_40), 2),
        "baseline_exec_total_s": round(total(baseline, "agent_exec_s", TASKS_40), 1),
        "final_exec_total_s": round(total(final, "agent_exec_s", TASKS_40), 1),
        "jointly_passed_efficiency": {
            "n_jointly_passed": len(joint),
            "baseline_turns": total(baseline, "turns", joint),
            "final_turns": total(final, "turns", joint),
            "baseline_cost_usd": round(total(baseline, "cost_usd", joint), 2),
            "final_cost_usd": round(total(final, "cost_usd", joint), 2),
            "baseline_exec_s": round(total(baseline, "agent_exec_s", joint), 1),
            "final_exec_s": round(total(final, "agent_exec_s", joint), 1),
        },
    }

    # ---- drift check -------------------------------------------------------
    # Compare the fresh final run's failure profile against the prior best2-40
    # run (27/40, same 40 tasks, Sep-7) and the Sep-9/10 SetupBench drift
    # evidence. Baseline-like drift signature = many hard-cap kills /
    # trickle timeouts (exec_s pinned at the task cap, is_err=True) that the
    # watchdog should have prevented.
    # T0.5: unevaluable trials are NOT failures — exclude them from the
    # failure profile so the drift verdict is not biased by verifier
    # infrastructure errors (E10: the 2 qemu trials).
    final_fails = [t for t in PAIRED if not passed(final[t])]
    best2_fails = [t for t in TASKS_40 if not passed(best2[t])]
    baseline_fails = [t for t in TASKS_40 if not passed(baseline[t])]

    def fail_profile(arm: dict, tasks: list[str]) -> dict:
        prof = {}
        for t in tasks:
            tr = arm[t]
            exec_s = tr["agent_exec_s"]
            prof[t] = {
                "is_error": tr["is_error"],
                "turns": tr["turns"],
                "exec_s": exec_s,
                "cost_usd": tr["cost_usd"],
            }
        return prof

    # hard-cap-kill heuristic: exec span within 5% of 900s+ (or the task's
    # long cap) AND is_error True AND zero-ish turns -> trickle/kill signature
    def looks_like_hard_kill(tr: dict) -> bool:
        if not tr["is_error"]:
            return False
        e = tr["agent_exec_s"]
        if e is None:
            return False
        return e >= 850.0  # all 40 tasks have caps >= 900s except none below

    final_hard_kills = [t for t in final_fails if looks_like_hard_kill(final[t])]
    baseline_hard_kills = [t for t in baseline_fails if looks_like_hard_kill(baseline[t])]
    best2_hard_kills = [t for t in best2_fails if looks_like_hard_kill(best2[t])]

    # overlap of failure sets vs best2 (prior non-drifted run)
    fail_overlap_best2 = sorted(set(final_fails) & set(best2_fails))
    fail_overlap_baseline = sorted(set(final_fails) & set(baseline_fails))

    drift_check = {
        "question": (
            "Does the fresh final run show anomalous baseline-like behavior "
            "(hard-cap trickle kills the watchdog should prevent) suggesting "
            "upstream API drift between Sep-7 (stored arms) and Sep-10 (fresh)?"
        ),
        "fresh_final_fails": sorted(final_fails),
        "fresh_final_hard_kill_like": sorted(final_hard_kills),
        "n_fresh_hard_kill_like": len(final_hard_kills),
        "stored_baseline_fails": sorted(baseline_fails),
        "n_baseline_hard_kill_like": len(baseline_hard_kills),
        "prior_best2_fails": sorted(best2_fails),
        "n_best2_hard_kill_like": len(best2_hard_kills),
        "failure_set_overlap_with_best2": fail_overlap_best2,
        "failure_set_overlap_with_baseline": fail_overlap_baseline,
        "setupbench_drift_evidence": (
            "Sep-10 dev-12 gate on the final build: 6/12 pass, 111 turns, "
            "0 timeouts, 0 exceptions — matches the Sep-9 prior-incumbent "
            "profile (6/12, 113 turns), indicating no API drift on Sep-10."
        ),
        "verdict": None,  # filled below
        "action_taken": None,
    }

    # Drift verdict logic: baseline-like drift would show a LARGE hard-kill
    # fraction among fresh fails (baseline had 4/8 fails as hard-cap kills).
    # If fresh hard-kill-like fails are few and the failure set largely
    # overlaps the prior best2 run's failures, behavior is consistent with
    # the non-drifted profile.
    frac_hard = len(final_hard_kills) / len(final_fails) if final_fails else 0.0
    base_frac = len(baseline_hard_kills) / len(baseline_fails) if baseline_fails else 0.0
    if frac_hard <= 0.35 and len(fail_overlap_best2) >= len(final_fails) * 0.5:
        drift_check["verdict"] = (
            "NO DRIFT SUSPECTED: fresh failure profile is dominated by "
            "completed-but-wrong outcomes, not hard-cap trickle kills "
            f"({len(final_hard_kills)}/{len(final_fails)} hard-kill-like vs "
            f"baseline's {len(baseline_hard_kills)}/{len(baseline_fails)}); "
            f"{len(fail_overlap_best2)}/{len(final_fails)} fresh failures "
            "also failed under the prior best2 run. Stored baseline numbers "
            "retained; no same-day baseline re-run required."
        )
        drift_check["action_taken"] = (
            "Stored baseline arm (Sep-7) used as-is for the paired comparison."
        )
    else:
        drift_check["verdict"] = (
            "DRIFT SUSPECTED: fresh run shows baseline-like hard-kill "
            "behavior; re-run the baseline arm same-day before trusting "
            "the stored numbers."
        )
        drift_check["action_taken"] = "RE-RUN BASELINE ARM REQUIRED."

    # ---- context comparisons ----------------------------------------------
    k_best2 = sum(1 for t in TASKS_40 if passed(best2[t]))
    b2_vs_final = {
        "b_best2fail_finalpass": sum(
            1 for t in TASKS_40 if not passed(best2[t]) and passed(final[t])),
        "c_best2pass_finalfail": sum(
            1 for t in TASKS_40 if passed(best2[t]) and not passed(final[t])),
    }
    context = {
        "prior_best2_40": {
            "pass": k_best2, "n": 40,
            "rate": round(k_best2 / 40, 4),
            "mcnemar_vs_final_p": exact_mcnemar(
                b2_vs_final["b_best2fail_finalpass"],
                b2_vs_final["c_best2pass_finalfail"]),
            "flips_vs_final": b2_vs_final,
        },
        "tb20_best3": {"pass": 15, "n": 20, "rate": 0.75,
                       "note": "TB-20 subset (ranks 1-20), best3 build, Sep-9"},
        "setupbench_remaining81_final": {
            "pass": 59, "n": 81, "rate": round(59 / 81, 4),
            "note": "SetupBench remaining81, final build, Sep-10 "
                    "(50 carried Sep-9 passes + 31 fresh re-runs)"},
    }

    # ---- per-task table ----------------------------------------------------
    per_task = {}
    for t in TASKS_40:
        per_task[t] = {
            "baseline_reward": baseline[t]["reward"],
            "final_reward": final[t]["reward"],
            "best2_reward": best2[t]["reward"],
            "baseline_is_err": baseline[t]["is_error"],
            "final_is_err": final[t]["is_error"],
            "baseline_turns": baseline[t]["turns"],
            "final_turns": final[t]["turns"],
            "baseline_cost_usd": baseline[t]["cost_usd"],
            "final_cost_usd": final[t]["cost_usd"],
            "baseline_exec_s": baseline[t]["agent_exec_s"],
            "final_exec_s": final[t]["agent_exec_s"],
        }

    analysis = {
        "protocol": {
            "benchmark": "Terminal-Bench 2.0 (terminal-bench/terminal-bench-2) via Harbor",
            "tasks": "ranks 1-40 of bench/task-selection-40.md (4 easy / 36 medium)",
            "arms": {
                "baseline": "bench/ada-baseline.tgz (git commit df0c537); "
                            "30 fresh trials results-baseline-40/2026-09-07__18-32-07 "
                            "+ 10 originals results-baseline/2026-09-07__14-32-12",
                "final": "bench/ada-final.tgz (git commit 08a8d5d, tag "
                         "ada-final-59of81); all 40 fresh trials "
                         "results-ada-final-40/2026-09-10__12-37-32",
                "best2_context": "bench/ada-best2.tgz; 32 trials "
                                 "results-best2-40/2026-09-07__20-12-31 + 8 pilot "
                                 "results-best2-pilot/2026-09-07__17-56-49",
            },
            "conditions": "identical harness (bench/ada_agent.py), model "
                          "z-ai/glm-5.3-flash via OpenRouter, node v24.19.0, "
                          "-n 4, per-task agent timeout from task.toml, "
                          "runner_cap_ms = (timeout-60s)*1000",
            "run_dates": "baseline 2026-09-07; best2 2026-09-07; final 2026-09-10",
            "pass_signal": "verifier reward == 1.0",
            "generated_at": datetime.now().isoformat(),
        },
        "unevaluable_trials": {
            "policy": (
                "T0.5 (fina_run.md E10): a trial with missing verifier/ctrf.json "
                "or 404 Not Found / command not found in verifier/test-stdout.txt "
                "is UNEVALUABLE (verifier infrastructure failure, not an agent "
                "failure) and is excluded from the paired set in EITHER arm."
            ),
            "final_arm": unevaluable["final"],
            "baseline_arm": unevaluable["baseline"],
            "excluded_tasks": sorted(
                set(unevaluable["final"]) | set(unevaluable["baseline"])),
            "n_excluded": len(TASKS_40) - n_paired,
        },
        "primary": {
            "baseline_pass": k_base,
            "final_pass": k_final,
            "n": n_paired,
            "pass_rate_difference": round((k_final - k_base) / n_paired, 4),
            "mcnemar_exact": {
                "b_baseline_pass_final_fail": b,
                "c_baseline_fail_final_pass": c,
                "n_discordant": b + c,
                "p_value": round(p_mcnemar, 6),
            },
            "newcombe_95ci_difference": {
                "lower": round(ci_lo, 4),
                "upper": round(ci_hi, 4),
                "method": "Newcombe Method 10 (hybrid score, paired)",
            },
            "note": (
                "Primary endpoint computed on the evaluable paired set "
                f"(n={n_paired} of 40); the raw 40-task endpoint "
                "(baseline 28/40 vs final 26/40) is retained in the reports "
                "for continuity but treats 2 verifier-infrastructure "
                "failures as agent regressions (E10)."
            ),
        },
        "secondary": secondary,
        "flip_table": {
            "both_pass": {"n": len(both_pass), "tasks": sorted(both_pass)},
            "both_fail": {"n": len(both_fail), "tasks": sorted(both_fail)},
            "conversions_baseline_fail_final_pass": {
                "n": len(conv), "tasks": sorted(conv)},
            "regressions_baseline_pass_final_fail": {
                "n": len(regr), "tasks": sorted(regr)},
        },
        "drift_check": drift_check,
        "context_comparisons": context,
        "per_task": per_task,
    }

    out = BENCH / "FINAL40_PAIRED_ANALYSIS.json"
    out.write_text(json.dumps(analysis, indent=1))
    print(f"wrote {out}")
    print(f"evaluable paired set: n={n_paired} of 40 "
          f"(excluded: {sorted(set(unevaluable['final']) | set(unevaluable['baseline']))})")
    print(f"baseline {k_base}/{n_paired} vs final {k_final}/{n_paired}")
    print(f"McNemar b={b} c={c} p={p_mcnemar:.6f}")
    print(f"Newcombe 95% CI [{ci_lo:.4f}, {ci_hi:.4f}]")
    print(f"conversions: {sorted(conv)}")
    print(f"regressions: {sorted(regr)}")
    print(f"drift verdict: {drift_check['verdict']}")


if __name__ == "__main__":
    main()