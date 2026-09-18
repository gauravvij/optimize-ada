#!/usr/bin/env python3
"""Machine verification of RUN_REGISTRY.md and CTRL_VS_T12_REPORT.md.

Re-derives every figure in both documents from the raw driver logs and diagnostics
files -- independently of ctrl_vs_t12_analysis.py -- then asserts that the analysis
JSON and the prose both agree with that derivation, and that the withdrawn +28 claim
is no longer stated as live anywhere in the published documents.

Run: python3 bench/ctrl_vs_t12_verify.py   (exit 0 = all green)
"""
from __future__ import annotations

import json
import math
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
    return {r["task_id"]: dict(passed=bool(r["passed"]), valid=bool(r.get("valid", True)),
                               timed_out=bool(r["timed_out"]), turns=r["turns"],
                               task_type=r.get("task_type"),
                               duration=r.get("duration_seconds"),
                               is_error=bool(r.get("agent_is_error")),
                               terminal=r.get("terminal_result"),
                               rc=r.get("grader_returncode"))
            for r in json.loads(p.read_text())["results"]}


def mcnemar(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, k) for k in range(0, min(b, c) + 1)) / 2 ** n)


def wilson(k: int, m: int, z: float = 1.959963985) -> tuple[float, float, float]:
    if m == 0:
        return 0.0, 0.0, 0.0
    ph = k / m
    d = 1 + z * z / m
    c = (ph + z * z / (2 * m)) / d
    h = z * math.sqrt(ph * (1 - ph) / m + z * z / (4 * m * m)) / d
    return ph, c - h, c + h


def paired(A: dict, B: dict) -> dict:
    ts = [t for t in sorted(set(A) & set(B)) if A[t]["valid"] and B[t]["valid"]]
    ka = sum(A[t]["passed"] for t in ts)
    kb = sum(B[t]["passed"] for t in ts)
    b = sum(1 for t in ts if A[t]["passed"] and not B[t]["passed"])
    c = sum(1 for t in ts if not A[t]["passed"] and B[t]["passed"])
    pa, la, ua = wilson(ka, len(ts))
    pb, lb, ub = wilson(kb, len(ts))
    diff = pb - pa
    return dict(n=len(ts), a=ka, b_pass=kb, net=kb - ka, b=b, c=c, p=mcnemar(b, c),
                diff=diff,
                lo=diff - math.sqrt((pb - lb) ** 2 + (ua - pa) ** 2),
                hi=diff + math.sqrt((ub - pb) ** 2 + (pa - la) ** 2))


# ---------------------------------------------------------------- the eight runs
R1 = from_diag(DIAG / "ada-baseline/manual/remaining81_baseline.json")
R2 = from_diag(DIAG / "manual/remaining81_incumbent.json")
R3 = from_diag(DIAG / "20260910T0728Z-t04ctrl/0.json")
R4 = from_diag(DIAG / "20260911T1540Z-t12rem81/rem81_t12_candidate.json")
R5 = from_diag(DIAG / "ada-baseline/20260912T1031Z-frem81base/0.json")
R6 = from_log(BENCH / "fresh_rem81_best.log")
R7 = from_diag(DIAG / "ada-t01gateoff/20260912T1603Z-t04ctrl2/0.json")
R8 = from_diag(DIAG / "20260912T1603Z-t12cand2/0.json")

CTRL_LOG = from_log(BENCH / "ctrl_vs_t12_control.log")
CAND_LOG = from_log(BENCH / "ctrl_vs_t12_candidate.log")
J = json.loads((BENCH / "CTRL_VS_T12_PAIRED_ANALYSIS.json").read_text())
REG = (BENCH / "RUN_REGISTRY.md").read_text()
REP = (BENCH / "CTRL_VS_T12_REPORT.md").read_text()


def flat(s: str) -> str:
    """Collapse whitespace so prose checks survive line wrapping."""
    return re.sub(r"\s+", " ", s)


def live(s: str) -> str:
    """Drop ~~struck~~ spans: retracted text is a record, not a live claim."""
    return re.sub(r"~~.+?~~", "", flat(s))


def tally(R: dict) -> tuple[int, int, int, int, int, int]:
    ev = [r for r in R.values() if r["valid"]]
    return (len(R), sum(1 for r in R.values() if not r["valid"]),
            sum(r["passed"] for r in ev), sum(r["timed_out"] for r in ev),
            sum(1 for r in ev if r["turns"] == 0), sum(r["turns"] for r in ev))


# ============================================================ RUN_REGISTRY.md
REGISTRY = [
    ("R1", R1, 81, 0, 27, 53, 53, 556),
    ("R2", R2, 81, 0, 50, 3, 43, 557),
    ("R3", R3, 81, 0, 24, 0, 0, 1544),
    ("R4", R4, 81, 0, 52, 0, 0, 1274),
    ("R5", R5, 81, 0, 34, 45, 46, 750),
    ("R6", R6, 81, 7, 43, 0, 0, 1284),
    ("R7", R7, 81, 0, 54, 0, 0, 1554),
    ("R8", R8, 81, 0, 50, 0, 0, 1389),
]
for name, R, rows, inv, pas, to, zt, turns in REGISTRY:
    got = tally(R)
    want = (rows, inv, pas, to, zt, turns)
    check(f"registry {name}: rows/invalid/pass/timeouts/zero-turn/turns = {want}",
          got == want, f"got {got}")
    ev = rows - inv
    check(f"registry {name}: row reads '{pas}/{ev}' in RUN_REGISTRY.md",
          f"| {pas}/{ev} |" in flat(REG))

check("registry R2 footnote is justified: R2 has few timeouts but many zero-turn rows",
      tally(R2)[3] == 3 and tally(R2)[4] == 43 and tally(R1)[3] == tally(R1)[4] == 53)
check("registry R6 footnote is justified: R6 is the only run with invalid rows",
      all(tally(R)[1] == 0 for n, R, *_ in REGISTRY if n != "R6") and tally(R6)[1] == 7)

# --------------------------------------------------- registry pairing verdicts
p57, p78, p58, p56 = paired(R5, R7), paired(R7, R8), paired(R5, R8), paired(R5, R6)
check("registry R5->R7 = 34/81 -> 54/81, +20, p=1.1e-05",
      (p57["n"], p57["a"], p57["b_pass"], p57["net"]) == (81, 34, 54, 20)
      and abs(p57["p"] - 1.097e-05) < 1e-8, str(p57))
check("registry R7->R8 = 54/81 -> 50/81, -4, p=0.42",
      (p78["n"], p78["a"], p78["b_pass"], p78["net"], p78["b"], p78["c"]) == (81, 54, 50, -4, 9, 5)
      and abs(p78["p"] - 0.424) < 1e-3, str(p78))
check("registry R5->R8 = 34/81 -> 50/81, +16, p=0.0015",
      (p58["n"], p58["a"], p58["b_pass"], p58["net"]) == (81, 34, 50, 16)
      and abs(p58["p"] - 0.001544) < 1e-6, str(p58))
check("registry R5->R6 = 31/74 -> 43/74, +12, p=0.0075",
      (p56["n"], p56["a"], p56["b_pass"], p56["net"]) == (74, 31, 43, 12)
      and abs(p56["p"] - 0.007538) < 1e-6, str(p56))

# ------------------------------------------------------------- the noise floor
n37, n48, n68, n15 = paired(R3, R7), paired(R4, R8), paired(R6, R8), paired(R1, R5)
check("noise R3->R7 same build: 24->54, 30 gained / 0 lost, p=1.863e-09",
      (n37["a"], n37["b_pass"], n37["c"], n37["b"]) == (24, 54, 30, 0)
      and abs(n37["p"] - 1.863e-09) < 1e-12, str(n37))
check("noise R4->R8 same build: 52->50, 10 discordant, p=0.7539",
      (n48["a"], n48["b_pass"], n48["b"] + n48["c"]) == (52, 50, 10)
      and abs(n48["p"] - 0.7539) < 1e-4, str(n48))
check("noise R6->R8 same build same day: 43/74 -> 44/74, 11 discordant, p=1.0",
      (n68["n"], n68["a"], n68["b_pass"], n68["b"] + n68["c"], n68["p"]) == (74, 43, 44, 11, 1.0),
      str(n68))
check("noise R1->R5 same build: 27->34, 13 discordant, p=0.0923",
      (n15["a"], n15["b_pass"], n15["b"] + n15["c"]) == (27, 34, 13)
      and abs(n15["p"] - 0.09229) < 1e-5, str(n15))
check("registry states only same-day pairings are legitimate",
      "**Only same-day pairings.**" in flat(REG))
check("registry marks R3->R4 (the withdrawn +28) as measuring nothing",
      "| R3 → R4 |" in REG and "**nothing**" in flat(REG))
check("registry carries the intra-day stability check that licenses R5 vs R7",
      "Intra-day stability check" in REG and "43/74 → 44/74" in flat(REG))

# ==================================================== CTRL_VS_T12_PAIRED_ANALYSIS
check("analysis JSON status is COMPLETE (never PARTIAL again)", J["status"] == "COMPLETE")
check("analysis JSON primary contrast is populated", J["primary"] is not None)
pr = J["primary"]
check("analysis JSON primary matches independent derivation",
      pr["n"] == 81 and pr["a_pass"] == 54 and pr["b_pass"] == 50
      and pr["mcnemar_exact"]["b_a_pass_b_fail"] == 9
      and pr["mcnemar_exact"]["c_a_fail_b_pass"] == 5
      and abs(pr["mcnemar_exact"]["p_value"] - 0.424) < 1e-3)
check("analysis JSON records both arms' diagnostics as present",
      "MISSING" not in json.dumps(J["arms"]))
check("analysis JSON control_drift matches independent derivation",
      J["control_drift"]["a_pass"] == 24 and J["control_drift"]["b_pass"] == 54
      and J["control_drift"]["mcnemar_exact"]["c_a_fail_b_pass"] == 30
      and J["control_drift"]["mcnemar_exact"]["b_a_pass_b_fail"] == 0)

# ================================================================ run integrity
check("both arms 81 rows, identical task sets, no duplicates",
      len(CTRL_LOG) == len(CAND_LOG) == 81 and set(CTRL_LOG) == set(CAND_LOG))
check("all 162 rows valid, zero timeouts either arm",
      all(r["valid"] and not r["timed_out"] for r in CTRL_LOG.values())
      and all(r["valid"] and not r["timed_out"] for r in CAND_LOG.values()))
check("driver logs agree with diagnostics per task, both arms",
      {t: (r["passed"], r["turns"]) for t, r in CTRL_LOG.items()}
      == {t: (r["passed"], r["turns"]) for t, r in R7.items()}
      and {t: (r["passed"], r["turns"]) for t, r in CAND_LOG.items()}
      == {t: (r["passed"], r["turns"]) for t, r in R8.items()})
check("T0.1 holding: terminal_result on every row, zero turns=0 rows, both arms",
      all(r["terminal"] for r in R7.values()) and all(r["terminal"] for r in R8.values())
      and not any(r["turns"] == 0 for r in R7.values())
      and not any(r["turns"] == 0 for r in R8.values()))
check("driver recorded COMPLETE and both arms exit 0",
      "COMPLETE" in (BENCH / "ctrl_vs_t12_STATUS").read_text()
      and (BENCH / "ctrl_vs_t12_driver.log").read_text().count("DONE exit=0") == 2)
check("driver preflight pinned both agent trees to the intended commits",
      "PREFLIGHT OK   targets/ada-t01gateoff  HEAD=6672af8  agent/ == 6672af8"
      in (BENCH / "ctrl_vs_t12_driver.log").read_text()
      and "agent/ == 2e495bb" in (BENCH / "ctrl_vs_t12_driver.log").read_text())

# ================================================== report section 3: watchdog
hung = [t for t in R5 if R5[t]["turns"] == 0]
ran = [t for t in R5 if R5[t]["turns"] > 0]
check("report §3: 46 baseline-hung tasks, 0/46 -> 21/46",
      len(hung) == 46 and sum(R5[t]["passed"] for t in hung) == 0
      and sum(R7[t]["passed"] for t in hung) == 21)
check("report §3: 35 baseline-ran tasks, 34/35 -> 33/35",
      len(ran) == 35 and sum(R5[t]["passed"] for t in ran) == 34
      and sum(R7[t]["passed"] for t in ran) == 33)

# =============================================== report section 4: the -4 split
intr = [t for t in R7 if R7[t]["is_error"]]
clean = [t for t in R7 if not R7[t]["is_error"]]
check("report §4: 34 control-interrupted tasks, 12/34 -> 13/34",
      len(intr) == 34 and sum(R7[t]["passed"] for t in intr) == 12
      and sum(R8[t]["passed"] for t in intr) == 13)
check("report §4: 47 control-clean tasks, 42/47 -> 37/47",
      len(clean) == 47 and sum(R7[t]["passed"] for t in clean) == 42
      and sum(R8[t]["passed"] for t in clean) == 37)
BY_TYPE = {"dbsetup": (13, 11, 8), "dependency_resolution": (14, 6, 4),
           "bgsetup": (7, 6, 6), "reposetup": (47, 31, 32)}
for tt, (n, kc, kk) in BY_TYPE.items():
    sub = [t for t in R7 if R7[t]["task_type"] == tt]
    check(f"report §4: {tt} n={n}, control {kc}, candidate {kk}",
          len(sub) == n and sum(R7[t]["passed"] for t in sub) == kc
          and sum(R8[t]["passed"] for t in sub) == kk)
lost = [t for t in R7 if R7[t]["passed"] and not R8[t]["passed"]]
check("report §4: 3 of the 9 lost tasks ended with >40% of budget unused",
      len(lost) == 9 and sum(1 for t in lost if R8[t]["duration"] < 0.6 * 480) == 3)

# ================================================ report section 5: mechanism
check("report §5: interrupted runs 34 -> 7 (-79%)",
      sum(1 for r in R7.values() if r["is_error"]) == 34
      and sum(1 for r in R8.values() if r["is_error"]) == 7)
check("report §5: turns 1554 -> 1389 (-10.6%)",
      sum(r["turns"] for r in R7.values()) == 1554
      and sum(r["turns"] for r in R8.values()) == 1389
      and abs((1389 - 1554) / 1554 + 0.1062) < 5e-4)
check("report §5: summed wall time 29,353 s -> 27,881 s (-5.0%)",
      round(sum(r["duration"] for r in R7.values())) == 29353
      and round(sum(r["duration"] for r in R8.values())) == 27881)


def claimed_done_grader_failed(R: dict) -> int:
    return sum(1 for r in R.values()
               if not r["passed"] and not r["is_error"] and r["rc"] is not None)


check("report §5: 'agent said done, grader failed' = 5 of 27 vs 25 of 31",
      claimed_done_grader_failed(R7) == 5
      and sum(1 for r in R7.values() if not r["passed"]) == 27
      and claimed_done_grader_failed(R8) == 25
      and sum(1 for r in R8.values() if not r["passed"]) == 31)

# ==================================================== report prose obligations
check("report headline states -4 at p = 0.42, not +28",
      "**50/81 against 54/81, a net of −4 at p = 0.42**" in flat(REP))
check("report states the promotion is withdrawn",
      "**Verdict: the T1.2 promotion is withdrawn.**" in flat(REP))
check("report states this is NOT evidence of harm",
      "**This run does not show T1.2 is harmful.**" in flat(REP))
check("report explains the withdrawn +28 with the R3 drift",
      "30 tasks gained, 0 lost, p = 1.863e-09" in flat(REP))
check("report resolves the FRESH_REM81 'beaten 18-0' finding",
      "beaten 18–0 by its own ancestor" in REP and "There is no defect in `6672af8`" in flat(REP))
check("report carries a 'Not supported' section", "**Not supported:**" in flat(REP))
check("report discloses the stale-analysis defect it found",
      "PARTIAL" in REP and "eight hours" in flat(REP))
check("report gives reproduce commands",
      "ctrl_vs_t12_analysis.py" in REP and "ctrl_vs_t12_verify.py" in flat(REP))
check("report marks the §3/§4 subsets as post-hoc conditioned",
      "conditioned post-hoc" in REP or "descriptive decomposition" in flat(REP))

# ======================================= the withdrawn claim is gone everywhere
LIVE = {
    "README.md": (ROOT / "README.md").read_text(),
    "blog.md": (ROOT / "blog.md").read_text(),
    "ada/RESULTS.md": (ROOT / "ada/RESULTS.md").read_text(),
    "ada/REPORT.md": (ROOT / "ada/REPORT.md").read_text(),
    "ada/README.md": (ROOT / "ada/README.md").read_text(),
    # fina_run.md was removed during final packaging (2026-09-18); its §3/§7
    # rules are historical context recorded in bench/RUN_REGISTRY.md.
    "bench/RUN_REGISTRY.md": REG,
    "bench/CTRL_VS_T12_REPORT.md": REP,
    "bench/FRESH_REM81_REPORT.md": (BENCH / "FRESH_REM81_REPORT.md").read_text(),
}
WITHDRAWN_TOKENS = ("52/81", "24/81", "net +28", "7.66e-07")
# Words that mark a figure as no longer current. A withdrawn number may be printed --
# deleting it would hide what was claimed -- but never without one of these beside it.
WITHDRAWAL_WORDS = ("withdraw", "Withdraw", "WITHDRAWN", "supersede", "Supersede",
                    "not be quoted", "depressed", "void", "Void", "outlier",
                    "unusable", "anomalous", "inflated", "not a sound anchor",
                    "inherits the defect")
# The 2026-09-15 confirmation run (R9/R10) scores the shipped build 47/81 and 52/81, so the
# bare fraction "52/81" legitimately appears as a current number. A token sitting next to one
# of these is that run, not the withdrawn R4 figure -- which is always the *pairing*
# 52/81 vs 24/81 and is caught by its own tokens ("24/81", "net +28", "7.66e-07").
CONFIRMATION_WORDS = ("R9", "R10", "2026-09-15", "20260915T0825Z", "confirmation run")


def unmarked(text: str) -> list[str]:
    """Withdrawn figures may appear, but never without a withdrawal marker beside them.

    Struck-through spans are exempt (the strikethrough IS the marker); every other
    occurrence must have a withdrawal word within 300 characters.
    """
    t = live(text)
    out = []
    for tok in WITHDRAWN_TOKENS:
        for m in re.finditer(re.escape(tok), t):
            near = t[max(0, m.start() - 300):m.end() + 300]
            if any(w in near for w in WITHDRAWAL_WORDS):
                continue
            if tok == "52/81" and any(w in near for w in CONFIRMATION_WORDS):
                continue
            out.append(f"{tok} @ {m.start()}")
    return out


for name, text in LIVE.items():
    check(f"{name}: no withdrawn figure appears without a withdrawal marker beside it",
          not unmarked(text), "; ".join(unmarked(text)))
    check(f"{name}: names the same-day result 54/81 -> 50/81",
          "54/81" in flat(text) and "50/81" in flat(text))
    check(f"{name}: points at the canonical run registry",
          name == "bench/RUN_REGISTRY.md" or "RUN_REGISTRY" in flat(text))
    check(f"{name}: does not present T1.2 as promoted outside a strikethrough",
          "\u2705 **PROMOTED**" not in live(text)
          and "**Verdict: PROMOTED.**" not in live(text))

bad = [(n, d) for n, ok, d in CHECKS if not ok]
for n, ok, d in CHECKS:
    print(f"{'PASS' if ok else 'FAIL'}  {n}" + (f"  [{d}]" if d and not ok else ""))
print(f"\n{len(CHECKS) - len(bad)}/{len(CHECKS)} checks green")
sys.exit(1 if bad else 0)
