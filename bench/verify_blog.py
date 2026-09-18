#!/usr/bin/env python3
"""Every figure in blog.md, recomputed from the raw per-task diagnostics.

Each check asserts two things: the blog states the claim in these exact words, and
the raw data produces exactly that value. Editing the blog or the data without the
other fails the check. Definitions match bench/ctrl_vs_t12_verify.py: a run
"interrupted at the deadline" has agent_is_error set; a paired comparison uses only
tasks where both runs returned a valid row. Standard library only:

    python3 bench/verify_blog.py
"""
import hashlib
import json
import sys
from math import comb
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "bench/diagnostics").is_dir())
B, D = ROOT / "bench", ROOT / "bench/diagnostics"
BLOG = (ROOT / "blog.md").read_text()
FAILS = []


def claim(text, ok, source):
    """The blog must contain `text`, and the data must make `ok` true."""
    stated = text in BLOG
    good = stated and bool(ok)
    FAILS.extend([] if good else [text])
    why = "" if good else ("  [not in blog.md]" if not stated else "  [data disagrees]")
    print(f"{'PASS' if good else 'FAIL'}  {text[:88]}  <- {source}{why}")


def rows(rel):
    return {r["task_id"]: r for r in json.loads((B / rel).read_text())["results"]}


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

# ---------------------------------------------------------------- the runs
R1 = rows("diagnostics/ada-baseline/manual/remaining81_baseline.json")
R2 = rows("diagnostics/manual/remaining81_incumbent.json")
F31 = rows("diagnostics/manual/remaining81_final_failures31.json")
R3 = rows("diagnostics/20260910T0728Z-t04ctrl/0.json")
R4 = rows("diagnostics/20260911T1540Z-t12rem81/rem81_t12_candidate.json")
R5 = rows("diagnostics/ada-baseline/20260912T1031Z-frem81base/0.json")
R7 = rows("diagnostics/ada-t01gateoff/20260912T1603Z-t04ctrl2/0.json")
R8 = rows("diagnostics/20260912T1603Z-t12cand2/0.json")
R9a, R10a = rows("diagnostics/ada-baseline/20260915T0825Z-r1-base/0.json"), rows("diagnostics/ada-baseline/20260915T0825Z-r2-base/0.json")
R9b, R10b = rows("diagnostics/20260915T0825Z-r1-best/0.json"), rows("diagnostics/20260915T0825Z-r2-best/0.json")
BP = rows("diagnostics/budget-probe-20260916T0730Z/0.json")
S1, S2 = rows("diagnostics/20260917T0602Z-r1-shipped/0.json"), rows("diagnostics/20260917T0602Z-r2-shipped/0.json")
P1, P2 = rows("p3_evidence/20260917T0602Z-r1-p3/0.json"), rows("p3_evidence/20260917T0602Z-r2-p3/0.json")

# ------------------------------------------------ what the harness recorded
proto = [json.loads((D / p).read_text())["protocol"] for p in (
    "ada-baseline/20260915T0825Z-r1-base/0.json", "ada-baseline/20260915T0825Z-r2-base/0.json",
    "20260915T0825Z-r1-best/0.json", "20260915T0825Z-r2-best/0.json")]
runner = hashlib.sha256((B / "harness/setupbench_ada_runner.ts").read_bytes()).hexdigest()
evaluator = hashlib.sha256((B / "harness/setupbench_ada_domain_eval.py").read_bytes()).hexdigest()
claim("`z-ai/glm-5.3-flash`", all(p["model"] == "z-ai/glm-5.3-flash" for p in proto), "R9/R10 protocol.model")
claim("each with a 480-second budget", all(p["task_timeout_seconds"] == 480 for p in proto), "R9/R10 protocol.task_timeout_seconds")
claim("The campaign used 81 of its tasks", all(len(p["tasks"]) == 81 for p in proto), "R9/R10 protocol.tasks")
claim("is byte-identical to the one in `bench/harness/` in every run",
      all(p["runner_sha256"] == runner for p in proto), "protocol.runner_sha256 vs sha256(setupbench_ada_runner.ts)")
claim("the one in `bench/harness/` is a later revision",
      all(p["evaluator_sha256"] != evaluator for p in proto), "protocol.evaluator_sha256 vs sha256(setupbench_ada_domain_eval.py)")
ev = (B / "harness/setupbench_ada_eval.py").read_text()
claim("deadline passes first          ──► timed out: the grader never runs",
      "if not timed_out:" in ev and ev.index("if not timed_out:") < ev.index('task["success_command"]'),
      "setupbench_ada_eval.py: grader runs only when not timed_out")

# ------------------------------------------------------ R1, R2, Phase A
claim("(R1) passed 27 of 81 tasks and timed out on 53", passed(R1) == 27 and timeouts(R1) == 53, "R1 rows")
claim("Every timeout was a zero", all((r["turns"] or 0) == 0 for r in R1.values() if r["timed_out"]), "R1 timed-out rows")
claim("An early watchdog build cut timeouts from 53 to 3", timeouts(R2) == 3, "R2 rows")
z2 = zero(R2)
claim("43 runs were recorded with zero turns, although 41 of them were still graded and 19 passed",
      len(z2) == 43 and sum(r["grader_returncode"] is not None for r in z2) == 41 and sum(r["passed"] for r in z2) == 19,
      "R2 zero-turn rows")
claim("neither full run of that build recorded a zero-turn run", not zero(R3) and not zero(R7), "R3, R7 rows")
claim("The first headline to go was Phase A's: 27/81 to 59/81",
      passed(R1) == 27 and passed(R2) + passed(F31) == 59, "R1; R2 50 + re-run of 31 failures")
claim("That 59 was assembled from 50 passes carried over from earlier runs plus a re-run of only the 31 failures",
      passed(R2) == 50 and len(F31) == 31 and set(F31) == {t for t in R2 if not R2[t]["passed"]}, "R2 + failures31 rows")

# ------------------------------------------------ the same-day ladder (R5 R7 R8)
n, a, b, g, l, p = pair(R5, R7)
claim("| Origin `df0c537` | — | 34/81 | — |", passed(R5) == 34 and len(R5) == 81, "R5 rows")
claim("**+20**, 21 gained / 1 lost, p = 1.1e-05", (g, l, f"{p:.1e}") == (21, 1, "1.1e-05") and passed(R7) == 54, "R5 -> R7")
n, a, b, g, l, p = pair(R7, R8)
claim("**−4**, 5 gained / 9 lost, p = 0.42", (g, l, f"{p:.2f}") == (5, 9, "0.42") and passed(R8) == 50, "R7 -> R8")
hung = [t for t in R5 if (R5[t]["turns"] or 0) == 0]
ran = [t for t in R5 if (R5[t]["turns"] or 0) > 0]
claim("the origin build produced zero turns on 46 of the 81 tasks. The watchdog build passed 21 of those 46",
      len(hung) == 46 and sum(R7[t]["passed"] for t in hung) == 21, "R5 zero-turn tasks, R7 passes")
claim("On the 35 tasks the origin build could actually run, it had already passed 34, and nothing built since has improved on that",
      len(ran) == 35 and sum(R5[t]["passed"] for t in ran) == 34
      and max(sum(R[t]["passed"] for t in ran) for R in (R7, R8, R9b, R10b)) <= 34, "R5 ran tasks; R7 R8 R9b R10b")
claim("Runs cut off at the deadline fell from 34 to 7, turns fell 10.6%, and wall time fell 5.0%",
      (interrupted(R7), interrupted(R8)) == (34, 7) and f"{100 * (1 - turns(R8) / turns(R7)):.1f}" == "10.6"
      and f"{100 * (1 - secs(R8) / secs(R7)):.1f}" == "5.0", "R7, R8 rows")
clean = [t for t in R7 if not R7[t]["agent_is_error"]]
claim("on the 47 tasks where the watchdog build finished with time to spare, the time-hints build went from 42 passes to 37",
      len(clean) == 47 and sum(R7[t]["passed"] for t in clean) == 42 and sum(R8[t]["passed"] for t in clean) == 37,
      "R7 non-interrupted tasks")
said_done = lambda R: sum(not r["passed"] and not r["agent_is_error"] and r["grader_returncode"] is not None for r in R.values())
claim("25 of 31 ended with Ada announcing the task was done while the grader's command failed, against 5 of 27",
      (said_done(R8), len(R8) - passed(R8), said_done(R7), len(R7) - passed(R7)) == (25, 31, 5, 27), "R8, R7 failures")
claim("cut runs interrupted at the deadline by 79%", f"{100 * (1 - interrupted(R8) / interrupted(R7)):.0f}" == "79", "R7 -> R8")

# ------------------------------------------------------- the withdrawn +28
n, a, b, g, l, p = pair(R3, R4)
claim("**52/81 against 24/81, +28, p = 7.66e-07**", (passed(R4), passed(R3), g - l, f"{p:.2e}") == (52, 24, 28, "7.66e-07"), "R3 -> R4")
claim("The withdrawn comparison had p = 7.66e-07", f"{p:.2e}" == "7.66e-07", "R3 -> R4")
claim("but the commit it records", json.loads((D / "20260910T0728Z-t04ctrl/0.json").read_text())["workspace_commit"].startswith("6672af8"),
      "R3 workspace_commit (commit date: git log -1 --format=%cI 6672af8 after fetching bench/ada-campaign.bundle)")
n, a, b, g, l, p = pair(R3, R7)
claim("scored 54/81 — 30 tasks better and none worse, p = 1.9e-09", (b, g, l, f"{p:.1e}") == (54, 30, 0, "1.9e-09"), "R3 -> R7")
claim("(1,544 against 1,554)", (turns(R3), turns(R7)) == (1544, 1554), "R3, R7 turns")
claim("it hit the deadline on 63 runs against 34 and ran 23% longer",
      (interrupted(R3), interrupted(R7)) == (63, 34) and f"{100 * (secs(R3) / secs(R7) - 1):.0f}" == "23", "R3, R7 rows")
claim("Run fresh and whole on one day, the same line of builds scores 54/81 against the origin's 34/81",
      (passed(R7), passed(R5)) == (54, 34), "R7, R5")

# ---------------------------------------------- the confirmation (R9 + R10)
c9, c10 = pair(R9a, R9b), pair(R10a, R10b)
pool = [c9[i] + c10[i] for i in range(5)]
pp = mcnemar(pool[4], pool[3])
claim("**67/157 to 98/157**", pool[:3] == [157, 67, 98], "R9 + R10 paired")
claim("| R9 | 79 | 31 | **47** | +16 | 1.45e-04 |", (c9[:3], c9[3] - c9[4], f"{c9[5]:.2e}") == ((79, 31, 47), 16, "1.45e-04"), "R9a vs R9b")
claim("| R10 | 78 | 36 | **51** | +15 | 6.10e-05 |", (c10[:3], c10[3] - c10[4], f"{c10[5]:.2e}") == ((78, 36, 51), 15, "6.10e-05"), "R10a vs R10b")
claim("| **Pooled** | **157** | **67** | **98** | **+31** | **7.92e-09** |", f"{pp:.2e}" == "7.92e-09", "R9 + R10 pooled")
claim("32 runs were gained and 1 was lost", (pool[3], pool[4]) == (32, 1), "R9 + R10 pooled")
claim("each must gain at least 10 tasks net, neither arm may lose more than three rows to harness errors, and the pooled exact McNemar test must reach p < 0.001",
      min(c9[3] - c9[4], c10[3] - c10[4]) >= 10 and pp < 0.001
      and max(sum(not r.get("valid", True) for r in R.values()) for R in (R9a, R9b, R10a, R10b)) <= 3, "the pre-registered rule")
hz = [(a, b) for a, b in ((R9a, R9b), (R10a, R10b))]
zz = [(t, A, Bb) for A, Bb in hz for t in A if t in Bb and A[t].get("valid", True) and Bb[t].get("valid", True)]
h = [(A[t], Bb[t]) for t, A, Bb in zz if (A[t]["turns"] or 0) == 0]
r_ = [(A[t], Bb[t]) for t, A, Bb in zz if (A[t]["turns"] or 0) > 0]
gr, lr = sum(not x["passed"] and y["passed"] for x, y in r_), sum(x["passed"] and not y["passed"] for x, y in r_)
claim("On the 82 paired runs where the origin build recorded zero turns",
      len(h) == 82 and sum(y["passed"] for _, y in h) == 28, "R9 + R10 pairs, origin turns = 0")
claim("the two builds passed 67 and 70 — p = 0.375",
      (len(r_), sum(x["passed"] for x, _ in r_), sum(y["passed"] for _, y in r_), f"{mcnemar(lr, gr):.3f}") == (75, 67, 70, "0.375"),
      "R9 + R10 pairs, origin turns > 0")
base, best = {**{("9", t): r for t, r in R9a.items()}, **{("10", t): r for t, r in R10a.items()}}, \
             {**{("9", t): r for t, r in R9b.items()}, **{("10", t): r for t, r in R10b.items()}}
bz, sz = [r for r in base.values() if (r["turns"] or 0) == 0], [r for r in best.values() if (r["turns"] or 0) == 0]
comp = lambda Z: (sum(bool(r["timed_out"]) for r in Z), sum(not r.get("valid", True) for r in Z),
                  sum(r.get("valid", True) and not r["timed_out"] for r in Z))
claim("86 zero-turn runs are 82 of its 84 timeouts, 3 harness errors and 1 run that was graded",
      len(bz) == 86 and comp(bz) == (82, 3, 1) and sum(bool(r["timed_out"]) for r in base.values()) == 84, "R9a + R10a rows")
claim("The shipped build's 3 are 2 harness errors and 1 graded run; none of its runs was killed by the clock",
      len(sz) == 3 and comp(sz) == (0, 2, 1) and not any(r["timed_out"] for r in best.values()), "R9b + R10b rows")
fails = [r for r in base.values() if not r["passed"]]
claim("84 of its 94 failed runs in the confirmation were timeouts the grader never saw",
      len(fails) == 94 and sum(bool(r["timed_out"]) for r in fails) == 84, "R9a + R10a failures")
claim("from 84 runs the harness killed without grading to none",
      sum(bool(r["timed_out"]) for r in base.values()) == 84 and not any(r["timed_out"] for r in best.values()), "R9/R10 timeouts")
claim("It also used about 6% less wall time", f"{100 * (1 - sum(r['duration_seconds'] for r in best.values()) / sum(r['duration_seconds'] for r in base.values())):.0f}" == "6",
      "R9/R10 summed durations")
import subprocess
table = subprocess.run([sys.executable, str(B / "confirmation_table.py")], capture_output=True, text=True, check=True).stdout
claim("| Tasks passed (162 runs) | 68 (42.0%) | **99 (61.1%)** |",
      all(line in BLOG for line in table.strip().splitlines()), "every row printed by confirmation_table.py appears in blog.md")

# ------------------------------------------------------------- T1.1
t11 = json.loads((B / "T11_DEV12_PAIRED_ANALYSIS.json").read_text())
claim("It converted none of the ten failing tasks it was written for",
      t11["e3_smoke_precursor"]["result"].startswith("0/10"), "T11_DEV12_PAIRED_ANALYSIS.json e3_smoke_precursor")
claim("on a 12-task paired check it scored 2 against the control's 3",
      (t11["summary"]["n"], t11["summary"]["candidate_pass"], t11["summary"]["gateoff_pass"]) == (12, 2, 3), "T11_DEV12 summary")

# ------------------------------------------------ the time hints in the code
agent = (ROOT / "ada/agent/claude/agent.ts").read_text()
guide = (ROOT / "ada/agent/system-guidance.ts").read_text()
smoke = (ROOT / "ada/evidence/t12/t12_smoke_a1_log.txt").read_text(encoding="utf-8", errors="replace")
claim("a hook inserts a line such as `⏱ 78 s of 120 s remain.`",
      "`⏱ ${remainingSec} s of ${budgetSec} s remain.`" in agent and "⏱ 78 s of 120 s remain." in smoke, "agent.ts hint format; smoke log")
claim("the model repeated the hint word for word", "verbatim:\\n\\n> ⏱ 78 s of 120 s remain." in smoke, "t12_smoke_a1_log.txt")
claim("| Time hints, wrap-up instruction, Bash timeout clamp (T1.2) | `agent/claude/agent.ts` | ships switched off |",
      '(process.env.ADA_TIME_HINTS ?? "0") === "1"' in agent and '(process.env.ADA_BASH_CLAMP_REMAINING ?? "0") === "1"' in agent,
      "agent.ts gate defaults")
claim("| \"Definition of done\" prompt section (T1.1) | `agent/system-guidance.ts` | ships switched off |",
      '(process.env.ADA_PROMPT_DOD ?? "0") === "1"' in guide, "system-guidance.ts gate default")

# ------------------------------------------------------------ Terminal-Bench
tb = json.loads((B / "FINAL40_PAIRED_ANALYSIS.json").read_text())
ex = set(tb["unevaluable_trials"]["excluded_tasks"])
ev_ = {t: v for t, v in tb["per_task"].items() if t not in ex}
bp_, fp_ = (sum(v[k] >= 1.0 for v in ev_.values()) for k in ("baseline_reward", "final_reward"))
disc = (sum(v["baseline_reward"] >= 1 and v["final_reward"] < 1 for v in ev_.values()),
        sum(v["baseline_reward"] < 1 and v["final_reward"] >= 1 for v in ev_.values()))
claim("On the remaining 38 the two builds tied, 26 against 26, p = 1.0",
      (len(ev_), bp_, fp_, mcnemar(*disc)) == (38, 26, 26, 1.0), "FINAL40 per_task, evaluable")
claim("Both were origin passes, so the raw count is 28/40 against 26/40",
      all(tb["per_task"][t]["baseline_reward"] >= 1 for t in ex)
      and (sum(v["baseline_reward"] >= 1 for v in tb["per_task"].values()), sum(v["final_reward"] >= 1 for v in tb["per_task"].values())) == (28, 26),
      "FINAL40 per_task, all 40")
dt = lambda k: 100 * (1 - sum(v[f"final_{k}"] for v in ev_.values()) / sum(v[f"baseline_{k}"] for v in ev_.values()))
claim("with 40% fewer turns and 34% less execution time on the 38 tasks", (f"{dt('turns'):.0f}", f"{dt('exec_s'):.0f}") == ("40", "34"),
      "FINAL40 per_task, evaluable")
claim("The two arms were run three days apart", "2026-09-07" in tb["protocol"]["run_dates"] and "final 2026-09-10" in tb["protocol"]["run_dates"],
      "FINAL40 protocol.run_dates")

# ------------------------------------------------------------------ Phase C
failing25 = {l.strip() for l in (B / "FAILING25.txt").read_text().splitlines() if l.strip() and not l.startswith("#")}
both = {t for t in R9b if not R9b[t]["passed"] and R9b[t].get("valid", True) and t in R10b and not R10b[t]["passed"] and R10b[t].get("valid", True)}
claim("the 25 tasks the shipped build failed in both confirmation replicates", len(failing25) == 25 and failing25 == both,
      "FAILING25.txt vs R9b/R10b failures")
bp_proto = json.loads((D / "budget-probe-20260916T0730Z/0.json").read_text())["protocol"]
claim("It re-ran them at twice the budget, 960 seconds. Seven passed",
      bp_proto["task_timeout_seconds"] == 960 and passed(BP) == 7 and set(BP) == failing25, "budget probe rows")
q1, q2 = pair(S1, P1), pair(S2, P2)
claim("gained 2 across two replicates (p = 0.6875)",
      ((q1[3] + q2[3]) - (q1[4] + q2[4]), f"{mcnemar(q1[4] + q2[4], q1[3] + q2[3]):.4f}") == (2, "0.6875"), "P3 shipped vs p3 arms")
sf = [r for R in (S1, S2) for r in R.values() if r.get("valid", True) and not r["passed"]]
bf = [r for r in BP.values() if r.get("valid", True) and not r["passed"]]
claim("28 of the shipped build's 41 failures in that run were stopped at the deadline",
      (sum(bool(r["agent_is_error"]) for r in sf), len(sf)) == (28, 41) and not any(r["timed_out"] for r in sf), "P3 shipped arms")
claim("8 of the 17 failures at 960 seconds still ran out of time", (sum(bool(r["agent_is_error"]) for r in bf), len(bf)) == (8, 17),
      "budget probe failures")

# ------------------------------------------------------------------ the charts
# The SVGs are published without the script that drew them; each one's <desc> states the
# values it plots, so check those against the raw rows, and the captions against the same.
import re


def desc(name):
    return re.search(r"<desc[^>]*>(.*?)</desc>", (B / "figures" / name).read_text(), re.S).group(1)


def outcomes(*runs):
    c = {"passed": 0, "failed": 0, "timeout": 0, "error": 0}
    for R in runs:
        for r in R.values():
            k = "error" if not r.get("valid", True) else "timeout" if r["timed_out"] else "passed" if r["passed"] else "failed"
            c[k] += 1
    return c


o, s_ = outcomes(R9a, R10a), outcomes(R9b, R10b)
fmt = lambda c: f"{c['passed']} passed, {c['failed']} failed after grading, {c['timeout']} timed out, {c['error']} harness errors"
claim("![Where the 162 runs of each build went](bench/figures/runs-by-outcome.svg)",
      desc("runs-by-outcome.svg") == f"Origin df0c537: {fmt(o)}. Shipped 5f4c5c0: {fmt(s_)}.", "runs-by-outcome.svg <desc> vs R9/R10 rows")
claim(f"Origin: {fmt(o)}. Shipped: {fmt(s_)}.", sum(o.values()) == sum(s_.values()) == 162, "caption vs R9/R10 rows")
claim("54 more runs fail after grading and 31 more pass", (s_["failed"] - o["failed"], s_["passed"] - o["passed"]) == (54, 31),
      "R9/R10 rows")
nt = lambda a, b: pair(a, b)[3] - pair(a, b)[4]
claim("![The control moved more than the change](bench/figures/control-moved.svg)",
      desc("control-moved.svg") == f"Hours apart, 2026-09-11: control R3 {passed(R3)}, candidate R4 {passed(R4)}, net {nt(R3, R4):+d}. "
                                   f"Same day, 2026-09-12: control R7 {passed(R7)}, candidate R8 {passed(R8)}, net {nt(R7, R8):+d}.",
      "control-moved.svg <desc> vs R3 R4 R7 R8 rows")
claim("the watchdog build scored 24 and the time-hints build 52: +28 net", (passed(R3), passed(R4), nt(R3, R4)) == (24, 52, 28), "R3, R4")
claim("they scored 54 and 50: −4 net", (passed(R7), passed(R8), nt(R7, R8)) == (54, 50, -4), "R7, R8")

print(f"\n{'ALL BLOG CLAIMS VERIFIED' if not FAILS else f'{len(FAILS)} CLAIM(S) FAILED'}")
sys.exit(1 if FAILS else 0)
