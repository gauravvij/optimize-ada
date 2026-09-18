# Ada × SetupBench: 1200-second paired validation

## Direct outcome

The frozen Ada candidate **did not improve SetupBench pass rate** in this validation: both versions passed **26/36 attempts (72.2%)**. They each won three discordant pairs. The candidate had descriptively shorter attempt durations and fewer reported tokens on comparable pairs, but the run does **not** establish a candidate-specific cost saving or a robust task-level speed gain.

| Measure | Original Ada | Frozen candidate | Candidate − baseline |
|---|---:|---:|---:|
| Grader passes | 26/36 (72.2%) | 26/36 (72.2%) | 0/36 (0.0 pp) |
| Ada timeouts | 7/36 (19.4%) | 5/36 (13.9%) | −2/36 (−5.6 pp) |
| Sum of attempt durations | 23,814.406 s | 19,362.968 s | −4,451.438 s (−18.69%) |
| Median attempt duration | 537.147 s | 417.536 s | −119.611 s |
| Tasks passed in at least 2 of 3 repetitions | 9/12 | 8/12 | −1/12 |

The duration sum is **aggregate per-attempt wall time**, including container launch, Ada execution, grading, and cleanup—not just Ada runtime, elapsed validation-job time, or billed cost. Because attempts ran concurrently, it cannot be interpreted as time saved by the validation job.

## Protocol and provenance

- SetupBench **validation12** split: the same 12 tasks, each repeated three times for each variant; **36 matched pairs / 72 final attempts**. All 72 final attempts are marked valid.
- Within a task/repetition pair, original and candidate ran simultaneously. Up to three pairs ran at once (up to six Ada attempts). Task order was randomized per repetition with seed `20260904`.
- Ada attempt limit: **1200 s**; grader limit: **600 s**. Model used by Ada: `z-ai/glm-5.3-flash`.
- SetupBench commit: `041a412f01348c2a6f8b1b6a910138fe01885aee`. Both variants share Ada commit `0c5e1da7342ff86147b217a09c243cf17bf6c50d`; baseline tracked-diff SHA-256 is `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`, candidate tracked-diff SHA-256 is `9e6a3fe04725f3c3ca43b5fcfcd53bde07f8fbbffc58d7e80793f6ffb408bd4a`.
- Published, trace-free [compact evidence](ADA_SETUPBENCH_VALIDATION_1200S_COMPACT.json) contains every quantitative row; the full raw files remain in the autoresearch workspace and are pinned by SHA-256 below. The run-wide billing observation spans **2026-09-18 09:07:58–11:51:27 UTC**, about **2 h 43 min 29 s**.

This is a new **1200 s, concurrent** validation. The earlier [900 s report](ADA_SETUPBENCH_DIRECT_OUTCOME.md) used a different timeout and execution schedule, so its figures must not be treated as another repetition of this protocol or attributed solely to the timeout change.

## Paired quality

| Repetition | Original passes | Candidate passes | Difference | Original timeouts | Candidate timeouts |
|---|---:|---:|---:|---:|---:|
| 1 | 7/12 | 9/12 | +2 | 4/12 | 2/12 |
| 2 | 9/12 | 9/12 | 0 | 2/12 | 0/12 |
| 3 | 10/12 | 8/12 | −2 | 1/12 | 3/12 |
| **Total** | **26/36** | **26/36** | **0** | **7/36** | **5/36** |

| Matched-pair outcome | Count |
|---|---:|
| Both pass | 23 |
| Candidate passes, baseline fails | 3 |
| Baseline passes, candidate fails | 3 |
| Both fail | 7 |
| Unadjusted attempt-level exact McNemar p-value for pass discordance | 1.000 |
| Baseline-only timeout / candidate-only timeout / both timeout | 4 / 2 / 3 |

The 36 observations are repeated runs of only **12 distinct tasks**, not 36 independent benchmark problems. The paired p-value is a descriptive calculation, **not a valid 36-independent-pairs significance test**. The point estimate itself is a tie, so this run gives no evidence of a quality improvement. The pinned SetupBench harness treats the grader output marker `Setup successful` as a pass for non-dependency tasks even if the success command exits nonzero; dependency tasks require exit code 0. In this data, the six passes for `dishait-tov-template-39c0898` carried exit code 143 after printing the success marker; both variants were scored by the same rule.

## Per-task outcomes

`P` = grader pass; `F` = completed but failed; `T` = Ada timeout. Letters are repetitions 1, 2, 3.

| SetupBench task | Original Ada | Frozen candidate |
|---|:---:|:---:|
| microsoft-azure-pipelines-tasks-bfcd4b2 | TTP | TFT |
| prometheus-bd5b2ea | PPP | PPP |
| fsspec-filesystem_spec-3ff5fca | TPP | PPP |
| dishait-tov-template-39c0898 | PPP | PPP |
| hackmdio-codimd-f00df50 | FFF | PFT |
| whisper-517a43e | PPP | PPP |
| wagtail-wagtail-28fcd01 | TTT | TPT |
| deps-ultimate-frontrunning-bot-449d6 | PPP | PPP |
| deps-gatsby-plugin-intl-2b7ac | TPP | FPP |
| dbsetup-mongodb-2 | PPP | PPP |
| dbsetup-mysql-2 | PPP | PFF |
| bgsetup-filewatcher-daemon-2 | PPP | PPP |

## Duration and turns

| Paired duration measure | Result |
|---|---:|
| Candidate faster, all pairs | 23/36 |
| Median candidate − baseline, all pairs | −101.795 s |
| Mean candidate − baseline, all pairs | −123.651 s |
| Pairs with neither variant timed out | 27/36 |
| Candidate faster in neither-timeout pairs | 17/27 |
| Median candidate − baseline in neither-timeout pairs | −103.374 s |
| Mean candidate − baseline in neither-timeout pairs | −111.504 s |
| Tasks with lower candidate median duration across three repetitions | 8/12 |
| Two-sided sign-test p-value across those 12 task medians | 0.388 |

Ada execution is time-limited, so comparisons involving a timeout are censored; total attempt duration can still exceed 1200 seconds because it includes harness work. The neither-timeout subset still favors the candidate descriptively, but 8/12 faster task medians is not a strong task-level statistical result.

Turn counts are comparable only when **both** attempts returned terminal usage. That holds for **24/36 pairs**. On those pairs, baseline recorded **693 turns** versus candidate **432 turns** (−261, or −37.7%); candidate used fewer turns in **20/24**, with median paired difference **−9 turns**. A missing terminal result must not be interpreted as zero turns.

## Tokens and cost

Terminal token usage exists for **28/36 baseline** and **27/36 candidate** attempts, with **24/36 pairs** reporting it on both sides. The following comparisons use only those 24 matched pairs.

| Reported token measure | Original Ada | Frozen candidate | Candidate / baseline |
|---|---:|---:|---:|
| Input tokens | 1,542,588 | 960,527 | 0.6227 |
| Output tokens | 253,448 | 142,486 | 0.5622 |
| Cache-read tokens | 10,011,840 | 3,943,936 | 0.3939 |
| Input + output + cache-read | 11,807,876 | 5,046,949 | 0.4274 |
| Median per-pair total-token ratio | — | — | 0.4617 |

The candidate used fewer total reported tokens in **21/24** comparable pairs. These are observed token counts on a selected subset, **not a 57.3% price reduction**: cache-read tokens can be billed differently from input/output tokens, 12 pairs lack comparable terminal usage, and a token ratio is not a bill.

The OpenRouter key-wide billed-usage counter increased **$13.52195424** over the recorded run interval. Baseline and candidate requests overlapped, as did up to three pairs, so per-attempt key-usage deltas overlap and **must not be summed or assigned to a variant**. There is no defensible candidate-versus-baseline dollar-cost result from this run. The key-wide delta also cannot rule out any other use of the same key during that interval.

## Supplementary cost-telemetry follow-up (not replacement validation)

The original 36-pair validation is unchanged. We reran **three task pairs** solely to obtain comparable terminal usage: `prometheus-bd5b2ea` once and `whisper-517a43e` twice. These correspond to original repetition 3 for Prometheus and repetitions 2 and 3 for Whisper; follow-up repetition numbers restart at 1. Each new pair ran baseline and candidate concurrently in fresh containers, with the same pinned Ada revisions, SetupBench revision, model, evaluator hash, container image, and 1200/600-second limits as the original validation. Prometheus overlapped an aborted Whisper attempt; the two successful Whisper pairs later ran one pair at a time to avoid another disk-full failure. **All 6/6 recorded attempts were valid, passed, avoided timeout, and returned terminal token usage.** The new pass results are not substituted into the 26/36 quality comparison.

At the user-specified illustrative rates of **$0.09 per million input tokens, $0.30 per million output tokens, and $0.018 per million cache-read tokens**, the recorded usage yields:

| Measured subset | Baseline estimate | Candidate estimate | Candidate − baseline |
|---|---:|---:|---:|
| Original validation: 24 pairs with usage on both sides | $0.395080 | $0.200184 | −$0.194896 (−49.33%) |
| New follow-up: 3 fresh pairs | $0.040869 | $0.024488 | −$0.016381 (−40.08%) |
| Combined **measured sample**: 24 original + 3 new | $0.435949 | $0.224672 | −$0.211277 (−48.46%) |

| New pair | Pass (B/C) | Duration B/C | Estimated cost B/C |
|---|:---:|---:|---:|
| Prometheus follow-up 1 | P/P | 241.085 / 429.696 s | $0.003806 / $0.009259 |
| Whisper follow-up 1 | P/P | 1011.926 / 399.271 s | $0.021829 / $0.007234 |
| Whisper follow-up 2 | P/P | 309.457 / 1053.685 s | $0.015233 / $0.007995 |

Candidate estimated cost is lower in **2/3** new pairs, while candidate duration is lower in **1/3**. This variability does not overwrite the original duration result. The combined 27-pair row is **not a 27/36 complete-case result**: the three additions are new attempts, the original 12 pairs without matched usage remain missing, and nine of those involved an Ada timeout. The selected follow-up tasks and the different concurrent load limit generalization. Provider-limit retries and an earlier disk-protection abort produced no valid pair records and are excluded from these per-attempt estimates; their actual spend is not attributable from this telemetry. These prices are assumed rates, **not OpenRouter-billed variant costs**.

The published [compact evidence](ADA_SETUPBENCH_VALIDATION_1200S_COMPACT.json) also includes all six follow-up metric rows and their source hashes. Full-source SHA-256: original validation `d5398bb75a41fd6c57d8792448ecf516cb12498ea659c2a9b4482ad09a12c5f4`; Prometheus follow-up `0d1827e8ab4fafac96dfd984c5913003fdedb51834e7adda35673b53f474f446`; Whisper follow-up `b5ce3653271d190f48c63dec9e05efa772f58cd726bb672160a2aecb09768246`.

## Conclusion

At this 1200-second limit, the frozen candidate **ties original Ada on grader success (26/36 each)**. It shows descriptive reductions in duration, timeouts, turns, and measured tokens, with meaningful coverage and censoring limitations. The measured subsets have lower *estimated* candidate token cost at the assumed rates, but neither the original validation nor the supplementary follow-up establishes a complete-run or provider-billed cost saving.
