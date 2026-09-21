# deepseek/deepseek-v4.1-flash against deepseek/deepseek-v4-flash: the same two builds on the same 41 tasks

One attempt per task per cell, so this is descriptive. It separates 'the model' (compare the two models with the same build) from 'the code' (compare the two builds with the same model).

| Model / build | Attempts | Passed | Timed out | Interrupted by watchdog | Turns (mean) | Cost $ |
|---|---:|---:|---:|---:|---:|---:|
| deepseek/deepseek-v4-flash / baseline | 41 | 11 | 19 | 0 | 19.9 | 0.3543 |
| deepseek/deepseek-v4-flash / best | 41 | 11 | 0 | 18 | 25.9 | 0.4635 |
| deepseek/deepseek-v4.1-flash / baseline | 41 | 17 | 23 | 0 | 18.7 | 0.9698 |
| deepseek/deepseek-v4.1-flash / best | 41 | 26 | 0 | 14 | 16.3 | 0.8333 |

## Paired comparisons (gained = only the second passed, lost = only the first passed)

| Comparison | Pairs | First passed | Second passed | Gained | Lost | exact McNemar p |
|---|---:|---:|---:|---:|---:|---:|
| deepseek/deepseek-v4-flash: best vs baseline | 41 | 11 | 11 | 4 | 4 | 1.0 |
| deepseek/deepseek-v4.1-flash: best vs baseline | 41 | 17 | 26 | 10 | 1 | 0.0117 |
| baseline: deepseek/deepseek-v4.1-flash vs deepseek/deepseek-v4-flash | 41 | 11 | 17 | 8 | 2 | 0.1094 |
| best: deepseek/deepseek-v4.1-flash vs deepseek/deepseek-v4-flash | 41 | 11 | 26 | 15 | 0 | 0.0001 |

Effect of the best build's changes (best minus baseline passes): +0 on deepseek/deepseek-v4-flash, +9 on deepseek/deepseek-v4.1-flash.
