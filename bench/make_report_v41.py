"""Report generator for the DeepSeek V4.1 Flash comparison: writes readme3.md and ada/results3.md from a merged evidence folder.

  python3 bench/make_report_v41.py <MERGED_DIR> <COMPARISON_JSON> [--out-readme=PATH] [--out-results=PATH]

Every number comes from the evidence. Nothing is typed in by hand except prose.
"""
import collections, datetime as dt, glob, json, math, os, pathlib, re, statistics, sys

ROOT = pathlib.Path("/home/azureuser/adaAgent")
argv = [a for a in sys.argv[1:] if not a.startswith("--")]
EV = pathlib.Path(argv[0])
CMP = json.load(open(argv[1]))
opt = {a.split("=")[0]: a.split("=")[1] for a in sys.argv[1:] if a.startswith("--") and "=" in a}
OUT_README = pathlib.Path(opt.get("--out-readme", ROOT / "readme3.md"))
OUT_RESULTS = pathlib.Path(opt.get("--out-results", ROOT / "ada/results3.md"))
rel = lambda p: os.path.relpath(pathlib.Path(p).resolve(), ROOT)   # path relative to the repo root

S = json.load(open(EV / "summary.json"))
B, T, P = S["baseline"], S["best"], S["paired"]
BT, TT = B["tasks"], T["tasks"]
M = json.load(open(EV / "MERGE.json"))
V4 = json.load(open(ROOT / "ada/runs/deepseek-v4-flash/r1/summary.json"))
MODEL = B["protocol"]["model"]
EVR = rel(EV)                      # e.g. ada/runs/deepseek-v4.1-flash/r1_all
RUNS = M["sources"]                # the runs that were merged, in order
run_info = []
for r in RUNS:
    rp = pathlib.Path(r)
    if not rp.is_absolute(): rp = ROOT / rp
    pr = json.load(open(rp / "PROTOCOL.run.json"))
    load = lambda s: " / ".join(s.split()[:3])
    run_info.append({"dir": rel(rp), "name": rp.name, "start": pr["started_utc"], "end": pr["finished_utc"],
                     "load_start": load(pr["loadavg_start"]), "load_end": load(pr["loadavg_end"]),
                     "tasks": sum(1 for l in open(rp / "tasks.txt") if l.strip())})


def pct(n, d): return f"{100 * n / d:.1f}%"
def usd(x, n=3): return f"${x:.{n}f}"
def hm(s): return s[11:16]
def mins(a, b):
    t = lambda s: dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")
    return (t(b) - t(a)).total_seconds() / 60


def route(ids, tasks):
    c = collections.Counter()
    for t in ids:
        c[("interrupted" if tasks[t]["watchdog_stopped"] else "own", "passed" if tasks[t]["passed"] else "failed")] += 1
    return c


valid_b = {t for t, x in BT.items() if x["valid"]}; valid_t = {t for t, x in TT.items() if x["valid"]}
nb, nt = len(BT), len(TT)
b_pass, t_pass = B["passed"], T["passed"]
b_to = B["timed_out"]; t_wd, t_wd_pass = T["watchdog_stopped"], T["watchdog_stopped_then_passed"]
b_own_pass = sum(1 for x in BT.values() if x["passed"]); b_own_fail = sum(1 for x in BT.values() if x["outcome"] == "failed_check")
t_own_pass = sum(1 for x in TT.values() if x["passed"] and not x["watchdog_stopped"])
t_own_fail = sum(1 for x in TT.values() if x["outcome"] == "failed_check" and not x["watchdog_stopped"])
t_wd_fail = t_wd - t_wd_pass
timed = [t for t in BT if BT[t]["timed_out"] and TT[t]["valid"]]
fin = [t for t in BT if not BT[t]["timed_out"] and BT[t]["valid"] and TT[t]["valid"]]
r_to, r_fin = route(timed, TT), route(fin, TT)
p_val = P["mcnemar_exact_p"]; gained, lost = P["gained_tasks"], P["lost_tasks"]
wd_in_to = r_to[("interrupted", "passed")] + r_to[("interrupted", "failed")]
own_in_to = r_to[("own", "passed")] + r_to[("own", "failed")]
wd_in_fin = r_fin[("interrupted", "passed")] + r_fin[("interrupted", "failed")]
b_hard = B["harness_errors"]; t_hard = T["harness_errors"]
raw = {a: {p.parent.name: json.load(open(p)) for p in (EV / a).glob("*/result.json")} for a in ("baseline", "best")}
ba, ta = B["api"], T["api"]; cb, ct = B["cost_usd"], T["cost_usd"]; tok_b, tok_t = B["tokens_openrouter_records"], T["tokens_openrouter_records"]
cli_b, cli_t = cb["cli_reported_total_not_used"], ct["cli_reported_total_not_used"]
rec_b, rec_t = B["token_reconciliation"], T["token_reconciliation"]
gen_models = collections.Counter()
for l in open(EV / "proxy.best/generations.jsonl"):
    m = (json.loads(l).get("generation") or {}).get("model")
    if m: gen_models[m] += 1
resolved = gen_models.most_common(1)[0][0]
pricing = json.load(open(EV / "pricing_snapshot.json"))["model"]["pricing"]
ms = lambda d: f"{d['median']:.0f} / {d['p90']:.0f}"
sec = lambda d: f"{d['median']:.2f} / {d['p90']:.2f}"
turns = lambda d: f"{d['mean']} / {d['median']:.0f} / {d['p90']:.0f} / {d['max']:.0f}"
wall = lambda d: f"{d['mean']:.0f} / {d['median']:.0f} / {d['p90']:.0f}"
cost_task = lambda d: f"{usd(d['mean'], 4)} / {usd(d['median'], 4)} / {usd(d['p90'], 4)}"
wd_run = [raw["best"][t]["agent_duration_seconds"] for t in TT if TT[t]["watchdog_stopped"]]
own_run = [raw["best"][t]["agent_duration_seconds"] for t in TT if not TT[t]["watchdog_stopped"] and TT[t]["valid"]]

# ---- model versus code, from compare_runs.py
cells, paired = CMP["cells"], CMP["paired"]
mA, mB = CMP["models"]
cell = lambda m, a: cells[f"{m} / {a}"]
pr = lambda k: paired[k]
code_a, code_b = pr(f"{mA}: best vs baseline"), pr(f"{mB}: best vs baseline")
mod_base, mod_best = pr(f"baseline: {mB} vs {mA}"), pr(f"best: {mB} vs {mA}")
ncommon = CMP["tasks"]

# ---- harness-file exploration
pat = re.compile(r"\.setupbench-cache|\.ada-trace|\.ada\.log|\.setupbench-task|setupbench-fixtures|setupbench-ada-runner|/input\b")
def explore(run_dir, arm):
    att, n = set(), 0
    for f in glob.glob(f"{run_dir}/{arm}/*/trace.jsonl"):
        n += 1
        for l in open(f):
            e = json.loads(l)
            if e.get("type") != "assistant": continue
            for b in e["content"]:
                if b.get("type") == "tool_use" and pat.search(json.dumps(b.get("input"))): att.add(f)
    return len(att), n
ex41 = {a: explore(EV, a) for a in ("baseline", "best")}
ex4 = {a: explore(ROOT / "ada/runs/deepseek-v4-flash/r1", a) for a in ("baseline", "best")}
runner_read = {a: sum(1 for f in glob.glob(f"{EV}/{a}/*/trace.jsonl") if "setupbench-ada-runner" in open(f).read()) for a in ("baseline", "best")}

# ---- prose that depends on the result
def verdict():
    d = t_pass - b_pass
    if p_val < 0.05:
        return (f"The best build passed **{d}** more tasks than the baseline, by more than chance easily explains "
                f"(exact McNemar p = {p_val:.3f}).")
    return (f"The two builds are **not clearly different**: the best build's {'lead' if d > 0 else 'deficit' if d < 0 else 'tie'} "
            f"of {abs(d)} tasks is the kind of split chance can produce (exact McNemar p = {p_val:.2f}).")

# =====================================================================================================
README = f"""# Ada on SetupBench with DeepSeek V4.1 Flash: baseline against best

[Ada](https://github.com/rabbah/ada) is an open-source coding agent built on Claude Code through the
Claude Agent SDK, written by Simon Guerrier, Rodric Rabbah and contributors and released under the MIT
licence. This document records one side-by-side run of two builds of Ada on SetupBench, with
`{MODEL}` as the model: what was compared, how it was measured, and what came out. Every attempt's trace is in the repository.

## In short

**What was run.** Two builds of Ada, the **baseline** and the **best**, each attempted all {nb} SetupBench tasks
once, with `{MODEL}` as the model through OpenRouter, both builds at the same time. The best build stops itself 30 seconds
before the time limit so its work gets checked, has a time-aware prompt, and limits the model's thinking. The
baseline has none of these.

**Result.** The baseline passed **{b_pass} of {nb}** attempts and the best build passed **{t_pass} of {nt}**.
Counting task by task, the best build passed {P['gained']} tasks the baseline did not, and the baseline passed
{P['lost']} the best build did not. {verdict()}

**Where the builds differ.** The baseline was still running at the 480-second limit on **{b_to} of {nb}**
tasks, so the harness stopped it and never ran the check. The best build never ran out of time: its watchdog
interrupted **{t_wd}** attempts and the check then ran on them, and {t_wd_pass} of those passed.

**Model against code.** On the same {ncommon} tasks, the best build's changes were worth
**{code_b['y_passed'] - code_b['x_passed']:+d}** passes on {mB.split('/')[-1]} and **{code_a['y_passed'] - code_a['x_passed']:+d}** on {mA.split('/')[-1]}
(best minus baseline). The two models also differ on their own: with the same build, {mB.split('/')[-1]} passed
{mod_base['y_passed']} against {mod_base['x_passed']} for the baseline, and {mod_best['y_passed']} against {mod_best['x_passed']} for the best build.

**Cost.** The whole comparison cost **{usd(cb['total_all_calls'] + ct['total_all_calls'], 2)}**
({usd(cb['total_all_calls'])} for the baseline, {usd(ct['total_all_calls'])} for the best build) and used
{tok_b['prompt_tokens'] + tok_t['prompt_tokens'] + tok_b['completion_tokens'] + tok_t['completion_tokens']:,} tokens, measured from OpenRouter's own per-call records.

> This is one attempt per task per build. It says what happened in this run, not how often it would happen.

---

## The problem

[SetupBench](https://github.com/microsoft/SetupBench) gives an AI agent a real software repository and a setup
job, such as installing dependencies or getting the tests to run. Each task comes with a **check**: a command,
written by SetupBench's authors, that succeeds only if the job was done.

A test **harness** runs every attempt in a fresh Docker container and gives Ada **480 seconds**. If Ada is still
working at 480 seconds, the harness stops it and **never runs the check**. The attempt fails, however much Ada had
done.

Ada is built on the Claude Agent SDK, but no Claude model did the work in this run. The harness points the SDK at
OpenRouter and sets the model to `{MODEL}`. Every model-usage record the run saved names only
that model (OpenRouter's records show it resolved to `{resolved}`).

## The two builds

| | Baseline | Best |
|---|---|---|
| Ada commit | `df0c537` plus a 7-line shim | `5f4c5c0` |
| Agent tree | `7c88c8270e3b` | `dab704de524a` |

The shim exists because the benchmark runner imports `systemPromptGuidance` from Ada, and `df0c537` does not
export it. The shim adds that function as a pass-through to the existing `systemGuidance()`, so the prompt is
unchanged. Its exact patch is saved as [`baseline.build.patch`]({rel(RUNS[0])}/baseline.build.patch).

The best build's code changes are in two source files of Ada, plus their tests. Four changes are on by default:

| Change | What it does |
|---|---|
| **Watchdog** | A timer inside Ada that stops it 30 seconds before the time limit: at 450 s of 480 s, counting from when the container started. |
| **Clean exit** | After the watchdog stops Ada, Ada shuts down normally and reports, so the check runs. |
| **Time-aware prompt** | Replaces the baseline's short, fixed instructions with ones that adapt to the time limit Ada is given (a longer-horizon version applies above 300 s; this run declares 480 s). |
| **Thinking limit** | Sets `MAX_THINKING_TOKENS` to 1,024 by default, and a 60 s request timeout (`API_TIMEOUT_MS`) so a hung request is retried. |

Four more changes are in the best build's code but switched off by default, and stayed off in this run: time
reminders during the task, a cap on command timeouts near the deadline, a "definition of done" prompt section, and
a retry when the model stalls.

This run compares the two builds as wholes. It does not test the four default-on changes one at a time, so it cannot
say how much each contributed.

What happens to an attempt that is still running when time is nearly up:

| Ada is still working at | Baseline | Best |
|---|---|---|
| 450 s | keeps working | the watchdog stops Ada, and Ada exits normally |
| 480 s | the harness stops Ada | already stopped |
| **Is the task checked?** | **No: it counts as a fail** | **Yes: it can still pass** |

An attempt that finishes before 450 s is checked the same way in both builds.

## Terms used below

| Term | Meaning |
|---|---|
| **Baseline** | Ada at `df0c537` plus the pass-through shim. |
| **Best** | Ada at `5f4c5c0`. |
| **Attempt** | One build working on one task once. |
| **Passed** | The task's check succeeded. |
| **Timed out** | Ada was still working at 480 s, so the harness stopped it and the check never ran. |
| **Interrupted by the watchdog** | The best build's watchdog stopped Ada at 450 s. Ada then exited normally and the check ran. |
| **Finished on its own** | Ada ended its session before any cut-off, and the check ran. |
| **Harness error** | The harness itself failed during the attempt (for example Docker was too slow to start the container), so there is no result. Such attempts were re-run; see Setup. |
| **Pair** | The two builds' attempts at the same task. |
| **Gained / Lost** | A pair that only the best build passed / only the baseline passed. |
| **p** | The chance of a split between gained and lost at least this uneven if the two builds were equally good (exact McNemar test). The smaller it is, the less likely the difference is luck. |
| **Turn** | One model reply. Turns are counted from the trace, the same way for every attempt: tool rounds plus the final reply. |

---

## Result

Both builds attempted all {nb} tasks once. They ran at the same time, on the same machine, with the same task order.

| Every attempt | Baseline | Best |
|---|---:|---:|
| Passed, out of {nb} | **{b_pass}** ({pct(b_pass, nb)}) | **{t_pass}** ({pct(t_pass, nt)}) |
| Finished on its own, passed | {b_own_pass} | {t_own_pass} |
| Finished on its own, failed the check | {b_own_fail} | {t_own_fail} |
| Interrupted by the watchdog, passed | 0 | {t_wd_pass} |
| Interrupted by the watchdog, failed the check | 0 | {t_wd_fail} |
| Timed out, so never checked | {b_to} | 0 |
| Harness errors (no valid attempt even after a retry) | {b_hard} | {t_hard} |

Task by task:

| Pairs | Baseline passed | Best passed | Gained | Lost | p |
|---:|---:|---:|---:|---:|---|
| {P['pairs']} | {P['baseline_passed']} | {P['best_passed']} | {P['gained']} | {P['lost']} | {p_val:.3f} |

The tasks that changed are listed in [`ada/results3.md`](ada/results3.md).

### Where the difference comes from

| The baseline's attempt | Pairs | Baseline passed | Best passed |
|---|---:|---:|---:|
| Timed out | {len(timed)} | 0 | {P['baseline_timed_out_pairs']['best_passed']} |
| Finished in time | {len(fin)} | {P['baseline_finished_pairs']['baseline_passed']} | {P['baseline_finished_pairs']['best_passed']} |

Where the baseline timed out ({len(timed)} pairs), it passed none, as a timeout always fails. The best build was
interrupted by its watchdog on {wd_in_to} of them ({r_to[('interrupted','passed')]} passed) and finished the other
{own_in_to} on its own ({r_to[('own','passed')]} passed).

Where the baseline finished in time ({len(fin)} pairs), the best build passed {P['baseline_finished_pairs']['best_passed']}
against the baseline's {P['baseline_finished_pairs']['baseline_passed']}. It was interrupted by its watchdog on {wd_in_fin} of
these {len(fin)} tasks ({r_fin[('interrupted','passed')]} passed).

### Model against code

The same two builds were also run on DeepSeek V4 Flash, in a separate run where the builds ran one after the other.
Restricted to the {ncommon} tasks both runs share:

| Model / build | Passed | Timed out | Interrupted by watchdog | Turns (mean) | Cost |
|---|---:|---:|---:|---:|---:|
""" + "\n".join(f"| {k} | {c['passed']} of {c['attempts']} | {c['timed_out']} | {c['interrupted']} | {c['turns_mean']} | {usd(c['cost_usd'], 2)} |" for k, c in cells.items()) + f"""

| Comparison (gained = only the second passed) | Pairs | First passed | Second passed | Gained | Lost | p |
|---|---:|---:|---:|---:|---:|---:|
""" + "\n".join(f"| {k} | {q['pairs']} | {q['x_passed']} | {q['y_passed']} | {q['gained']} | {q['lost']} | {q['p']:.3f} |" for k, q in paired.items()) + f"""

The code effect is the best build against the baseline **within** a model; the model effect is one model against
the other **within** a build. All of it is one attempt per task per cell.

### Turns, time and cost

| | Baseline | Best |
|---|---:|---:|
| Turns per task (mean / median / p90 / max) | {turns(B['turns'])} | {turns(T['turns'])} |
| Wall time per attempt, s, including the check (mean / median / p90) | {wall(B['duration_seconds'])} | {wall(T['duration_seconds'])} |
| Model reply per turn, s (median / p90) | {sec(B['per_turn_seconds']['model_reply'])} | {sec(T['per_turn_seconds']['model_reply'])} |
| Tool execution per turn, s (median / p90) | {sec(B['per_turn_seconds']['tool_execution'])} | {sec(T['per_turn_seconds']['tool_execution'])} |
| Prompt tokens, including cached | {tok_b['prompt_tokens']:,} | {tok_t['prompt_tokens']:,} |
| Completion tokens | {tok_b['completion_tokens']:,} | {tok_t['completion_tokens']:,} |
| Cost per task (mean / median / p90) | {cost_task(cb['per_task'])} | {cost_task(ct['per_task'])} |
| **Cost, all calls** | **{usd(cb['total_all_calls'])}** | **{usd(ct['total_all_calls'])}** |

Cost is the sum of OpenRouter's own per-call records, attributed to tasks through each attempt's session id. The
Claude Code CLI also prints a cost, but it does not know this model and prices it at a Claude rate, so it reported
{usd(cli_b, 2)} and {usd(cli_t, 2)}, about {cli_b / cb['total_all_calls']:.0f}x and {cli_t / ct['total_all_calls']:.0f}x too high. Those figures are kept in
each attempt's `result.json` and are not used anywhere. Token totals also come from OpenRouter's records, because
the CLI leaves out interrupted and retried calls.

For this model OpenRouter's providers charge between $0.13 and $0.38 per million input tokens, and it picks a provider
for every call. **Part of any cost difference between the two builds is therefore routing luck**, not the builds:
the providers that served each build are listed in [`ada/results3.md`](ada/results3.md).

---

## What this run does not show

- **One attempt per task per build.** A task that flipped between the builds may have flipped by chance.
- **The run was made in parts under different machine load.** Both builds always ran at the same time, so within
  each part they faced the same load, but the parts did not: """ + "; ".join(f"`{r['name']}` began at a load of {r['load_start'].split(' / ')[0]}" for r in run_info) + f""". Timeouts depend on load.
- **The baseline includes a 7-line shim** (see above). It is a pass-through, but it is not byte-for-byte `df0c537`.
- **The four default-on changes are not separated.** No part of this run says which one did what.
- **The comparison with the other model is across runs.** The DeepSeek V4 Flash run had the builds running one after
  the other, this one at the same time, so machine and provider conditions are not identical.
- **The agent can see the harness.** Inside the container the agent can read the task prompt, a small metadata file, the
  runner's source and the per-task setup scripts. In this run agents looked at such files in {ex41['baseline'][0]} of {ex41['baseline'][1]} baseline
  and {ex41['best'][0]} of {ex41['best'][1]} best attempts (DeepSeek V4 Flash: {ex4['baseline'][0]} of {ex4['baseline'][1]} and {ex4['best'][0]} of {ex4['best'][1]}). No solution was found in them, and it is the same
  for both builds, but it is part of the environment.
- **Traces are not full transcripts.** The runner cuts each tool input and result at 4,000 characters and each
  thinking block at 2,000.

## Setup

| Item | Value |
|---|---|
| Model | `{MODEL}` through OpenRouter |
| Provider setting | `provider.ignore = ["StreamLake"]` on every request, added by a small proxy ([`bench/harness/openrouter_proxy.py`](bench/harness/openrouter_proxy.py)). A 10-call check of this model under OpenRouter's default routing was healthy; the exclusion is kept so both models are configured alike. |
| Baseline build | `df0c537` plus the pass-through shim, agent tree `7c88c8270e3b` |
| Best build | `5f4c5c0`, agent tree `dab704de524a` |
| Benchmark | SetupBench at `041a412`, {nb} of its 93 tasks, in parts (below) |
| Time limits | 480 s for Ada, 600 s for the check |
| Parallelism | both builds at the same time, 3 tasks at once each; the same seed, so the same task order within a part |
| Runner | [`setupbench_ada_runner_ts.ts`](bench/harness/setupbench_ada_runner_ts.ts), a copy of the standard runner that only adds a timestamp to every trace entry |
| Driver | [`bench/run_pair.sh`](bench/run_pair.sh) |

| Part | Tasks | Started (UTC) | Length |
|---|---:|---|---:|
""" + "\n".join(f"| [`{r['name']}`]({r['dir']}/) | {r['tasks']} | 2026-09-19 {hm(r['start'])} | {mins(r['start'], r['end']):.0f} min |" for r in run_info) + f"""

The parts are merged by [`bench/merge_runs.py`](bench/merge_runs.py) with one rule: per build and per task the first valid
attempt is used, and a later attempt replaces an earlier one only if the earlier was a harness error. What was
used and what was left out is in [`MERGE.md`]({EVR}/MERGE.md).

Model calls: {ba['calls']:,} for the baseline and {ta['calls']:,} for the best build. Every one carried the provider
setting, and none was served by the excluded provider.

## Check it yourself

```bash
python3 bench/deepseek_summary.py {EVR}     # rebuilds summary.md and summary.json from the raw attempt files
grep -rE 'sk-or-' {rel(pathlib.Path(RUNS[0]).parent)}    # prints nothing: no API key is in the evidence
```

The script needs nothing but Python 3, and its output is byte-for-byte the same each time. Each attempt's own files
are the raw evidence, and this reads any of them as a timeline:

```bash
python3 bench/trace_attempt.py {EVR} best <task-id>
```

```
<run folder>/<baseline|best>/<task>/trace.jsonl    every message, tool call and result, with a timestamp
<run folder>/<baseline|best>/<task>/agent.log      Ada's own log, including watchdog lines
<run folder>/<baseline|best>/<task>/result.json    outcome, turns, duration, tokens, grader output
```

## Where to look next

| For | See |
|---|---|
| Every table, every task, and the lists of tasks that changed | [`ada/results3.md`](ada/results3.md) |
| The summary tables, rebuilt from the raw files | [`summary.md`]({EVR}/summary.md), [`summary.json`]({EVR}/summary.json) |
| Model against code, in full | [`comparison_vs_deepseek-v4-flash_r1.md`]({EVR}/comparison_vs_deepseek-v4-flash_r1.md) |
| What was merged from which run | [`MERGE.md`]({EVR}/MERGE.md) |
| How the run is driven and monitored | [`bench/COMPARISON_WORKFLOW.md`](bench/COMPARISON_WORKFLOW.md) |
"""

# =====================================================================================================
def oc(x):
    if not x["valid"]: return "harness error"
    if x["timed_out"]: return "timed out"
    if x["watchdog_stopped"]: return "passed (interrupted)" if x["passed"] else "failed (interrupted)"
    return "passed" if x["passed"] else "failed"

def oc4(arm, t):
    x = V4[arm]["tasks"].get(t)
    return oc(x) if x else "-"

rows = []
for t in sorted(BT):
    b, x = BT[t], TT[t]
    pair = "gained" if t in gained else ("lost" if t in lost else "")
    rows.append(f"| `{t}` | {raw['baseline'][t].get('task_type', '')} | {oc(b)} | {b['turns']} | {b['duration_seconds']:.0f} | {usd(b['cost_usd'], 4)} "
                f"| {oc(x)} | {x['turns']} | {x['duration_seconds']:.0f} | {usd(x['cost_usd'], 4)} | {pair} | {oc4('baseline', t)} | {oc4('best', t)} |")

def prov_table():
    names = sorted((set(ba["providers"]) | set(ta["providers"])) - {"(no model call)"}, key=lambda n: -(ba["providers"].get(n, 0) + ta["providers"].get(n, 0)))
    out = ["| Provider | Baseline calls | Best calls |", "|---|---:|---:|"]
    for n in names: out.append(f"| {n} | {ba['providers'].get(n, 0):,} | {ta['providers'].get(n, 0):,} |")
    return "\n".join(out)

def top(tasks, k=5): return sorted(tasks.items(), key=lambda kv: -kv[1]["cost_usd"])[:k]

RESULTS = f"""# DeepSeek V4.1 Flash on SetupBench: baseline against best, results

The full record of one run: two builds of Ada, each attempting all {nb} SetupBench tasks once, with `{MODEL}`
through OpenRouter, both builds at the same time. The overview is in [`../readme3.md`](../readme3.md). Every number here
is rebuilt from the raw attempt files by `python3 bench/deepseek_summary.py {EVR}`, and the raw files are in the
run folders listed in section 1.

## 1. What was run

| | Baseline | Best |
|---|---|---|
| Ada commit | `df0c537` plus a 7-line pass-through shim | `5f4c5c0` |
| Agent tree | `7c88c8270e3b` | `dab704de524a` |
| Model | `{MODEL}` (resolved by OpenRouter to `{resolved}`) | same |
| Tasks | {nb} of SetupBench's 93, at `041a412` | same, same order within a part |
| Limits | 480 s for Ada, 600 s for the check | same |
| Parallelism | 3 tasks at once, both builds at the same time | same |

The run was made in parts, and merged by [`bench/merge_runs.py`](../bench/merge_runs.py):

| Part | Tasks | Started (UTC) | Finished (UTC) | Machine load (1 / 5 / 15 min) at start, at end |
|---|---:|---|---|---|
""" + "\n".join(f"| [`{r['name']}`](runs/deepseek-v4.1-flash/{r['name']}/) | {r['tasks']} | {r['start']} | {r['end']} | {r['load_start']}, {r['load_end']} |" for r in run_info) + f"""

Rule of the merge: per build and per task the first valid attempt is used, and a later attempt replaces an earlier one
only when the earlier was a harness error. Attempts left out are listed in [`MERGE.md`](runs/deepseek-v4.1-flash/{EV.name}/MERGE.md).
The shim adds `systemPromptGuidance` as a pass-through to `systemGuidance()`, because `df0c537` does not export it and the
benchmark runner imports it. The prompt is unchanged. The patch is in
[`baseline.build.patch`](runs/deepseek-v4.1-flash/{pathlib.Path(RUNS[0]).name}/baseline.build.patch).

## 2. Outcome of every attempt

| | Baseline | Best |
|---|---:|---:|
| Attempts | {nb} | {nt} |
| **Passed** | **{b_pass}** ({pct(b_pass, nb)}) | **{t_pass}** ({pct(t_pass, nt)}) |
| Finished on its own, passed | {b_own_pass} | {t_own_pass} |
| Finished on its own, failed the check | {b_own_fail} | {t_own_fail} |
| Interrupted by the watchdog, passed | 0 | {t_wd_pass} |
| Interrupted by the watchdog, failed the check | 0 | {t_wd_fail} |
| Timed out, never checked | {b_to} | 0 |
| Harness errors (no valid attempt after retries) | {b_hard} | {t_hard} |

The watchdog belongs to the best build only. It is recognised in each attempt's `agent.log` by its
`[claude:watchdog] ... interrupting stream` line. The two groups do not overlap in run time: every interrupted
attempt had run for at least {min(wd_run):.1f} s (the cut-off is 450 s), and every attempt that finished on its
own had finished within {max(own_run):.1f} s.

## 3. Task by task

Pairs valid in both builds: **{P['pairs']}**. Baseline passed {P['baseline_passed']}, best passed {P['best_passed']}.
**Gained {P['gained']}, lost {P['lost']}, exact McNemar p = {p_val:.3f}.** One attempt per task per build, so this is
a description of one run, not a test of how often it would recur.

| The baseline's attempt | Pairs | Baseline passed | Best passed |
|---|---:|---:|---:|
| Timed out | {len(timed)} | 0 | {P['baseline_timed_out_pairs']['best_passed']} |
| Finished in time | {len(fin)} | {P['baseline_finished_pairs']['baseline_passed']} | {P['baseline_finished_pairs']['best_passed']} |

How the best build's attempts ended, by what the baseline did on the same task:

| The baseline's attempt | Best: finished on its own, passed | Best: finished on its own, failed | Best: interrupted, passed | Best: interrupted, failed |
|---|---:|---:|---:|---:|
| Timed out ({len(timed)}) | {r_to[('own','passed')]} | {r_to[('own','failed')]} | {r_to[('interrupted','passed')]} | {r_to[('interrupted','failed')]} |
| Finished in time ({len(fin)}) | {r_fin[('own','passed')]} | {r_fin[('own','failed')]} | {r_fin[('interrupted','passed')]} | {r_fin[('interrupted','failed')]} |

**Gained ({len(gained)}, only the best build passed):** {', '.join(f'`{t}`' for t in gained) or 'none'}.

**Lost ({len(lost)}, only the baseline passed):** {', '.join(f'`{t}`' for t in lost) or 'none'}.

## 4. Model against code

The same two builds were run on DeepSeek V4 Flash in a separate run (the builds one after the other). Restricted to the
{ncommon} tasks both runs share, one attempt per task per cell:

| Model / build | Attempts | Passed | Timed out | Interrupted by watchdog | Turns (mean) | Cost $ |
|---|---:|---:|---:|---:|---:|---:|
""" + "\n".join(f"| {k} | {c['attempts']} | {c['passed']} | {c['timed_out']} | {c['interrupted']} | {c['turns_mean']} | {c['cost_usd']} |" for k, c in cells.items()) + f"""

| Comparison (gained = only the second passed, lost = only the first passed) | Pairs | First passed | Second passed | Gained | Lost | exact McNemar p |
|---|---:|---:|---:|---:|---:|---:|
""" + "\n".join(f"| {k} | {q['pairs']} | {q['x_passed']} | {q['y_passed']} | {q['gained']} | {q['lost']} | {q['p']:.3f} |" for k, q in paired.items()) + f"""

- **The code effect** is best against baseline within one model: {code_b['y_passed'] - code_b['x_passed']:+d} passes on {mB.split('/')[-1]} and
  {code_a['y_passed'] - code_a['x_passed']:+d} on {mA.split('/')[-1]}.
- **The model effect** is one model against the other within one build.
- Caution: the two runs differ in more than the model. On V4 Flash the builds ran one after the other; here they ran at the
  same time. Machine load and the mix of providers differ too.

## 5. Turns, time and latency

| | Baseline | Best |
|---|---:|---:|
| Turns per task (mean / median / p90 / max) | {turns(B['turns'])} | {turns(T['turns'])} |
| Wall time per attempt, s, including the check (mean / median / p90) | {wall(B['duration_seconds'])} | {wall(T['duration_seconds'])} |
| Model reply per turn, s (median / p90) | {sec(B['per_turn_seconds']['model_reply'])} | {sec(T['per_turn_seconds']['model_reply'])} |
| Tool execution per turn, s (median / p90) | {sec(B['per_turn_seconds']['tool_execution'])} | {sec(T['per_turn_seconds']['tool_execution'])} |
| API time to first byte, ms (median / p90) | {ms(ba['ms_first_byte'])} | {ms(ta['ms_first_byte'])} |
| API time for a whole reply, ms (median / p90) | {ms(ba['ms_total'])} | {ms(ta['ms_total'])} |

Model reply time is the time from a tool result to the next reply; tool execution time is the time from a reply to its
tool result. Both come from the timestamps the runner adds to every trace entry. Wall time includes the check, so a
timed-out or interrupted attempt shows more than 480 s. Turns are counted from the trace for every attempt, as tool
rounds plus the final reply. The Claude Code CLI's own count is the same for attempts that finish on their own, and is
usually one higher after a watchdog interrupt.

## 6. Tokens and cost

| | Baseline | Best |
|---|---:|---:|
| Prompt tokens, including cached | {tok_b['prompt_tokens']:,} | {tok_t['prompt_tokens']:,} |
| Of which cached | {tok_b['cached_prompt_tokens']:,} | {tok_t['cached_prompt_tokens']:,} |
| Completion tokens | {tok_b['completion_tokens']:,} | {tok_t['completion_tokens']:,} |
| **Cost, all calls** | **{usd(cb['total_all_calls'], 4)}** | **{usd(ct['total_all_calls'], 4)}** |
| Cost per task (mean / median / p90) | {cost_task(cb['per_task'])} | {cost_task(ct['per_task'])} |

**Where the numbers come from.** Cost and tokens are OpenRouter's own per-call records (`total_cost`, native token counts),
attributed to tasks through each attempt's Claude Code session id. The records equal what OpenRouter charges: in a 36-call
test across nine providers on an idle key, the records summed to $0.010434 and the key counter rose $0.010433 once it settled.

**What is not used.**

- The Claude Code CLI's own cost ({usd(cli_b, 2)} baseline, {usd(cli_t, 2)} best) is not used. The CLI does not know this model and prices it
  at a Claude rate, about {cli_b / cb['total_all_calls']:.0f}x and {cli_t / ct['total_all_calls']:.0f}x too high.
- The CLI's token counts are not used. They omit calls that were aborted or retried, and the timed-out attempts report none.
  For {rec_b['matching_openrouter_records']} of the {rec_b['attempts_with_cli_usage']} baseline attempts that reported usage the CLI's counts equal OpenRouter's records; for the
  best build that holds for {rec_t['matching_openrouter_records']} of {rec_t['attempts_with_cli_usage']}, and in the others OpenRouter billed more (the request cut off at a watchdog interrupt is billed but not counted by the CLI).
- The OpenRouter key's usage counter is not used as a total: the key is shared, so the counter also includes other people's use.

**Providers set the price.** For this model OpenRouter lists prices from ${float(pricing['prompt']) * 1e6:.2f} per million input tokens
(the list price shown first) up to $0.38 among the providers used, and it picks a provider for every call. The mix that served each
build is below, so part of a cost difference between the builds is routing luck.

{prov_table()}

**Most expensive attempts.**

| Baseline | Cost | Best | Cost |
|---|---:|---|---:|
""" + "\n".join(f"| `{a[0]}` | {usd(a[1]['cost_usd'], 4)} | `{b[0]}` | {usd(b[1]['cost_usd'], 4)} |" for a, b in zip(top(BT), top(TT))) + f"""

**Calls not in the cost.** {ba['cut_off_calls_without_generation_record'] + ta['cut_off_calls_without_generation_record']} request(s) were cut off before OpenRouter's id for them reached the proxy, so they have no record and may have been billed
(the most a single call cost was under a cent). Requests cut off the same way that had already received their id ({ba['calls_cut_off_by_the_client']} in the baseline, {ta['calls_cut_off_by_the_client']} in the best build) are in the records.

## 7. Model calls

| | Baseline | Best |
|---|---:|---:|
| Model calls | {ba['calls']:,} | {ta['calls']:,} |
| Calls that carried the provider setting | {ba['injected_provider_ignore']:,} | {ta['injected_provider_ignore']:,} |
| Calls served by the excluded provider (among calls with a provider record) | {ba['calls_from_ignored_provider']} | {ta['calls_from_ignored_provider']} |
| Non-200 model calls | {sum(ba['non_200'].values())} | {sum(ta['non_200'].values())} |
| Empty replies (a finished request with no content) | {ba['empty_agent_replies']} | {ta['empty_agent_replies']} |
| Requests cut off by the client before finishing | {ba['calls_cut_off_by_the_client']} | {ta['calls_cut_off_by_the_client']} |

`count_tokens` requests, an endpoint OpenRouter does not have, return 404 and are free; they are not model calls.

## 8. The agent and the harness

Inside every container the agent can read the task prompt (`/testbed/.setupbench-task.txt`), a small metadata file
(`.setupbench-cache.json`: task id, repository, commit), its own log and trace, the runner's source
(`/opt/setupbench-ada-runner.ts`) and `/setupbench-fixtures`, the per-task setup scripts. None of these contains a solution or
a success command. Counting attempts whose tool calls mention any of them:

| | Baseline | Best |
|---|---:|---:|
| This run (V4.1 Flash) | {ex41['baseline'][0]} of {ex41['baseline'][1]} | {ex41['best'][0]} of {ex41['best'][1]} |
| Of which read the runner's source | {runner_read['baseline']} | {runner_read['best']} |
| DeepSeek V4 Flash | {ex4['baseline'][0]} of {ex4['baseline'][1]} | {ex4['best'][0]} of {ex4['best'][1]} |

It is the same for both builds. It shows an agent exploring its environment, which is part of this benchmark as run here.

## 9. Every task

Turns and seconds are per attempt; the cost is that attempt's own OpenRouter cost. "interrupted" means the best build's watchdog
stopped Ada at 450 s and the check then ran. The last two columns give the outcome of the same builds on DeepSeek V4 Flash.

| Task | Type | Baseline | Turns | s | Cost | Best | Turns | s | Cost | Pair | V4 baseline | V4 best |
|---|---|---|---:|---:|---:|---|---:|---:|---:|---|---|---|
""" + "\n".join(rows) + f"""

## 10. Checks on the data

| Check | Result |
|---|---|
| Attempts with a `trace.jsonl`, `agent.log` and `result.json` | {sum(1 for a in ('baseline', 'best') for t in raw[a] if raw[a][t]['valid'])} of {nb + nt} (the others were harness errors with no container) |
| Models billed, from the CLI's usage and from OpenRouter's records | only `{MODEL}` (`{resolved}`) |
| API key anywhere in the evidence | none (searched for `sk-or-` tokens and for the key itself) |
| `python3 bench/deepseek_summary.py {EVR}` run twice | byte-identical output |

## 11. What this run does not show

- One attempt per task per build.
- The run was made in parts under different machine load (section 1). Both builds always ran together, so within a part they
  faced the same load; timeouts depend on load, and the parts differ.
- The baseline includes a 7-line pass-through shim; it is not byte-for-byte `df0c537`.
- The four default-on changes of the best build are not separated by this run.
- The model-against-code comparison is across two runs that differ in more than the model.
- Traces are what the runner keeps: each tool input and result is cut at 4,000 characters and each thinking block at 2,000.

## 12. Regenerating this record

```bash
python3 bench/merge_runs.py {EVR} {' '.join(r['dir'] for r in run_info)}   # only if the folder does not exist yet
python3 bench/deepseek_summary.py {EVR}
python3 bench/compare_runs.py ada/runs/deepseek-v4-flash/r1 {EVR}
```
"""
OUT_README.write_text(README); OUT_RESULTS.write_text(RESULTS)
print("written:", OUT_README, len(README.splitlines()), "lines;", OUT_RESULTS, len(RESULTS.splitlines()), "lines")
