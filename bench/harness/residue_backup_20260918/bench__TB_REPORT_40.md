# Terminal-Bench 2.0 — 40-Task Comparison: Baseline (`df0c537`) vs Budget-Adaptive Best2

**Date:** 2026-09-07 · **Harness:** Harbor (`harbor run`) · **Adapter:** `bench/ada_agent.py` (`BaseInstalledAgent`) · **Model:** `z-ai/glm-5.3-flash` via OpenRouter (identical for both variants)

**Variants under test**
| Variant | Tarball | Agent state | Diff vs prior |
|---|---|---|---|
| baseline | `bench/ada-baseline.tgz` | git commit `df0c537` | — |
| best (prior 10-task run) | `bench/ada-best.tgz` | working tree: `agent/claude/agent.ts` + `agent/system-guidance.ts` (short-horizon) | — |
| **best2 (this run)** | `bench/ada-best2.tgz` | working tree + budget-adaptive `agent/system-guidance.ts` | vs `ada-best.tgz`: **exactly** `agent/system-guidance.ts` |

**Budget-adaptive guidance under test:** `systemGuidance()` reads `ADA_RUNNER_TIMEOUT_MS` (default 115000). Budget ≤ 300000 ms → byte-identical original short-horizon string. Budget > 300000 ms → long-budget variant stating the real time budget, Bash timeout scaled to `min(120000, budget/6)` ms, sustained commands allowed, efficiency wins kept, long-horizon discipline section. All 40 tasks here have agent timeouts 750–3600 s → `runner_cap_ms` 690000–3540000 → all runs used the **long-budget guidance** in the best2 arm (identical harness/env for both arms).

**Results provenance**
- Baseline: 10 original trials `bench/results-baseline/2026-09-07__14-32-12` + 30 fresh `bench/results-baseline-40/2026-09-07__18-32-07`.
- Best2: 8 pilot trials `bench/results-best2-pilot/2026-09-07__17-56-49` + 32 fresh `bench/results-best2-40/2026-09-07__20-12-31`.
- Pilot trials reused only because run conditions were identical to the 40-task run (variant=best2, `-n 4`, same per-task `agent.timeout_sec` → `runner_cap_ms` mapping — verified in per-trial `Ada run` log lines).
- All numbers below are cross-checked against `bench/parse_results.py` output on the four result dirs (merged table in `/tmp/merged40.json`).

---

## 1. Per-task results (all 40 tasks)

Reward 1.0 = verifier PASS, 0.0 = FAIL. `is_err` = Ada runner `is_error` (hard-cap kill → cost $0). **Reward is the pass signal** (a few trials graded PASS despite `is_err=True`, e.g. `build-cython-ext`).

| # | Task | Base reward | Base turns | Base cost $ | Best2 reward | Best2 turns | Best2 cost $ | Flip |
|---|------|------------:|-----------:|------------:|-------------:|------------:|-------------:|------|
| 1 | fix-git | 1.0 | 16 | 0.29 | 1.0 | 15 | 0.39 | — |
| 2 | prove-plus-comm | 1.0 | 8 | 0.20 | 1.0 | 6 | 0.08 | — |
| 3 | cobol-modernization | 0.0 | 44 | 0.00 | 0.0 | 42 | 0.00 | — |
| 4 | overfull-hbox | 0.0 | 56 | 0.00 | 0.0 | 61 | 0.00 | — |
| 5 | crack-7z-hash | 1.0 | 22 | 0.40 | 0.0 | 28 | 0.00 | **regress** |
| 6 | raman-fitting | 0.0 | 38 | 0.00 | 0.0 | 27 | 0.00 | — |
| 7 | mteb-leaderboard | 0.0 | 129 | 0.00 | 1.0 | 60 | 3.53 | **convert** |
| 8 | kv-store-grpc | 1.0 | 17 | 0.28 | 1.0 | 10 | 0.13 | — |
| 9 | pytorch-model-recovery | 1.0 | 10 | 0.43 | 1.0 | 21 | 0.83 | — |
| 10 | constraints-scheduling | 1.0 | 7 | 0.28 | 1.0 | 7 | 0.30 | — |
| 11 | mteb-retrieve | 1.0 | 24 | 0.57 | 0.0 | 11 | 0.27 | **regress** |
| 12 | hf-model-inference | 1.0 | 13 | 0.23 | 1.0 | 13 | 0.20 | — |
| 13 | merge-diff-arc-agi-task | 1.0 | 22 | 0.83 | 1.0 | 21 | 0.52 | — |
| 14 | nginx-request-logging | 1.0 | 13 | 0.18 | 1.0 | 13 | 0.23 | — |
| 15 | openssl-selfsigned-cert | 1.0 | 11 | 0.23 | 1.0 | 12 | 0.21 | — |
| 16 | polyglot-c-py | 0.0 | 17 | 1.21 | 0.0 | 13 | 1.17 | — |
| 17 | vulnerable-secret | 1.0 | 11 | 0.24 | 1.0 | 9 | 0.22 | — |
| 18 | break-filter-js-from-html | 1.0 | 11 | 0.24 | 1.0 | 21 | 0.98 | — |
| 19 | count-dataset-tokens | 1.0 | 12 | 0.24 | 1.0 | 9 | 0.17 | — |
| 20 | extract-elf | 0.0 | 26 | 0.00 | 1.0 | 16 | 0.55 | **convert** |
| 21 | git-leak-recovery | 1.0 | 18 | 0.24 | 1.0 | 15 | 0.29 | — |
| 22 | multi-source-data-merger | 1.0 | 10 | 0.30 | 1.0 | 8 | 0.22 | — |
| 23 | pytorch-model-cli | 0.0 | 48 | 0.00 | 1.0 | 25 | 0.78 | **convert** |
| 24 | qemu-alpine-ssh | 1.0 | 20 | 0.78 | 0.0 | 38 | 0.00 | **regress** |
| 25 | qemu-startup | 1.0 | 37 | 0.00 | 0.0 | 29 | 0.00 | **regress** |
| 26 | sanitize-git-repo | 1.0 | 28 | 0.39 | 1.0 | 22 | 0.42 | — |
| 27 | sqlite-with-gcov | 1.0 | 40 | 0.53 | 1.0 | 27 | 0.37 | — |
| 28 | tune-mjcf | 0.0 | 39 | 0.00 | 0.0 | 25 | 0.00 | — |
| 29 | code-from-image | 1.0 | 7 | 0.16 | 1.0 | 8 | 0.12 | — |
| 30 | financial-document-processor | 0.0 | 159 | 0.00 | 0.0 | 33 | 0.56 | — |
| 31 | custom-memory-heap-crash | 1.0 | 68 | 2.48 | 1.0 | 22 | 0.51 | — |
| 32 | dna-insert | 0.0 | 20 | 1.69 | 0.0 | 26 | 1.26 | — |
| 33 | reshard-c4-data | 1.0 | 90 | 6.12 | 1.0 | 72 | 3.01 | — |
| 34 | large-scale-text-editing | 1.0 | 11 | 0.36 | 1.0 | 14 | 0.54 | — |
| 35 | chess-best-move | 1.0 | 17 | 0.88 | 0.0 | 25 | 0.64 | **regress** |
| 36 | db-wal-recovery | 1.0 | 10 | 0.30 | 1.0 | 12 | 0.55 | — |
| 37 | regex-log | 1.0 | 11 | 1.26 | 1.0 | 8 | 1.17 | — |
| 38 | filter-js-from-html | 0.0 | 1 | 0.83 | 0.0 | 78 | 5.01 | — |
| 39 | build-cython-ext | 1.0 | 196 | 0.00 | 1.0 | 123 | 0.00 | — |
| 40 | gcode-to-text | 0.0 | 47 | 1.72 | 1.0 | 45 | 1.28 | **convert** |

---

## 2. Aggregates

| Metric | Baseline | Best2 | Δ |
|---|---|---|---|
| **Pass rate** | 28/40 (0.700) | 27/40 (0.675) | **−1 task (−0.025)** |
| Total turns | 1384 | 1070 | **−314 (−22.7%)** |
| Total cost (claude-reported $) | 23.91 | 26.54 | +2.63 (+11.0%) |
| Sum agent exec time | 25068 s (6.96 h) | 21311 s (5.92 h) | **−3757 s (−15.0%)** |
| Harbor wall-clock | 1h04m47s + 1h33m05s ≈ 2h38m | 28m19s + 1h24m51s ≈ 1h53m | −45 min |
| Hard-cap kills (`is_err=True`, $0) | 10 | 8 | −2 |
| Exceptions (infra) | 0 | 0 | — |

**Cost note:** `cost_usd` above is the claude-reported figure (model-usage based). Actual metered OpenRouter spend (GLM) is ~67× lower — see caveats §5.

**Efficiency on the 23 tasks BOTH variants passed:** turns 640 → 488 (**−23.8%**); claude-reported cost $15.83 → $11.48 (**−27.5%**).

---

## 3. Flip analysis (9 discordant pairs)

**Conversions (4): baseline FAIL → best2 PASS**
| Task | Baseline failure mode | Best2 mechanism |
|---|---|---|
| mteb-leaderboard | Hard-cap kill: 129 turns, hit 3541 s cap, $0 | PASS in 60 turns / 1579 s / $3.53. Long-horizon guidance (sustained commands allowed) enabled the pip/MTEB work the short-horizon guidance forbids. **Attribution caveat:** this task also passed under the prior *best* variant (32 turns/$1.68/927 s) — see §5. |
| extract-elf | Hard-cap kill: 26 turns, 841 s, $0 | PASS in 16 turns / 360 s / $0.55. Sustained commands + real-budget awareness let the agent finish the ELF extraction pipeline instead of stopping early. |
| pytorch-model-cli | Hard-cap kill: 48 turns, 841 s, $0 | PASS in 25 turns / 608 s / $0.78. Same mechanism (install/build allowed, longer per-command budget). |
| gcode-to-text | Completed but wrong: 47 turns, $1.72, reward 0 | PASS in 45 turns / $1.28. Marginal — same effort, better output; plausibly stochastic rather than guidance-driven. |

**Regressions (5): baseline PASS → best2 FAIL**
| Task | Best2 failure mode | Notes |
|---|---|---|
| crack-7z-hash | Hard-cap kill: 28 turns, 841 s, $0 | Baseline passed in 22 turns/$0.40. Same regression under prior *best* — this is the known crack-7z weakness of the optimized guidance, not new to best2. |
| qemu-alpine-ssh | Hard-cap kill: 38 turns, 841 s, $0 | Baseline passed in 20 turns/$0.78. Long-horizon run burned the budget in sustained QEMU debugging without converging. |
| qemu-startup | Hard-cap kill: 29 turns, 843 s, $0 | Baseline passed in 37 turns (is_err=True but reward 1.0 — verifier accepted despite runner error). Stochastic-ish flip. |
| mteb-retrieve | Completed but wrong: 11 turns, $0.27 | Baseline passed in 24 turns/$0.57. Best2 stopped far earlier — plausible premature-termination miss. |
| chess-best-move | Completed but wrong: 25 turns, $0.64 | Baseline passed in 17 turns/$0.88. Not a timeout; wrong move computed. |

**Same-outcome pairs:** 23 both-PASS, 8 both-FAIL.

Mechanism summary: the long-budget guidance converts ~hard-cap-kill tasks into passes when the task genuinely needs sustained commands (installs/builds/long pipelines) — 3 of the 4 conversions are exactly that pattern. But it also spends the larger budget less decisively on a few tasks that the short-horizon guidance would have wrapped up quickly (crack-7z-hash, qemu-alpine-ssh, mteb-retrieve). Net pass-rate effect on this sample: −1.

---

## 4. Paired significance

Discordant pairs: 4 conversions vs 5 regressions (n=9). Exact McNemar (two-sided binomial on discordant pairs, p = 2·P(X≤min(4,5)) under X~Bin(9, 0.5)): **p = 1.0000**. The observed outcome difference is entirely consistent with chance; there is **no statistically significant pass-rate difference** between baseline and best2 on these 40 tasks.

Efficiency deltas (−22.7% turns, −15.0% agent-exec time on all tasks; −23.8% turns / −27.5% cost on the 23 both-pass tasks) are directionally strong and consistent with the prior 10-task run (−30% turns, −2.2× wall-clock) but are **not** significance-tested here (no per-task paired variance model was pre-registered for turns/cost).

---

## 5. Claim, with honest caveats

**Claim:** On this 40-task Terminal-Bench 2.0 subset, the budget-adaptive variant (**best2**) shows **no pass-rate improvement over baseline** (27/40 vs 28/40, McNemar p=1.0) but a **consistent, material efficiency gain** (−22.7% turns, −15.0% agent-exec time overall; −23.8% turns and −27.5% claude-reported cost on the 23 tasks both pass). The long-budget guidance converts some hard-cap-kill failures into passes (extract-elf, pytorch-model-cli, mteb-leaderboard, gcode-to-text) at the cost of a comparable number of regressions on tasks where decisive early stopping mattered (crack-7z-hash, qemu-alpine-ssh, mteb-retrieve, chess-best-move, qemu-startup). **Recommendation: adopt as a throughput/cost optimization for long-horizon runs, not as a correctness improvement.** For correctness-critical use, prefer the short-horizon variant (baseline pass rate, byte-identical guidance preserved at budgets ≤ 300000 ms).

**Caveats**
1. **Credit-floor supersession:** the task constraint "keep OpenRouter credit > $250" is superseded — the key's monthly limit was externally changed 450 → 250 mid-run, unrelated to spend. Post-run `limit_remaining` = $117.74, `usage_monthly` = $132.26; actual metered spend for this whole 40-task campaign was only ~$2–3 (usage_monthly rose ~$2 across all runs). The `cost_usd` figures in this report are **claude-reported**, ~67× inflated vs actual GLM OpenRouter charges.
2. **mteb-leaderboard attribution:** its conversion to PASS is *not unique* to the budget-adaptive guidance — it also passed under the prior `best` variant (32 turns/$1.68/927 s). It is a genuine baseline→best2 conversion but cannot be attributed solely to the long-budget guidance change. (Only extract-elf, pytorch-model-cli, gcode-to-text are net-new vs the prior best run.)
3. **Task-selection bias:** the 40 tasks are the easy-first 40 of 89 (4 easy / 36 medium / 0 hard) by `expert_time_estimate_min`/`timeout_sec`. Results do not generalize to the 49 harder tasks (30 hard tasks excluded). Within the ranked 40 there is also a difficulty-gradient confound (ranks 1–10 easiest).
4. **Reward vs is_err:** several trials grade PASS despite the Ada runner reporting `is_error=True` (e.g. `build-cython-ext` reward 1.0 in both arms; `qemu-startup` baseline reward 1.0). Reward (verifier grade) is the pass signal used throughout; `is_err`/exec-span are reported separately for mechanism analysis.
5. **Single trial per task per variant:** no repetition; the flip set (±4/∓5) is within the noise band (McNemar p=1.0). Efficiency deltas come from single paired runs too.
6. **Cost model:** claude-reported cost tracks token volume, not the actual GLM billing; use the metered OpenRouter numbers for real spend (see caveat 1).
7. **Not all FAILs are timeouts:** of the 8 baseline-40 FAILs only 4 are hard-cap kills (extract-elf, financial-document-processor, pytorch-model-cli, tune-mjcf); dna-insert, filter-js-from-html, gcode-to-text, polyglot-c-py completed with real spend but wrong output. Labeling them uniformly as "timeouts" would be incorrect.

---

## 6. Reproduction

```
# per-variant runs (identical harness; only the tarball differs)
harbor run -d terminal-bench/terminal-bench-2 -a bench.ada_agent:AdaAgent \
  --ak variant=<baseline|best2> --ae OPENROUTER_API_KEY=$OR_KEY \
  -i terminal-bench/<task> ... -n 4 -o bench/results-<name> -y

# parse
python3 bench/parse_results.py bench/results-<name>/<timestamp>
```

Full 40-task `-i` lists are in the subtask execution records; task selection rationale in `bench/task-selection-40.md`.
