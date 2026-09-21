#!/usr/bin/env python3
"""Read one attempt as a timeline (plain Python, no dependencies).

  python3 bench/trace_attempt.py <EVIDENCE_DIR> <baseline|best> <task_id> [--full] [--calls]
  e.g. python3 bench/trace_attempt.py ada/runs/deepseek-v4-flash/r1 best bolsote-isoduration-ae0bd61

Shows the outcome and cost of the attempt, the grader's last output, then every model reply, tool call and tool result with
the seconds since the attempt started. --full stops the 120-character cut on each line. --calls adds one line per model call
(provider, tokens, cost) from the proxy log. Note: the runner itself cuts tool inputs/results at 4000 characters
and thinking at 2000, so a trace is not a full transcript.
"""
import json, re, sys
from pathlib import Path

args = [a for a in sys.argv[1:] if not a.startswith("--")]
full, calls = "--full" in sys.argv, "--calls" in sys.argv
if len(args) != 3:
    sys.exit(__doc__)
ev, arm, task = Path(args[0]), args[1], args[2]
d = ev / arm / task
if not d.is_dir():
    sys.exit(f"no such attempt: {d}\nlist tasks with: ls {ev}/{arm}")
res = json.load(open(d / "result.json"))
log = (d / "agent.log").read_text(errors="replace")
trace = [json.loads(l) for l in (d / "trace.jsonl").read_text().splitlines() if l.strip()]
m = re.search(r'"session_id":"([0-9a-f-]{36})"', log)
sid = m.group(1) if m else None
interrupted = bool(re.search(r"\[claude:watchdog\][^\n]*interrupting stream", log))
gens = []
gp = ev / f"proxy.{arm}" / "generations.jsonl"
if gp.exists():
    gens = [json.loads(l) for l in gp.read_text().splitlines() if l.strip()]
    gens = [g for g in gens if g.get("session_id") == sid]
cost = sum((g.get("generation") or {}).get("total_cost") or 0 for g in gens)
prov = {}
for g in gens:
    p = (g.get("generation") or {}).get("provider_name") or "?"
    prov[p] = prov.get(p, 0) + 1
outcome = "TIMED OUT (never checked)" if res["timed_out"] else ("PASSED" if res["passed"] else "FAILED the check")
print(f"== {arm} / {task}  ({ev})")
print(f"outcome : {outcome}{' | interrupted by the 450 s watchdog' if interrupted else ''}")
print(f"numbers : turns {res['turns'] or res.get('turns_from_trace')} | wall {res['duration_seconds']:.0f}s (agent {res.get('agent_duration_seconds', 0):.0f}s)"
      f" | {len(gens)} model calls, cost ${cost:.4f} | providers {prov}")
if res.get("grader_output"):
    print("grader  : rc", res.get("grader_returncode"), "|", res["grader_output"].strip().replace("\n", " | ")[-300:])
cut = (lambda s: s) if full else (lambda s: s if len(s) <= 120 else s[:117] + "...")
one = lambda x: re.sub(r"\s+", " ", x if isinstance(x, str) else json.dumps(x)).strip()
print("\ntimeline (seconds since the first entry):")
t0 = next((e["ts"] for e in trace if e.get("ts")), None)
for e in trace:
    t = f"{(e['ts'] - t0) / 1000:7.1f}s" if e.get("ts") and t0 else "       ?"
    if e["type"] == "system":
        print(f"{t}  system {e.get('subtype')}")
    elif e["type"] == "assistant":
        for b in e["content"]:
            if b["type"] == "thinking": print(f"{t}  thinking   {cut(one(b.get('thinking', '')))}")
            elif b["type"] == "text":   print(f"{t}  says       {cut(one(b.get('text', '')))}")
            elif b["type"] == "tool_use": print(f"{t}  TOOL {b['name']:<6} {cut(one(b.get('input', '')))}")
    elif e["type"] == "user":
        for b in e["content"]:
            if b["type"] == "tool_result": print(f"{t}  result{' (ERROR)' if b.get('is_error') else '':<9} {cut(one(b.get('content', '')))}")
            else: print(f"{t}  user message (no tool result)")
    elif e["type"] == "result":
        print(f"{t}  END        stop={e.get('stop_reason')} turns={e.get('num_turns')} is_error={e.get('is_error')}")
if calls:
    print("\nmodel calls (from the proxy log):")
    for g in sorted(gens, key=lambda g: g["ts"]):
        gg = g.get("generation") or {}
        print(f"  {g['ts']:.0f}  {gg.get('provider_name') or '?':<14} prompt {gg.get('native_tokens_prompt')} (cached {gg.get('native_tokens_cached')}) out {gg.get('native_tokens_completion')} "
              f"${gg.get('total_cost') or 0:.5f} first byte {g.get('ms_first_byte')}ms {'CUT OFF' if g.get('client_disconnected') else ''}{'EMPTY' if g.get('blocks') == [] and not g.get('client_disconnected') else ''}")
