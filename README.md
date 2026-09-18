# Ada on SetupBench — an optimisation campaign

[Ada](https://github.com/rabbah/ada) is an open-source coding agent built on Claude Code
through the Claude Agent SDK, written by Simon Guerrier and Rodric Rabbah and released
under the MIT licence. This branch records one campaign to make it pass more real
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
deadline with zero turns recorded, and the grader never ran. The work it had done was lost.

**The fix that held is a watchdog.** Anchor the deadline to the container's real start time,
interrupt the agent before the external kill, and exit cleanly so the partial work gets
graded. It changes nothing about the model and everything about whether its work is counted.

**It was confirmed on 2026-09-15** by a two-replicate run whose pass rule was fixed before any
money was spent — the confirmation run R9/R10, both builds running side by side on one
machine, nothing but the build differing:

| Replicate | n evaluable | origin `df0c537` | shipped `5f4c5c0` | Net | Exact McNemar |
|---|---:|---:|---:|---:|---|
| R9 | 79 | 31 | **47** | **+16** | p = 1.45e-04 |
| R10 | 78 | 36 | **51** | **+15** | p = 6.10e-05 |
| **Pooled** | **157** | **67** | **98** | **+31** | **p = 7.92e-09** |

All four pre-registered conditions are met: **67/157 → 98/157**, 32 gained and 1 lost. The
whole gain is hang conversion. On the 82 paired runs where the origin build hung with zero
turns, the shipped build passes 28. On the 75 where the origin build ran normally, it is
67/75 → 70/75 (p = 0.375) — no real difference. **The shipped build is not a more capable
agent. It stops being killed.**

Two more things are equally part of the result. A second change — telling the agent how much
time it has left — works exactly as designed and does not raise the pass rate. And two
headlines were published during the campaign and then withdrawn by the agent that published
them. Both are reported here in full.

---

## Results

### Origin vs shipped, head to head — R9 + R10, 162 task-runs per build

| Measure | Origin `df0c537` | **Shipped `5f4c5c0`** | Change |
|---|---:|---:|---|
| **Tasks passed** | 68 (42.0%) | **99 (61.1%)** | **+31 tasks, +19.1 points** |
| Paired result, evaluable runs | 67/157 | **98/157** | net +31, exact McNemar p = 7.92e-09 |
| **Killed before grading** (zero turns) | 86 | **3** | −83 — this is the entire mechanism |
| Timed out | 84 | **0** | −84 |
| Interrupted at the deadline, then graded | — | 69 | the partial work now counts |
| Turns, total | 1,386 | 2,825 | +104% — the agent actually gets to work |
| Latency, mean per task | 406 s | **383 s** | −6% |
| Total wall time | 18.3 h | **17.2 h** | −6% |
| Cost | not captured | not captured | the harness records no tokens or spend |

### The same-day ladder — 2026-09-12, runs R5 / R7 / R8

Three builds, all 81 tasks, one driver, one day. Each row adds one change to the row above.

| Build | What it adds | Passed | Against the row above |
|---|---|---:|---|
| `df0c537` | campaign origin, no watchdog | 34/81 | — |
| `6672af8` | **+ T0.1** watchdog, container-anchored deadline, clean exit | **54/81** | **+20 net**, 21 gained / 1 lost, exact McNemar **p = 1.1e-05** |
| `2e495bb` | **+ T1.2** time hints, wrap-up instruction, Bash timeout clamp | 50/81 | **−4 net**, 5 gained / 9 lost, **p = 0.42** |

**What works is the watchdog.** All 20 of its net conversions come from the 46 tasks the
origin build hung on with zero turns: 0/46 → 21/46. On the 35 tasks the origin build could
actually run, it scored 34/35, and nothing built since has improved on that.

**The time hints are an efficiency result, not an accuracy result.** They do what they were
designed to do: runs interrupted at the deadline 34 → 7, turns −10.6%, wall time −5.0%. They
do not raise the pass rate (−4, p = 0.42, inside the noise floor), so they ship in the code
**default off**. The shipped build `5f4c5c0` is `2e495bb` with both time-hint gates off,
which makes its behaviour `6672af8`'s — and it was measured under its own name in R9/R10
rather than inferred.

### Two numbers that were withdrawn

| Published | What was wrong | What it measures when run properly |
|---|---|---|
| Phase A: 27/81 → **59/81** | Assembled from 50 carried-over passes plus a re-run of only the 31 failures. Withdrawn. | Fresh and whole on one day: **54/81** against the origin build's **34/81** (R7 vs R5) |
| Phase B: time hints 52/81 against 24/81, net +28, p = 7.66e-07 | The 24/81 control was a depressed run; the same build scored 54/81 two days later, 30 tasks better and none worse. Withdrawn. | Same-day: **54/81 → 50/81**, −4, p = 0.42 |

Both failed the same way: a comparison anchored to a run measured under conditions that no
longer held. The harness moves 30 tasks on identical code between two days. **Same-day paired
arms are now the only admissible evidence**, and every run is indexed by ID in
[`bench/RUN_REGISTRY.md`](bench/RUN_REGISTRY.md) so that no document can name "the control"
without naming which run it was.

### Outside SetupBench

On Terminal-Bench 2.0 an earlier build (`08a8d5d`, from Phase A) tied the origin build,
26/38 against 26/38 evaluable tasks, p = 1.0. Two tasks were excluded because the
verifier's own infrastructure failed. The pass-rate gain did not carry over; efficiency did,
with 39% fewer turns and 35% less execution time. Reported cost is not comparable between the
arms, because a run killed at the hard cap records $0. The shipped build has not been run
outside SetupBench. Analysis: `bench/FINAL40_PAIRED_ANALYSIS.json`; the earlier 2026-09-07
comparison of a prompt-only variant is [`bench/TB_REPORT_40.md`](bench/TB_REPORT_40.md).

### Where the remaining gap is

Phase C (2026-09-16 → 09-17) asked whether the 25 tasks that fail on every run are slow or
hard. **Mostly hard.** At twice the budget (960 s) the shipped build passes 7 of them. A late
wrap-up candidate (P3) moved +2 pooled, p = 0.6875, and was rejected against its
pre-registered gate. Two further candidates were dropped before any spend because no
clock-out population remained for them to fix. Nothing was promoted; the shipped build is
unchanged. Ledger: [`bench/PHASE_C_SUMMARY.md`](bench/PHASE_C_SUMMARY.md).

---

## The journey

### 1. Read the failures

Ada, running `z-ai/glm-5.3-flash` through OpenRouter, lost **53 of 81** SetupBench tasks to
timeouts on the first full run (R1, 27/81). The traces showed the same shape again and again:
seven minutes of competent work, then a `sleep 300` poll or a fresh debugging tangent with
seconds left, and a hard kill. The only mention of the budget was a line in the system prompt,
written once and never updated.

### 2. Phase A — stop the kill (2026-09-08 → 09-10)

Phase A's final build (`08a8d5d`) added a watchdog that interrupts before the harness does,
a deadline anchored to the container's start rather than the agent's, and a thinking cap.
Timeouts fell from 53 (R1) to 3 (R2) — but 43 runs were still recorded with zero turns,
because after the interrupt the agent process was force-killed instead of exiting. T0.1
(`6672af8`) made it exit cleanly after the interrupt; in its next full run (R7), not one run was recorded
with zero turns. That
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
one driver. It is the only measurement in which the time hints are the sole variable.

### 5. Confirm the build that ships

A pre-registered two-replicate run on 2026-09-15 (R9/R10): both replicates complete with both
diagnostics; each replicate net ≥ +10; at most 3 invalid rows per arm per replicate; pooled
exact McNemar p < 0.001. All four are met. **VERDICT: HOLDS.**

### 6. Look for what is left

Phase C, above: a budget probe, one rejected candidate, two dropped, one deferred. The
remaining gap on this model is capability, not scaffolding: most of the tasks that still fail
end with a setup the grader rejects, not with the clock running out.

---

## What re-measuring taught us

**Your control is a measurement too.** The same build scored 24/81 and then 54/81 on the same
tasks two days apart, doing provably identical work. Every wrong headline in this campaign came
from a control measured under conditions that no longer held. A p-value of 7.66e-07 on the
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
| The harness | `bench/harness/setupbench_ada_eval.py`, `bench/harness/setupbench_ada_runner.ts` |

### How the builds resolve

`ada/` is a snapshot of tag `ada-best-61pct-20260916` (commit `32f4754`, the shipped build
`5f4c5c0` plus documentation). No agent code differs from that tag. Eight files do:

- `ada/RESULTS.md`, and five scripts in `ada/evidence/`, edited during final packaging on
  2026-09-18 to point at the archived evidence. The two verify scripts among them also find
  the repository root themselves and check `blog.md` alongside this README.
- `ada/evidence/t12/CTRL_VS_T12_PAIRED_ANALYSIS.json`, regenerated from the archived
  diagnostics during packaging. Only its timestamp and file paths changed; every number is
  identical.
- `ada/scripts/probe-thinking.ts`, the thinking-budget probe, which was never committed.

The campaign's own history — its commits, the three build branches and both tags the records
cite — is in `bench/ada-campaign.bundle`, on top of upstream `rabbah/ada` at `ebaeb9a`:

```bash
git clone https://github.com/rabbah/ada ada-history && cd ada-history
git fetch ../bench/ada-campaign.bundle 'refs/heads/*:refs/remotes/campaign/*' 'refs/tags/*:refs/tags/*'
git rev-parse --short=12 5f4c5c0:agent     # dab704de524a, the shipped agent tree
```

One build cannot be rebuilt from history. The origin arm of R9/R10 ran as `417a8f1`, which is
`df0c537` plus a runner shim committed in a workspace since removed. Its agent tree,
`df8a18c09278`, is pinned in the diagnostics and asserted by
`bench/baseline_vs_best_verify.py`, but the commit itself is not in the bundle.

---

## Checking the numbers yourself

```bash
python3 bench/baseline_vs_best_verify.py            # the confirmation run (R9/R10);   exit 0
python3 bench/ctrl_vs_t12_verify.py                 # the same-day ladder + run registry; exit 0
python3 bench/fresh_rem81_verify.py                 # the 2026-09-12 morning run (R5/R6); exit 0
python3 bench/harness/archive_integrity_check.py    # every archived diagnostic against the registry
```

Each script re-derives its figures from the raw diagnostics rather than trusting the prose,
recomputes exact McNemar independently, and asserts that withdrawn numbers are never quoted in
this README, the blog or the record without being marked as withdrawn. They need only Python 3.

Packaging on 2026-09-18 removed regenerable bulk: the SetupBench task-input cache (3.1 GB),
the variant tarballs, and the local SetupBench checkout. Re-running an evaluation needs
[microsoft/SetupBench](https://github.com/microsoft/SetupBench) at `041a412` in
`bench/harness/setupbench/`, Docker, and an OpenRouter key. The driver scripts in `bench/`
(`run_*.sh` and friends) are the record of how each run was launched, and keep the absolute
paths of the machine they ran on.

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
