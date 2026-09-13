#!/usr/bin/env python3
"""Mine baseline traces for optimization signals.

Reads arm B (ada) per-trial ada-events.jsonl + result.json to characterize:
  - tool_result payload size distribution (target of E2 tool_result capping)
  - tool_call arg sizes (also a cost lever)
  - cache-read ratio per trial (target of E3 cache stabilization)
  - output tokens per trial (verbose model output)
  - error clusters (AgentTimeoutError etc.)
Outputs a compact signal table to stdout and eval/analysis/trace-signals.md.
"""
import json
import glob
from pathlib import Path

JOBS = Path("/root/optimize_ada/eval/jobs/baseline-armB")


def analyze_trial(trial_dir: Path) -> dict:
    events_file = trial_dir / "agent" / "ada-events.jsonl"
    trial = trial_dir.name
    sig = {
        "trial": trial,
        "n_tool_results": 0,
        "result_chars": [],
        "n_tool_args": 0,
        "arg_chars": [],
        "max_result": 0,
        "total_result_chars": 0,
        "tool_names": {},
    }
    if not events_file.exists():
        return sig
    for line in events_file.read_text(errors="replace").splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        d = e.get("data") or {}
        t = d.get("type")
        if t == "TOOL_CALL_RESULT":
            c = d.get("content")
            if isinstance(c, str):
                n = len(c)
            elif isinstance(c, dict):
                n = len(json.dumps(c))
            else:
                n = 0
            sig["n_tool_results"] += 1
            sig["result_chars"].append(n)
            sig["total_result_chars"] += n
            sig["max_result"] = max(sig["max_result"], n)
        elif t == "TOOL_CALL_START":
            sig["tool_names"][d.get("toolCallName") or "?"] = (
                sig["tool_names"].get(d.get("toolCallName") or "?", 0) + 1
            )
        elif t == "TOOL_CALL_ARGS":
            a = d.get("content")
            n = len(json.dumps(a)) if a is not None else 0
            sig["n_tool_args"] += 1
            sig["arg_chars"].append(n)
    sig["result_chars"].sort(reverse=True)
    return sig


def main():
    rows = []
    for rf in sorted(glob.glob(str(JOBS / "*" / "result.json"))):
        trial_dir = Path(rf).parent
        d = json.load(open(rf))
        sig = analyze_trial(trial_dir)
        ar = d.get("agent_result") or {}
        md = ar.get("metadata") or {}
        sig["task"] = d.get("task_name")
        sig["cost"] = ar.get("cost_usd")
        sig["n_output_tokens"] = ar.get("n_output_tokens")
        sig["n_input_tokens"] = ar.get("n_input_tokens")
        sig["n_cache_tokens"] = ar.get("n_cache_tokens")
        ni = sig["n_input_tokens"] or 0
        nc = sig["n_cache_tokens"] or 0
        sig["cache_read_ratio"] = (nc / ni) if ni else None
        sig["num_turns"] = md.get("num_turns")
        sig["exception"] = bool(d.get("exception_info"))
        rows.append(sig)

    # ---- aggregate ---------------------------------------------------------
    all_results = sorted(
        (n for r in rows for n in r["result_chars"]), reverse=True
    )
    print(f"Trials: {len(rows)}")
    print(f"\nTool results total: {len(all_results)}")
    if all_results:
        print(f"  max chars: {all_results[0]}")
        print(f"  p99: {all_results[int(len(all_results)*0.01)] if len(all_results)>=100 else all_results[-1]}")
        print(f"  p95: {all_results[int(len(all_results)*0.05)] if len(all_results)>=20 else all_results[-1]}")
        print(f"  p90: {all_results[int(len(all_results)*0.10)] if len(all_results)>=10 else all_results[-1]}")
        print(f"  median: {all_results[len(all_results)//2]}")
        print(f"  total chars: {sum(all_results)}")
        over1k = sum(1 for n in all_results if n > 1000)
        over5k = sum(1 for n in all_results if n > 5000)
        over10k = sum(1 for n in all_results if n > 10000)
        over50k = sum(1 for n in all_results if n > 50000)
        print(f"  >1k: {over1k}  >5k: {over5k}  >10k: {over10k}  >50k: {over50k}")
        if over10k:
            print(f"  chars in >10k results: {sum(n for n in all_results if n>10000)} "
                  f"({100*sum(n for n in all_results if n>10000)/sum(all_results):.0f}% of total)")

    cache = [r["cache_read_ratio"] for r in rows if r["cache_read_ratio"] is not None]
    if cache:
        print(f"\nCache-read ratio: mean {sum(cache)/len(cache):.3f}, "
              f"min {min(cache):.3f}, max {max(cache):.3f} (n={len(cache)})")
    outs = [r["n_output_tokens"] for r in rows if r["n_output_tokens"] is not None]
    if outs:
        print(f"Output tokens/trial: mean {sum(outs)/len(outs):.0f}, "
              f"max {max(outs):.0f} (n={len(outs)})")

    print("\nPer-trial top tool-result consumers (top 8 by total_result_chars):")
    for r in sorted(rows, key=lambda x: -x["total_result_chars"])[:8]:
        topn = ", ".join(f"{k}:{v}" for k, v in sorted(
            r["tool_names"].items(), key=lambda kv: -kv[1])[:4])
        print(f"  {r['task']:28s} total={r['total_result_chars']:>9,} "
              f"max={r['max_result']:>7,} n={r['n_tool_results']:>2} cost=${r['cost'] or 0:.4f} "
              f"tools=[{topn}]")

    # save markdown
    L = ["# Trace signals from baseline arm B (ada)", ""]
    L.append(f"- {len(rows)} trials analyzed.")
    L.append(f"- Tool results: {len(all_results)} total.")
    if all_results:
        L.append(f"- max {all_results[0]} chars; median {all_results[len(all_results)//2]};")
        L.append(f"- p90 {all_results[int(len(all_results)*0.10)] if len(all_results)>=10 else all_results[-1]};")
        L.append(f"- total {sum(all_results):,} chars; >10k results {over10k} "
                 f"({100*sum(n for n in all_results if n>10000)/sum(all_results):.0f}% of chars)")
    L.append("")
    if cache:
        L.append(f"- Mean cache-read ratio: {sum(cache)/len(cache):.3f} "
                 f"(min {min(cache):.3f}, max {max(cache):.3f}).")
    if outs:
        L.append(f"- Mean output tokens/trial: {sum(outs)/len(outs):.0f} (max {max(outs):.0f}).")
    L.append("")
    L.append("Per-trial top tool-result consumers:")
    for r in sorted(rows, key=lambda x: -x["total_result_chars"])[:8]:
        L.append(f"- {r['task']}: total {r['total_result_chars']:,} chars, "
                 f"max {r['max_result']:,}, n={r['n_tool_results']}, cost ${r['cost'] or 0:.4f}")
    L.append("")
    L.append("_Generated by eval/analysis/mine_traces.py_")
    Path("/root/optimize_ada/eval/analysis/trace-signals.md").write_text("\n".join(L) + "\n")
    print("\nWrote eval/analysis/trace-signals.md")


if __name__ == "__main__":
    main()
