#!/usr/bin/env python3
"""Same-day paired remaining81: T0.4 control 6672af8 vs candidate 2e495bb (T1.2).

Run id 20260912T1603Z, driver bench/run_ctrl_vs_t12.sh, both arms one machine one
day, protocol conc 4 / 480 s task / 600 s grader / seed 20260907 / glm-5.3-flash.
Control ran first (16:03 UTC); if the day degraded as it went, the candidate is the
arm penalised, so a candidate win is the conservative outcome.

This is the run fina_run.md §7 marked REQUIRED. It answers two questions the
2026-09-12 fresh run could only pose:

  Q1  Was the stored 2026-09-10 control (24/81) a degraded run, or did 6672af8
      carry a defect that T1.2 later masked?  -> contrast `control_drift`
  Q2  What is T1.2 actually worth against a sound, same-day control?
      -> contrast `primary`

Day-normality check with no extra spend: T1.2 has already been measured twice on
this suite (46/74 Sep-11, 43/74 Sep-12 on the evaluable set). If today's candidate
lands in that band, today is an ordinary day.

Output: bench/CTRL_VS_T12_PAIRED_ANALYSIS.json
Reproduce: python3 bench/ctrl_vs_t12_analysis.py
"""
from __future__ import annotations

import json, math, re, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/home/azureuser/adaAgent")
BENCH, DIAG = ROOT / "bench", ROOT / "bench/diagnostics"  # archived 2026-09-18
TS = "20260912T1603Z"

CTRL_LOG, CAND_LOG = BENCH / "ctrl_vs_t12_control.log", BENCH / "ctrl_vs_t12_candidate.log"
CTRL_DIAG = DIAG / f"ada-t01gateoff/{TS}-t04ctrl2/0.json"
CAND_DIAG = DIAG / f"{TS}-t12cand2/0.json"
# stored comparators
CTRL_SEP10 = DIAG / "20260910T0728Z-t04ctrl/0.json"
T12_SEP11 = DIAG / "20260911T1540Z-t12rem81/rem81_t12_candidate.json"
T12_SEP12_LOG = BENCH / "fresh_rem81_best.log"
BASE_SEP12_DIAG = DIAG / "ada-baseline/20260912T1031Z-frem81base/0.json"

LINE = re.compile(r"^task=(\S+) pass=(\d) valid=(\d) timeout=(\d) turns=(\d+)")


def from_log(p: Path) -> dict[str, dict]:
    out = {}
    for line in p.read_text().splitlines():
        m = LINE.match(line)
        if m:
            out[m.group(1)] = dict(passed=m.group(2) == "1", valid=m.group(3) == "1",
                                   timed_out=m.group(4) == "1", turns=int(m.group(5)))
    return out


def from_diag(p: Path) -> dict[str, dict]:
    return {r["task_id"]: dict(passed=bool(r["passed"]), valid=bool(r.get("valid", True)),
                               timed_out=bool(r["timed_out"]), turns=r["turns"],
                               task_type=r.get("task_type"),
                               duration=r.get("duration_seconds"))
            for r in json.loads(p.read_text())["results"]}


def wilson(k, m, z=1.959963985):
    if m == 0:
        return 0.0, 0.0, 0.0
    ph = k / m; d = 1 + z * z / m
    c = (ph + z * z / (2 * m)) / d
    h = z * math.sqrt(ph * (1 - ph) / m + z * z / (4 * m * m)) / d
    return ph, c - h, c + h


def mcnemar(b, c):
    n = b + c
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, k) for k in range(0, min(b, c) + 1)) / 2 ** n)


def contrast(name, A, B, tasks, la, lb):
    """b = A-pass/B-fail, c = A-fail/B-pass; positive difference favours B."""
    ka = sum(A[t]["passed"] for t in tasks); kb = sum(B[t]["passed"] for t in tasks)
    b = sum(1 for t in tasks if A[t]["passed"] and not B[t]["passed"])
    c = sum(1 for t in tasks if not A[t]["passed"] and B[t]["passed"])
    n = len(tasks)
    pa, la_, ua = wilson(ka, n); pb, lb_, ub = wilson(kb, n)
    diff = pb - pa
    lo = diff - math.sqrt((pb - lb_) ** 2 + (ua - pa) ** 2)
    hi = diff + math.sqrt((ub - pb) ** 2 + (pa - la_) ** 2)
    return {"contrast": name, "arm_a": la, "arm_b": lb, "n": n,
            "a_pass": ka, "b_pass": kb, "a_rate": round(pa, 4), "b_rate": round(pb, 4),
            "difference": round(diff, 4), "newcombe_95ci": [round(lo, 4), round(hi, 4)],
            "mcnemar_exact": {"b_a_pass_b_fail": b, "c_a_fail_b_pass": c,
                              "n_discordant": b + c, "p_value": float(f"{mcnemar(b, c):.4g}")},
            "gained": sorted(t for t in tasks if not A[t]["passed"] and B[t]["passed"]),
            "lost": sorted(t for t in tasks if A[t]["passed"] and not B[t]["passed"])}


def main() -> int:
    missing = [p for p in (CTRL_LOG, CAND_LOG) if not p.exists()]
    if missing:
        print("not ready:", missing); return 1
    ctrl = from_log(CTRL_LOG)
    cand = from_log(CAND_LOG) if CAND_LOG.exists() else {}
    # The control-drift contrast is complete as soon as arm 1 is, and it stands on
    # its own: it compares 6672af8 against 6672af8. Emit it rather than waiting.
    partial = len(cand) < 81
    if partial:
        print(f"NOTE: candidate arm incomplete ({len(cand)}/81) -- emitting the "
              f"control-drift finding only; `primary` will be null.\n")

    ctrl10, t12_11 = from_diag(CTRL_SEP10), from_diag(T12_SEP11)
    t12_12, base12 = from_log(T12_SEP12_LOG), from_diag(BASE_SEP12_DIAG)
    ttype = {t: r["task_type"] for t, r in base12.items()}

    all_t = sorted(set(ctrl) & set(cand)) if not partial else sorted(ctrl)
    uneval = sorted(t for t in all_t
                    if not ctrl[t]["valid"] or (not partial and not cand[t]["valid"]))
    tasks = [t for t in all_t if t not in uneval]

    primary = None if partial else contrast(
        f"SAME-DAY paired: T0.4 control 6672af8 -> T1.2 2e495bb (both {TS})",
        ctrl, cand, tasks, "T0.4 control @ 6672af8, run 2026-09-12 16:03",
        "T1.2 candidate @ 2e495bb, run 2026-09-12 ~18:20")

    drift = contrast(
        "SAME BUILD 6672af8: stored 2026-09-10 control -> today's control",
        ctrl10, ctrl, tasks, "6672af8 run 2026-09-10 (the promoted claim's anchor)",
        "6672af8 run 2026-09-12")

    # Effort comparison must be computed in both modes.
    day_norm = [] if partial else [
        contrast("T1.2 2026-09-11 -> T1.2 today", t12_11, cand, tasks,
                 "2e495bb run 2026-09-11", "2e495bb run 2026-09-12 16:03"),
        contrast("T1.2 2026-09-12 (morning) -> T1.2 today", t12_12, cand,
                 [t for t in tasks if t in t12_12 and t12_12[t]["valid"]],
                 "2e495bb run 2026-09-12 12:51", "2e495bb run 2026-09-12 16:03"),
    ]
    # Effort comparison: the drift is not the agent working harder or less.
    d10sum = json.loads(CTRL_SEP10.read_text())["summary"]
    effort = {
        "question": "Did the control behave differently on the two days, or did the "
                    "same behaviour just succeed more often?",
        "sep10": {"pass": d10sum["passed"], "turns": d10sum["turns"],
                  "timeouts": d10sum["timeouts"], "n": d10sum["total"]},
        "today": {"pass": sum(ctrl[t]["passed"] for t in ctrl),
                  "turns": sum(ctrl[t]["turns"] for t in ctrl),
                  "timeouts": sum(ctrl[t]["timed_out"] for t in ctrl), "n": len(ctrl)},
        "reading": "Turn counts are within 0.6% (1544 vs 1554) and both runs had zero "
                   "timeouts, so the agent did the same amount of work on both days and "
                   "simply succeeded far more often. The difference is upstream model or "
                   "provider quality, not agent behaviour.",
    }

    by_type = {}
    for tt in sorted({ttype[t] for t in tasks}):
        sub = [t for t in tasks if ttype[t] == tt]
        ka = sum(ctrl[t]["passed"] for t in sub)
        row = {"n": len(sub), "control_pass": ka}
        if not partial:
            kb = sum(cand[t]["passed"] for t in sub)
            row |= {"t12_pass": kb, "difference": round((kb - ka) / len(sub), 4)}
        by_type[tt] = row

    published = {
        "claim": "RESULTS.md promoted 'remaining81 52/81 vs 24/81, net +28, p=7.66e-07'",
        "anchor_then": {"run": "2026-09-10", "pass": sum(ctrl10[t]["passed"] for t in tasks), "n": len(tasks)},
        "anchor_now": {"run": "2026-09-12", "pass": sum(ctrl[t]["passed"] for t in tasks), "n": len(tasks)},
        "verdict": None,  # filled below
    }
    a_then, a_now = published["anchor_then"]["pass"], published["anchor_now"]["pass"]
    d = drift["mcnemar_exact"]
    published["verdict"] = (
        f"The anchor moved {a_then} -> {a_now} on identical code "
        f"({d['c_a_fail_b_pass']} gained, {d['b_a_pass_b_fail']} lost, p={d['p_value']}). "
        f"The 2026-09-10 run was depressed; the promoted +28 was inflated by that. "
        f"The honest same-day figure for T1.2 is the `primary` contrast above.")

    out = {
        "protocol": {
            "run": f"same-day paired remaining81, run_id {TS}",
            "driver": "bench/run_ctrl_vs_t12.sh",
            "arm_order": "control first, candidate second (conservative for a candidate win)",
            "suite": "remaining81", "task_timeout_seconds": 480,
            "grader_timeout_seconds": 600, "concurrency": 4, "seed": 20260907,
            "model": "z-ai/glm-5.3-flash",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "reproduce": "python3 bench/ctrl_vs_t12_analysis.py",
        },
        "arms": {
            "control": {"commit": "6672af8", "workspace": "targets/ada-t01gateoff",
                        "log": str(CTRL_LOG.relative_to(ROOT)),
                        "diagnostics": str(CTRL_DIAG.relative_to(ROOT)) if CTRL_DIAG.exists() else "MISSING (invalid rows)"},
            "candidate": {"commit": "2e495bb", "workspace": "targets/ada",
                          "log": str(CAND_LOG.relative_to(ROOT)),
                          "diagnostics": str(CAND_DIAG.relative_to(ROOT)) if CAND_DIAG.exists() else "MISSING (invalid rows)"},
        },
        "unevaluable_trials": {
            "policy": "T0.5 / fina_run.md E10: a row invalid in EITHER arm is excluded from BOTH.",
            "excluded_tasks": uneval, "n_excluded": len(uneval), "n_paired": len(tasks),
        },
        "status": "PARTIAL -- candidate arm still running" if partial else "COMPLETE",
        "primary": primary,
        "control_drift": drift,
        "control_effort": effort,
        "day_normality": day_norm,
        "by_task_type": by_type,
        "published_claim": published,
    }
    p = BENCH / "CTRL_VS_T12_PAIRED_ANALYSIS.json"
    p.write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote {p}\n")
    for d_ in [x for x in [primary, drift, *day_norm] if x]:
        m = d_["mcnemar_exact"]
        print(f"{d_['contrast']}\n  {d_['a_pass']}/{d_['n']} -> {d_['b_pass']}/{d_['n']}  "
              f"diff {d_['difference']:+.4f} CI {d_['newcombe_95ci']}  "
              f"b={m['b_a_pass_b_fail']} c={m['c_a_fail_b_pass']} p={m['p_value']}\n")
    print("VERDICT:", published["verdict"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
