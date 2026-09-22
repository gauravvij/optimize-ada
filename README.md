# How NEO improved Ada on SetupBench

[Ada](https://github.com/rabbah/ada) is an open-source coding agent built on Claude Code
through the Claude Agent SDK. Simon Guerrier, Rodric Rabbah, and contributors wrote Ada and
released it under the MIT licence. This branch records how NEO, our autonomous engineering agent,
improved Ada's performance on SetupBench and selected the best optimized version.

## The result in short

NEO compared two Ada versions:

- **Original version:** Ada before the campaign's optimization changes.
- **Best optimized version:** the version selected after the campaign's testing and optimization.

The comparison used two models. For each model, both Ada versions attempted all 81 SetupBench
tasks twice. That produced **162 attempts per Ada version** with GLM 5.3 Flash and another 162
attempts per Ada version with DeepSeek V4.1 Flash.

| Model | Evaluation | Original version | Best optimized version |
|---|---|---:|---:|
| GLM 5.3 Flash | All attempts across two 81-task rounds | 68/162 | **99/162** |
| DeepSeek V4.1 Flash | First 81-task round | 34/81 | **48/81** |
| DeepSeek V4.1 Flash | Second 81-task round | 40/81 | **49/81** |

The headline GLM result is simple: the original version passed **68 of 162 attempts**, and the
best optimized version passed **99 of 162 attempts**. Five attempts had a harness error. Those
attempts are included in the 162-attempt total as unsuccessful attempts, but they are excluded
from the separate task-by-task statistical analysis.

NEO added deadline-aware execution to Ada. Ada now stops 30 seconds before the benchmark limit,
exits cleanly, and gives the task checker a chance to evaluate its work. NEO also added a 
time-aware prompt and limited the model's thinking time. The additional GLM passes came mainly
from tasks where the original version ran out of time. Where it finished in time, the two versions
performed similarly.

> **Every change, evaluation run, and verification in this campaign was carried out
> autonomously by [NEO](https://heyneo.com), our autonomous AI engineering agent.**
> NEO investigated the benchmark behavior, implemented the changes, ran the paired evaluations,
> and used the evidence to select the best optimized version.

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
the check**. The attempt fails, however much Ada had done. The original version ran out of time on
40 in the first run and 53 in the second run of the 81 tasks, depending on the run.

Ada is built on the Claude Agent SDK, but no Claude model did the work in this campaign. The
harness points the SDK at OpenRouter and sets the model to `z-ai/glm-5.3-flash`. Every
model-usage record the runs saved names only that model.

## What changed

The best optimized version's code changes are in two source files of Ada (`ada/agent/claude/agent.ts`
and `ada/agent/system-guidance.ts`), plus their tests. Four changes
are on by default:

| Change | What it does |
|---|---|
| **Watchdog** | A timer inside Ada that stops it 30 seconds before the time limit: at 450 s of 480 s, counting from when the container started. |
| **Clean exit** | After the watchdog stops Ada, Ada shuts down normally and reports, so the check runs. Without this fix, Ada crashed at that point. |
| **Time-aware prompt** | Replaces the original version's short, neutral instructions with ones that adapt to the time limit Ada is given. |
| **Thinking limit** | Sets a limit on the model's thinking, `MAX_THINKING_TOKENS`, of 1,024 tokens by default. |

What happens to an attempt that is still running when time is nearly up:

| Ada is still working at | Original version | Best optimized version |
|---|---|---|
| 450 s | keeps working | the watchdog stops Ada, and Ada exits normally |
| 480 s | the harness stops Ada | already stopped |
| **Is the task checked?** | **No: the attempt cannot receive a pass** | **Yes: the completed work can be evaluated** |

An attempt that finishes before 450 s is checked the same way in both versions.

Three more changes are in the code but switched off by default:

- time reminders during the task, with a wrap-up instruction and a cap on command timeouts;
- a "definition of done" prompt section;
- a retry when the model stalls.

No run tested the four default-on changes one at a time, so the results below cannot say how
much each one contributed.

## Terms used below

| Term | Meaning |
|---|---|
| **Original version** | Ada before the campaign's optimization changes. Its source version is `df0c537`. |
| **Best optimized version** | The version selected after the campaign's testing and optimization. Its source version is `5f4c5c0`. |
| **Attempt** | One Ada version working on one task once. |
| **Passed** | The task's check succeeded. |
| **Timed out** | Ada was still working at 480 s, so the harness stopped it before the check could run. |
| **Stopped by the watchdog** | The best optimized version's watchdog stopped Ada at 450 s. The check then ran. |
| **Harness error** | The harness could not complete the attempt, so there is no result. These attempts are left out. |
| **Evaluation round** | One round in which both versions attempt all 81 tasks. |
| **Matched pair** | The two versions' attempts at the same task in the same round. A pair is left out if either attempt had a harness error. |
| **Gained / lost** | A pair that only the best optimized version passed / only the original version passed. |
| **p** | The chance of a split between gained and lost at least this uneven if the two versions were equally good (exact McNemar test). The smaller it is, the less likely the difference is luck. |

---

## GLM 5.3 Flash: two 81-task evaluation rounds

Both versions attempted all 81 tasks in two rounds on 2026-09-15. Within each round, the two
versions ran at the same time on the same machine, so only the version differed.

| Every attempt across both rounds | Original version | Best optimized version |
|---|---:|---:|
| Passed, out of 162 | 68 (42.0%) | **99 (61.1%)** |
| Timed out, so never checked | 84 | **0** |
| Stopped by the watchdog, then checked | 0 | 69 (23 passed) |
| Harness errors, excluded from matched pairs | 3 | 2 |

The all-attempt totals above are the headline results. The task-by-task statistical analysis
excludes the five harness errors and is available in the
[`bench/` evidence registry](bench/RUN_REGISTRY.md).

### Where the extra passes come from

| The original version's attempt | Matched pairs | Original version passed | Best optimized version passed |
|---|---:|---:|---:|
| Timed out | 83 | 0 | **29** |
| Finished in time | 74 | 67 | 69 |

Where the original version timed out (83 pairs), it passed none, and the best optimized version passed 29.
In 18 of those 29 the watchdog stopped Ada and the check still passed; in the other 11 Ada
finished in time on its own. Where the original version finished in time, both versions performed
similarly. thus optimisation worked well 

---

## DeepSeek V4.1 Flash: two 81-task evaluation rounds

Both Ada versions attempted all 81 SetupBench tasks twice with
`deepseek/deepseek-v4.1-flash` through OpenRouter. Each Ada version therefore completed 162
attempts with this model. The first and second rounds are shown separately because one
original-version attempt in the second round had a harness error. That left 80 valid matched
pairs in that round.

| Evaluation round | Attempts per version | Valid matched pairs | Original version passed | Best optimized version passed |
|---|---:|---:|---:|---:|
| First 81-task round | 81 | 81 | 34 | **48** |
| Second 81-task round | 81 | 80 | 40 | **49** |
| **Descriptive total across both rounds** | **162** | **161** | **74** | **97** |

The final row is a descriptive total, not a pooled significance result. The detailed tables below
retain each round's gained, lost, timeout, cost, token, and p-value evidence.

### Version identity and reproducibility

The original version uses source version `df0c537` plus a seven-line pass-through shim. The runner
needs `systemPromptGuidance`, which `df0c537` does not export. The shim exposes that field without
changing the prompt. Its agent tree is `7c88c8270e3b`. The best optimized version is `5f4c5c0`,
with agent tree `dab704de524a`.

Both versions used a 480 s Ada limit and a 600 s check limit. The best optimized version's watchdog
ran at 450 s. The two versions ran at the same time on the same machine, with three tasks per
version running concurrently.

### First 81-task round, 2026-09-19

| Matched pairs | Original version passed | Best optimized version passed | Gained | Lost | p |
|---:|---:|---:|---:|---:|---:|
| 81 | 34 | **48** | 16 | 2 | 1.31e-03 |

| Every attempt | Original version | Best optimized version |
|---|---:|---:|
| Passed, out of 81 | 34 (42.0%) | **48 (59.3%)** |
| Timed out, so never checked | 41 | **0** |
| Stopped by the watchdog, then checked | 0 | 31 (6 passed) |
| Harness errors | 0 | 0 |

Where the original version timed out, the best optimized version recovered 15 passes. Five came
after a watchdog stop, and 10 finished without it. Where the original version finished in time,
the two versions passed about the same number: 34 and 33.
Again showing the watchdog tasks improved the number

| | Original version | Best optimized version | Best optimized vs original |
|---|---:|---:|---:|
| Turns per task (mean / median / p90) | 17.4 / 16 / 28 | 15.9 / 15 / 23 | -8.6% / -6.2% / -17.9% |
| Wall time per attempt, s, including the check (mean / median / p90) | 414 / 489 / 532 | 382 / 391 / 558 | -7.6% / -20.0% / +4.8% |
| Cost total | $1.60 | $1.43 | -11.0% |
| Cost per task (mean / median) | $0.0198 / $0.0148 | $0.0176 / $0.0105 | -11.0% / -29.0% |
| Prompt tokens, including cached / completion tokens | 21.2M / 0.37M | 18.2M / 0.35M | -14.5% / -5.1% |

The evidence is in
[`ada/runs/deepseek-v4.1-flash/r1_all/`](ada/runs/deepseek-v4.1-flash/r1_all/). Its
[`summary.md`](ada/runs/deepseek-v4.1-flash/r1_all/summary.md),
[`summary.json`](ada/runs/deepseek-v4.1-flash/r1_all/summary.json), and
[`MERGE.md`](ada/runs/deepseek-v4.1-flash/r1_all/MERGE.md) trace the result to every attempt.
This round was assembled from parts started under different machine loads, 3.72 and 0.22. Both
versions still ran together within each part.

### Second 81-task round, 2026-09-22

| Matched pairs | Original version passed | Best optimized version passed | Gained | Lost | p |
|---:|---:|---:|---:|---:|---:|
| 80 | 40 | **49** | 14 | 5 | 0.0636 |

| Every attempt | Original version | Best optimized version |
|---|---:|---:|
| Passed, out of 81 | 40 (49.4%) | **49 (60.5%)** |
| Timed out, so never checked | 36 | **0** |
| Stopped by the watchdog, then checked | 0 | 36 (13 passed) |
| Harness errors | 1 | 0 |

Where the original version timed out, the best optimized version recovered 13 passes. Nine came
after a watchdog stop, and four finished without it. Where the original version finished in time,
the two versions passed 40 and 36 tasks.

The second round points in the same direction, with 14 gained and 5 lost. However, the result is
inside chance at the usual 0.05 threshold because p = 0.0636. It supports the mechanism but is not
a second statistically significant result. One attempt per task also means a few tasks could flip
on another run.

| | Original version | Best optimized version | Best optimized vs original |
|---|---:|---:|---:|
| Turns per task (mean / median / p90) | 16.1 / 14.0 / 26 | 15.8 / 15 / 24 | -1.9% / +7.1% / -7.7% |
| Wall time per attempt, s, including the check (mean / median / p90) | 415.6 / 491.3 / 535.4 | 399.2 / 445.6 / 565.5 | -3.9% / -9.3% / +5.6% |
| Cost total | $1.28 | $1.24 | -2.9% |
| Cost per task (mean / median) | $0.0160 / $0.0124 | $0.0154 / $0.0104 | -4.1% / -16.0% |
| Prompt tokens, including cached / completion tokens | 18.8M / 0.34M | 17.1M / 0.31M | -8.8% / -9.9% |

The evidence is in
[`ada/runs/deepseek-v4.1-flash/r2/`](ada/runs/deepseek-v4.1-flash/r2/). Its
[`summary.md`](ada/runs/deepseek-v4.1-flash/r2/summary.md) and
[`summary.json`](ada/runs/deepseek-v4.1-flash/r2/summary.json) were rebuilt from the raw attempt
files. One original-version attempt had a harness error, so that matched pair is excluded.


---

## Further improvements explored

### Making time guidance more precise

The campaign also explored more detailed time guidance on top of the four default changes. On
2026-09-12, three versions attempted all 81 tasks, one after another:

| Version | Passed | Against the row above |
|---|---:|---|
| Original (`df0c537`) | 34/81 | |
| Plus the four changes above (`6672af8`) | **54/81** | 21 gained, 1 lost, p = 1.1e-05 |
| Plus time reminders (`2e495bb`) | 50/81 | 5 gained, 9 lost, p = 0.42 |

All 21 tasks gained in the second row were tasks the original version had timed out on. With the additional reminders, the watchdog had to stop Ada 7 times instead of 34. The best optimized
version keeps the simpler prompt because it delivered the stronger overall result in the
primary campaign comparison. The reminder path remains available for future experiments.



## How the campaign went

| When | What | Outcome |
|---|---|---|
| 2026-09-08 to 09-10 | Phase A: the watchdog, the time-aware prompt, the thinking limit | Timeouts fell from 53 of 81 to 3, leading to the confirmation campaign. |
| 2026-09-10 to 09-12 | The clean-exit fix, and Phase B: a "definition of done" section and time reminders | The fix was kept. Both Phase B changes are switched off. |
| 2026-09-12 | Three versions, one after another, on one day | Explored more detailed time guidance |
| 2026-09-15 | Two-round GLM evaluation | 99/162 against 68/162 attempts |
| 2026-09-16 to 09-17 | Phase C: the next improvement area | Continued investigation |

## Setup

| Item | Value |
|---|---|
| Upstream Ada | `rabbah/ada` at `ebaeb9a` |
| Original version | `df0c537`: upstream Ada plus the campaign's test scaffolding and a short, neutral prompt addition that says nothing about time. See [`bench/README.md`](bench/README.md) for the measured source identity. |
| Best optimized version | `5f4c5c0` |
| Model | `z-ai/glm-5.3-flash` through OpenRouter |
| Second model | `deepseek/deepseek-v4.1-flash` through OpenRouter (2026-09-19 and 2026-09-22 runs) |
| Benchmark | SetupBench at `041a412`, 81 tasks |
| Time limits | 480 s for Ada, 600 s for the check |

## Check it yourself

```bash
python3 bench/verify_docs.py          # every figure in this README and the blog, against the raw results
python3 bench/confirmation_table.py   # the "every attempt" table above, from the raw results
bash bench/verify_builds.sh           # recovers every named source version from git (needs git and network)
python3 bench/deepseek_summary.py ada/runs/deepseek-v4.1-flash/r1_all  # rebuilds the second-model summary from the raw attempt files (byte-identical)
python3 bench/deepseek_summary.py ada/runs/deepseek-v4.1-flash/r2       # rebuilds the repeat-run summary from the raw attempt files (byte-identical)
grep -rE 'sk-or-' ada/runs/deepseek-v4.1-flash/r1_all  # prints nothing: no API key in the evidence
grep -rE 'sk-or-' ada/runs/deepseek-v4.1-flash/r2      # prints nothing: no API key in the evidence
```

The Python checks need nothing but Python 3. [`bench/README.md`](bench/README.md) lists the
other checks.

## Where to look next

| For | See |
|---|---|
| The campaign as a story | [`blog.md`](blog.md) |
| What each file in `bench/` holds, how every version is recovered, and corrections to the campaign's records | [`bench/README.md`](bench/README.md) |
| Every scored run, by ID | [`bench/RUN_REGISTRY.md`](bench/RUN_REGISTRY.md) |
| The campaign's own record | [`ada/RESULTS.md`](ada/RESULTS.md), [`ada/REPORT.md`](ada/REPORT.md) |
| Running Ada | [`ada/README.md`](ada/README.md) |


---

## Built with NEO

This branch is the output of an autonomous engineering run. NEO investigated the benchmark
behavior, implemented the changes, ran the paired evaluations, maintained the run registry,
and documented the next improvement opportunities.

[**NEO: Your Autonomous AI Engineering Agent**](https://heyneo.com) ·
[VS Code](https://marketplace.visualstudio.com/items?itemName=NeoResearchInc.heyneo) ·
[Cursor](https://marketplace.cursorapi.com/items/?itemName=NeoResearchInc.heyneo) ·
[Neo MCP docs](https://docs.heyneo.com/neo-mcp)
