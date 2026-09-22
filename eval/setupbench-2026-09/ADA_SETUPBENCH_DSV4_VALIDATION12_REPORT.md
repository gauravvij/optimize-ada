# Ada × SetupBench: 1200-second paired validation — DeepSeek V4.1 Flash

This is the **same 1200-second, 36-pair validation protocol** as the GLM run
([`ADA_SETUPBENCH_VALIDATION_1200S_PARALLEL3_REPORT.md`](ADA_SETUPBENCH_VALIDATION_1200S_PARALLEL3_REPORT.md)),
re-run with Ada pointed at **`deepseek/deepseek-v4.1-flash`** instead of `z-ai/glm-5.3-flash`.
The candidate, SetupBench split, timeouts, concurrency, and seed are unchanged, so the two runs are
directly comparable.

## Direct outcome

The frozen Ada candidate **did not improve SetupBench pass rate** under DeepSeek V4.1 Flash: both
versions passed **26/36 attempts (72.2%)**. They each won **seven** discordant pairs — a perfectly
symmetric split. The candidate had descriptively shorter attempt durations and fewer reported tokens
on comparable pairs, but the run does **not** establish a candidate-specific cost saving or a robust
task-level speed gain.

| Measure | Original Ada | Frozen candidate | Candidate − baseline |
|---|---:|---:|---:|
| Grader passes | 26/36 (72.2%) | 26/36 (72.2%) | 0/36 (0.0 pp) |
| Ada timeouts | 6/36 (16.7%) | 4/36 (11.1%) | −2/36 (−5.6 pp) |
| Sum of attempt durations | 21,464.139 s | 19,182.156 s | −2,281.983 s (−10.63%) |
| Mean attempt duration | 596.226 s | 532.838 s | −63.388 s |
| Max attempt duration | 1,211.884 s | 1,225.931 s | +14.047 s |
| Tasks passed in at least 2 of 3 repetitions | 9/12 | 9/12 | 0/12 |

The duration sum is **aggregate per-attempt wall time**, including container launch, Ada execution,
grading, and cleanup — not just Ada runtime, elapsed validation-job time, or billed cost. Because
attempts ran concurrently, it cannot be interpreted as time saved by the validation job.

## Protocol and provenance

- SetupBench **validation12** split: the same 12 tasks, each repeated three times for each variant;
  **36 matched pairs / 72 final attempts**. All 72 final attempts are marked valid.
- Within a task/repetition pair, original and candidate ran simultaneously. Up to three pairs ran at
  once (up to six Ada attempts). Task order was randomized per repetition with seed `20260904`.
- Ada attempt limit: **1200 s**; grader limit: **600 s**. Model used by Ada:
  **`deepseek/deepseek-v4.1-flash`**.
- SetupBench commit: `041a412f01348c2a6f8b1b6a910138fe01885aee`. Both variants share Ada commit
  `0c5e1da7342ff86147b217a09c243cf17bf6c50d`; baseline tracked-diff SHA-256 is
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` (clean), candidate tracked-diff
  SHA-256 is `9e6a3fe04725f3c3ca43b5fcfcd53bde07f8fbbffc58d7e80793f6ffb408bd4a` (frozen candidate).
- Published, trace-free [compact evidence](ADA_SETUPBENCH_DSV4_VALIDATION12_COMPACT.json) contains
  every quantitative row; the full raw file remains in the autoresearch workspace and is pinned by
  SHA-256 below. The run-wide billing observation spans two segments totalling **$7.181121** key-wide.

This is a new **1200 s, concurrent** validation under a different model. It is **not** a repetition
of the GLM protocol and must not be pooled with it.

## Paired quality

| Repetition | Original passes | Candidate passes | Difference | Original timeouts | Candidate timeouts |
|---|---:|---:|---:|---:|---:|
| 1 | 11/12 | 6/12 | −5 | 1/12 | 4/12 |
| 2 | 8/12 | 10/12 | +2 | 2/12 | 0/12 |
| 3 | 7/12 | 10/12 | +3 | 3/12 | 0/12 |
| **Total** | **26/36** | **26/36** | **0** | **6/36** | **4/36** |

| Matched-pair outcome | Count |
|---|---:|
| Both pass | 19 |
| Candidate passes, baseline fails | 7 |
| Baseline passes, candidate fails | 7 |
| Both fail | 3 |
| Unadjusted attempt-level exact McNemar p-value for pass discordance | 1.000 |
| Baseline-only timeout / candidate-only timeout / both timeout | 5 / 3 / 1 |

The 36 observations are repeated runs of only **12 distinct tasks**, not 36 independent benchmark
problems. The paired p-value is a descriptive calculation, **not** a valid 36-independent-pairs
significance test. The point estimate itself is a tie, so this run gives no evidence of a quality
improvement. The pinned SetupBench harness treats the grader output marker `Setup successful` as a
pass for non-dependency tasks even if the success command exits nonzero; dependency tasks require
exit code 0. Both variants were scored by the same rule.

## Per-task outcomes

`P` = grader pass; `F` = completed but failed; `T` = Ada timeout. Letters are repetitions 1, 2, 3.

| SetupBench task | Original Ada | Frozen candidate |
|---|:---:|:---:|
| microsoft-azure-pipelines-tasks-bfcd4b2 | PFT | TFP |
| prometheus-bd5b2ea | PPP | FPP |
| fsspec-filesystem_spec-3ff5fca | PFP | PPP |
| dishait-tov-template-39c0898 | PPP | PPP |
| hackmdio-codimd-f00df50 | PTT | TPP |
| whisper-517a43e | PPF | PPP |
| wagtail-wagtail-28fcd01 | TTT | TPP |
| deps-ultimate-frontrunning-bot-449d6 | PPP | PPP |
| deps-gatsby-plugin-intl-2b7ac | PPP | TPP |
| dbsetup-mongodb-2 | PPP | PPF |
| dbsetup-mysql-2 | PPF | FFF |
| bgsetup-filewatcher-daemon-2 | PPP | PPP |

Notable: the candidate **loses** where the baseline is strong (`dbsetup-mysql-2` 2/3→0/3,
`prometheus` 3/3→2/3, `dbsetup-mongodb-2` 3/3→2/3) but **wins** on the two hardest, timing-sensitive
tasks (`wagtail` 0/3→2/3, `hackmdio` 1/3→2/3). This is consistent with a watchdog interaction: the
frozen candidate adds a model-wait watchdog (baseline has none), which can convert a baseline
timeout into a candidate pass on tasks where the model stalls, while the candidate's own reasoning
overhead can cost it elsewhere.

## Duration and turns

| Paired duration measure | Result |
|---|---:|
| Candidate faster, all pairs | 24/36 |
| Median candidate − baseline, all pairs | −103.622 s |
| Mean candidate − baseline, all pairs | −63.388 s |
| Pairs with neither variant timed out | 27/36 |
| Candidate faster in neither-timeout pairs | 19/27 |
| Median candidate − baseline in neither-timeout pairs | −144.305 s |

Ada execution is time-limited, so comparisons involving a timeout are censored; total attempt
duration can still exceed 1200 seconds because it includes harness work. The neither-timeout subset
still favors the candidate descriptively.

Turn counts are comparable only when **both** attempts returned terminal usage. That holds for
**23/36 pairs**. On those pairs, baseline recorded **436 turns** versus candidate **307 turns**
(−129, or −29.6%). A missing terminal result must not be interpreted as zero turns.

## Tokens and cost

Terminal token usage exists for **36/36 baseline** and **36/36 candidate** attempts, with **23/36
pairs** reporting it on both sides. The following comparisons use only those 23 matched pairs.

| Reported token measure | Original Ada | Frozen candidate | Candidate / baseline |
|---|---:|---:|---:|
| Input tokens | 2,458,856 | 1,711,536 | 0.6961 |
| Output tokens | 128,584 | 93,525 | 0.7273 |
| Cache-read tokens | 4,441,632 | 2,335,680 | 0.5259 |
| Input + output + cache-read | 7,029,072 | 4,140,741 | 0.5891 |
| Median per-pair total-token ratio | — | — | 0.6098 |

These are observed token counts on a selected subset, **not a 41% price reduction**: cache-read
tokens can be billed differently from input/output tokens, 13 pairs lack comparable terminal usage,
and a token ratio is not a bill.

The OpenRouter key-wide billed-usage counter increased **$7.181121** across the two run segments
(phase 1 `$3.9638615`, phase 2 `$3.21725933`). Baseline and candidate requests overlapped, as did up
to three pairs, so per-attempt key-usage deltas overlap and **must not be summed or assigned to a
variant**. There is no defensible candidate-versus-baseline dollar-cost result from this run. The
key-wide delta also cannot rule out any other use of the same key during that interval.

## Model attribution (no silent fallback)

The injected model id is **`deepseek/deepseek-v4.1-flash`** in both arms, via the same harness code
path (`-e ANTHROPIC_MODEL=…`). Evidence from the raw result JSON:

- `deepseek/deepseek-v4.1-flash` appears **120** times.
- `canonicalModel: "deepseek/deepseek-v4.1-flash"` appears **60** times (one per completed agent run).
- Fallback leakage: `claude-opus` 0, `claude-haiku` 0, `z-ai` 0, `glm-5.3-flash` 0,
  `deepseek-v4-flash` 0, `deepseek-v4-flash-latest` 0.
- `unrecognized_model` warnings: **0**.

## Run-stability note

The first launch aborted at 22/36 pairs with
`RuntimeError: persistent LLM API error for task=whisper-517a43e variant=baseline`. This was a
**transient upstream API error** under six-way concurrency, not a key/credit problem: the OpenRouter
key was healthy (≈$47.62 remaining, not free tier) and a live probe of the model returned HTTP 200
`PONG` immediately after. The harness aborts the whole run when a variant hits
`terminal_reason:"api_error"` on all three infrastructure retries. Re-running with `--resume`
retained the 44 already-completed variant results and finished the remaining 14 pairs cleanly. No
`terminal_reason:"api_error"` string persisted into the saved JSON and no row is invalid.

## Conclusion

At this 1200-second limit under DeepSeek V4.1 Flash, the frozen candidate **ties original Ada on
grader success (26/36 each)**, with a symmetric 7-vs-7 discordant split. It shows descriptive
reductions in duration, timeouts, turns, and measured tokens, with coverage and censoring
limitations. The measured subset has lower *estimated* candidate token cost, but this run does not
establish a complete-run or provider-billed cost saving.

**Cross-model note:** this 26/36-vs-26/36 tie **matches the GLM 1200-second validation exactly**
(26/36 both arms). Swapping the model from `z-ai/glm-5.3-flash` to `deepseek/deepseek-v4.1-flash`
did not change the outcome, and the candidate's descriptive efficiency edge persists under both
models. The 1-task DeepSeek smoke signal (candidate looked clearly better) did **not** generalize —
confirming the smoke was not representative and the full run was necessary.

## Evidence

- [Compact, trace-free metrics for all 72 attempts](ADA_SETUPBENCH_DSV4_VALIDATION12_COMPACT.json)
- Full raw file (workspace): `examples/SETUPBENCH_ADA_DSV4_VALIDATION12_RAW.json`, SHA-256
  `b6295e852d67339df8e274dff8ea7b1da44f259c4969e66a8467284519c5eb3e`
- Root-cause / model-validity investigation: `examples/SETUPBENCH_ADA_DSV4_BASELINE_ROOTCAUSE.md`
- GLM 1200-second validation (same protocol, different model):
  [report](ADA_SETUPBENCH_VALIDATION_1200S_PARALLEL3_REPORT.md) ·
  [compact](ADA_SETUPBENCH_VALIDATION_1200S_COMPACT.json)