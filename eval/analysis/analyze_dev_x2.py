#!/usr/bin/env python3
"""Analyze dev-x2 (verify-against-criteria, X1-refined) vs the fresh dev-baseline.

Pre-registered criteria (eval/experiments/dev-loop/ledger.md, X2 row):
  X2 kill:  dev pass < 26/40 (baseline+2) OR mean cost > 1.15 x $0.0879 = $0.1011
  X2 success targets (learning from X1): cancel-async-tasks >= 2/4 AND
            regex-log >= 2/4
  Promotion gate (unchanged): dev pass >= 28/40 AND guards 4/4 AND mean cost
            <= 1.10 x $0.0879 = $0.0967

Comparison conventions (shared with prior arms):
  - Position-based pairing WITHIN task (trial order 0..3 in each arm's JSONL,
    NOT the 'trial' field — not comparable across arms).
  - Cost pairing excludes tasks with timeout-no-usage trials in either arm.
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
SUCCESS_TARGETS = ["cancel-async-tasks", "regex-log"]
BASE = "/root/optimize_ada/eval/results"
A_BASE = f"{BASE}/dev-baseline.jsonl"
A_X2 = f"{BASE}/dev-x2.jsonl"

try:
    from scipy.stats import binom
    HAVE_SCIPY = True
except ImportError:
    HAVE_SCIPY = False


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
    """Two-sided exact McNemar on discordant counts (b = base-only, c = x2-only)."""
    n = b + c
    if n == 0 or not HAVE_SCIPY:
        return 1.0
    return min(1.0, 2.0 * binom.sf(max(b, c) - 1, n, 0.5))


def pair_rows(base, x2):
    b_by = defaultdict(list)
    x_by = defaultdict(list)
    for r in base:
        b_by[r["task"]].append(r)
    for r in x2:
        x_by[r["task"]].append(r)
    pairs = []
    for t in DEV_TASKS:
        bs = sorted(b_by.get(t, []), key=lambda r: r["trial"])
        xs = sorted(x_by.get(t, []), key=lambda r: r["trial"])
        n = min(len(bs), len(xs))
        for i in range(n):
            pairs.append((t, i, bs[i], xs[i]))
    return pairs


def main():
    base = load(A_BASE)
    x2 = load(A_X2)
    pairs = pair_rows(base, x2)
    print(f"Loaded base {len(base)} / x2 {len(x2)}; paired {len(pairs)} "
          f"({len(pairs)//4} tasks x 4)")

    k_b = sum(1 for r in base if r["pass"] == 1.0)
    k_x = sum(1 for r in x2 if r["pass"] == 1.0)
    n_b, n_x = len(base), len(x2)
    pb, lb, ub = wilson(k_b, n_b)
    px, lx, ux = wilson(k_x, n_x)
    print(f"\nSuite pass: base {k_b}/{n_b}={pb:.3f} Wilson[{lb:.3f},{ub:.3f}] | "
          f"x2 {k_x}/{n_x}={px:.3f} Wilson[{lx:.3f},{ux:.3f}] | "
          f"delta {px-pb:+.3f}")

    both_pass = both_fail = b_only = x_only = 0
    per_task_conv = defaultdict(lambda: [0, 0])
    for t, i, rb, rx in pairs:
        bpass = rb["pass"] == 1.0
        xpass = rx["pass"] == 1.0
        if bpass and xpass:
            both_pass += 1
        elif not bpass and not xpass:
            both_fail += 1
        elif bpass and not xpass:
            b_only += 1
            per_task_conv[t][0] += 1
        else:
            x_only += 1
            per_task_conv[t][1] += 1
    p_mc = exact_mcnemar(b_only, x_only)
    print(f"\nMcNemar (position-based, within task): both-pass {both_pass}, "
          f"both-fail {both_fail}, base-only {b_only}, x2-only {x_only} -> "
          f"exact p = {p_mc:.4f}")

    g_b = sum(1 for r in base if r["task"] in GUARDS and r["pass"] == 1.0)
    g_x = sum(1 for r in x2 if r["task"] in GUARDS and r["pass"] == 1.0)
    print(f"\nGuards: base {g_b}/8, x2 {g_x}/8")

    cb = [r["cost_usd"] for r in base if r.get("cost_usd") is not None]
    cx = [r["cost_usd"] for r in x2 if r.get("cost_usd") is not None]
    mb = sum(cb) / len(cb)
    mx = sum(cx) / len(cx)
    print(f"\nMean cost (cost-bearing): base ${mb:.4f} (n={len(cb)}), "
          f"x2 ${mx:.4f} (n={len(cx)}) -> ratio {mx/mb:.3f}")
    kill_cost = 0.0879 * 1.15
    promo_cost = 0.0879 * 1.10
    print(f"X2 kill guard cost > ${kill_cost:.4f}? {'YES -> KILL' if mx > kill_cost else 'no'}")
    print(f"Promotion gate cost <= ${promo_cost:.4f}? {'YES' if mx <= promo_cost else 'NO'}")

    bm = {}
    xm = {}
    for r in base:
        bm.setdefault(r["task"], []).append(r.get("cost_usd"))
    for r in x2:
        xm.setdefault(r["task"], []).append(r.get("cost_usd"))

    def tm(d):
        vals = []
        for t in DEV_TASKS:
            cs = [v for v in d[t] if v is not None]
            vals.append(sum(cs) / len(cs) if cs else None)
        vals = [v for v in vals if v is not None]
        return sum(vals) / len(vals)
    mbt, mxt = tm(bm), tm(xm)
    print(f"Task-mean cost: base ${mbt:.4f}, x2 ${mxt:.4f} -> ratio {mxt/mbt:.3f}")

    print(f"\n{'Task':<28}{'Base':>10}{'X2':>10}{'Conv':>8}{'costB':>9}{'costX':>9}{'ratio':>8}")
    b_task = defaultdict(list)
    x_task = defaultdict(list)
    for r in base:
        b_task[r["task"]].append(r)
    for r in x2:
        x_task[r["task"]].append(r)
    for t in DEV_TASKS:
        bs = b_task[t]
        xs = x_task[t]
        ps = sum(r["pass"] for r in bs)
        pxs = sum(r["pass"] for r in xs)
        cbs = [r["cost_usd"] for r in bs if r.get("cost_usd")]
        cxs = [r["cost_usd"] for r in xs if r.get("cost_usd")]
        mcb = sum(cbs) / len(cbs) if cbs else float("nan")
        mcx = sum(cxs) / len(cxs) if cxs else float("nan")
        ratio = mcx / mcb if cbs and cxs and mcb > 0 else float("nan")
        conv = per_task_conv[t]
        print(f"{t:<28}{ps:>5}/4{pxs:>5}/4  "
              f"B-only {conv[0]}, X-only {conv[1]:<4} "
              f"${mcb:.4f} ${mcx:.4f} {ratio:>7.2f}")

    # success targets (X1 learning: cancel-async-tasks + regex-log)
    print("\nSuccess targets (must be >= 2/4 each):")
    for t in SUCCESS_TARGETS:
        ps = sum(r["pass"] for r in x_task[t])
        print(f"  {t}: {ps}/4 {'OK' if ps >= 2 else 'MISS'}")

    verdict_kill = (k_x < 26) or (mx > kill_cost)
    verdict_promo = (k_x >= 28) and (g_x == 8) and (mx <= promo_cost)
    targets_ok = all(
        sum(r["pass"] for r in x_task[t]) >= 2 for t in SUCCESS_TARGETS
    )
    print(f"\n=== VERDICT ===")
    print(f"Kill triggered (pass<26 OR cost>${kill_cost:.4f})? {'YES' if verdict_kill else 'NO'}")
    print(f"Promotion gate met (pass>=28 AND guards 8/8 AND cost<=${promo_cost:.4f})? "
          f"{'YES' if verdict_promo else 'NO'}")
    print(f"Success targets met (cancel-async-tasks>=2/4 AND regex-log>=2/4)? "
          f"{'YES' if targets_ok else 'NO'}")


if __name__ == "__main__":
    main()
