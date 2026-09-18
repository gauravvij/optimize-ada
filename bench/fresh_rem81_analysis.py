#!/usr/bin/env python3
"""Fresh same-day paired remaining81 run of 2026-09-12 (run_id 20260912T1031Z).

Arms actually run (driver: run_rem81.sh, both arms same machine, same day,
protocol conc 4 / 480 s task / 600 s grader / seed 20260907 / z-ai/glm-5.3-flash):

  arm 1  df0c537  targets/ada-baseline  -> bench/fresh_rem81_baseline.log  (+ diagnostics)
  arm 2  2e495bb  targets/ada  (T1.2)   -> bench/fresh_rem81_best.log      (log only)

Arm 2 wrote NO diagnostics JSON: 7 of 81 rows came back valid=0 (docker infra
timeouts), and setupbench_ada_domain_eval.py:257 returns 2 without writing the
report when any row is invalid. Arm 2's per-task data therefore comes from its
stdout log, which carries pass/valid/timeout/turns but NOT duration_seconds,
terminal_result or agent_stop_reason. Every metric below is restricted to what
both arms can support.

Unevaluable policy (adopted from T0.5 / fina_run.md E10, as used by
FINAL40_PAIRED_ANALYSIS.json): a task whose row is valid=0 in EITHER arm is a
harness-infrastructure failure, not an agent failure, and is excluded from the
paired set in BOTH arms. 7 excluded -> n = 74.

Stored comparators, same suite and protocol, re-restricted to the same 74:
  T1.2 @ 2e495bb run 2026-09-11  (the run behind the promoted 52/81 claim)
  T0.4 control @ 6672af8 run 2026-09-10  (the control behind that claim)

Output: bench/FRESH_REM81_PAIRED_ANALYSIS.json
Reproduce: python3 bench/fresh_rem81_analysis.py
"""
from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/home/azureuser/adaAgent")
BENCH = ROOT / "bench"
DIAG = ROOT / "bench/diagnostics"  # archived 2026-09-18 from the former autoresearcher workspaces

FRESH_BASE_LOG = BENCH / "fresh_rem81_baseline.log"
FRESH_BEST_LOG = BENCH / "fresh_rem81_best.log"
FRESH_BASE_DIAG = DIAG / "ada-baseline/20260912T1031Z-frem81base/0.json"
STORED_T12_DIAG = DIAG / "20260911T1540Z-t12rem81/rem81_t12_candidate.json"
STORED_CTRL_DIAG = DIAG / "20260910T0728Z-t04ctrl/0.json"

LINE = re.compile(r"^task=(\S+) pass=(\d) valid=(\d) timeout=(\d) turns=(\d+)")


def from_log(path: Path) -> dict[str, dict]:
    rows = {}
    for line in path.read_text().splitlines():
        m = LINE.match(line)
        if m:
            rows[m.group(1)] = {
                "passed": bool(int(m.group(2))), "valid": bool(int(m.group(3))),
                "timed_out": bool(int(m.group(4))), "turns": int(m.group(5)),
            }
    return rows


def from_diag(path: Path) -> dict[str, dict]:
    return {r["task_id"]: r for r in json.loads(path.read_text())["results"]}


def wilson(k: int, m: int, z: float = 1.959963985) -> tuple[float, float, float]:
    if m == 0:
        return (0.0, 0.0, 0.0)
    phat = k / m
    denom = 1 + z * z / m
    centre = (phat + z * z / (2 * m)) / denom
    half = z * math.sqrt(phat * (1 - phat) / m + z * z / (4 * m * m)) / denom
    return (phat, centre - half, centre + half)


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact binomial on the discordant pairs. b and c are the two
    discordant counts; returns 1.0 when there are no discordant pairs."""
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(0, min(b, c) + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def contrast(name: str, a_rows: dict, b_rows: dict, tasks: list[str],
             a_label: str, b_label: str) -> dict:
    """Paired contrast, arm A vs arm B, over `tasks`. b = A-pass/B-fail,
    c = A-fail/B-pass, so positive difference favours B."""
    ka = sum(a_rows[t]["passed"] for t in tasks)
    kb = sum(b_rows[t]["passed"] for t in tasks)
    n = len(tasks)
    b = sum(1 for t in tasks if a_rows[t]["passed"] and not b_rows[t]["passed"])
    c = sum(1 for t in tasks if not a_rows[t]["passed"] and b_rows[t]["passed"])
    pa, la, ua = wilson(ka, n)
    pb, lb, ub = wilson(kb, n)
    diff = pb - pa
    # Newcombe Method 10 (hybrid score) on the paired difference.
    lo = diff - math.sqrt((pb - lb) ** 2 + (ua - pa) ** 2)
    hi = diff + math.sqrt((ub - pb) ** 2 + (pa - la) ** 2)
    return {
        "contrast": name,
        "arm_a": a_label, "arm_b": b_label,
        "n": n,
        "a_pass": ka, "b_pass": kb,
        "a_rate": round(pa, 4), "b_rate": round(pb, 4),
        "difference": round(diff, 4),
        "newcombe_95ci": [round(lo, 4), round(hi, 4)],
        "mcnemar_exact": {
            "b_a_pass_b_fail": b, "c_a_fail_b_pass": c,
            "n_discordant": b + c, "p_value": float(f"{mcnemar_exact(b, c):.4g}"),
        },
        "gained": sorted(t for t in tasks if not a_rows[t]["passed"] and b_rows[t]["passed"]),
        "lost": sorted(t for t in tasks if a_rows[t]["passed"] and not b_rows[t]["passed"]),
    }


def main() -> int:
    fresh_base = from_log(FRESH_BASE_LOG)
    fresh_best = from_log(FRESH_BEST_LOG)
    base_diag = from_diag(FRESH_BASE_DIAG)
    t12_sep11 = from_diag(STORED_T12_DIAG)
    ctrl_sep10 = from_diag(STORED_CTRL_DIAG)

    all_tasks = sorted(set(fresh_base) & set(fresh_best))
    unevaluable = {
        t: {
            "baseline_valid": fresh_base[t]["valid"],
            "t12_valid": fresh_best[t]["valid"],
        }
        for t in all_tasks
        if not fresh_base[t]["valid"] or not fresh_best[t]["valid"]
    }
    tasks = [t for t in all_tasks if t not in unevaluable]

    task_type = {t: base_diag[t]["task_type"] for t in tasks}

    primary = contrast(
        "fresh df0c537 -> fresh T1.2 (both 2026-09-12, same machine, same day)",
        fresh_base, fresh_best, tasks,
        "df0c537 campaign-origin baseline", "2e495bb T1.2 time-awareness bundle")

    repro = contrast(
        "T1.2 2026-09-11 -> T1.2 2026-09-12 (same build 2e495bb, same protocol, 1 day apart)",
        t12_sep11, fresh_best, tasks,
        "T1.2 @ 2e495bb run 2026-09-11", "T1.2 @ 2e495bb run 2026-09-12")

    published = contrast(
        "T0.4 control 6672af8 -> T1.2 2026-09-11, restricted to the same 74 tasks",
        ctrl_sep10, t12_sep11, tasks,
        "T0.4 control @ 6672af8 run 2026-09-10", "T1.2 @ 2e495bb run 2026-09-11")

    # Per-task-type decomposition of the primary contrast.
    by_type = {}
    for tt in sorted(set(task_type.values())):
        sub = [t for t in tasks if task_type[t] == tt]
        kb_ = sum(fresh_base[t]["passed"] for t in sub)
        kc_ = sum(fresh_best[t]["passed"] for t in sub)
        _, lb_, ub_ = wilson(kb_, len(sub))
        _, lc_, uc_ = wilson(kc_, len(sub))
        by_type[tt] = {
            "n": len(sub),
            "baseline_pass": kb_, "baseline_rate": round(kb_ / len(sub), 4),
            "baseline_wilson95": [round(lb_, 4), round(ub_, 4)],
            "t12_pass": kc_, "t12_rate": round(kc_ / len(sub), 4),
            "t12_wilson95": [round(lc_, 4), round(uc_, 4)],
            "difference": round((kc_ - kb_) / len(sub), 4),
        }

    # The decisive split: 41 of the 74 baseline rows are zero-turn hangs. Contrast
    # the two arms on the subset the baseline actually got to run, where no
    # watchdog difference can be in play.
    ran = [t for t in tasks if not fresh_base[t]["timed_out"]]
    hung = [t for t in tasks if fresh_base[t]["timed_out"]]
    on_ran = contrast(
        "fresh df0c537 -> fresh T1.2, restricted to tasks the baseline actually ran "
        "(no zero-turn hang)",
        fresh_base, fresh_best, ran,
        "df0c537 campaign-origin baseline", "2e495bb T1.2 time-awareness bundle")
    on_hung = contrast(
        "fresh df0c537 -> fresh T1.2, restricted to tasks where the baseline hung "
        "with zero turns",
        fresh_base, fresh_best, hung,
        "df0c537 campaign-origin baseline", "2e495bb T1.2 time-awareness bundle")

    # Mechanism: the baseline arm's failure mode is the zero-turn hang.
    base_to = [t for t in tasks if fresh_base[t]["timed_out"]]
    mechanism = {
        "question": "Is the primary difference the T1.2 time hints, or the hard "
                    "deadline and watchdog that df0c537 predates (08a8d5d)?",
        "baseline_timeouts_in_paired_set": len(base_to),
        "baseline_timeouts_with_zero_turns": sum(
            1 for t in base_to if fresh_base[t]["turns"] == 0),
        "t12_timeouts_in_paired_set": sum(1 for t in tasks if fresh_best[t]["timed_out"]),
        "conversions_that_were_baseline_timeouts": sum(
            1 for t in primary["gained"] if fresh_base[t]["timed_out"]),
        "conversions_total": len(primary["gained"]),
        "baseline_turns_total": sum(fresh_base[t]["turns"] for t in tasks),
        "t12_turns_total": sum(fresh_best[t]["turns"] for t in tasks),
        "note": "df0c537 predates 08a8d5d (container-anchored hard deadline + "
                "stall-retry watchdog). A zero-turn 480 s timeout is that build "
                "hanging with no deadline to cut it off, so any conversion out of "
                "a baseline timeout is attributable to 08a8d5d and NOT to T1.2.",
    }

    # Control integrity: 6672af8 (the T0.4 anchor behind the promoted claim) is a
    # strict SUPERSET of df0c537 -- it is df0c537 plus the watchdog work. On tasks
    # where neither build hangs it should therefore be >= df0c537. Test that.
    ctrl_vs_base_ran = contrast(
        "T0.4 control 6672af8 (Sep-10) -> df0c537 (Sep-12), on the 33 tasks df0c537 ran",
        ctrl_sep10, fresh_base, ran,
        "T0.4 control @ 6672af8, run 2026-09-10", "df0c537 campaign-origin baseline, run 2026-09-12")
    control_integrity = {
        "question": "Is the 24/81 T0.4 control a sound anchor, or is it a depressed run?",
        "test": "6672af8 is df0c537 plus the watchdog work, so on tasks where neither "
                "build hangs it cannot legitimately be far WORSE than df0c537.",
        "on_33_tasks_df0c537_ran": {
            "ctrl_6672af8_sep10_pass": sum(bool(ctrl_sep10[t]["passed"]) for t in ran),
            "df0c537_sep12_pass": sum(fresh_base[t]["passed"] for t in ran),
            "t12_sep12_pass": sum(fresh_best[t]["passed"] for t in ran),
            "n": len(ran),
        },
        "contrast": ctrl_vs_base_ran,
        "control_timeouts_on_paired_set": sum(
            1 for t in tasks if ctrl_sep10[t]["timed_out"]),
        "verdict": "CONTROL IS SUSPECT. The control loses 18 of these 33 tasks to a "
                   "strictly older build and wins none (b=0, c=18, p=7.6e-06), with 0 "
                   "timeouts on either side, so the deficit is grader failures and not "
                   "hangs. A build cannot be beaten 18-0 by its own ancestor on tasks "
                   "neither one hangs on. Either the 2026-09-10 run was executed on a "
                   "badly degraded day, or 6672af8 carried a defect T1.2 later masked. "
                   "fina_run.md already flagged this run as anomalous (24/81 against the "
                   "Sep-9 incumbent's 50/81 on nearly the same lineage) and attributed it "
                   "to drift, then used it as the anchor anyway.",
        "consequence": "The promoted '52/81 vs 24/81, +28 conversions' is measured against "
                       "this anchor. Its DIRECTION is probably real but its MAGNITUDE is "
                       "inflated by a depressed control, and the size of the inflation is "
                       "not estimable from any run on disk.",
    }

    analysis = {
        "protocol": {
            "run": "fresh same-day paired remaining81, run_id 20260912T1031Z",
            "driver": "run_rem81.sh (arm 1 10:31-12:51 UTC, arm 2 12:51-14:59 UTC)",
            "suite": "remaining81",
            "task_timeout_seconds": 480,
            "grader_timeout_seconds": 600,
            "concurrency": 4,
            "seed": 20260907,
            "model": "z-ai/glm-5.3-flash",
            "metric": "tasks passing the official SetupBench executable graders",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "reproduce": "python3 bench/fresh_rem81_analysis.py",
        },
        "arms": {
            "fresh_baseline": {
                "commit": "df0c537", "workspace": "targets/ada-baseline",
                "log": "bench/fresh_rem81_baseline.log",
                "diagnostics": str(FRESH_BASE_DIAG.relative_to(ROOT)),
                "raw": "34/81 pass, 45 timeouts, 750 turns, 0 invalid",
            },
            "fresh_t12": {
                "commit": "2e495bb", "workspace": "targets/ada",
                "log": "bench/fresh_rem81_best.log",
                "diagnostics": "NONE — eval returned 2 on 7 invalid rows before writing",
                "raw": "81 rows, 7 invalid, 43/74 pass on the evaluable set, 0 timeouts",
            },
        },
        "unevaluable_trials": {
            "policy": "T0.5 / fina_run.md E10: a row that is valid=0 in EITHER arm is a "
                      "harness-infrastructure failure, not an agent failure, and is "
                      "excluded from the paired set in BOTH arms.",
            "cause": "docker exec timed out after 10 s (x3) and docker run timed out "
                     "after 60 s (x4) during arm 2, at peak memory pressure "
                     "(min avail 1917 MB, swap 2557 MB at 14:19 UTC; the run guard's "
                     "abort floor is 1200 MB and never tripped)",
            "excluded_tasks": sorted(unevaluable),
            "n_excluded": len(unevaluable),
            "n_paired": len(tasks),
            "asymmetry_note": "all 7 were invalid in arm 2 only; arm 1 had 0 invalid rows. "
                              "The exclusion is applied to both arms regardless.",
        },
        "control_integrity": control_integrity,
        "primary": primary,
        "primary_split_baseline_ran": on_ran,
        "primary_split_baseline_hung": on_hung,
        "reproducibility": repro,
        "published_claim_restricted": published,
        "by_task_type": by_type,
        "mechanism": mechanism,
        "limitations": [
            "Arm 2 has no diagnostics JSON, so duration_seconds, terminal_result, "
            "agent_stop_reason and grader_returncode are unavailable for it. Wall-clock "
            "and claimed-verified-but-failed metrics reported for previous rungs cannot "
            "be computed for this run.",
            "The primary contrast pairs T1.2 against df0c537, which is NOT the control "
            "behind the promoted 52/81 claim (that control is 6672af8). df0c537 predates "
            "the watchdog, so the primary contrast confounds T1.2 with 08a8d5d.",
            "n=74 of 81; the 7 excluded tasks were not re-run.",
            "published_claim_restricted shows the promoted comparison is statistically "
            "robust ON ITS OWN ANCHOR, but control_integrity shows that anchor is itself "
            "suspect, so that contrast is NOT a validation of the promoted effect size.",
        ],
        "per_task": [
            {
                "task_id": t,
                "task_type": task_type[t],
                "fresh_baseline_pass": fresh_base[t]["passed"],
                "fresh_baseline_timeout": fresh_base[t]["timed_out"],
                "fresh_baseline_turns": fresh_base[t]["turns"],
                "fresh_t12_pass": fresh_best[t]["passed"],
                "fresh_t12_turns": fresh_best[t]["turns"],
                "t12_sep11_pass": bool(t12_sep11[t]["passed"]),
                "ctrl_sep10_pass": bool(ctrl_sep10[t]["passed"]),
            }
            for t in tasks
        ],
    }

    out = BENCH / "FRESH_REM81_PAIRED_ANALYSIS.json"
    out.write_text(json.dumps(analysis, indent=2) + "\n")
    print(f"wrote {out}")
    print("\nCONTROL INTEGRITY:", control_integrity["verdict"].split(".")[0])
    for key in ("primary", "primary_split_baseline_ran", "primary_split_baseline_hung",
                "reproducibility", "published_claim_restricted"):
        d = analysis[key]
        m = d["mcnemar_exact"]
        print(f"\n{d['contrast']}\n  {d['a_pass']}/{d['n']} -> {d['b_pass']}/{d['n']}  "
              f"diff {d['difference']:+.4f} CI {d['newcombe_95ci']}  "
              f"b={m['b_a_pass_b_fail']} c={m['c_a_fail_b_pass']} p={m['p_value']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
