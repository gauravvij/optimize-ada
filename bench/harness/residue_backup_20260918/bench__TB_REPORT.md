# Terminal-Bench 2.0 Subset — Ada Baseline vs Optimized Comparison Report

> **▶ 40-task comparison (baseline `df0c537` vs budget-adaptive **best2**): see [`TB_REPORT_40.md`](./TB_REPORT_40.md).** This 10-task report is the earlier, smaller-scale comparison; the 40-task report supersedes it for pass-rate and efficiency conclusions.

**Date:** 2026-09-07
**Harness:** Harbor (`harbor run`), custom `BaseInstalledAgent` adapter (`bench/ada_agent.py`, variant `bench.ada_agent:AdaAgent`)
**Dataset:** `terminal-bench/terminal-bench-2` (89 tasks; 10-task subset selected for speed — see `bench/task-selection.md`)
**Model (both variants):** `z-ai/glm-5.3-flash` via OpenRouter (`ANTHROPIC_BASE_URL=https://openrouter.ai/api`)
**Runner:** `node scripts/autoresearch-run-agent.ts` with `ADA_RUNNER_TIMEOUT_MS = (agent_timeout_sec − 60) × 1000`

| Config | Source | Tarball |
|---|---|---|
| **Baseline** | git commit `df0c537` (agent files restored from `git show df0c537`) | `bench/ada-baseline.tgz` |
| **Optimized ("best")** | current working tree (`agent/claude/agent.ts` +15, `agent/system-guidance.ts` +29/−10) | `bench/ada-best.tgz` |

The two variants differ in **exactly** those two files (verified with `diff -rq`); everything else (node_modules, runner script, model, tasks, timeout policy) is identical. Run results: `bench/results-baseline/2026-09-07__14-32-12/`, `bench/results-best/2026-09-07__15-40-57/`.

---

## 1. Per-task results

| Task | Diff | timeout_sec | Baseline reward | Baseline turns | Baseline cost | Best reward | Best turns | Best cost | Outcome |
|---|---|---|---|---|---|---|---|---|---|
| fix-git | easy | 900 | **1.0** | 16 | $0.288 | **1.0** | 11 | $0.212 | pass → pass |
| prove-plus-comm | easy | 900 | **1.0** | 8 | $0.202 | **1.0** | 6 | $0.114 | pass → pass |
| cobol-modernization | easy | 900 | 0.0 ⏱ | 44 | $0.00 | 0.0 ⏱ | 41 | $0.00 | fail → fail |
| overfull-hbox | easy | 750 | 0.0 ⏱ | 56 | $0.00 | 0.0 ⏱ | 54 | $0.00 | fail → fail |
| crack-7z-hash | medium | 900 | **1.0** | 22 | $0.398 | 0.0 ⏱ | 43 | $0.00 | **pass → fail** |
| raman-fitting | medium | 900 | 0.0 ⏱ | 38 | $0.00 | 0.0 ⏱ | 28 | $0.00 | fail → fail |
| mteb-leaderboard | medium | 3600 | 0.0 ⏱ | 129 | $0.00 | **1.0** | 32 | $1.677 | **fail → pass** |
| kv-store-grpc | medium | 900 | **1.0** | 17 | $0.283 | **1.0** | 10 | $0.250 | pass → pass |
| pytorch-model-recovery | medium | 900 | **1.0** | 10 | $0.429 | **1.0** | 13 | $0.329 | pass → pass |
| constraints-scheduling | medium | 1200 | **1.0** | 7 | $0.277 | **1.0** | 6 | $0.147 | pass → pass |

⏱ = runner hard-cap timeout kill (`is_error=True`, `cost=$0.00`, `exec ≈ timeout_sec − 60s` — verified in every failed trial's execution span).

**Both runs: 0 harbor exceptions, 0 retries** → all failures are agent-side outcomes, not infrastructure/verifier failures.

## 2. Aggregate comparison

| Metric | Baseline (df0c537) | Optimized (working tree) | Δ |
|---|---|---|---|
| Pass rate | **6 / 10** (0.600) | **6 / 10** (0.600) | 0 |
| Total turns | 347 | 244 | **−103 (−30%)** |
| Passing-run turns | 80 | 78 | −2 |
| Total LLM cost (passing runs) | $1.8765 | $2.7295 | +$0.853 |
| Per-pass avg cost | $0.313 | $0.455 | +$0.142 (mteb outlier skews) |
| Wall-clock (10 tasks, -n 4) | **1h04m47s** | **29m37s** | **−2.2×** |
| Timeout-kill failures | 4 | 4 | 0 |
| Harbor exceptions / retries | 0 / 0 | 0 / 0 | 0 |

Task-level outcome agreement: **8/10 identical** (6 pass + 2 fail both), **2/10 flipped** — mteb-leaderboard (fail→pass) and crack-7z-hash (pass→fail).

## 3. Time-boxing analysis: where the optimized guidance helped and hurt

The optimized variant's retained changes (see `git diff df0c537` in `bench/ada-best/`) consist of: (a) rewritten `agent/system-guidance.ts` with hard time-boxing rules — every Bash call must carry an explicit `timeout ≤ 20000 ms`, batched independent reads, no re-reading files, immediate termination once the work is done, and a prompt frame tuned for "~2-minute" tasks; (b) `agent/claude/agent.ts` — `MAX_THINKING_TOKENS=4000`, `API_TIMEOUT_MS=60000`, tool trimming. Both variants share the identical runner-level hard cap (`ADA_RUNNER_TIMEOUT_MS = task_timeout − 60s`), so *all* wall-clock caps are equal by construction; what differs is how each agent spends that window.

**Where it helped (mteb-leaderboard: FAIL → PASS).** The single clearest positive signal. Baseline spent 129 turns ruminating up against the 3600s window's 3540s cap and produced nothing (`cost $0`). Best finished in 32 turns / 927s with a passing verifier result. The time-boxed prompt's forced-progress and early-termination rules plausibly pushed the agent off over-exploration and into decisive execution on a long-horizon task. This is the best evidence that the optimization generalizes beyond the author's short dev tasks.

**Where it hurt (crack-7z-hash: PASS → FAIL).** Baseline passed in 22 turns / $0.398. Best burned 43 turns to the 840s cap and timed out. The task (cracking a 7z hash) is a sustained-digs security task where repeated probing attempts are the path to a solution; the aggressive ≤20s-per-command time-boxing and "~2 minutes" prompt framing plausibly cut off productive continued iteration — the agent gave up on promising attack threads sooner. Cost: the flip cost one pass ($0.40 → $0) and the run's per-pass average is dragged up by mteb's $1.677 bill.

**Where neither variant succeeded (cobol-modernization, overfull-hbox, raman-fitting).** Both hard-cap-fail all three. The optimized prompt trimmed wasted turns on each (−3, −2, −10 turns respectively; raman-fitting −26%) — evidence it suppresses churn — but in no case did it convert the reduced churn into a solution. These tasks' genuine solution cost exceeds what either agent can fit inside the capped window even with tighter iteration, so the optimization cannot rescue them. Note these are *not* evidence of regression: identical outcomes, marginally fewer turns.

**Aggregate read.** On this 10-task subset the optimization changes **which** tasks are solved but not **how many**: pass rate is 6/10 under both. It systematically reduces wasted turn-churn (total turns −30%, every passing task except pytorch-model-recovery finished in fewer turns), which is why wall-clock fell 2.2×. The mixed flips (1 win, 1 loss, net 0) mean the pass-rate neutrality is not an artifact of identical behavior — the prompt change genuinely alters behavior, with distribution-specific effects.

## 4. Go / No-Go recommendation

**Verdict: NO-GO on pass rate; GO on efficiency (conditional hold).** Recommendation: **do not adopt the optimized variant as strictly better on correctness** — this subset shows equal pass rate (6/10 vs 6/10) with a task-level trade (mteb +, crack −). Adopting it is reasonable **if** the operational priorities are wall-clock throughput and token/turn economy (2.2× faster, −30% turns), which do not sacrifice correctness on this sample. The retained-changes baseline-vs-best decision should therefore be framed as an **efficiency optimization, not a correctness improvement**, and the earlier autoresearcher claim of a large pass-rate gain (+101.5% on the private 6-task dev suite) does **not** reproduce on this unseen Terminal-Bench subset at the pass-rate level — it reproduces at the efficiency level.

**Suggested next step if pass-rate superiority is required:** a larger TB subset (~30–50 tasks) or repeated paired runs (5 seeds × 10 tasks) to establish whether the crack-7z-hash-style regression (sustained-digs tasks) or the mteb-style win is the systematic pattern; n=10 with a single stochastic run per cell is too small to separate signal from noise.

## 5. Limitations

- **Single stochastic run per (task × variant).** LLM agent runs are high-variance; per-task flips may reflect sampling noise as much as prompt effect. Two flipped tasks in opposite directions (net 0) are consistent with noise or with genuine distribution-specific effects — the evidence cannot distinguish them at n=10.
- **Small, speed-biased subset.** Tasks were chosen for *fast* execution (easy-first, lowest expert-time estimate), which tilts toward the ~2-minute-tuned prompt's home turf and away from the long-horizon regime where aggressive time-boxing could systematically hurt.
- **Cost comparison is pass-run-only.** All timeout kills cost $0 by construction (runner exits before billing a final response), so per-pass cost excludes failed-run spend; a true $/solution comparison would need to include any partial spend on failed runs.
- **mteb-leaderboard cost outlier.** Best's $1.677 on mteb (a 3600s task with real external API calls) dominates the per-pass average; dropping it, best's other five passes average $0.210 vs baseline's five (excl. none) $0.296.

---
*Reproduction: `harbor run -d terminal-bench/terminal-bench-2 -a bench.ada_agent:AdaAgent --ak variant=<baseline|best> --ae OPENROUTER_API_KEY=$OR_KEY -i terminal-bench/<task> … -n 4 -o bench/results-<name> -y` (10 `-i` flags, one per task; full command in subtask context). Raw data: per-trial `result.json` files under the two results dirs; parser: `bench/parse_results.py`.*
