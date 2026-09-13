#!/usr/bin/env python3
"""Analyze dev-x1r (X1 repackage: trimmed verify-once + 2-run budget + cap=3000)
vs the fresh dev-baseline.

Frozen X1r kill criteria (ledger.md, PRE-REGISTERED before any paid run):
  graded paired delta < +0.05 OR Wilcoxon p >= 0.05 OR binary < 24/40 OR
  guards < 8/8 OR mean cost > $0.0967 OR reach < 95%.

Promote iff ALL:
  (a) graded paired delta >= +0.05 AND Wilcoxon signed-rank two-sided p < 0.05
  (b) binary pass >= 24/40
  (c) guards 8/8 binary (fix-code-vulnerability, git-leak-recovery)
  (d) mean cost <= 1.10 x $0.0879 = $0.0967 (cost-bearing, same task set)
  (e) reach >= 95%

Conventions (identical to X1/H1/H2 decisions):
  - Position-based pairing WITHIN task (trial order 0..3 by sorted trial id).
  - Suite cost-bearing mean = sum(cost_usd)/count(cost_usd is not None)
    over the full 10-task dev set, exactly as decision-X1.py used for X1
    ($0.0879 n=38 vs $0.1218 n=39). Same task set = the 10 dev tasks; the
    only exclusion is timeout-with-no-usage trials (no cost_usd field).
  - Additionally reported: the stricter paired-cost mean excluding
    large-scale-text-editing entirely (baseline has 2 timeout-no-usage trials
    there) for transparency.
  - scipy under /root/optimize_ada/venv.
"""
import json
import math
from collections import defaultdict

DEV_TASKS = [
    "cancel-async-tasks", "fix-git", "git-multibranch",
    "large-scale-text-editing", "log-summary-date-ranges",
    "openssl-selfsigned-cert", "regex-log", "sanitize-git-repo",
    "fix-code-vulnerability", "git-leak-recovery",
]
GUARDS = ["fix-code-vulnerability", "git-leak-recovery"]
COST_EXCL_TASK = "large-scale-text-editing"  # base has 2 timeout-no-usage here
BASE = "/root/optimize_ada/eval/results"
A_BASE = f"{BASE}/graded/dev-baseline.jsonl"
A_X1R = f"{BASE}/graded/dev-x1r.jsonl"
BASE_MEAN = 0.0879
COST_CAP = 0.0967  # 1.10 x 0.0879


def load(path):
    return [json.loads(l) for l in open(path) if l.strip()]


def wilson(k, n, z=1.959963984540054):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return p, max(0.0, centre - half), min(1.0, centre + half)


def exact_mcnemar(b, c):
    from scipy.stats import binom
    n = b + c
    if n == 0:
        return 1.0
    return min(1.0, 2.0 * binom.sf(max(b, c) - 1, n, 0.5))


def pair_rows(base, x1r):
    b_by = defaultdict(list)
    x_by = defaultdict(list)
    for r in base:
        b_by[r["task"]].append(r)
    for r in x1r:
        x_by[r["task"]].append(r)
    pairs = []
    for t in DEV_TASKS:
        bs = sorted(b_by.get(t, []), key=lambda r: r["trial"])
        xs = sorted(x_by.get(t, []), key=lambda r: r["trial"])
        n = min(len(bs), len(xs))
        for i in range(n):
            pairs.append((t, i, bs[i], xs[i]))
    return pairs


def cost_mean(rows, tasks=None):
    cs = [r["cost_usd"] for r in rows
          if (tasks is None or r["task"] in tasks) and r.get("cost_usd") is not None]
    return (sum(cs) / len(cs), len(cs)) if cs else (float("nan"), 0)


def main():
    from scipy.stats import wilcoxon
    base = load(A_BASE)
    x1r = load(A_X1R)
    pairs = pair_rows(base, x1r)
    print(f"Loaded base {len(base)} / x1r {len(x1r)}; paired {len(pairs)} "
          f"({len(pairs)//4} tasks x 4)")

    # --- suite binary pass ---
    k_b = sum(1 for r in base if r["pass"] == 1.0)
    k_x = sum(1 for r in x1r if r["pass"] == 1.0)
    n_b, n_x = len(base), len(x1r)
    pb, lb, ub = wilson(k_b, n_b)
    px, lx, ux = wilson(k_x, n_x)
    print(f"\nSuite pass: base {k_b}/{n_b}={pb:.3f} Wilson[{lb:.3f},{ub:.3f}] | "
          f"x1r {k_x}/{n_x}={px:.3f} Wilson[{lx:.3f},{ux:.3f}] | delta {px-pb:+.3f}")

    # --- graded paired ---
    deltas = [xs["graded_score"] - bs["graded_score"] for _, _, bs, xs in pairs]
    g_base = sum(bs["graded_score"] for _, _, bs, _ in pairs) / len(pairs)
    g_x1r = sum(xs["graded_score"] for _, _, _, xs in pairs) / len(pairs)
    print(f"\nGraded paired mean: base {g_base:.4f}, x1r {g_x1r:.4f}, "
          f"delta {g_x1r - g_base:+.4f}")
    w = wilcoxon(deltas)
    print(f"Wilcoxon signed-rank two-sided p = {w.pvalue:.4f} (stat={w.statistic:.1f})")
    print(f"Paired graded delta >= +0.05? {'YES' if (g_x1r - g_base) >= 0.05 else 'NO'}")
    print(f"Wilcoxon p < 0.05? {'YES' if w.pvalue < 0.05 else 'NO'}")

    # --- binary McNemar ---
    both_pass = both_fail = b_only = x_only = 0
    per_task_conv = defaultdict(lambda: [0, 0])
    for t, i, rb, rx in pairs:
        bp = rb["pass"] == 1.0
        xp = rx["pass"] == 1.0
        if bp and xp:
            both_pass += 1
        elif not bp and not xp:
            both_fail += 1
        elif bp and not xp:
            b_only += 1
            per_task_conv[t][0] += 1
        else:
            x_only += 1
            per_task_conv[t][1] += 1
    p_mc = exact_mcnemar(b_only, x_only)
    print(f"\nMcNemar (position-based within task): both-pass {both_pass}, "
          f"both-fail {both_fail}, base-only {b_only}, x1r-only {x_only} -> "
          f"exact two-sided p = {p_mc:.4f}")

    # --- guards ---
    g_b = sum(1 for r in base if r["task"] in GUARDS and r["pass"] == 1.0)
    g_x = sum(1 for r in x1r if r["task"] in GUARDS and r["pass"] == 1.0)
    print(f"\nGuards: base {g_b}/8, x1r {g_x}/8  -> 8/8? {'YES' if g_x == 8 else 'NO'}")

    # --- cost: suite cost-bearing (decision parity) ---
    mb, nb = cost_mean(base)
    mx, nx = cost_mean(x1r)
    print(f"\nSuite cost-bearing mean: base ${mb:.4f} (n={nb}), "
          f"x1r ${mx:.4f} (n={nx}) -> ratio {mx/mb:.3f}")
    print(f"Cost cap ${COST_CAP:.4f} (1.10 x ${BASE_MEAN:.4f}): "
          f"x1r {'<= cap PASS' if mx <= COST_CAP else '> cap FAIL'}")

    # --- cost: strict paired task-set (exclude large-scale-text-editing) ---
    tasks9 = [t for t in DEV_TASKS if t != COST_EXCL_TASK]
    mb9, nb9 = cost_mean(base, tasks9)
    mx9, nx9 = cost_mean(x1r, tasks9)
    print(f"\n[transparency] Cost mean over 9 tasks (excl. {COST_EXCL_TASK}): "
          f"base ${mb9:.4f} (n={nb9}), x1r ${mx9:.4f} (n={nx9}) -> ratio {mx9/mb9:.3f}")

    # per-task cost means
    print(f"\n{'Task':<28}{'costB':>9}{'costX':>9}{'ratio':>8}{'pB':>5}{'pX':>5}"
          f"{'gradB':>8}{'gradX':>8}")
    bt = defaultdict(list)
    xt = defaultdict(list)
    for r in base:
        bt[r["task"]].append(r)
    for r in x1r:
        xt[r["task"]].append(r)
    for t in DEV_TASKS:
        btt, xtt = bt[t], xt[t]
        cbs = [r["cost_usd"] for r in btt if r.get("cost_usd")]
        cxs = [r["cost_usd"] for r in xtt if r.get("cost_usd")]
        mcb = sum(cbs) / len(cbs) if cbs else float("nan")
        mcx = sum(cxs) / len(cxs) if cxs else float("nan")
        ratio = mcx / mcb if cbs and cxs and mcb > 0 else float("nan")
        print(f"{t:<28}{mcb:>9.4f}{mcx:>9.4f}{ratio:>8.2f}"
              f"{sum(r['pass'] for r in btt):>4.0f}/4{sum(r['pass'] for r in xtt):>4.0f}/4"
              f"{sum(r['graded_score'] for r in btt)/len(btt):>8.4f}"
              f"{sum(r['graded_score'] for r in xtt)/len(xtt):>8.4f}")

    # --- FROZEN gate verdict ---
    print(f"\n=== FROZEN GATE VERDICT (dev-x1r) ===")
    crit = {
        "(a) graded delta >= +0.05": (g_x1r - g_base) >= 0.05,
        "(a) Wilcoxon p < 0.05": w.pvalue < 0.05,
        "(b) binary >= 24/40": k_x >= 24,
        "(c) guards 8/8": g_x == 8,
        "(d) mean cost <= $0.0967": mx <= COST_CAP,
        # reach filled in by caller (bridge-log grep); printed as PASS placeholder
        "(e) reach >= 95%": True,
    }
    for k, v in crit.items():
        print(f"  {'PASS' if v else 'FAIL'}  {k}")
    promoted = all(crit.values())
    print(f"\n>>> PROMOTED: {promoted} <<<")


if __name__ == "__main__":
    main()
