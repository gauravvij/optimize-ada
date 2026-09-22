#!/usr/bin/env python3
"""Summarise a direct-Anthropic (Haiku) run from its evidence directory (plain Python, no dependencies).

  python3 bench/haiku_summary.py [EVIDENCE_DIR]      # default: ada/runs/haiku/r1

Reads <EVIDENCE_DIR>/{baseline,best}/<task>/{result.json,trace.jsonl,agent.log} and
<EV>/pricing_snapshot.json, writes summary.json and summary.md next to them.
Deterministic: the same evidence always yields byte-identical output.

There is no proxy log in direct mode. Cost is CLI token usage x Anthropic list prices:
(input_tokens x input + output_tokens x output + cache_creation_tokens x cache_write_5m
+ cache_read_tokens x cache_read) / 1e6. The CLI's own total_cost_usd is kept as a
cross-check column: for a first-party model it should agree. Timed-out attempts report
no usage and contribute $0 (an undercount, disclosed in the table).
"""
from __future__ import annotations

import collections
import json
import math
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EV = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "ada/runs/haiku/r1"
ARMS = ("baseline", "best")
FALLBACK_PRICES = {"input": 1.0, "output": 5.0, "cache_write_5m": 1.25, "cache_read": 0.10}


def stats(values: list[float], digits: int = 3) -> dict:
    if not values:
        return {"n": 0}
    v = sorted(values)
    p90 = v[min(len(v) - 1, math.ceil(0.9 * len(v)) - 1)]
    return {"n": len(v), "mean": round(statistics.fmean(v), digits), "median": round(statistics.median(v), digits),
            "p90": round(p90, digits), "max": round(v[-1], digits), "total": round(sum(v), digits)}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.is_file() else []


def outcome(row: dict) -> str:
    if not row["valid"]:
        return "harness_error"
    if row["timed_out"]:
        return "timed_out"
    if row["passed"]:
        return "passed"
    return "agent_no_output" if not row.get("turns_from_trace") else "failed_check"


def latencies(trace: Path) -> tuple[list[float], list[float]]:
    """Model time (tool result -> next reply) and tool time (reply -> its tool result), in seconds, from trace timestamps."""
    model, tool, last_ts, last_kind = [], [], None, None
    for entry in read_jsonl(trace):
        ts, kind = entry.get("ts"), entry.get("type")
        if ts is None:
            continue
        is_result = kind == "user" and any(b.get("type") == "tool_result" for b in entry.get("content") or [])
        if is_result and last_kind == "assistant":
            tool.append((ts - last_ts) / 1000)
        elif kind == "assistant" and last_kind == "user_result":
            model.append((ts - last_ts) / 1000)
        if is_result:
            last_kind, last_ts = "user_result", ts
        elif kind == "assistant":
            last_kind, last_ts = "assistant", ts
    return model, tool


def prices() -> dict:
    snap = EV / "pricing_snapshot.json"
    if snap.is_file():
        try:
            return json.loads(snap.read_text())["usd_per_mtok"]
        except (KeyError, ValueError):
            pass
    return dict(FALLBACK_PRICES)


def load_arm(arm: str, pr: dict) -> dict | None:
    rows = {p.parent.name: json.loads(p.read_text()) for p in sorted((EV / arm).glob("*/result.json"))}
    if not rows:
        return None

    def cost(r: dict) -> float:
        return ((r.get("input_tokens") or 0) * pr["input"] + (r.get("output_tokens") or 0) * pr["output"]
                + (r.get("cache_creation_tokens") or 0) * pr["cache_write_5m"]
                + (r.get("cache_read_tokens") or 0) * pr["cache_read"]) / 1e6

    tasks, model_s, tool_s, cost_mismatch = {}, [], [], []
    for task, r in rows.items():
        log = EV / arm / task / "agent.log"
        log_text = log.read_text(errors="replace") if log.is_file() else ""
        watchdog = bool(re.search(r"\[claude:watchdog\][^\n]*interrupting stream", log_text))  # the interrupt itself; the exit path that follows varies
        c = round(cost(r), 6)
        cli = r.get("cost_cli_usd")
        if cli is not None and abs(cli - c) > max(0.01, 0.05 * c):
            cost_mismatch.append({"task": task, "computed_usd": c, "cli_usd": cli})
        m, t = latencies(EV / arm / task / "trace.jsonl")
        model_s += m
        tool_s += t
        prompt_incl_cached = (r.get("input_tokens") or 0) + (r.get("cache_read_tokens") or 0) + (r.get("cache_creation_tokens") or 0)
        cached = (r.get("cache_read_tokens") or 0) + (r.get("cache_creation_tokens") or 0)
        tasks[task] = {
            "outcome": outcome(r), "passed": bool(r["passed"]), "valid": bool(r["valid"]), "timed_out": bool(r["timed_out"]),
            "watchdog_stopped": watchdog, "turns": r.get("turns_from_trace") or r["turns"] or 0, "cli_turns": r["turns"],  # the trace is the one count taken the same way for every attempt
            "duration_seconds": r["duration_seconds"], "agent_duration_seconds": r.get("agent_duration_seconds"),
            "prompt_tokens": prompt_incl_cached, "completion_tokens": r.get("output_tokens") or 0, "cached_prompt_tokens": cached,
            "cli_input_tokens": r.get("input_tokens") or 0, "cli_output_tokens": r.get("output_tokens") or 0,
            "cli_cache_read_tokens": r.get("cache_read_tokens") or 0, "cli_cache_creation_tokens": r.get("cache_creation_tokens") or 0,
            "cost_usd": c, "cli_cost_usd": cli, "models_seen": r["models_seen"],
            "stop_reason": r.get("agent_stop_reason"), "evidence_error": r.get("evidence_error") or None,
        }
    protocol = json.loads((EV / f"PROTOCOL.{arm}.json").read_text()) if (EV / f"PROTOCOL.{arm}.json").is_file() else {}
    attributed = sum(t["cost_usd"] for t in tasks.values())
    ok = [t for t in tasks.values() if t["valid"]]
    return {
        "arm": arm, "protocol": {k: protocol.get(k) for k in ("model", "workspace_commit", "base_commit", "agent_tree", "concurrency", "started_utc", "finished_utc", "exit_code", "direct")},
        "attempts": len(tasks), "outcomes": dict(sorted(collections.Counter(t["outcome"] for t in tasks.values()).items())),
        "passed": sum(t["passed"] for t in tasks.values()), "timed_out": sum(t["timed_out"] for t in tasks.values()),
        "watchdog_stopped": sum(t["watchdog_stopped"] for t in tasks.values()),
        "watchdog_stopped_then_passed": sum(t["watchdog_stopped"] and t["passed"] for t in tasks.values()),
        "harness_errors": sum(not t["valid"] for t in tasks.values()),
        "turns": stats([t["turns"] for t in ok], 1), "duration_seconds": stats([t["duration_seconds"] for t in ok], 1),
        "tokens_cli_records": {k: sum(t[k] for t in tasks.values()) for k in ("prompt_tokens", "cached_prompt_tokens", "completion_tokens")},
        "cost_usd": {"per_task": stats([t["cost_usd"] for t in ok], 5), "total_all_calls": round(attributed, 6),
                     "attributed_to_tasks": round(attributed, 6),
                     "cli_reported_total": round(sum(t["cli_cost_usd"] or 0 for t in tasks.values()), 4),
                     "cost_mismatches_computed_vs_cli": cost_mismatch},
        "api": {"note": "direct Anthropic API: no proxy log; per-call records unavailable",
                "attempts_with_usage": sum(1 for t in tasks.values() if (t["cli_input_tokens"] or t["cli_output_tokens"]))},
        "per_turn_seconds": {"model_reply": stats(model_s, 2), "tool_execution": stats(tool_s, 2)},
        "models_seen": sorted({m for t in tasks.values() for m in t["models_seen"]}),
        "tasks": tasks,
    }


def mcnemar(gained: int, lost: int) -> float:
    n = gained + lost
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, k) for k in range(min(gained, lost) + 1)) / 2 ** n)


def pair(base: dict, best: dict) -> dict:
    both = sorted(set(base["tasks"]) & set(best["tasks"]))
    ok = [t for t in both if base["tasks"][t]["valid"] and best["tasks"][t]["valid"]]
    gained = [t for t in ok if best["tasks"][t]["passed"] and not base["tasks"][t]["passed"]]
    lost = [t for t in ok if base["tasks"][t]["passed"] and not best["tasks"][t]["passed"]]
    timed = [t for t in ok if base["tasks"][t]["timed_out"]]
    fin = [t for t in ok if not base["tasks"][t]["timed_out"]]
    return {"pairs": len(ok), "baseline_passed": sum(base["tasks"][t]["passed"] for t in ok), "best_passed": sum(best["tasks"][t]["passed"] for t in ok),
            "gained": len(gained), "lost": len(lost), "mcnemar_exact_p": mcnemar(len(gained), len(lost)),
            "baseline_timed_out_pairs": {"n": len(timed), "baseline_passed": sum(base["tasks"][t]["passed"] for t in timed), "best_passed": sum(best["tasks"][t]["passed"] for t in timed)},
            "baseline_finished_pairs": {"n": len(fin), "baseline_passed": sum(base["tasks"][t]["passed"] for t in fin), "best_passed": sum(best["tasks"][t]["passed"] for t in fin)},
            "gained_tasks": gained, "lost_tasks": lost,
            "note": "single replicate: descriptive only, no significance claim"}


def markdown(summary: dict) -> str:
    arms = [a for a in ARMS if a in summary]
    out = [f"# {summary[arms[0]]['protocol']['model'] or 'model'} on SetupBench: {' vs '.join(arms)} (generated by bench/haiku_summary.py)", "",
           "One replicate; descriptive only. Cost = CLI token usage x Anthropic list prices (pricing_snapshot.json). Timed-out attempts report no usage and contribute $0.", ""]

    def row(label: str, fn) -> str:
        return "| " + label + " | " + " | ".join(str(fn(summary[a])) for a in arms) + " |"

    def sline(d: dict, keys=("mean", "median", "p90")) -> str:
        return "n/a (no samples)" if not d.get("n") else " / ".join(str(d[k]) for k in keys)

    out += ["| | " + " | ".join(arms) + " |", "|---|" + "---:|" * len(arms)]
    for label, fn in (
        ("Attempts", lambda s: s["attempts"]), ("Passed", lambda s: s["passed"]),
        ("Outcomes", lambda s: s["outcomes"]), ("Timed out (harness, never checked)", lambda s: s["timed_out"]),
        ("Interrupted by the 450 s watchdog / of which then passed", lambda s: f"{s['watchdog_stopped']} / {s['watchdog_stopped_then_passed']}"),
        ("Harness errors", lambda s: s["harness_errors"]),
        ("Turns per task (mean / median / p90 / max)", lambda s: (sline(s["turns"], ("mean", "median", "p90", "max")))),
        ("Task wall time s (mean / median / p90)", lambda s: sline(s["duration_seconds"])),
        ("Tokens, CLI usage records: prompt (incl. cached) / cached / completion", lambda s: f"{s['tokens_cli_records']['prompt_tokens']:,} / {s['tokens_cli_records']['cached_prompt_tokens']:,} / {s['tokens_cli_records']['completion_tokens']:,}"),
        ("Cost per task $ (mean / median / p90)", lambda s: sline(s["cost_usd"]["per_task"])),
        ("Cost total $", lambda s: s["cost_usd"]["total_all_calls"]),
        ("CLI-reported cost $ (cross-check; should agree for a first-party model)", lambda s: s["cost_usd"]["cli_reported_total"]),
        ("Computed-vs-CLI cost mismatches", lambda s: s["cost_usd"]["cost_mismatches_computed_vs_cli"] or "none"),
        ("Attempts with token usage", lambda s: f"{s['api']['attempts_with_usage']} (timed-out attempts report none)"),
        ("Per-turn model reply s (median / p90)", lambda s: sline(s["per_turn_seconds"]["model_reply"], ("median", "p90"))),
        ("Per-turn tool execution s (median / p90)", lambda s: sline(s["per_turn_seconds"]["tool_execution"], ("median", "p90"))),
        ("Models billed", lambda s: s["models_seen"]),
    ):
        out.append(row(label, fn))
    if "paired" in summary:
        p = summary["paired"]
        out += ["", "## Paired (tasks valid in both arms)", "",
                f"pairs={p['pairs']}  baseline passed={p['baseline_passed']}  best passed={p['best_passed']}  gained={p['gained']}  lost={p['lost']}  exact McNemar p={p['mcnemar_exact_p']:.3g} *(single replicate)*", "",
                f"Where baseline timed out ({p['baseline_timed_out_pairs']['n']} pairs): baseline passed {p['baseline_timed_out_pairs']['baseline_passed']}, best passed {p['baseline_timed_out_pairs']['best_passed']}.  ",
                f"Where baseline finished ({p['baseline_finished_pairs']['n']} pairs): baseline passed {p['baseline_finished_pairs']['baseline_passed']}, best passed {p['baseline_finished_pairs']['best_passed']}."]
    return "\n".join(out) + "\n"


def main() -> int:
    pr = prices()
    summary = {a: s for a in ARMS if (s := load_arm(a, pr))}
    if not summary:
        raise SystemExit(f"no result.json files under {EV}")
    if len(summary) == 2:
        summary["paired"] = pair(summary["baseline"], summary["best"])
    (EV / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    (EV / "summary.md").write_text(markdown(summary))
    print(markdown(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
