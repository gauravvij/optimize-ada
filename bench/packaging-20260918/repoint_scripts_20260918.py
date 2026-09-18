#!/usr/bin/env python3
"""2026-09-18 subtask 4c: repoint verify/analysis scripts to archived evidence.

The autoresearcher/targets/ workspaces are gone (final packaging). Raw run
diagnostics now live in the archive:
  - ada-workspace runs          -> bench/diagnostics/<run>/<file>
  - ada-baseline-workspace runs -> bench/diagnostics/ada-baseline/<run>/<file>
  - ada-t01gateoff runs         -> bench/diagnostics/ada-t01gateoff/<run>/<file>
  - P3-candidate arms           -> bench/p3_evidence/<run>/<file>

This script applies exact-string replacements (each asserting its expected
occurrence count) to the bench/ originals AND their byte-identical ada/evidence/
copies, removes the fina_run.md read from ctrl_vs_t12_verify.py's LIVE dict
(that file was removed during final packaging), and py-compiles everything.
"""
from __future__ import annotations

import py_compile
import sys
from pathlib import Path

ROOT = Path("/home/azureuser/adaAgent")
os.chdir(ROOT) if False else None

# (relative_path, old, new, expected_count)   count=-1 -> replace all, report
EDITS: list[tuple[str, str, str, int]] = [
    # ---------------- baseline_vs_best_verify.py (+ evidence copy) -----------
    ("bench/baseline_vs_best_verify.py",
     'T = ROOT / "autoresearcher/targets"',
     'T = ROOT / "bench/diagnostics"  # archived 2026-09-18 (was autoresearcher/targets)', 1),
    ("bench/baseline_vs_best_verify.py",
     '    doc = json.loads((T / workspace / ".autoresearch/diagnostics" / f"{TS}-{run}" / "0.json").read_text())',
     '    # archived layout: ada runs at bench/diagnostics/<run>/, ada-baseline at\n'
     '    # bench/diagnostics/ada-baseline/<run>/ (final packaging, 2026-09-18)\n'
     '    sub = {"ada": "", "ada-baseline": "ada-baseline"}[workspace]\n'
     '    doc = json.loads((T / sub / f"{TS}-{run}" / "0.json").read_text())', 1),
    # ---------------- baseline_vs_best_analysis.py (+ evidence copy) -----------
    ("bench/baseline_vs_best_analysis.py",
     'DIAG = ROOT / "autoresearcher/targets"',
     'DIAG = ROOT / "bench/diagnostics"  # archived 2026-09-18 (was autoresearcher/targets)', 1),
    ("bench/baseline_vs_best_analysis.py",
     'bp = DIAG / f"ada-baseline/.autoresearch/diagnostics/{ts}-r{r}-base/0.json"',
     'bp = DIAG / f"ada-baseline/{ts}-r{r}-base/0.json"', 1),
    ("bench/baseline_vs_best_analysis.py",
     'cp = DIAG / f"ada/.autoresearch/diagnostics/{ts}-r{r}-best/0.json"',
     'cp = DIAG / f"{ts}-r{r}-best/0.json"', 1),
    # ---------------- ctrl_vs_t12_verify.py (+ evidence copy) ------------------
    ("bench/ctrl_vs_t12_verify.py",
     'DIAG = ROOT / "autoresearcher/targets"',
     'DIAG = ROOT / "bench/diagnostics"  # archived 2026-09-18 (was autoresearcher/targets)', 1),
    ("bench/ctrl_vs_t12_verify.py",
     'DIAG / "ada-baseline/.autoresearch/diagnostics/manual/remaining81_baseline.json"',
     'DIAG / "ada-baseline/manual/remaining81_baseline.json"', 1),
    ("bench/ctrl_vs_t12_verify.py",
     'DIAG / "ada/.autoresearch/diagnostics/manual/remaining81_incumbent.json"',
     'DIAG / "manual/remaining81_incumbent.json"', 1),
    ("bench/ctrl_vs_t12_verify.py",
     'DIAG / "ada/.autoresearch/diagnostics/20260910T0728Z-t04ctrl/0.json"',
     'DIAG / "20260910T0728Z-t04ctrl/0.json"', 1),
    ("bench/ctrl_vs_t12_verify.py",
     'DIAG / "ada/.autoresearch/diagnostics/20260911T1540Z-t12rem81/rem81_t12_candidate.json"',
     'DIAG / "20260911T1540Z-t12rem81/rem81_t12_candidate.json"', 1),
    ("bench/ctrl_vs_t12_verify.py",
     'DIAG / "ada-baseline/.autoresearch/diagnostics/20260912T1031Z-frem81base/0.json"',
     'DIAG / "ada-baseline/20260912T1031Z-frem81base/0.json"', 1),
    ("bench/ctrl_vs_t12_verify.py",
     'DIAG / "ada-t01gateoff/.autoresearch/diagnostics/20260912T1603Z-t04ctrl2/0.json"',
     'DIAG / "ada-t01gateoff/20260912T1603Z-t04ctrl2/0.json"', 1),
    ("bench/ctrl_vs_t12_verify.py",
     'DIAG / "ada/.autoresearch/diagnostics/20260912T1603Z-t12cand2/0.json"',
     'DIAG / "20260912T1603Z-t12cand2/0.json"', 1),
    ("bench/ctrl_vs_t12_verify.py",
     '    "fina_run.md": (ROOT / "fina_run.md").read_text(),',
     '    # fina_run.md was removed during final packaging (2026-09-18); its §3/§7\n'
     '    # rules are historical context recorded in bench/RUN_REGISTRY.md.', 1),
    # ---------------- ctrl_vs_t12_analysis.py ---------------------------------
    ("bench/ctrl_vs_t12_analysis.py",
     'BENCH, DIAG = ROOT / "bench", ROOT / "autoresearcher/targets"',
     'BENCH, DIAG = ROOT / "bench", ROOT / "bench/diagnostics"  # archived 2026-09-18', 1),
    ("bench/ctrl_vs_t12_analysis.py",
     'CTRL_DIAG = DIAG / f"ada-t01gateoff/.autoresearch/diagnostics/{TS}-t04ctrl2/0.json"',
     'CTRL_DIAG = DIAG / f"ada-t01gateoff/{TS}-t04ctrl2/0.json"', 1),
    ("bench/ctrl_vs_t12_analysis.py",
     'CAND_DIAG = DIAG / f"ada/.autoresearch/diagnostics/{TS}-t12cand2/0.json"',
     'CAND_DIAG = DIAG / f"{TS}-t12cand2/0.json"', 1),
    ("bench/ctrl_vs_t12_analysis.py",
     'CTRL_SEP10 = DIAG / "ada/.autoresearch/diagnostics/20260910T0728Z-t04ctrl/0.json"',
     'CTRL_SEP10 = DIAG / "20260910T0728Z-t04ctrl/0.json"', 1),
    ("bench/ctrl_vs_t12_analysis.py",
     'T12_SEP11 = DIAG / "ada/.autoresearch/diagnostics/20260911T1540Z-t12rem81/rem81_t12_candidate.json"',
     'T12_SEP11 = DIAG / "20260911T1540Z-t12rem81/rem81_t12_candidate.json"', 1),
    ("bench/ctrl_vs_t12_analysis.py",
     'BASE_SEP12_DIAG = DIAG / "ada-baseline/.autoresearch/diagnostics/20260912T1031Z-frem81base/0.json"',
     'BASE_SEP12_DIAG = DIAG / "ada-baseline/20260912T1031Z-frem81base/0.json"', 1),
    # ---------------- fresh_rem81_verify.py -----------------------------------
    ("bench/fresh_rem81_verify.py",
     'DIAG = ROOT / "autoresearcher/targets"',
     'DIAG = ROOT / "bench/diagnostics"  # archived 2026-09-18 (was autoresearcher/targets)', 1),
    ("bench/fresh_rem81_verify.py",
     'DIAG / "ada-baseline/.autoresearch/diagnostics/20260912T1031Z-frem81base/0.json"',
     'DIAG / "ada-baseline/20260912T1031Z-frem81base/0.json"', 3),
    ("bench/fresh_rem81_verify.py",
     'DIAG / "ada/.autoresearch/diagnostics/20260911T1540Z-t12rem81/rem81_t12_candidate.json"',
     'DIAG / "20260911T1540Z-t12rem81/rem81_t12_candidate.json"', 1),
    ("bench/fresh_rem81_verify.py",
     'DIAG / "ada/.autoresearch/diagnostics/20260910T0728Z-t04ctrl/0.json"',
     'DIAG / "20260910T0728Z-t04ctrl/0.json"', 1),
    ("bench/fresh_rem81_verify.py",
     'not list((DIAG / "ada").glob(".autoresearch/diagnostics/*frem81best*"))',
     'not list(DIAG.glob("**/*frem81best*"))', 1),
    # ---------------- fresh_rem81_analysis.py ---------------------------------
    ("bench/fresh_rem81_analysis.py",
     'DIAG = ROOT / "autoresearcher/targets"',
     'DIAG = ROOT / "bench/diagnostics"  # archived 2026-09-18 (was autoresearcher/targets)', 1),
    ("bench/fresh_rem81_analysis.py",
     'FRESH_BASE_DIAG = DIAG / "ada-baseline/.autoresearch/diagnostics/20260912T1031Z-frem81base/0.json"',
     'FRESH_BASE_DIAG = DIAG / "ada-baseline/20260912T1031Z-frem81base/0.json"', 1),
    ("bench/fresh_rem81_analysis.py",
     'STORED_T12_DIAG = DIAG / "ada/.autoresearch/diagnostics/20260911T1540Z-t12rem81/rem81_t12_candidate.json"',
     'STORED_T12_DIAG = DIAG / "20260911T1540Z-t12rem81/rem81_t12_candidate.json"', 1),
    ("bench/fresh_rem81_analysis.py",
     'STORED_CTRL_DIAG = DIAG / "ada/.autoresearch/diagnostics/20260910T0728Z-t04ctrl/0.json"',
     'STORED_CTRL_DIAG = DIAG / "20260910T0728Z-t04ctrl/0.json"', 1),
    # ---------------- t12_paired_analysis.py (+ evidence copy) -----------------
    ("bench/t12_paired_analysis.py",
     'CAND = ROOT / f"autoresearcher/targets/ada/.autoresearch/diagnostics/{RUN_ID}/{RUNG}_t12_candidate.json"',
     'CAND = ROOT / f"bench/diagnostics/{RUN_ID}/{RUNG}_t12_candidate.json"  # archived 2026-09-18', 1),
    ("bench/t12_paired_analysis.py",
     'GATE = ROOT / f"autoresearcher/targets/ada-t01gateoff/.autoresearch/diagnostics/{RUN_ID}/{RUNG}_t01_gateoff.json"',
     'GATE = ROOT / f"bench/diagnostics/ada-t01gateoff/{RUN_ID}/{RUNG}_t01_gateoff.json"  # archived', 1),
    ("bench/t12_paired_analysis.py",
     '"diagnostics": f"targets/ada/.autoresearch/diagnostics/{RUN_ID}/{RUNG}_t12_candidate.json",',
     '"diagnostics": f"bench/diagnostics/{RUN_ID}/{RUNG}_t12_candidate.json",', 1),
    ("bench/t12_paired_analysis.py",
     '"diagnostics": f"targets/ada-t01gateoff/.autoresearch/diagnostics/{RUN_ID}/{RUNG}_t01_gateoff.json",',
     '"diagnostics": f"bench/diagnostics/ada-t01gateoff/{RUN_ID}/{RUNG}_t01_gateoff.json",', 1),
    ("bench/t12_paired_analysis.py",
     '"""T1.2 paired-rung analysis (fina_run.md §3 rules 2-3).',
     '"""T1.2 paired-rung analysis (campaign-spec fina_run.md §3 rules 2-3; the spec was\nremoved during final packaging 2026-09-18 — rules recorded in bench/RUN_REGISTRY.md).', 1),
    # ---------------- t12_rem81_analysis.py (+ evidence copy) ------------------
    ("bench/t12_rem81_analysis.py",
     'CAND = ROOT / f"autoresearcher/targets/ada/.autoresearch/diagnostics/{RUN_ID}/rem81_t12_candidate.json"',
     'CAND = ROOT / f"bench/diagnostics/{RUN_ID}/rem81_t12_candidate.json"  # archived 2026-09-18', 1),
    ("bench/t12_rem81_analysis.py",
     'CTRL = ROOT / "autoresearcher/targets/ada/.autoresearch/diagnostics/20260910T0728Z-t04ctrl/0.json"',
     'CTRL = ROOT / "bench/diagnostics/20260910T0728Z-t04ctrl/0.json"  # archived 2026-09-18', 1),
    ("bench/t12_rem81_analysis.py",
     '"diagnostics": f"targets/ada/.autoresearch/diagnostics/{RUN_ID}/rem81_t12_candidate.json",',
     '"diagnostics": f"bench/diagnostics/{RUN_ID}/rem81_t12_candidate.json",', 1),
    ("bench/t12_rem81_analysis.py",
     '"diagnostics": "targets/ada/.autoresearch/diagnostics/20260910T0728Z-t04ctrl/0.json",',
     '"diagnostics": "bench/diagnostics/20260910T0728Z-t04ctrl/0.json",', 1),
    ("bench/t12_rem81_analysis.py",
     '"""T1.2 remaining81 paired rung analysis (fina_run.md §3 rules 3-4).',
     '"""T1.2 remaining81 paired rung analysis (campaign-spec fina_run.md §3 rules 3-4;\nthe spec was removed during final packaging 2026-09-18 — rules in bench/RUN_REGISTRY.md).', 1),
    # ---------------- p3_paired_analysis.py -----------------------------------
    ("bench/p3_paired_analysis.py",
     'DIAG = ROOT / "autoresearcher/targets"',
     'DIAG = ROOT / "bench/diagnostics"  # shipped arms, archived 2026-09-18\nP3E = ROOT / "bench/p3_evidence"    # P3-candidate arms, archived 2026-09-18', 1),
    ("bench/p3_paired_analysis.py",
     'sp = DIAG / f"ada/.autoresearch/diagnostics/{ts}-r{r}-shipped/0.json"',
     'sp = DIAG / f"{ts}-r{r}-shipped/0.json"', 1),
    ("bench/p3_paired_analysis.py",
     'pp = DIAG / f"ada-p3/.autoresearch/diagnostics/{ts}-r{r}-p3/0.json"',
     'pp = P3E / f"{ts}-r{r}-p3/0.json"', 1),
    ("bench/p3_paired_analysis.py",
     '(shipped arm from targets/ada,\nP3 arm from targets/ada-p3)',
     '(shipped arm from bench/diagnostics — archived from the former targets/ada —\nP3 arm from bench/p3_evidence — archived from targets/ada-p3)', 1),
    # ---------------- budget_probe_analysis.py (docstring only) ---------------
    ("bench/budget_probe_analysis.py",
     'pre-registered in plans/plan.md BEFORE the spend:',
     'pre-registered BEFORE the spend (campaign plan of 2026-09-16, since removed\n    during final packaging; the rule is recorded in bench/PHASE_C_SUMMARY.md\n    and bench/RUN_REGISTRY.md):', 1),
]

# byte-identical ada/evidence/ copies receive the same edit set
COPIES = {
    "bench/baseline_vs_best_verify.py": "ada/evidence/confirm/baseline_vs_best_verify.py",
    "bench/baseline_vs_best_analysis.py": "ada/evidence/confirm/baseline_vs_best_analysis.py",
    "bench/ctrl_vs_t12_verify.py": "ada/evidence/t12/ctrl_vs_t12_verify.py",
    "bench/t12_paired_analysis.py": "ada/evidence/t12/t12_paired_analysis.py",
    "bench/t12_rem81_analysis.py": "ada/evidence/t12/t12_rem81_analysis.py",
}

fails: list[str] = []
edited: set[str] = set()

for orig, copy in COPIES.items():
    a, b = (ROOT / orig).read_text(), (ROOT / copy).read_text()
    print(f"copy check {copy}: {'IDENTICAL' if a == b else 'DIFFERS — skipping copy edits'}")
    if a != b:
        fails.append(f"copy differs: {copy}")

for rel, old, new, want in EDITS:
    p = ROOT / rel
    text = p.read_text()
    n = text.count(old)
    if want != -1 and n != want:
        fails.append(f"{rel}: expected {want} occurrence(s) of {old[:60]!r}, found {n}")
        continue
    p.write_text(text.replace(old, new))
    edited.add(rel)
    print(f"OK  {rel}: replaced {n}x  {old[:58]!r}")

# apply the same edits to the evidence copies
for orig, copy in COPIES.items():
    if orig in edited:
        (ROOT / copy).write_text((ROOT / orig).read_text())
        edited.add(copy)
        print(f"SYNCED copy {copy} <- {orig}")

for rel in sorted(edited):
    try:
        py_compile.compile(str(ROOT / rel), doraise=True)
        print(f"COMPILES {rel}")
    except py_compile.PyCompileError as e:
        fails.append(f"compile {rel}: {e}")

print(f"\n{'ALL EDITS APPLIED' if not fails else str(len(fails)) + ' FAILURES'}")
for f in fails:
    print("  " + f)
sys.exit(1 if fails else 0)
