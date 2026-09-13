#!/usr/bin/env python3
"""Collect Harbor trial results into a per-run JSONL for analysis.

Idempotent: globs <jobs-dir>/<job>/*/result.json (per-trial files, written
incrementally by Harbor as each trial completes — these ARE the checkpoints).
Run any time, including mid-job, to snapshot progress.

Usage: collect.py <jobs_dir> <job_name> <arm> <out_jsonl>
"""
import json
import glob
import os
import sys
from datetime import datetime

def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()

def tool_counts(trial_dir, arm):
    """Count tool calls from the arm's native logs."""
    counts = {}
    if arm == "ada":
        f = os.path.join(trial_dir, "agent", "ada-events.jsonl")
        if not os.path.exists(f):
            return counts
        for line in open(f):
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            d = e.get("data") or {}
            if d.get("type") == "TOOL_CALL_START":
                n = d.get("toolCallName") or "unknown"
                counts[n] = counts.get(n, 0) + 1
    else:
        f = os.path.join(trial_dir, "agent", "claude-code.txt")
        if not os.path.exists(f):
            return counts
        for line in open(f, errors="replace"):
            if '"type":"assistant"' not in line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            msg = e.get("message") or {}
            for c in (msg.get("content") or []):
                if isinstance(c, dict) and c.get("type") == "tool_use":
                    n = c.get("name") or "unknown"
                    counts[n] = counts.get(n, 0) + 1
    return counts

def main():
    jobs_dir, job, arm, out = sys.argv[1:5]
    rows = []
    for f in sorted(glob.glob(os.path.join(jobs_dir, job, "*", "result.json"))):
        d = json.load(open(f))
        if "trial_name" not in d:
            continue  # job-level result
        ar = d.get("agent_result") or {}
        md = ar.get("metadata") or {}
        trial_dir = os.path.dirname(f)
        dur_ms = (ts(d["finished_at"]) - ts(d["started_at"])) * 1000
        exc = d.get("exception_info")
        rows.append({
            "task": d["task_name"],
            "trial": d["trial_name"],
            "arm": arm,
            "pass": float((d.get("verifier_result") or {}).get("rewards", {}).get("reward") or 0),
            "cost_usd": ar.get("cost_usd"),
            "n_input_tokens": ar.get("n_input_tokens"),
            "n_cache_tokens": ar.get("n_cache_tokens"),
            "n_output_tokens": ar.get("n_output_tokens"),
            "ttft_ms": md.get("ttft_ms"),
            "duration_ms": md.get("duration_ms") if md.get("duration_ms") else round(dur_ms),
            "duration_source": "ada_result_event" if md.get("duration_ms") else "trial_wallclock",
            "num_turns": md.get("num_turns"),
            "tool_counts": tool_counts(trial_dir, arm),
            "error": exc is not None,
            "error_info": (str(exc)[:300] if exc else None),
            "started_at": d["started_at"],
            "finished_at": d["finished_at"],
        })
    with open(out, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    n_cost = sum(1 for r in rows if r["cost_usd"] is not None)
    print(f"{job} [{arm}]: {len(rows)} trials collected, {n_cost} with cost -> {out}")
    if rows:
        print(f"  pass rate: {sum(r['pass'] for r in rows)/len(rows):.3f}, "
              f"mean cost: ${sum(r['cost_usd'] or 0 for r in rows)/len(rows):.4f}")

if __name__ == "__main__":
    main()
