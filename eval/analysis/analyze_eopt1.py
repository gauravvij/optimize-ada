#!/usr/bin/env python3
"""E-opt1 (concision guidance) vs BASELINE ARM B — paired analysis + decision.

Applies the pre-registered rule from eval/config.json:
  ACCEPT iff (cost OR latency paired delta is significant at 95%)
           AND (pass-rate delta is within the noise band).

Noise band for pass rate = arm B's Wilson 95% CI [0.425, 0.669] around 0.550
(±0.126). Comparison is vs BASELINE ARM B only (arm A is the fixed reference).

Methodological notes (consistent with report_baseline.py):
- durations are trial wall-clock (started_at -> finished_at) for BOTH arms.
- arm B large-scale-text-editing has only 3 usable trials (1 AgentTimeoutError
  with no usage); its trial is counted as a fail in pass denominators and the
  task is EXCLUDED from paired usage cost/wall stats (flag, don't drop).
"""
import json
import math
import sys
from collections import defaultdict

from scipy import stats

ARM_B = "/root/optimize_ada/eval/results/baseline-armB.jsonl"
E_OPT1 = "/root/optimize_ada/eval/results/e-opt1-arm.jsonl"
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
    print(f"  E-opt1   : {ek}/{en} pass = {ek/en:.3f}  Wilson 95% CI [{eci[0]:.3f}, {eci[1]:.3f}]")
    print(f"  delta (E-opt1 - B) = {(ek/en)-(bk/bn):+.3f}")
    # pass-rate delta within noise band?
    in_noise = (ek/en) >= bci[0] - 1e-9 and (ek/en) <= bci[1] + 1e-9
    print(f"  pass-rate delta within arm-B noise band [{bci[0]:.3f}, {bci[1]:.3f}]? {'YES' if in_noise else 'NO'}")

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
    print(f"\nPAIRED DELTAS (E-opt1 - B, per-task means)")
    print(f"  cost delta  ({len(cost_d)} tasks; excluded {sorted(EXCLUDE_COST)}): "
          f"{cm:+.4f}  [{clo:+.4f}, {chi:+.4f}]  "
          f"{'SIGNIFICANT' if clo is not None and (clo > 0 or chi < 0) else 'not significant'}")
    print(f"  wall delta  ({len(wall_d)} tasks): "
          f"{wm:+.0f}ms  [{wlo:+.0f}, {whi:+.0f}]  "
          f"{'SIGNIFICANT' if wlo is not None and (wlo > 0 or whi < 0) else 'not significant'}")

    # ---- per-task solved discordants (McNemar exact on pass-count pairs) --
    disc = []
    for t in tasks:
        bs, es = b.get(t), e.get(t)
        if not bs or not es:
            continue
        bp = 1 if bs["pass"] > 0 else 0
        ep = 1 if es["pass"] > 0 else 0
        if bp != ep:
            disc.append((t, bp, ep))
    n_pn = sum(1 for _, bp, ep in disc if bp == 1 and ep == 0)  # B-only
    n_np = sum(1 for _, bp, ep in disc if bp == 0 and ep == 1)  # E-only
    if n_pn + n_np > 0:
        mcp = stats.binomtest(min(n_pn, n_np), n_pn + n_np, 0.5,
                              alternative="two-sided").pvalue
    else:
        mcp = 1.0
    print(f"\nPER-TASK SOLVED DISCORDANTS: {n_pn} B-only, {n_np} E-opt1-only "
          f"({[(t, 'B' if bp else '-', 'E' if ep else '-') for t, bp, ep in disc]})")
    print(f"  McNemar exact p = {mcp:.4f}")

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

    summary = {
        "arm_b": {"pass": bk, "n": bn, "rate": bk / bn,
                  "wilson": list(bci), "mean_cost": sum(
                      r.get("cost_usd") or 0 for r in b_rows) / bn},
        "e_opt1": {"pass": ek, "n": en, "rate": ek / en,
                   "wilson": list(eci), "mean_cost": sum(
                       r.get("cost_usd") or 0 for r in e_rows) / en},
        "paired": {"n_tasks": len(use_tasks),
                   "cost_delta": [cm, clo, chi],
                   "wall_delta_ms": [wm, wlo, whi],
                   "cost_significant": cost_sig,
                   "wall_significant": wall_sig},
        "mcnemar": {"n_b_only": n_pn, "n_e_only": n_np, "p": mcp},
        "pass_delta_in_noise": in_noise,
        "verdict": verdict,
        "per_task": {t: {"B": b.get(t), "E": e.get(t)} for t in tasks},
    }
    with open("/root/optimize_ada/eval/experiments/E-opt1/decision.json", "w") as f:
        json.dump(_native(summary), f, indent=2)
    print("\nWrote /root/optimize_ada/eval/experiments/E-opt1/decision.json")


if __name__ == "__main__":
    main()
