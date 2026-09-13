# Dev-loop experiment ledger — Ada autoresearch

Arm shape: 10-task dev set × k=4 = 40 trials ≈ $4.50, ~1h05m, claude-haiku-4-5,
n_concurrent=2. All dev decisions are DIRECTIONAL (Wilson ±0.15 at n=40);
proof lives in the held-out validation sweep (15 × k=8), which only runs on
promotion.

## Dev set (fixed)
8 MIXED: cancel-async-tasks, fix-git, git-multibranch, large-scale-text-editing,
log-summary-date-ranges, openssl-selfsigned-cert, regex-log, sanitize-git-repo
2 ALL-PASS guards: fix-code-vulnerability, git-leak-recovery

Held out (validation only, never tuned against): vulnerable-secret,
configure-git-webserver, db-wal-recovery, filter-js-from-html, password-recovery

## Fresh dev baseline (job `dev-baseline`, Sep 3, untreated, gates OFF)
- **24/40 pass = 0.600** · mean cost $0.0879/trial (38 cost-bearing; 2
  AgentTimeoutError on large-scale-text-editing have no usage) · mean wall 150.5s
- Guards: fix-code-vulnerability 4/4, git-leak-recovery 4/4
- Per-task: cancel-async-tasks 0/4, fix-git 2/4, git-multibranch 3/4,
  large-scale-text-editing 2/4, log-summary-date-ranges 3/4,
  openssl-selfsigned-cert 3/4, regex-log 2/4, sanitize-git-repo 1/4,
  fix-code-vulnerability 4/4, git-leak-recovery 4/4
- Mining: 16 failing trials; 14 with ctrf near-miss data; **7/14 passed ≥50%
  of verifier tests**. cancel-async-tasks is the purest instance: 0/4 pass,
  4/4 fails ≥50% verifier tests, 3/4 trials = 1 Write + 2 turns (agent wrote
  run.py, narrated "Done!", never executed it). Baseline tool mix: Bash 394,
  Read 68, Write 27, Edit 27, Grep 8. Tool results 524 (16 >10k chars, 3.1%).
  Cache-read ratio mean 0.913.
- Stale Sep-2 arm B on this subset was 29/40 = 0.725 → measured drift −0.125
  confirms the fresh-baseline requirement. **All comparisons below are vs the
  FRESH dev-baseline only.**

## Statistical conventions
- Position-based pairing WITHIN task (trial order 0..3) for McNemar; the
  `trial` field is NOT comparable across arms.
- Cost pairing excludes a task when either arm has a timeout-with-no-usage
  trial (large-scale-text-editing: dev baseline has 2).
- scipy exists only under /root/optimize_ada/venv.
- Mean cost guard uses cost-bearing trials of the same task set (baseline
  $0.0879). Cost multipliers below apply to that mean.
- Baseline+2 / +4 arithmetic derives from the FRESH baseline 24/40 (the
  plan.md literal "≥33/40" was stale arm-B arithmetic; the +4 delta rule is
  fixed, so the promotion threshold is 24+4 = 28/40).

## Queue (re-ranked after X2, Sep 3)
| ID | Hypothesis | Mechanism targeted | Pre-registered kill criterion |
|---|---|---|---|
| X1 | verify-once (L1-lite) — **DONE: KILL** | Agent never executes its own deliverable; a SINGLE run-once/fix-once check. | cost guard $0.1011 breached at 1.386×; pass +6/40 directional (McNemar p=0.1094); NOT promoted |
| X2 | verify-against-criteria (X1-refined) — **DONE: NOT PROMOTED** | Criteria-targeted edge-case verification before finish; fix once, STOP on pass. Solved X1's cost blow-up (1.386× → 1.043×; task-mean 0.977×). | success-target miss (cancel-async-tasks 1/4 < 2/4) + suite delta McNemar p=0.424 in noise → conservative NOT PROMOTED despite literal gate met. X2 cost-control design INHERITED by future levers. |
| X3 | **effort-realism directive** (NEXT) | Exhaustive exploration / strategy-thrash on hard tasks (large-scale-text-editing 2 timeouts @1200s, sanitize-git-repo 1/4). Directive: prefer complete working minimal solution over exhaustive exploration; after ≤3 failed attempts on one approach, switch; no speculative reads; when verifying, do it cheaply against the stated criteria (X2 inherited). | dev pass < 24/40 (baseline) OR mean cost > 1.05 × $0.0879 = **$0.0923**; success targets: large-scale-text-editing ≥ 3/4 AND sanitize-git-repo ≥ 2/4; litmus watch: cancel-async-tasks (record; regression to 0/4 triggers review — X3's thrash mechanism is orthogonal to cancel-async-tasks' never-runs mechanism, so not binding) |
| X4+ | from mining (conditional cheap-verify) | Only if a future verify candidate also fails cost: trigger verification ONLY on ex-ante signs of near-miss (code-artifact task + few turns so far), not unconditionally. | TBD when registered |

## Promotion gate (pre-registered, X1 onward)
Promote iff (a) dev pass ≥ baseline + 4 = **28/40**,
(b) both ALL-PASS guards 4/4,
(c) mean cost ≤ 1.10 × $0.0879 = **$0.0967**,
(d) trace evidence the mechanism engaged (marker in bridge logs + behavior
    change in tool/turn profile vs baseline).

## Validation sweep ACCEPT rule (pre-registered, only on promotion)
15 tasks × k=8 × 2 arms (candidate + fresh untreated baseline drift control).
ACCEPT iff (a) suite pass delta ≥ +0.08 vs fresh baseline arm AND position-
based McNemar one-sided p < 0.05, (b) all three ALL-PASS guards (fix-code-
vulnerability, git-leak-recovery, vulnerable-secret) ≥ 7/8, (c) mean cost
≤ 1.10 × baseline arm, (d) treatment reach ≥ 95% of bridge logs.

## Multiple-comparisons guard
Dev loop screens many candidates; only the promoted one gets ONE validation
test, rule fixed in advance. No re-validation with relaxed rules after a fail.
If the queue exhausts with no promotion, that IS a result — report the null
campaign honestly; do not relax the gate.

## Run log
| Date | Job | Arm | Pass | Mean cost $ | Notes |
|---|---|---|---|---|---|
| Sep 3 | dev-baseline | untreated | 24/40 (0.600) | 0.0879 | 2 AgentTimeoutError (large-scale-text-editing) |
| Sep 3 | dev-x1 | verify-once | 30/40 (0.750) | 0.1218 | KILL (cost 1.386× > guard $0.1011); McNemar p=0.1094; guards 8/8; reach 40/40 |
| Sep 3 | dev-x2 | verify-against-criteria | 28/40 (0.700) | 0.0917 | NOT PROMOTED (success-target miss cancel-async-tasks 1/4<2/4 + McNemar p=0.424 in noise); literal gate met, conservative adjudication; cost 1.043× / task-mean 0.977×; reach 40/40; decision-X2.md |
## Phase 0 (loop v2): graded metric upgrade — COMPLETE, zero API spend

**Graded scorer**: `eval/analysis/graded_score.py` re-scored all 466 trials from
`verifier/ctrf.json` per-test results into `eval/results/graded/*.jsonl`
(0 excluded; graded in [0,1]; 1-test tasks graded == binary exactly).
Graded = verifier tests passed / total. 32/42 TB2 tasks carry >1 test.

**Re-analysis** (`eval/analysis/regrade_arms.py` → `regrade-report.md`):

| arm | graded delta | Wilcoxon p | binary delta | McNemar p | shift |
|---|---|---|---|---|---|
| dev-x1 | +0.122 | **0.0160** | +0.150 | 0.1094 | graded SIG, binary NS |
| dev-x2 | +0.046 | 0.5898 | +0.100 | 0.4240 | both NS |
| dev-x3 | +0.062 | 0.3613 | +0.100 | 0.3438 | both NS |
| e-opt1-arm | −0.083 | 0.0982 | −0.050 | 0.6291 | both NS |
| e-opt1-arm-v2 | −0.067 | 0.1050 | −0.067 | 0.3438 | both NS |
| l1l2-arm | −0.014 | 0.7247 | −0.017 | 1.0000 | both NS |

**Answer to the pre-registered question: X2/X3 are NOT resurrected.** Their
+0.100 binary deltas were noise, not underpowered real effects — under the
higher-resolution graded metric they shrink to +0.046/+0.062 with p=0.59/0.36.
The underpowered-metric hypothesis is REFUTED for X2/X3. The one lever the
graded metric does rescue is **X1 (verify-once): graded +0.122, p=0.016** —
a real effect that was killed on COST (1.386×), not on signal. Its mechanism
(verification before finish) is confirmed twice now; only its delivery
(always-on prompt text) was too expensive. This directly motivates H1.

**Power calibration** (`eval/analysis/power_calibration.py`, dev-baseline n=40):
- Bootstrap 95% CI of graded mean at n=40: half-width ±0.105
- Null paired-delta 95% band at n=40: [−0.145, +0.147]; MDE ≈ 0.146 (unpaired)
- At n=120 (validation): band [−0.085, +0.084]; MDE ≈ 0.084
- Paired within-task Wilcoxon is the powerful test: it detected X1's +0.122 at
  p=0.016 where binary McNemar gave p=0.109 on the same trials.

## GRADED PROMOTION GATE (pre-registered BEFORE any Phase 1 paid run)

A hook arm is PROMOTED to validation iff ALL of:
  (a) paired graded delta ≥ **+0.05** vs fresh dev-baseline AND
      Wilcoxon signed-rank (two-sided) p < **0.05** on paired graded scores;
  (b) binary pass ≥ 24/40 (no binary regression below baseline);
  (c) both ALL-PASS guards 8/8 binary (fix-code-vulnerability, git-leak-recovery);
  (d) mean cost ≤ 1.10 × $0.0879 = **$0.0967** (cost-bearing, same task set);
  (e) treatment reach ≥ 95% (hook-fired marker in bridge logs).

Kill criterion for every hook arm (pre-registered): ANY of
graded delta < +0.05, Wilcoxon p ≥ 0.05, binary < 24/40, any guard loss,
mean cost > $0.0967, reach < 95%.

Validation sweep ACCEPT rule is UNCHANGED and remains binary-primary:
suite binary delta ≥ +0.08, position-based McNemar one-sided p < 0.05,
guards ≥ 7/8, cost ≤ 1.10× baseline arm, reach ≥ 95%. Graded is the dev-loop
instrument only; the final verdict is in the benchmark's own metric.

## Phase 1 queue (new mechanism class: deterministic SDK hooks)

| ID | Hypothesis | Mechanism | Pre-registered kill |
|---|---|---|---|
| H0 | Hook seam spike (≤$1) | env-gated no-op PostToolUse logging hook in ada/agent/claude/agent.ts; must fire end-to-end | HARD GATE: no hook-fired marker in probe logs → STOP Phase 1, report |
| H1 | Stop-hook verification gate | On Stop event, if no execution-class tool call since last file write, block stop ONCE ("run your solution against real input before finishing"). Deterministic L1-mechanism, ~0 prompt tokens. X1 graded p=0.016 motivates this. | gate above (a)–(e); kill on any miss |
| H2 | PostToolUse output capping | Truncate tool results >10k chars (head+tail + elision marker). Targets measured 22 results >10k chars = 44% of tool-result chars. | mean cost not ≥10% BELOW dev-baseline OR graded drop > 1 noise band (−0.105) OR any guard binary loss |
| H3 | maxTurns cap (only if budget remains) | Hard turn cap from measured turn distribution; targets thrash (large-scale-text-editing timeouts) without prompt tokens. | gate (a)–(e); kill on any miss |

If hooks fire but H1–H3 all return null: that IS the campaign answer. No gate
relaxation, no re-sampling the exhausted prompt-directive class.

## H0 — hook seam spike (COMPLETE, 2025-09-04)

- Seam: env-gated `adaHookOptions()` in `ada/agent/claude/agent.ts` (mirrored to
  eval/ada-runtime, md5 parity verified). Gates: ADA_HOOK_SPIKE (H0),
  ADA_HOOK_VERIFY_GATE (H1), ADA_HOOK_OUTPUT_CAP (H2), ADA_HOOK_MAX_TURNS (H3).
  Plumbed via AdaBridgeAgent kwargs hook_spike/hook_verify_gate/hook_output_cap/
  hook_max_turns → _bridge_env(); zero-cost binding test PASSED (spike arm sets
  ADA_HOOK_SPIKE=1, default arm clean). tsc: 0 errors in agent.ts.
- Probe: `harbor run ... --ak hook_spike=1 --ak lever_debug=1 -i regex-log -k 1 -n 1`,
  job h0-spike, 1 trial, 0 exceptions, ~$0.09.
- **HARD GATE PASSED**: `regex-log__XBCFTFM/agent/ada-bridge.log:150:
  "[hook:spike] PostToolUse Write fired"` — hooks fire end-to-end through the
  astropods adapter passthrough. The seam correction is confirmed empirically.
- Note: harbor agent import requires PYTHONPATH=/root/optimize_ada (namespace
  package `eval`); recorded for all future runs.
- Post-spike seam addition: H1 Stop hook now logs EVERY Stop event
  (`[hook:gate] Stop fired (writeSeq=…, bashSeq=…, alreadyBlocked=…)`) so arm
  reach is provable even when the block condition never triggers.

## H1 — Stop-hook verification gate: reach probe (PASSED, 2025-09-04)

- Probe: job h1-reach-probe, regex-log, 1 trial, 0 exceptions, ~$0.09,
  `--ak hook_verify_gate=1 --ak lever_debug=1`.
- Evidence (ada-bridge.log): line 213 `[hook:gate] Stop fired (writeSeq=1,
  bashSeq=0, alreadyBlocked=false)` → line 214 `[hook:gate] Stop blocked once:
  no execution-class tool call since last write` → line 278 `[hook:gate] Stop
  fired (writeSeq=2, bashSeq=4, alreadyBlocked=true)` (agent then executed via
  Bash and stopped cleanly). Mechanism confirmed end-to-end: block fires exactly
  once, re-entrancy latch respected.
- H1 40-trial dev arm launched (job dev-h1): 10 dev tasks x k=4, --ak
  hook_verify_gate=1. Pre-registered kill (from gate table above): graded
  paired delta < +0.05 or Wilcoxon p >= 0.05, binary < 24/40, guards < 8/8,
  mean cost > $0.0967, reach < 95%.

## H1 — Stop-hook verification gate: 40-trial dev arm (KILLED, 2025-09-04)

- Run: job dev-h1, 10 dev tasks x k=4 = 40 trials, 0 exceptions, wall 52m40s,
  mean cost **$0.1193**/trial (vs dev-baseline $0.0879).
- Reach: Stop hook fired in **40/40** trials (100%); block triggered in
  **9/40** (22.5%) — the gate condition (write w/o subsequent execution) is
  rare on haiku-4.5, which usually runs its code anyway.
- Results vs dev-baseline (paired, position-based):
  - Graded: 0.8350 vs 0.7842, paired delta **+0.0508** [CI -0.0875, +0.1858],
    Wilcoxon p=**0.4551**
  - Binary: 27/40 vs 24/40, delta +0.075, McNemar p=0.5811
  - Guards: fix-code-vulnerability 4/4, git-leak-recovery 4/4 (8/8 OK)
- **VERDICT: KILL per pre-registered gate.** Graded delta nominally meets
  +0.05 but p=0.4551 >> 0.05 (well inside the ±0.105 noise band), and mean
  cost $0.1193 breaches the $0.0967 (1.10x) cap. Two independent criteria fail.
- Learning: the deterministic Stop gate works mechanically (probe + 9 blocks)
  but (a) the unexecuted-write condition is too rare to move 40 trials, and
  (b) the one-time block + forced continuation adds ~$0.03/trial — the same
  cost disease as prompt-lever L1, just smaller. X1's +0.122 graded effect came
  from the *prompt* telling the model to verify; the hook only catches the
  rare case where the model forgot, and that case is not where the misses are.

## H2 — PostToolUse output capping: root-cause fix + reach probe (PASSED, 2025-09-04)

- Root cause of the two failed probes (h2-reach-probe, h2-reach-probe2): the cap
  hook guarded `typeof tool_response === "string"`, but the SDK types
  tool_response as `unknown` and Bash/Read/Write responses are OBJECTS
  ({stdout,stderr,...}, {type,file}, {type,filePath,content,...}) — the guard
  never matched, silent no-op. Secondary: hook only logged on truncation, so
  reach was unprovable. Fix: shape-aware `capToolResponse()` (string / object
  string-fields / content-block array, head 60% + tail 25% + elision marker,
  same shape returned via updatedToolOutput) + per-fire reach log. Unit test
  eval/analysis/test_cap_hook.mjs: 13/13 PASS. Provenance:
  eval/experiments/dev-loop/h2-fix-provenance.md.
- Probe: job h2-reach-probe3, large-scale-text-editing, cap=300, 1 trial,
  0 exceptions, reward 1.0, cost $0.2567 (slightly over the $0.25 probe line,
  recorded honestly). Evidence
  (large-scale-text-editing__ahbEBTF/agent/ada-bridge.log): **27 fired lines +
  6 actual truncations** — mechanism confirmed end-to-end. Note the trial still
  passed at cap=300 (aggressive truncation did not break it).

## H2 — 40-trial dev arm: PRE-REGISTERED kill criterion (2025-09-04, BEFORE run)

- Run: job dev-h2, 10 dev tasks x k=4 = 40 trials, --ak hook_output_cap=10000
  (truncate >10k chars, head+tail + elision marker), --ak lever_debug=1.
- Baseline: dev-baseline (graded 0.7842, binary 24/40, mean cost $0.0879).
- **KILL if ANY of**: (a) mean cost NOT >=10% below dev-baseline (i.e. mean
  cost > $0.0791); (b) paired graded delta < -0.105 (one noise band below
  baseline); (c) any guard task (fix-code-vulnerability, git-leak-recovery)
  loses a binary pass vs 4/4; (d) reach < 95% of trials showing hook fired.
- PROMOTE only if: graded paired delta >= +0.05 with Wilcoxon p < 0.05 AND
  binary >= 28/40 AND guards 8/8 AND mean cost <= $0.0967 AND reach >= 95%
  (frozen Phase-0 gate).

## H2 — PostToolUse output capping: 40-trial dev arm (KILLED, 2025-09-04)

- Run: job dev-h2, 10 dev tasks x k=4 = 40 trials, 2 timeouts, wall 1h14m,
  cap=10000 confirmed in config.json kwargs.
- Reach: [hook:cap] fired in 40/40 trials (609 fired lines), 14 actual
  truncation events across the arm (~0.35/trial) — mechanism fires, but the
  >10k-char condition is dilute on this dev set at cap=10000.
- Results vs dev-baseline (paired, position-based):
  - Graded: 0.7358 vs 0.7842, paired delta **-0.0483** [p=0.5627], inside the
    ±0.105 noise band (no significant drop, no gain)
  - Binary: 22/40 vs 24/40, delta -0.050, McNemar p=0.8036
  - Guards: fix-code-vulnerability 4/4, git-leak-recovery 4/4 (8/8 OK)
  - Cost: mean $0.0883 (38 cost-bearing) vs baseline $0.0879 → **+0.5%**, NOT
    >=10% below baseline (kill threshold $0.0791)
  - Turns: mean 15.8 vs 14.8 (slightly UP)
- **VERDICT: KILL per pre-registered criterion (a): mean cost not >=10% below
  dev-baseline.** Cost is +0.5% (target was >=10% reduction), and graded/binary
  are flat-to-slightly-down. The hypothesis (truncating >10k-char tool results
  cuts context cost) is not supported: (1) at cap=10000 the truncation
  condition fires only ~0.35x/trial on the dev set — too dilute to move cost;
  (2) the +0.5% cost drift and turn increase suggest the model may re-read or
  re-derive truncated content.
- Learning: the earlier [measured] "22 results >10k chars = 44% of tool-result
  chars" came from full-suite baseline traces; on the 10-task dev set the long
  outputs are rarer and/or the trials that hit them already time out (2
  AgentTimeoutError). Output capping as a cost lever needs a much lower cap to
  bind (probe3 at cap=300 fired 6 truncations in ONE trial and still passed),
  but that aggressiveness risks correctness — no graded evidence of benefit at
  any tested cap, so the lever is parked. The shape-aware capToolResponse fix
  remains in the codebase (env-gated OFF) as a working seam.

## H3 — maxTurns cap: PRE-RUN STRUCTURAL REJECTION (2025-09-04, no paid spend)

- Planned mechanism: hard maxTurns cap on the agentic loop (env-gated
  ADA_HOOK_MAX_TURNS, plumbing verified in ada_agent.py hook_max_turns kwarg →
  _bridge_env, and in agent.ts adaHookOptions which sets options.maxTurns).
- **Rejected BEFORE any paid run** (E3 precedent: cheap rejection with trace
  evidence). Measured dev-baseline turn distribution (n=40, position-based):
  - PASSING trials (n=24): mean 17.1 turns, p90 36, **max 39**
  - FAILING trials (n=14): mean 10.8, p90 24, max 30
  - Guard task fix-code-vulnerability passes at 10/29/36/39 turns (4/4);
    large-scale-text-editing passes at 18/37; git-multibranch passes at 23/26/39.
  - Cap impact matrix: cap=30 would truncate 4 passing / 0 failing baseline
    trials (guaranteed guard regression + graded loss); cap=39 is a near-no-op
    (baseline max is 39; only 2 passing trials exceed 38).
- Conclusion: **NO admissible maxTurns cap exists on this dev set.** The
  failing/thrash tail (≤30 turns) is inseparable from the guard/long-pass tail
  (up to 39 turns). Any cap that binds thrash also cuts the guard tasks that
  must stay 8/8; any cap ≥39 changes nothing. maxTurns cannot win here — the
  hypothesis (hard turn budget cuts thrash cost without hurting correctness)
  is structurally unsupported by the measured turn distribution, independent
  of implementation.
- Cost avoided: ~$4.5 (a 40-trial arm was not run).
- Learning: maxTurns is not a free lunch when task success correlates with
  turn count. On haiku-4.5 with these tasks, the long-turn trials are the
  passes, not the fails — a cap would be a correctness tax, not a thrash
  brake. Combined with H1 (stop gate: +$0.03/trial, no signal) and H2
  (output cap: no cost reduction), the deterministic-hook class did not find
  a lever on the dev set.

## Promotion gate application (2025-09-04, all Phase-1 hook arms)

Frozen GRADED PROMOTION GATE (pre-registered before any Phase-1 paid run):
(a) paired graded delta >= +0.05 AND Wilcoxon p < 0.05; (b) binary >= 24/40;
(c) guards 8/8; (d) mean cost <= $0.0967; (e) reach >= 95%.

| Arm | Graded delta (p) | Binary | Guards | Cost | Reach | Gate |
|---|---|---|---|---|---|---|
| H1 Stop gate | +0.0508 (p=0.4551) | 27/40 | 8/8 | $0.1193 (FAIL d) | 100% | **KILL** |
| H2 output cap | -0.0483 (p=0.5627) | 22/40 | 8/8 | $0.0883 (+0.5%, FAIL a-kill) | 100% | **KILL** |
| H3 maxTurns | — (no admissible cap, pre-run rejection) | — | — | $0 (arm not run) | — | **REJECT** |

**NO arm promoted.** Phase 2 validation sweep (15 tasks x k=8 x 2 arms, ~$28)
**MUST NOT run** per the frozen gate and the multiple-comparisons guard.

## X1r — verify-once repackage (trimmed + bounded + output-cap composition): PRE-REGISTERED (2026-09-05, BEFORE any paid run)

**Motivation.** X1 is the campaign's only statistically significant graded
effect (+0.122, Wilcoxon p=0.016, regrade-report.md) — killed on COST (1.386x
= $0.1218/trial vs $0.0967 gate), not on signal. This arm re-delivers the
same mechanism within the frozen gate.

**Zero-cost trace diagnosis (dev-x1 vs dev-baseline, no API spend).**
Extra spend decomposition (4-trial totals, X1 $4.75 vs baseline $3.34):
- (a) Redundant re-verification on already-solved tasks: fix-code-vulnerability
  +$0.276 (turns 28.5→44.2, ZERO pass gain — agent re-ran verification after
  already executing the fix), git-leak-recovery +$0.019 (0 gain), openssl
  +$0.084 (3/4→3/4). Largest waste pool.
- (b) Fix-loop cascade: regex-log +$0.608 (turns 2→19, output 76k→129k tok,
  only +1 pass).
- (c) Unconvertible verification: cancel-async-tasks +$0.099 (0/4→0/4 —
  running cannot fix a wrong concurrency model).
- The WINS were cheap: fix-git +$0.047 (+2), log-summary +$0.023 (+1),
  sanitize +$0.037 (+1); large-scale-text-editing net −$0.126.
- Cost mechanics: TURN-DRIVEN cache-read re-feed (input 1.56x, cache-read
  ratio 0.913→0.959; extra ≈ +$0.77 cache-read +$0.50 output −$0.31 fresh
  input). The directive text itself is cached — trimming text is NOT a cost
  lever; bounding TURNS is.
- Output-cap threshold: cap=3000 reclaims 46.3% of tool-result chars in
  x1-shaped traces (6.0% of results over) vs 25.7% at cap=10000 — explains
  H2@10k cost-neutrality. Post-write Bash calls: 324 (x1) vs 143 (baseline).

**Design (X1r = trimmed verify-once + 2 bounds + cap composition).**
1. ALREADY-EXECUTED EXEMPTION: "if you have ALREADY run the deliverable
   during this session and observed it working, finish immediately — do not
   re-verify" → kills driver (a).
2. HARD RUN BUDGET: "at most 2 verification runs in total — fix once, re-run
   once, then finish on evidence either way" → kills driver (b).
3. Composition: ADA_HOOK_OUTPUT_CAP=3000 via the proven H2 hook seam
   (shape-aware capToolResponse, 13/13 unit tests) → cuts turn-driven
   context re-feed. Verification outputs are small, so capping should not
   blind the fix loop.
Driver (c) accepted as residual waste: no ex-ante signal separates
cancel-async-tasks from fix-git without task-name selection bias.
Delivery: env ADA_VERIFY_ONCE_TRIMMED=1 (verifyOnceTrimmedGuidance in
lever-guidance.ts, wired in index.ts) + kwarg verify_once_trimmed in
ada_agent.py; binding test PASSED (candidate arm sets
ADA_VERIFY_ONCE_TRIMMED=1 + ADA_HOOK_OUTPUT_CAP=3000; default arm clean);
md5 parity verified; tsc clean in edited files.

**Projections (pre-registered).** Cost: $0.1218 − ~$0.007/trial (guard
exemption) − ~$0.007/trial (regex-log cascade bound) − ~$0.005–0.015/trial
(cap re-feed) ≈ **$0.09–0.105** vs gate $0.0967 — TIGHT, honest risk of
missing. Graded: even if regex-log's +0.25 graded conversion is lost to the
harder bound, projected delta ≈ **+0.095** ≥ +0.05 gate.

**KILL criteria (frozen, any one kills):** graded paired delta < +0.05 OR
Wilcoxon p ≥ 0.05 OR binary < 24/40 OR any guard loss (fix-code-
vulnerability, git-leak-recovery < 8/8) OR mean cost > $0.0967/trial OR
reach < 95% (directive marker in bridge logs).

**PROMOTE only if ALL:** graded delta ≥ +0.05 AND Wilcoxon p < 0.05 AND
binary ≥ 24/40 AND guards 8/8 AND mean cost ≤ $0.0967 AND reach ≥ 95%
(frozen Phase-0 gate, unchanged).

**Run plan:** ≤$0.25 reach probe on fix-code-vulnerability (21 results
>3000 chars in baseline traces — exercises BOTH the directive marker and
[hook:cap] firing) — HARD GATE before paid arm; then job dev-x1r, 10 tasks
x k=4, --ak verify_once_trimmed=1 hook_output_cap=3000 lever_debug=1,
export eval/results/dev-x1r.jsonl. Validation sweep ONLY on promotion.
Combined with the Phase-0 regrade of prior arms (X1 cost-KILL, X2/X3 noise,
E-opt1 v2 REJECT, L1L2 REJECT), the campaign verdict is an **honest null**:
no lever — prompt-directive or deterministic SDK hook — cleared the
pre-registered bar on claude-haiku-4-5 at this dev set. No gate relaxation.

## X1r run log (dev-x1r, 2026-09-05) — NOT PROMOTED (honest null)

**Probe (hard gate):** dev-x1r-probe, fix-code-vulnerability, k=1, cost
$0.1220665 ≤ $0.25, reward 1.0. Bridge log: X1r marker `ALREADY run the
deliverable` (1 hit), `[hook:cap] PostToolUse` 31 hits, `truncated (cap
3000)` 3 hits → directive + cap mechanism demonstrably fire. Job dir:
eval/jobs/dev-x1r-probe/ (config + 1 trial + result.json).

**Arm:** dev-x1r, 10 tasks x k=4 = 40 trials, 1h07m52s foreground, 1
AgentTimeoutError (large-scale-text-editing). Exported
eval/results/dev-x1r.jsonl (40 records, 39 cost-bearing); graded 40/40
scored (0 excluded), eval/results/graded/dev-x1r.jsonl.
Analysis: eval/analysis/analyze_dev_x1r.py (+ dev-x1r added to
graded_score.py ARM_TO_JOB).

**Gate application (frozen, vs dev-baseline graded 0.7842 / binary 24/40 /
cost $0.0879):**

| Criterion | Value | Pass? |
|---|---|---|
| (a) graded paired Δ ≥ +0.05 | **+0.0558** (0.7842 → 0.8400) | PASS (magnitude) |
| (a) Wilcoxon two-sided p < 0.05 | **p = 0.3601** (stat 44.0) | **FAIL** |
| (b) binary ≥ 24/40 | **29/40** (Δ +0.125) | PASS |
| (c) guards 8/8 | **7/8** — fix-code-vulnerability 4/4 → 3/4 | **FAIL** |
| (d) mean cost ≤ $0.0967 | **$0.1005 (n=39), ratio 1.144** | **FAIL** |
| (d-alt) 9-task excl. large-scale | $0.0891 vs 1.10×$0.0794=$0.0873 | FAIL (transparency) |
| (e) reach ≥ 95% | **40/40 = 100%** (marker); 716 [hook:cap] lines, 46 truncations at cap=3000 (13/40 trials) | PASS |

**VERDICT: KILL / NOT PROMOTED** on three independent criteria (Wilcoxon
p=0.3601 ≥ 0.05; guard loss fix-code-vulnerability 4/4→3/4 = pre-registered
"any guard loss" kill; cost $0.1005 > $0.0967 under the suite cost-bearing
convention AND the 9-task transparency convention). Binary +5 trials
(McNemar p=0.3018 NS), reach 100%. **Phase 2 validation (~$28) MUST NOT
run. Zero validation spend. No gate relaxation.** Full record:
eval/experiments/dev-loop/decision-X1r.md.

**X1r learning:**
1. Text-trim + output-cap did NOT make verify-once cheap enough: cost
   1.386× → 1.144× (improved, still > 1.10× gate). The turns that carry the
   graded signal ARE the cost — trimming/bounding removed both waste AND
   repair, halving the graded effect (+0.122 p=0.016 → +0.0558 p=0.3601).
2. The exemption clause worked exactly as designed on its target
   (fix-code-vulnerability cost 0.74×, X1's biggest waste pool) but cost one
   guard pass (4/4 → 3/4) — an exemption that suppresses needed verification
   is a kill regardless of dollars saved.
3. The 2-run budget stopped regex-log's cascade (2.23× → 1.15× cost) but
   also forfeited X1's regex-log conversion (+1 pass, graded +0.25) — bounding
   iteration bounds repair too.
4. cancel-async-tasks remains the cleanest uncaptured pool (2.09× cost,
   graded 0.833→0.917 but McNemar-weak): a conditional verify-only-when-
   runnable-artifact directive WITHOUT a repair mandate is the untested
   successor hypothesis.
5. Campaign verdict (now 9 closed arms incl. X1r): no lever on
   claude-haiku-4-5 clears the pre-registered bar. Pass rate is
   capability-bound, not process-bound.

Spend: probe ~$0.122 + arm 39 × $0.1005 ≈ $3.92 → X1r ≈ $4.0. Cumulative
campaign ≈ $70–71 of $150 cap.
