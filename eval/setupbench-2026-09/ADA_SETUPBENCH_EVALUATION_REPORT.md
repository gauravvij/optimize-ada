# Ada optimization on SetupBench: consolidated evaluation

Status: completed 12-task validation, three repetitions (2026-09-15–16). The frozen candidate is **not established as more accurate** than original Ada. It was faster and used fewer reported turns/tokens in this sample, with a small and inconclusive pass-rate advantage.

## Research question and scope

Can the autoresearch system improve Ada on SetupBench environment-setup tasks? This exercise evaluates that domain, not Ada's general coding ability. The autoresearch run used a fixed 12-task SetupBench development split to propose up to 10 candidate changes. The final frozen candidate and original Ada were then evaluated on a **separate** fixed 12-task validation split. This report covers that validation; it is **not** the complete 93-task SetupBench evaluation or an official leaderboard submission.

The historical six-task comparison in [SETUPBENCH_ADA_RESULTS.md](../examples/SETUPBENCH_ADA_RESULTS.md) had an incorrect grader working directory and is not valid comparative evidence. An earlier 480-second validation attempt yielded baseline 5/12 and candidate 6/12, but each variant had five timeouts; the 900-second, three-repetition protocol below supersedes it for the current conclusion.

## Candidate and experiment history

- Original Ada: local checkout at commit `0c5e1da7342ff86147b217a09c243cf17bf6c50d`, no tracked diff.
- Frozen candidate: same Ada commit plus changes under `agent/**` only. `agent/coding-guidance.ts` adds short wall-clock-economy guidance. `agent/claude/agent.ts` sets Bash default/max timeouts to 300/600 seconds and adds a 90-second **model-wait** watchdog with bounded retries. The watchdog pauses while tools run; it does not bound an overlong install, build, or test command. The guidance says “roughly 8 minutes,” although the final validation allowed 15 minutes per Ada attempt.
- Both variants used `z-ai/glm-5.3-flash` through OpenRouter and Ada's actual Claude-compatible agent integration, with Read/Edit/Write/Bash/Grep/Glob tools.
- Development: original Ada's recorded initial score was 4/12. The autoresearch run exhausted its 10-candidate budget and retained mechanisms from experiments 4 and 7. A best single development roll reached 10/12, but same-code rolls varied widely; experiment 4's gain failed its independent confirmation pair, and experiment 7 was not independently confirmed. The 10/12 figure must therefore **not** be presented as the candidate's expected performance.

Development record: `targets/ada-setupbench-paired/.autoresearch/runs/20260914T083236Z-e93655ba/state.json` (local, ignored). The final candidate was frozen before validation.

## Validation protocol

The evaluator was [`examples/setupbench_ada_eval.py`](../examples/setupbench_ada_eval.py), using the fixed `validation12` split at SetupBench commit `041a412f01348c2a6f8b1b6a910138fe01885aee`. Twelve official scenarios were run three times per variant in fresh containers: **12 tasks × 2 variants × 3 repetitions = 72 attempts**. Task order was reshuffled between repetitions, and baseline/candidate order alternated by task index. Only one agent attempt was active at a time, avoiding paired CPU/disk contention. Ada received the official problem statement but not the success command; grading used each scenario's official executable success command from `/testbed`.

Each Ada attempt had a 900-second wall-clock limit; grading had a separate 600-second limit. Both variants used the same host, images, model, fixtures, timeout, and grading logic. The Ada runtime and Node dependencies were mounted into otherwise minimal task containers, a disclosed departure from a wholly minimal environment. The protocol, image IDs, source fingerprints, exact task order, per-attempt results, and failed-attempt trace tails are recorded in the raw checkpoint.

The first run of this protocol hit an OpenRouter **monthly API-key limit** partway through repetition 1. Those API failures were initially misclassified as benchmark failures. After the key limit was raised, the evaluator was corrected to reject such API errors, archive the invalid checkpoint, preserve only seven complete unaffected pairs, and rerun every affected pair. Later, an outer evaluator process disappeared mid-pair; the incomplete pair was rerun from its last durable checkpoint. These interruptions did not contribute to the 72 results below. All final records have `valid=true`; no final pair contains the key-limit error. The archived invalid output is **not** an evaluation result.

## Primary result: pass/fail

| Repetition | Original Ada | Frozen candidate | Candidate difference |
|---|---:|---:|---:|
| 1 | 6/12 | 8/12 | +2 |
| 2 | 8/12 | 9/12 | +1 |
| 3 | 9/12 | 7/12 | −2 |
| **All attempts** | **23/36 (63.9%)** | **24/36 (66.7%)** | **+1/36 (+2.8 pp)** |

There were three candidate-only passes and two baseline-only passes among the 36 matched attempts. The exact paired McNemar two-sided p-value is **1.0**; the accuracy difference is not statistically conclusive. Repeated attempts on one task are correlated, so the 36 pairs are not 36 independent tasks. On the more conservative per-task majority criterion (at least two passes in three attempts), **both variants passed 8/12 tasks**.

The table below shows each task's outcomes in repetition order: `P` pass, `F` completed but failed grader, `T` Ada timeout.

| Validation task | Original Ada | Frozen candidate |
|---|:---:|:---:|
| Filewatcher daemon | PPP | PPP |
| MongoDB | PPP | PPP |
| MySQL | FPP | PPF |
| Gatsby plugin dependency | TPP | PPP |
| Frontrunning-bot dependency | PPP | PPP |
| Tov-template | PPP | PPP |
| Fsspec | TTF | FFF |
| CodiMD | FTP | TFT |
| Azure Pipelines Tasks | TTT | TTT |
| Prometheus | PPP | PPP |
| Wagtail | TTT | TPT |
| Whisper | PPP | PPP |

## Secondary result: efficiency and reliability

| Measure | Original Ada | Frozen candidate | Interpretation |
|---|---:|---:|---|
| Ada timeouts | 10/36 | 7/36 | Three fewer; exact paired timeout p = 0.453, not conclusive on its own. |
| Sum of per-attempt total duration | 19,553 s (5.43 h) | 16,143 s (4.48 h) | Candidate used 17.4% less measured wall time, including grading. |
| Faster matched attempts | — | 30/36 | Candidate faster descriptively. |
| Faster when neither timed out | — | 22/24 | Median candidate-minus-baseline duration: −78.8 s. |
| Fewer turns when both counts were reported | — | 20/21 | Median paired reduction: 8 turns. |
| Fewer tokens when both usages were reported | — | 18/21 | Median candidate/baseline total-token ratio: 0.48. |

The timing signal is meaningful but should not be overstated: across the **12 task-level median** duration differences, the candidate was faster on 9 tasks (two-sided sign-test p ≈ 0.146). Repetitions and some task outcomes are correlated, and timeouts censor completion time. The 17.4% aggregate is descriptive, not a benchmark-wide speedup estimate. Turn/token comparisons exclude attempts without terminal usage; `turns=0` on a timeout or missing terminal result means **unavailable**, not necessarily no work. The Claude-compatible trace's `total_cost_usd` uses an incompatible/synthetic pricing basis for GLM, so this report does not assert a measured OpenRouter bill.

## Why candidate accuracy fell to 7/12 in repetition 3

Seven tasks passed for the candidate in **every** repetition. Its 8 → 9 → 7 trajectory came from two unstable tasks:

1. **MySQL: PPF.** In repetition 3 the agent installed and populated the database and verified `mysql -u root -proot`, but changed root authentication without creating `/root/.my.cnf` or otherwise preserving bare `mysql -u root` access. The official grader uses bare `mysql -u root`; it returned `ERROR 1045 (28000): Access denied ... (using password: NO)`. Candidate repetitions 1 and 2 created `.my.cnf` and passed. Baseline was FPP on this task, illustrating stochastic variation on both sides. This is a concrete interface-compatibility failure, not an API or harness failure.
2. **Wagtail: TPT.** Repetition 2 reached a working `wagtail start` and passed. In repetition 3 the agent spent its budget running broad Wagtail test suites, diagnosing missing timezone data, installing `tzdata`, and launching another full test command; it hit the 900-second Ada cutoff before grading. The official success check was just `wagtail start mysite`. The candidate's model-wait watchdog could not intervene while those Bash tools were active. Baseline timed out in all three repetitions.

CodiMD did **not** cause the candidate's own 9 → 7 drop: the candidate failed all three repetitions, twice by timeout. Baseline passed it only in repetition 3, widening that repetition's baseline/candidate gap. Candidate repetition 3 spent substantial time installing Node/PostgreSQL and polling a long install; candidate repetition 1 consumed time polling a webpack build. The baseline repetition-3 pass also exposed a grader limitation: it had left a server running, and the official `node app.js && echo "Setup successful" || echo "Setup failed"` command emitted a port-in-use stack trace **and** `Setup successful` (the shell `&&/||` structure treats the already-running process's normal termination differently). The evaluator followed the benchmark's literal success marker; this task should not be interpreted as strong evidence of a reliably working second server launch.

No final run-3 attempt was marked infrastructure-invalid. The score swing is explained by task-level stochastic agent choices and the hard deadline, not by another API-key outage.

## Interpretation and next decision

The answer to the research question is **partial**: autoresearch found an Ada candidate that is more economical on this SetupBench validation sample and did not show a clear aggregate quality regression. It did **not** demonstrate a reproducible accuracy improvement: the net advantage was only one pass in 36 attempts, the third repetition reversed direction, and majority-task success was tied 8/12.

The candidate's general efficiency guidance helps on several tasks (notably Prometheus), but its completion policy remains inconsistent. The remaining observed failure modes are concrete: preserve verifier-compatible command interfaces (MySQL), avoid nonessential exhaustive tests once the decisive setup check works (Wagtail), and prevent long active tool calls from consuming the entire wall budget. Those are hypotheses for a *future* optimization cycle, not fixes evaluated here. Do not tune the frozen candidate using these validation traces and then re-label this same split as untouched holdout. A corrected candidate would require a fresh comparison protocol.

The full 93-task SetupBench set has **not** been evaluated for this frozen candidate. The earlier complete-set Ada study discussed in other notes belonged to a different candidate/protocol and must not be conflated with this 12-task 3× result.

Raw local result: `targets/ada-setupbench-paired/.setupbench_diagnostics/validation-900s-3x.json` (gitignored; 72 per-attempt records, protocol fingerprints, failure trace tails). Archived invalid checkpoint: `validation-900s-3x-key-limit-failed.json` in the same directory. Development record: `targets/ada-setupbench-paired/.autoresearch/runs/20260914T083236Z-e93655ba/state.json` (gitignored). This report is the portable summary; it does not embed the large raw traces.
