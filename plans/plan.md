# Ada Autoresearch Loop v2 — Measurement Upgrade + New Mechanism Class

## Goal

Restart the hill-climb with (a) a higher-resolution metric that costs nothing and re-scores all
466 existing trials retroactively, and (b) a genuinely different lever class — deterministic SDK
hooks instead of prompt directives — then validate any promoted advancement on the binary
benchmark metric at k=8.

## Why the loop stalled (diagnosis, measured)

Five experiments, five nulls: E-opt1 (0.483 vs 0.550), L1+L2 (0.533, cost guard breach),
X1 (KILL), X2 (28/40 vs 24/40, p=0.424), X3 (28/40 vs 24/40, cost 1.317×).

Two systematic faults, not five unlucky ideas:

1. **Metric resolution.** Binary pass/fail throws away the graded signal the verifiers already
   emit. **[measured]** 32 of 42 TB2 tasks have >1 verifier test; dev-set counts: cancel-async-tasks 6,
   openssl-selfsigned-cert 6, fix-code-vulnerability 6, git-leak-recovery 5,
   large-scale-text-editing 5, sanitize-git-repo 3, fix-git 2, log-summary-date-ranges 2,
   git-multibranch 1, regex-log 1. A 5/7→6/7 improvement currently scores as zero. With
   ±0.126 binary noise at k=4, real effects of the size we keep seeing (+0.100) are
   undetectable by construction.
2. **Mechanism monoculture.** All five levers were prompt-directive nudges: probabilistic
   (model may ignore) and token-costly (L1 turns 20.3→23.6 blew the cost guard; X3 hit 1.317×).
   The class has now been sampled to exhaustion with consistent nulls.

**Seam correction [measured]:** the earlier "no mid-loop seam without forking
@astropods/adapter-claude-agent-sdk" finding is WRONG. `@anthropic-ai/claude-agent-sdk` 0.3.193
(vendored under the adapter) declares `hooks?: Partial<Record<HookEvent, HookCallbackMatcher[]>>`
and `maxTurns?: number`; `HOOK_EVENTS` includes PreToolUse, PostToolUse, PostToolUseFailure,
Stop, SubagentStop. The adapter is a thin passthrough (`export const query = patched.query`),
and `ada/agent/claude/agent.ts` composes the options object directly (~line 169, alongside
`systemPromptAppend`). Hooks are reachable with a local edit — no fork.

## Approach

**Phase 0 — measurement upgrade (zero API spend, highest value first).** Extract per-test
results from every `verifier/ctrf.json`, define the graded score, re-score all 466 completed
trials, and re-run paired stats on every prior arm. This may resurrect a killed lever for free
and calibrates how much power the graded metric actually buys.

**Phase 1 — new mechanism class: deterministic SDK hooks.** Prompt nudges request behavior;
hooks enforce it at zero token cost. Each hook lever is env-gated (default OFF), reach-probed,
then run as a 40-trial dev arm scored on the graded metric.

**Phase 2 — validation.** Promote on graded evidence, confirm on the **binary** benchmark metric
at k=8 (graded is our instrument; binary is the benchmark's definition of success — the final
verdict must be in the benchmark's own terms).

**Explore/exploit discipline.** Phase 0 exploits existing data. Phase 1 explores a new class.
If two hook levers both show graded signal, one combined arm is allowed. If the hook class also
returns null across 3 arms, that is a real finding — report the null and stop, do not re-sample
the prompt class hoping for a different outcome.

## Subtasks

1. **Graded scorer + retroactive re-scoring (no API spend).**
   Build `eval/analysis/graded_score.py`: for each trial, parse `verifier/ctrf.json` →
   `tests_passed / tests_total` (binary `pass` retained alongside). Handle 1-test tasks
   (graded == binary) and missing/malformed ctrf (exclude, log). Emit
   `eval/results/graded/<arm>.jsonl` for all arms: baseline-armA/B, dev-baseline, dev-x1/x2/x3,
   e-opt1-arm-v2, l1l2-arm. Verify: per-arm record counts match the source JSONLs; graded score
   ∈ [0,1]; for 1-test tasks graded == binary exactly.
2. **Re-analysis of all prior experiments on the graded metric (no API spend).**
   `eval/analysis/regrade_arms.py`: for each prior arm vs its correct baseline, compute mean
   graded score ± bootstrap 95% CI, paired per-task graded deltas (position-based within task),
   Wilcoxon signed-rank on paired graded scores, and the binary result side by side.
   Deliverable `eval/experiments/dev-loop/regrade-report.md`. Explicit question to answer:
   **do X2/X3 (+0.100 binary, p≈0.34–0.42) show a significant graded effect?**
   Verify: every prior arm appears with both metrics; any metric disagreement is called out.
3. **Power calibration (no API spend).** From the graded re-scoring, estimate the graded-metric
   noise band at n=40 (bootstrap/permutation over dev-baseline) and state the minimum detectable
   effect for k=4 dev arms and k=8 validation. Write the resulting **graded promotion gate** into
   the ledger BEFORE Phase 1 runs. Verify: gate is numeric and pre-registered in
   `eval/experiments/dev-loop/ledger.md`.
4. **Hook seam spike (≤$1).** In `ada/agent/claude/agent.ts`, add an env-gated `hooks` block to
   the options object (default OFF, mirroring the `systemPromptAppend` pattern) with a no-op
   PostToolUse hook that only logs. Confirm the hook actually fires end-to-end in a 1–2 trial
   probe (marker in bridge logs). **HARD GATE: if hooks do not fire, stop Phase 1 and report —
   do not proceed to paid hook arms.** Verify: hook-fired marker present in probe logs; md5
   parity `ada/agent/` ↔ `eval/ada-runtime/ada/agent/`.
5. **H1 — Stop-hook verification gate (deterministic L1).** On the `Stop` event, if no
   execution-class tool call (Bash running the produced artifact) occurred since the last file
   write, block the stop once with a short reason ("run your solution against real input before
   finishing"). Deterministic, fires at most once, ~0 added prompt tokens.
   Pre-registered kill: graded delta < the Phase-3 gate OR mean cost > 1.10× dev-baseline
   ($0.0879 → $0.0967) OR guards below 8/8 binary.
   Rationale: L1's mechanism was confirmed (44 near-miss trials) but its *delivery* (always-on
   prompt text + iterative fix mandate) cost 3.3 turns/trial. A hook fires only when needed.
6. **H2 — PostToolUse output capping (the original E2, now feasible).** Truncate tool results
   above a threshold (head+tail with an elision marker), targeting the **[measured]** 22 results
   >10k chars = 44% of all tool-result characters. Threshold chosen on the dev set only.
   Pre-registered kill: mean cost not ≥10% below dev-baseline OR graded score drops below
   baseline − 1 noise band OR any guard task loses a binary pass.
7. **H3 — turn/effort budget via `maxTurns` (only if H1/H2 leave budget).** Hard cap informed by
   the measured turn distribution; targets the thrash tasks without prompt tokens.
   Pre-registered kill: graded delta < gate OR any guard regression.
8. **Validation sweep (only on promotion).** 15 tasks × k=8 = 120 trials × 2 arms (promoted
   candidate + fresh untreated baseline for drift control), ≈$28. **Primary verdict on the
   binary metric** (benchmark's own definition): pass delta ≥ +0.08 with position-based McNemar
   one-sided p < 0.05; graded delta reported as the secondary/supporting result. Guards ≥7/8,
   cost ≤1.10× baseline arm, reach ≥95%. Write
   `eval/experiments/dev-loop/validation-decision.json`.
9. **Final report.** Update `eval/campaign-report.md`: the metric-resolution finding, the seam
   correction, the full ledger (all experiments incl. nulls with their learnings), validation
   verdict, spend. If Phase 1 also returns null, report the null campaign honestly and state
   what the evidence says about prompt-vs-hook lever classes on haiku-4.5.

## Deliverables

| Path | Description |
|---|---|
| `eval/analysis/graded_score.py` | ctrf → graded score extractor |
| `eval/results/graded/*.jsonl` | All 466 trials re-scored, both metrics |
| `eval/analysis/regrade_arms.py` | Paired graded re-analysis of every prior arm |
| `eval/experiments/dev-loop/regrade-report.md` | Binary-vs-graded verdict table for all prior experiments |
| `eval/experiments/dev-loop/ledger.md` | Updated: graded gate, H-series hypotheses, per-experiment learnings |
| `ada/agent/claude/agent.ts` + `lever-guidance.ts` | Env-gated hooks seam (default OFF) |
| `eval/results/dev-h*.jsonl` | Hook-lever dev arms |
| `eval/experiments/dev-loop/validation-decision.json` | Validation verdict (if promoted) |
| `eval/campaign-report.md` | Final campaign narrative |

## Evaluation Criteria

- Phase 0 completes with **zero API spend** and re-scores all 466 trials; 1-test tasks satisfy graded == binary
- The regrade report explicitly answers whether any killed lever is significant under graded scoring
- Graded promotion gate is numeric and pre-registered before any Phase-1 paid run
- Hook spike proves hooks fire before any paid hook arm (hard gate)
- Every hook arm: pre-registered kill in ledger → reach probe → 40-trial arm → paired graded + binary analysis → learning recorded
- Validation (if reached): 120/120 both arms, **binary** primary verdict, graded secondary
- Total spend ≤ ~$45 of the ~$105 remaining (Phase 0 $0; spike ≤$1; 3 hook arms ≈$13.5; validation ≈$28)

## Notes & Constraints

- Model claude-haiku-4-5, CLI 2.1.258; venv activate; Node PATH export; API key from `.env`;
  harbor foreground NEVER under a timeout; ALL `--include-task-name` flags; `rm -rf` blocked on /root/*.
- Position-based pairing within task for all paired stats; scipy only in venv.
- All levers env-gated default-OFF; md5 parity `ada/agent/` ↔ `eval/ada-runtime/ada/agent/` after every edit.
- Dev set unchanged (8 MIXED + 2 guards); 5 tasks still held out for validation only.
- **Graded metric is the dev-loop instrument; binary remains the benchmark verdict.** Never
  promote on graded alone without the binary confirmation sweep.
- If hooks fire but all three hook arms return null, that is the campaign's answer — do not
  relax gates or re-sample the exhausted prompt-directive class.
