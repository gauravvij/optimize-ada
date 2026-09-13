#!/usr/bin/env python3
"""Variance probe analysis: per-task CV in cost/duration/pass from the
variance-probe job (3 tasks x 3 repeats, reference claude-code agent, haiku).

Derives the required number of repeats k for the baseline run:
  - cost/duration CV drives k via the paired-delta CI half-width:
      For a paired A/B with per-run CV c and k repeats per arm, the SE of the
      mean cost per task ~ c*mean/sqrt(k). We want the CI half-width on the
      paired cost delta to be <= 20% of the mean cost (pre-registered
      detectable effect size for cost experiments):
      1.96 * c / sqrt(k) <= 0.20  =>  k >= (1.96*c/0.20)^2
  - pass-rate: with binary outcomes, k must be large enough that a per-task
      pass-rate difference of 1/k is resolvable; k=3 gives pass in {0,1/3,2/3,1}.
      Pass-rate deltas are judged at the aggregate (15-task) level with
      McNemar's, so per-task k=3 suffices.
"""
import json
import math
import glob
import os
from collections import defaultdict

JOB = "/root/optimize_ada/eval/jobs/variance-probe"

def cv(xs):
    m = sum(xs) / len(xs)
    if m == 0:
        return float("nan")
    var = sum((x - m) ** 2 for x in xs) / (len(xs) - 1)  # sample variance
    return math.sqrt(var) / m

rows = defaultdict(lambda: {"cost": [], "dur": [], "ttft": [], "pass": []})
for f in glob.glob(os.path.join(JOB, "*", "result.json")):
    d = json.load(open(f))
    if "trial_name" not in d:
        continue  # job-level result.json
    task = d["task_name"]
    ar = d.get("agent_result") or {}
    md = (ar.get("metadata") or {})
    rows[task]["cost"].append(ar.get("cost_usd") or 0)
    # Reference arm has no duration_ms metadata — use trial wall-clock
    # (started_at -> finished_at) as the duration measure for BOTH arms.
    from datetime import datetime
    def ts(s):
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    dur_ms = (ts(d["finished_at"]) - ts(d["started_at"])) * 1000
    rows[task]["dur"].append(dur_ms)
    rows[task]["ttft"].append(md.get("ttft_ms") or 0)
    rows[task]["pass"].append(
        float((d.get("verifier_result") or {}).get("rewards", {}).get("reward") or 0)
    )

print(f"{'task':<22}{'n':>3}{'cost mean':>11}{'cost CV':>9}{'dur mean(s)':>12}{'dur CV':>8}{'pass':>7}")
cost_cvs, dur_cvs = [], []
for t, r in sorted(rows.items()):
    cc, dc = cv(r["cost"]), cv(r["dur"])
    cost_cvs.append(cc); dur_cvs.append(dc)
    print(f"{t:<22}{len(r['cost']):>3}{sum(r['cost'])/len(r['cost']):>11.4f}{cc:>9.3f}"
          f"{sum(r['dur'])/len(r['dur'])/1000:>12.1f}{dc:>8.3f}"
          f"{'/'.join(str(int(p)) for p in r['pass']):>7}")

avg_cost_cv = sum(cost_cvs) / len(cost_cvs)
avg_dur_cv = sum(dur_cvs) / len(dur_cvs)
print(f"\nmean cost CV = {avg_cost_cv:.3f}, mean duration CV = {avg_dur_cv:.3f}")

# k for cost: 1.96 * CV / sqrt(k) <= 0.20 (detect 20% cost delta)
k_cost = (1.96 * avg_cost_cv / 0.20) ** 2
# k for duration: detect 25% latency delta
k_dur = (1.96 * avg_dur_cv / 0.25) ** 2
k = max(2, math.ceil(max(k_cost, k_dur)))
print(f"k from cost CV: {k_cost:.2f}; k from duration CV: {k_dur:.2f}")
print(f"=> REQUIRED k = {k}")

out = {
    "per_task": {t: {"cost_cv": cv(r["cost"]), "dur_cv": cv(r["dur"]),
                     "cost_mean": sum(r["cost"])/len(r["cost"]),
                     "pass": r["pass"]} for t, r in rows.items()},
    "mean_cost_cv": avg_cost_cv, "mean_dur_cv": avg_dur_cv,
    "k_cost_raw": k_cost, "k_dur_raw": k_dur, "required_k": k,
}
with open("/root/optimize_ada/eval/variance-probe.json", "w") as f:
    json.dump(out, f, indent=1)
print("wrote eval/variance-probe.json")
