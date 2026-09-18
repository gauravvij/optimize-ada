#!/usr/bin/env python3
"""Every result stated in README.md, blog.md and bench/README.md, checked against the raw per-task diagnostics
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


DOCS = {"blog": norm((ROOT / "blog.md").read_text()), "readme": norm((ROOT / "README.md").read_text()),
        "guide": norm((ROOT / "bench/README.md").read_text())}
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
claim("blog", "`z-ai/glm-5.3-flash`", all(p["model"] == "z-ai/glm-5.3-flash" for p in conf), "R9/R10 protocol.model")
claim("blog", "480-second budget", all(p["task_timeout_seconds"] == 480 for p in conf), "R9/R10 protocol.task_timeout_seconds")
claim("blog", "used 81 of its tasks", all(len(p["tasks"]) == 81 for p in conf), "R9/R10 protocol.tasks")
claim("blog", "byte-identical to the one in `bench/harness/` in every run", all(p["runner_sha256"] == runner for p in conf),
      "protocol.runner_sha256 vs sha256(setupbench_ada_runner.ts)")
claim("blog", "matches none of the versions the runs recorded",
      evaluator not in {proto(p).get("evaluator_sha256") for p in P.values()}, "every run's protocol.evaluator_sha256 vs sha256(setupbench_ada_domain_eval.py)")
ev = (B / "harness/setupbench_ada_eval.py").read_text()
claim("blog", "timed out: the grader never runs",
      "if not timed_out:" in ev and ev.index("if not timed_out:") < ev.index('task["success_command"]'), "setupbench_ada_eval.py")
agent = (ROOT / "ada/agent/claude/agent.ts").read_text()
margin = re.search(r"ADA_DEADLINE_MARGIN_MS \?\? ([\d_]+)\)", agent)
cutoff_ok = (margin and int(margin.group(1).replace("_", "")) == 30000
             and "taskBudgetMs - deadlineMarginMs" in agent
             and all(r["duration_seconds"] >= 450 for k in ("R3", "R7", "R8", "R9b", "R10b", "S1", "S2") for r in R[k].values() if r["agent_is_error"])
             and all(r["duration_seconds"] >= 930 for r in BP.values() if r["agent_is_error"]))
claim("blog", "interrupts Ada 30 seconds before the budget runs out",
      cutoff_ok, "agent.ts ADA_DEADLINE_MARGIN_MS default; every interrupted row ends past the cut-off")
claim("blog", "450-second mark", cutoff_ok, "480 s budget minus the 30 s margin")
claim("blog", "The runs up to R8 ran four tasks at a time; the confirmation ran one task at a time per build",
      all(proto(P[k]).get("concurrency") == 4 for k in ("R1", "R2", "R3", "R4", "R5", "R7", "R8")) and all(p["concurrency"] == 1 for p in conf),
      "protocol.concurrency")
drv = (B / "baseline_vs_best_20260915T0825Z_driver.log").read_text()
rule = (B / "run_baseline_vs_best.sh").read_text()
claim("blog", "`bench/run_baseline_vs_best.sh`",
      "PRE-REGISTERED RULE (fixed before any spend)" in rule and "net >= +10" in rule and "p < 0.001" in rule
      and "rule: {'all_replicates_complete': True, 'each_replicate_net_ge_10': True, 'each_replicate_invalid_le_3': True, 'pooled_p_lt_0.001': True}" in drv,
      "the rule at the top of the driver script, applied in the run's log")

# ------------------------------------------------------------ R1, R2, Phase A
claim("blog", "(R1) passed 27 of 81 tasks and timed out on 53", passed(R1) == 27 and timeouts(R1) == 53, "R1 rows")
claim("blog", "Every timeout was a zero", all((r["turns"] or 0) == 0 for r in R1.values() if r["timed_out"]), "R1 timed-out rows")
claim("blog", "cut timeouts from 53 to 3", timeouts(R2) == 3, "R2 rows")
z2 = zero(R2)
r2_ok = len(z2) == 43 and sum(r["grader_returncode"] is not None for r in z2) == 41 and sum(r["passed"] for r in z2) == 19
claim("blog", "43 runs were recorded with zero turns, although 41 of them were still graded and 19 passed", r2_ok, "R2 zero-turn rows")
claim("blog", "neither full run of that build recorded a zero-turn run", not zero(R3) and not zero(R7), "R3, R7 rows")
hybrid = passed(R2) == 50 and len(F31) == 31 and set(F31) == {t for t in R2 if not R2[t]["passed"]} and passed(R2) + passed(F31) == 59
claim("blog", "Phase A's: 27/81 to 59/81", hybrid and passed(R1) == 27, "R1; R2 + re-run of its 31 failures")
claim("blog", "50 passes carried over from earlier runs plus a re-run of only the 31 failures", hybrid, "R2 + failures31 rows")

# ------------------------------------------------- the same-day ladder (R5 R7 R8)
_, _, _, g, l, p = pair(R5, R7)
claim("blog", "| Origin `df0c537` | nothing | 34/81 |", passed(R5) == 34 and len(R5) == 81, "R5 rows")
claim("blog", "**54/81** | **+20**, 21 gained / 1 lost, p = 1.1e-05",
      (g, l, f"{p:.1e}", passed(R7)) == (21, 1, "1.1e-05", 54), "R5 -> R7")
_, _, _, g, l, p = pair(R7, R8)
claim("blog", "50/81 | **-4**, 5 gained / 9 lost, p = 0.42",
      (g, l, f"{p:.2f}", passed(R8)) == (5, 9, "0.42", 50), "R7 -> R8")
to5 = [t for t in R5 if R5[t]["timed_out"]]
fin5 = [t for t in R5 if not R5[t]["timed_out"]]
gained57 = {t for t in R5 if not R5[t]["passed"] and R7[t]["passed"]}
to5_ok = len(to5) == 45 and sum(R7[t]["passed"] for t in to5) == 21 and len(gained57) == 21 and gained57 <= set(to5)
fin5_ok = (len(fin5) == 36 and [sum(X[t]["passed"] for t in fin5) for X in (R5, R7, R8)] == [34, 33, 30]
           and max(sum(X[t]["passed"] for t in fin5) for X in (R7, R8, R9b, R10b)) <= 34)
claim("blog", "the origin build timed out on 45 of the 81 tasks, and the watchdog build passed 21 of those 45", to5_ok, "R5 timed-out tasks, R7")
claim("blog", "On the 36 tasks the origin build finished in time, it had already passed 34, and nothing built since has improved on that",
      fin5_ok, "R5 finished tasks; R7 R8 R9b R10b")
mech = ((interrupted(R7), interrupted(R8)) == (34, 7) and f"{100 * (1 - turns(R8) / turns(R7)):.1f}" == "10.6"
        and f"{100 * (1 - secs(R8) / secs(R7)):.1f}" == "5.0")
claim("blog", "Runs interrupted by the watchdog fell from 34 to 7, turns fell 10.6%, and wall time fell 5.0%", mech, "R7, R8 rows")
claim("blog", "by 79%", f"{100 * (1 - interrupted(R8) / interrupted(R7)):.0f}" == "79", "R7 -> R8 interrupted runs")
clean = [t for t in R7 if not R7[t]["agent_is_error"]]
claim("blog", "On the 47 tasks where the watchdog build finished with time to spare, the time-hints build went from 42 passes to 37",
      len(clean) == 47 and sum(R7[t]["passed"] for t in clean) == 42 and sum(R8[t]["passed"] for t in clean) == 37, "R7 non-interrupted tasks")
said_done = lambda X: sum(not r["passed"] and not r["agent_is_error"] and r["grader_returncode"] is not None for r in X.values())
claim("blog", "Of the time-hints build's 31 failures, 25 ended", (said_done(R8), len(R8) - passed(R8)) == (25, 31), "R8 failures")
claim("blog", "For the watchdog build it was 5 of 27", (said_done(R7), len(R7) - passed(R7)) == (5, 27), "R7 failures")

# ------------------------------------------------------------ the withdrawn +28
_, _, _, g, l, p = pair(R3, R4)
claim("blog", "52/81 against 24/81, +28, p = 7.66e-07", (passed(R4), passed(R3), g - l, f"{p:.2e}") == (52, 24, 28, "7.66e-07"), "R3 -> R4")
ci = json.loads((B / "T12_REM81_PAIRED_ANALYSIS.json").read_text())["statistics"]["newcombe_95ci_diff"]
claim("blog", "95% confidence interval ran from +19 to +48 points", ci[0] > 0 and (round(100 * ci[0]), round(100 * ci[1])) == (19, 48),
      "T12_REM81_PAIRED_ANALYSIS.json statistics.newcombe_95ci_diff")
r3commit = json.loads((B / P["R3"]).read_text())["workspace_commit"]
_, _, b, g, l, p = pair(R3, R7)
claim("blog", "scored 54/81 on the same tasks: 30 tasks better and none worse, p = 1.9e-09", (b, g, l, f"{p:.1e}") == (54, 30, 0, "1.9e-09"), "R3 -> R7")
claim("blog", "(1,544 against 1,554)", (turns(R3), turns(R7)) == (1544, 1554), "R3, R7 turns")
depressed = (interrupted(R3), interrupted(R7)) == (63, 34) and f"{100 * (secs(R3) / secs(R7) - 1):.0f}" == "23"
claim("blog", "the watchdog interrupted 63 of its runs against 34, and it ran 23% longer", depressed, "R3, R7 rows")
claim("blog", "the same line of builds scores 54/81 against the origin's 34/81", (passed(R7), passed(R5)) == (54, 34), "R7, R5")

# ------------------------------------------------------ the confirmation (R9/R10)
c9, c10 = pair(R9a, R9b), pair(R10a, R10b)
pool = [c9[i] + c10[i] for i in range(5)]
pp = mcnemar(pool[4], pool[3])
claim("blog", "**67/157 to 98/157**", pool[:3] == [157, 67, 98], "R9 + R10 paired")
row9 = (c9[:3], c9[3] - c9[4], f"{c9[5]:.2e}") == ((79, 31, 47), 16, "1.45e-04")
row10 = (c10[:3], c10[3] - c10[4], f"{c10[5]:.2e}") == ((78, 36, 51), 15, "6.10e-05")
claim("blog", "| R9 | 79 | 31 | **47** | +16 | 1.45e-04 |", row9, "R9a vs R9b")
claim("blog", "| R10 | 78 | 36 | **51** | +15 | 6.10e-05 |", row10, "R10a vs R10b")
claim("blog", "7.92e-09", f"{pp:.2e}" == "7.92e-09", "R9 + R10 pooled McNemar")
claim("blog", "with 32 runs gained and 1 lost", (pool[3], pool[4]) == (32, 1), "R9 + R10 pooled")
rule_met = (min(c9[3] - c9[4], c10[3] - c10[4]) >= 10 and pp < 0.001
            and max(sum(not r.get("valid", True) for r in X.values()) for X in (R9a, R9b, R10a, R10b)) <= 3)
claim("blog", "each must gain at least 10 tasks net", rule_met, "the rule, applied to the raw rows")
raw_ok = (c9[0], c10[0], passed(R9a), passed(R10a), passed(R9b), passed(R10b)) == (79, 78, 32, 36, 47, 52)
claim("blog", "so R9 pairs 79 tasks and R10 pairs 78. Out of 81, the origin passed 32 and 36, and the shipped build passed 47 and 52", raw_ok, "raw vs paired")
pairs_ = [(A[t], Bb[t]) for A, Bb in ((R9a, R9b), (R10a, R10b)) for t in A if t in Bb and A[t].get("valid", True) and Bb[t].get("valid", True)]
tp = [(x, y) for x, y in pairs_ if x["timed_out"]]
fp = [(x, y) for x, y in pairs_ if not x["timed_out"]]
gf, lf = sum(not x["passed"] and y["passed"] for x, y in fp), sum(x["passed"] and not y["passed"] for x, y in fp)
split_to = (len(tp), sum(x["passed"] for x, _ in tp), sum(y["passed"] for _, y in tp),
            sum(y["passed"] and bool(y["agent_is_error"]) for _, y in tp), sum(y["passed"] and not y["agent_is_error"] for _, y in tp)) == (83, 0, 29, 18, 11)
split_fin = (len(fp), sum(x["passed"] for x, _ in fp), sum(y["passed"] for _, y in fp), gf, lf, f"{mcnemar(lf, gf):.3f}") == (74, 67, 69, 3, 1, "0.625")
claim("blog", "Where the origin build timed out (83 pairs), it passed none, and the shipped build passed 29. In 18 of those 29 the watchdog stopped Ada and the check still passed; in the other 11, Ada finished in time on its own.",
      split_to, "R9 + R10 pairs, origin timed out")
claim("blog", "Where the origin build finished in time (74 pairs), both builds passed about the same number: 67 and 69.", split_fin, "R9 + R10 pairs, origin finished; p = 0.625")
claim("blog", "The extra passes come from tasks the original build ran out of time on. On tasks it already finished in time, both builds did about equally well.",
      split_to and split_fin and pool[:3] == [157, 67, 98], "R9 + R10 pairs split by the origin attempt")
base = [r for X in (R9a, R10a) for r in X.values()]
best = [r for X in (R9b, R10b) for r in X.values()]
comp = lambda Z: (sum(bool(r["timed_out"]) for r in Z), sum(not r.get("valid", True) for r in Z), sum(r.get("valid", True) and not r["timed_out"] for r in Z))
fails = [r for r in base if not r["passed"]]
claim("blog", "84 of its 94 failed runs were timeouts the grader never saw", (len(fails), sum(bool(r["timed_out"]) for r in fails)) == (94, 84), "R9a + R10a")
claim("blog", "from 84 runs the harness killed without grading to none", sum(bool(r["timed_out"]) for r in base) == 84 and not any(r["timed_out"] for r in best), "R9/R10")
table = subprocess.run([sys.executable, str(B / "confirmation_table.py")], capture_output=True, text=True, check=True).stdout
lines = [l for l in table.strip().splitlines()]
claim("both", "| Passed, out of 162 | 68 (42.0%) | **99 (61.1%)** |", all(norm(l) in DOCS["blog"] and norm(l) in DOCS["readme"] for l in lines),
      "every row printed by confirmation_table.py, in both documents")

# -------------------------------------------------------------- Terminal-Bench
tb = json.loads((B / "FINAL40_PAIRED_ANALYSIS.json").read_text())
ex = set(tb["unevaluable_trials"]["excluded_tasks"])
ev_ = {t: v for t, v in tb["per_task"].items() if t not in ex}
disc = (sum(v["baseline_reward"] >= 1 and v["final_reward"] < 1 for v in ev_.values()), sum(v["baseline_reward"] < 1 and v["final_reward"] >= 1 for v in ev_.values()))
tie = (len(ev_), sum(v["baseline_reward"] >= 1 for v in ev_.values()), sum(v["final_reward"] >= 1 for v in ev_.values()), mcnemar(*disc)) == (38, 26, 26, 1.0)
claim("blog", "the two builds tied, 26 against 26, p = 1.0", tie, "FINAL40 per_task, evaluable")
raw40 = (all(tb["per_task"][t]["baseline_reward"] >= 1 for t in ex)
         and (sum(v["baseline_reward"] >= 1 for v in tb["per_task"].values()), sum(v["final_reward"] >= 1 for v in tb["per_task"].values())) == (28, 26))
claim("blog", "28/40 against 26/40", raw40, "FINAL40 per_task, all 40")
dt = lambda k: 100 * (1 - sum(v[f"final_{k}"] for v in ev_.values()) / sum(v[f"baseline_{k}"] for v in ev_.values()))
claim("blog", "40% fewer turns and 34% less execution time", (f"{dt('turns'):.0f}", f"{dt('exec_s'):.0f}") == ("40", "34"), "FINAL40 per_task, evaluable")
claim("blog", "The two arms ran three days apart",
      "baseline 2026-09-07" in tb["protocol"]["run_dates"] and "final 2026-09-10" in tb["protocol"]["run_dates"], "FINAL40 protocol.run_dates")

# ------------------------------------------------------------------ Phase C
failing25 = {l.strip() for l in (B / "FAILING25.txt").read_text().splitlines() if l.strip() and not l.startswith("#")}
both_failed = {t for t in R9b if not R9b[t]["passed"] and R9b[t].get("valid", True) and t in R10b and not R10b[t]["passed"] and R10b[t].get("valid", True)}
claim("blog", "25 tasks the shipped build failed in both confirmation replicates", len(failing25) == 25 and failing25 == both_failed, "FAILING25.txt vs R9b/R10b")
probe = proto(P["BP"])["task_timeout_seconds"] == 960 and passed(BP) == 7 and set(BP) == failing25
claim("blog", "960 seconds, and seven passed, which is MIXED", probe, "budget probe rows")
q1, q2 = pair(S1, P1), pair(S2, P2)
claim("blog", "gained 2 across two replicates (p = 0.6875)",
      ((q1[3] + q2[3]) - (q1[4] + q2[4]), f"{mcnemar(q1[4] + q2[4], q1[3] + q2[3]):.4f}") == (2, "0.6875"), "P3 shipped vs P3 arms")
sf = [r for X in (S1, S2) for r in X.values() if r.get("valid", True) and not r["passed"]]
bf = [r for r in BP.values() if r.get("valid", True) and not r["passed"]]
p3_ok = (sum(bool(r["agent_is_error"]) for r in sf), len(sf)) == (28, 41) and not any(r["timed_out"] for r in sf)
claim("blog", "the watchdog interrupted 28 of the shipped build's 41 failures in that run", p3_ok, "P3 shipped arms")
bp_ok = (sum(bool(r["agent_is_error"]) for r in bf), len(bf)) == (8, 17)
claim("blog", "it interrupted 8 of the 17 failures", bp_ok, "budget probe failures")
claim("blog", "P2, the Bash timeout clamp, was only ever measured inside the time-hints bundle (-4)",
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
      desc("control-moved.svg") == f"Separate runs: control R3 {passed(R3)}, candidate R4 {passed(R4)}, net {net(R3, R4):+d}. "
                                   f"Same day, 2026-09-12: control R7 {passed(R7)}, candidate R8 {passed(R8)}, net {net(R7, R8):+d}.",
      "control-moved.svg <desc> vs R3 R4 R7 R8 rows")
claim("blog", "the watchdog build scored 24 and the time-hints build 52: +28 net", (passed(R3), passed(R4), net(R3, R4)) == (24, 52, 28), "R3, R4")
claim("blog", "they scored 54 and 50: -4 net", (passed(R7), passed(R8), net(R7, R8)) == (54, 50, -4), "R7, R8")
f31_raw = json.loads((B / P["F31"]).read_text())

# ------------------------------------- figures restated elsewhere in each document
# An anchor only proves one sentence; every other sentence that repeats a figure gets its own.
pooled = pool[:3] == [157, 67, 98] and pool[3] - pool[4] == 31 and f"{pp:.2e}" == "7.92e-09"
claim("blog", "| **Pooled** | **157** | **67** | **98** | **+31** | **7.92e-09** |", pooled, "R9 + R10 pooled")
claim("blog", "took a coding agent from 67 to 98 passed runs out of 157", pooled, "R9 + R10 pooled")
claim("blog", "the shipped build went from 67 to 98 passed runs out of 157 on SetupBench", pooled, "R9 + R10 pooled")
claim("blog", "It also went from 84 runs the harness killed without grading to none", sum(bool(r["timed_out"]) for r in base) == 84 and not any(r["timed_out"] for r in best), "R9/R10")
claim("blog", "98/157 against 67/157 on paired runs", pooled, "R9 + R10 pooled")
r78 = (passed(R7), passed(R8), net(R7, R8), f"{pair(R7, R8)[5]:.2f}") == (54, 50, -4, "0.42")
claim("blog", "scored 50/81 against 54/81. That −4 is inside the noise", r78, "R7 -> R8")
claim("blog", "That 59 was assembled from 50 passes", hybrid, "R2 + failures31 rows")
_, _, _, g37, l37, _ = pair(R3, R7)
claim("blog", "The withdrawn result's 24/81 was a control run of the watchdog build (R3)", passed(R3) == 24 and r3commit.startswith("6672af8"), "R3 rows")
claim("blog", "The 24/81 control was a depressed run", passed(R3) == 24 and depressed, "R3, R7 rows")
claim("blog", "A control that moves 30 tasks on its own cannot anchor a claim of 28", (g37, l37, net(R3, R4)) == (30, 0, 28), "R3 -> R7, R3 -> R4")
claim("blog", "the same build scored 24/81 and 54/81 on different days", (passed(R3), passed(R7)) == (24, 54) and "20260912" in P["R7"], "R3, R7 rows")
claim("blog", "The withdrawn comparison had p = 7.66e-07", f"{pair(R3, R4)[5]:.2e}" == "7.66e-07", "R3 -> R4")
z2_killed = sum(bool(r["timed_out"]) and r["grader_returncode"] is None for r in z2) == 2
claim("blog", "On the remaining 38 the two builds tied", tie, "FINAL40 per_task, evaluable")
claim("blog", "on 40 public tasks", len(tb["per_task"]) == 40, "FINAL40 per_task")
tb_err = lambda arm: [v[f"{arm}_cost_usd"] for v in tb["per_task"].values() if v[f"{arm}_is_err"]]
tb_logs = [(B / "results-ada-final-40").glob(f"*/{t}__*/verifier/test-stdout.txt") for t in ex]
tb_logs = [p.read_text() for g_ in tb_logs for p in g_]
claim("blog", "a package mirror returned 404 and a tool was missing",
      len(tb_logs) == len(ex) == 2 and all("404  Not Found" in s and "command not found" in s for s in tb_logs), "results-ada-final-40 verifier logs")
claim("blog", "At 960 seconds it interrupted 8 of the 17 failures, 30 seconds before the longer budget ran out", probe and bp_ok and cutoff_ok, "budget probe rows")
summary_c = (B / "PHASE_C_SUMMARY.md").read_text()
claim("blog", "thinking tokens took up to 93% of its output", "thinking tokens consuming up to 93% of output" in (ROOT / "ada/REPORT.md").read_text(),
      "ada/REPORT.md, the record it cites")
origin_runs = [json.loads((B / P[k]).read_text()) for k in ("R1", "R5", "R9a", "R10a")]
claim("blog", "taken here from the smoke test with its 120-second budget", "budget=120000ms" in smoke, "t12_smoke_a1_log.txt")
claim("blog", "the pooled exact McNemar test must reach p < 0.001", "p < 0.001" in rule and pp < 0.001, "run_baseline_vs_best.sh; R9 + R10 pooled")
claim("blog", "34% less execution time on the 38 tasks", tie and f"{dt('exec_s'):.0f}" == "34", "FINAL40 per_task, evaluable")

# ------------------------------------------------------------------- the README
# Each check anchors one statement of README.md, in the order the README makes them.
RM = "readme"
timeouts_ok = sum(bool(r["timed_out"]) for r in base) == 84 and not any(r["timed_out"] for r in best)
unchecked_timeouts = all(r["grader_returncode"] is None and not r["passed"] for r in base + best if r["timed_out"])
watchdog_checked = all(r["grader_returncode"] is not None for r in best if r["agent_is_error"]) and sum(r["passed"] for r in best if r["agent_is_error"]) == 23
no_origin_watchdog = not any(r["agent_is_error"] for r in base)
invalid = [r for r in base + best if not r.get("valid", True)]
off = ('(process.env.ADA_TIME_HINTS ?? "0") === "1"' in agent and '(process.env.ADA_BASH_CLAMP_REMAINING ?? "0") === "1"' in agent
       and '(process.env.ADA_PROMPT_DOD ?? "0") === "1"' in guide and "process.env.ADA_STALL_RETRIES ?? 0)" in agent)
claim(RM, "Run side by side on the same tasks, the shipped build passed **98 of 157** attempts", pooled, "R9 + R10 pooled")
claim(RM, "the **origin build**, passed **67 of 157** (p = 7.92e-09)", pooled, "R9 + R10 pooled")
claim(RM, "The origin build ran out of time on **84 of its 162** attempts. The shipped build never did.", timeouts_ok, "R9/R10 timed_out")
claim(RM, "The extra passes come from tasks the origin build ran out of time on. On tasks it already finished in time, both builds did about equally well.",
      split_to and split_fin and pooled, "R9 + R10 pairs split by the origin attempt: 0 -> 29 of 83; 67 -> 69 of 74, p = 0.625")
claim(RM, "If Ada is still working at 480 seconds, the harness stops it and **never runs the check**", unchecked_timeouts, "timed-out rows have no check result")
claim(RM, "The origin build ran out of time on 40 to 53 of the 81 tasks, depending on the run",
      (min(map(timeouts, (R1, R5, R9a, R10a))), max(map(timeouts, (R1, R5, R9a, R10a)))) == (40, 53), "origin runs R1 R5 R9a R10a")
evaluator_src = (B / "harness/setupbench_ada_eval.py").read_text()
routing = ('"ANTHROPIC_BASE_URL=https://openrouter.ai/api"' in evaluator_src and '"ANTHROPIC_MODEL=z-ai/glm-5.3-flash"' in evaluator_src
           and "from setupbench_ada_eval import" in (B / "harness/setupbench_ada_domain_eval.py").read_text()
           and "model: resolveModel()" in (B / "harness/setupbench_ada_runner.ts").read_text()
           and "env.ANTHROPIC_MODEL ??" in (ROOT / "ada/agent/config/model.ts").read_text())
usage_models, usage_records = set(), 0
for f in [*(B / "diagnostics").rglob("*.json"), *(B / "p3_evidence").rglob("*.json"), *B.glob("results-*/**/*.*"), *(ROOT / "ada/evidence").rglob("*.*")]:
    if not f.is_file() or f.suffix not in (".json", ".jsonl", ".log", ".txt"):
        continue
    text = f.read_text(errors="replace")
    for body in (text, text.replace('\\"', '"')):
        for m in re.finditer(r'"modelUsage"\s*:\s*', body):
            try:
                obj, _ = json.JSONDecoder().raw_decode(body, m.end())
            except ValueError:
                continue
            if isinstance(obj, dict) and obj:
                usage_records += 1
                usage_models |= set(obj)
claim(RM, "The harness points the SDK at OpenRouter and sets the model to `z-ai/glm-5.3-flash`. Every model-usage record the runs saved names only that model",
      routing and usage_records > 800 and usage_models == {"z-ai/glm-5.3-flash"}, f"harness env; {usage_records} saved model-usage records")
claim(RM, "A timer inside Ada that stops it 30 seconds before the time limit: at 450 s of 480 s, counting from when the container started", cutoff_ok, "agent.ts margin; interrupted rows")
claim(RM, "ones that adapt to the time limit Ada is given", "process.env.ADA_RUNNER_TIMEOUT_MS" in guide, "system-guidance.ts reads the time limit")
claim(RM, "`MAX_THINKING_TOKENS`, of 1,024 tokens by default", 'MAX_THINKING_TOKENS: process.env.MAX_THINKING_TOKENS ?? "1024"' in agent, "agent.ts default")
claim(RM, "| 450 s | keeps working | the watchdog stops Ada, and Ada exits normally |", no_origin_watchdog and cutoff_ok, "R9a/R10a: no watchdog stops")
claim(RM, "| **Is the task checked?** | **No: it counts as a fail** | **Yes: it can still pass** |", unchecked_timeouts and watchdog_checked, "R9/R10 rows")
claim(RM, "Three more changes are in the code but switched off by default", off, "agent.ts and system-guidance.ts gate defaults")
claim(RM, "Ada was still working at 480 s, so the harness stopped it and the check never ran", unchecked_timeouts, "timed-out rows")
claim(RM, "The shipped build's watchdog stopped Ada at 450 s. The check then ran.", watchdog_checked and cutoff_ok, "watchdog-stopped rows have a check result")
claim(RM, "The harness itself failed during the attempt, so there is no result",
      len(invalid) == 5 and all(r["harness_error"] and r["grader_returncode"] is None for r in invalid), "R9/R10 invalid rows")
claim(RM, "Within each replicate the two builds ran at the same time on the same machine",
      "REPLICATE 1/2 both arms concurrently" in drv and re.search(r"REPLICATE 2/2 launched \(pids \d+ \d+\)", drv) is not None, "driver log")
claim(RM, "| R9 | 79 | 31 | **47** | 17 | 1 | 1.45e-04 |", c9[:5] == (79, 31, 47, 17, 1) and f"{c9[5]:.2e}" == "1.45e-04", "R9a vs R9b")
claim(RM, "| R10 | 78 | 36 | **51** | 15 | 0 | 6.10e-05 |", c10[:5] == (78, 36, 51, 15, 0) and f"{c10[5]:.2e}" == "6.10e-05", "R10a vs R10b")
claim(RM, "| **Both** | **157** | **67** | **98** | **32** | **1** | **7.92e-09** |", pooled and (pool[3], pool[4]) == (32, 1), "R9 + R10 pooled")
claim(RM, "There are fewer than 81 pairs per replicate because pairs with a harness error are left out", (c9[0], c10[0]) == (79, 78) and len(invalid) == 5, "R9/R10 pairs")
claim(RM, "([`bench/run_baseline_vs_best.sh`](bench/run_baseline_vs_best.sh)). The run's log shows the script checking it at the end",
      "PRE-REGISTERED RULE" in rule and "rule: {'all_replicates_complete': True, 'each_replicate_net_ge_10': True, 'each_replicate_invalid_le_3': True, 'pooled_p_lt_0.001': True}" in drv,
      "rule in the script; its application in the log")
claim(RM, "| Both replicates finish | Yes |", "REP_1_DONE" in drv and "REP_2_DONE" in drv, "driver log")
claim(RM, "| In each replicate, at least 10 more pairs gained than lost | Yes: 16 and 15 |", "net >= +10" in rule and (c9[3] - c9[4], c10[3] - c10[4]) == (16, 15), "rule; R9, R10")
claim(RM, "| In each replicate, at most 3 harness errors per build | Yes: at most 2 |",
      "<= 3 invalid rows per arm" in rule and max(sum(not r.get("valid", True) for r in X.values()) for X in (R9a, R9b, R10a, R10b)) == 2, "rule; R9/R10 rows")
claim(RM, "| Over both replicates, p below 0.001 | Yes: 7.92e-09 |", "p < 0.001" in rule and pooled, "rule; pooled")
claim(RM, "| Timed out | 83 | 0 | **29** |", split_to, "R9 + R10 pairs, origin timed out")
claim(RM, "| Finished in time | 74 | 67 | 69 |", split_fin, "R9 + R10 pairs, origin finished")
claim(RM, "Where the origin build timed out (83 pairs), it passed none, and the shipped build passed 29. In 18 of those 29 the watchdog stopped Ada and the check still passed; in the other 11 Ada finished in time on its own.",
      split_to, "R9 + R10 pairs, origin timed out")
claim(RM, "Where the origin build finished in time (74 pairs), both builds passed about the same number: 67 and 69.", split_fin, "R9 + R10 pairs, origin finished; p = 0.625")
claim(RM, "| Origin (`df0c537`) | 34/81 |", passed(R5) == 34, "R5")
claim(RM, "| Plus the four changes above (`6672af8`) | **54/81** | 21 gained, 1 lost, p = 1.1e-05 |",
      (pair(R5, R7)[3], pair(R5, R7)[4], f"{pair(R5, R7)[5]:.1e}", passed(R7)) == (21, 1, "1.1e-05", 54), "R5 -> R7")
claim(RM, "| Plus time reminders (`2e495bb`) | 50/81 | 5 gained, 9 lost, p = 0.42 |", (pair(R7, R8)[3], pair(R7, R8)[4], passed(R8)) == (5, 9, 50) and r78, "R7 -> R8")
claim(RM, "All 21 tasks gained in the second row were tasks the origin build had timed out on", to5_ok, "R5 timed-out tasks, R7")
claim(RM, "the watchdog had to stop Ada 7 times instead of 34, but passes fell from 54 to 50", (interrupted(R7), interrupted(R8)) == (34, 7) and r78, "R7, R8")
claim(RM, "| Early watchdog work (Phase A): 59/81 against 27/81 | Built from one run's 50 passes plus a re-run of only its 31 failures.", hybrid and passed(R1) == 27, "R1; R2 + failures31")
claim(RM, "| 54/81 (with the four changes) against 34/81, both builds on one day |", (passed(R7), passed(R5)) == (54, 34), "R7, R5")
claim(RM, "| Time reminders: 52/81 against 24/81, p = 7.66e-07 |", (passed(R4), passed(R3), f"{pair(R3, R4)[5]:.2e}") == (52, 24, "7.66e-07"), "R3 -> R4")
r7commit = json.loads((B / P["R7"]).read_text())["workspace_commit"]
claim(RM, "The 24/81 comparison run (R3) was run separately, before the time-reminders run. The same build scored 54/81 on 2026-09-12.",
      passed(R3) == 24 and P["R3"].split("/")[1] < P["R4"].split("/")[1] and r3commit == r7commit and passed(R7) == 54, "R3, R4 run IDs; R3 and R7 record one commit")
claim(RM, "| 50/81 against 54/81, both builds on one day |", r78, "R7 -> R8")
claim(RM, "the same build passed 30 more tasks in one run than in another", (g37, l37) == (30, 0), "R3 -> R7")
claim(RM, "tied the origin build: 26 against 26 of 38 tasks", tie, "FINAL40 per_task, evaluable")
claim(RM, "Two more tasks were left out because the benchmark's own checker broke; the origin build had passed both",
      len(ex) == 2 and all(tb["per_task"][x]["baseline_reward"] >= 1 for x in ex) and len(tb_logs) == 2
      and all("404  Not Found" in s and "command not found" in s for s in tb_logs), "FINAL40; results-ada-final-40 verifier logs")
claim(RM, "The two builds also ran on different days", "baseline 2026-09-07" in tb["protocol"]["run_dates"] and "final 2026-09-10" in tb["protocol"]["run_dates"], "FINAL40 protocol.run_dates")
claim(RM, "25 tasks failed in both replicates for the shipped build. With twice the time (960 s), it passed 7 of them.",
      len(failing25) == 25 and failing25 == both_failed and probe, "FAILING25.txt; budget probe rows")
claim(RM, "gained 2 pairs net. It was rejected by its own rule (p = 0.6875)",
      ((q1[3] + q2[3]) - (q1[4] + q2[4]), f"{mcnemar(q1[4] + q2[4], q1[3] + q2[3]):.4f}") == (2, "0.6875"), "P3 shipped vs P3 arms")
claim(RM, "Timeouts fell from 53 of 81 to 3.", (timeouts(R1), timeouts(R2)) == (53, 3), "R1, R2")
claim(RM, "| 98/157 against 67/157 |", pooled, "R9 + R10 pooled")
claim(RM, "| Model | `z-ai/glm-5.3-flash` through OpenRouter |", all(q["model"] == "z-ai/glm-5.3-flash" for q in conf), "R9/R10 protocol.model")
claim(RM, "| Benchmark | SetupBench at `041a412`, 81 tasks |", all(q["setupbench_commit"].startswith("041a412") and len(q["tasks"]) == 81 for q in conf), "R9/R10 protocol")
claim(RM, "| Time limits | 480 s for Ada, 600 s for the check |",
      all((q["task_timeout_seconds"], q["grader_timeout_seconds"]) == (480, 600) for q in conf), "R9/R10 protocol")
claim(RM, "R9/R10 ran it as `417a8f1`", all(json.loads((B / P[k]).read_text())["workspace_commit"].startswith("417a8f1") for k in ("R9a", "R10a")), "R9a/R10a workspace_commit")

# -------------------------------------------------------- the file guide, bench/README.md
GD = "guide"
origin_runs = [json.loads((B / P[k]).read_text()) for k in ("R1", "R5", "R9a", "R10a")]
claim(GD, "R1 and R5 ran `df0c537` with one uncommitted file, `agent/system-guidance.ts`; R9/R10 record `417a8f1` with none",
      [(j["workspace_commit"][:7], j["changed_paths"]) for j in origin_runs] == [("df0c537", ["agent/system-guidance.ts"])] * 2 + [("417a8f1", [])] * 2,
      "R1 R5 R9a R10a workspace_commit, changed_paths")
claim(GD, "`df8a18c09278`, is recorded in the results", all(j["agent_tree"].startswith("df8a18c09278") for j in origin_runs[2:]), "R9a/R10a agent_tree")
claim(GD, "byte-identical to the runner every run recorded", all(q["runner_sha256"] == runner for q in conf), "protocol.runner_sha256")
claim(GD, "It matches no `evaluator_sha256` that a run recorded", evaluator not in {proto(v).get("evaluator_sha256") for v in P.values()}, "every run's protocol")
explo = [json.loads((B / "harness" / f).read_text())["protocol"] for f in ("SETUPBENCH_ADA_RAW.json", "ADA_HOLDOUT_5X_RAW.json")]
claim(GD, "exploratory evaluation of Ada at commit `0c5e1da` (not in the bundle), with a 600 s limit",
      all("0c5e1da" in json.dumps(q) and ("timeout_seconds" in q and q["timeout_seconds"] == 600 or q.get("variant_timeout_seconds") == 600) for q in explo), "the two protocols")
claim(GD, "Of the 29 passes recovered where the origin build timed out, 18 came after a watchdog stop and 11 did not involve the watchdog", split_to, "R9 + R10 pairs")
claim(GD, "whose commit time in `ada-campaign.bundle` is 07:24 UTC on **2026-09-11**", r3commit.startswith("6672af8"), "R3 workspace_commit (commit time: bash bench/verify_builds.sh)")
claim(GD, "the +28 compared runs from different days", net(R3, R4) == 28, "R3 -> R4")
claim(GD, "its arms were not run together, and the same build scored 54/81 on 2026-09-12", passed(R7) == 54 and r3commit == r7commit, "R3, R7")
claim(GD, "Almost the same number of turns, or model responses (1,544 against 1,554), but the watchdog stopped 63 of R3's attempts against 34, and R3 took 23% longer in total",
      (turns(R3), turns(R7)) == (1544, 1554) and depressed, "R3, R7 rows")
claim(GD, "Phase C found \"zero 480 s clock-outs\"", "zero 480 s clock-outs" in summary_c.lower(), "PHASE_C_SUMMARY.md")
claim(GD, "the watchdog stopped 28 of the shipped build's 41 failed attempts in the P3 run, and 8 of 17 failed attempts at 960 s", p3_ok and bp_ok, "P3 shipped arms; budget probe")
claim(GD, "P2 was only ever measured inside the time-reminders bundle (T1.2)", "ADA_BASH_CLAMP_REMAINING" in agent and net(R7, R8) == -4, "agent.ts gate; R7 -> R8")
claim(GD, "Phase C's \"17 hard clock-outs\"", "17 hard clock-outs" in summary_c and len(bf) == 17, "PHASE_C_SUMMARY.md; budget probe")
claim(GD, "These are the 960-second run's 17 failed attempts without a harness error: the watchdog stopped 8 of them, and 9 finished and failed their check",
      bp_ok and sum(not r["agent_is_error"] and r["grader_returncode"] is not None for r in bf) == 9, "budget probe failures")
claim(GD, "R2's 43 zero-turn attempts", r2_ok, "R2 zero-turn rows")
claim(GD, "They were a reporting bug: 41 were checked and 19 passed. Only 2 were stopped by the harness", r2_ok and z2_killed, "R2 zero-turn rows")
claim(GD, "| R10a had 40 zero-turn attempts (`RUN_REGISTRY.md`) | 41,", len(zero(R10a)) == 41, "R10a rows")
claim(GD, "The origin build ran on 2026-09-07 and `08a8d5d` on 2026-09-10", "baseline 2026-09-07" in tb["protocol"]["run_dates"] and "final 2026-09-10" in tb["protocol"]["run_dates"], "FINAL40 protocol.run_dates")
claim(GD, "rewrote one path field, `incumbent_source`",
      "autoresearcher/targets/ada/.autoresearch/diagnostics/manual/remaining81_incumbent.json" in json.dumps(f31_raw), "the raw file carries its original path again")

print(f"\n{'ALL DOCUMENT CLAIMS VERIFIED' if not FAILS else f'{len(FAILS)} CLAIM(S) FAILED'}")
sys.exit(1 if FAILS else 0)
