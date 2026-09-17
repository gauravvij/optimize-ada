# Ada × SetupBench: direct outcome

## Evaluation

| Value | Result |
|---|---:|
| Validation tasks | 12 |
| Repetitions | 3 |
| Variants | 2 |
| Total attempts | 72 |
| Matched pairs | 36 |
| Ada timeout per attempt | 900 s |
| Grader timeout per attempt | 600 s |
| Valid final attempts | 72/72 |
| Invalid final attempts | 0/72 |

## Passes

| Repetition | Original Ada | Frozen candidate | Difference |
|---|---:|---:|---:|
| 1 | 6/12 | 8/12 | +2 |
| 2 | 8/12 | 9/12 | +1 |
| 3 | 9/12 | 7/12 | −2 |
| **Total** | **23/36 (63.9%)** | **24/36 (66.7%)** | **+1/36 (+2.8 pp)** |

| Paired quality value | Result |
|---|---:|
| Candidate-only passes | 3 |
| Baseline-only passes | 2 |
| Both pass | 21 |
| Both fail | 10 |
| Exact paired McNemar p-value | 1.000 |
| Tasks passed in at least 2/3 repetitions: baseline | 8/12 |
| Tasks passed in at least 2/3 repetitions: candidate | 8/12 |

## Per-task outcomes

`P` = pass. `F` = completed without timeout but failed grader. `T` = Ada timeout. Outcomes are repetitions 1, 2, 3.

| Task | Original Ada | Frozen candidate | Baseline passes | Candidate passes |
|---|:---:|:---:|---:|---:|
| bgsetup-filewatcher-daemon-2 | PPP | PPP | 3/3 | 3/3 |
| dbsetup-mongodb-2 | PPP | PPP | 3/3 | 3/3 |
| dbsetup-mysql-2 | FPP | PPF | 2/3 | 2/3 |
| deps-gatsby-plugin-intl-2b7ac | TPP | PPP | 2/3 | 3/3 |
| deps-ultimate-frontrunning-bot-449d6 | PPP | PPP | 3/3 | 3/3 |
| dishait-tov-template-39c0898 | PPP | PPP | 3/3 | 3/3 |
| fsspec-filesystem_spec-3ff5fca | TTF | FFF | 0/3 | 0/3 |
| hackmdio-codimd-f00df50 | FTP | TFT | 1/3 | 0/3 |
| microsoft-azure-pipelines-tasks-bfcd4b2 | TTT | TTT | 0/3 | 0/3 |
| prometheus-bd5b2ea | PPP | PPP | 3/3 | 3/3 |
| wagtail-wagtail-28fcd01 | TTT | TPT | 0/3 | 1/3 |
| whisper-517a43e | PPP | PPP | 3/3 | 3/3 |

## Timeouts

| Repetition | Original Ada | Frozen candidate | Difference |
|---|---:|---:|---:|
| 1 | 4/12 | 3/12 | −1 |
| 2 | 4/12 | 1/12 | −3 |
| 3 | 2/12 | 3/12 | +1 |
| **Total** | **10/36 (27.8%)** | **7/36 (19.4%)** | **−3/36 (−8.3 pp)** |

| Paired timeout value | Result |
|---|---:|
| Baseline-only timeouts | 5 |
| Candidate-only timeouts | 2 |
| Exact paired timeout McNemar p-value | 0.453125 |

## Duration

| Value | Original Ada | Frozen candidate | Difference |
|---|---:|---:|---:|
| Sum of total attempt durations | 19,553.258 s | 16,143.215 s | −3,410.043 s |
| Sum of total attempt durations | 5.431 h | 4.484 h | −0.947 h |
| Relative aggregate duration | 100% | 82.56% | −17.44% |

| Paired duration value | Result |
|---|---:|
| Candidate faster, all pairs | 30/36 |
| Median candidate − baseline duration, all pairs | −51.114 s |
| Mean candidate − baseline duration, all pairs | −94.723 s |
| Pairs where neither variant timed out | 24/36 |
| Candidate faster where neither timed out | 22/24 |
| Median candidate − baseline duration, neither timed out | −78.819 s |
| Mean candidate − baseline duration, neither timed out | −109.064 s |
| Tasks with lower candidate median duration across 3 repetitions | 9/12 |
| Two-sided task-level sign-test p-value | 0.145996 |

## Turns

| Value | Original Ada | Frozen candidate | Difference |
|---|---:|---:|---:|
| Sum of recorded turns | 543 | 449 | −94 |
| Pairs with turn counts reported for both variants | 21/36 | 21/36 | — |
| Pairs with fewer candidate turns | — | 20/21 | — |
| Median candidate − baseline turns | — | −8 | — |
| Mean candidate − baseline turns | — | −10.571 | — |

`turns=0` on a timeout or missing terminal result is unavailable data and is excluded from paired turn comparisons.

## Tokens

| Value | Result |
|---|---:|
| Pairs with token usage reported for both variants | 21/36 |
| Pairs with fewer candidate tokens | 18/21 |
| Median candidate/baseline total-token ratio | 0.4785 |
| Median relative token reduction | 52.15% |

Total tokens = reported input + output + cache-read tokens. Attempts without terminal usage are excluded.

## Development search

| Value | Result |
|---|---:|
| Development tasks | 12 |
| Maximum candidate experiments | 10 |
| Candidate experiments used | 10 |
| Initial recorded original-Ada development score | 4/12 |
| Best single recorded development score | 10/12 |
| Retained experiment numbers | 4, 7 |
| Experiment 4 independent confirmation | Failed |
| Experiment 7 independent confirmation | Not completed |
| Experiment 10 | Failed before evaluation: provider output-length truncation |
| Stop condition | Maximum experiments reached |

## Direct conclusion

| Claim | Result |
|---|---|
| Demonstrated accuracy improvement | No |
| Accuracy point estimate | Candidate +1/36 passes |
| Task-majority accuracy | Tie: 8/12 vs 8/12 |
| Demonstrated statistically significant pass-rate improvement | No |
| Descriptive aggregate duration improvement | Candidate −17.44% |
| Descriptive timeout improvement | Candidate −3 timeouts |
| Descriptive turn improvement | Candidate −94 recorded turns |
| Descriptive token improvement | Candidate median ratio 0.4785 on 21 comparable pairs |
| Complete 93-task evaluation for this frozen candidate | Not run |
