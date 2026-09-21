#!/usr/bin/env python3
"""Summarise a DeepSeek V4 Flash run from its evidence directory (plain Python, no dependencies).

  python3 bench/deepseek_summary.py [EVIDENCE_DIR]      # default: ada/runs/deepseek-v4-flash/r1

Reads <EVIDENCE_DIR>/{baseline,best}/<task>/{result.json,trace.jsonl,agent.log} and
<EVIDENCE_DIR>/proxy.<arm>/generations.jsonl, writes summary.json and summary.md next to them.
Deterministic: the same evidence always yields byte-identical output.

Cost is the sum of OpenRouter's own generation records (total_cost) for the calls made by each task's
Claude Code session. The CLI's total_cost_usd is NOT used: it prices this model at a Claude fallback rate.
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
EV = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "ada/runs/deepseek-v4-flash/r1"
ARMS = ("baseline", "best")


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


def load_arm(arm: str) -> dict | None:
    rows = {p.parent.name: json.loads(p.read_text()) for p in sorted((EV / arm).glob("*/result.json"))}
    if not rows:
        return None
    gens = read_jsonl(EV / f"proxy.{arm}" / "generations.jsonl")
    cost_by_session, calls_by_session = collections.defaultdict(float), collections.Counter()
    for g in gens:
        if g.get("session_id"):
            cost_by_session[g["session_id"]] += (g.get("generation") or {}).get("total_cost") or 0
            calls_by_session[g["session_id"]] += 1
    tokens_by_session = collections.defaultdict(lambda: [0, 0, 0])  # prompt (incl. cached), completion, cached
    for g in gens:
        if g.get("session_id") and g.get("generation"):
            tokens_by_session[g["session_id"]][0] += g["generation"].get("native_tokens_prompt") or 0
            tokens_by_session[g["session_id"]][1] += g["generation"].get("native_tokens_completion") or 0
            tokens_by_session[g["session_id"]][2] += g["generation"].get("native_tokens_cached") or 0
    compared, mismatched = 0, []
    tasks, model_s, tool_s = {}, [], []
    for task, r in rows.items():
        log = EV / arm / task / "agent.log"
        log_text = log.read_text(errors="replace") if log.is_file() else ""
        found = re.search(r'"session_id":"([0-9a-f-]{36})"', log_text)
        sid = (r.get("result_event") or {}).get("session_id") or (found.group(1) if found else None)
        watchdog = bool(re.search(r"\[claude:watchdog\][^\n]*interrupting stream", log_text))  # the interrupt itself; the exit path that follows varies
        if (r.get("result_event") or {}).get("session_id"):  # only attempts that reported usage can be cross-checked
            compared += 1
            cli = (r["input_tokens"] + r["cache_read_tokens"] + r["cache_creation_tokens"], r["output_tokens"])
            if tuple(tokens_by_session[sid][:2]) != cli:
                mismatched.append({"task": task, "openrouter_prompt_completion": tokens_by_session[sid][:2], "cli_prompt_completion": list(cli)})
        m, t = latencies(EV / arm / task / "trace.jsonl")
        model_s += m
        tool_s += t
        tasks[task] = {
            "outcome": outcome(r), "passed": bool(r["passed"]), "valid": bool(r["valid"]), "timed_out": bool(r["timed_out"]),
            "watchdog_stopped": watchdog, "turns": r.get("turns_from_trace") or r["turns"] or 0, "cli_turns": r["turns"],  # the trace is the one count taken the same way for every attempt; the CLI's is off by one after a watchdog interrupt, and by 32 in one case
            "duration_seconds": r["duration_seconds"], "agent_duration_seconds": r.get("agent_duration_seconds"),
            "prompt_tokens": tokens_by_session[sid][0], "completion_tokens": tokens_by_session[sid][1], "cached_prompt_tokens": tokens_by_session[sid][2],
            "cli_input_tokens": r["input_tokens"], "cli_output_tokens": r["output_tokens"],
            "cli_cache_read_tokens": r["cache_read_tokens"], "cli_cache_creation_tokens": r["cache_creation_tokens"],
            "cost_usd": round(cost_by_session.get(sid, 0.0), 6), "api_calls": calls_by_session.get(sid, 0),
            "cli_cost_usd_not_used": r.get("cost_cli_usd"), "models_seen": r["models_seen"],
            "stop_reason": r.get("agent_stop_reason"), "evidence_error": r.get("evidence_error") or None,
        }
    msgs = [g for g in gens if g.get("path", "").split("?")[0].endswith("/v1/messages")]  # model calls only
    other_calls = len(gens) - len(msgs)  # count_tokens: OpenRouter has no such endpoint (404); free
    agent_calls = [g for g in msgs if g.get("tools")]
    protocol = json.loads((EV / f"PROTOCOL.{arm}.json").read_text()) if (EV / f"PROTOCOL.{arm}.json").is_file() else {}
    gen_total = sum((g.get("generation") or {}).get("total_cost") or 0 for g in gens)
    attributed = sum(t["cost_usd"] for t in tasks.values())
    ku = protocol.get("openrouter_key_usage_after", {}).get("usage"), protocol.get("openrouter_key_usage_before", {}).get("usage")
    ok = [t for t in tasks.values() if t["valid"]]
    return {
        "arm": arm, "protocol": {k: protocol.get(k) for k in ("model", "workspace_commit", "base_commit", "agent_tree", "concurrency", "started_utc", "finished_utc", "exit_code", "provider_ignore")},
        "attempts": len(tasks), "outcomes": dict(sorted(collections.Counter(t["outcome"] for t in tasks.values()).items())),
        "passed": sum(t["passed"] for t in tasks.values()), "timed_out": sum(t["timed_out"] for t in tasks.values()),
        "watchdog_stopped": sum(t["watchdog_stopped"] for t in tasks.values()),
        "watchdog_stopped_then_passed": sum(t["watchdog_stopped"] and t["passed"] for t in tasks.values()),
        "harness_errors": sum(not t["valid"] for t in tasks.values()),
        "turns": stats([t["turns"] for t in ok], 1), "duration_seconds": stats([t["duration_seconds"] for t in ok], 1),
        "tokens_openrouter_records": {k: sum(t[k] for t in tasks.values()) for k in ("prompt_tokens", "cached_prompt_tokens", "completion_tokens")},
        "tokens_cli_reported_undercount": {k: sum(t[k] for t in tasks.values()) for k in ("cli_input_tokens", "cli_cache_read_tokens", "cli_cache_creation_tokens", "cli_output_tokens")},
        "cost_usd": {"per_task": stats([t["cost_usd"] for t in ok], 5), "total_all_calls": round(gen_total, 6),
                     "attributed_to_tasks": round(attributed, 6),
                     "openrouter_key_usage_delta": None if None in ku else round(ku[0] - ku[1], 6),  # (after, before)
                     "cli_reported_total_not_used": round(sum(t["cli_cost_usd_not_used"] or 0 for t in tasks.values()), 4)},
        "api": {"calls": len(msgs), "non_model_calls_count_tokens_404": other_calls, "agent_calls": len(agent_calls),
                "cut_off_calls_without_generation_record": sum(1 for g in msgs if not g.get("generation_id")),
                "empty_agent_replies_by_provider": dict(sorted(collections.Counter((g.get("generation") or {}).get("provider_name") for g in agent_calls if g.get("blocks") == [] and g.get("status") == 200 and not g.get("client_disconnected")).items())),
                "calls_cut_off_by_the_client": sum(1 for g in msgs if g.get("client_disconnected")),
                "empty_agent_replies": sum(1 for g in agent_calls if g.get("blocks") == [] and g.get("status") == 200 and not g.get("client_disconnected")),
                "non_200": dict(collections.Counter(g.get("status") for g in msgs if g.get("status") != 200)),
                "injected_provider_ignore": sum(1 for g in msgs if g.get("provider_ignore")),
                "calls_from_ignored_provider": sum(1 for g in msgs if (g.get("generation") or {}).get("provider_name") in set(protocol.get("provider_ignore") or [])),
                "providers": dict(sorted(collections.Counter((g.get("generation") or {}).get("provider_name") or "(no model call)" for g in msgs).items(), key=lambda kv: -kv[1])),
                "ms_first_byte": stats([g["ms_first_byte"] for g in agent_calls if g.get("ms_first_byte") is not None], 0),
                "ms_total": stats([g["ms_total"] for g in agent_calls if g.get("ms_total") is not None], 0)},
        "token_reconciliation": {"attempts_with_cli_usage": compared, "matching_openrouter_records": compared - len(mismatched), "mismatches": mismatched},
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
    out = [f"# {summary[arms[0]]['protocol']['model'] or 'model'} on SetupBench: {' vs '.join(arms)} (generated by bench/deepseek_summary.py)", "",
           "One replicate; descriptive only. Cost = sum of OpenRouter generation records per task session. The CLI's own cost is **not** used (it prices this model at a Claude fallback rate).", ""]

    def row(label: str, fn) -> str:
        return "| " + label + " | " + " | ".join(str(fn(summary[a])) for a in arms) + " |"

    out += ["| | " + " | ".join(arms) + " |", "|---|" + "---:|" * len(arms)]
    for label, fn in (
        ("Attempts", lambda s: s["attempts"]), ("Passed", lambda s: s["passed"]),
        ("Outcomes", lambda s: s["outcomes"]), ("Timed out (harness, never checked)", lambda s: s["timed_out"]),
        ("Interrupted by the 450 s watchdog / of which then passed", lambda s: f"{s['watchdog_stopped']} / {s['watchdog_stopped_then_passed']}"),
        ("Harness errors", lambda s: s["harness_errors"]),
        ("Turns per task (mean / median / p90 / max)", lambda s: "{mean} / {median} / {p90} / {max}".format(**s["turns"])),
        ("Task wall time s (mean / median / p90)", lambda s: "{mean} / {median} / {p90}".format(**s["duration_seconds"])),
        ("Tokens, OpenRouter records: prompt (incl. cached) / cached / completion", lambda s: f"{s['tokens_openrouter_records']['prompt_tokens']:,} / {s['tokens_openrouter_records']['cached_prompt_tokens']:,} / {s['tokens_openrouter_records']['completion_tokens']:,}"),
        ("Cost per task $ (mean / median / p90)", lambda s: "{mean} / {median} / {p90}".format(**s["cost_usd"]["per_task"])),
        ("Cost total $ (all calls)", lambda s: s["cost_usd"]["total_all_calls"]),
        ("OpenRouter key counter delta $ (cross-check; also counts anyone else using the key, and posts late)", lambda s: s["cost_usd"]["openrouter_key_usage_delta"] if s["cost_usd"]["openrouter_key_usage_delta"] is not None else "n/a: the arms shared one key and ran together (PROTOCOL.run.json)"),
        ("CLI-reported cost $ (not used)", lambda s: s["cost_usd"]["cli_reported_total_not_used"]),
        ("API calls / agent calls", lambda s: f"{s['api']['calls']} / {s['api']['agent_calls']}"),
        ("Empty agent replies (completed, no content) / non-200 model calls", lambda s: f"{s['api']['empty_agent_replies']} / {s['api']['non_200']}"),
        ("Empty replies by provider (the request completed with no content)", lambda s: s["api"]["empty_agent_replies_by_provider"] or "none"),
        ("Requests cut off by the client (watchdog interrupt or container kill) before finishing", lambda s: s["api"]["calls_cut_off_by_the_client"]),
        ("Cut-off requests with no OpenRouter record (possibly billed, not counted in cost)", lambda s: s["api"]["cut_off_calls_without_generation_record"]),
        ("provider.ignore injected / calls from ignored provider", lambda s: f"{s['api']['injected_provider_ignore']} / {s['api']['calls_from_ignored_provider']}"),
        ("Providers", lambda s: s["api"]["providers"]),
        ("API ms to first byte (median / p90)", lambda s: "{median} / {p90}".format(**s["api"]["ms_first_byte"])),
        ("Per-turn model reply s (median / p90)", lambda s: "{median} / {p90}".format(**s["per_turn_seconds"]["model_reply"])),
        ("Per-turn tool execution s (median / p90)", lambda s: "{median} / {p90}".format(**s["per_turn_seconds"]["tool_execution"])),
        ("Attempts whose CLI usage equals OpenRouter's records (the CLI omits aborted/retried calls and timed-out attempts)", lambda s: f"{s['token_reconciliation']['matching_openrouter_records']} / {s['token_reconciliation']['attempts_with_cli_usage']}"),
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
    summary = {a: s for a in ARMS if (s := load_arm(a))}
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
