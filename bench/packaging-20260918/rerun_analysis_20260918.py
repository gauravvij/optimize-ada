#!/usr/bin/env python3
"""2026-09-18 subtask 4c (cont): prove repointed analysis scripts still work.

1. Back up every bench/*.json to bench/harness/json_backup_20260918/.
2. Run all repointed analysis scripts against the archived diagnostics layout.
3. Diff regenerated JSONs vs backups (numbers must match; path strings may change).
4. Re-run the three verify scripts to confirm they still pass on regenerated JSONs.
Exit 0 only if every analysis and verify run exits 0.
"""
from __future__ import annotations

import difflib
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path("/home/azureuser/adaAgent")
BENCH = ROOT / "bench"
BAK = BENCH / "harness/json_backup_20260918"
PY = sys.executable or "/usr/bin/python3"

ANALYSIS = [
    ["bench/baseline_vs_best_analysis.py"],
    ["bench/ctrl_vs_t12_analysis.py"],
    ["bench/fresh_rem81_analysis.py"],
    ["bench/t12_paired_analysis.py", "dev12"],
    ["bench/t12_paired_analysis.py", "val12"],
    ["bench/t12_rem81_analysis.py"],
    ["bench/p3_paired_analysis.py"],
    ["bench/budget_probe_analysis.py"],
]
VERIFIERS = [
    ["bench/baseline_vs_best_verify.py"],
    ["bench/ctrl_vs_t12_verify.py"],
    ["bench/fresh_rem81_verify.py"],
]

fails: list[str] = []

# 1. backup
BAK.mkdir(parents=True, exist_ok=True)
backed: dict[str, str] = {}
for j in sorted(BENCH.glob("*.json")):
    rel = j.name
    shutil.copy2(j, BAK / rel)
    backed[rel] = j.read_text()
print(f"backed up {len(backed)} bench JSONs -> {BAK.relative_to(ROOT)}")

# 2. run analysis scripts
for cmd in ANALYSIS:
    r = subprocess.run([PY, *cmd], cwd=ROOT, capture_output=True, text=True)
    tail = "\n".join((r.stdout or "").strip().splitlines()[-3:])
    print(f"\n--- {' '.join(cmd)} -> rc={r.returncode}")
    if tail:
        print(tail)
    if r.returncode != 0:
        fails.append(f"analysis rc={r.returncode}: {' '.join(cmd)} :: {(r.stderr or '').strip()[-400:]}")

# 3. diff regenerated JSONs vs backups
print("\n=== JSON diff vs pre-rerun backups ===")
for j in sorted(BENCH.glob("*.json")):
    old = backed.get(j.name)
    new = j.read_text()
    if old is None:
        print(f"NEW     {j.name} ({len(new)} bytes)")
        continue
    if old == new:
        print(f"IDENTICAL {j.name}")
    else:
        d = [l for l in difflib.unified_diff(old.splitlines(), new.splitlines(), lineterm="", n=0)]
        d = [l for l in d if l.startswith(("+", "-")) and not l.startswith(("+++", "---"))]
        print(f"CHANGED  {j.name}: {len(d)} changed lines")
        for line in d[:6]:
            print("   ", line[:160])

# 4. re-run verify scripts on the regenerated artifacts
print("\n=== verify scripts after regeneration ===")
for cmd in VERIFIERS:
    r = subprocess.run([PY, *cmd], cwd=ROOT, capture_output=True, text=True)
    lines = (r.stdout or "").strip().splitlines()
    summary = [l for l in lines if ("ALL" in l or "checks green" in l or "failures" in l)]
    print(f"--- {' '.join(cmd)} -> rc={r.returncode}  {' | '.join(summary[-2:])}")
    if r.returncode != 0:
        fails.append(f"verify rc={r.returncode}: {' '.join(cmd)} :: {(r.stderr or '').strip()[-400:]}")
        print((r.stdout or "")[-800:])

print(f"\n{'ALL GREEN' if not fails else str(len(fails)) + ' FAILURES'}")
for f in fails:
    print("  " + f)
sys.exit(1 if fails else 0)
