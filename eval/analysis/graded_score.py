#!/usr/bin/env /usr/bin/python3
"""Graded scorer: re-score all completed trials from verifier/ctrf.json per-test results.

# For each trial in eval/results/<arm>.jsonl, parse
# eval/jobs/<jobdir>/<trial>/verifier/ctrf.json -> results.tests[] and compute:

#    graded = tests_passed / tests_total   (0.0 .. 1.0)
#    binary = 1.0 iff all tests passed     (kept alongside for cross-checking)

# Emits eval/results/graded/<arm>.jsonl with the original record fields plus:
#    graded_score, graded_passed, graded_total, graded_source

# Conventions:
#  - A test counts as passed iff status == 'passed'.
#  - Missing / malformed / empty ctrf -> record excluded from output, logged to
#    stderr (never silently scored as 0).
#  - For 1-test tasks graded == binary by construction; verified in main().
#  - Arm -> jobdir mapping is explicit (l1l2-arm.jsonl lives in job l1l2-arm-v2).

# Zero API spend: reads only local files.
"""

import json
import os
import sys
import glob

BASE = "/root/optimize_ada/eval"
OUT_DIR = f"{BASE}/results/graded"

# arm jsonl name -> job dir containing the trial directories
ARM_TO_JOB = {
    "baseline-armA": "baseline-armA",
    "baseline-armB": "baseline-armB",
    "dev-baseline": "dev-baseline",
    "dev-x1": "dev-x1",
    "dev-x2": "dev-x2",
    "dev-x3": "dev-x3",
    "e-opt1-arm": "e-opt1-arm",
    "e-opt1-arm-v2": "e-opt1-arm-v2",
    "e-opt1-probe": "e-opt1-probe",
    "l1l2-arm": "l1l2-arm-v2",
    "dev-h1": "dev-h1",
    "dev-h2": "dev-h2",
    "dev-x1r": "dev-x1r",
}


def score_ctrf(ctrf_path):
    """Return (passed, total) or None if the ctrf is missing/malformed/empty."""
    if not os.path.exists(ctrf_path):
        return None
    try:
        with open(ctrf_path) as f:
            d = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    try:
        tests = d["results"]["tests"]
    except (KeyError, TypeError):
        return None
    if not isinstance(tests, list) or len(tests) == 0:
        return None
    passed = sum(1 for t in tests if t.get("status") == "passed")
    return passed, len(tests)


def regrade_arm(arm, jobdir):
    src = f"{BASE}/results/{arm}.jsonl"
    rows = [json.loads(l) for l in open(src) if l.strip()]
    out, excluded = [], []
    for r in rows:
        trial = r["trial"]
        res = score_ctrf(f"{BASE}/jobs/{jobdir}/{trial}/verifier/ctrf.json")
        if res is None:
            excluded.append(trial)
            continue
        passed, total = res
        o = dict(r)
        o["graded_passed"] = passed
        o["graded_total"] = total
        o["graded_score"] = passed / total
        o["graded_source"] = f"jobs/{jobdir}/{trial}/verifier/ctrf.json"
        out.append(o)
    return rows, out, excluded


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    total_in = total_out = 0
    print(f"{'arm':<18}{'in':>5}{'out':>5}{'excl':>5}  mean_graded  mean_binary  1-test-graded==binary")
    for arm, jobdir in ARM_TO_JOB.items():
        rows, out, excluded = regrade_arm(arm, jobdir)
        with open(f"{OUT_DIR}/{arm}.jsonl", "w") as f:
            for o in out:
                f.write(json.dumps(o) + "\n")
        total_in += len(rows)
        total_out += len(out)
        mg = sum(o["graded_score"] for o in out) / len(out) if out else float("nan")
        mb = sum(o["pass"] for o in out) / len(out) if out else float("nan")
        # invariant: for 1-test tasks graded must equal binary exactly
        mism = 0
        for o in out:
            if o["graded_total"] == 1 and o["graded_score"] != o["pass"]:
                mism += 1
        flag = "OK" if mism == 0 else f"MISMATCH({mism})"
        print(f"{arm:<18}{len(rows):>5}{len(out):>5}{len(excluded):>5}  "
              f"{mg:>10.4f}  {mb:>11.4f}  {flag}")
        for t in excluded:
            print(f"    EXCLUDED {arm}: {t} (missing/malformed ctrf)", file=sys.stderr)
    print(f"\nTOTAL: {total_in} in -> {total_out} out ({total_in - total_out} excluded)")
    # sanity: graded score in [0,1]
    bad = 0
    for f in glob.glob(f"{OUT_DIR}/*.jsonl"):
        for l in open(f):
            o = json.loads(l)
            if not (0.0 <= o["graded_score"] <= 1.0):
                bad += 1
    print(f"Range check [0,1]: {'OK' if bad == 0 else f'{bad} BAD'}")


if __name__ == "__main__":
    main()
