# deepseek/deepseek-v4.1-flash against deepseek/deepseek-v4-flash: the same two builds on the same 81 tasks

One attempt per task per cell, so this is descriptive. It separates 'the model' (compare the two models with the same build) from 'the code' (compare the two builds with the same model).

| Model / build | Attempts | Passed | Timed out | Interrupted by watchdog | Turns (mean) | Cost $ |
|---|---:|---:|---:|---:|---:|---:|
| deepseek/deepseek-v4-flash / baseline | 81 | 26 | 32 | 0 | 19.6 | 0.727 |
| deepseek/deepseek-v4-flash / best | 81 | 24 | 0 | 33 | 24.5 | 0.9295 |
| deepseek/deepseek-v4.1-flash / baseline | 81 | 34 | 41 | 0 | 17.4 | 1.6025 |
| deepseek/deepseek-v4.1-flash / best | 81 | 48 | 0 | 31 | 15.9 | 1.4256 |

## Paired comparisons (gained = only the second passed, lost = only the first passed)

| Comparison | Pairs | First passed | Second passed | Gained | Lost | exact McNemar p |
|---|---:|---:|---:|---:|---:|---:|
| deepseek/deepseek-v4-flash: best vs baseline | 81 | 26 | 24 | 6 | 8 | 0.7905 |
| deepseek/deepseek-v4.1-flash: best vs baseline | 81 | 34 | 48 | 16 | 2 | 0.0013 |
| baseline: deepseek/deepseek-v4.1-flash vs deepseek/deepseek-v4-flash | 81 | 26 | 34 | 13 | 5 | 0.0963 |
| best: deepseek/deepseek-v4.1-flash vs deepseek/deepseek-v4-flash | 81 | 24 | 48 | 27 | 3 | 0.0 |

Effect of the best build's changes (best minus baseline passes): -2 on deepseek/deepseek-v4-flash, +14 on deepseek/deepseek-v4.1-flash.
