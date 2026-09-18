# How NEO Stopped a Coding Agent From Dying on the Clock

*NEO, our autonomous engineering agent, took a coding agent from 67 to 98 passed runs out of 157 on real software-setup tasks — not by making it smarter, but by making sure its work reached the grader. Along the way it promoted a second fix, caught its own control being a bad day, and withdrew the claim. The withdrawal is as useful as the win.*

The system we optimized is [Ada](https://github.com/rabbah/ada), an open-source coding agent built on Claude Code by Simon Guerrier and Rodric Rabbah. You give it a task in plain English — *install the dependencies and make the tests pass* — and it works through it in a sandbox, running commands, editing files, and checking its own results.

A typical failing run looked like this. Given a task with an eight-minute budget, Ada would work competently for seven minutes: install packages, fix a config, start a service. Then, with a minute left, it would start a `sleep 300` poll or a fresh debugging tangent. The budget ran out mid-flight, the harness killed the container, and the task was scored as a failure.

The grader never ran. Everything Ada had done was thrown away.

Nothing looked broken. There was no crash in Ada and no error in the model. The agent simply did not know the deadline was coming: the only mention of the budget was one line in its system prompt, written once at the start and never updated.

That is a dangerous failure for any agent that works against a time limit. A crash gets noticed. A run that does most of the work and then vanishes looks exactly like a run that did nothing.

This is what survived the campaign:

- A watchdog that stops Ada cleanly before the deadline took it from **67/157 to 98/157** passed runs, confirmed by a two-replicate run whose rules were fixed before it was paid for.
- The whole gain is runs that used to be killed before grading. On the runs where the original build did get graded, nothing changed.
- A second fix — telling Ada how much time it has left — did everything it was designed to do and did not raise the pass rate. It ships switched off.
- Two headline numbers were published during the campaign and then withdrawn by NEO itself, both for the same reason.
- On a second benchmark, Terminal-Bench 2.0, an earlier build tied the original.

Four builds of Ada are compared throughout, and these are the names used for them:

- **Origin** — Ada as the campaign found it, commit `df0c537`.
- **Watchdog** — the origin plus the watchdog and a clean exit, commit `6672af8`.
- **Time hints** — the watchdog build plus the time-awareness change, commit `2e495bb`.
- **Shipped** — the time-hints build with the time hints switched off, commit `5f4c5c0`. It behaves exactly like the watchdog build, and it was measured under its own name.

## What Ada does

Ada is a wrapper around a Claude Code session. A small service starts the session through the Claude Agent SDK, gives it its own writable workspace, and streams everything it does — its messages, each tool call, each result — to whatever is listening: a Slack thread, a web chat, or any frontend that speaks the AG-UI event protocol. Follow-up messages continue the same session in the same workspace.

The spawned agent runs with a scrubbed environment. Only the essentials are forwarded — the path, the model credential, the user's GitHub token — so a command the model runs cannot read the host's secrets. The code is in [`ada/`](ada/), and [`ada/README.md`](ada/README.md) covers running it: a demo that needs no API key, a local run against the real SDK, and deployment on the Astro platform.

In this campaign Ada ran `z-ai/glm-5.3-flash` through OpenRouter, not a Claude model, and was driven headlessly by a benchmark harness:

```
harness     for each task: start the task's own Docker container
            copy Ada in, give it the task, start the clock (480 s)
                │
Ada         Claude Agent SDK loop ──► z-ai/glm-5.3-flash via OpenRouter
            tools run inside the container: shell, file edits, installs, services
                │
harness     Ada exits before the deadline ──► run the task's success command ──► pass / fail
            deadline passes first          ──► timed out: the grader never runs  ──► fail
```

The last line is the whole story. A run that overran was not partly right. It was never looked at.

The changes that were measured all live in two files of [`ada/agent/`](ada/agent/):

| Change | Where it lives in `ada/` | Status |
|---|---|---|
| Watchdog and a deadline anchored to the container's start | `agent/claude/agent.ts`, `agent/system-guidance.ts` | ships |
| Clean exit after the watchdog interrupt (T0.1) | `agent/claude/agent.ts` | ships |
| "Definition of done" prompt section (T1.1) | `agent/system-guidance.ts` | ships switched off |
| Time hints, wrap-up instruction, Bash timeout clamp (T1.2) | `agent/claude/agent.ts` | ships switched off |

## How it was measured

The benchmark is [SetupBench](https://github.com/microsoft/SetupBench): real repositories, each with a task such as installing dependencies, configuring a database, or getting a test suite running, and a success command written by the benchmark's authors that decides pass or fail. The campaign used 81 of its tasks, each with a 480-second budget.

The harness is in [`bench/harness/`](bench/harness/). It records, for every task, whether the grader passed it, how many turns Ada took, how long it ran, and whether it timed out. Two builds are compared on the same tasks, task by task, with an exact McNemar test on the tasks where they disagree.

One rule was learned the hard way and is described below: **both builds must run on the same day, side by side.** Every run ever scored is listed with its ID in [`bench/RUN_REGISTRY.md`](bench/RUN_REGISTRY.md), and every document in the campaign names its runs by those IDs.

## The first full run: killed by the clock

The first full run of the origin build (R1) passed 27 of 81 tasks and timed out on 53. Every timeout was a zero: the harness never graded the work.

NEO's first fix, in Phase A, went after the clock directly. A watchdog interrupts the agent before the harness would kill it, and the deadline is measured from the container's start rather than the agent's, so Ada's clock and the harness's clock agree. Timeouts fell from 53 to 3.

The interrupt still ended badly: after it fired, the agent process was force-killed instead of exiting, and 43 runs were recorded with zero turns. The clean-exit fix (T0.1) made Ada finish properly after the interrupt. In the next full run of that build (R7), not one run was recorded with zero turns.

## The watchdog, measured on one day

On 2026-09-12 NEO ran three builds on all 81 tasks, one after another, with the same driver:

| Build | What it adds | Passed | Against the row above |
|---|---|---:|---|
| Origin `df0c537` | — | 34/81 | — |
| Watchdog `6672af8` | watchdog, container-anchored deadline, clean exit | **54/81** | **+20**, 21 gained / 1 lost, p = 1.1e-05 |
| Time hints `2e495bb` | time hints, wrap-up instruction, Bash clamp | 50/81 | **−4**, 5 gained / 9 lost, p = 0.42 |

The watchdog's gain is entirely one thing. On that day the origin build produced zero turns on 46 of the 81 tasks. The watchdog build passed 21 of those 46. On the 35 tasks the origin build could actually run, it had already passed 34, and nothing built since has improved on that.

## Two ideas that did not work

Before the time hints, NEO tried two changes that asked the model to behave differently.

The first was a careful "definition of done" section in the prompt: reproduce paths, ports and values exactly, use the project's own toolchain, and run the success check in a fresh shell before claiming victory. The model provably received it. It converted none of the ten failing tasks it was written for, and on a 12-task paired check it scored 2 against the control's 3. It ships switched off.

The second was to make the model think less, because thinking tokens were eating up to 93% of its output on some runs. The gateway rejects turning thinking off, a low-effort setting had no effect, and the thinking budget that did work at the raw API level is never forwarded by the SDK path Ada uses. NEO dropped it before spending anything on an evaluation.

## The time hints: a working mechanism that did not help

The third idea did not ask the model to change. It gave the model a fact it provably lacked. Before every model request, a hook inserts a line such as `⏱ 74 s of 480 s remain.` Near the end, the line becomes an instruction to stop exploring and make the success command pass. And any Bash command's timeout is capped so a single `sleep` cannot eat the rest of the budget.

The mechanism works. Asked to quote any timing note it had seen, the model repeated the hint word for word. Runs cut off at the deadline fell from 34 to 7, turns fell 10.6%, and wall time fell 5.0%. The agent really does pace itself once it can see the clock.

It does not pass more tasks. On the same day as the watchdog build, the time-hints build scored 50/81 against 54/81. That −4 is inside the noise, so it is no measured benefit rather than measured harm. Where it lost is telling: on the 47 tasks where the watchdog build finished with time to spare, the time-hints build went from 42 passes to 37. The wrap-up instruction reached tasks that were never in trouble and told them to stop.

It also changed how Ada fails. Of the time-hints build's failures, 25 of 31 ended with Ada announcing the task was done while the grader's command failed, against 5 of 27 for the watchdog build. The hints make Ada declare more tasks finished, not finish more.

So the time hints are an efficiency result, not an accuracy result, and they are reported as one.

## Two numbers NEO took back

The time hints had not always looked like this. They were first reported — in a result since withdrawn — at **52/81 against 24/81, +28, p = 7.66e-07**, and promoted.

The withdrawn result's 24/81 was a control run of the watchdog build from 2026-09-10, the day before the time-hints run it was compared with. On 2026-09-12 the same build, on the same tasks, scored 54/81 — 30 tasks better and none worse, p = 1.9e-09 — while doing measurably identical work: 1,544 turns against 1,554, no timeouts either day. The 24/81 control was a depressed run. The model behind it was having a worse day. A control that moves 30 tasks on its own cannot anchor a claim of 28.

The first headline to go was Phase A's: 27/81 to 59/81. That 59 was assembled from 50 passes carried over from earlier runs plus a re-run of only the 31 failures. Run fresh and whole on one day, the same line of builds scores 54/81 against the origin's 34/81. NEO withdrew that too.

Both failures are the same failure: a comparison anchored to a run measured under conditions that no longer held. One carried scores across protocols; the other carried a control across days. After the second, NEO made same-day paired runs the only admissible evidence and built the run registry, so that no document can say "the control" without saying which run.

## Confirming what was left

With the time hints switched off, the build that ships behaves like the watchdog build. NEO did not infer its score from that. It measured it.

On 2026-09-15 it ran the origin build and the shipped build side by side, twice, all 81 tasks each time. The rules were written down before the run was paid for: both replicates must complete, each must gain at least 10 tasks net, neither arm may lose more than three rows to harness errors, and the pooled exact McNemar test must reach p < 0.001.

| Confirmation run | Tasks that could be paired | Origin | Shipped | Net | p |
|---|---:|---:|---:|---:|---|
| R9 | 79 | 31 | **47** | +16 | 1.45e-04 |
| R10 | 78 | 36 | **51** | +15 | 6.10e-05 |
| **Pooled** | **157** | **67** | **98** | **+31** | **7.92e-09** |

All four rules are met. 32 runs were gained and 1 was lost.

The decomposition is the clearest result of the campaign. On the 82 paired runs where the origin build hung and was killed with zero turns, the shipped build passed 28. On the 75 where the origin build ran normally, the two builds passed 67 and 70 — p = 0.375, no real difference. Across all 162 runs, runs killed before grading fell from 86 to 3 and timeouts from 84 to 0, and the shipped build used about 6% less wall time than the origin spent dying.

## Beyond SetupBench

On Terminal-Bench 2.0, a different benchmark of terminal tasks, NEO compared the origin build with Phase A's final build (`08a8d5d`) on 40 public tasks. Two tasks were excluded because the verifier's own infrastructure failed — a package mirror returned 404 and a tool was missing — which says nothing about the agent. On the remaining 38 the two builds tied, 26 against 26, p = 1.0. The efficiency carried over, with 39% fewer turns and 35% less execution time. The pass-rate gain did not. The shipped build has not been run outside SetupBench.

## Where the remaining gap is

After the confirmation, NEO asked whether the 25 tasks that fail on every run are slow or hard. It re-ran them at twice the budget, 960 seconds. Seven passed, and none timed out. One more candidate, a later wrap-up aimed at the runs that were still being interrupted, gained 2 across two replicates (p = 0.6875) and failed its pre-registered gate. Two others were dropped without spending anything, because the fresh runs showed no clock-outs left for them to fix.

The remaining failures are mostly setups the grader rejects, not runs that ran out of time. On this model, the gap that is left is capability, not scaffolding.

## What this experiment can and cannot claim

The evidence supports these claims:

- The shipped build passes more SetupBench tasks than the origin build: 98/157 against 67/157 on paired runs, confirmed under rules fixed in advance.
- The gain comes from runs that were killed before grading. It is not a gain in the agent's ability on tasks it could already attempt.
- The time hints make Ada use its time more efficiently without raising its pass rate.

It does not establish that Ada is a more capable agent. It does not establish any gain outside SetupBench: the shipped build was never run elsewhere, and the one external comparison was a tie. The harness records no token counts or spend, so there is no measured cost for the confirmation run. And all 81 tasks come from one benchmark, graded by its authors' success commands.

## What this approach demonstrates

**The control is a measurement too.** The same build scored 24/81 and 54/81 two days apart on identical work. Every withdrawn headline in this campaign rested on a control measured under conditions that no longer held. Statistics on the candidate cannot fix a control from a different day.

**A small p-value is not a shield against a bad design.** The withdrawn comparison had p = 7.66e-07 and a confidence interval far from zero. Both were computed correctly. They answered whether two particular runs differed, and they did — but not because of the code.

**Keep efficiency and accuracy apart.** The time hints cut runs interrupted at the deadline by 79%. That is real and worth having. It is not a pass-rate gain, and one number that blends the two is how a change gets promoted on evidence it does not have.

**A working mechanism is not a working change.** The model received the hint, quoted it, and paced itself. It did exactly what it was asked and did not get better at the task.

**Look at what the grader actually sees.** The biggest gain in the campaign came from noticing that most of the original build's failures were never graded at all: 86 of its 94 failed runs in the confirmation.

## Check it yourself

Every number in this article traces to a file in [`bench/`](bench/), and four scripts re-derive them from the raw per-task diagnostics, with nothing but Python 3:

```bash
python3 bench/baseline_vs_best_verify.py            # the confirmation run (R9/R10)
python3 bench/ctrl_vs_t12_verify.py                 # the same-day ladder and the run registry
python3 bench/fresh_rem81_verify.py                 # the 2026-09-12 morning run
python3 bench/harness/archive_integrity_check.py    # every archived run against the registry
```

The scripts also check this article: they fail if a withdrawn figure appears here without being marked as withdrawn. The full record is [`ada/RESULTS.md`](ada/RESULTS.md), and the campaign's own narrative is [`ada/REPORT.md`](ada/REPORT.md). The [README](README.md) explains how to recover the exact commit behind each build.

## What the optimization delivered

Ada now stops itself cleanly before its deadline, so the work it has done is always graded. On SetupBench that took it from 67 to 98 passed runs out of 157, and from 86 runs killed before grading to 3, at slightly less wall time. It is not a smarter agent. It is an agent whose work now counts.

NEO did the failure analysis, the changes, the paired evaluations, the run registry, the confirmation run and the probes that followed — and withdrew its own numbers twice when they did not hold.

**[NEO: Your Autonomous AI Engineering Agent](https://heyneo.com)**

[![VS Code Extension](https://img.shields.io/badge/VS%20Code-Get%20the%20Extension-007ACC?style=for-the-badge&logo=visualstudiocode&logoColor=white)](https://marketplace.visualstudio.com/items?itemName=NeoResearchInc.heyneo)
[![Cursor Extension](https://img.shields.io/badge/Cursor-Get%20the%20Extension-1F1F1F?style=for-the-badge&logo=cursor&logoColor=white)](https://marketplace.cursorapi.com/items/?itemName=NeoResearchInc.heyneo)
[![Neo MCP Docs](https://img.shields.io/badge/Neo%20MCP-Documentation-6E56CF?style=for-the-badge&logo=readthedocs&logoColor=white)](https://docs.heyneo.com/neo-mcp)
