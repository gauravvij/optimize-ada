# Ada on SetupBench: an optimisation campaign

[Ada](https://github.com/rabbah/ada) is an open-source coding agent built on Claude Code
through the Claude Agent SDK, written by Simon Guerrier, Rodric Rabbah and contributors and
released under the MIT licence. This branch records one campaign to make Ada pass more
SetupBench tasks: what was changed, how it was measured, and what held up.

## In short

**Before.** The build the campaign started from, the **origin build**, passed **68 of 162**
attempts on SetupBench (81 tasks, each run twice). Most of its failures were never checked at all:
**84 of its 94 failures** were attempts still running at the 480-second time limit, which the
harness stopped without ever checking the work.

**What changed.** The shipped build stops itself 30 seconds before the limit and exits cleanly,
so its work gets checked. It also has a time-aware prompt and a limit on the model's
thinking.

**After.** The shipped build passed **99 of 162** attempts and never ran out of time. Counting
only tasks where neither build hit a harness error, it passed 98 of 157 against the origin
build's 67 (p = 7.92e-09). The extra passes are on tasks the origin build used to run out of
time on; where the origin build finished in time, both builds did about the same.

**Second model.** Both builds attempted all 81 tasks once more with `deepseek/deepseek-v4.1-flash`
as the model. The baseline passed **34 of 81** and the best build **48 of 81** (16 gained,
2 lost, p = 1.31e-03): the same pattern, with the baseline out of time on 41 tasks and the
best build on none, and about the same where the baseline finished in time (34 against 33).
One replicate only, so it checks the mechanism on another model rather than retesting the
main result.

> **Every change, evaluation run and verification in this campaign was carried out
> autonomously by [NEO](https://heyneo.com) — Your Autonomous AI Engineering Agent.**
> NEO traced the failures, wrote the changes, ran the paired evaluations, withdrew two of
> its own headlines, and confirmed the one result that held with a two-replicate run.

[![NEO](https://img.shields.io/badge/Built%20autonomously%20by-NEO-0B0B0B?style=for-the-badge)](https://heyneo.com)
[![VS Code Extension](https://img.shields.io/badge/VS%20Code-Get%20the%20Extension-007ACC?style=for-the-badge&logo=visualstudiocode&logoColor=white)](https://marketplace.visualstudio.com/items?itemName=NeoResearchInc.heyneo)
[![Cursor Extension](https://img.shields.io/badge/Cursor-Get%20the%20Extension-1F1F1F?style=for-the-badge&logo=cursor&logoColor=white)](https://marketplace.cursorapi.com/items/?itemName=NeoResearchInc.heyneo)
[![Neo MCP Docs](https://img.shields.io/badge/Neo%20MCP-Documentation-6E56CF?style=for-the-badge&logo=readthedocs&logoColor=white)](https://docs.heyneo.com/neo-mcp)

---

## The problem

[SetupBench](https://github.com/microsoft/SetupBench) gives an AI agent a real software
repository and a setup job, such as installing dependencies or getting the tests to run. Each
task comes with a **check**: a command, written by SetupBench's authors, that succeeds only if
the job was done.

A test **harness** runs every attempt in a fresh Docker container and gives Ada
**480 seconds**. If Ada is still working at 480 seconds, the harness stops it and **never runs
the check**. The attempt fails, however much Ada had done. The origin build ran out of time on
40 to 53 of the 81 tasks, depending on the run.

Ada is built on the Claude Agent SDK, but no Claude model did the work in this campaign. The
harness points the SDK at OpenRouter and sets the model to `z-ai/glm-5.3-flash`. Every
model-usage record the runs saved names only that model.

## What changed

The shipped build's code changes are in two source files of Ada (`ada/agent/claude/agent.ts`
and `ada/agent/system-guidance.ts`), plus their tests. Four changes
are on by default:

| Change | What it does |
|---|---|
| **Watchdog** | A timer inside Ada that stops it 30 seconds before the time limit: at 450 s of 480 s, counting from when the container started. |
| **Clean exit** | After the watchdog stops Ada, Ada shuts down normally and reports, so the check runs. Without this fix, Ada crashed at that point. |
| **Time-aware prompt** | Replaces the origin build's short, neutral instructions with ones that adapt to the time limit Ada is given. |
| **Thinking limit** | Sets a limit on the model's thinking, `MAX_THINKING_TOKENS`, of 1,024 tokens by default. |

What happens to an attempt that is still running when time is nearly up:

| Ada is still working at | Origin build | Shipped build |
|---|---|---|
| 450 s | keeps working | the watchdog stops Ada, and Ada exits normally |
| 480 s | the harness stops Ada | already stopped |
| **Is the task checked?** | **No: it counts as a fail** | **Yes: it can still pass** |

An attempt that finishes before 450 s is checked the same way in both builds.

Three more changes are in the code but switched off by default:

- time reminders during the task, with a wrap-up instruction and a cap on command timeouts;
- a "definition of done" prompt section;
- a retry when the model stalls.

No run tested the four default-on changes one at a time, so the results below cannot say how
much each one contributed.

## Terms used below

| Term | Meaning |
|---|---|
| **Origin build** | The build the campaign started from (`df0c537`). |
| **Shipped build** | The build at the end of the campaign (`5f4c5c0`). |
| **Baseline / Best** | The names used in the second-model section for the origin / shipped builds. The baseline adds a 7-line pass-through shim (agent tree `7c88c8270e3b`); the best build is `5f4c5c0`. |
| **Attempt** | One build working on one task once. |
| **Passed** | The task's check succeeded. |
| **Timed out** | Ada was still working at 480 s, so the harness stopped it and the check never ran. |
| **Stopped by the watchdog** | The shipped build's watchdog stopped Ada at 450 s. The check then ran. |
| **Harness error** | The harness itself failed during the attempt, so there is no result. These attempts are left out. |
| **Replicate** | One round in which both builds attempt all 81 tasks. |
| **Pair** | The two builds' attempts at the same task in the same replicate. A pair is left out if either attempt had a harness error. |
| **Gained / lost** | A pair that only the shipped (best) build passed / only the origin (baseline) build passed. |
| **p** | The chance of a split between gained and lost at least this uneven if the two builds were equally good (exact McNemar test). The smaller it is, the less likely the difference is luck. |

---

## Main result (R9 and R10, 2026-09-15)

Both builds attempted all 81 tasks in two replicates, R9 and R10 (IDs from
[`bench/RUN_REGISTRY.md`](bench/RUN_REGISTRY.md)). Within each replicate the two
builds ran at the same time on the same machine, so only the build differed.

| Replicate | Pairs | Origin passed | Shipped passed | Gained | Lost | p |
|---|---:|---:|---:|---:|---:|---|
| R9 | 79 | 31 | **47** | 17 | 1 | 1.45e-04 |
| R10 | 78 | 36 | **51** | 15 | 0 | 6.10e-05 |
| **Both** | **157** | **67** | **98** | **32** | **1** | **7.92e-09** |

There are fewer than 81 pairs per replicate because pairs with a harness error are left out.

The run had a pre-registered pass rule, written at the top of the script that launched it
([`bench/run_baseline_vs_best.sh`](bench/run_baseline_vs_best.sh)). The run's log shows the
script checking it at the end, and all four conditions were met:

| Condition | Result |
|---|---|
| Both replicates finish | Yes |
| In each replicate, at least 10 more pairs gained than lost | Yes: 16 and 15 |
| In each replicate, at most 3 harness errors per build | Yes: at most 2 |
| Over both replicates, p below 0.001 | Yes: 7.92e-09 |

Every attempt, including the ones left out of the pairs:

| Every attempt, both replicates | Origin `df0c537` | Shipped `5f4c5c0` |
|---|---:|---:|
| Passed, out of 162 | 68 (42.0%) | **99 (61.1%)** |
| Timed out, so never checked | 84 | **0** |
| Stopped by the watchdog, then checked | 0 | 69 (23 passed) |
| Harness errors, left out | 3 | 2 |

### Where the extra passes come from

| The origin build's attempt | Pairs | Origin passed | Shipped passed |
|---|---:|---:|---:|
| Timed out | 83 | 0 | **29** |
| Finished in time | 74 | 67 | 69 |

Where the origin build timed out (83 pairs), it passed none, and the shipped build passed 29.
In 18 of those 29 the watchdog stopped Ada and the check still passed; in the other 11 Ada
finished in time on its own. Where the origin build finished in time (74 pairs), both builds
passed about the same number: 67 and 69.

---

## Second model (DeepSeek V4.1 Flash, 2026-09-19)

Both builds attempted all 81 tasks once more, with `deepseek/deepseek-v4.1-flash` as the model
through OpenRouter. The two builds ran at the same time on the same machine, so only the build
differed. The baseline is the origin build plus a 7-line pass-through shim: the runner needs
`systemPromptGuidance`, which `df0c537` does not export, so the shim adds it without changing
the prompt. The best build is the shipped build (`5f4c5c0`). This is one attempt per task per
build: a check that the mechanism holds on another model, not a retest of the main result.

| Pairs | Baseline passed | Best passed | Gained | Lost | p |
|---:|---:|---:|---:|---:|---|
| 81 | 34 | **48** | 16 | 2 | 1.31e-03 |

Every attempt:

| Every attempt | Baseline | Best |
|---|---:|---:|
| Passed, out of 81 | 34 (42.0%) | **48 (59.3%)** |
| Timed out, so never checked | 41 | **0** |
| Stopped by the watchdog, then checked | 0 | 31 (6 passed) |
| Harness errors | 0 | 0 |

### Where the extra passes come from

| The baseline's attempt | Pairs | Baseline passed | Best passed |
|---|---:|---:|---:|
| Timed out | 41 | 0 | **15** |
| Finished in time | 40 | 34 | 33 |

Where the baseline timed out (41 pairs), it passed none, and the best build passed 15: 5 after
a watchdog stop and 10 by finishing on its own. Where the baseline finished in time (40 pairs),
both builds passed about the same number: 34 and 33. The same mechanism as the main result:
the extra passes are on tasks the baseline ran out of time on.

### Turns, time and cost

| | Baseline | Best | Best vs baseline |
|---|---:|---:|---:|
| Turns per task (mean / median / p90) | 17.4 / 16 / 28 | 15.9 / 15 / 23 | -8.6% / -6.2% / -17.9% |
| Wall time per attempt, s, including the check (mean / median / p90) | 414 / 489 / 532 | 382 / 391 / 558 | -7.6% / -20.0% / +4.8% |
| Cost total | $1.60 | $1.43 | -11.0% |
| Cost per task (mean / median) | $0.0198 / $0.0148 | $0.0176 / $0.0105 | -11.0% / -29.0% |
| Prompt tokens, including cached / completion tokens | 21.2M / 0.37M | 18.2M / 0.35M | -14.5% / -5.1% |

The evidence is the merged run folder
[`ada/runs/deepseek-v4.1-flash/r1_all/`](ada/runs/deepseek-v4.1-flash/r1_all/):
[`summary.md`](ada/runs/deepseek-v4.1-flash/r1_all/summary.md) and
[`summary.json`](ada/runs/deepseek-v4.1-flash/r1_all/summary.json) rebuilt from the raw
attempt files, [`MERGE.md`](ada/runs/deepseek-v4.1-flash/r1_all/MERGE.md) recording which part
each attempt came from, and every attempt's `trace.jsonl`, `agent.log` and `result.json`. The
per-task table and the gained/lost task lists are in [`ada/RESULTS_DEEPSEEK_V41.md`](ada/RESULTS_DEEPSEEK_V41.md).

Limitations:

- one attempt per task, so a flipped task may have flipped by chance;
- the run was assembled from parts started under different machine load (3.72 and 0.22), though both builds always ran together within each part;
- the baseline carries the shim, so it is not byte-for-byte `df0c537`;
- inside the containers the agents looked at harness files in 76 of 81 baseline and 74 of 81 best attempts, the same for both builds, with no solution in them.

---

## Other findings

### Time reminders do not raise the pass rate

The time reminders were tested on their own, on top of the four changes. On 2026-09-12 three
builds attempted all 81 tasks, one after another (runs R5, R7 and R8):

| Build | Passed | Against the row above |
|---|---:|---|
| Origin (`df0c537`) | 34/81 | |
| Plus the four changes above (`6672af8`) | **54/81** | 21 gained, 1 lost, p = 1.1e-05 |
| Plus time reminders (`2e495bb`) | 50/81 | 5 gained, 9 lost, p = 0.42 |

All 21 tasks gained in the second row were tasks the origin build had timed out on. With time
reminders, the watchdog had to stop Ada 7 times instead of 34, but passes fell from 54 to 50,
which is within chance. The reminders ship switched off: the shipped build is the last row with
them turned off.

### Outside SetupBench

On Terminal-Bench 2.0, a different benchmark, an earlier build (`08a8d5d`) tied the origin
build: 26 against 26 of 38 tasks. Two more tasks were left out because the benchmark's own
checker broke; the origin build had passed both. The two builds also ran on different days. The
shipped build was not run there.

### Tasks that still fail

25 tasks failed in both replicates for the shipped build. With twice the time (960 s), it passed
7 of them. One more change aimed at them, a late wrap-up instruction (P3), gained 2 pairs net.
It was rejected by its own rule (p = 0.6875). Nothing after the main result was shipped.

---

## How the campaign went

| When | What | Outcome |
|---|---|---|
| 2026-09-08 to 09-10 | Phase A: the watchdog, the time-aware prompt, the thinking limit | Timeouts fell from 53 of 81 to 3. The pass-rate headline was later withdrawn (see [`blog.md`](blog.md)). |
| 2026-09-10 to 09-12 | The clean-exit fix, and Phase B: a "definition of done" section and time reminders | The fix was kept. Both Phase B changes are switched off. |
| 2026-09-12 | Three builds, one after another, on one day | Time reminders do not help |
| 2026-09-15 | Main result (R9, R10) | 98/157 against 67/157 |
| 2026-09-16 to 09-17 | Phase C: the tasks that still fail | Nothing shipped |

## Setup

| Item | Value |
|---|---|
| Upstream Ada | `rabbah/ada` at `ebaeb9a` |
| Origin build | `df0c537`: upstream Ada plus the campaign's test scaffolding and a short, neutral prompt addition that says nothing about time. R9/R10 ran it as `417a8f1` (see [`bench/README.md`](bench/README.md)). |
| Shipped build | `5f4c5c0` |
| Model | `z-ai/glm-5.3-flash` through OpenRouter |
| Second model | `deepseek/deepseek-v4.1-flash` through OpenRouter (2026-09-19 run) |
| Benchmark | SetupBench at `041a412`, 81 tasks |
| Time limits | 480 s for Ada, 600 s for the check |

## Check it yourself

```bash
python3 bench/verify_docs.py          # every figure in this README and the blog, against the raw results
python3 bench/confirmation_table.py   # the "every attempt" table above, from the raw results
bash bench/verify_builds.sh           # recovers every build named here from git (needs git and network)
python3 bench/deepseek_summary.py ada/runs/deepseek-v4.1-flash/r1_all  # rebuilds the second-model summary from the raw attempt files (byte-identical)
grep -rE 'sk-or-' ada/runs/deepseek-v4.1-flash/r1_all  # prints nothing: no API key in the evidence
```

The Python checks need nothing but Python 3. [`bench/README.md`](bench/README.md) lists the
other checks.

## Where to look next

| For | See |
|---|---|
| The campaign as a story | [`blog.md`](blog.md) |
| What each file in `bench/` holds, how every build is recovered, and the corrections to the campaign's own records | [`bench/README.md`](bench/README.md) |
| Every scored run, by ID | [`bench/RUN_REGISTRY.md`](bench/RUN_REGISTRY.md) |
| The campaign's own record | [`ada/RESULTS.md`](ada/RESULTS.md), [`ada/REPORT.md`](ada/REPORT.md) |
| Running Ada | [`ada/README.md`](ada/README.md) |

The campaign's own records keep their original text. Where the raw data disagrees with them, a
dated note at the top of each record says so, and [`bench/README.md`](bench/README.md) lists
every correction.

---

## Built with NEO

This branch is the output of an autonomous engineering run. NEO did the failure analysis, the
changes, the paired evaluations, the run registry, the main result and the Phase C probes.
That includes the negative results and the two withdrawals reported above.

[**NEO — Your Autonomous AI Engineering Agent**](https://heyneo.com) ·
[VS Code](https://marketplace.visualstudio.com/items?itemName=NeoResearchInc.heyneo) ·
[Cursor](https://marketplace.cursorapi.com/items/?itemName=NeoResearchInc.heyneo) ·
[Neo MCP docs](https://docs.heyneo.com/neo-mcp)
