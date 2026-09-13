#!/usr/bin/env python
"""Paired graded + binary re-analysis of every prior arm (zero API spend).

For each prior experiment arm vs its correct baseline, compute:
  - mean graded score +/- bootstrap 95% CI (both arms)
  - paired per-task graded deltas (position-based pairing within task)
  - Wilcoxon signed-rank on paired graded scores (scipy, venv)
  - binary result side by side (pass counts + exact McNemar)

Comparisons:
  dev-x1, dev-x2, dev-x3  vs  dev-baseline   (dev loop, 10 tasks x 4)
  e-opt1-arm, e-opt1-arm-v2, l1l2-arm  vs  baseline-armB  (60-trial arms)

Emits eval/experiments/dev-loop/regrade-report.md.

Run under: source /root/optimize_ada/venv/bin/activate (scipy).
"""
import json
import random
from collections import defaultdict
from math import comb

from scipy.stats import wilcoxon

BASE = "/root/optimize_ada/eval"
GRADED = f"{BASE}/results/graded"
OUT = f"{BASE}/experiments/dev-loop/regrade-report.md"

COMPARISONS = [
    ("dev-x1", "dev-baseline"),
    ("dev-x2", "dev-baseline"),
    ("dev-x3", "dev-baseline"),
    ("e-opt1-arm", "baseline-armB"),
    ("e-opt1-arm-v2", "baseline-armB"),
    ("l1l2-arm", "baseline-armB"),
    ("dev-h1", "dev-baseline"),
    ("dev-h2", "dev-baseline"),
]


def load(arm):
    return [json.loads(l) for l in open(f"{GRADED}/{arm}.jsonl") if l.strip()]


def mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def bootstrap_ci(xs, n=10000, seed=0):
    rng = random.Random(seed)
    N = len(xs)
    stats = []
    for _ in range(n):
        s = [xs[rng.randrange(N)] for _ in range(N)]
        stats.append(mean(s))
    stats.sort()
    return stats[int(0.025 * n)], stats[int(0.975 * n)]


def pair_rows(a, b):
    """Position-based pairing within task (order of appearance in each JSONL)."""
    by_a, by_b = defaultdict(list), defaultdict(list)
    for r in a:
        by_a[r["task"]].append(r)
    for r in b:
        by_b[r["task"]].append(r)
    pairs = []
    for t in sorted(set(by_a) & set(by_b)):
        na, nb = len(by_a[t]), len(by_b[t])
        for i in range(min(na, nb)):
            pairs.append((t, by_a[t][i], by_b[t][i]))
    return pairs


def exact_mcnemar(b, c):
    """Two-sided exact McNemar: b = baseline-only passes, c = arm-only passes."""
    n = b + c
    if n == 0:
        return 1.0
    p = sum(comb(n, k) for k in range(max(b, c), n + 1)) / (2 ** n)
    return min(1.0, 2 * p)


def analyze(arm, base):
    a, b = load(arm), load(base)
    ga = [r["graded_score"] for r in a]
    gb = [r["graded_score"] for r in b]
    ma, mb = mean(ga), mean(gb)
    la, ua = bootstrap_ci(ga)
    lb, ub = bootstrap_ci(gb)

    pairs = pair_rows(a, b)
    deltas = [ra["graded_score"] - rb["graded_score"] for _, ra, rb in pairs]
    md = mean(deltas)
    dlo, dhi = bootstrap_ci(deltas, seed=1)
    if any(d != 0 for d in deltas):
        W, p_w = wilcoxon([ra["graded_score"] for _, ra, _ in pairs],
                          [rb["graded_score"] for _, _, rb in pairs],
                          zero_method="wilcox", alternative="two-sided")
    else:
        W, p_w = float("nan"), 1.0

    ka = sum(1 for r in a if r["pass"] == 1.0)
    kb = sum(1 for r in b if r["pass"] == 1.0)
    b_only = c_only = 0
    for _, ra, rb in pairs:
        if rb["pass"] == 1.0 and ra["pass"] != 1.0:
            b_only += 1
        elif ra["pass"] == 1.0 and rb["pass"] != 1.0:
            c_only += 1
    p_mc = exact_mcnemar(b_only, c_only)

    tasks = sorted(set(r["task"] for r in a) | set(r["task"] for r in b))
    per_task = []
    for t in tasks:
        ta = [r["graded_score"] for r in a if r["task"] == t]
        tb = [r["graded_score"] for r in b if r["task"] == t]
        pa = sum(1 for r in a if r["task"] == t and r["pass"] == 1.0)
        pb = sum(1 for r in b if r["task"] == t and r["pass"] == 1.0)
        per_task.append((t, mean(ta), mean(tb), pa, len(ta), pb, len(tb)))

    return dict(arm=arm, base=base, n_a=len(a), n_b=len(b), ma=ma, mb=mb,
                ci_a=(la, ua), ci_b=(lb, ub), n_pairs=len(pairs), md=md,
                dci=(dlo, dhi), W=W, p_wilcox=p_w, ka=ka, kb=kb,
                b_only=b_only, c_only=c_only, p_mcnemar=p_mc, per_task=per_task)


def fmt(r):
    lines = []
    lines.append(f"### {r['arm']} vs {r['base']}  (n={r['n_a']} vs {r['n_b']}, paired {r['n_pairs']})")
    lines.append("")
    lines.append(f"- **Graded**: {r['arm']} {r['ma']:.4f} [95% CI {r['ci_a'][0]:.4f}, {r['ci_a'][1]:.4f}] "
                 f"vs {r['base']} {r['mb']:.4f} [CI {r['ci_b'][0]:.4f}, {r['ci_b'][1]:.4f}]")
    lines.append(f"- **Paired graded delta**: {r['md']:+.4f} [CI {r['dci'][0]:+.4f}, {r['dci'][1]:+.4f}], "
                 f"Wilcoxon W={r['W']:.1f}, p={r['p_wilcox']:.4f}")
    lines.append(f"- **Binary**: {r['arm']} {r['ka']}/{r['n_a']} ({r['ka']/r['n_a']:.3f}) vs "
                 f"{r['base']} {r['kb']}/{r['n_b']} ({r['kb']/r['n_b']:.3f}); "
                 f"discordant base-only {r['b_only']} / arm-only {r['c_only']}, exact McNemar p={r['p_mcnemar']:.4f}")
    lines.append("")
    lines.append(f"| task | graded {r['arm']} | graded {r['base']} | d graded | pass {r['arm']} | pass {r['base']} |")
    lines.append("|---|---|---|---|---|---|")
    for t, mta, mtb, pa, na, pb, nb in r["per_task"]:
        lines.append(f"| {t} | {mta:.3f} | {mtb:.3f} | {mta-mtb:+.3f} | {pa}/{na} | {pb}/{nb} |")
    lines.append("")
    return lines


def main():
    results = [analyze(a, b) for a, b in COMPARISONS]
    out = ["# Regrade report: graded vs binary re-analysis of all prior experiments",
           "",
           "Generated by eval/analysis/regrade_arms.py from eval/results/graded/*.jsonl",
           "(per-test re-scoring of verifier/ctrf.json). Zero API spend.",
           "",
           "Graded = verifier tests passed / total. Binary = all-tests-passed.",
           "Pairing is position-based within task; Wilcoxon is two-sided signed-rank;",
           "McNemar is two-sided exact on binary discordants.",
           "",
           "## Headline table",
           "",
           "| arm | vs baseline | graded delta | Wilcoxon p | binary delta | McNemar p | verdict shift |",
           "|---|---|---|---|---|---|---|"]
    for r in results:
        bd = r["ka"] / r["n_a"] - r["kb"] / r["n_b"]
        sig_g = r["p_wilcox"] < 0.05
        sig_b = r["p_mcnemar"] < 0.05
        shift = "graded SIG, binary NS" if sig_g and not sig_b else \
                ("both SIG" if sig_g and sig_b else
                 ("binary SIG, graded NS" if sig_b and not sig_g else "both NS"))
        out.append(f"| {r['arm']} | {r['base']} | {r['md']:+.4f} | {r['p_wilcox']:.4f} | "
                   f"{bd:+.4f} | {r['p_mcnemar']:.4f} | {shift} |")
    out.append("")
    out.append("## Detail per comparison")
    out.append("")
    for r in results:
        out.extend(fmt(r))
    with open(OUT, "w") as f:
        f.write("\n".join(out) + "\n")
    for r in results:
        bd = r["ka"] / r["n_a"] - r["kb"] / r["n_b"]
        print(f"{r['arm']:>14} vs {r['base']:<14} graded {r['md']:+.4f} "
              f"(p={r['p_wilcox']:.4f})  binary {bd:+.4f} (p={r['p_mcnemar']:.4f})")
    print(f"\nReport written to {OUT}")


if __name__ == "__main__":
    main()
