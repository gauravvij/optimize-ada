# deepseek/deepseek-v4.1-flash against deepseek/deepseek-v4-flash: the same two builds on the same 81 tasks

One attempt per task per cell, so this is descriptive. It separates 'the model' (compare the two models with the same build) from 'the code' (compare the two builds with the same model).

| Model / build | Attempts | Passed | Timed out | Interrupted by watchdog | Turns (mean) | Cost $ |
|---|---:|---:|---:|---:|---:|---:|
| deepseek/deepseek-v4-flash / baseline | 81 | 26 | 32 | 0 | 19.6 | 0.727 |
| deepseek/deepseek-v4-flash / best | 81 | 24 | 0 | 33 | 24.5 | 0.9295 |
| deepseek/deepseek-v4.1-flash / baseline | 81 | 40 | 36 | 0 | 15.9 | 1.2818 |
| deepseek/deepseek-v4.1-flash / best | 81 | 49 | 0 | 36 | 15.8 | 1.245 |

## Paired comparisons (gained = only the second passed, lost = only the first passed)

| Comparison | Pairs | First passed | Second passed | Gained | Lost | exact McNemar p |
|---|---:|---:|---:|---:|---:|---:|
| deepseek/deepseek-v4-flash: best vs baseline | 81 | 26 | 24 | 6 | 8 | 0.7905 |
| deepseek/deepseek-v4.1-flash: best vs baseline | 80 | 40 | 49 | 14 | 5 | 0.0636 |
| baseline: deepseek/deepseek-v4.1-flash vs deepseek/deepseek-v4-flash | 80 | 26 | 40 | 16 | 2 | 0.0013 |
| best: deepseek/deepseek-v4.1-flash vs deepseek/deepseek-v4-flash | 81 | 24 | 49 | 25 | 0 | 0.0 |

Effect of the best build's changes (best minus baseline passes): -2 on deepseek/deepseek-v4-flash, +9 on deepseek/deepseek-v4.1-flash.
