# How this folder was assembled

Sources, in order: `/home/azureuser/adaAgent/ada/runs/deepseek-v4.1-flash/r1`, `/home/azureuser/adaAgent/ada/runs/deepseek-v4.1-flash/r1_set41`, `/home/azureuser/adaAgent/ada/runs/deepseek-v4.1-flash/r1_retry`.

Rule: per build and per task, the first valid attempt is used. A later attempt replaces an earlier one only when the earlier
one was a harness error. Nothing is copied: `<build>/<task>` are symlinks into the source folders.

## baseline

81 tasks. Attempts taken from each source: `/home/azureuser/adaAgent/ada/runs/deepseek-v4.1-flash/r1` 40, `/home/azureuser/adaAgent/ada/runs/deepseek-v4.1-flash/r1_set41` 41, `/home/azureuser/adaAgent/ada/runs/deepseek-v4.1-flash/r1_retry` 0.
Harness errors still in the result (no valid attempt exists): none.

Attempts not used:

| Task | Source | Why |
|---|---|---|
| `pytesseract-df9fce0` | `/home/azureuser/adaAgent/ada/runs/deepseek-v4.1-flash/r1_retry` | task already had a valid attempt |

Model calls of unused attempts left out of the cost: 13, $0.0106.

## best

81 tasks. Attempts taken from each source: `/home/azureuser/adaAgent/ada/runs/deepseek-v4.1-flash/r1` 39, `/home/azureuser/adaAgent/ada/runs/deepseek-v4.1-flash/r1_set41` 41, `/home/azureuser/adaAgent/ada/runs/deepseek-v4.1-flash/r1_retry` 1.
Harness errors still in the result (no valid attempt exists): none.

Attempts not used:

| Task | Source | Why |
|---|---|---|
| `pytesseract-df9fce0` | `/home/azureuser/adaAgent/ada/runs/deepseek-v4.1-flash/r1` | harness error, replaced by a later valid attempt |

Model calls of unused attempts left out of the cost: 0, $0.0000.

