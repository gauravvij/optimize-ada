# Ada on SetupBench — an optimisation campaign

[Ada](https://github.com/rabbah/ada) is an open-source coding agent built on Claude Code
through the Claude Agent SDK, written by Simon Guerrier, Rodric Rabbah and contributors and
released under the MIT licence. This branch records one campaign to make it pass more real
software-setup tasks: what was changed, what was measured, and which claims survived being
measured again.

The agent is ordinary. What is unusual is where its gain came from, and how that was checked.

> **Every change, evaluation run and verification in this campaign was carried out
> autonomously by [NEO](https://heyneo.com) — Your Autonomous AI Engineering Agent.**
> NEO traced the failures, wrote the changes, ran the paired evaluations, withdrew two of
> its own headlines, and confirmed the one result that held with a pre-registered
> two-replicate run.

[![NEO](https://img.shields.io/badge/Built%20autonomously%20by-NEO-0B0B0B?style=for-the-badge)](https://heyneo.com)
[![VS Code Extension](https://img.shields.io/badge/VS%20Code-Get%20the%20Extension-007ACC?style=for-the-badge&logo=visualstudiocode&logoColor=white)](https://marketplace.visualstudio.com/items?itemName=NeoResearchInc.heyneo)
[![Cursor Extension](https://img.shields.io/badge/Cursor-Get%20the%20Extension-1F1F1F?style=for-the-badge&logo=cursor&logoColor=white)](https://marketplace.cursorapi.com/items/?itemName=NeoResearchInc.heyneo)
[![Neo MCP Docs](https://img.shields.io/badge/Neo%20MCP-Documentation-6E56CF?style=for-the-badge&logo=readthedocs&logoColor=white)](https://docs.heyneo.com/neo-mcp)

---

## What happened here

**Ada was being killed by the clock.** On SetupBench — 81 real software-setup tasks, each
with a 480-second budget and graded by the task's own checker in Docker — the original build
overran on 40 to 53 of the 81 tasks, depending on the run. Each overrun was hard-killed at the
deadline, and the grader never ran. The work it had done was lost.

**The fix that held is a watchdog.** Anchor the deadline to the container's real start time,
interrupt the agent 30 seconds before the budget runs out (the 450-second mark on a 480-second
task, `ADA_DEADLINE_MARGIN_MS` in `ada/agent/claude/agent.ts`), and exit cleanly so the
partial work gets graded. Everywhere below, "interrupted by the watchdog" means that cut-off. It changes nothing about the model and everything about whether its work is counted.

**It was confirmed on 2026-09-15** by a two-replicate run, R9/R10, with both builds running
side by side on one machine and nothing but the build differing. Its pass rule is written at
the top of the script that launched it (`bench/run_baseline_vs_best.sh`), and the run's log
shows that script applying the rule when the run finished; no timestamped copy of the rule
predates the run.

| Replicate | n evaluable | origin `df0c537` | shipped `5f4c5c0` | Net | Exact McNemar |
|---|---:|---:|---:|---:|---|
| R9 | 79 | 31 | **47** | **+16** | p = 1.45e-04 |
| R10 | 78 | 36 | **51** | **+15** | p = 6.10e-05 |
| **Pooled** | **157** | **67** | **98** | **+31** | **p = 7.92e-09** |

Paired counts leave out any task where either build hit a harness error, so R9 pairs 79 tasks
and R10 pairs 78. Out of all 81, the origin build passed 32 and 36 and the shipped build 47 and
52; those raw counts appear in the table below.

All four pre-registered conditions are met: **67/157 → 98/157**, 32 gained and 1 lost.
Almost all of the gain is runs the origin build lost to the clock. On the 82 paired runs where
it recorded zero turns, the shipped build passes 28. On the 75 where it ran, it is
67/75 → 70/75 (p = 0.375) — not a significant difference. **The shipped build is not a more
capable agent. It stops being killed.**

Two more things are equally part of the result. A second change — telling the agent how much
time it has left — works exactly as designed and does not raise the pass rate. And two
headlines were published during the campaign and then withdrawn by the agent that published
them. Both are reported here in full.

---

## Results

### Baseline vs shipped build, head to head — R9 + R10

The confirmation run: the same 81 SetupBench tasks, run twice per build, both arms of each
replicate running at the same time on one machine — 162 task-runs per build. Nothing but the
build differs. Every cell is computed from the four raw diagnostics by
`python3 bench/confirmation_table.py`.

| Metric | Baseline `df0c537` | Shipped `5f4c5c0` | Change |
|---|---:|---:|---|
| Tasks passed (162 runs) | 68 (42.0%) | **99 (61.1%)** | +31 tasks, +19.1 pts, +46% relative |
| Paired result, evaluable runs | 67/157 | **98/157** | net +31, 32 gained / 1 lost, exact McNemar p = 7.92e-09 |
| Per replicate (R9, R10) | 32/81, 36/81 | 47/81, 52/81 | paired +16 (p = 1.45e-04), +15 (p = 6.10e-05) |
| **Timed out**: killed by the harness, never graded | 84 | **0** | −84: this is the mechanism |
| Runs recorded with zero turns | 86 | 3 | −83 (mostly the timeouts above) |
| Interrupted by the watchdog, then graded | 0 | 69 | the partial work now counts |
| Turns, total | 1,386 | 2,825 | +104%: the agent actually gets to work |
| Turns, median per task | 0 | 17 | the baseline's median run never took a turn |
| Latency, mean per task | 406 s | **383 s** | −6% |
| Latency, median per task | 485 s | 417 s | −14% |
| Latency on tasks that passed | 313 s mean / 299 s median | 333 s mean / 313 s median | +6%: passing takes slightly longer |
| Total wall time (162 runs) | 18.3 h | **17.2 h** | −6% |
| Invalid rows (excluded from pairing) | 3 | 2 | −1 |
| Tasks still failing | 94/162 | 63/162 | −31 |
| Cost | not captured | not captured | the R9/R10 diagnostics record no tokens or spend |

The baseline's 86 zero-turn runs are 82 of its 84 timeouts, 3 harness errors and 1 run that was
graded; its other 2 timeouts had recorded turns. The shipped build's 3 are 2 harness errors and
1 graded run — none of its runs was killed by the clock.

R1 to R8 ran four tasks at a time. R9/R10 ran one task at a time per build, with both builds and
both replicates overlapping (replicate 2 started at 12:11 while replicate 1 ran until 17:42), so
up to four containers ran at once, as before.

**Where the +31 comes from.** Split the 157 paired runs by what the baseline did:

| Baseline behaviour | n | Baseline passed | Shipped passed | Verdict |
|---|---:|---:|---:|---|
| Recorded zero turns (almost all hard-killed at the deadline) | 82 | 0 | **28** | nearly the whole gain |
| Ran with turns | 75 | 67 | 70 | not significant, p = 0.375 |

### The same-day ladder — 2026-09-12, runs R5 / R7 / R8

Three builds, all 81 tasks, the same harness, one day. Each row adds one change to the row above.

| Build | What it adds | Passed | Against the row above |
|---|---|---:|---|
| `df0c537` | campaign origin, no watchdog | 34/81 | — |
| `6672af8` | **+ T0.1** watchdog, container-anchored deadline, clean exit | **54/81** | **+20 net**, 21 gained / 1 lost, exact McNemar **p = 1.1e-05** |
| `2e495bb` | **+ T1.2** time hints, wrap-up instruction, Bash timeout clamp | 50/81 | **−4 net**, 5 gained / 9 lost, **p = 0.42** |

**What works is the watchdog.** All 21 of its conversions come from the 46 tasks the origin
build hung on with zero turns: 0/46 → 21/46. On the 35 tasks the origin build could actually
run, it scored 34/35 — the watchdog build lost one of them — and nothing built since has
improved on that.

**The time hints are an efficiency result, not an accuracy result.** They do what they were
designed to do: runs interrupted by the watchdog 34 → 7, turns −10.6%, wall time −5.0%. They
do not raise the pass rate (−4, p = 0.42, inside the noise floor), so they ship in the code
**default off**. The shipped build `5f4c5c0` is `2e495bb` with both time-hint gates off,
which makes its behaviour `6672af8`'s. It was measured directly in R9/R10 rather than
inferred, as commit `1d82e56`: the same agent tree (`dab704de524a`) with later documentation
commits.

### Two numbers that were withdrawn

| Published | What was wrong | What it measures when run properly |
|---|---|---|
| Phase A: 27/81 → **59/81** | Assembled from 50 carried-over passes plus a re-run of only the 31 failures. Withdrawn. | Fresh and whole on one day: **54/81** against the origin build's **34/81** (R7 vs R5) |
| Phase B: time hints 52/81 against 24/81, net +28, p = 7.66e-07 | The 24/81 control (R3) was a depressed run, measured hours before its candidate rather than alongside it; the same build scored 54/81 on 2026-09-12, 30 tasks better and none worse. Withdrawn. | Same-day: **54/81 → 50/81**, −4, p = 0.42 |

Both failed the same way: a comparison whose arms were not measured together. The harness
moved 30 tasks on the same build between one run and the next. The campaign's rule became
**same-day paired arms**, and every run is indexed by ID in
[`bench/RUN_REGISTRY.md`](bench/RUN_REGISTRY.md) so that no document can name "the control"
without naming which run it was. The re-check below found that R3 most likely ran on the same
day as its candidate, eight hours earlier, so the rule that actually protects a result is the
stricter one the confirmation run followed: both arms running at the same time.

### Outside SetupBench

On Terminal-Bench 2.0 an earlier build (`08a8d5d`, from Phase A) tied the origin build,
26/38 against 26/38 evaluable tasks, p = 1.0. Two tasks were excluded because the
verifier's own infrastructure failed; both were origin-build passes, so the raw 40-task count
is 28/40 against 26/40. The two arms were run on different days (2026-09-07 and 2026-09-10),
which the campaign's own rule would not now admit. The pass-rate gain did not carry over;
efficiency did, with 40% fewer turns and 34% less execution time on the 38 evaluable tasks. Reported cost is not comparable between the
arms, because a run killed at the hard cap records $0. The shipped build has not been run
outside SetupBench. Analysis: `bench/FINAL40_PAIRED_ANALYSIS.json`; the earlier 2026-09-07
comparison of a prompt-only variant is [`bench/TB_REPORT_40.md`](bench/TB_REPORT_40.md).

### Where the remaining gap is

Phase C (2026-09-16 → 09-17) asked whether the 25 tasks the shipped build failed in both
confirmation replicates are slow or hard. At twice the budget (960 s) it passes 7 of them —
**MIXED** by the pre-registered rule. A late wrap-up candidate (P3) moved +2 pooled,
p = 0.6875, and was rejected against its pre-registered gate. Two further candidates were
dropped before any spend, on the reading that no runs were being cut off by the clock any
more. The raw rows do not support that reading: the harness killed nothing, because the
watchdog stops Ada first, but the watchdog interrupted 28 of the shipped build's 41 failures in
the P3 run. P2, the Bash timeout clamp, was only ever measured inside the time-hints bundle
(R7 → R8, −4) and never on its own; P4, the install hook, never ran. Neither has been tested
alone. Nothing was promoted; the
shipped build is unchanged. Ledger: [`bench/PHASE_C_SUMMARY.md`](bench/PHASE_C_SUMMARY.md).

---

## The journey

### 1. Read the failures

Ada, running `z-ai/glm-5.3-flash` through OpenRouter, lost **53 of 81** SetupBench tasks to
timeouts on the first full run (R1, 27/81), and the grader never saw any of them. The
campaign's report describes the typical shape: minutes of competent work, then a `sleep 300`
poll or a fresh debugging tangent with seconds left, and a hard kill. According to the record,
the budget was stated once at the start and never updated.

### 2. Phase A — stop the kill (2026-09-08 → 09-10)

Phase A added a watchdog that interrupts the agent before the harness would kill it, and then
a deadline anchored to the container's start rather than the agent's and a thinking cap (final
build `08a8d5d`). An early watchdog build cut timeouts from 53 (R1) to 3 (R2, whose exact build
was not recorded). After an interrupt, though, the agent crashed instead of exiting: the runner
never printed its result, so 43 runs were recorded with zero turns — 41 of them were still
graded and 19 passed — and 2 hung until the harness killed them. T0.1 (`6672af8`) made the agent
exit cleanly after the interrupt; neither of its full runs (R3, R7) recorded a zero-turn run. That
fix is real and ships. Phase A's pass-rate headline was not, and is withdrawn above.

### 3. Phase B — let the agent see the clock (2026-09-10 → 09-12)

Two prompt-level ideas came first and failed. A precise "definition of done" section (T1.1)
converted none of the ten failures it targeted and ships default off. Cutting the model's
thinking was a dead end before any evaluation money was spent: the gateway rejects
`thinking: disabled` and the SDK path never forwards a thinking budget. The third idea (T1.2)
injected the remaining time before every model request. It was promoted on a control that
turned out to be a depressed run, and then withdrawn.

### 4. Settle it on one day

The same-day ladder above: origin, watchdog, watchdog plus time hints, all on 2026-09-12 with
the same harness. It is the only measurement in which the time hints are the sole variable.

### 5. Confirm the build that ships

A two-replicate run on 2026-09-15 (R9/R10), under the rule at the top of
`bench/run_baseline_vs_best.sh`: both replicates complete with both diagnostics; each replicate net ≥ +10; at most 3 invalid rows per arm per replicate; pooled
exact McNemar p < 0.001. All four are met. **VERDICT: HOLDS.**

### 6. Look for what is left

Phase C, above: a budget probe, one rejected candidate, two dropped, one deferred. The
deadline still ends most of the remaining failures, so whether more time or better work would
convert them is still open.

---

## What re-measuring taught us

**Your control is a measurement too.** The same build scored 24/81 and then 54/81 on the same
tasks a day apart, with almost the same number of turns (1,544 against 1,554). The depressed
run was slower — the watchdog interrupted 63 of its runs against 34, and it took 23% longer in total — and
nothing recorded says why. Every withdrawn headline in this campaign came from a comparison
whose arms were not measured together. A p-value of 7.66e-07 on the
withdrawn comparison was computed correctly; it answered whether those two particular runs
differed, and they did — just not because of the code.

**Separate an efficiency result from an accuracy result.** The time hints cut interrupted runs
by 79% and turns by 11%. That is real and worth having. It is not a pass-rate gain, and one
number that blends the two is how a change gets promoted on evidence it does not have.

**A working mechanism is not a working change.** The model provably receives the time hint,
quotes it verbatim, and paces itself. The agent did exactly what it was asked and did not get
better at the task.

---

## Repository layout

```
ada/       the agent — a snapshot of rabbah/ada with the campaign's changes, and its record
bench/     the evaluation — harness, raw run diagnostics, paired analyses, reports, run registry
blog.md    the campaign as a story, for readers new to it
```

| Question | Document |
|---|---|
| What is Ada and how do I run it? | [`ada/README.md`](ada/README.md) |
| What changed, what was measured, what does the evidence **not** support? | [`ada/RESULTS.md`](ada/RESULTS.md) — **the record** |
| Tell me the story | [`blog.md`](blog.md), and [`ada/REPORT.md`](ada/REPORT.md) for the campaign's own narrative |
| **Which run is which?** | [`bench/RUN_REGISTRY.md`](bench/RUN_REGISTRY.md) — every scored run, and which pairings are legitimate |
| Why was the time-hints result withdrawn? | [`bench/CTRL_VS_T12_REPORT.md`](bench/CTRL_VS_T12_REPORT.md) — the same-day paired run |
| How noisy is the harness? | [`bench/FRESH_REM81_REPORT.md`](bench/FRESH_REM81_REPORT.md) — the 2026-09-12 morning run (R5/R6) |
| What happened after the confirmation? | [`bench/PHASE_C_SUMMARY.md`](bench/PHASE_C_SUMMARY.md), [`bench/BUDGET_PROBE_REPORT.md`](bench/BUDGET_PROBE_REPORT.md), [`bench/P3_PAIRED_REPORT.md`](bench/P3_PAIRED_REPORT.md) |
| How did it do outside SetupBench? | `bench/FINAL40_PAIRED_ANALYSIS.json`, and [`bench/TB_REPORT_40.md`](bench/TB_REPORT_40.md) for the earlier prompt-only variant |

| Evidence | Path |
|---|---|
| The confirmation run (R9/R10), pooled contrast and decomposition | `bench/BASELINE_VS_BEST_20260915T0825Z.json` |
| The same-day ladder (R5 / R7 / R8) | `bench/CTRL_VS_T12_PAIRED_ANALYSIS.json` |
| Raw per-task diagnostics for every run | `bench/diagnostics/` (baseline arms in `ada-baseline/`, watchdog-only arms in `ada-t01gateoff/`), `bench/p3_evidence/` |
| Terminal-Bench trials | `bench/results-*/` |
| The blog's two charts | `bench/figures/` — each SVG states its values in its `<desc>`, and `bench/verify_docs.py` checks them against the raw rows |
| The harness | `bench/harness/setupbench_ada_runner.ts` (byte-identical to the runner every run recorded), `bench/harness/setupbench_ada_domain_eval.py` (a later revision: the exact evaluator versions that scored the runs, identified by `evaluator_sha256` in each run's protocol, were not kept) |

### How the builds resolve

`ada/` is a snapshot of tag `ada-best-61pct-20260916` (commit `32f4754`, the shipped build
`5f4c5c0` plus documentation). No agent code differs from that tag. Nine files do:

- `ada/RESULTS.md`, and five scripts in `ada/evidence/`, edited during final packaging on
  2026-09-18 to point at the archived evidence. `ada/RESULTS.md` also carries a dated re-check
  banner at the top. The two verify scripts among them also find
  the repository root themselves and check `blog.md` alongside this README.
- `ada/evidence/t12/CTRL_VS_T12_PAIRED_ANALYSIS.json`, regenerated from the archived
  diagnostics during packaging. Only its timestamp and file paths changed; every number is
  identical.
- `ada/REPORT.md`, which carries a dated re-check banner at the top; the text below it is unchanged.
- `ada/scripts/probe-thinking.ts`, the thinking-budget probe, which was never committed.

The campaign's own history — its commits, the three build branches and both tags the records
cite — is in `bench/ada-campaign.bundle`, on top of upstream `rabbah/ada` at `ebaeb9a`:

```bash
git clone https://github.com/rabbah/ada ada-history && cd ada-history
git fetch ../bench/ada-campaign.bundle 'refs/heads/*:refs/remotes/campaign/*' 'refs/tags/*:refs/tags/*'
git rev-parse --short=12 5f4c5c0:agent     # dab704de524a, the shipped agent tree
```

The records name the shipped build by four commits that share the agent tree `dab704de524a`:
`5f4c5c0` (the build), `1d82e56` (as measured in R9/R10, with later documentation), `32f4754`
(the tag) and `c6f917e` (the same build in the byte-identical mirror workspace, removed during
packaging; it is in the bundle on branch `p3-late-wrapup`). `bash bench/verify_builds.sh` runs
the recipe above and checks every build the records name.

One build cannot be rebuilt from history. The origin arm of R9/R10 ran as `417a8f1`, which is
`df0c537` plus a runner shim committed in a workspace since removed. Its agent tree,
`df8a18c09278`, is pinned in the diagnostics and asserted by
`bench/baseline_vs_best_verify.py`, but the commit itself is not in the bundle.

---

## Checking the numbers yourself

```bash
python3 bench/verify_docs.py                        # every result in blog.md and this README
python3 bench/baseline_vs_best_verify.py            # the confirmation run (R9/R10);   exit 0
python3 bench/ctrl_vs_t12_verify.py                 # the same-day ladder + run registry; exit 0
python3 bench/fresh_rem81_verify.py                 # the 2026-09-12 morning run (R5/R6); exit 0
python3 bench/harness/archive_integrity_check.py    # every archived diagnostic against the registry
python3 bench/confirmation_table.py                 # the full R9/R10 table, from the raw rows
```

`verify_docs.py` checks every result the blog and this README state against the raw rows or the file it cites, and
fails if a document or the data changes without the other. `bash bench/verify_builds.sh`
recovers the campaign's git history and checks every build's agent tree; it needs git and
network access. [`bench/README.md`](bench/README.md) says what every file in `bench/` is. The three verify scripts re-derive their figures from the
raw diagnostics rather than trusting the prose and recompute exact McNemar independently; `ctrl_vs_t12_verify.py` also fails if a
withdrawn number appears in this README, the blog or the record without being marked as
withdrawn. The integrity check confirms every archived run's row count, pass count and recorded
build. They need only Python 3.

Packaging on 2026-09-18 removed regenerable bulk: the SetupBench task-input cache (3.1 GB),
the variant tarballs, and the local SetupBench checkout. Re-running an evaluation needs
[microsoft/SetupBench](https://github.com/microsoft/SetupBench) at `041a412` in
`bench/harness/setupbench/`, Docker, and an OpenRouter key. The driver scripts in `bench/`
(`run_*.sh` and friends) are the record of how each run was launched, and keep the absolute
paths of the machine they ran on.

## Re-checked against the raw data, 2026-09-18

Before this branch was published, every claim in this README and the blog was checked against
the raw per-task diagnostics. The confirmation run, the same-day ladder and the Terminal-Bench
tie all reproduce exactly. Eight statements in the campaign's own records do not, and are
corrected above. The records themselves — `ada/RESULTS.md`, `ada/REPORT.md`,
`bench/RUN_REGISTRY.md`, `bench/PHASE_C_SUMMARY.md` and `bench/CTRL_VS_T12_REPORT.md` — keep
their original text, with a dated re-check banner at the top of each that points here.

| The record says | The raw data shows |
|---|---|
| R3, the withdrawn control, ran on 2026-09-10 (its run ID is `20260910T0728Z`), so the +28 compared runs from different days | R3 records commit `6672af8`, which was created at 07:24 UTC on **2026-09-11**, four minutes before R3's start time; on the machine that ran it, its driver log (`bench/t04_control_run.log`) was last written at 10:01 that day, which matches its summed task time (file times are not preserved in git, so that part cannot be checked from a clone; the commit time can, from the bundle). R3 almost certainly ran on 2026-09-11, the same day as R4, about eight hours earlier. The comparison is still withdrawn: its arms were not run together, and the same build scored 54/81 the next day. |
| R3 and R7 did "identical work" | Almost identical turns (1,544 against 1,554), but the watchdog interrupted 63 of R3's runs against 34, and R3 took 23% longer in total. |
| Phase C found "zero 480 s clock-outs", so the Bash clamp (P2) and install hook (P4) had nothing to fix | No run was killed by the harness, but the watchdog interrupted 28 of the shipped build's 41 failures in the P3 run, and 8 of 17 failures in the 960 s probe. P2 was only ever measured inside the time-hints bundle, and P4 never ran; neither has been tested alone. |
| Phase C's "17 hard clock-outs" (`bench/PHASE_C_SUMMARY.md`) | These are the budget probe's 17 valid failures: the watchdog interrupted 8 of them, and 9 finished and failed grading. |
| R2's 43 zero-turn rows came from the interrupt path | They were a reporting bug: 41 were graded and 19 passed. Only 2 were true force-kills (commit `6672af8`'s message). R2 ran on 2026-09-09, before `08a8d5d` existed. |
| R10a had 40 zero-turn rows (`bench/RUN_REGISTRY.md`) | 41, in both the raw diagnostics and `bench/BASELINE_VS_BEST_20260915T0825Z.json`. |
| Terminal-Bench compared arms under one protocol | The origin arm ran on 2026-09-07 and `08a8d5d` on 2026-09-10 — a cross-day comparison. |
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
