#!/usr/bin/env python3
"""Merge several pair runs (bench/run_pair.sh) into one evidence view for a single analysis (plain Python, no dependencies).

  python3 bench/merge_runs.py <OUT_DIR> <SRC_DIR> [<SRC_DIR> ...]
  e.g. python3 bench/merge_runs.py ada/runs/deepseek-v4.1-flash/r1_all \
         ada/runs/deepseek-v4.1-flash/r1 ada/runs/deepseek-v4.1-flash/r1_set41 ada/runs/deepseek-v4.1-flash/r1_retry

Rule (applied per build and per task, sources in the order given): the FIRST VALID attempt is used. A later attempt
replaces an earlier one only if the earlier one was a harness error (`valid` is false). A valid attempt is never replaced,
and a retry of a task that already has a valid attempt is ignored and listed as excluded.

OUT_DIR gets: <build>/<task> as symlinks to the chosen attempt folders (nothing is copied, no evidence is duplicated),
proxy.<build>/generations.jsonl with only the model calls of the chosen attempts, PROTOCOL.<build>.json, tasks.txt,
pricing_snapshot.json and MERGE.md (what came from where, and what was left out and what that cost). Then run:
  python3 bench/deepseek_summary.py <OUT_DIR>
"""
import json, os, re, sys
from pathlib import Path

if len(sys.argv) < 3:
    sys.exit(__doc__)
out, srcs = Path(sys.argv[1]), [Path(s) for s in sys.argv[2:]]
ARMS = ("baseline", "best")
if out.exists() and any(out.iterdir()):
    sys.exit(f"{out} already has content; use a new folder")


def session_of(attempt: Path):
    m = re.search(r'"session_id":"([0-9a-f-]{36})"', (attempt / "agent.log").read_text(errors="replace")) if (attempt / "agent.log").is_file() else None
    return m.group(1) if m else None


def jl(p: Path):
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.is_file() else []


L = ["# How this folder was assembled", "",
     "Sources, in order: " + ", ".join(f"`{s}`" for s in srcs) + ".", "",
     "Rule: per build and per task, the first valid attempt is used. A later attempt replaces an earlier one only when the earlier",
     "one was a harness error. Nothing is copied: `<build>/<task>` are symlinks into the source folders.", ""]
summary = {"sources": [str(s) for s in srcs], "chosen": {}, "excluded": []}
for arm in ARMS:
    chosen = {}      # task -> (src index, attempt dir, valid)
    ignored = []     # (task, src index, attempt dir, why)
    for i, src in enumerate(srcs):
        for rj in sorted((src / arm).glob("*/result.json")):
            task, d = rj.parent.name, rj.parent
            valid = bool(json.load(open(rj))["valid"])
            if task not in chosen:
                chosen[task] = (i, d, valid)
            elif not chosen[task][2] and valid:
                ignored.append((task, chosen[task][0], chosen[task][1], "harness error, replaced by a later valid attempt"))
                chosen[task] = (i, d, valid)
            else:
                ignored.append((task, i, d, "task already had a valid attempt" if chosen[task][2] else "also a harness error"))
    (out / arm).mkdir(parents=True)
    for task, (i, d, valid) in sorted(chosen.items()):
        (out / arm / task).symlink_to(os.path.relpath(d.resolve(), (out / arm).resolve()))
    keep = {session_of(d) for _, d, _ in chosen.values()} - {None}
    drop = {session_of(d): (t, i) for t, i, d, _ in ignored} | {session_of(d): (t, i) for t, (i, d, v) in chosen.items() if False}
    rows, dropped_cost, dropped_calls = [], 0.0, 0
    for i, src in enumerate(srcs):
        for g in jl(src / f"proxy.{arm}" / "generations.jsonl"):
            sid = g.get("session_id")
            if sid is None or sid in keep:
                rows.append(g)
            else:
                dropped_calls += 1
                dropped_cost += (g.get("generation") or {}).get("total_cost") or 0
    seen_ids, unique = set(), []
    for g in rows:   # one row per OpenRouter generation, so overlapping sources can never double-count a call
        gid = g.get("generation_id")
        if gid is None or gid not in seen_ids:
            seen_ids.add(gid); unique.append(g)
    rows = unique
    rows.sort(key=lambda g: g["ts"])
    (out / f"proxy.{arm}").mkdir()
    (out / f"proxy.{arm}" / "generations.jsonl").write_text("".join(json.dumps(g, sort_keys=True) + "\n" for g in rows))
    protos = [json.load(open(s / f"PROTOCOL.{arm}.json")) for s in srcs if (s / f"PROTOCOL.{arm}.json").is_file()]
    p = dict(protos[0])
    p.update(started_utc=min(x["started_utc"] for x in protos), finished_utc=max(x["finished_utc"] for x in protos), exit_code=None,
             tasks=len(chosen), merged_from=[str(s) for s in srcs], note="assembled by bench/merge_runs.py; see MERGE.md",
             merged_source_started_utc=[x["started_utc"] for x in protos])
    (out / f"PROTOCOL.{arm}.json").write_text(json.dumps(p, indent=2) + "\n")
    per_src = {str(srcs[i]): sum(1 for _, (j, _, _) in chosen.items() if j == i) for i in range(len(srcs))}
    invalid_left = [t for t, (_, _, v) in chosen.items() if not v]
    L += [f"## {arm}", "", f"{len(chosen)} tasks. Attempts taken from each source: " + ", ".join(f"`{k}` {v}" for k, v in per_src.items()) + ".",
          f"Harness errors still in the result (no valid attempt exists): {', '.join(f'`{t}`' for t in invalid_left) or 'none'}.", ""]
    if ignored:
        L += ["Attempts not used:", "", "| Task | Source | Why |", "|---|---|---|"] + [f"| `{t}` | `{srcs[i]}` | {why} |" for t, i, d, why in ignored] + [""]
    L += [f"Model calls of unused attempts left out of the cost: {dropped_calls}, ${dropped_cost:.4f}.", ""]
    summary["chosen"][arm] = {t: str(d) for t, (i, d, v) in chosen.items()}
    summary["excluded"] += [{"arm": arm, "task": t, "source": str(srcs[i]), "why": why} for t, i, d, why in ignored]
    summary.setdefault("excluded_cost_usd", {})[arm] = round(dropped_cost, 6)
tasks = sorted(set(summary["chosen"]["baseline"]) | set(summary["chosen"]["best"]))
(out / "tasks.txt").write_text("\n".join(tasks) + "\n")
for s in srcs:
    if (s / "pricing_snapshot.json").is_file():
        (out / "pricing_snapshot.json").write_text((s / "pricing_snapshot.json").read_text()); break
(out / "MERGE.md").write_text("\n".join(L) + "\n"); (out / "MERGE.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
print("\n".join(L))
