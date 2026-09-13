# optimize-ada

A measured, pre-registered optimization campaign for the **Ada agent harness** on
Terminal-Bench 2.0, running a fixed-model paired A/B against the reference
`claude-code` agent — both on **claude-haiku-4-5** (Claude Code CLI 2.1.258 pinned).

The campaign ran **9 lever arms across 3 mechanism classes** (prompt directives,
deterministic SDK hooks, and a repackaged composite), every one gated by
pre-registered promotion/kill criteria, and every one honestly adjudicated.
**No lever cleared the pre-registered bar** — an honest null, with the evidence
for *why* documented below.

> The `ada/` directory is a flattened snapshot of
> [github.com/rabbah/ada](https://github.com/rabbah/ada) at commit
> `ebaeb9a` plus this campaign's env-gated lever modifications (all OFF by
> default). The upstream `.git` history was preserved outside this repo during
> packaging.

---

## Campaign design

- **Benchmark**: Terminal-Bench 2.0 (`terminal-bench@2.0` via Harbor), 15-task
  full subset (loop v1) and a 10-task dev subset (loop v2), k=4 repeats
  (measured from cost CV 0.19 — never below k=4 for paired claims).
- **Arms**: reference `claude-code` agent (arm A) vs the Ada bridge
  (`eval/ada-agent/ada_agent.py` `AdaBridgeAgent`) (arm B), same model, same CLI.
- **Metrics**: binary pass/fail (benchmark's definition of success) plus a
  **graded score** (`tests_passed / tests_total` from each verifier's
  `ctrf.json`) introduced in loop v2 — zero-cost, higher-resolution instrument.
- **Statistics**: position-based within-task pairing; McNemar exact (binary),
  Wilcoxon (graded); Wilson 95% CIs; bootstrap power calibration.
- **Discipline**: every lever was pre-registered in the experiment ledger
  (`eval/experiments/dev-loop/ledger.md`) with explicit kill criteria BEFORE any
  paid run; reach probes (≤$0.25) verified the mechanism actually fired before
  full arms; no gate was ever relaxed.

---

## What was done, in order

### 0. Infrastructure fixes (prerequisites)

- **Dataset-resolution blocker (fixed)**: Harbor's registry pinned terminal-bench
  2.0 task URLs to a dead GitHub repo (404). Root-caused in harbor 0.22.0 source
  (`TaskClient._download_git_tasks` shortuuid cache logic) and fixed WITHOUT
  modifying Harbor: `eval/populate_task_cache.py` pre-populates the deterministic
  cache path from the correct repo at the registry-pinned commit. Proven with an
  oracle run on the previously-crashing task.
- **Adapter kwargs-swallowing defect (found & fixed)**: `AdaBridgeAgent` base
  classes dropped `--ak` kwargs, so env-gated levers silently never reached the
  bridge — the first E-opt1 arm and first L1L2 arm were **untreated re-runs**
  (invalidated, parked under `eval/jobs/*-untreated-invalid/` and
  `*-wrong-aborted/`). Fixed with explicit `__init__` kwarg→env bindings; both
  experiments were re-run as treated v2 arms.

### 1. Baseline (120 runs: 15 tasks × 2 arms × k=4)

| Metric | Arm A (claude-code) | Arm B (Ada bridge) | Delta |
|---|---|---|---|
| Pass rate | 0.450 (27/60) | 0.550 (33/60) | +0.100 (McNemar p=1.0, n.s.) |
| Mean cost/trial | $0.1159 | $0.1042 | −$0.0074 (n.s.) |
| Mean wall/trial | 296s | 187s | **−109s — significant** |

**The one significant, reproducible finding of the whole campaign**: the Ada
harness is a **~1.6× wall-time win at cost parity** vs the reference agent.
Report: `eval/baseline-report.md`.

### 2. Trace mining (signal source)

Over 60 arm-B trials: 22 tool results >10k chars carried **44% of all
tool-result chars**; cache-read ratio mean **0.919** (near ceiling — cache
stabilization rejected pre-run for lack of headroom); output tokens mean
8,003/trial. See `eval/analysis/trace-signals.md`.

### 3. Loop v1 — prompt-directive levers (5 arms, all null)

| Lever | Mechanism | Result | Verdict |
|---|---|---|---|
| **E-opt1** (v1 + v2 treated re-test) | Operating-efficiency guidance (targeted reads, summarize-not-echo, no re-runs) | 0.483 vs 0.550; cost +$0.009 n.s.; wall +5.6s n.s. | **REJECT** |
| **L1+L2** | Always-on self-verify-before-finish + task-adaptive concision gating (ex-ante prompt heuristic, 0 hand-tuned tasks) | 0.533 vs 0.550; cost +20% (turns 20.3→23.6); 3 of 7 pre-registered kills triggered | **REJECT** |
| **X1 verify-once** | Run the deliverable once, fix once, re-run once, finish on evidence | **30/40 vs 24/40 (+0.150)**; graded **+0.122, Wilcoxon p=0.016 — the campaign's only significant effect**; but cost **1.386×** baseline | **KILL (cost)** |
| **X2 verify-against-criteria** | Test against stated success criteria + edge cases, fix once, stop | 28/40 (+0.100 binary, p=0.424; graded +0.046, p=0.59 — noise) | **NOT PROMOTED** |
| **X3 effort-realism** | Minimal working solution, switch approach after ≤3 failures, no speculative reads | 28/40 (+0.100 binary; graded +0.062, p=0.36 — noise); cost **1.317×** | **KILL (cost)** |

### 4. Loop v2 Phase 0 — graded metric upgrade (zero API spend)

- `eval/analysis/graded_score.py` re-scored **546 trials across 12 arms** from
  existing verifier output — binary retained, graded = tests_passed/tests_total.
- **Headline finding**: X2/X3's +0.100 binary deltas were **noise** (graded
  +0.046/+0.062, p≈0.36–0.59) — the "underpowered metric hid real effects"
  hypothesis is refuted for them. The graded metric **did** rescue X1's signal
  (+0.122, p=0.016), confirming verify-once as real but cost-killed.
- Power calibration: at n=40 the graded MDE ≈ 0.146; paired within-task Wilcoxon
  is the powerful test (detected +0.122 at p=0.016 where binary McNemar gave
  p=0.109).
- **Frozen promotion gate** (pre-registered before any paid Phase-1 run):
  graded Δ ≥ +0.05 AND Wilcoxon p < 0.05; binary ≥ 24/40; guards 8/8;
  cost ≤ $0.0967/trial; reach ≥ 95%.

### 5. Loop v2 Phase 1 — deterministic SDK hooks (3 arms + spike)

Seam correction: the loop-v1 "no mid-loop seam without forking the adapter"
finding was **wrong** — `@anthropic-ai/claude-agent-sdk` 0.3.193 exposes
`hooks` (PreToolUse/PostToolUse/Stop/…) and `maxTurns`, reachable via a local
edit in `ada/agent/claude/agent.ts` (`adaHookOptions`, env-gated OFF).

| Arm | Mechanism | Result | Verdict |
|---|---|---|---|
| **H0** | no-op PostToolUse spike | hook fired in bridge log | seam works |
| **H1** | Stop-hook verification gate (block stop once if no execution since last write) | graded +0.0508 but p=0.455; 9/40 real blocks; cost $0.1193 > cap | **KILL** |
| **H2** | PostToolUse output capping (head+tail truncation) | graded −0.0483; cost only +0.5% (needed ≥10% below); shape-aware `capToolResponse()` fix documented in `h2-fix-provenance.md` | **KILL** |
| **H3** | maxTurns hard cap | **pre-run structural rejection, $0 spent**: passing trials need up to 39 turns — long-turn trials are the passes, not the fails | **REJECT** |

### 6. X1r — verify-once repackage (the final arm)

X1 was the only significant graded effect, killed purely on cost (1.386×). X1r
re-delivered the same mechanism inside the frozen gate by attacking the three
zero-cost-trace-measured cost drivers: an **already-executed exemption** clause,
a **hard 2-run verification budget**, and **ADA_HOOK_OUTPUT_CAP=3000**
composition (reclaims 46.3% of tool-result chars vs 25.7% at cap=10000).

Reach probe passed (marker + hook-cap firing verified, $0.12). Full 40-trial
dev arm:

| Criterion | Baseline | X1r | Pass? |
|---|---|---|---|
| Graded paired Δ (magnitude) | 0.7842 | 0.8400 (Δ +0.0558) | ✓ |
| Wilcoxon p < 0.05 | — | **p = 0.3601** | ✗ |
| Binary ≥ 24/40 | 24/40 | 29/40 (McNemar p=0.30) | ✓ |
| Guards 8/8 | 8/8 | **7/8** (fix-code-vulnerability 4/4→3/4) | ✗ |
| Cost ≤ $0.0967 | $0.0879 | **$0.1005 (1.144×)** | ✗ |
| Reach ≥ 95% | — | 100% | ✓ |

**KILL / NOT PROMOTED** — three independent criteria failed. Phase 2 validation
(~$28) correctly not run; zero validation spend.

---

## Learnings (what the evidence says)

1. **The Ada harness itself is the win**: ~1.6× faster at cost parity vs the
   reference claude-code agent on haiku-4.5. That's the campaign's significant,
   reproducible result.
2. **The prompt-directive class is exhausted on this model/dev set**: 5 arms,
   5 nulls. The one real signal (X1 verify-once, +0.122 graded, p=0.016) was
   real but **its cost is inseparable from its effect** — the verification
   turns that convert near-misses ARE the dollars. Repackaging (X1r) halved
   both the cost ratio (1.386×→1.144×) and the effect (+0.122→+0.0558, p=0.36):
   trimming removed waste and repair together.
3. **Exemptions that suppress needed verification are kills regardless of
   savings**: X1r's already-executed clause cut fix-code-vulnerability cost
   0.74× as designed but cost one guard pass (4/4→3/4).
4. **Deterministic hooks fire reliably but can't reach the failure modes
   cheaply**: Stop-gate and output-cap mechanisms were proven end-to-end
   (reach 40/40), but the unexecuted-write condition is too rare and capping
   didn't reduce cost (model re-reads truncated content).
5. **maxTurns is not a free lunch when success correlates with turn count** —
   the long-turn trials are the passes. Rejected pre-run on trace evidence, $0 spent.
6. **Binary metrics hide graded signal, but also expose noise as signal**:
   the graded upgrade rescued X1's real effect and simultaneously showed X2/X3's
   binary deltas were noise. Both directions mattered.
7. **Pass rate on this dev set is capability-bound, not process-bound** — no
   process lever (prompt, hook, or composite) moved it past the pre-registered
   bar. The cleanest uncaptured pool left: cancel-async-tasks (2.09× cost,
   never converts); the untested successor hypothesis is a conditional
   verify-only-when-runnable-artifact directive WITHOUT a repair mandate.
8. **Process discipline that paid off**: pre-registration prevented every
   temptation to relax gates; ≤$0.25 reach probes caught mechanism failures
   before paid arms; the kwargs-binding defect was caught by reach verification
   (invalid runs were parked, not deleted); power calibration told us exactly
   what n=40 could and couldn't detect (MDE ≈ 0.146).

---

## Budget

Cumulative API spend ≈ **$70–71 of the $150 cap** (baseline ~$17; L1L2 cycle
~$14.5 incl. ~$14 of documented invalid runs; E-opt1 re-test ~$6; loop-v2
Phase-1 hooks ~$9; X1r ~$4; probes). Phase 2 validation (~$28) never ran —
saved by the honest nulls.

---

## Repository layout

```
ada/                     Agent source (rabbah/ada @ ebaeb9a + campaign levers,
                         all env-gated OFF by default)
  agent/lever-guidance.ts     X1/X2/X3/X1r + L1/L2 directives
  agent/concision-guidance.ts  E-opt1 guidance
  agent/claude/agent.ts        adaHookOptions SDK-hook seam (H0/H1/H2)
  agent/index.ts               systemPromptAppend wiring
eval/
  ada-agent/ada_agent.py       AdaBridgeAgent (kwarg→env bindings)
  driver/                      harness driver + collect
  analysis/                    graded_score, regrade, power calibration,
                               trace mining, per-arm paired analyses
  results/                     per-arm JSONL records (+ graded/ re-scores)
  jobs/                        raw trial data for every arm and probe
  experiments/                 E-opt1, L1L2, dev-loop decision records
  experiments/dev-loop/ledger.md   the pre-registration ledger (read this first)
  campaign-report.md           the full campaign report (source of this README)
  baseline-report.md           baseline A/B report
plans/                   loop-v2 plan
ada-audit.md             pre-campaign audit of the Ada codebase
```

## Reproducing / extending

- All levers are **env-gated OFF by default** — the tree is inert for normal runs.
- Enable a lever via adapter kwargs, e.g.
  `--ak verify_once_trimmed=1 hook_output_cap=3000` (see `eval/ada-agent/ada_agent.py`).
- Score any arm: `python3 eval/analysis/graded_score.py` (per-test extraction
  from `verifier/ctrf.json`).
- Read `eval/experiments/dev-loop/ledger.md` for every pre-registration and
  `eval/campaign-report.md` for the full narrative with all tables.