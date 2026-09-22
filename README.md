# Ada on SetupBench: 1200-second validation

This branch contains a frozen Ada candidate produced by Neo using Autoresearcher and its paired evaluation against original Ada. The **1200-second validation found no accuracy improvement**: both versions passed **26/36** attempts (72.2%). The candidate was descriptively faster and used fewer tokens on the attempts with comparable telemetry; a complete-run or provider-billed cost saving was **not** established.

The same protocol was then **re-run with a second model** (`deepseek/deepseek-v4.1-flash` instead of `z-ai/glm-5.3-flash`) to check whether the result was model-specific. It was not: the DeepSeek run reproduced the **exact same 26/36-vs-26/36 tie** (see [DeepSeek validation](#deepseek-v41-flash-validation-second-model) below).

## What was optimized

Neo searched on 12 fixed SetupBench development tasks, with a 10-experiment budget. Autoresearcher changed Ada, ran candidate/control comparisons, and retained two mechanisms: experiment 4's wall-clock guidance and longer Bash timeouts, and experiment 7's tool-aware recovery from a stalled model response. The final candidate was frozen before evaluation on 12 **separate** validation tasks. Experiment 4's initial gain failed its independent development confirmation; experiment 7 had no independent confirmation, so neither development score is a validated quality claim. The exact changes are in [the candidate patch](eval/setupbench-2026-09/frozen-candidate.patch) and the frozen source is in [ada/](ada/).

| Pinned component | Value |
|---|---|
| Ada evaluation base (used by original arm) | `0c5e1da7342ff86147b217a09c243cf17bf6c50d` |
| Candidate | Same Ada commit plus tracked-diff SHA-256 `9e6a3fe04725f3c3ca43b5fcfcd53bde07f8fbbffc58d7e80793f6ffb408bd4a` |
| SetupBench commit | `041a412f01348c2a6f8b1b6a910138fe01885aee` |
| Model used by Ada (primary run) | `z-ai/glm-5.3-flash` via OpenRouter |
| Model used by Ada (second run) | `deepseek/deepseek-v4.1-flash` via OpenRouter |

## 1200-second evaluation protocol

Each of the 12 held-out SetupBench tasks ran three times for original Ada and three times for the frozen candidate: **36 matched pairs, 72 attempts, 72/72 valid records**. Baseline and candidate ran concurrently within each pair; at most three pairs (six attempts) were active together. Ada had **1200 seconds** per attempt and the grader **600 seconds**. Fresh containers and the pinned SetupBench graders determined pass/fail.

## Quantitative outcome: all 36 original pairs

| Repetition | Original passes | Candidate passes | Original timeouts | Candidate timeouts |
|---|---:|---:|---:|---:|
| 1 | 7/12 | 9/12 | 4/12 | 2/12 |
| 2 | 9/12 | 9/12 | 2/12 | 0/12 |
| 3 | 10/12 | 8/12 | 1/12 | 3/12 |
| **Total** | **26/36** | **26/36** | **7/36** | **5/36** |

| Measure | Original Ada | Frozen candidate | Difference / interpretation |
|---|---:|---:|---|
| Grader passes | 26/36 (72.2%) | 26/36 (72.2%) | Tie; 0 percentage points |
| Tasks passing at least 2 of 3 runs | 9/12 | 8/12 | Candidate −1 task |
| Ada timeouts | 7/36 | 5/36 | Candidate −2 |
| Sum of attempt durations | 23,814.406 s | 19,362.968 s | Candidate −4,451.438 s (−18.69%) |
| Median attempt duration | 537.147 s | 417.536 s | Candidate ≈−119.6 s |

Of the 36 matched pairs, **23 both passed, 3 candidate-only passed, 3 baseline-only passed, and 7 both failed**. The candidate was faster in **23/36** pairs (median paired duration difference **−101.795 s**). Neither side timed out in **27** pairs; the candidate was faster in **17/27** of those. Across the 12 distinct tasks, the candidate had a lower median duration on **8/12**. Duration includes container setup, execution, grading, and cleanup, and timeout durations are censored. Because attempts ran concurrently, summed durations are **not** validation-job wall-clock savings. Repetitions of the same 12 tasks are not 36 independent benchmark problems.

## Turns, tokens, and estimated cost

Terminal token usage was available for **28/36 baseline** attempts and **27/36 candidate** attempts, but on **both** sides of only **24/36 pairs**. The following turn, token, and cost comparison uses **only those 24 matched original pairs**; missing telemetry is not zero usage.

| Original 24 matched-usage pairs | Original Ada | Frozen candidate | Candidate / baseline |
|---|---:|---:|---:|
| Agent turns | 693 | 432 | 0.6234 (−37.7%) |
| Input tokens | 1,542,588 | 960,527 | 0.6227 |
| Output tokens | 253,448 | 142,486 | 0.5622 |
| Cache-read tokens | 10,011,840 | 3,943,936 | 0.3939 |
| Total reported tokens | 11,807,876 | 5,046,949 | 0.4274 |
| Estimated token cost at rates below | $0.395080 | $0.200184 | 0.5067 (−49.33%) |

The candidate used fewer turns in **20/24** pairs and fewer total reported tokens in **21/24**; the median per-pair total-token ratio was **0.4617**. A total-token ratio is not a cost ratio because cache reads have a different assumed price.

For estimated cost, the specified illustrative rates were **$0.09 per million input**, **$0.30 per million output**, and **$0.018 per million cache-read tokens**. Three fresh pairs were rerun *only to obtain telemetry*: one Prometheus pair and two Whisper pairs. All **6/6** fresh attempts were valid, passed, avoided timeout, and returned usage. They did **not** replace any of the original 36 quality pairs.

| Measured sample | Baseline estimated cost | Candidate estimated cost | Candidate difference |
|---|---:|---:|---:|
| Original validation: 24 comparable pairs | $0.395080 | $0.200184 | −$0.194896 (−49.33%) |
| Separate three-pair follow-up | $0.040869 | $0.024488 | −$0.016381 (−40.08%) |
| Combined measured sample: 24 original + 3 fresh | $0.435949 | $0.224672 | −$0.211277 (−48.46%) |

The combined row is **not 27/36 original pairs**. The original 12 pairs without comparable usage still lack it; nine of those involved an Ada timeout. The follow-up estimates also exclude invalid provider-limit retries and an aborted disk-protection attempt, whose spend cannot be allocated here. The OpenRouter key-wide billed-usage counter rose **$13.52195424** over the original run interval, but concurrent requests and possible other key activity make that figure **unattributable by variant**. Neither it nor the measured subset establishes full-run, provider-billed savings.

## DeepSeek V4.1 Flash validation (second model)

To test whether the tie was specific to `z-ai/glm-5.3-flash`, the **identical 1200-second protocol**
was re-run with Ada pointed at **`deepseek/deepseek-v4.1-flash`** (same frozen candidate, same
SetupBench split, same timeouts, concurrency, and seed). The result was **the same tie**:

| Measure | Original Ada | Frozen candidate | Difference / interpretation |
|---|---:|---:|---|
| Grader passes | 26/36 (72.2%) | 26/36 (72.2%) | Tie; 0 percentage points |
| Ada timeouts | 6/36 | 4/36 | Candidate −2 |
| Sum of attempt durations | 21,464.139 s | 19,182.156 s | Candidate −2,281.983 s (−10.63%) |
| Mean attempt duration | 596.226 s | 532.838 s | Candidate −63.388 s |

Of the 36 matched pairs, **19 both passed, 7 candidate-only passed, 7 baseline-only passed, and 3
both failed** — a perfectly symmetric discordant split (descriptive McNemar p = 1.000). The candidate
was faster in **24/36** pairs (median paired duration difference **−103.622 s**). All 72 attempts were
valid, with 0 harness errors and 0 agent errors.

| DeepSeek 23 matched-usage pairs | Original Ada | Frozen candidate | Candidate / baseline |
|---|---:|---:|---:|
| Agent turns | 436 | 307 | 0.7041 (−29.6%) |
| Input tokens | 2,458,856 | 1,711,536 | 0.6961 |
| Output tokens | 128,584 | 93,525 | 0.7273 |
| Cache-read tokens | 4,441,632 | 2,335,680 | 0.5259 |
| Total reported tokens | 7,029,072 | 4,140,741 | 0.5891 |

The OpenRouter key-wide billed-usage counter rose **$7.181121** across the two run segments
(phase 1 `$3.9638615`, phase 2 `$3.21725933`); as with the GLM run this is **unattributable by
variant** because baseline and candidate requests overlapped. Model attribution was verified with no
silent fallback: `deepseek/deepseek-v4.1-flash` appears 120×, `canonicalModel` 60×, and 0 occurrences
of any fallback model id.

**Interpretation:** the candidate's tie is **not model-specific** — it reproduces under both models,
and the candidate's descriptive efficiency edge (fewer turns, tokens, timeouts, shorter durations)
persists under both. The candidate **loses** where the baseline is strong (`dbsetup-mysql-2`
2/3→0/3, `prometheus` 3/3→2/3) but **wins** on the two hardest timing-sensitive tasks (`wagtail`
0/3→2/3, `hackmdio` 1/3→2/3), consistent with the candidate's model-wait watchdog converting
baseline timeouts into passes while its own reasoning overhead costs it elsewhere.

## Conclusion and evidence

The frozen candidate **tied original Ada on SetupBench success at the 1200-second limit** — under
**both** models tested (`z-ai/glm-5.3-flash` and `deepseek/deepseek-v4.1-flash`), each 26/36 vs 26/36.
It showed lower aggregate duration and timeout counts, and lower turns, tokens, and *estimated* cost
in the telemetry-complete subsets. These are descriptive efficiency results with missing-usage and
repeated-task limitations, not a proven general quality or total-bill improvement. The complete
93-task SetupBench set was **not** run for this candidate.

- [Detailed 1200-second report (GLM), including per-task outcomes and caveats](eval/setupbench-2026-09/ADA_SETUPBENCH_VALIDATION_1200S_PARALLEL3_REPORT.md)
- [Compact, trace-free metrics for all 72 GLM original and 6 follow-up attempts](eval/setupbench-2026-09/ADA_SETUPBENCH_VALIDATION_1200S_COMPACT.json)
- [Detailed 1200-second report (DeepSeek V4.1 Flash)](eval/setupbench-2026-09/ADA_SETUPBENCH_DSV4_VALIDATION12_REPORT.md)
- [Compact, trace-free metrics for all 72 DeepSeek attempts](eval/setupbench-2026-09/ADA_SETUPBENCH_DSV4_VALIDATION12_COMPACT.json)
- [DeepSeek baseline root-cause & model-validity investigation](eval/setupbench-2026-09/ADA_SETUPBENCH_DSV4_BASELINE_ROOTCAUSE.md)
