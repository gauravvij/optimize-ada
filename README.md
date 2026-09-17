# Ada optimization on SetupBench

This branch preserves one completed autoresearch campaign that attempted to
optimize the [Ada agent](https://github.com/rabbah/ada) for SetupBench
environment-setup tasks. It contains the frozen candidate that was evaluated,
the candidate patch, and the resulting baseline-versus-candidate measurements.

This is not an official Ada branch. It is also separate from the Terminal-Bench
campaign on this repository's `main` branch.

## Research question

Can the autoresearch loop improve Ada on SetupBench by modifying Ada, evaluating
each candidate on a fixed development set, retaining promising mechanisms, and
then comparing the frozen final candidate with original Ada on a separate
validation set?

## Process

| Item | Value |
|---|---|
| Ada base | `0c5e1da7342ff86147b217a09c243cf17bf6c50d` |
| Benchmark | SetupBench at `041a412f01348c2a6f8b1b6a910138fe01885aee` |
| Ada model | `z-ai/glm-5.3-flash` through OpenRouter |
| Development set | 12 fixed SetupBench tasks |
| Candidate budget | 10 experiments |
| Validation set | 12 separate SetupBench tasks |
| Final validation | 3 repetitions per variant |

1. **Freeze the baseline.** Original Ada and the evaluator, task split, model,
   timeouts, and official graders were fixed before optimization.
2. **Search on development tasks.** Autoresearch inspected traces, proposed one
   Ada change per experiment, and measured it against a fresh same-cycle control
   on the same 12 development tasks.
3. **Retain measured winners.** Regressions were rolled back; experiments 4 and
   7 were retained. The loop stopped after its 10-experiment budget.
4. **Freeze the candidate.** The final candidate combined only the retained
   experiment 4 and 7 mechanisms. Development results were not used again.
5. **Validate separately.** Original Ada and the frozen candidate were compared
   on 12 different SetupBench tasks, with three runs per task and variant.

## Retained candidate: what actually changed

| Experiment | Observed problem and hypothesis | Retained implementation |
|---|---|---|
| **4 — wall-clock economy** | Long commands were being killed or repeated, and extra turns consumed the fixed task budget. | Added concise instructions to batch work, start long operations early, detach services, verify by exit code, and stop after success. Raised Bash default/max timeouts to 300/600 seconds. |
| **7 — stalled-model recovery** | Some runs emitted no model output and consumed the remaining wall clock without useful work. | Added a tool-aware 90-second model-wait watchdog, up to four attempts, and a 360-second deadline for starting retries. The watchdog pauses during legitimate tool execution. |

Experiment 4 initially scored 8/12 against a 4/12 control, but its separate
confirmation failed at 5/12 against 7/12. Experiment 7 later scored 10/12
against a 7/12 control but did not receive an independent confirmation run.
Those caveats are why the combined candidate was evaluated on a separate split.

The retained changes are limited to `ada/agent/coding-guidance.ts` and
`ada/agent/claude/agent.ts`. No SetupBench success commands or task-specific
solutions were added to Ada.

The complete frozen source is in `ada/`. The exact two-file delta is archived as
[`frozen-candidate.patch`](eval/setupbench-2026-09/frozen-candidate.patch).

## Development search outcome

| Value | Result |
|---|---:|
| Original Ada's initial recorded score | 4/12 |
| Best single recorded candidate roll | 10/12 |
| Experiments consumed | 10/10 |
| Retained experiments | 4 and 7 |
| Experiment 4 independent confirmation | Failed |
| Experiment 7 independent confirmation | Not completed |
| Stop condition | Maximum experiments reached |

The 10/12 development roll was not treated as the expected candidate quality.
Repeated measurements of unchanged code varied substantially, so the final
candidate was frozen and evaluated separately.

## Final validation protocol

- 12 validation tasks not used for the development search.
- Original Ada and the frozen candidate each ran every task three times.
- 72 total attempts: 12 tasks × 2 variants × 3 repetitions.
- 900-second Ada timeout and 600-second grader timeout per attempt.
- Fresh containers and official executable SetupBench graders.
- 72/72 final attempts were valid.
- Only one agent attempt was active at a time to avoid paired CPU/disk
  contention.

## Final quantitative outcome

### Passes

| Repetition | Original Ada | Frozen candidate | Difference |
|---|---:|---:|---:|
| 1 | 6/12 | 8/12 | +2 |
| 2 | 8/12 | 9/12 | +1 |
| 3 | 9/12 | 7/12 | −2 |
| **Total** | **23/36 (63.9%)** | **24/36 (66.7%)** | **+1/36 (+2.8 pp)** |

### Aggregate comparison

| Metric | Original Ada | Frozen candidate | Difference / result |
|---|---:|---:|---:|
| Passes | 23/36 | 24/36 | +1 pass |
| Tasks passing in at least 2/3 runs | 8/12 | 8/12 | Tie |
| Timeouts | 10/36 | 7/36 | −3 timeouts |
| Total attempt duration | 19,553.258 s | 16,143.215 s | −3,410.043 s (−17.44%) |
| Recorded turns | 543 | 449 | −94 turns |
| Candidate faster | — | 30/36 pairs | — |
| Candidate faster without either timing out | — | 22/24 pairs | — |
| Median duration difference | — | −51.114 s | Candidate faster |
| Median duration difference without timeouts | — | −78.819 s | Candidate faster |
| Median candidate/baseline token ratio | — | 0.4785 | −52.15% on 21 comparable pairs |

### Statistical checks

| Test | Result |
|---|---:|
| Candidate-only passes | 3 |
| Baseline-only passes | 2 |
| Exact paired McNemar p-value for passes | 1.000 |
| Baseline-only timeouts | 5 |
| Candidate-only timeouts | 2 |
| Exact paired McNemar p-value for timeouts | 0.453125 |
| Task-level duration sign-test p-value | 0.145996 |

The task-level P/F/T matrix is in the [direct quantitative outcome](eval/setupbench-2026-09/ADA_SETUPBENCH_DIRECT_OUTCOME.md).

## Conclusion

The candidate did **not** demonstrate an accuracy improvement. Its pass-rate
advantage was only 1/36, task-majority accuracy tied 8/12, and the paired pass
test was not significant. It showed descriptive efficiency improvements in
this sample—fewer timeouts, lower aggregate duration, fewer turns, and fewer
reported tokens—but those differences were not established as statistically
conclusive either.

The complete 93-task SetupBench set was not run for this candidate.

## Evidence

- [Direct quantitative outcome](eval/setupbench-2026-09/ADA_SETUPBENCH_DIRECT_OUTCOME.md)
- [Detailed evaluation report](eval/setupbench-2026-09/ADA_SETUPBENCH_EVALUATION_REPORT.md)
- [Candidate provenance](eval/setupbench-2026-09/README.md)
- [Exact frozen patch](eval/setupbench-2026-09/frozen-candidate.patch)
