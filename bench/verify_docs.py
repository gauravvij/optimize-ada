#!/usr/bin/env python3
"""Every result stated in blog.md and README.md, checked against the raw per-task diagnostics
or the analysis file or record it cites.

Each check names the document(s) it applies to, a short anchor that must appear there, and
a condition the raw data must satisfy. Anchors are matched after collapsing whitespace and
dashes, so rewording a sentence around a number does not break a check, but changing the
number, or the data, does. Definitions match bench/ctrl_vs_t12_verify.py: a run
"interrupted by the watchdog" has agent_is_error set; a paired comparison uses only tasks
where both runs returned a valid row. Standard library only:

    python3 bench/verify_docs.py
"""
import hashlib
import json
import re
import subprocess
import sys
from math import comb
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "bench/diagnostics").is_dir())
B, D = ROOT / "bench", ROOT / "bench/diagnostics"


def norm(text):
    return re.sub(r"\s+", " ", re.sub("[—–−]", "-", text.replace("→", "->")))


DOCS = {"blog": norm((ROOT / "blog.md").read_text()), "readme": norm((ROOT / "README.md").read_text())}
FAILS = []


def claim(where, anchors, ok, source):
    """Each named document must contain its anchor, and the data must make `ok` true."""
    if isinstance(anchors, str):
        anchors = {d: anchors for d in ("blog", "readme")} if where == "both" else {where: anchors}
    for doc, anchor in anchors.items():
        stated = norm(anchor) in DOCS[doc]
        good = stated and bool(ok)
        if not good:
            FAILS.append(f"{doc}: {anchor}")
        why = "" if good else ("  [not in document]" if not stated else "  [data disagrees]")
        print(f"{'PASS' if good else 'FAIL'}  {doc:6s} {anchor[:78]}  <- {source}{why}")


def rows(rel):
    return {r["task_id"]: r for r in json.loads((B / rel).read_text())["results"]}


def proto(rel):
    return json.loads((B / rel).read_text()).get("protocol", {})


def mcnemar(b, c):
    n = b + c
    return min(1.0, 2 * sum(comb(n, k) for k in range(min(b, c) + 1)) / 2 ** n) if n else 1.0


def pair(a, b):
    """(n, a passes, b passes, gained, lost, p) over tasks valid in both runs."""
    ids = [t for t in a if t in b and a[t].get("valid", True) and b[t].get("valid", True)]
    g = sum(not a[t]["passed"] and b[t]["passed"] for t in ids)
    l = sum(a[t]["passed"] and not b[t]["passed"] for t in ids)
    return len(ids), sum(a[t]["passed"] for t in ids), sum(b[t]["passed"] for t in ids), g, l, mcnemar(l, g)


passed = lambda R: sum(r["passed"] for r in R.values())
timeouts = lambda R: sum(bool(r["timed_out"]) for r in R.values())
zero = lambda R: [r for r in R.values() if (r["turns"] or 0) == 0]
interrupted = lambda R: sum(bool(r["agent_is_error"]) for r in R.values())
turns = lambda R: sum(r["turns"] or 0 for r in R.values())
secs = lambda R: sum(r["duration_seconds"] for r in R.values())
net = lambda a, b: pair(a, b)[3] - pair(a, b)[4]

# ---------------------------------------------------------------------- the runs
P = {
    "R1": "diagnostics/ada-baseline/manual/remaining81_baseline.json", "R2": "diagnostics/manual/remaining81_incumbent.json",
    "F31": "diagnostics/manual/remaining81_final_failures31.json", "R3": "diagnostics/20260910T0728Z-t04ctrl/0.json",
    "R4": "diagnostics/20260911T1540Z-t12rem81/rem81_t12_candidate.json", "R5": "diagnostics/ada-baseline/20260912T1031Z-frem81base/0.json",
    "R7": "diagnostics/ada-t01gateoff/20260912T1603Z-t04ctrl2/0.json", "R8": "diagnostics/20260912T1603Z-t12cand2/0.json",
    "R9a": "diagnostics/ada-baseline/20260915T0825Z-r1-base/0.json", "R10a": "diagnostics/ada-baseline/20260915T0825Z-r2-base/0.json",
    "R9b": "diagnostics/20260915T0825Z-r1-best/0.json", "R10b": "diagnostics/20260915T0825Z-r2-best/0.json",
    "BP": "diagnostics/budget-probe-20260916T0730Z/0.json",
    "S1": "diagnostics/20260917T0602Z-r1-shipped/0.json", "S2": "diagnostics/20260917T0602Z-r2-shipped/0.json",
    "P1": "p3_evidence/20260917T0602Z-r1-p3/0.json", "P2": "p3_evidence/20260917T0602Z-r2-p3/0.json",
}
R = {k: rows(v) for k, v in P.items()}
R1, R2, F31, R3, R4, R5, R7, R8 = (R[k] for k in ("R1", "R2", "F31", "R3", "R4", "R5", "R7", "R8"))
R9a, R10a, R9b, R10b, BP, S1, S2, P1, P2 = (R[k] for k in ("R9a", "R10a", "R9b", "R10b", "BP", "S1", "S2", "P1", "P2"))

# ------------------------------------------------- the harness and the watchdog
conf = [proto(P[k]) for k in ("R9a", "R10a", "R9b", "R10b")]
runner = hashlib.sha256((B / "harness/setupbench_ada_runner.ts").read_bytes()).hexdigest()
evaluator = hashlib.sha256((B / "harness/setupbench_ada_domain_eval.py").read_bytes()).hexdigest()
claim("both", "`z-ai/glm-5.3-flash`", all(p["model"] == "z-ai/glm-5.3-flash" for p in conf), "R9/R10 protocol.model")
claim("both", "480-second budget", all(p["task_timeout_seconds"] == 480 for p in conf), "R9/R10 protocol.task_timeout_seconds")
claim("blog", "used 81 of its tasks", all(len(p["tasks"]) == 81 for p in conf), "R9/R10 protocol.tasks")
claim("readme", "81 real software-setup tasks", all(len(p["tasks"]) == 81 for p in conf), "R9/R10 protocol.tasks")
claim("blog", "byte-identical to the one in `bench/harness/` in every run", all(p["runner_sha256"] == runner for p in conf),
      "protocol.runner_sha256 vs sha256(setupbench_ada_runner.ts)")
claim("readme", "byte-identical to the runner every run recorded", all(p["runner_sha256"] == runner for p in conf),
      "protocol.runner_sha256 vs sha256(setupbench_ada_runner.ts)")
claim("both", "a later revision", all(p["evaluator_sha256"] != evaluator for p in conf),
      "protocol.evaluator_sha256 vs sha256(setupbench_ada_domain_eval.py)")
ev = (B / "harness/setupbench_ada_eval.py").read_text()
claim("blog", "timed out: the grader never runs",
      "if not timed_out:" in ev and ev.index("if not timed_out:") < ev.index('task["success_command"]'), "setupbench_ada_eval.py")
agent = (ROOT / "ada/agent/claude/agent.ts").read_text()
margin = re.search(r"ADA_DEADLINE_MARGIN_MS \?\? ([\d_]+)\)", agent)
cutoff_ok = (margin and int(margin.group(1).replace("_", "")) == 30000
             and "taskBudgetMs - deadlineMarginMs" in agent
             and all(r["duration_seconds"] >= 450 for k in ("R3", "R7", "R8", "R9b", "R10b", "S1", "S2") for r in R[k].values() if r["agent_is_error"])
             and all(r["duration_seconds"] >= 930 for r in BP.values() if r["agent_is_error"]))
claim("both", {"blog": "interrupts Ada 30 seconds before the budget runs out", "readme": "interrupt the agent 30 seconds before the budget runs out"},
      cutoff_ok, "agent.ts ADA_DEADLINE_MARGIN_MS default; every interrupted row ends past the cut-off")
claim("both", "450-second mark", cutoff_ok, "480 s budget minus the 30 s margin")
claim("blog", "The runs up to R8 ran four tasks at a time; the confirmation ran one task at a time per build",
      all(proto(P[k]).get("concurrency") == 4 for k in ("R1", "R2", "R3", "R4", "R5", "R7", "R8")) and all(p["concurrency"] == 1 for p in conf),
      "protocol.concurrency")
drv = (B / "baseline_vs_best_20260915T0825Z_driver.log").read_text()
claim("readme", "R1 to R8 ran four tasks at a time. R9/R10 ran one task at a time per build",
      all(proto(P[k]).get("concurrency") == 4 for k in ("R1", "R2", "R3", "R4", "R5", "R7", "R8")) and all(p["concurrency"] == 1 for p in conf),
      "protocol.concurrency")
claim("readme", "replicate 2 started at 12:11 while replicate 1 ran until 17:42",
      "REPLICATE 2/2 launched" in drv and "12:11:42" in drv and "REP_1_DONE Tue Sep 15 17:42" in drv, "baseline_vs_best driver log")
rule = (B / "run_baseline_vs_best.sh").read_text()
claim("both", "`bench/run_baseline_vs_best.sh`",
      "PRE-REGISTERED RULE (fixed before any spend)" in rule and "net >= +10" in rule and "p < 0.001" in rule
      and "rule: {'all_replicates_complete': True, 'each_replicate_net_ge_10': True, 'each_replicate_invalid_le_3': True, 'pooled_p_lt_0.001': True}" in drv,
      "the rule at the top of the driver script, applied in the run's log")

# ------------------------------------------------------------ R1, R2, Phase A
claim("blog", "(R1) passed 27 of 81 tasks and timed out on 53", passed(R1) == 27 and timeouts(R1) == 53, "R1 rows")
claim("readme", "**53 of 81** SetupBench tasks to timeouts on the first full run (R1, 27/81)", passed(R1) == 27 and timeouts(R1) == 53, "R1 rows")
claim("blog", "Every timeout was a zero", all((r["turns"] or 0) == 0 for r in R1.values() if r["timed_out"]), "R1 timed-out rows")
claim("readme", "overran on 40 to 53 of the 81 tasks",
      (min(map(timeouts, (R1, R5, R9a, R10a))), max(map(timeouts, (R1, R5, R9a, R10a)))) == (40, 53), "origin runs R1 R5 R9a R10a")
claim("blog", "cut timeouts from 53 to 3", timeouts(R2) == 3, "R2 rows")
claim("readme", "cut timeouts from 53 (R1) to 3 (R2,", timeouts(R2) == 3, "R2 rows")
z2 = zero(R2)
r2_ok = len(z2) == 43 and sum(r["grader_returncode"] is not None for r in z2) == 41 and sum(r["passed"] for r in z2) == 19
claim("blog", "43 runs were recorded with zero turns, although 41 of them were still graded and 19 passed", r2_ok, "R2 zero-turn rows")
claim("readme", "43 runs were recorded with zero turns - 41 of them were still graded and 19 passed", r2_ok, "R2 zero-turn rows")
claim("blog", "neither full run of that build recorded a zero-turn run", not zero(R3) and not zero(R7), "R3, R7 rows")
claim("readme", "neither of its full runs (R3, R7) recorded a zero-turn run", not zero(R3) and not zero(R7), "R3, R7 rows")
hybrid = passed(R2) == 50 and len(F31) == 31 and set(F31) == {t for t in R2 if not R2[t]["passed"]} and passed(R2) + passed(F31) == 59
claim("blog", "Phase A's: 27/81 to 59/81", hybrid and passed(R1) == 27, "R1; R2 + re-run of its 31 failures")
claim("blog", "50 passes carried over from earlier runs plus a re-run of only the 31 failures", hybrid, "R2 + failures31 rows")
claim("readme", "27/81 -> **59/81** | Assembled from 50 carried-over passes plus a re-run of only the 31 failures", hybrid, "R2 + failures31 rows")

# ------------------------------------------------- the same-day ladder (R5 R7 R8)
_, _, _, g, l, p = pair(R5, R7)
claim("blog", "| Origin `df0c537` | nothing | 34/81 |", passed(R5) == 34 and len(R5) == 81, "R5 rows")
claim("readme", "| `df0c537` | campaign origin, no watchdog | 34/81 |", passed(R5) == 34 and len(R5) == 81, "R5 rows")
claim("both", {"blog": "**54/81** | **+20**, 21 gained / 1 lost, p = 1.1e-05", "readme": "**54/81** | **+20 net**, 21 gained / 1 lost, exact McNemar **p = 1.1e-05**"},
      (g, l, f"{p:.1e}", passed(R7)) == (21, 1, "1.1e-05", 54), "R5 -> R7")
_, _, _, g, l, p = pair(R7, R8)
claim("both", {"blog": "50/81 | **-4**, 5 gained / 9 lost, p = 0.42", "readme": "50/81 | **-4 net**, 5 gained / 9 lost, **p = 0.42**"},
      (g, l, f"{p:.2f}", passed(R8)) == (5, 9, "0.42", 50), "R7 -> R8")
hung = [t for t in R5 if (R5[t]["turns"] or 0) == 0]
ran = [t for t in R5 if (R5[t]["turns"] or 0) > 0]
hung_ok = len(hung) == 46 and sum(R7[t]["passed"] for t in hung) == 21
ran_ok = (len(ran) == 35 and sum(R5[t]["passed"] for t in ran) == 34 and sum(R7[t]["passed"] for t in ran) == 33
          and max(sum(X[t]["passed"] for t in ran) for X in (R7, R8, R9b, R10b)) <= 34)
claim("blog", "zero turns on 46 of the 81 tasks, and the watchdog build passed 21 of those 46", hung_ok, "R5 zero-turn tasks, R7")
claim("readme", "0/46 -> 21/46", hung_ok, "R5 zero-turn tasks, R7")
claim("blog", "it had already passed 34, and nothing built since has improved on that", ran_ok, "R5 ran tasks; R7 R8 R9b R10b")
claim("readme", "it scored 34/35 - the watchdog build lost one of them - and nothing built since has improved", ran_ok, "R5 ran tasks; R7 R8 R9b R10b")
mech = ((interrupted(R7), interrupted(R8)) == (34, 7) and f"{100 * (1 - turns(R8) / turns(R7)):.1f}" == "10.6"
        and f"{100 * (1 - secs(R8) / secs(R7)):.1f}" == "5.0")
claim("blog", "Runs interrupted by the watchdog fell from 34 to 7, turns fell 10.6%, and wall time fell 5.0%", mech, "R7, R8 rows")
claim("readme", "runs interrupted by the watchdog 34 -> 7, turns -10.6%, wall time -5.0%", mech, "R7, R8 rows")
claim("both", "by 79%", f"{100 * (1 - interrupted(R8) / interrupted(R7)):.0f}" == "79", "R7 -> R8 interrupted runs")
claim("readme", "turns by 11%", f"{100 * (1 - turns(R8) / turns(R7)):.0f}" == "11", "R7 -> R8 turns")
clean = [t for t in R7 if not R7[t]["agent_is_error"]]
claim("blog", "On the 47 tasks where the watchdog build finished with time to spare, the time-hints build went from 42 passes to 37",
      len(clean) == 47 and sum(R7[t]["passed"] for t in clean) == 42 and sum(R8[t]["passed"] for t in clean) == 37, "R7 non-interrupted tasks")
said_done = lambda X: sum(not r["passed"] and not r["agent_is_error"] and r["grader_returncode"] is not None for r in X.values())
claim("blog", "Of the time-hints build's 31 failures, 25 ended", (said_done(R8), len(R8) - passed(R8)) == (25, 31), "R8 failures")
claim("blog", "For the watchdog build it was 5 of 27", (said_done(R7), len(R7) - passed(R7)) == (5, 27), "R7 failures")

# ------------------------------------------------------------ the withdrawn +28
_, _, _, g, l, p = pair(R3, R4)
claim("both", {"blog": "52/81 against 24/81, +28, p = 7.66e-07", "readme": "52/81 against 24/81, net +28, p = 7.66e-07"}, (passed(R4), passed(R3), g - l, f"{p:.2e}") == (52, 24, 28, "7.66e-07"), "R3 -> R4")
ci = json.loads((B / "T12_REM81_PAIRED_ANALYSIS.json").read_text())["statistics"]["newcombe_95ci_diff"]
claim("blog", "95% confidence interval ran from +19 to +48 points", ci[0] > 0 and (round(100 * ci[0]), round(100 * ci[1])) == (19, 48),
      "T12_REM81_PAIRED_ANALYSIS.json statistics.newcombe_95ci_diff")
r3commit = json.loads((B / P["R3"]).read_text())["workspace_commit"]
claim("blog", "the commit it records was only created at 07:24 UTC on 2026-09-11", r3commit.startswith("6672af8"),
      "R3 workspace_commit (its commit time: bash bench/verify_builds.sh)")
claim("readme", "R3 records commit `6672af8`", r3commit.startswith("6672af8"), "R3 workspace_commit")
_, _, b, g, l, p = pair(R3, R7)
claim("blog", "scored 54/81 on the same tasks: 30 tasks better and none worse, p = 1.9e-09", (b, g, l, f"{p:.1e}") == (54, 30, 0, "1.9e-09"), "R3 -> R7")
claim("readme", "the same build scored 54/81 on 2026-09-12, 30 tasks better and none worse", (b, g, l) == (54, 30, 0), "R3 -> R7")
claim("both", "(1,544 against 1,554)", (turns(R3), turns(R7)) == (1544, 1554), "R3, R7 turns")
depressed = (interrupted(R3), interrupted(R7)) == (63, 34) and f"{100 * (secs(R3) / secs(R7) - 1):.0f}" == "23"
claim("blog", "the watchdog interrupted 63 of its runs against 34, and it ran 23% longer", depressed, "R3, R7 rows")
claim("readme", "the watchdog interrupted 63 of R3's runs against 34, and R3 took 23% longer", depressed, "R3, R7 rows")
claim("blog", "the same line of builds scores 54/81 against the origin's 34/81", (passed(R7), passed(R5)) == (54, 34), "R7, R5")

# ------------------------------------------------------ the confirmation (R9/R10)
c9, c10 = pair(R9a, R9b), pair(R10a, R10b)
pool = [c9[i] + c10[i] for i in range(5)]
pp = mcnemar(pool[4], pool[3])
claim("both", {"blog": "**67/157 to 98/157**", "readme": "**67/157 -> 98/157**"}, pool[:3] == [157, 67, 98], "R9 + R10 paired")
row9 = (c9[:3], c9[3] - c9[4], f"{c9[5]:.2e}") == ((79, 31, 47), 16, "1.45e-04")
row10 = (c10[:3], c10[3] - c10[4], f"{c10[5]:.2e}") == ((78, 36, 51), 15, "6.10e-05")
claim("both", {"blog": "| R9 | 79 | 31 | **47** | +16 | 1.45e-04 |", "readme": "| R9 | 79 | 31 | **47** | **+16** | p = 1.45e-04 |"}, row9, "R9a vs R9b")
claim("both", {"blog": "| R10 | 78 | 36 | **51** | +15 | 6.10e-05 |", "readme": "| R10 | 78 | 36 | **51** | **+15** | p = 6.10e-05 |"}, row10, "R10a vs R10b")
claim("both", "7.92e-09", f"{pp:.2e}" == "7.92e-09", "R9 + R10 pooled McNemar")
claim("blog", "with 32 runs gained and 1 lost", (pool[3], pool[4]) == (32, 1), "R9 + R10 pooled")
rule_met = (min(c9[3] - c9[4], c10[3] - c10[4]) >= 10 and pp < 0.001
            and max(sum(not r.get("valid", True) for r in X.values()) for X in (R9a, R9b, R10a, R10b)) <= 3)
claim("blog", "each must gain at least 10 tasks net", rule_met, "the rule, applied to the raw rows")
raw_ok = (c9[0], c10[0], passed(R9a), passed(R10a), passed(R9b), passed(R10b)) == (79, 78, 32, 36, 47, 52)
claim("blog", "so R9 pairs 79 tasks and R10 pairs 78. Out of 81, the origin passed 32 and 36, and the shipped build passed 47 and 52", raw_ok, "raw vs paired")
claim("readme", "so R9 pairs 79 tasks and R10 pairs 78. Out of all 81, the origin build passed 32 and 36 and the shipped build 47 and 52", raw_ok, "raw vs paired")
pairs_ = [(A[t], Bb[t]) for A, Bb in ((R9a, R9b), (R10a, R10b)) for t in A if t in Bb and A[t].get("valid", True) and Bb[t].get("valid", True)]
h = [(x, y) for x, y in pairs_ if (x["turns"] or 0) == 0]
r_ = [(x, y) for x, y in pairs_ if (x["turns"] or 0) > 0]
gr, lr = sum(not x["passed"] and y["passed"] for x, y in r_), sum(x["passed"] and not y["passed"] for x, y in r_)
claim("blog", "On the 82 paired runs where the origin build recorded zero turns, the shipped build passed 28",
      len(h) == 82 and sum(y["passed"] for _, y in h) == 28, "R9 + R10 pairs, origin turns = 0")
claim("readme", "| 82 | 0 | **28** |", len(h) == 82 and sum(y["passed"] for _, y in h) == 28 and not any(x["passed"] for x, _ in h),
      "R9 + R10 pairs, origin turns = 0")
ran_c = (len(r_), sum(x["passed"] for x, _ in r_), sum(y["passed"] for _, y in r_), f"{mcnemar(lr, gr):.3f}") == (75, 67, 70, "0.375")
claim("blog", "the two builds passed 67 and 70 (p = 0.375)", ran_c, "R9 + R10 pairs, origin turns > 0")
claim("readme", "| 75 | 67 | 70 | not significant, p = 0.375 |", ran_c, "R9 + R10 pairs, origin turns > 0")
base = [r for X in (R9a, R10a) for r in X.values()]
best = [r for X in (R9b, R10b) for r in X.values()]
comp = lambda Z: (sum(bool(r["timed_out"]) for r in Z), sum(not r.get("valid", True) for r in Z), sum(r.get("valid", True) and not r["timed_out"] for r in Z))
bz, sz = [r for r in base if (r["turns"] or 0) == 0], [r for r in best if (r["turns"] or 0) == 0]
comp_ok = len(bz) == 86 and comp(bz) == (82, 3, 1) and sum(bool(r["timed_out"]) for r in base) == 84 and len(sz) == 3 and comp(sz) == (0, 2, 1)
claim("both", "86 zero-turn runs are 82 of its 84 timeouts, 3 harness errors and 1 run that was", comp_ok, "R9a + R10a rows")
claim("blog", "The shipped build's 3 are 2 harness errors and 1 graded run", comp_ok and not any(r["timed_out"] for r in best), "R9b + R10b rows")
fails = [r for r in base if not r["passed"]]
claim("blog", "84 of its 94 failed runs were timeouts the grader never saw", (len(fails), sum(bool(r["timed_out"]) for r in fails)) == (94, 84), "R9a + R10a")
claim("blog", "from 84 runs the harness killed without grading to none", sum(bool(r["timed_out"]) for r in base) == 84 and not any(r["timed_out"] for r in best), "R9/R10")
claim("blog", "about 6% less wall time", f"{100 * (1 - sum(r['duration_seconds'] for r in best) / sum(r['duration_seconds'] for r in base)):.0f}" == "6", "R9/R10 durations")
table = subprocess.run([sys.executable, str(B / "confirmation_table.py")], capture_output=True, text=True, check=True).stdout
lines = [l for l in table.strip().splitlines()]
claim("both", "| Tasks passed (162 runs) | 68 (42.0%) | **99 (61.1%)** |", all(norm(l) in DOCS["blog"] and norm(l) in DOCS["readme"] for l in lines),
      "every row printed by confirmation_table.py, in both documents")

# -------------------------------------------------------------- Terminal-Bench
tb = json.loads((B / "FINAL40_PAIRED_ANALYSIS.json").read_text())
ex = set(tb["unevaluable_trials"]["excluded_tasks"])
ev_ = {t: v for t, v in tb["per_task"].items() if t not in ex}
disc = (sum(v["baseline_reward"] >= 1 and v["final_reward"] < 1 for v in ev_.values()), sum(v["baseline_reward"] < 1 and v["final_reward"] >= 1 for v in ev_.values()))
tie = (len(ev_), sum(v["baseline_reward"] >= 1 for v in ev_.values()), sum(v["final_reward"] >= 1 for v in ev_.values()), mcnemar(*disc)) == (38, 26, 26, 1.0)
claim("blog", "the two builds tied, 26 against 26, p = 1.0", tie, "FINAL40 per_task, evaluable")
claim("readme", "26/38 against 26/38 evaluable tasks, p = 1.0", tie, "FINAL40 per_task, evaluable")
raw40 = (all(tb["per_task"][t]["baseline_reward"] >= 1 for t in ex)
         and (sum(v["baseline_reward"] >= 1 for v in tb["per_task"].values()), sum(v["final_reward"] >= 1 for v in tb["per_task"].values())) == (28, 26))
claim("both", "28/40 against 26/40", raw40, "FINAL40 per_task, all 40")
dt = lambda k: 100 * (1 - sum(v[f"final_{k}"] for v in ev_.values()) / sum(v[f"baseline_{k}"] for v in ev_.values()))
claim("both", "40% fewer turns and 34% less execution time", (f"{dt('turns'):.0f}", f"{dt('exec_s'):.0f}") == ("40", "34"), "FINAL40 per_task, evaluable")
claim("both", {"blog": "The two arms ran three days apart", "readme": "The origin arm ran on 2026-09-07 and `08a8d5d` on 2026-09-10"},
      "baseline 2026-09-07" in tb["protocol"]["run_dates"] and "final 2026-09-10" in tb["protocol"]["run_dates"], "FINAL40 protocol.run_dates")

# ------------------------------------------------------------------ Phase C
failing25 = {l.strip() for l in (B / "FAILING25.txt").read_text().splitlines() if l.strip() and not l.startswith("#")}
both_failed = {t for t in R9b if not R9b[t]["passed"] and R9b[t].get("valid", True) and t in R10b and not R10b[t]["passed"] and R10b[t].get("valid", True)}
claim("both", "25 tasks the shipped build failed in both confirmation replicates", len(failing25) == 25 and failing25 == both_failed, "FAILING25.txt vs R9b/R10b")
probe = proto(P["BP"])["task_timeout_seconds"] == 960 and passed(BP) == 7 and set(BP) == failing25
claim("blog", "960 seconds, and seven passed, which is MIXED", probe, "budget probe rows")
claim("readme", "(960 s) it passes 7 of them", probe, "budget probe rows")
q1, q2 = pair(S1, P1), pair(S2, P2)
claim("both", {"blog": "gained 2 across two replicates (p = 0.6875)", "readme": "moved +2 pooled, p = 0.6875"},
      ((q1[3] + q2[3]) - (q1[4] + q2[4]), f"{mcnemar(q1[4] + q2[4], q1[3] + q2[3]):.4f}") == (2, "0.6875"), "P3 shipped vs P3 arms")
sf = [r for X in (S1, S2) for r in X.values() if r.get("valid", True) and not r["passed"]]
bf = [r for r in BP.values() if r.get("valid", True) and not r["passed"]]
p3_ok = (sum(bool(r["agent_is_error"]) for r in sf), len(sf)) == (28, 41) and not any(r["timed_out"] for r in sf)
claim("blog", "the watchdog interrupted 28 of the shipped build's 41 failures in that run", p3_ok, "P3 shipped arms")
claim("readme", "the watchdog interrupted 28 of the shipped build's 41 failures", p3_ok, "P3 shipped arms")
bp_ok = (sum(bool(r["agent_is_error"]) for r in bf), len(bf)) == (8, 17)
claim("blog", "it interrupted 8 of the 17 failures", bp_ok, "budget probe failures")
claim("readme", "the watchdog interrupted 8 of them, and 9 finished and failed grading",
      bp_ok and sum(not r["agent_is_error"] and r["grader_returncode"] is not None for r in bf) == 9, "budget probe failures")
claim("both", {"blog": "P2, the Bash timeout clamp, was only ever measured inside the time-hints bundle (-4)",
               "readme": "P2, the Bash timeout clamp, was only ever measured inside the time-hints bundle (R7 -> R8, -4)"},
      "ADA_BASH_CLAMP_REMAINING" in agent and net(R7, R8) == -4, "agent.ts gate; R7 -> R8")

# -------------------------------------------------------------- T1.1 and time hints
t11 = json.loads((B / "T11_DEV12_PAIRED_ANALYSIS.json").read_text())
claim("blog", "none of the ten failing tasks it was written for", t11["e3_smoke_precursor"]["result"].startswith("0/10"), "T11_DEV12 e3_smoke_precursor")
claim("blog", "On a 12-task paired check it scored 2 against the control's 3",
      (t11["summary"]["n"], t11["summary"]["candidate_pass"], t11["summary"]["gateoff_pass"]) == (12, 2, 3), "T11_DEV12 summary")
guide = (ROOT / "ada/agent/system-guidance.ts").read_text()
smoke = (ROOT / "ada/evidence/t12/t12_smoke_a1_log.txt").read_text(encoding="utf-8", errors="replace")
claim("blog", "`⏱ 78 s of 120 s remain.`", "`⏱ ${remainingSec} s of ${budgetSec} s remain.`" in agent and "verbatim:\\n\\n> ⏱ 78 s of 120 s remain." in smoke,
      "agent.ts hint format; smoke log echo")
claim("blog", "| Time hints, wrap-up instruction, Bash timeout clamp (T1.2) | `agent/claude/agent.ts` | ships switched off |",
      '(process.env.ADA_TIME_HINTS ?? "0") === "1"' in agent and '(process.env.ADA_BASH_CLAMP_REMAINING ?? "0") === "1"' in agent, "agent.ts gate defaults")
claim("blog", "| \"Definition of done\" prompt section (T1.1) | `agent/system-guidance.ts` | ships switched off |",
      '(process.env.ADA_PROMPT_DOD ?? "0") === "1"' in guide, "system-guidance.ts gate default")

# --------------------------------------------------------------- charts and records
def desc(name):
    return re.search(r"<desc[^>]*>(.*?)</desc>", (B / "figures" / name).read_text(), re.S).group(1)


def outcomes(rs):
    c = {"passed": 0, "failed": 0, "timeout": 0, "error": 0}
    for r in rs:
        c["error" if not r.get("valid", True) else "timeout" if r["timed_out"] else "passed" if r["passed"] else "failed"] += 1
    return c


o, s_ = outcomes(base), outcomes(best)
fmt = lambda c: f"{c['passed']} passed, {c['failed']} failed after grading, {c['timeout']} timed out, {c['error']} harness errors"
claim("blog", "![Where the 162 runs of each build went](bench/figures/runs-by-outcome.svg)",
      desc("runs-by-outcome.svg") == f"Origin df0c537: {fmt(o)}. Shipped 5f4c5c0: {fmt(s_)}.", "runs-by-outcome.svg <desc> vs R9/R10 rows")
claim("blog", f"Origin: {fmt(o)}. Shipped: {fmt(s_)}.", True, "caption, same values as the <desc>")
claim("blog", "54 more runs fail after grading and 31 more pass", (s_["failed"] - o["failed"], s_["passed"] - o["passed"]) == (54, 31), "R9/R10 rows")
claim("blog", "![The control moved more than the change](bench/figures/control-moved.svg)",
      desc("control-moved.svg") == f"Hours apart, 2026-09-11: control R3 {passed(R3)}, candidate R4 {passed(R4)}, net {net(R3, R4):+d}. "
                                   f"Same day, 2026-09-12: control R7 {passed(R7)}, candidate R8 {passed(R8)}, net {net(R7, R8):+d}.",
      "control-moved.svg <desc> vs R3 R4 R7 R8 rows")
claim("blog", "the watchdog build scored 24 and the time-hints build 52: +28 net", (passed(R3), passed(R4), net(R3, R4)) == (24, 52, 28), "R3, R4")
claim("blog", "they scored 54 and 50: -4 net", (passed(R7), passed(R8), net(R7, R8)) == (54, 50, -4), "R7, R8")
claim("readme", "| R10a had 40 zero-turn rows (`bench/RUN_REGISTRY.md`) | 41,", len(zero(R10a)) == 41, "R10a rows")
f31_raw = json.loads((B / P["F31"]).read_text())
claim("readme", "rewrote one path field, `incumbent_source`",
      "autoresearcher/targets/ada/.autoresearch/diagnostics/manual/remaining81_incumbent.json" in json.dumps(f31_raw), "the raw file carries its original path again")

# ------------------------------------- figures restated elsewhere in each document
# An anchor only proves one sentence; every other sentence that repeats a figure gets its own.
pooled = pool[:3] == [157, 67, 98] and pool[3] - pool[4] == 31 and f"{pp:.2e}" == "7.92e-09"
hung_c = len(h) == 82 and sum(y["passed"] for _, y in h) == 28
claim("both", {"blog": "| **Pooled** | **157** | **67** | **98** | **+31** | **7.92e-09** |",
               "readme": "| **Pooled** | **157** | **67** | **98** | **+31** | **p = 7.92e-09** |"}, pooled, "R9 + R10 pooled")
claim("readme", "**67/157 → 98/157**, 32 gained and 1 lost", pooled and (pool[3], pool[4]) == (32, 1), "R9 + R10 pooled")
claim("readme", "On the 82 paired runs where it recorded zero turns, the shipped build passes 28. On the 75 where it ran, it is 67/75 → 70/75 (p = 0.375)",
      hung_c and ran_c, "R9 + R10 pairs split by origin turns")
claim("blog", "On the 75 where the origin build ran, the two builds passed 67 and 70 (p = 0.375)", ran_c, "R9 + R10 pairs, origin turns > 0")
claim("readme", "**Where the +31 comes from.** Split the 157 paired runs", pooled, "R9 + R10 pooled")
claim("blog", "took a coding agent from 67 to 98 passed runs out of 157", pooled, "R9 + R10 pooled")
claim("blog", "On SetupBench that took it from 67 to 98 passed runs out of 157", pooled, "R9 + R10 pooled")
claim("blog", "98/157 against 67/157 on paired runs", pooled, "R9 + R10 pooled")
claim("readme", "its other 2 timeouts had recorded turns. The shipped build's 3 are 2 harness errors and 1 graded run",
      comp_ok and sum(bool(r["timed_out"]) and (r["turns"] or 0) > 0 for r in base) == 2, "R9/R10 rows")
gained57 = {t for t in R5 if not R5[t]["passed"] and R7[t]["passed"]}
claim("readme", "All 21 of its conversions come from the 46 tasks", hung_ok and len(gained57) == 21 and gained57 <= set(hung), "R5 -> R7 gained tasks")
claim("both", "On the 35 tasks the origin build could actually run", ran_ok, "R5 tasks with turns")
r78 = (passed(R7), passed(R8), net(R7, R8), f"{pair(R7, R8)[5]:.2f}") == (54, 50, -4, "0.42")
claim("readme", "(−4, p = 0.42, inside the noise floor)", r78, "R7 -> R8")
claim("readme", "Same-day: **54/81 → 50/81**, −4, p = 0.42", r78, "R7 -> R8")
claim("blog", "scored 50/81 against 54/81. That −4 is inside the noise", r78, "R7 -> R8")
claim("readme", "Fresh and whole on one day: **54/81** against the origin build's **34/81** (R7 vs R5)", (passed(R7), passed(R5)) == (54, 34), "R7, R5")
claim("blog", "That 59 was assembled from 50 passes", hybrid, "R2 + failures31 rows")
_, _, _, g37, l37, _ = pair(R3, R7)
claim("readme", "The 24/81 control (R3) was a depressed run", passed(R3) == 24 and depressed, "R3, R7 rows")
claim("readme", "moved 30 tasks on the same build between one run and the next", (g37, l37) == (30, 0), "R3 -> R7")
claim("readme", "the +28 compared runs from different days", net(R3, R4) == 28, "R3 -> R4")
claim("readme", "the same build scored 54/81 the next day", passed(R7) == 54, "R7 rows")
claim("readme", "last written at 10:01 that day, which matches its summed task time",
      proto(P["R3"])["concurrency"] == 4 and abs(7 * 60 + 28 + secs(R3) / 4 / 60 - (10 * 60 + 1)) < 10,
      "R3: start 07:28 (run ID) plus summed task time over 4 slots")
claim("blog", "The withdrawn result's 24/81 was a control run of the watchdog build (R3)", passed(R3) == 24 and r3commit.startswith("6672af8"), "R3 rows")
claim("blog", "The 24/81 control was a depressed run", passed(R3) == 24 and depressed, "R3, R7 rows")
claim("blog", "A control that moves 30 tasks on its own cannot anchor a claim of 28", (g37, l37, net(R3, R4)) == (30, 0, 28), "R3 -> R7, R3 -> R4")
claim("blog", "the same build scored 24/81 and 54/81 a day apart", (passed(R3), passed(R7)) == (24, 54), "R3, R7 rows")
claim("blog", "The withdrawn comparison had p = 7.66e-07", f"{pair(R3, R4)[5]:.2e}" == "7.66e-07", "R3 -> R4")
z2_killed = sum(bool(r["timed_out"]) and r["grader_returncode"] is None for r in z2) == 2
claim("readme", "and 2 hung until the harness killed them", r2_ok and z2_killed, "R2 zero-turn rows")
claim("readme", "They were a reporting bug: 41 were graded and 19 passed. Only 2 were true force-kills", r2_ok and z2_killed, "R2 zero-turn rows")
claim("readme", "each replicate net ≥ +10; at most 3 invalid rows per arm per replicate",
      "net >= +10" in rule and "<= 3 invalid rows per arm" in rule, "run_baseline_vs_best.sh")
claim("readme", "on the 38 evaluable tasks", tie, "FINAL40 per_task, evaluable")
claim("blog", "On the remaining 38 the two builds tied", tie, "FINAL40 per_task, evaluable")
claim("blog", "on 40 public tasks", len(tb["per_task"]) == 40, "FINAL40 per_task")
tb_err = lambda arm: [v[f"{arm}_cost_usd"] for v in tb["per_task"].values() if v[f"{arm}_is_err"]]
claim("readme", "because a run killed at the hard cap records $0", all(c == 0 for c in tb_err("baseline")) and all(c > 0 for c in tb_err("final")),
      "FINAL40: the origin arm's hard-cap kills cost $0; 08a8d5d's watchdog stops report cost")
tb_logs = [(B / "results-ada-final-40").glob(f"*/{t}__*/verifier/test-stdout.txt") for t in ex]
tb_logs = [p.read_text() for g_ in tb_logs for p in g_]
claim("blog", "a package mirror returned 404 and a tool was missing",
      len(tb_logs) == len(ex) == 2 and all("404  Not Found" in s and "command not found" in s for s in tb_logs), "results-ada-final-40 verifier logs")
claim("blog", "At 960 seconds it interrupted 8 of the 17 failures, 30 seconds before the longer budget ran out", probe and bp_ok and cutoff_ok, "budget probe rows")
claim("readme", "8 of 17 failures in the 960 s probe", probe and bp_ok, "budget probe rows")
summary_c = (B / "PHASE_C_SUMMARY.md").read_text()
claim("readme", "Phase C found \"zero 480 s clock-outs\"", "zero 480 s clock-outs" in summary_c.lower(), "PHASE_C_SUMMARY.md")
claim("readme", "Phase C's \"17 hard clock-outs\"", "17 hard clock-outs" in summary_c and len(bf) == 17, "PHASE_C_SUMMARY.md; budget probe failures")
claim("blog", "thinking tokens took up to 93% of its output", "thinking tokens consuming up to 93% of output" in (ROOT / "ada/REPORT.md").read_text(),
      "ada/REPORT.md, the record it cites")
claim("blog", "taken here from the smoke test with its 120-second budget", "budget=120000ms" in smoke, "t12_smoke_a1_log.txt")
claim("readme", "These are the budget probe's 17 valid failures", bp_ok, "budget probe failures")
claim("readme", "R2's 43 zero-turn rows", r2_ok, "R2 zero-turn rows")
claim("blog", "the pooled exact McNemar test must reach p < 0.001", "p < 0.001" in rule and pp < 0.001, "run_baseline_vs_best.sh; R9 + R10 pooled")
claim("blog", "34% less execution time on the 38 tasks", tie and f"{dt('exec_s'):.0f}" == "34", "FINAL40 per_task, evaluable")

print(f"\n{'ALL DOCUMENT CLAIMS VERIFIED' if not FAILS else f'{len(FAILS)} CLAIM(S) FAILED'}")
sys.exit(1 if FAILS else 0)
