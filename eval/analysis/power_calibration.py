#!/usr/bin/env python
"""Power calibration for the graded metric (zero API spend).

From the graded re-scoring of dev-baseline (n=40), estimate:
  1. The graded-metric noise band at n=40 (bootstrap over trials, and a
     permutation-style null: split dev-baseline into two halves and measure
     the distribution of half-vs-half graded deltas).
  2. Minimum detectable effect (MDE) for k=4 dev arms (n=40) and k=8
     validation (n=120) at alpha=0.05, two-sided Wilcoxon approximation via
     paired-delta bootstrap.

Outputs the numbers used to pre-register the graded promotion gate.
"""
import json
import random

BASE = "/root/optimize_ada/eval"
GRADED = f"{BASE}/results/graded"


def load(arm):
    return [json.loads(l) for l in open(f"{GRADED}/{arm}.jsonl") if l.strip()]


def mean(xs):
    return sum(xs) / len(xs)


def main():
    rows = load("dev-baseline")
    g = [r["graded_score"] for r in rows]
    n = len(g)
    rng = random.Random(42)

    # 1. Bootstrap CI half-width of the mean graded score at n=40
    stats = []
    for _ in range(20000):
        s = [g[rng.randrange(n)] for _ in range(n)]
        stats.append(mean(s))
    stats.sort()
    lo, hi = stats[int(0.025 * 20000)], stats[int(0.975 * 20000)]
    half_width = (hi - lo) / 2
    print(f"dev-baseline graded mean = {mean(g):.4f}")
    print(f"Bootstrap 95% CI of mean at n=40: [{lo:.4f}, {hi:.4f}] (half-width {half_width:.4f})")

    # 2. Null distribution of paired-delta means: resample pairs of bootstrap
    #    means from the SAME arm (a null arm vs itself) at n=40 and n=120.
    for label, m in (("k=4 (n=40)", 40), ("k=8 validation (n=120)", 120)):
        deltas = []
        for _ in range(20000):
            a = mean([g[rng.randrange(n)] for _ in range(m)])
            b = mean([g[rng.randrange(n)] for _ in range(m)])
            deltas.append(a - b)
        deltas.sort()
        d05 = deltas[int(0.025 * 20000)]
        d95 = deltas[int(0.975 * 20000)]
        # MDE ~ the |delta| whose one-sided 5% quantile excludes 0:
        # use the 97.5th percentile of |null delta| as the detection threshold
        absd = sorted(abs(d) for d in deltas)
        mde = absd[int(0.95 * 20000)]
        print(f"\n{label}: null paired-delta 95% band [{d05:+.4f}, {d95:+.4f}], "
              f"MDE (95th pct |null delta|) = {mde:.4f}")

    # 3. Also: per-task graded variance (for context)
    from collections import defaultdict
    by_task = defaultdict(list)
    for r in rows:
        by_task[r["task"]].append(r["graded_score"])
    print("\nPer-task graded (dev-baseline):")
    for t in sorted(by_task):
        v = by_task[t]
        print(f"  {t:32s} mean {mean(v):.3f}  vals {[round(x,2) for x in v]}")


if __name__ == "__main__":
    main()
