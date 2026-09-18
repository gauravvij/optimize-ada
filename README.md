# Ada on SetupBench — an optimisation campaign

[Ada](https://github.com/rabbah/ada) is an open-source coding agent built on Claude Code
through the Claude Agent SDK, written by Simon Guerrier, Rodric Rabbah and contributors and
released under the MIT licence. This branch records one campaign to make Ada pass more
SetupBench tasks: what was changed, how it was measured, and which results held up when they
were measured again.

**Result.** The shipped build passed **98** of 157 paired attempts, against **67** for the
build the campaign started from (exact McNemar p = 7.92e-09). Every attempt of the starting
build that ran out of time was lost without being graded; the shipped build ran out of time
**0** times, against 84. Of the net gain of 31, 29 came from tasks on which the starting build
had run out of time. On the tasks the starting build did finish, the difference is not
significant (67 against 69 of 74).

> **Every change, evaluation run and verification in this campaign was carried out
> autonomously by [NEO](https://heyneo.com) — Your Autonomous AI Engineering Agent.**
> NEO traced the failures, wrote the changes, ran the paired evaluations, withdrew two of
> its own headlines, and confirmed the one result that held with a two-replicate run.

[![NEO](https://img.shields.io/badge/Built%20autonomously%20by-NEO-0B0B0B?style=for-the-badge)](https://heyneo.com)
[![VS Code Extension](https://img.shields.io/badge/VS%20Code-Get%20the%20Extension-007ACC?style=for-the-badge&logo=visualstudiocode&logoColor=white)](https://marketplace.visualstudio.com/items?itemName=NeoResearchInc.heyneo)
[![Cursor Extension](https://img.shields.io/badge/Cursor-Get%20the%20Extension-1F1F1F?style=for-the-badge&logo=cursor&logoColor=white)](https://marketplace.cursorapi.com/items/?itemName=NeoResearchInc.heyneo)
[![Neo MCP Docs](https://img.shields.io/badge/Neo%20MCP-Documentation-6E56CF?style=for-the-badge&logo=readthedocs&logoColor=white)](https://docs.heyneo.com/neo-mcp)

This is not an official Ada branch. It is separate from the Terminal-Bench campaign on this
repository's `main` branch and from the 1200-second validation on `setupbench-frozen-candidate`,
which starts from a different Ada commit (`0c5e1da`).

---

## The question

Why was Ada failing SetupBench tasks, and can changing Ada itself (not the model behind it)
make it pass more of them?

## How the evaluation works

[SetupBench](https://github.com/microsoft/SetupBench) gives an agent a real software
repository and a setup task, such as installing dependencies or getting a test suite to run.
Each task comes with a success command written by the benchmark's authors. The task passes if
that command succeeds after the agent stops.

In this campaign, every attempt went the same way:

1. The harness in [`bench/harness/`](bench/harness/) starts the task's own Docker container,
   copies Ada in, and gives it the task.
2. Ada works inside the container, using `z-ai/glm-5.3-flash` through OpenRouter.
3. Ada has **480 seconds**. If Ada stops in time, the harness runs the task's success command,
   which decides pass or fail.
4. If Ada is still running at 480 seconds, the harness stops the container and **does not run
   the success command**. The attempt fails, whatever Ada had done.

| Pinned component | Value |
|---|---|
| Upstream Ada | `rabbah/ada` at `ebaeb9a` |
| Starting build ("origin") | `df0c537`: upstream Ada plus the campaign's evaluation scaffolding and a short, neutral system-prompt addition that says nothing about time. R9/R10 ran it as `417a8f1` (see "How the builds resolve") |
| Shipped build | `5f4c5c0` |
| Model | `z-ai/glm-5.3-flash` through OpenRouter |
| Benchmark | SetupBench at `041a412`, 81 tasks |
| Time budget per attempt | 480 s for Ada; 600 s for the success command |

### Terms used in the results

| Term | Meaning |
|---|---|
| **Attempt** | One build working on one task once, in a fresh container. |
| **Passed** | The task's success command succeeded after Ada stopped. |
| **Timed out** | Ada was still running at 480 s. The harness stopped it and never ran the success command, so the attempt failed. |
| **Stopped by the watchdog** | The shipped build's watchdog stopped Ada 30 s before the budget ran out. Ada then exited normally, and the success command was run on whatever Ada had done by then. |
| **Harness error** | The harness's own check on the container failed (a `docker exec` call timed out), so the attempt has no result. It is left out of every paired count. |
| **Replicate** | One pass over all 81 tasks by both builds. The confirmation run has two, R9 and R10. |
| **Pair** | The two builds' attempts at the same task in the same replicate. A pair counts only if neither attempt had a harness error. |
| **Gained / lost** | A pair where only the shipped build passed / only the origin build passed. |
| **Exact McNemar p** | Looks only at gained and lost pairs, and gives the probability of a split at least this uneven if the two builds were equally good. A small p means the difference is very unlikely to be chance. |
| **Turn** | One model response inside an attempt. |

## What changed

The origin build ran out of time on 40 to 53 of the 81 tasks, depending on the run. Those
attempts were never graded, so any work Ada had done in them was lost.

Apart from documentation, evidence files and tests, the shipped build differs from the origin
build in two source files, `agent/claude/agent.ts` and `agent/system-guidance.ts`. Four changes
are on by default:

| Change | What it does |
|---|---|
| Time-aware system prompt | Replaces the short, neutral prompt addition with guidance that adapts to the time budget Ada is given. |
| Thinking cap | Sets a default cap of 1,024 thinking tokens (`MAX_THINKING_TOKENS`). |
| Deadline and watchdog | Measures the deadline from the moment the container started, and stops Ada 30 s before the budget runs out: the 450-second mark on a 480-second task. |
| Clean exit (T0.1) | After the watchdog stops it, Ada exits normally and reports its result, so the harness grades its work. |

Three later changes are in the code but **switched off by default**: time hints before every
model request, with a wrap-up instruction and a cap on Bash command timeouts (T1.2,
`ADA_TIME_HINTS`, `ADA_BASH_CLAMP_REMAINING`); a "definition of done" prompt section (T1.1,
`ADA_PROMPT_DOD`); and a retry for stalled model responses (`ADA_STALL_RETRIES`). No run in
this campaign measures the four default-on changes separately from each other.

---

## Main result: the confirmation run (R9 and R10)

On 2026-09-15 the origin build and the shipped build each ran all 81 tasks twice. In each
replicate the two builds ran at the same time on one machine, so nothing but the build
differed between them. R1 to R8 ran four tasks at a time. R9/R10 ran one task at a time per
build, with both builds and both replicates overlapping (replicate 2 started at 12:11 while
replicate 1 ran until 17:42), so up to four containers ran at once, as before.

The pass rule is written at the top of the script that launched the run,
[`bench/run_baseline_vs_best.sh`](bench/run_baseline_vs_best.sh), and the run's log shows the
script checking it at the end. No timestamped copy of the rule predates the run. The rule has
four conditions, and all four are met:

| Condition | Result |
|---|---|
| Both replicates complete, with a result file for each build | Met |
| In each replicate, the shipped build gains at least 10 more pairs than it loses | Met: +16 and +15 |
| In each replicate, each build has at most 3 harness errors | Met: at most 2 |
| Over both replicates, the shipped build is better with exact McNemar p < 0.001 | Met: p = 7.92e-09 |

| Replicate | Pairs counted | Origin passed | Shipped passed | Gained | Lost | Exact McNemar p |
|---|---:|---:|---:|---:|---:|---|
| R9 | 79 | 31 | **47** | 17 | 1 | 1.45e-04 |
| R10 | 78 | 36 | **51** | 15 | 0 | 6.10e-05 |
| **Both** | **157** | **67** | **98** | **32** | **1** | **7.92e-09** |

R9 counts 79 pairs and R10 counts 78 because a pair is left out when either build had a harness
error. Counting every attempt instead, the origin build passed 32 and 36 and the shipped build
47 and 52.

All 162 attempts per build (81 tasks, two replicates), computed from the four raw result files
by `python3 bench/confirmation_table.py`:

| Measure | Origin `df0c537` | Shipped `5f4c5c0` | Difference |
|---|---:|---:|---|
| Attempts passed, out of all 162 | 68 (42.0%) | **99 (61.1%)** | +31 |
| Pairs passed, out of 157 pairs | 67 | **98** | 32 gained, 1 lost; exact McNemar p = 7.92e-09 |
| Timed out, so never graded | 84 | **0** | −84 |
| Stopped by the watchdog, then graded | 0 | 69 | 23 of the 69 passed |
| Harness errors, left out of the pairs | 3 | 2 | |

### Where the gain comes from

Split the 157 pairs by what happened to the origin build's attempt:

| Origin attempt | Pairs | Origin passed | Shipped passed | What it shows |
|---|---:|---:|---:|---|
| Timed out, never graded | 83 | 0 | **29** | 29 of the net gain of 31 |
| Finished in time and graded | 74 | 67 | 69 | 3 gained, 1 lost, p = 0.625: no significant difference |

Of the 29 passes recovered where the origin build had timed out, the shipped build passed **18**
after its watchdog stopped it, and **11** by finishing inside the budget on its own. The second
group did not involve the watchdog, and the data cannot say which of the other changes
produced it.

---

## Other measurements

### The same-day ladder (2026-09-12: R5, R7, R8)

Three builds, all 81 tasks, the same harness, run one after another on one day. Each row adds to
the row above.

| Build | What it adds | Passed | Against the row above |
|---|---|---:|---|
| `df0c537` | the origin build | 34/81 | — |
| `6672af8` | the four default-on changes above | **54/81** | 21 gained / 1 lost, exact McNemar **p = 1.1e-05** |
| `2e495bb` | time hints, wrap-up instruction, Bash timeout cap (T1.2), switched on | 50/81 | 5 gained / 9 lost, **p = 0.42** |

The origin build (R5) timed out on 45 of the 81 tasks; `6672af8` passed 21 of them, and all
21 of its gained pairs are among them. On the other 36 tasks, the ones the origin build
finished in time, the three builds passed 34, 33 and 30.

**The time hints did what they were built to do, but did not raise the pass rate.** Attempts
stopped by the watchdog fell from 34 to 7, but passes went from 54 to 50, inside the noise. So
the time hints ship switched off. The shipped build `5f4c5c0` is `2e495bb` with them off by
default, and it was measured directly in R9/R10 as commit `1d82e56`, which has the same agent
code (tree `dab704de524a`).

### Two results that were withdrawn

| Result as first reported | What was wrong | Measured properly |
|---|---|---|
| Phase A: 27/81 → **59/81** | Assembled from 50 passes carried over from one run plus a re-run of only that run's 31 failures. Withdrawn. | One fresh run of all 81 tasks on one day: **54/81** against the origin build's **34/81** (R7 vs R5) |
| Phase B: time hints 52/81 against 24/81, net +28, p = 7.66e-07 | The 24/81 control run (R3) was run separately, before the time-hints run, not alongside it. The same build scored 54/81 on 2026-09-12, 30 tasks better and none worse. Withdrawn. | Both builds on one day: **54/81 → 50/81**, −4, p = 0.42 |

Both failed the same way: the two builds being compared were not measured together. The same
build moved 30 tasks between one run and the next. After the second withdrawal, only same-day
paired runs counted, and every run got an ID in [`bench/RUN_REGISTRY.md`](bench/RUN_REGISTRY.md)
so that no document can say "the control" without naming the run. The confirmation run went
further: both of its arms ran at the same time.

### Outside SetupBench

On Terminal-Bench 2.0, an earlier build from the campaign (`08a8d5d`, the end of Phase A)
tied the origin build: 26 against 26 of 38 tasks, p = 1.0. Two of the 40 tasks were left out
because the benchmark's own checker failed to install its tools; the origin build had passed
both, so counting all 40 gives 28/40 against 26/40. The two builds ran on different days
(2026-09-07 and 2026-09-10), which the campaign's own rule would no longer allow. The earlier
build used 40% fewer turns and 34% less execution time on the 38 evaluable tasks. The shipped
build has not been run outside SetupBench. Analysis: `bench/FINAL40_PAIRED_ANALYSIS.json`.

### The tasks that still fail (Phase C, 2026-09-16 → 09-17)

25 tasks failed in both confirmation replicates for the shipped build. Given twice the time
(960 s), the shipped build passed 7 of them. A late wrap-up instruction (P3) gained 2 pairs net
across two replicates, p = 0.6875, and was rejected by the rule written for it in
[`bench/P3_P2_PREREGISTRATION.md`](bench/P3_P2_PREREGISTRATION.md). Two further candidates, a
Bash timeout cap (P2) and an install hook (P4), were dropped without being run, on the reading
that the clock no longer cut attempts off. That reading does not hold: the watchdog stopped 28
of the shipped build's 41 failed attempts in the P3 run. P2 was only ever measured inside the
time-hints bundle (R7 → R8, −4) and never on its own; P4, the install hook, never ran. A fifth
(P5) was deferred. Nothing was promoted, and the shipped build is unchanged. Ledger:
[`bench/PHASE_C_SUMMARY.md`](bench/PHASE_C_SUMMARY.md).

---

## How the campaign went

1. **Find the failure.** In the first full run of the origin build (R1), Ada passed 27 of 81
   tasks and timed out on **53 of 81**, none of which were graded.
2. **Phase A (2026-09-08 → 09-10): stop running out of time.** NEO added the time-aware
   prompt, the thinking cap, the deadline anchored to the container's start and the watchdog
   (final build `08a8d5d`). An early watchdog build cut timeouts from 53 (R1) to 3 (R2, whose
   exact build was not recorded). After a watchdog stop, though, Ada crashed instead of
   exiting, so it never reported a result: 43 attempts were recorded with zero turns — 41 of
   them were still graded and 19 passed — and 2 hung until the harness killed them. The clean
   exit (T0.1, `6672af8`) fixed this; neither of its full runs (R3, R7) recorded a zero-turn
   attempt. Phase A's pass-rate headline was withdrawn (above).
3. **Phase B (2026-09-10 → 09-12): tell Ada the time.** A "definition of done" prompt section
   (T1.1) came first and failed: it converted none of the ten failures it targeted, and ships
   switched off. The time hints (T1.2) were promoted on a comparison against a control run
   separately, and then withdrawn (above).
4. **Measure on one day.** The same-day ladder (above) is the only measurement in which the
   time hints are the only difference.
5. **Confirm the build that ships.** The two-replicate confirmation run on 2026-09-15 (above).
6. **Look at what is left.** Phase C (above).

## What this shows, and what it does not

- The shipped build passes more SetupBench tasks than the origin build under this harness:
  98/157 pairs against 67/157.
- 29 of the net gain of 31 is on tasks where the origin build ran out of time. On tasks it
  finished, the difference is not significant (67 against 69 of 74, p = 0.625).
- It does **not** show which of the four default-on changes produced the gain. 18 of the 29
  recovered passes came after a watchdog stop; the other 11 did not involve the watchdog.
- It does **not** measure cost: the result files record no token counts or spend.
- It covers one benchmark, one model and one 480-second budget. The shipped build was not run
  on the full SetupBench set, on other models, or outside SetupBench.

---

## Repository layout

```
ada/       the agent — a snapshot of rabbah/ada with the campaign's changes, and its record
bench/     the evaluation — harness, raw run results, paired analyses, reports, run registry
blog.md    the campaign as a story, for readers new to it
```

| Question | Document |
|---|---|
| What is Ada and how do I run it? | [`ada/README.md`](ada/README.md) |
| What does each file in `bench/` hold? | [`bench/README.md`](bench/README.md) |
| **Which run is which?** | [`bench/RUN_REGISTRY.md`](bench/RUN_REGISTRY.md) — every scored run, by ID |
| The campaign's own record and narrative | [`ada/RESULTS.md`](ada/RESULTS.md), [`ada/REPORT.md`](ada/REPORT.md) (read their re-check notes first) |
| Why was the time-hints result withdrawn? | [`bench/CTRL_VS_T12_REPORT.md`](bench/CTRL_VS_T12_REPORT.md) — the same-day paired run |
| What happened after the confirmation? | [`bench/PHASE_C_SUMMARY.md`](bench/PHASE_C_SUMMARY.md), [`bench/BUDGET_PROBE_REPORT.md`](bench/BUDGET_PROBE_REPORT.md), [`bench/P3_PAIRED_REPORT.md`](bench/P3_PAIRED_REPORT.md) |

| Evidence | Path |
|---|---|
| Raw per-task results of every run | `bench/diagnostics/` (origin-build runs in `ada-baseline/`), `bench/p3_evidence/` |
| The confirmation run's paired analysis | `bench/BASELINE_VS_BEST_20260915T0825Z.json` |
| The same-day ladder's paired analysis | `bench/CTRL_VS_T12_PAIRED_ANALYSIS.json` |
| Terminal-Bench trials | `bench/results-*/` |
| The blog's two charts | `bench/figures/` — each SVG states its values in its `<desc>`, and `bench/verify_docs.py` checks them against the raw rows |
| The harness | `bench/harness/setupbench_ada_runner.ts` (byte-identical to the runner every run recorded), `bench/harness/setupbench_ada_domain_eval.py` (not a version any run recorded: the exact evaluator versions that scored the runs, identified by `evaluator_sha256` in each run's protocol, were not kept) |

### How the builds resolve

`ada/` is a snapshot of tag `ada-best-61pct-20260916` (commit `32f4754`, the shipped build
`5f4c5c0` plus documentation). No agent code differs from that tag. Nine files do:

- `ada/RESULTS.md`, and five scripts in `ada/evidence/`, edited during final packaging on
  2026-09-18 to point at the archived evidence. `ada/RESULTS.md` also carries a dated re-check
  note at the top. The two verify scripts among them also find the repository root themselves
  and check `blog.md` alongside this README.
- `ada/evidence/t12/CTRL_VS_T12_PAIRED_ANALYSIS.json`, regenerated from the archived
  diagnostics during packaging. Only its timestamp and file paths changed; every number is
  identical.
- `ada/REPORT.md`, which carries a dated re-check note at the top; the text below it is unchanged.
- `ada/scripts/probe-thinking.ts`, a thinking-budget probe, which was never committed.

The campaign's own history — its commits, the three build branches and both tags the records
cite — is in `bench/ada-campaign.bundle`, on top of upstream `rabbah/ada` at `ebaeb9a`:

```bash
git clone https://github.com/rabbah/ada ada-history && cd ada-history
git fetch ../bench/ada-campaign.bundle 'refs/heads/*:refs/remotes/campaign/*' 'refs/tags/*:refs/tags/*'
git rev-parse --short=12 5f4c5c0:agent     # dab704de524a, the shipped agent tree
```

The records name the shipped build by four commits that share the agent tree `dab704de524a`:
`5f4c5c0` (the build), `1d82e56` (as measured in R9/R10, with later documentation), `32f4754`
(the tag) and `c6f917e` (the same agent tree, committed in a mirror workspace that packaging
removed; it is in the bundle on branch `p3-late-wrapup`). `bash bench/verify_builds.sh` runs
the recipe above and checks every build the records name.

One build cannot be rebuilt from history. The origin arm of R9/R10 ran as `417a8f1`, which the
records describe as `df0c537` with its runner shim committed. R1 and R5 ran `df0c537` with one
uncommitted file, `agent/system-guidance.ts`; R9/R10 record `417a8f1` with none. Its agent tree,
`df8a18c09278`, is pinned in the diagnostics and asserted by
`bench/baseline_vs_best_verify.py`, but the commit itself is not in the bundle, so the shim
cannot be compared byte for byte.

---

## Checking the numbers yourself

```bash
python3 bench/verify_docs.py                        # every result in blog.md and this README
python3 bench/baseline_vs_best_verify.py            # the confirmation run (R9/R10)
python3 bench/ctrl_vs_t12_verify.py                 # the same-day ladder and the run registry
python3 bench/fresh_rem81_verify.py                 # the 2026-09-12 morning run (R5/R6)
python3 bench/harness/archive_integrity_check.py    # every archived run against the registry
python3 bench/confirmation_table.py                 # the results table above, from the raw rows
```

`verify_docs.py` checks every result the blog and this README state against the raw rows or
the file it cites, and fails if a document or the data changes without the other. The other
three verify scripts recompute their figures from the raw results, including exact McNemar;
`ctrl_vs_t12_verify.py` also fails if a withdrawn number appears in this README, the blog or
the record without being marked as withdrawn. The integrity check confirms every archived
run's row count, pass count and recorded build. They need only Python 3.
`bash bench/verify_builds.sh` recovers the campaign's git history and checks every build's
agent code; it needs git and network access.

Packaging on 2026-09-18 removed regenerable bulk: the SetupBench task-input cache, the variant
tarballs, and the local SetupBench checkout. Re-running an evaluation needs
[microsoft/SetupBench](https://github.com/microsoft/SetupBench) at `041a412` in
`bench/harness/setupbench/`, Docker, and an OpenRouter key. The driver scripts in `bench/`
(`run_*.sh` and friends) are the record of how each run was launched, and keep the absolute
paths of the machine they ran on.

## Re-checked against the raw data, 2026-09-18

Before this branch was published, every claim in this README and the blog was checked against
the raw per-task results. The confirmation run, the same-day ladder and the Terminal-Bench tie
all reproduce exactly. Nine statements in the campaign's own records do not, and are corrected
above. The records themselves — `ada/RESULTS.md`, `ada/REPORT.md`, `bench/RUN_REGISTRY.md`,
`bench/PHASE_C_SUMMARY.md` and `bench/CTRL_VS_T12_REPORT.md` — keep their original text, with a
dated re-check note at the top of each that points here.

| The record says | The raw data shows |
|---|---|
| The watchdog (T0.1) is "the entire mechanism" of the gain (`ada/RESULTS.md`) | The step from `df0c537` to `6672af8` carries all four default-on changes, and no run separates them. Of the 29 passes recovered where the origin build timed out, 18 came after a watchdog stop and 11 did not involve the watchdog. |
| R3, the withdrawn control, ran on 2026-09-10 (its run ID is `20260910T0728Z`), so the +28 compared runs from different days | R3 records commit `6672af8`, whose commit time in `bench/ada-campaign.bundle` is 07:24 UTC on **2026-09-11**, the day after the date in its run ID. Which day R3 ran is therefore uncertain. The comparison stays withdrawn either way: its arms were not run together, and the same build scored 54/81 on 2026-09-12. |
| R3 and R7 did "identical work" | Almost the same number of turns (1,544 against 1,554), but the watchdog stopped 63 of R3's attempts against 34, and R3 took 23% longer in total. |
| Phase C found "zero 480 s clock-outs", so the Bash cap (P2) and install hook (P4) had nothing to fix | The harness stopped no attempt, but the watchdog stopped 28 of the shipped build's 41 failed attempts in the P3 run, and 8 of 17 failed attempts at 960 s. P2 was only ever measured inside the time-hints bundle, and P4 never ran; neither has been tested alone. |
| Phase C's "17 hard clock-outs" (`bench/PHASE_C_SUMMARY.md`) | These are the 960-second run's 17 failed attempts without a harness error: the watchdog stopped 8 of them, and 9 finished and failed their success command. |
| R2's 43 zero-turn attempts came from the watchdog stop | They were a reporting bug: 41 were graded and 19 passed. Only 2 were true force-kills (commit `6672af8`'s message). |
| R10a had 40 zero-turn attempts (`bench/RUN_REGISTRY.md`) | 41, in both the raw results and `bench/BASELINE_VS_BEST_20260915T0825Z.json`. |
| Terminal-Bench compared the two builds under one protocol | The origin build ran on 2026-09-07 and `08a8d5d` on 2026-09-10. |
| Packaging (2026-09-18) only moved and repointed files | It also rewrote one path field, `incumbent_source`, in the raw file `bench/diagnostics/manual/remaining81_final_failures31.json`. That file is restored to its original bytes; every other packaging change is listed in `bench/packaging-20260918/changes.diff`. |

`bench/RUN_REGISTRY.md` also cites a footnote ⁴ for `417a8f1` that it never defines; the
paragraph "How the builds resolve" above says what is known about that build.

## Running Ada

See [`ada/README.md`](ada/README.md): a demo that needs no API key, a local run against the
real Claude Agent SDK, and deployment on the Astro platform.

---

## Built with NEO

This branch is the output of an autonomous engineering run. NEO did the failure analysis, the
changes, the paired evaluations, the run registry, the confirmation run and the Phase C probes
— including the negative results and the two withdrawals, which are reported here in full.

A narrative walkthrough of the campaign is in [`blog.md`](blog.md).

[**NEO — Your Autonomous AI Engineering Agent**](https://heyneo.com) ·
[VS Code](https://marketplace.visualstudio.com/items?itemName=NeoResearchInc.heyneo) ·
[Cursor](https://marketplace.cursorapi.com/items/?itemName=NeoResearchInc.heyneo) ·
[Neo MCP docs](https://docs.heyneo.com/neo-mcp)
