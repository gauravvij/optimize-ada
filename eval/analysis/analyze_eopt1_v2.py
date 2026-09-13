#!/usr/bin/env python3
"""E-opt1 v2 (concision guidance, TREATED re-test) vs BASELINE ARM B —
paired analysis + decision.

WHY v2 EXISTS: the original E-opt1 arm (eval/results/e-opt1-arm.jsonl, job
e-opt1-arm) ran via the kwargs-swallowing adapter defect (harbor BaseAgent
dropped --ak kwargs), so ADA_CONCISION_GUIDANCE never reached the bridge and
the "treated" run was actually an untreated baseline re-run (0 treatment
markers). The adapter now has an explicit AdaBridgeAgent.__init__ binding
concision_guidance -> ADA_CONCISION_GUIDANCE=1 (verified zero-cost via
importlib test + in-container probe e-opt1-probe-v2: 2/2 bridge logs carried
the guidance marker). This script analyzes the valid treated arm
eval/results/e-opt1-arm-v2.jsonl (job e-opt1-arm-v2) against the SAME
pre-registered rule from eval/experiments/E-opt1/README.md:
  ACCEPT iff (cost OR latency paired delta is significant at 95%)
           AND (pass-rate delta is within the noise band).

Noise band for pass rate = arm B's Wilson 95% CI [0.425, 0.669] around 0.550
(+-0.126). Comparison is vs BASELINE ARM B only (arm A is the fixed reference).

Methodological notes (consistent with report_baseline.py):
- durations are trial wall-clock (started_at -> finished_at) for BOTH arms.
- arm B large-scale-text-editing has only 3 usable trials (1 AgentTimeoutError
  with no usage); its trial is counted as a fail in pass denominators and the
  task is EXCLUDED from paired usage cost/wall stats (flag, don't drop).
- McNemar uses POSITION-BASED pairing WITHIN task: the 'trial' field in the
  JSONL is NOT comparable across arms (suffix shortuuids differ per run), so
  each task's 4 trials are paired by position of appearance (sort by
  started_at within task; pair B position i with V2 position i) -> 60 pairs.
  (The per-task "task-level solved" McNemar over ~15 units is reported as a
  secondary reference only; the primary test is position-based.)
"""
import json
import math
from collections import defaultdict

from scipy import stats

ARM_B = "/root/optimize_ada/eval/results/baseline-armB.jsonl"
E_OPT1 = "/root/optimize_ada/eval/results/e-opt1-arm-v2.jsonl"
OUT = "/root/optimize_ada/eval/experiments/E-opt1/decision-v2.json"
# Cost pairing: arm B large-scale-text-editing has only 3 usable costs (one
# AgentTimeoutError trial with no usage) -> exclude from COST pairing only.
# Wall pairing: duration_ms is driver-measured (started_at->finished_at) and
# exists for ALL trials in both arms -> include all 15 tasks.
EXCLUDE_COST = {"large-scale-text-editing"}
EXCLUDE_WALL: set[str] = set()


def load(path):
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def wilson_ci(k, n, z=1.96):
    """Wilson score interval for a proportion."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (centre - half, centre + half)


def mean_ci(xs, z=1.96):
    """t-based 95% CI of the mean; returns (mean, lo, hi)."""
    n = len(xs)
    if n == 0:
        return (None, None, None)
    mean = sum(xs) / n
    if n == 1:
        return (mean, mean, mean)
    se = stats.sem(xs)
    h = stats.t.ppf(0.975, n - 1) * se
    return (mean, mean - h, mean + h)


def per_task_stats(rows):
    d = defaultdict(list)
    for r in rows:
        d[r["task"]].append(r)
    out = {}
    for t, rs in d.items():
        passes = sum(1 for r in rs if r.get("pass"))
        costs = [r["cost_usd"] for r in rs if r.get("cost_usd") is not None]
        walls = [r.get("duration_ms") for r in rs if r.get("duration_ms") is not None]
        if not walls:  # fall back to trial wall-clock field if present
            walls = [r.get("wall_ms") for r in rs if r.get("wall_ms") is not None]
        out[t] = {
            "n": len(rs),
            "pass": passes,
            "mean_cost": sum(costs) / len(costs) if costs else None,
            "cost_n": len(costs),
            "mean_wall": sum(walls) / len(walls) if walls else None,
            "wall_n": len(walls),
        }
    return out


def position_pair_within_task(a_rows, b_rows):
    """Pair trials POSITIONALLY within task: sort each arm's trials for a task
    by started_at and pair index i of arm A with index i of arm B. The 'trial'
    field is NOT comparable across arms (shortuuid suffixes differ per run).

    Returns list of (task, a_pass, b_pass, a_cost, b_cost, a_wall, b_wall)."""
    by_task_a = defaultdict(list)
    by_task_b = defaultdict(list)
    for r in a_rows:
        by_task_a[r["task"]].append(r)
    for r in b_rows:
        by_task_b[r["task"]].append(r)
    for d in (by_task_a, by_task_b):
        for t in d:
            d[t].sort(key=lambda r: r.get("started_at") or "")
    pairs = []
    for t in sorted(set(by_task_a) & set(by_task_b)):
        la, lb = by_task_a[t], by_task_b[t]
        for i in range(max(len(la), len(lb))):
            ra = la[i] if i < len(la) else None
            rb = lb[i] if i < len(lb) else None
            if ra is None or rb is None:
                continue
            pairs.append((t,
                          1 if ra.get("pass") else 0,
                          1 if rb.get("pass") else 0,
                          ra.get("cost_usd"), rb.get("cost_usd"),
                          ra.get("duration_ms"), rb.get("duration_ms")))
    return pairs


def main():
    b_rows = load(ARM_B)
    e_rows = load(E_OPT1)
    b = per_task_stats(b_rows)
    e = per_task_stats(e_rows)
    tasks = sorted(set(b) | set(e))

    # ---- aggregate pass rate + Wilson CIs -------------------------------
    def agg(rows):
        n = len(rows)
        k = sum(1 for r in rows if r.get("pass"))
        return k, n, wilson_ci(k, n)

    bk, bn, bci = agg(b_rows)
    ek, en, eci = agg(e_rows)
    print("AGGREGATE")
    print(f"  arm B    : {bk}/{bn} pass = {bk/bn:.3f}  Wilson 95% CI [{bci[0]:.3f}, {bci[1]:.3f}]")
    print(f"  E-opt1v2 : {ek}/{en} pass = {ek/en:.3f}  Wilson 95% CI [{eci[0]:.3f}, {eci[1]:.3f}]")
    print(f"  delta (E-opt1v2 - B) = {(ek/en)-(bk/bn):+.3f}")
    # pass-rate delta within noise band?
    in_noise = (ek/en) >= bci[0] - 1e-9 and (ek/en) <= bci[1] + 1e-9
    print(f"  pass-rate delta within arm-B noise band [{bci[0]:.3f}, {bci[1]:.3f}]? {'YES' if in_noise else 'NO'}")
    print(f"  candidate rate >= arm-B Wilson lower bound {bci[0]:.4f}? {'YES' if ek/en >= bci[0] else 'NO'}")

    # ---- per-task table ------------------------------------------------
    print("\nPER-TASK (pass counts k/n; mean cost $; mean wall s)")
    print(f"{'task':<28}{'B pass':>10}{'E pass':>10}{'B $':>10}{'E $':>10}{'B wall s':>10}{'E wall s':>10}")
    for t in tasks:
        bs, es = b.get(t), e.get(t)
        if not bs or not es:
            print(f"{t:<28} MISSING in one arm!")
            continue
        wl = lambda s: f"{s/1000:.0f}" if s is not None else "—"
        cf = lambda x: f"{x:.4f}" if x is not None else "—"
        print(f"{t:<28}{bs['pass']}/{bs['n']:<3}{es['pass']}/{es['n']:<3}"
              f"{cf(bs['mean_cost']):>10}{cf(es['mean_cost']):>10}"
              f"{wl(bs['mean_wall']):>10}{wl(es['mean_wall']):>10}")

    # ---- paired usage deltas (exclude task flagged) ----------------------
    use_tasks = [t for t in tasks if t not in EXCLUDE_COST and b.get(t) and e.get(t)]
    cost_d = []
    for t in use_tasks:
        bs, es = b[t], e[t]
        if bs["mean_cost"] is not None and es["mean_cost"] is not None:
            cost_d.append(es["mean_cost"] - bs["mean_cost"])  # E-opt1 minus B
    cm, clo, chi = mean_ci(cost_d)

    # ---- paired wall deltas (all 15 tasks; driver-measured for both arms) -
    wall_tasks = [t for t in tasks if t not in EXCLUDE_WALL and b.get(t) and e.get(t)]
    wall_d = []
    for t in wall_tasks:
        bs, es = b[t], e[t]
        if bs["mean_wall"] is not None and es["mean_wall"] is not None:
            wall_d.append(es["mean_wall"] - bs["mean_wall"])
    wm, wlo, whi = mean_ci(wall_d)
    print(f"\nPAIRED DELTAS (E-opt1 v2 - B, per-task means)")
    print(f"  cost delta  ({len(cost_d)} tasks; excluded {sorted(EXCLUDE_COST)}): "
          f"{cm:+.4f}  [{clo:+.4f}, {chi:+.4f}]  "
          f"{'SIGNIFICANT' if clo is not None and (clo > 0 or chi < 0) else 'not significant'}")
    print(f"  wall delta  ({len(wall_d)} tasks): "
          f"{wm:+.0f}ms  [{wlo:+.0f}, {whi:+.0f}]  "
          f"{'SIGNIFICANT' if wlo is not None and (wlo > 0 or whi < 0) else 'not significant'}")

    # ---- POSITION-BASED WITHIN-TASK trial McNemar (60 pairs) -------------
    # 'trial' field is NOT comparable across arms -> pair B position i with
    # V2 position i per task (order of appearance by started_at).
    pos_pairs = position_pair_within_task(b_rows, e_rows)
    n_b_only = sum(1 for _, pb, pe, *_ in pos_pairs if pb == 1 and pe == 0)
    n_v_only = sum(1 for _, pb, pe, *_ in pos_pairs if pb == 0 and pe == 1)
    n_both = sum(1 for _, pb, pe, *_ in pos_pairs if pb == 1 and pe == 1)
    n_neither = sum(1 for _, pb, pe, *_ in pos_pairs if pb == 0 and pe == 0)
    n_pairs = len(pos_pairs)
    if n_b_only + n_v_only > 0:
        mcp = stats.binomtest(min(n_b_only, n_v_only), n_b_only + n_v_only,
                              0.5, alternative="two-sided").pvalue
    else:
        mcp = 1.0
    discord = [(t, "B" if pb == 1 and pe == 0 else "", "V2" if pb == 0 and pe == 1 else "")
               for t, pb, pe, *_ in pos_pairs if pb != pe]
    print(f"\nPOSITION-BASED WITHIN-TASK McNEMAR ({n_pairs} paired positions)")
    print(f"  both pass {n_both}, both fail {n_neither}, "
          f"B-only regress {n_b_only}, V2-only improve {n_v_only}")
    print(f"  discordants: {discord}")
    print(f"  McNemar exact p = {mcp:.4f}")

    # ---- per-task solved discordants (secondary; pass>0 per task) --------
    disc = []
    for t in tasks:
        bs, es = b.get(t), e.get(t)
        if not bs or not es:
            continue
        bp = 1 if bs["pass"] > 0 else 0
        ep = 1 if es["pass"] > 0 else 0
        if bp != ep:
            disc.append((t, bp, ep))
    tn_pn = sum(1 for _, bp, ep in disc if bp == 1 and ep == 0)  # B-only
    tn_np = sum(1 for _, bp, ep in disc if bp == 0 and ep == 1)  # V2-only
    if tn_pn + tn_np > 0:
        tmcp = stats.binomtest(min(tn_pn, tn_np), tn_pn + tn_np, 0.5,
                               alternative="two-sided").pvalue
    else:
        tmcp = 1.0
    print(f"\nTASK-LEVEL SOLVED DISCORDANTS (per-task pass>0): {tn_pn} B-only, {tn_np} V2-only "
          f"({[(t, 'B' if bp else '-', 'V2' if ep else '-') for t, bp, ep in disc]})")
    print(f"  McNemar exact p = {tmcp:.4f}")

    # ---- decision rule --------------------------------------------------
    cost_sig = (clo is not None) and (clo > 0 or chi < 0)
    wall_sig = (wlo is not None) and (wlo > 0 or whi < 0)
    print("\nDECISION (pre-registered rule)")
    print(f"  cost significant at 95%?  {'YES' if cost_sig else 'no'}")
    print(f"  wall significant at 95%?  {'YES' if wall_sig else 'no'}")
    print(f"  pass-rate delta in noise band?  {'YES' if in_noise else 'NO'}")
    if (cost_sig or wall_sig) and in_noise:
        verdict = "ACCEPT"
        print(f"  VERDICT: {verdict} — E-opt1 concision guidance adopted.")
    else:
        verdict = "REJECT"
        reason = []
        if not (cost_sig or wall_sig):
            reason.append("no significant cost/latency delta")
        if not in_noise:
            reason.append("pass-rate delta outside noise band")
        print(f"  VERDICT: {verdict} — {'; '.join(reason)}.")

    # ---- persist structured summary --------------------------------------
    def _native(o):
        """Coerce numpy/scipy scalars to native Python for JSON serialization."""
        if isinstance(o, dict):
            return {k: _native(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [_native(v) for v in o]
        if hasattr(o, "item"):  # numpy scalars (float64, bool_, int64, ...)
            return o.item()
        return o

    spend = sum(r.get("cost_usd") or 0 for r in e_rows)
    spend_n = sum(1 for r in e_rows if r.get("cost_usd") is not None)
    print(f"\nACTUAL SPEND: ${spend:.4f} over {spend_n} cost records")

    # position-based per-position cost delta (supplementary, trial level)
    pos_cost_d = []
    for _, _, _, ca, cb, _, _ in pos_pairs:
        if ca is not None and cb is not None:
            pos_cost_d.append(cb - ca)
    pcm, pclo, pchi = mean_ci(pos_cost_d)

    reason = []
    if not (cost_sig or wall_sig):
        reason.append("no significant cost/latency delta")
    if not in_noise:
        reason.append("pass-rate delta outside noise band")
    reason_str = "; ".join(reason) if reason else "criteria met"

    summary = {
        "arm": "e-opt1-v2",
        "job": "e-opt1-arm-v2",
        "results_file": "eval/results/e-opt1-arm-v2.jsonl",
        "baseline": "eval/results/baseline-armB.jsonl",
        "invalidated_original": {
            "job": "e-opt1-arm",
            "results_file": "eval/results/e-opt1-arm.jsonl",
            "reason": "ran via kwargs-swallowing adapter defect (BaseAgent.__init__ dropped --ak concision_guidance); ADA_CONCISION_GUIDANCE never reached the bridge => untreated baseline re-run; superseded by this v2 treated arm"
        },
        "model": "anthropic/claude-haiku-4-5",
        "dataset": "terminal-bench@2.0",
        "n_tasks": len(tasks),
        "k": 4,
        "n_trials": 60,
        "arm_b": {"pass": bk, "n": bn, "rate": bk / bn,
                  "wilson": list(bci), "mean_cost": sum(
                      r.get("cost_usd") or 0 for r in b_rows) / bn},
        "e_opt1_v2": {"pass": ek, "n": en, "rate": ek / en,
                      "wilson": list(eci), "mean_cost": sum(
                          r.get("cost_usd") or 0 for r in e_rows) / en,
                      "total_cost_usd": spend, "cost_n": spend_n},
        "paired": {"n_tasks": len(use_tasks),
                   "cost_delta": [cm, clo, chi],
                   "wall_delta_ms": [wm, wlo, whi],
                   "cost_significant": cost_sig,
                   "wall_significant": wall_sig},
        "mcnemar_position_within_task": {
            "n_pairs": n_pairs,
            "n_both_pass": n_both,
            "n_neither_pass": n_neither,
            "n_regressed_b_only": n_b_only,
            "n_improved_v2_only": n_v_only,
            "p": mcp,
            "pairing_note": "B position i paired with V2 position i per task "
                            "(order of appearance by started_at); 'trial' "
                            "field is NOT comparable across arms"
        },
        "mcnemar_task_level_solved": {
            "n_b_only": tn_pn, "n_v2_only": tn_np, "p": tmcp,
            "note": "secondary reference; primary test is position-based"
        },
        "position_cost_delta": {"n_pairs": len(pos_cost_d),
                                "mean": pcm, "ci95": [pclo, pchi]},
        "pass_delta_in_noise": in_noise,
        "pass_rate_ge_wilson_lb": (ek / en) >= bci[0],
        "wilson_lb_arm_b": bci[0],
        "verdict": verdict,
        "verdict_reason": (
            "Pre-registered rule: ACCEPT iff (cost OR wall paired delta "
            "significant at 95%) AND pass-rate delta within arm-B noise band. "
            f"cost_sig={cost_sig}; wall_sig={wall_sig}; "
            f"pass_in_noise={in_noise}. "
            f"VERDICT {verdict}: {reason_str}."
        ),
        "per_task": {t: {"B": b.get(t), "E": e.get(t)} for t in tasks},
    }
    with open(OUT, "w") as f:
        json.dump(_native(summary), f, indent=2)
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
