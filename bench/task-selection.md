# Terminal-Bench 2.0 — 10-Task Selection (Fastest Subset)

**Dataset:** `terminal-bench/terminal-bench-2` (89 tasks, resolved via `harbor dataset download terminal-bench/terminal-bench-2` → `bench/terminal-bench-2/`)

**Difficulty distribution:** 4 easy / 55 medium / 30 hard

## Selection rule

Rank all 89 tasks by:
1. `difficulty` ascending (easy → medium → hard) — from `[metadata].difficulty` in each `task.toml`
2. `expert_time_estimate_min` ascending — from `[metadata].expert_time_estimate_min`
3. `agent.timeout_sec` ascending (tie-break) — from `[agent].timeout_sec`

Take the first 10. Script: `bench/select_tasks.py` (deterministic, no randomness).

## Selected tasks (in ranked order)

| # | Task | Difficulty | Expert min | Agent timeout (s) | Verifier timeout (s) | Category | Docker image |
|---|------|-----------|-----------:|------------------:|---------------------:|----------|--------------|
| 1 | fix-git | easy | 5 | 900 | 900 | software-engineering | alexgshaw/fix-git:20251031 |
| 2 | prove-plus-comm | easy | 5 | 900 | 900 | software-engineering | alexgshaw/prove-plus-comm:20251031 |
| 3 | cobol-modernization | easy | 20 | 900 | 900 | software-engineering | alexgshaw/cobol-modernization:20251031 |
| 4 | overfull-hbox | easy | 60 | 750 | 750 | debugging | alexgshaw/overfull-hbox:20251031 |
| 5 | crack-7z-hash | medium | 5 | 900 | 900 | security | alexgshaw/crack-7z-hash:20251031 |
| 6 | raman-fitting | medium | 5 | 900 | 900 | scientific-computing | alexgshaw/raman-fitting:20251031 |
| 7 | mteb-leaderboard | medium | 5 | 3600 | 3600 | data-science | alexgshaw/mteb-leaderboard:20251031 |
| 8 | kv-store-grpc | medium | 15 | 900 | 900 | software-engineering | alexgshaw/kv-store-grpc:20251031 |
| 9 | pytorch-model-recovery | medium | 15 | 900 | 900 | model-training | alexgshaw/pytorch-model-recovery:20251031 |
| 10 | constraints-scheduling | medium | 15 | 1200 | 1200 | personal-assistant | alexgshaw/constraints-scheduling:20251031 |

All 10 tasks have `allow_internet = true` in `[environment]`.

**Notes:**
- All 4 easy tasks in the dataset are included (there are only 4).
- `mteb-leaderboard` has a 3600s agent timeout (the only long-timeout task in the set) — it ranks in because its `expert_time_estimate_min` is 5. It is kept per the deterministic rule; its wall-clock cost is bounded by the agent's own behavior.
- First 11–20 alternates (if a task proves unrunnable): mteb-retrieve, hf-model-inference, merge-diff-arc-agi-task, nginx-request-logging, openssl-selfsigned-cert, polyglot-c-py, vulnerable-secret.

## Harbor task-filter CLI flag

Restrict a run to specific tasks with **`--include-task-name` / `-i`** (repeatable, supports glob patterns), e.g.:

```bash
harbor run -d terminal-bench/terminal-bench-2 \
  -i fix-git -i prove-plus-comm -i cobol-modernization -i overfull-hbox \
  -i crack-7z-hash -i raman-fitting -i mteb-leaderboard -i kv-store-grpc \
  -i pytorch-model-recovery -i constraints-scheduling \
  -a oracle -n 4 -o results-oracle-smoke
```

(Companion flag: `-x/--exclude-task-name`; `-l/--n-tasks` caps count after filters.)
