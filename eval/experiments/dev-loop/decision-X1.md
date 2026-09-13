# Dev-loop X1 decision — verify-once (L1-lite)

Job: `dev-x1` · Arm: `dev-x1` · Lever: `ADA_VERIFY_ONCE=1` (env-gated
`verifyOnceGuidance` in `ada/agent/lever-guidance.ts`, wired into
`systemPromptAppend` in `index.ts`) · Model: `anthropic/claude-haiku-4-5`
Dataset: `terminal-bench@2.0`, 10 dev tasks × k=4 = 40 trials
Run: Sep 3, 1h09m35s foreground (no timeout) · Results:
`eval/results/dev-x1.jsonl` (40 records, arm=`dev-x1`, 39 cost-bearing) ·
Analysis: `eval/analysis/analyze_dev_x1.py`

Reference arm: FRESH `dev-baseline` (`eval/results/dev-baseline.jsonl`,
24/40 = 0.600, mean cost $0.0879). Comparisons are position-based within
task (the `trial` field is not comparable across arms).

## Hypothesis
Agents write a plausible artifact, narrate "Done!", and never execute it —
cancel-async-tasks 0/4 with 4/4 failing trials ≥50% verifier pass (3/4 trials
were 1 Write + 2 turns); 7/14 near-miss fails ≥50%. L1's self-verify mandate
converted near-misses but blew cost (+20%, unbounded fix loop). X1 = run the
deliverable once, fix once, re-run once, then finish on evidence.

## Results vs pre-registered criteria (ledger.md)

| Criterion | Baseline | X1 | Result |
|---|---|---|---|
| Suite pass | 24/40 = 0.600 | **30/40 = 0.750** | Δ +0.150 (6 trials converted) |
| Wilson 95% CI | [0.446, 0.737] | [0.598, 0.858] | overlap (directional only at n=40) |
| Guards (fix-code-vulnerability, git-leak-recovery) | 8/8 | 8/8 | intact ✓ |
| Position-based McNemar | — | 22 both-pass, 8 both-fail, 2 base-only, **8 X1-only** | two-sided exact p = 0.1094 (one-sided 0.0547, directional) |
| Mean cost (cost-bearing) | $0.0879 (n=38) | **$0.1218 (n=39)** | ratio **1.386** |
| Task-mean cost | $0.0955 | $0.1240 | ratio 1.298 |
| X1 kill guard (cost > 1.15×$0.0879 = $0.1011) | — | $0.1218 > $0.1011 | **BREACHED → KILL** |
| Promotion gate (pass ≥ 28/40 AND guards 8/8 AND cost ≤ 1.10× = $0.0967) | — | pass 30 ✓, guards ✓, cost ✗ | **NOT MET** |

## Per-task breakdown
| Task | Base | X1 | Conv (B-only/X-only) | costB | costX | ratio | turnsB→X |
|---|---|---|---|---|---|---|---|
| cancel-async-tasks | 0/4 | 0/4 | 0/0 | $0.0221 | $0.0468 | 2.12 | 2.8→9.0 |
| fix-code-vulnerability | 4/4 | 4/4 | 0/0 | $0.1849 | $0.2539 | 1.37 | 28.5→44.2 |
| fix-git | 2/4 | 4/4 | 0/2 | $0.0285 | $0.0403 | 1.41 | 10.5→14.5 |
| git-leak-recovery | 4/4 | 4/4 | 0/0 | $0.0278 | $0.0326 | 1.17 | 10.0→11.5 |
| git-multibranch | 3/4 | 4/4 | 0/1 | $0.1336 | $0.1516 | 1.13 | 29.5→29.8 |
| large-scale-text-editing | 2/4 | 2/4 | 2/2 | $0.2398 | $0.2084 | 0.87 | 13.8→20.5 |
| log-summary-date-ranges | 3/4 | 4/4 | 0/1 | $0.0300 | $0.0357 | 1.19 | 6.5→6.8 |
| openssl-selfsigned-cert | 3/4 | 3/4 | 0/0 | $0.0439 | $0.0648 | 1.48 | 14.2→18.8 |
| regex-log | 2/4 | 3/4 | 0/1 | $0.1233 | $0.2754 | 2.23 | 2.0→19.0 |
| sanitize-git-repo | 1/4 | 2/4 | 0/1 | $0.1209 | $0.1301 | 1.08 | 22.8→23.8 |

## Mechanism evidence (treatment reach + behavior change)
- **Treatment reach: 40/40** bridge logs contain the marker text
  `Execution check for this run` (0 miss, 0 absent) → genuinely treated.
- **Behavior changed**: mean turns rose on nearly every task (suite
  2.8→9.0 cancel-async-tasks, 2.0→19.0 regex-log, 10.5→14.5 fix-git,
  28.5→44.2 fix-code-vulnerability) — agents that previously wrote-then-stopped
  now execute and iterate on their deliverable. (Tool-count fields are empty in
  the JSONL for this arm — collect.py's tool_counts() only parses ada-events
  when arm == "ada", and dev arms are labelled dev-*; the num_turns metric from
  result metadata is the reliable mechanism signal.)
- **Conversion pattern**: all 8 X1-only wins are near-miss flips on tasks whose
  baseline failure was write-without-run (fix-git 2, git-multibranch 1,
  log-summary 1, regex-log 1, sanitize-git 1, large-scale-text-editing 2);
  large-scale-text-editing also lost 2 (regression/flip noise at k=4).
- **Cost drivers**: (a) already-solved guard tasks ran redundant verification
  loops (fix-code-vulnerability +15.7 turns, git-leak +1.5, both were 4/4 →
  pure overhead); (b) run-reveals-failure tasks triggered long fix iterations
  despite the "fix once, re-run once" bound (regex-log 2→19 turns, 2.23× cost);
  (c) cancel-async-tasks 2.8→9.0 turns at 2.12× cost with 0/4 pass — running
  alone does not fix a wrong concurrency model; the failure (cancel_above_max)
  needs targeted edge-case testing, not a smoke run.

## VERDICT: KILL (cost guard breach) — NOT promoted
Per the pre-registered rule the cost kill criterion is binding: mean cost
1.386× baseline far exceeds the 1.15× kill guard, and the promotion cost gate
(1.10×) is not met. The +6-trial pass gain is real and directional (McNemar
one-sided p = 0.055) but the mechanism is too expensive as an unconditional
directive — it taxes already-solving tasks and rewards over-iteration.

**Learning (drives queue re-ranking):**
1. Unconditional run-once verification converts near-misses (+6/40) at a
   cost too high to promote (1.39×).
2. The overhead concentrates where the check is redundant (already-passing
   guard tasks: fix-code-vulnerability +$0.069/trial for zero pass gain) and
   where one run surfaces a cascade of fixes (regex-log).
3. Running does NOT fix cancel-async-tasks (0/4 → 0/4): the check needs to
   exercise the task's stated success criteria / edge case, not just execute.
4. Any next candidate should either (a) make the verification conditional on
   ex-ante signs the task needs it, or (b) keep the run mandate but cap the
   repair iteration harder, or (c) target verify-against-success-criteria
   rather than verify-execute.

Spend: dev-x1 ~$4.75 (39 cost-bearing records, mean $0.1218; 1
AgentTimeoutError on large-scale-text-editing has no usage) + probe ~$0.12.
