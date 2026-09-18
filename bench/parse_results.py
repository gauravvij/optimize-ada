#!/usr/bin/env python3
"""Parse a harbor jobs-dir tree into a per-task summary table (JSON to stdout).

Usage: python3 parse_results.py <results-dir> [<results-dir> ...]
Each dir should contain one or more <timestamp>/<task>__<id>/result.json trials.
"""
import json
import sys
from pathlib import Path


def parse_job_dir(job_dir: Path) -> list[dict]:
    trials = []
    for trial_dir in sorted(job_dir.iterdir()):
        if not trial_dir.is_dir() or "__" not in trial_dir.name:
            continue
        rp = trial_dir / "result.json"
        if not rp.is_file():
            continue
        d = json.loads(rp.read_text())
        ar = d.get("agent_result") or {}
        vr = d.get("verifier_result") or {}
        rewards = (vr.get("rewards") or {}).get("reward")
        reward = rewards if rewards is not None else None
        exc = d.get("exception_info")
        meta = ar.get("metadata") or {}
        trials.append(
            {
                "task": d.get("task_name", trial_dir.name),
                "trial": trial_dir.name,
                "reward": reward,
                "reward_raw": vr.get("rewards"),
                "is_error": meta.get("ada_is_error"),
                "turns": meta.get("ada_num_turns"),
                "cost_usd": ar.get("cost_usd"),
                "input_tokens": ar.get("n_input_tokens"),
                "output_tokens": ar.get("n_output_tokens"),
                "cache_tokens": ar.get("n_cache_tokens"),
                "exception": exc.get("type") if isinstance(exc, dict) else (
                    str(exc) if exc else None
                ),
                "agent_exec_s": _span_secs(d.get("agent_execution")),
            }
        )
    return trials


def _span_secs(span: dict | None) -> float | None:
    if not span or not span.get("started_at") or not span.get("finished_at"):
        return None
    from datetime import datetime

    f = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))
    return (f(span["finished_at"]) - f(span["started_at"])).total_seconds()


def main() -> None:
    for arg in sys.argv[1:]:
        job_dir = Path(arg)
        trials = parse_job_dir(job_dir)
        print(f"=== {job_dir} ({len(trials)} trials) ===")
        n_pass = sum(1 for t in trials if t["reward"] == 1.0)
        n_fail = sum(1 for t in trials if t["reward"] == 0.0)
        print(f"pass={n_pass} fail={n_fail} reward=None={len(trials)-n_pass-n_fail}")
        hdr = (
            f"{'task':<28} {'reward':>6} {'is_err':>6} {'turns':>5} "
            f"{'cost_usd':>9} {'exec_s':>8} {'exception'}"
        )
        print(hdr)
        print("-" * len(hdr))
        for t in trials:
            print(
                f"{t['task'].split('/')[-1]:<28} {str(t['reward']):>6} "
                f"{str(t['is_error']):>6} {str(t['turns']):>5} "
                f"{t['cost_usd'] if t['cost_usd'] is not None else 0:>9.4f} "
                f"{str(t['agent_exec_s']):>8} {str(t['exception'] or ''):<30}"
            )
        print(json.dumps(trials, indent=1))


if __name__ == "__main__":
    main()
