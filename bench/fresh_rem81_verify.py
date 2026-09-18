#!/usr/bin/env python3
"""Machine verification of FRESH_REM81_REPORT.md against the raw artifacts.

Re-derives every figure in the report from the two run logs and the three
diagnostics files, independently of fresh_rem81_analysis.py, then asserts the
analysis JSON and the report text both agree with that derivation.

Run: python3 bench/fresh_rem81_verify.py   (exit 0 = all green)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "bench/diagnostics").is_dir())  # repo root, wherever it is cloned
BENCH = ROOT / "bench"
DIAG = ROOT / "bench/diagnostics"  # archived 2026-09-18 from the former autoresearcher workspaces

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(cond), detail))


LINE = re.compile(r"^task=(\S+) pass=(\d) valid=(\d) timeout=(\d) turns=(\d+)")


def from_log(p: Path) -> dict[str, dict]:
    out = {}
    for line in p.read_text().splitlines():
        m = LINE.match(line)
        if m:
            out[m.group(1)] = dict(passed=m.group(2) == "1", valid=m.group(3) == "1",
                                   timed_out=m.group(4) == "1", turns=int(m.group(5)))
    return out


def from_diag(p: Path) -> dict[str, dict]:
    return {r["task_id"]: r for r in json.loads(p.read_text())["results"]}


base = from_log(BENCH / "fresh_rem81_baseline.log")
best = from_log(BENCH / "fresh_rem81_best.log")
base_diag = from_diag(DIAG / "ada-baseline/20260912T1031Z-frem81base/0.json")
t12_11 = from_diag(DIAG / "20260911T1540Z-t12rem81/rem81_t12_candidate.json")
ctrl_10 = from_diag(DIAG / "20260910T0728Z-t04ctrl/0.json")
J = json.loads((BENCH / "FRESH_REM81_PAIRED_ANALYSIS.json").read_text())
REPORT = (BENCH / "FRESH_REM81_REPORT.md").read_text()

# --- raw arm facts -----------------------------------------------------------
check("arm1 log has 81 rows", len(base) == 81, str(len(base)))
check("arm2 log has 81 rows", len(best) == 81, str(len(best)))
check("arm1 has 0 invalid rows", sum(not r["valid"] for r in base.values()) == 0)
check("arm2 has 7 invalid rows", sum(not r["valid"] for r in best.values()) == 7)
check("arm1 diagnostics summary is 34/81, 45 timeouts",
      json.loads((DIAG / "ada-baseline/20260912T1031Z-frem81base/0.json").read_text())
      ["summary"] == {"passed": 34, "total": 81, "timeouts": 45, "turns": 750})
check("arm2 wrote no diagnostics",
      not list(DIAG.glob("**/*frem81best*")))
check("arm1 workspace_commit is df0c537",
      json.loads((DIAG / "ada-baseline/20260912T1031Z-frem81base/0.json").read_text())
      ["workspace_commit"].startswith("df0c537"))

# --- unevaluable set ---------------------------------------------------------
uneval = sorted(t for t in base if not base[t]["valid"] or not best[t]["valid"])
tasks = sorted(t for t in base if t not in uneval)
check("7 unevaluable, n=74 paired", len(uneval) == 7 and len(tasks) == 74,
      f"{len(uneval)}/{len(tasks)}")
check("analysis JSON lists the same unevaluable set",
      J["unevaluable_trials"]["excluded_tasks"] == uneval)
check("all 7 unevaluable are arm-2-only",
      all(base[t]["valid"] for t in uneval))
for t in uneval:
    check(f"report names unevaluable task {t}", t in REPORT)

# --- primary contrast --------------------------------------------------------
kb = sum(base[t]["passed"] for t in tasks)
kc = sum(best[t]["passed"] for t in tasks)
b = sum(1 for t in tasks if base[t]["passed"] and not best[t]["passed"])
c = sum(1 for t in tasks if not base[t]["passed"] and best[t]["passed"])
check("primary is 31 -> 43", (kb, kc) == (31, 43), f"{kb} -> {kc}")
check("primary flips are 15 gained / 3 lost", (c, b) == (15, 3), f"{c}/{b}")
check("analysis JSON primary agrees",
      (J["primary"]["a_pass"], J["primary"]["b_pass"],
       J["primary"]["mcnemar_exact"]["c_a_fail_b_pass"],
       J["primary"]["mcnemar_exact"]["b_a_pass_b_fail"]) == (31, 43, 15, 3))
check("report states 31/74 -> 43/74", "31/74 → **43/74**" in REPORT)

# --- the decisive split ------------------------------------------------------
hung = [t for t in tasks if base[t]["timed_out"]]
ran = [t for t in tasks if not base[t]["timed_out"]]
check("41 hung / 33 ran", (len(hung), len(ran)) == (41, 33), f"{len(hung)}/{len(ran)}")
check("every baseline timeout in the paired set has turns=0",
      all(base[t]["turns"] == 0 for t in hung))
check("baseline passes 0 of the hung subset", sum(base[t]["passed"] for t in hung) == 0)
check("T1.2 passes 15 of the hung subset", sum(best[t]["passed"] for t in hung) == 15)
check("ALL 15 conversions lie in the hung subset",
      sum(1 for t in hung if not base[t]["passed"] and best[t]["passed"]) == c == 15)
check("zero conversions in the ran subset",
      sum(1 for t in ran if not base[t]["passed"] and best[t]["passed"]) == 0)
check("ran subset is 31 -> 28",
      (sum(base[t]["passed"] for t in ran), sum(best[t]["passed"] for t in ran)) == (31, 28))
check("T1.2 has 0 timeouts in the paired set",
      sum(best[t]["timed_out"] for t in tasks) == 0)
check("report states 15 of 15 conversions", "15 of 15 conversions" in REPORT)

# --- noise floor -------------------------------------------------------------
k11 = sum(bool(t12_11[t]["passed"]) for t in tasks)
d11 = sum(1 for t in tasks if bool(t12_11[t]["passed"]) != best[t]["passed"])
down = sum(1 for t in tasks if t12_11[t]["passed"] and not best[t]["passed"])
up = sum(1 for t in tasks if not t12_11[t]["passed"] and best[t]["passed"])
check("same build scores 46 then 43 on the 74", (k11, kc) == (46, 43), f"{k11}/{kc}")
check("15 tasks flip between the two same-build runs", d11 == 15, str(d11))
check("flips are 9 down / 6 up", (down, up) == (9, 6), f"{down}/{up}")
check("20% flip rate as stated", round(d11 / len(tasks) * 100) == 20)
check("report states 46/74 and 43/74", "46/74 → 43/74" in REPORT)

# --- published claim restricted ---------------------------------------------
kctrl = sum(bool(ctrl_10[t]["passed"]) for t in tasks)
pb = sum(1 for t in tasks if ctrl_10[t]["passed"] and not t12_11[t]["passed"])
pc = sum(1 for t in tasks if not ctrl_10[t]["passed"] and t12_11[t]["passed"])
check("restricted published claim is 22 -> 46", (kctrl, k11) == (22, 46), f"{kctrl}/{k11}")
check("restricted flips are 27 gained / 3 lost", (pc, pb) == (27, 3), f"{pc}/{pb}")
check("restricted discordance exceeds the noise floor", pc + pb > d11, f"{pc+pb} vs {d11}")

# --- task types --------------------------------------------------------------
tt = {}
for t in tasks:
    tt.setdefault(base_diag[t]["task_type"], []).append(t)
for name, exp in [("reposetup", (44, 16, 25)), ("dependency_resolution", (13, 1, 4)),
                  ("dbsetup", (13, 10, 10)), ("bgsetup", (4, 4, 4))]:
    sub = tt[name]
    got = (len(sub), sum(base[t]["passed"] for t in sub), sum(best[t]["passed"] for t in sub))
    check(f"task type {name} is n={exp[0]} {exp[1]}->{exp[2]}", got == exp, str(got))

# --- turns -------------------------------------------------------------------
check("paired turns 708 baseline vs 1284 T1.2",
      (sum(base[t]["turns"] for t in tasks), sum(best[t]["turns"] for t in tasks)) == (708, 1284))

# --- control integrity ------------------------------------------------------
kc10 = sum(bool(ctrl_10[t]["passed"]) for t in ran)
kb12 = sum(base[t]["passed"] for t in ran)
cb = sum(1 for t in ran if ctrl_10[t]["passed"] and not base[t]["passed"])
cc = sum(1 for t in ran if not ctrl_10[t]["passed"] and base[t]["passed"])
check("control 6672af8 scores 13/33 where df0c537 scores 31/33",
      (kc10, kb12) == (13, 31), f"{kc10}/{kb12}")
check("control loses 18 and wins 0 against its own ancestor", (cc, cb) == (18, 0), f"{cc}/{cb}")
check("neither arm timed out on that subset",
      sum(ctrl_10[t]["timed_out"] for t in ran) == 0 and sum(base[t]["timed_out"] for t in ran) == 0)
check("analysis JSON records the control as suspect",
      J["control_integrity"]["verdict"].startswith("CONTROL IS SUSPECT"))
check("report states the 18-0 result", "18 / 0" in REPORT and "18\u20130" in REPORT)
check("report no longer claims the promoted result simply survives",
      "Does the promoted claim survive?" not in REPORT)
check("report lists the inflated effect size as not supported",
      "not supported as an effect size" in REPORT)

# --- report hygiene ----------------------------------------------------------
check("report states the control is the wrong build",
      "not the pairing behind the promoted claim" in REPORT.lower()
      or "This is not the pairing behind the promoted claim" in REPORT)
check("report carries a 'not supported' section", "**Not supported**" in REPORT)
check("report gives a reproduce command", "fresh_rem81_analysis.py" in REPORT)
check("analysis JSON records the unevaluable policy",
      "E10" in J["unevaluable_trials"]["policy"])
check("analysis JSON records its limitations", len(J["limitations"]) >= 3)

# --- report ------------------------------------------------------------------
bad = [(n, d) for n, ok, d in CHECKS if not ok]
for n, ok, d in CHECKS:
    print(f"{'PASS' if ok else 'FAIL'}  {n}" + (f"  [{d}]" if d and not ok else ""))
print(f"\n{len(CHECKS) - len(bad)}/{len(CHECKS)} checks green")
sys.exit(1 if bad else 0)
