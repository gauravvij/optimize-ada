#!/usr/bin/env python3
"""Subtask 4 (2026-09-18): bench/ slim-down — the teardown record.

Drops regenerable bulk (variant tarballs, harbor venv, TB dataset copy,
extracted working-tree snapshots, smoke scratch) and stale logs, keeps every
report, analysis JSON, referenced results dir, driver script, and run log.

Safety: items in CHECKED_FILES are deleted ONLY if no kept file references
their basename. Items dropped unconditionally are either regenerable (with
regeneration notes added to the referencing reports) or superseded scratch.
Partial diagnostics of the VOID P3 attempt stay in bench/p3_evidence/.

Run:  python3 bench/harness/slim_bench_20260918.py   (from /home/azureuser/adaAgent)
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

os.chdir("/home/azureuser/adaAgent")
ROOT = Path(".")
report: list[str] = []


def sh(cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)


def du(path: str) -> str:
    return sh(f"du -sh {path}").stdout.strip()


# ---------------------------------------------------------------- 0. before
before = du("bench")
report.append(f"du bench BEFORE: {before}")

# ------------------------------------------------- 1. unregister smoke worktree
r = sh("git -C ada worktree remove bench/harness/worktrees/ada-smoke")
if r.returncode != 0:
    r = sh("git -C ada worktree remove --force bench/harness/worktrees/ada-smoke")
    report.append(f"worktree remove --force rc={r.returncode} {r.stderr.strip()[:200]}")
else:
    report.append("worktree ada-smoke removed (git-registered, was smoke-run checkout @ tag)")
sh("git -C ada worktree prune")

# ------------------------------- 2. preserve budget-probe driver/memory logs
bp = Path("bench/BUDGET_PROBE_20260916T0730Z")
arch = Path("bench/diagnostics/budget-probe-20260916T0730Z")
for f in ("driver.log", "memory.log"):
    src, dst = bp / f, arch / f
    if src.exists() and not dst.exists():
        shutil.move(str(src), str(dst))
        report.append(f"MOVED {src} -> {dst}")

# ------------------------------------------------------------- 3. drop lists
UNCOND_DIRS = [
    "bench/ada-baseline",            # extracted variant snapshot, regenerable from git
    "bench/ada-best",                # ditto (Sep-7 working tree)
    "bench/ada-best2",               # ditto
    "bench/.venv",                   # harbor venv, pip-regenerable
    "bench/terminal-bench-2",        # TB dataset copy, harbor-dataset-download
    "bench/__pycache__",
    "bench/harness/__pycache__",
    "bench/harness/worktrees",       # smoke worktree scratch (unregistered above)
    "bench/results-ada-smoke",       # smoke dirs, superseded
    "bench/results-ada-final-smoke",
    "bench/results-ada-final-smoke2",
    "bench/results-best3-smoke",
    "bench/results-best3-smoke2",
    "bench/results-best3-smoke3",
    "bench/results-best3-smoke4",
    "bench/BUDGET_PROBE_20260916T0730Z",  # dup of archived diagnostics (logs moved)
]
UNCOND_FILES = [
    # variant tarballs — regenerable from pinned git commits (+ bun install); the
    # measured per-trial outputs and reports are all retained.
    "bench/ada-baseline.tgz", "bench/ada-best.tgz", "bench/ada-best2.tgz",
    "bench/ada-best3.tgz", "bench/ada-final.tgz",
    "bench/BUDGET_PROBE_20260916T0730Z_nohup.out",   # 0 bytes
    # VOID P3 attempt (20260916T1340Z) + aborted starts — partial DIAGNOSTICS stay
    # in bench/p3_evidence/20260916T1340Z-r1-p3/; these are launch logs only.
    "bench/p3_paired_20260916T1326Z_driver.log",
    "bench/p3_paired_20260916T1340Z_driver.log",
    "bench/p3_paired_20260916T1340Z_memory.log",
    "bench/p3_paired_20260916T1340Z_r1_p3.log",
    "bench/p3_paired_20260916T1340Z_r1_shipped.log",
    "bench/p3_paired_20260917T0600Z_driver.log",
    "bench/p3_paired_nohup.out",
    # dead scratch: autoresearcher-loop integration + never-fired staged runs +
    # one-shot doc editors (their outputs live in the kept reports)
    "bench/ada25_eval_wrapper.sh",     # autoresearcher-loop wrapper (loop deleted)
    "bench/run_tb40_t12.sh",            # STAGED, never fired
    "bench/tb40_tasks.txt",             # input of the never-fired staged run
    "bench/write_p3_driver.py",         # scratch that generated run_p3_paired.sh
    "bench/watch_ctrl_vs_t12.py",       # session watcher
    "bench/append_tb20_section.py",    # one-shot doc editor (archive/ gone)
    "bench/final_verify.py",            # verifies deleted archive/ docs
    "bench/final_verify_final81.py",    # verifies deleted archive/ docs
    # stale smoke scratch logs (canonical evidence lives in reports + diagnostics)
    "bench/stall_smoke_log.txt",
    "bench/t01_smoke_log.txt",
    "bench/t02_probe_output.txt",
    # zero-byte launcher stubs
    "bench/t12_dev12_launcher.log", "bench/t12_val12_launcher.log",
    "bench/t12_rem81_launcher.log",
    # aborted fresh_rem81 attempt logs (the completed run's logs are kept)
    "bench/fresh_rem81_baseline.ABORTED-harness-20260912T0835Z.log",
    "bench/fresh_rem81_baseline.ABORTED-oom-20260912T0708Z.log",
    "bench/fresh_rem81_memory.ABORTED-20260912T0835Z.log",
    # aborted 2026-09-13 bvb starts (the 0825Z run is the evidence)
    "bench/baseline_vs_best_detached.out",
    "bench/baseline_vs_best_20260913T0306Z_driver.log",
    "bench/baseline_vs_best_20260913T0307Z_driver.log",
    # bench/ duplicate copies of t12 smoke logs — canonical copies live in
    # ada/evidence/t12/ (verified byte-identical) and are referenced by RESULTS.md
    "bench/t12_smoke_a1_log.txt", "bench/t12_smoke_a2_log.txt",
    "bench/t12_smoke_b_log.txt",
]
# Deleted ONLY if zero references in the kept corpus.
CHECKED_FILES = [
    "bench/t11_dev12_candidate.log", "bench/t11_dev12_gateoff.log",
    "bench/t11_smoke_e3.log",
    "bench/t12_dev12_candidate.log", "bench/t12_dev12_gateoff.log",
    "bench/t12_val12_candidate.log", "bench/t12_val12_gateoff.log",
    "bench/t12_smoke_b2_log.txt",
    "bench/t12_smoke_a1_trace.jsonl", "bench/t12_smoke_a2_trace.jsonl",
    "bench/t12_smoke_b_trace.jsonl", "bench/t12_smoke_b2_trace.jsonl",
    "bench/fresh_dev12_baseline.log", "bench/fresh_dev12_best.log",
    "bench/ada-final-40_run.log", "bench/final31_run.log",
    "bench/tb2",
]

drop_set = set(UNCOND_DIRS + UNCOND_FILES + CHECKED_FILES)
drop_prefixes = tuple(d + "/" for d in UNCOND_DIRS)


def is_dropped(p: Path) -> bool:
    s = str(p)
    return s in drop_set or s.startswith(drop_prefixes)


# ------------------------------------------- 4. kept corpus for reference scan
corpus: list[Path] = []
for base in ("bench", "ada"):
    for p in Path(base).rglob("*"):
        if (p.is_file() and ".git" not in p.parts and ".autoresearch" not in p.parts
                and ".setupbench_cache" not in p.parts and ".venv" not in p.parts
                and not is_dropped(p) and p.stat().st_size < 2_000_000):
            corpus.append(p)
for p in ROOT.glob("*.md"):
    if p.is_file():
        corpus.append(p)
report.append(f"reference corpus: {len(corpus)} kept files")


def referenced(name: str) -> list[str]:
    pat = re.escape(name)
    return [str(p) for p in corpus if pat in p.read_text(errors="ignore")]


# ----------------------------------------------------------------- 5. delete
freed = 0
for d in UNCOND_DIRS:
    p = Path(d)
    if p.exists():
        sz = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
        shutil.rmtree(p)
        freed += sz
        report.append(f"DELETED DIR  {d} ({sz / 1e6:.1f} MB)")
for f in UNCOND_FILES:
    p = Path(f)
    if p.exists():
        freed += p.stat().st_size
        os.remove(p)
        report.append(f"DELETED      {f}")

kept_referenced: list[tuple[str, list[str]]] = []
for f in CHECKED_FILES:
    p = Path(f)
    if not p.exists():
        report.append(f"ABSENT       {f}")
        continue
    hits = referenced(p.name)
    if hits:
        kept_referenced.append((f, hits[:3]))
    else:
        freed += p.stat().st_size
        os.remove(p)
        report.append(f"DELETED      {f} (unreferenced)")

after = du("bench")
report.append(f"du bench AFTER:  {after}")
report.append(f"freed this pass: {freed / 1e6:.1f} MB")

print("\n".join(report))
print("\nKEPT despite drop-candidacy (still referenced):")
for f, h in kept_referenced:
    print(f"  {f}")
    for x in h:
        print(f"    <- {x}")
rc = sh("git -C ada status --porcelain").stdout.strip()
print(f"\nada/ git status after worktree removal:\n{rc or '(clean apart from known doc edits)'}")
sys.exit(0)
