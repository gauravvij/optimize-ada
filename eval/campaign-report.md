# Ada Optimization Campaign — Final Report

Campaign per `/root/optimize_ada/plans/plan.md`. Fixed-model paired A/B on
Terminal-Bench 2.0: reference `claude-code` agent vs the Ada bridge, both on
**claude-haiku-4-5**, same 15-task subset, k=4 repeats (measured by variance
probe), model and CLI pinned (haiku-4-5, Claude Code 2.1.258).

Sections 1–6 document loop v1 (prompt-directive levers; all null). Section 7
documents **loop v2** (graded-metric upgrade + deterministic SDK-hook class),
which ended in an honest null with the metric-resolution finding, the seam
correction, and the full H-series ledger.

## 1. Dataset-resolution blocker (fixed)

`harbor run --dataset terminal-bench@2.0` crashed at dataset fetch: Harbor's
registry pins terminal-bench 2.0 task git URLs to the **dead**
`https://github.com/laude-institute/terminal-bench-2.git` (repo moved to
`github.com/harbor-framework/terminal-bench-2`; git clone exit 128, 404).

**Root-cause mechanism** (read from harbor 0.22.0 source, `tasks/client.py`):
`TaskClient._download_git_tasks` caches git tasks at
`~/.cache/harbor/tasks/<shortuuid.uuid(str(task_id))>/<task_name>/` and SKIPS
the clone when that deterministic path already exists. The cache dir is keyed
by a hash of `GitTaskId(git_url=<dead URL>, git_commit_id, path=<task>)`.

**Fix**: pre-populate the cache from the correct repo at the registry-pinned
commit `69671fbaac6d67a7ef0dfec016cc38a64ef7a77c`, WITHOUT modifying Harbor or
overriding any URL.
- `eval/populate_task_cache.py` clones `harbor-framework/terminal-bench-2`
  (which redirects the registry id) at the pinned commit, computes the exact
  shortuuid cache path per task, and copies all 15 subset task dirs in.
- Validated the hash logic against pre-existing cache dirs (regex-log,
  fix-git, sqlite-db-truncate matched exactly).
- Functional proof: oracle run on `password-recovery` (previously the crashing
  path) exited 0, 1/1 reward 1.0, 0 exceptions, 28s — no dead-URL clone.

## 2. Baseline (120 runs = 15 tasks x 2 arms x k=4)

Jobs: `baseline-armA` (reference claude-code agent) and `baseline-armB`
(Ada bridge via `eval/ada-agent/ada_agent.py` `AdaBridgeAgent`).
Full results: `eval/results/baseline-armA.jsonl` + `baseline-armB.jsonl`
(60 records each). Report: `eval/baseline-report.md`.

| Metric | Arm A (claude-code) | Arm B (Ada bridge) | Delta (B − A) |
|---|---|---|---|
| Pass rate | 0.450 (27/60) | 0.550 (33/60) | +0.100 |
| Wilson 95% CI | [0.331, 0.575] | [0.425, 0.669] | McNemar exact p = 1.0000 (n.s.) |
| Mean cost / trial | $0.1159 | $0.1042 | −$0.0074 [−0.0350, +0.0203] n.s. |
| Mean wall / trial | 296s | 187s | −109.2s [−157.1, −61.3] **significant** |
| Exceptions | 0 | 1 (AgentTimeoutError, large-scale-text-editing @1200s) | — |
| Per-task solved | 10/15 | 10/15 | discordants: 1 A-only, 1 B-only |

Verdict: Ada's harness contribution on haiku-4.5 is **+10.0 points pass rate**
(not statistically distinguishable from noise at k=4), **significantly faster**
per trial (~1.6×), and **cost-neutral** (slightly cheaper, n.s.). Wall time is
the only paired delta significant at 95%.

## 3. Trace mining (signal source for experiments)

`eval/analysis/mine_traces.py` → `eval/analysis/trace-signals.md` over 60
arm-B trials:
- 1,161 tool results; 22 results >10k chars = **44% of all tool-result chars**
  (max 32,990; p99 15,991; median 132).
- Cache-read ratio mean **0.919** (min 0.550, max 0.984) — near ceiling.
- Output tokens/trial mean **8,003** (max 34,384).

## 4. Candidate funnel (all evaluated candidates)

| Candidate | Result | Evidence |
|---|---|---|
| E1 registry cap / session TTL | N/A (harness) | Fresh container+bridge per trial; adapter DELETEs its single session — registry never grows. Not measurable via A/B. |
| E2 literal tool_result capping | INFEASIBLE | Claude Agent SDK `query()` loop has no mid-loop seam without forking @astropods/adapter-claude-agent-sdk. |
| E3 cache stabilization | REJECTED pre-run | Measured cache-read ratio 0.919 is near ceiling; no headroom worth a paid run. |
| E5 build-cache pre-warm | OUT OF SCOPE | Image-level change to task base images; not an Ada-layer A/B. |
| **E-opt1 concision guidance** | **REJECTED** (v2 treated re-test, RESOLVED) | v1 verdict SUSPECT (kwargs-swallowing defect → untreated). Re-test `e-opt1-arm-v2` (treated, reach verified 60/60): 0.483 vs B 0.550 (in noise), cost +$0.0091 n.s., wall +5.6s n.s. → REJECT per pre-registered rule. See `eval/experiments/E-opt1/decision-v2.json`. |
| **L1+L2 self-verify + adaptive concision** | **REJECTED** (measured) | Full 15x4 arm run (treated, reach verified 60/60); 3 of 7 pre-registered kill criteria triggered. |

### E-opt1 (measured): env-gated concision guidance

Change: `ada/agent/concision-guidance.ts` (env-gated system-prompt guidance:
targeted reads over full-file dumps, summarize-not-echo, no re-runs, terse
narration) appended via `systemPromptAppend` array-join in `ada/agent/index.ts`;
adapter kwarg `concision_guidance` (default OFF) gates it. Enabled only via
`--ak concision_guidance=1`. Synced source + runtime with md5 parity.

Dev probe (3 tasks x k=2): 6/6, 0 exceptions, mean 0.667, Pass@2 1.000;
cost $0.0575 vs $0.0582 arm-B direction down → PROMISING → full arm.

Full arm (15 tasks x k=4, job `e-opt1-arm`, 60/60 trials, 0 exceptions):
`eval/results/e-opt1-arm.jsonl`, decision in
`eval/experiments/E-opt1/decision.json`.

| Metric | Arm B | E-opt1 | Delta | 95% CI | Sig? |
|---|---|---|---|---|---|
| Pass rate | 0.550 | 0.500 | −0.050 | E Wilson [0.377, 0.623] | within B noise band ✓ |
| Mean cost | $0.1024 | $0.1018 | +$0.0074 (14 paired tasks) | [−0.0074, +0.0221] | no |
| Mean wall | — | — | −27.6s (15 paired tasks) | [−100.1s, +44.9s] | no |

McNemar exact p = 1.0000 (1 B-only, 2 E-only per-task solved discordants).
Pre-registered rule: ACCEPT iff (cost OR latency significant at 95%) AND pass
delta within B's noise band → neither cost nor wall significant →
**VERDICT: REJECT** (no measurable effect at k=4). Code stays in-tree but the
gate is OFF by default, so E-opt1 is inert for all non-candidate runs.

Direction note (not an over-claim): large-scale-text-editing went 0/4 → 3/4
and password-recovery 0/4 → 1/4 under the guidance; regex-log 3/4 → 0/4 and
fix-git 4/4 → 1/4 regressed. Mixed at k=4 — consistent with run-to-run
variance; unresolved at this sample size.

> **Caveat (added post-L1L2) — RESOLVED by the v2 re-test (below):** E-opt1's
> original REJECT was **suspect** because the v1 arm ran through the same
> `AdaBridgeAgent` kwargs-swallowing defect discovered during L1L2 (base classes
> dropped `--ak` kwargs, so `ADA_CONCISION_GUIDANCE` never reached the bridge —
> the v1 arm was an untreated baseline re-run). The v2 treated re-test below
> provides the valid measurement.

#### E-opt1 re-test (v2, TREATED arm) — job `e-opt1-arm-v2` (resolves SUSPECT)

Re-test run after the adapter fix (explicit `AdaBridgeAgent.__init__` binds
`concision_guidance` → `ADA_CONCISION_GUIDANCE=1` in `_bridge_env()`). Zero-cost
pre-flight passed: importlib kwargs-binding test (`KWARGS BINDING VERIFIED`) +
in-container probe `e-opt1-probe-v2` (2 tasks × k=1, $0.0895) with the
`Operating-efficiency guidance` marker present in both bridge logs.

Full arm (15 tasks x k=4, job `e-opt1-arm-v2`, 60/60 trials, 1 exception —
large-scale-text-editing `AgentTimeoutError` @1200s, mirroring arm B's known
exception on the same task; 1h37m52s): `eval/results/e-opt1-arm-v2.jsonl`,
decision in `eval/experiments/E-opt1/decision-v2.json`. Treatment reach:
**60/60 bridge logs** contain the concision-guidance marker (see
`eval/experiments/E-opt1/verification-provenance-v2.md`).

| Metric | Arm B | E-opt1 v2 | Delta | 95% CI | Sig? |
|---|---|---|---|---|---|
| Pass rate | 0.550 (33/60) | 0.483 (29/60) | −0.067 | V2 Wilson [0.362, 0.607] | within B noise band ✓ |
| Mean cost | $0.1024 | $0.1001 | +$0.0091 (14 paired tasks) | [−0.0149, +0.0330] | no |
| Mean wall | 125s | 131s | +5.6s (15 paired tasks) | [−43.6s, +54.7s] | no |

Position-based within-task McNemar (60 paired positions): 24 both-pass, 22
both-fail, **9 B-only, 5 V2-only** → exact p = 0.4240. Task-level solved
McNemar (secondary): 0 B-only, 1 V2-only → p = 1.0. Cost pairing excluded
large-scale-text-editing (B has only 3 usable costs there; v2 has its own
AgentTimeoutError there). Pre-registered rule: ACCEPT iff (cost OR latency
significant at 95%) AND pass delta within B's noise band → neither significant
→ **VERDICT: REJECT** (v2 treated measurement confirms v1's REJECT direction).

v2-vs-v1 reading: v1 (untreated, 0.500) vs v2 (treated, 0.483) differ by 0.017
— within k=4 noise, consistent with v1 being an untreated re-run. Treated v2
still shows the same task-adaptive direction: large-scale-text-editing 0/4 →
2/4 (cost $0.368→$0.151, wall 907s→627s) while fix-git 4→2, regex-log 3→1,
vulnerable-secret 4→3 regressed. Concision guidance delivered correctly does
not clear the pre-registered bar at haiku-4.5 k=4.

### L1+L2 (measured): self-verification + adaptive concision

Change: `ada/agent/lever-guidance.ts` (new module, md5 `ccadffd9`, synced
source+runtime) wired into the same `systemPromptAppend` seam. **L1** =
always-on (in-arm) *self-verification-before-finish* directive
(`ADA_SELF_VERIFY=1`): run what you produced, check observable output, fix and
re-verify. **L2** = task-adaptive concision gating (`ADA_ADAPTIVE_CONCISION=1`)
that reuses the E-opt1 operating-efficiency guidance ONLY when an **ex-ante
prompt-property heuristic** fires: bulk-volume signal
(`/million|thousand|large[- ]scale/i`) OR forensic-search signal
(`/forensic/i` AND `/deleted/`) → fires on exactly `large-scale-text-editing`
+ `password-recovery` (0 hand-tuned tasks). No task-name allowlist. Adapter
`eval/ada-agent/ada_agent.py` gained an explicit `__init__` binding
`self_verify`/`adaptive_concision`/`lever_debug` → `ADA_*` env vars (fixes the
kwargs-swallowing defect above).

Smoke evidence: unit gating test 11/11 (fires on exactly 2/15 prompts, gates
OFF clean); bridge smoke 3-part vs 2-part append; **in-container v2 run 60/60
bridge logs carry `[lever-debug]` + `Self-verification requirement`**, and the
L2 guidance is present in 4/4 large-scale + 4/4 password logs, 0/4 elsewhere —
treatment reach verified end-to-end.

Full arm (15 tasks x k=4, job `l1l2-arm-v2`, 60/60 trials, 0 exceptions,
1h33m43s): `eval/results/l1l2-arm.jsonl`, decision in
`eval/experiments/L1L2/decision.json`.

| Metric | Arm B | L1+L2 | Delta | 95% CI | Sig? |
|---|---|---|---|---|---|
| Pass rate | 0.550 (33/60) | 0.533 (32/60) | −0.017 | V Wilson [0.409, 0.654] | no (McNemar p=1.0) |
| Mean cost | $0.1042 | $0.1248 | +$0.0211 (59 paired) | [−0.0003, +0.0426] | no |
| Mean wall (duration_ms) | 125s | 127s | +2.3s (60 paired) | [−59.8s, +64.4s] | no |
| Tokens (total in/out) | 26.2M / 472k | 32.8M / 576k | +6.6M / +104k | — | — |
| MIXED (8 tasks) | 21/32 | 19/32 | −2 | — | within ±0.126 noise |

McNemar exact p = 1.0000 (7 B-only, 6 L1L2-only discordants).
Pre-registered kill criteria — 3 of 7 triggered → **VERDICT: REJECT**:

1. **L1 MIXED pass count: 19 < 23** (bar = B's 21 + 2) — KILL
2. **L2 fix-git + regex-log: 4 ≤ 5** (bar = B's 7 − 2; fix-git 4→2, regex-log
   3→2) — KILL
3. **Mean cost $0.1248 > $0.1229** (bar = B × 1.2; L1 adds verification turns
   20.3→23.6) — KILL
4. ALL-PASS guards: all 3 tasks 4/4 — pass
5. L2 large-scale-text-editing: 0 → 2/4 (at bar) — pass
6. L2 suite rate 0.533 ≥ 0.424 — pass
7. Heuristic hand-tuned tasks: 0 ≤ 3 — pass

Only clean L2-positive signal: large-scale-text-editing 0/4 → 2/4 (the gate
targeted it; same thrash-relief seen in E-opt1). Offset by precision-task
regressions (fix-git 4→2, regex-log 3→2, cancel-async-tasks 2→0) — the same
E-opt1 flip pattern. The always-on L1 directive did not convert the near-miss
cluster at haiku-4.5 and added cost. Suite delta is inside the k=4 noise band
(±0.126); the kill is per the pre-registered bar, not significance.

## 5. Budget & runtime

- **Prior spend** (baseline 120 runs + E-opt1 + probes): ~$17 API
  (~$6.95 arm A + ~$6.04 arm B + ~$6.11 E-opt1 + probes).
- **L1L2 cycle spend** (this cycle, all API): **~$14.47** —
  - `l1l2-arm-wrong-aborted` (first launch omitted `--include-task-name`, ran
    28 off-subset tasks at k=1): ~$7.50 wasted;
  - `l1l2-arm` (60-trial run, later found UNTREATED due to adapter
    kwargs-swallowing): $6.6151 — parked at
    `eval/jobs/l1l2-arm-untreated-invalid/`;
  - `l1l2-probe` (4-trial treatment-reach probe): $0.353;
  - `l1l2-arm-v2` (valid treated 60-trial arm): **$7.4895**.
- **E-opt1 re-test cycle spend** (this cycle, all API): **~$6.09** —
  - `e-opt1-probe-v2` (2-trial treatment-reach probe): $0.0895;
  - `e-opt1-arm-v2` (valid treated 60-trial arm): **$6.0042** (59 cost records;
    1 AgentTimeoutError with no usage).
- **Cumulative API spend: ~$44–45 of the $150 cap** (~$105–106 headroom).
- Wall: baseline 2h32m (A) + 1h37m (B); E-opt1 full 1h22m; E-opt1 v2 full
  1h37m52s; L1L2 v2 full 1h33m43s; probes 4m27s / 3m16s.

## 6. Recommendations (updated config guidance)

- Keep `claude-haiku-4-5` and CLI 2.1.258 pinned; keep the 15-task subset and
  k=4 (measured from cost CV 0.19; do not drop below k=4 for paired claims).
- The Ada harness is a **wall-time win at parity cost** vs the reference
  claude-code agent — the significant, reproducible finding of the baseline.
- Pass-rate differences between bridge variants at k=4 are noise-limited
  (±0.126); any future candidate must clear the pre-registered significance
  bar or add repeats.
- E-opt1-style prompt guidance can be tested cheaply via the existing env-gate
  mechanism; at haiku-4.5 cost levels the achievable delta is below the k=4
  resolution. Candidates that move wall time (e.g., concurrency/queue surfacing)
  are more likely to clear significance than token-level tweaks.

## Deliverables

- `eval/results/baseline-armA.jsonl`, `baseline-armB.jsonl`,
  `e-opt1-arm.jsonl` (INVALIDATED v1, untreated), `e-opt1-arm-v2.jsonl`
  (v2 TREATED arm), `e-opt1-probe.jsonl` (raw per-run records)
- `eval/baseline-report.md`, `eval/variance-probe.md`,
  `eval/analysis/trace-signals.md` (reports)
- `eval/experiments/E-opt1/{README.md,decision.json}` (v1 experiment record,
  invalidated), `eval/experiments/E-opt1/{decision-v2.json,
  verification-provenance-v2.md}` (v2 treated record, RESOLVED)
- `eval/results/l1l2-arm.jsonl` (TREATED v2 arm; invalid untreated run parked at
  `eval/jobs/l1l2-arm-untreated-invalid/`), `eval/experiments/L1L2/{README.md,
  decision.json,smoke_gate_test.mjs,smoke_bridge_test.sh}` (experiment record)
- `eval/populate_task_cache.py`, `eval/ada-agent/ada_agent.py`,
  `eval/ada-runtime/`, `eval/driver/collect.py`, `eval/analysis/*.py`
- `ada/agent/concision-guidance.ts` + `ada/agent/index.ts` (E-opt1 patch,
  env-gated OFF by default)
- `ada/agent/lever-guidance.ts` + `ada/agent/index.ts` (L1+L2 patch, md5
  `ccadffd9`/`37fd53b1`, env-gated OFF by default; adapter kwargs bound via
  explicit `AdaBridgeAgent.__init__` in `eval/ada-agent/ada_agent.py`)

---

# Section 7 — Loop v2: graded metric upgrade + deterministic SDK hooks (honest null)

Loop v2 per `plans/plan.md` (2025-09-04). Full experiment ledger:
`eval/experiments/dev-loop/ledger.md`. Paired analysis:
`eval/experiments/dev-loop/regrade-report.md`.

## 7.1 Why the loop stalled (measured diagnosis)

Five prior experiments returned five nulls (E-opt1, L1+L2, X1, X2, X3). Two
systematic faults were measured, not five unlucky ideas:

1. **Metric resolution fault.** Binary pass/fail discards the graded signal the
   verifiers already emit. 32 of 42 TB2 tasks have >1 verifier test (dev-set
   counts: cancel-async-tasks 6, openssl-selfsigned-cert 6,
   fix-code-vulnerability 6, git-leak-recovery 5, large-scale-text-editing 5).
   A 5/7 → 6/7 improvement scores zero under the binary metric. With ±0.126
   binary noise at k=4, a +0.100 effect is undetectable by construction.
2. **Mechanism monoculture.** All five levers were prompt-directive nudges —
   probabilistic (the model may ignore them) and token-costly (L1 raised turns
   20.3 → 23.6 and blew the cost guard; X3 hit 1.317×).

## 7.2 Phase 0 — graded metric upgrade (zero API spend)

- `eval/analysis/graded_score.py`: per-test extraction from every
  `verifier/ctrf.json` → graded = tests_passed / tests_total (binary retained).
  Re-scored **546 trials across 12 arms** (all prior arms + dev-h1 + dev-h2),
  0 excluded; 1-test tasks graded == binary exactly; graded ∈ [0,1] checked.
- `eval/analysis/regrade_arms.py` → `regrade-report.md`: paired graded +
  binary side by side for every arm (position-based pairing within task).

**Headline regrade (graded delta | Wilcoxon p | binary delta | McNemar p):**

| arm | graded Δ | p (Wilcoxon) | binary Δ | p (McNemar) | shift |
|---|---|---|---|---|---|
| dev-x1 | +0.122 | **0.0160** | +0.150 | 0.1094 | graded SIG, binary NS |
| dev-x2 | +0.046 | 0.5898 | +0.100 | 0.4240 | both NS |
| dev-x3 | +0.062 | 0.3613 | +0.100 | 0.3438 | both NS |
| e-opt1-arm (invalidated) | −0.083 | 0.0982 | −0.050 | 0.6291 | both NS |
| e-opt1-arm-v2 | −0.067 | 0.1050 | −0.067 | 0.3438 | both NS |
| l1l2-arm | −0.014 | 0.7247 | −0.017 | 1.0000 | both NS |

**Answer to the pre-registered question: X2/X3 are NOT resurrected.** Their
+0.100 binary deltas were noise, not real effects killed by the underpowered
binary metric — under the higher-resolution graded metric they shrink to
+0.046/+0.062 with p = 0.59/0.36. The underpowered-metric hypothesis is
**REFUTED for X2/X3**.

The one lever the graded metric DOES rescue is **X1 (verify-once): graded
+0.122, Wilcoxon p = 0.016** — a real effect previously killed on COST
(1.386×), not on signal. Its mechanism (verification before finish) is
confirmed twice; only its delivery (always-on prompt text) was too expensive.
That directly motivated H1.

**Power calibration** (`eval/analysis/power_calibration.py`, dev-baseline
n=40): graded-mean bootstrap 95% CI half-width **±0.105** at n=40; null
paired-delta band [−0.145, +0.147], MDE ≈ 0.146; at n=120 the band narrows to
[−0.085, +0.084]. Paired within-task Wilcoxon is the powerful test — it
detected X1's +0.122 at p=0.016 where binary McNemar gave p=0.109.

**Graded promotion gate (pre-registered BEFORE any Phase-1 paid run):**
promote iff (a) paired graded delta ≥ +0.05 AND Wilcoxon p < 0.05;
(b) binary ≥ 24/40; (c) guards 8/8; (d) mean cost ≤ $0.0967; (e) reach ≥ 95%.

## 7.3 Seam correction (supersedes the loop-v1 E2 "no mid-loop seam" finding)

The earlier finding — "no mid-loop seam without forking
@astropods/adapter-claude-agent-sdk" — was **WRONG**. Verified in the
installed SDK (0.3.193, vendored under the adapter):
`hooks?: Partial<Record<HookEvent, HookCallbackMatcher[]>>` and
`maxTurns?: number`; `HOOK_EVENTS` includes PreToolUse, PostToolUse,
PostToolUseFailure, Stop, SubagentStop. The astropods adapter is a thin
passthrough (`export const query = patched.query`). Hooks are reachable with a
local edit — no fork.

**H2 tool_response root cause (measured).** Two reach probes (cap=300) showed
zero `[hook:cap]` hits because the hook guarded
`typeof tool_response === "string"` — but the SDK types `tool_response` as
`unknown` and real Bash/Read/Write responses are **objects**
(`{stdout, stderr, ...}`, `{type, file}`, `{type, filePath, content, ...}`),
so the guard never matched. Fix: shape-aware `capToolResponse()` (string /
object string-fields / content-block array; head 60% + tail 25% + elision
marker; same shape returned via `updatedToolOutput`, itself typed `unknown`)
plus a per-fire reach log. Unit test `eval/analysis/test_cap_hook.mjs` 13/13
PASS; md5 `ea5225ea34917de672f9543e80dd3fa8` across `ada/agent/claude/agent.ts`
↔ runtime mirror. Seam is env-gated OFF by default (`ADA_HOOK_*`).

## 7.4 Phase-1 H-series ledger (deterministic SDK hooks)

| Arm | Mechanism | Probe | 40-trial result | Verdict |
|---|---|---|---|---|
| **H0** | seam spike: no-op PostToolUse log | PASSED — `[hook:spike] PostToolUse Write fired` in regex-log bridge log (~$0.10) | — | seam works |
| **H1** | Stop-hook verification gate (block stop once if no execution since last write) | PASSED — block fired exactly once, re-entrancy latch respected (~$0.18) | graded 0.8350 vs 0.7842 (+0.0508, Wilcoxon p=0.4551); binary 27/40 vs 24/40 (p=0.5811); guards 8/8; cost **$0.1193** (> $0.0967 cap); reach 40/40, blocked 9/40 | **KILL** (p≥0.05 + cost breach) |
| **H2** | PostToolUse output capping (>N chars, head+tail) | probe3 PASSED after fix — 27 fired + 6 truncations at cap=300, trial still passed ($0.257) | cap=10000; graded 0.7358 vs 0.7842 (**−0.0483**, p=0.5627); binary 22/40 vs 24/40 (p=0.8036); guards 8/8; cost $0.0883 = **+0.5%** (kill threshold: ≥10% below); reach 40/40 (609 fired / 14 trunc) | **KILL** (cost not ≥10% below) |
| **H3** | maxTurns hard cap | — | **PRE-RUN STRUCTURAL REJECTION** (no paid spend): dev-baseline passing trials need up to 39 turns (fix-code-vulnerability guard passes at 29/36/39, git-multibranch 39, large-scale-text-editing 37) while failing trials max at 30 — no admissible cap exists | **REJECT** (trace evidence) |

H1 learning: the deterministic Stop gate works mechanically (9/40 real blocks)
but the unexecuted-write condition is too rare to move 40 trials, and the
one-time block adds ~$0.03/trial — the same cost disease as prompt-lever L1,
just smaller.

H2 learning: at cap=10000 the truncation condition fires only ~0.35×/trial on
the dev set (the 44%-of-chars figure came from full-suite traces; dev trials
that hit long outputs often time out). Cost did not drop and turns rose
slightly (15.8 vs 14.8); the model may re-read truncated content. Output
capping needs a far lower cap to bind (probe3 at cap=300 truncated 6× in one
trial and still passed) but that aggressiveness risks correctness — no graded
evidence of benefit at any tested cap.

H3 learning: maxTurns is not a free lunch when success correlates with turn
count — the long-turn trials are the passes, not the fails.

## 7.5 Promotion gate application — honest null

| Arm | (a) graded Δ≥+.05, p<.05 | (b) binary ≥24/40 | (c) guards 8/8 | (d) cost ≤$0.0967 | (e) reach ≥95% | Gate |
|---|---|---|---|---|---|---|
| H1 | Δ +0.0508 but p=0.4551 | 27/40 ✓ | ✓ | $0.1193 ✗ | ✓ | KILL |
| H2 | Δ −0.0483 ✗ | 22/40 ✗ | ✓ | +0.5% ✗ | ✓ | KILL |
| H3 | n/a | n/a | n/a | arm not run | n/a | REJECT |

**NO arm promoted. Phase 2 validation sweep (15 × k=8 × 2 arms) was NOT run.**
Combined with the Phase-0 regrade (X1 cost-KILL, X2/X3 noise, E-opt1 v2
REJECT, L1L2 REJECT), the campaign verdict is an **honest null**: no lever —
prompt-directive or deterministic SDK hook — cleared the pre-registered bar on
claude-haiku-4-5 on this dev set. **No gate relaxation.** What the evidence
says about lever classes on haiku-4.5: the prompt-directive class is exhausted
(5 arms, nulls; the one real signal, X1's verify-once, was too expensive to
deliver as always-on text), and the deterministic-hook class fires reliably
(mechanism proven end-to-end for Stop + PostToolUse) but its three natural
levers do not move this dev set — the failure modes are not where hooks can
reach cheaply, and the one structural cost lever (maxTurns) is defeated by the
correlation between long runs and success.

## 7.6 Loop v2 spend

- Phase 0 (graded upgrade, regrade, calibration): **$0.00** (API spend).
- H0 spike ~$0.10; H1 probe ~$0.18; H2 probes (2 aborted + probe3) ~$0.60;
  H1 arm $4.77; H2 arm $3.36 → **Phase-1 incremental ≈ $9.0**.
- Phase 2 validation: **not run** (~$28 saved by the honest null).
- Campaign cumulative API spend ≈ **$66–67 of the $150 cap** (~$58.3 visible
  trial-cost records across `eval/results/*.jsonl` + probes, plus the two
  documented invalid/untreated runs parked in loop v1: l1l2-arm-wrong-aborted
  ~$7.50 and l1l2-arm-untreated ~$6.62). Well under cap; no gate relaxation
  was ever needed for budget reasons.

## Deliverables added by loop v2

- `plans/plan.md` (loop-v2 plan), `eval/analysis/graded_score.py`,
  `eval/analysis/regrade_arms.py`, `eval/analysis/power_calibration.py`,
  `eval/analysis/test_cap_hook.mjs`
- `eval/results/graded/*.jsonl` (546 trials, 12 arms), `eval/results/dev-h1.jsonl`,
  `eval/results/dev-h2.jsonl`
- `eval/experiments/dev-loop/{ledger.md,regrade-report.md,h2-fix-provenance.md}`
- `ada/agent/claude/agent.ts` (adaHookOptions seam, env-gated OFF; md5
  `ea5225ea34917de672f9543e80dd3fa8`) mirrored to `eval/ada-runtime`
- `eval/ada-agent/ada_agent.py` (hook_spike/hook_verify_gate/hook_output_cap/
  hook_max_turns kwargs → env binding)
- Jobs: `h0-spike`, `h1-reach-probe`, `dev-h1`, `h2-reach-probe`,
  `h2-reach-probe2`, `h2-reach-probe3`, `dev-h2`

# Section 8 — X1r: verify-once repackage (trimmed + bounded + output-cap)

## 8.1 Rationale and design (pre-registered 2026-09-05, ledger.md)

X1 was the campaign's only statistically significant graded effect
(+0.122, Wilcoxon p=0.016) — killed on COST (1.386× = $0.1218/trial vs the
frozen $0.0967 gate), not on signal. X1r re-delivered the same verify-once
mechanism inside the gate by attacking the three zero-cost-trace-measured
cost drivers: (a) an ALREADY-EXECUTED EXEMPTION clause ("if you have ALREADY
run the deliverable during this session and observed it working, finish
immediately — do not re-verify") for redundant re-verification on already-
solving tasks (fix-code-vulnerability +15.7 turns, +$0.276, zero gain); (b) a
HARD RUN BUDGET ("at most 2 verification runs in total — fix once, re-run
once") for the regex-log fix-loop cascade (2→19 turns, +$0.608); (c) an
`ADA_HOOK_OUTPUT_CAP=3000` composition (46.3% of tool-result chars reclaimed
vs 25.7% at cap=10000) to cut the turn-driven cache-read re-feed. Driver (c)
of X1 (cancel-async-tasks 0/4, 2.8→9.0 turns) was pre-accepted as residual
waste. Delivery: env `ADA_VERIFY_ONCE_TRIMMED=1` via
`verifyOnceTrimmedGuidance()` in `lever-guidance.ts` wired into
`systemPromptAppend` in `index.ts`, kwargs-bound through `ada_agent.py`
(`verify_once_trimmed=1 hook_output_cap=3000`), md5 parity to
`eval/ada-runtime`, tsc clean, default OFF. Pre-registered projections:
cost $0.09–0.105 (TIGHT vs gate), graded Δ ≈ +0.095.

## 8.2 Reach probe (hard gate, ≤ $0.25)

Job `dev-x1r-probe` (fix-code-vulnerability, k=1): cost $0.1220665, reward
1.0. Bridge log markers: X1r directive marker `ALREADY run the deliverable`
(1 hit), `[hook:cap] PostToolUse` (31 hits), `truncated (cap 3000)` (3 hits)
→ directive and cap mechanism demonstrably fire before paid spend.

## 8.3 Dev arm (job dev-x1r, 40 trials)

10 dev tasks × k=4, 1h07m52s foreground, 1 AgentTimeoutError
(large-scale-text-editing). `eval/results/dev-x1r.jsonl` (40 records, 39
cost-bearing); graded 40/40 scored (0 excluded),
`eval/results/graded/dev-x1r.jsonl`. Result: **29/40 = 0.725**, Pass@2 0.900,
Pass@4 1.000.

## 8.4 Frozen gate application (vs fresh dev-baseline)

| Criterion | dev-baseline | dev-x1r | Pass? |
|---|---|---|---|
| (a) graded paired Δ ≥ +0.05 | 0.7842 | **0.8400** (Δ +0.0558) | PASS (magnitude) |
| (a) Wilcoxon two-sided p < 0.05 | — | **p = 0.3601** (stat 44.0) | **FAIL** |
| (b) binary ≥ 24/40 | 24/40 | **29/40** (Δ +0.125; McNemar p=0.3018) | PASS |
| (c) guards 8/8 | 8/8 | **7/8** — fix-code-vulnerability 4/4 → 3/4 | **FAIL** |
| (d) mean cost ≤ $0.0967 | $0.0879 (n=38) | **$0.1005 (n=39), ratio 1.144** | **FAIL** |
| (d-alt) 9-task excl. large-scale | $0.0794 (n=36) | $0.0891 (n=36), ratio 1.122 | FAIL (transparency) |
| (e) reach ≥ 95% | — | **40/40 = 100%** (marker); 716 [hook:cap] lines, 46 truncations, 13/40 trials | PASS |

## 8.5 VERDICT: KILL / NOT PROMOTED (honest null)

Three independent criteria fail: Wilcoxon p=0.3601 ≥ 0.05; guard loss
(fix-code-vulnerability 4/4→3/4 — the pre-registered "any guard loss" kill);
mean cost $0.1005 > $0.0967 under the suite cost-bearing convention AND the
9-task transparency convention. Binary +5 trials is directional but not
significant (McNemar p=0.3018). **Phase 2 validation (~$28) was NOT run.
Zero validation spend. No gate relaxation.**

Mechanism narrative: the exemption cut fix-code-vulnerability cost 0.74×
exactly as designed (X1's biggest waste pool) but cost one guard pass there
— an exemption that suppresses needed verification is a kill regardless of
dollars saved. The 2-run budget stopped regex-log's cascade (2.23× → 1.15×)
but forfeited X1's regex-log conversion (graded +0.25 lost). Cost improved
1.386× → 1.144× but did NOT clear 1.10×; graded effect halved +0.122
(p=0.016) → +0.0558 (p=0.3601): the turns that carry verify-once's graded
signal ARE its cost — trimming/bounding removed both waste AND repair.
cancel-async-tasks (2.09× cost, McNemar-weak) remains the cleanest
uncaptured pool; a conditional verify-only-when-runnable-artifact directive
WITHOUT a repair mandate is the untested successor hypothesis.

**Campaign verdict (now 9 closed lever arms): no lever — prompt-directive,
deterministic SDK hook, or repackaged composite — cleared the pre-registered
bar on claude-haiku-4-5 on this dev set.** X1's verify-once effect could not
be repackaged under the 1.10× cost cap. The pass rate is capability-bound,
not process-bound.

## 8.6 X1r spend

Probe $0.122 + arm 39 × $0.1005 ≈ $3.92 → **~$4.0**. Cumulative campaign
API spend ≈ **$70–71 of the $150 cap** (X1r is the final arm of the
campaign). Full record: `eval/experiments/dev-loop/decision-X1r.md`,
`eval/analysis/analyze_dev_x1r.py`.

## Deliverables added by the X1r repackage

- `ada/agent/lever-guidance.ts` + `ada/index.ts` (verifyOnceTrimmedGuidance,
  env-gated OFF; md5 parity to `eval/ada-runtime`)
- `eval/ada-agent/ada_agent.py` (verify_once_trimmed kwarg → env binding)
- `eval/results/dev-x1r.jsonl` + `eval/results/graded/dev-x1r.jsonl`
  (40 trials, graded 40/40, 0 excluded)
- `eval/analysis/analyze_dev_x1r.py`, `eval/analysis/graded_score.py`
  (dev-x1r added to ARM_TO_JOB)
- `eval/experiments/dev-loop/decision-X1r.md`, ledger X1r run-log row
- Jobs: `dev-x1r-probe`, `dev-x1r`
