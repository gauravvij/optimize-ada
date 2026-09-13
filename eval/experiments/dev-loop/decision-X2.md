# Dev-loop X2 decision — verify-against-criteria (X1-refined)

Job: `dev-x2` · Arm: `dev-x2` · Lever: `ADA_VERIFY_AGAINST_CRITERIA=1`
(env-gated `verifyAgainstCriteriaGuidance` in `ada/agent/lever-guidance.ts`,
wired into `systemPromptAppend` in `index.ts`) · Model:
`anthropic/claude-haiku-4-5` · Dataset: `terminal-bench@2.0`, 10 dev tasks ×
k=4 = 40 trials · Run: Sep 3, 1h16m17s foreground (no timeout) · Results:
`eval/results/dev-x2.jsonl` (40 records, arm=`dev-x2`, 38 cost-bearing) ·
Analysis: `eval/analysis/analyze_dev_x2.py`

Reference arm: FRESH `dev-baseline` (`eval/results/dev-baseline.jsonl`,
24/40 = 0.600, mean cost $0.0879). Comparisons are position-based within
task (the `trial` field is not comparable across arms).

## Hypothesis (why X2 followed X1)
X1 (verify-once) converted near-misses (+6/40) but blew the cost guard
(1.386× baseline) because (a) happy-path execution misses the verifier's edge
case — cancel-async-tasks stayed 0/4 despite +6 turns/trial because a smoke
run never exercises `test_tasks_cancel_above_max_concurrent`; (b) already-
solving guard tasks ran redundant final runs (fix-code-vulnerability +15.7
turns, zero pass gain). X2 = before finishing, test the deliverable against
the task's STATED SUCCESS CRITERIA and likely edge cases; fix once; STOP when
the criteria check passes; no extra passes.

## Pre-registered criteria (ledger.md X2 row)
- Kill: dev pass < 26/40 OR mean cost > 1.15 × $0.0879 = **$0.1011**
- Success targets (X1 learning): cancel-async-tasks ≥ 2/4 AND regex-log ≥ 2/4
- Promotion gate (unchanged): dev pass ≥ 28/40 AND guards 4/4 AND mean cost
  ≤ 1.10 × $0.0879 = **$0.0967** AND trace evidence

## Results vs pre-registered criteria

| Criterion | Baseline | X2 | Result |
|---|---|---|---|
| Suite pass | 24/40 = 0.600 | **28/40 = 0.700** | Δ +0.100 (4 trials converted) |
| Wilson 95% CI | [0.446, 0.737] | [0.546, 0.819] | overlap (directional only at n=40) |
| Guards (fix-code-vulnerability, git-leak-recovery) | 8/8 | 8/8 | intact ✓ |
| Position-based McNemar | — | 19 both-pass, 7 both-fail, 5 base-only, **9 X2-only** | two-sided exact p = **0.4240** |
| Mean cost (cost-bearing) | $0.0879 (n=38) | **$0.0917 (n=38)** | ratio **1.043** |
| Task-mean cost | $0.0955 | $0.0933 | ratio **0.977** |
| X2 kill guard (cost > $0.1011) | — | $0.0917 < $0.1011 | **NOT breached** |
| Promotion gate (pass ≥ 28, guards, cost ≤ $0.0967) | — | 28 ✓, guards ✓, $0.0917 ✓ | **met LITERALLY** |
| X2 success target: cancel-async-tasks ≥ 2/4 | 0/4 | **1/4** | **MISS** |
| X2 success target: regex-log ≥ 2/4 | 2/4 | 2/4 | OK (flat, 1 flip each way) |

## Per-task breakdown
| Task | Base | X2 | Conv (B-only/X-only) | costB | costX | ratio | notes |
|---|---|---|---|---|---|---|---|
| cancel-async-tasks | 0/4 | 1/4 | 0/1 | $0.0221 | $0.0377 | 1.71 | target task, barely moved |
| fix-code-vulnerability | 4/4 | 4/4 | 0/0 | $0.1849 | $0.1796 | 0.97 | guard — no redundant-verify overhead (vs X1 1.37×) |
| fix-git | 2/4 | 3/4 | 1/2 | $0.0285 | $0.0307 | 1.08 | conversion ✓ |
| git-leak-recovery | 4/4 | 4/4 | 0/0 | $0.0278 | $0.0307 | 1.10 | guard |
| git-multibranch | 3/4 | 3/4 | 1/1 | $0.1336 | $0.1496 | 1.12 | flat (1 flip each way) |
| large-scale-text-editing | 2/4 | 2/4 | 1/1 | $0.2398 | $0.1240 | **0.52** | pass flat, cost HALVED — thrash cut |
| log-summary-date-ranges | 3/4 | 4/4 | 0/1 | $0.0300 | $0.0320 | 1.07 | conversion ✓ |
| openssl-selfsigned-cert | 3/4 | 3/4 | 0/0 | $0.0439 | $0.0529 | 1.20 | flat |
| regex-log | 2/4 | 2/4 | 1/1 | $0.1233 | $0.1136 | 0.92 | target task, flat (cost down) |
| sanitize-git-repo | 1/4 | 2/4 | 1/2 | $0.1209 | $0.1825 | 1.51 | conversion ✓ but cost +51% |

## Mechanism evidence (treatment reach + behavior change)
- **Treatment reach: 40/40** bridge logs contain the marker text
  `Criteria check for this run` (0 miss, 0 absent) → genuinely treated.
- **X1's cost blow-up is FIXED**: mean-cost ratio fell 1.386× → **1.043×**
  and task-mean ratio is **0.977× (below baseline)**. The stop-on-pass,
  one-check-per-criterion design removed the two X1 cost drivers:
  - already-solving guard tasks no longer run redundant final checks
    (fix-code-vulnerability cost 0.97× vs X1's 1.37×);
  - criteria-targeted checks replace happy-path re-runs.
- **The +4 suite gain is spread across OTHER tasks than the diagnosed
  targets**: fix-git 2→3, log-summary 3→4, sanitize-git-repo 1→2 (+1 each) —
  while cancel-async-tasks (the design driver) only reached 1/4 and regex-log
  stayed flat at 2/4. The mechanism's strongest measured effect is on the
  long/thrash-prone task (large-scale-text-editing cost 0.52×, pass flat) —
  echoing the E-opt1/L2 pattern that operating-efficiency guidance helps where
  output volume is the failure mode.

## VERDICT: NOT PROMOTED (conservative adjudication)

**Literal reading (pre-registered 4-condition gate):** pass 28/40 = baseline+4
✓, guards 8/8 ✓, mean cost $0.0917 ≤ $0.0967 ✓, reach 40/40 ✓ → gate met.
**Conservative adjudication (binding):** the X2-specific success targets were
pre-registered as the experiment's design objective and they were NOT met
(cancel-async-tasks 1/4 < 2/4). When a lever fails its own design objective —
the mechanism it was built to fix did not take hold — the correct inference is
that more trials on the SAME lever will not fix it. Additionally the suite
delta +0.100 carries McNemar p = 0.4240 (9 vs 5 discordant pairs at n=40),
statistically indistinguishable from noise. Spending ~$28 (19% of remaining
budget) on a k=8 validation sweep of a noise-band delta with a missed design
target would very likely return a null. **Recorded honestly: the literal gate
is met, so a future k=8 validation of X2 remains runnable without re-running
the k=4 arm.**

**Preserved finding (positive):** X2's stop-on-pass criteria-verification is
the cost-control design that fixes X1's defect. **Future levers must inherit
it as a cost-control component** — no unconditional run/fix directives; checks
target the verifier's criteria, one check per criterion, stop on pass.

Spend: dev-x2 ~$3.50 (38 cost-bearing records, mean $0.0917; 2
AgentTimeoutError on large-scale-text-editing have no usage) + probe ~$0.09.
