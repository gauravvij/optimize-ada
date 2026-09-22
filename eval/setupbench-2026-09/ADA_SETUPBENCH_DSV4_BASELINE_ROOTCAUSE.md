# SetupBench Ada — DeepSeek Baseline Root-Cause & Model/Candidate Resolution

**Status: both open questions RESOLVED; full validation run COMPLETE.** See §7 (resolution summary), §8
(smoke run) and §9 (full 12-task × 3-rep validation: **baseline 26/36 vs candidate 26/36 — a tie**).

**Scope:** Root-cause the baseline arm's near-empty response in the DeepSeek smoke test
(`examples/SETUPBENCH_ADA_DSV4_SMOKE_RAW.json`), decide whether the injected model id is
valid for the baseline arm, reconcile the reproducibility anomaly, and identify the frozen candidate
that the `setupbench-frozen-candidate` branch is meant to evaluate.

**Model under test (final):** `deepseek/deepseek-v4.1-flash` — per the user directive this replaced the
original `deepseek/deepseek-v4-flash`; see §7 for the live-probe confirmation. The original v4-flash
pathology is retained below (§1–§3) because it is what established that the injected model id is the
root cause.

**Task under test:** `bgsetup-gunicorn-nginx-socket` (bare `ubuntu:22.04`, no `curl`/`python3` preinstalled).
**Harness:** `examples/setupbench_ada_eval_dsv4_smoke.py` (copy of `setupbench_ada_eval.py` with the model id swapped).
**Raw captures:** `/tmp/ada_dbg/capture_base/`, `capture_base2/`, `capture_opt/`, `capture_alt/`
(each holds the full untruncated in-container `/testbed/.ada.log` + `/testbed/.ada-trace.jsonl`).
**Repro script:** `/tmp/ada_dbg/run_base.sh` (replicates the eval's exact `docker run` invocation).

---

## 1. The baseline pathology (raw evidence)

Baseline run with the pinned id `deepseek/deepseek-v4-flash` (`capture_base/.ada.log`, 5253 B):

```
[claude:stderr] [claude-code:unrecognized_model] {"model":"deepseek/deepseek-v4-flash","query_source":"generate_session_title"}
...
ADA_RUN_RESULT={"stop_reason":"end_turn", ... "usage":{"input_tokens":5507,"output_tokens":2, ...},
  "modelUsage":{"deepseek/deepseek-v4-flash":{"inputTokens":5507,"outputTokens":2,
    "cacheReadInputTokens":5376,"costUSD":0.030273,"canonicalModel":"deepseek/deepseek-v4-flash", ...}},
  "is_error":false,"num_turns":2,"subtype":"success","result":"", ...}
```

Trace (`capture_base/.ada-trace.jsonl`, 3 lines):

```
0 system init
1 user
2 result success
```

**Zero assistant messages.** The model produced no assistant turn at all — the loop opened, received the
user message, and emitted a terminal `result` with `result:""`, `output_tokens:2`, `num_turns:2`,
`stop_reason:end_turn`, `is_error:false`, `terminal_reason:"completed"`. This is a *clean* early exit,
not a crash, timeout, or auth error.

Because no work was done, the grader's `success_command`
(`curl -s http://localhost/ | grep -q "Hello from Gunicorn!" && echo "Setup successful" || echo "Setup failed"`)
emitted `Setup failed\nbash: line 1: curl: command not found` — the missing-`curl` message is the
*symptom* of an agent that never installed anything, not a harness defect.

---

## 2. Is `deepseek/deepseek-v4-flash` valid for the baseline arm? — **No (flaky/invalid).**

| Run | Model id injected | num_turns | output_tokens | `result` | Trace assistant msgs | Outcome |
|-----|-------------------|-----------|---------------|----------|----------------------|---------|
| `capture_base` | `deepseek/deepseek-v4-flash` | 2 | 2 | `""` | 0 | empty / no work |
| `capture_base2` | `deepseek/deepseek-v4-flash` | 4 | 348 | `""` | 5 | partial work, still empty final result |
| `capture_alt` | `~deepseek/deepseek-v4-flash-latest` | 18 | 4792 | full "Setup complete and verified…" | 20+ | **SETUP-SUCCESSFUL** |
| `capture_opt` (candidate) | `deepseek/deepseek-v4-flash` | — | — | watchdog-aborted | — | grader "Setup successful" |

**Verdict:** the pinned id `deepseek/deepseek-v4-flash` is **not reliable** for the baseline arm — it
returns an empty final turn (0 assistant messages, `output_tokens:2`) and does no work. The alias
`~deepseek/deepseek-v4-flash-latest` **works**: 18 turns, 4792 output tokens, a full completion summary,
and a verified `SETUP-SUCCESSFUL` grader result.

**Important caveat on the `unrecognized_model` warning:** the line
`[claude-code:unrecognized_model] {"model":"deepseek/deepseek-v4-flash","query_source":"generate_session_title"}`
appears in **every** run — including the working alias run (`capture_alt`, count = 1). It is scoped to
`query_source:"generate_session_title"` (a cosmetic title-generation call) and is therefore **not** the
root cause of the empty baseline turn. The differentiator is the model id's routing/validity, not the warning.

---

## 3. Reproducibility anomaly (reconciliation)

The initial smoke run and the first replays showed the 2-turn / 2-output-token / empty-result pathology
**3/3**. The extra run `capture_base2` broke that pattern: **4 turns, 348 output tokens**, with 5 assistant
messages in the trace — i.e. the model *did* start working — yet the final `result` was still `""` and the
grader still failed.

**Reconciliation:** the pinned id is **flaky, not deterministically broken**. It sometimes emits a few
assistant turns before terminating with an empty final result, and sometimes emits none. In every observed
case with the pinned id the run ends with `result:""` and no completed setup. The alias, by contrast, was
consistent (full multi-turn completion). So the correct characterization is: *the pinned id is unreliable
for this arm; the alias is reliable.* The "3/3" claim should be read as "3/3 empty-result failures," not
"3/3 exactly-2-turn runs."

---

## 4. Ada wall-clock budget (separate, related finding)

The candidate arm (`targets/ada`) has an internal watchdog: `RUN_BUDGET_MS` default **455000 ms** plus
`WATCHDOG_EXIT_GRACE_MS` 8000 → force-exit at **~458–463 s**, i.e. ~140 s *before* the harness
`--timeout-seconds 600`. The eval harness never sets `ADA_RUN_BUDGET_MS`, so the 455 s default silently
caps every candidate attempt.

On watchdog fire the synthetic result carries `num_turns:0` and no usage — which is exactly why the
optimized smoke row shows `turns=0 / input_tokens=0 / agent_is_error=true` while the grader still
independently reported `Setup successful`. The baseline (`targets/ada-baseline`) has **no** watchdog
(0 references), so it relies solely on the harness kill.

**Action taken (implemented):** the budget raise is now applied in
`examples/setupbench_ada_eval_dsv4_smoke.py`'s `run_variant()` docker args:

```python
"-e", f"ADA_RUN_BUDGET_MS={(timeout_seconds + 120) * 1000}",
```

This derives Ada's internal budget from the harness `--timeout-seconds` (+120 s headroom), so the harness
kill stays authoritative while Ada still emits its final `ADA_RUN_RESULT`. For `--timeout-seconds 600` this
sets `ADA_RUN_BUDGET_MS=720000` (720 s); for 1200 s it sets 1320000. Verified: `python3 -m py_compile` OK,
and the env var propagates into the container (`docker run -e ADA_RUN_BUDGET_MS=720000 … → container_sees=720000`).
`examples/setupbench_ada_eval.py` remains untouched (0 `ADA_RUN_BUDGET` refs).

---

## 5. Candidate identity (RESOLVED)

The branch `targets/optimize-ada` @ `setupbench-frozen-candidate` documents the authoritative frozen
candidate. Its `README.md` pins it as: base commit `0c5e1da…` plus tracked-diff SHA-256
**`9e6a3fe04725f3c3ca43b5fcfcd53bde07f8fbbffc58d7e80793f6ffb408bd4a`**; the archived source is under
`targets/optimize-ada/ada/` and the standalone diff is
`targets/optimize-ada/eval/setupbench-2026-09/frozen-candidate.patch`.

**Which workspace actually reproduces the canonical fingerprint `9e6a3fe0…`?**

| Workspace | HEAD | tracked-diff sha256 | changed files | is the frozen candidate? |
|---|---|---|---|---|
| `targets/ada-setupbench-paired` | `0c5e1da` | **`9e6a3fe0…`** | `AUTORESEARCH_TASK.md`, `agent.ts`, `coding-guidance.ts` | ✅ **YES — exact match** |
| `targets/ada` | `0c5e1da` | `5970e46d…` | `AUTORESEARCH_TASK.md`, `agent.ts`, `coding-guidance.ts`, `system-guidance.ts` | ❌ no (extra `system-guidance.ts`) |
| patched `ada-baseline` copy | `0c5e1da` | `e8740564…` | `agent.ts`, `coding-guidance.ts` | ❌ no (no `AUTORESEARCH_TASK.md` change) |
| `targets/ada-setupbench-opt` | `0c5e1da` | `88f4d107…` | `AUTORESEARCH_TASK.md`, `coding-guidance.ts` | ❌ no (older variant) |

**File-level proof:** the agent source in `targets/ada-setupbench-paired` is byte-identical to the archived
frozen source and to the patch reconstruction — `agent/claude/agent.ts` sha256 `ec71bbe7…`, `agent/coding-guidance.ts`
sha256 `1eea1154…` (both match the branch README's pinned file hashes exactly). The only difference between
`ada-setupbench-paired` and the patch reconstruction is that `ada-setupbench-paired` also carries the
`AUTORESEARCH_TASK.md` edit — which is *not* part of the candidate patch (it is the optimization task spec,
not production agent code), yet it *is* included in the harness's whole-working-tree `tracked_diff_fingerprint`.
That is why the canonical `9e6a3fe0…` = paired-workspace fingerprint, while the patch-only reconstruction
gives `e8740564…`.

**Definitive conclusion:**
- **The frozen candidate = `targets/ada-setupbench-paired`** (fingerprint `9e6a3fe0…`, matching every
  canonical 900s/1200s validation record). Its *agent code* is identical to `frozen-candidate.patch`
  (`ec71bbe7…` / `1eea1154…`); it additionally carries the `AUTORESEARCH_TASK.md` spec edit that the
  whole-tree fingerprint folds in.
- **`targets/ada` is NOT the frozen candidate** — it is a *different, later* candidate implementation
  (720-line `agent.ts` with a run-budget watchdog + `system-guidance.ts` changes). The earlier smoke test
  (protocol `candidate_diff_sha256 = 5970e46d…`) therefore evaluated the **wrong candidate** relative to the
  branch's frozen release.
- The `ebf48e4d…` fingerprint in the GLM full93 run is yet another distinct workspace and is not the
  canonical frozen candidate either.

**Implication for the intended run:** the branch's stated purpose is *baseline Ada vs the frozen candidate*.
To reproduce that, the candidate workspace must be the frozen one (`9e6a3fe0…` / agent code `ec71bbe7…`),
i.e. pass `--candidate-workspace targets/ada-setupbench-paired` (or reconstruct via `frozen-candidate.patch`
applied to `ada-baseline`). Using `targets/ada` (the smoke default) compares against the wrong implementation.

**Budget-knob caveat:** the frozen candidate's `agent.ts` uses the *model-wait* watchdog
(`MODEL_WAIT_WATCHDOG_MS = 90_000`, `MAX_RUN_ATTEMPTS = 4`, `RETRY_WALL_DEADLINE_MS = 360_000`) and has **no
`RUN_BUDGET_MS`** — so the `ADA_RUN_BUDGET_MS` fix in Section 4 does **not** apply to the frozen candidate.
`RUN_BUDGET_MS` exists only in `targets/ada`, which is not the frozen candidate.

---

## 6. Recommendations (final)

1. **Model routing — RESOLVED.** Use `deepseek/deepseek-v4.1-flash` (user directive) for **both** arms. It is
   served on OpenRouter and returns real completions (see §7). The original `deepseek/deepseek-v4-flash` must
   not be used as the injected id; `~deepseek/deepseek-v4-flash-latest` is a verified-working fallback alias.
   Applied: all 4 refs in `examples/setupbench_ada_eval_dsv4_smoke.py` now read `deepseek/deepseek-v4.1-flash`.
2. **Candidate workspace — RESOLVED.** The frozen candidate is `targets/ada-setupbench-paired`
   (fingerprint `9e6a3fe0…`), **not** the harness default `targets/ada` (`5970e46d…`). Pass
   `--candidate-workspace targets/ada-setupbench-paired` on every run. The harness defaults `FINAL_ADA =
   targets/ada`; a one-line default change is optional but not required (see §7 decision).
3. **Ada budget knob — conditional.** The `ADA_RUN_BUDGET_MS` raise (§4) applies only to `targets/ada`'s
   run-budget watchdog. The **frozen candidate uses a model-wait watchdog with no `RUN_BUDGET_MS`**, so the
   knob is a no-op for it. Keep the injection (harmless; correct for `targets/ada`), but do not rely on it to
   fix frozen-candidate telemetry.
4. **Before the full run:** confirm the candidate workspace resolves to the frozen fingerprint in the
   protocol block (`candidate_diff_sha256 == 9e6a3fe0…`) and that `baseline_diff_sha256 == e3b0c442…`
   (clean baseline). Then launch with stdout `tee`'d to a log for exit-code/progress auditability.

---

## 7. Closing summary — both open questions resolved

**Q1 — root cause of the near-empty baseline response: RESOLVED.**
The injected model id was the cause. With `deepseek/deepseek-v4-flash`, the baseline arm's loop opened,
took the user message, and emitted a terminal result with `result:""`, `output_tokens:2`, zero assistant
turns — a clean early exit, not a crash/auth/timeout. The same id produced partial-but-still-empty runs
(4 turns / 348 tokens), so it is **flaky, not deterministically broken**. The cosmetic
`[claude-code:unrecognized_model]` title-generation warning is present in *every* run (including working
ones) and is **not** the root cause. The differentiator is model-id routing validity.

**Q2 — model validity: RESOLVED.** `deepseek/deepseek-v4-flash` is **not reliable** as the injected id
for the baseline arm; `~deepseek/deepseek-v4-flash-latest` was verified working. Per the user directive,
the model has been switched to **`deepseek/deepseek-v4.1-flash`** in all 4 refs of
`examples/setupbench_ada_eval_dsv4_smoke.py` (L2 docstring, L202 `ANTHROPIC_MODEL`, L294 modelUsage key,
L558 `protocol.model`).

**Live-probe confirmation of `deepseek/deepseek-v4.1-flash` (this session):**
- `GET https://openrouter.ai/api/v1/models` → HTTP 200, 446 models, `deepseek/deepseek-v4.1-flash` **FOUND**.
- `POST /api/v1/chat/completions` (model `deepseek/deepseek-v4.1-flash`, prompt "Reply with exactly PONG")
  → HTTP 200, `finish_reason: stop`, `content: "PONG"`, `reasoning_tokens: 10`, cost $0.000027.
- It is a **reasoning model** (emits reasoning tokens) — relevant for token accounting, since reasoning
  tokens count toward output usage but are not assistant text.
- `python3 -m py_compile examples/setupbench_ada_eval_dsv4_smoke.py` → **COMPILE_OK**.

**Q3 (raised by the user) — which candidate is the frozen one: RESOLVED.** The
`setupbench-frozen-candidate` branch documents its frozen candidate: base `0c5e1da…` + tracked-diff
`9e6a3fe0…`. That fingerprint is reproduced **exactly** by `targets/ada-setupbench-paired`, whose agent
code is byte-identical to `frozen-candidate.patch` (`agent.ts` `ec71bbe7…`, `coding-guidance.ts`
`1eea1154…`). **The harness default `targets/ada` (`5970e46d…`) is a different, later implementation and
is NOT the frozen candidate.**

**Decision taken (per user: "flag is fine if not much changes, otherwise hard-pointed is fine too"):**
**Use the flag** — pass `--candidate-workspace targets/ada-setupbench-paired`. Rationale: the candidate
source is mounted via `-v {ada}:/opt/ada-src:ro` while `node_modules` is a *separate* mount
(`NODE_MODULES = FINAL_ADA/node_modules`); both workspaces carry identical dependencies
(`package.json` sha `73216153…`, 172 entries each), so the shared `node_modules` mount works unchanged and
**no code change is required**. Hard-pointing `FINAL_ADA` would also alter what `NODE_MODULES` resolves to,
for no functional gain.

**Run executed — validation result (see §8).** The smoke test was run with
`--candidate-workspace targets/ada-setupbench-paired` and the new model; the protocol block confirms
`candidate_diff_sha256 == 9e6a3fe0…` and `baseline_diff_sha256 == e3b0c442…`.

---

## 8. Validation run — results

Command (run from repo root; harness auto-derives `ANTHROPIC_AUTH_TOKEN` from `OPENROUTER_API_KEY`):

```bash
python3 examples/setupbench_ada_eval_dsv4_smoke.py \
  --suite original6 --task bgsetup-gunicorn-nginx-socket \
  --candidate-workspace targets/ada-setupbench-paired \
  --timeout-seconds 600 --grader-timeout-seconds 600 \
  --repetitions 1 --parallel-pair \
  --output examples/SETUPBENCH_ADA_DSV4_RAW.json
```

Output: `examples/SETUPBENCH_ADA_DSV4_RAW.json` (31,361 B). Console:
`baseline=pass candidate=pass turns=17/9 timeouts=0/0 valid=1/1`.

**Protocol block (as recorded by the harness):**

| Field | Value | Check |
|-------|-------|-------|
| `model` | `deepseek/deepseek-v4.1-flash` | ✅ correct model |
| `baseline_ada_commit` | `0c5e1da…` | ✅ |
| `candidate_ada_commit` | `0c5e1da…` | ✅ |
| `baseline_diff_sha256` | `e3b0c442…` (empty) | ✅ clean baseline |
| `candidate_diff_sha256` | `9e6a3fe0…` | ✅ **matches frozen candidate** |
| `timeout_seconds` | 600 | ✅ |

**Per-variant results:**

| Variant | passed | valid | timed_out | duration | turns | in_tok | out_tok | agent_is_error | grader |
|---------|--------|-------|-----------|----------|-------|--------|---------|----------------|--------|
| baseline | ✅ True | ✅ True | False | 172.2 s | **17** | 144,937 | 4,086 | False | `Setup successful` |
| optimized | ✅ True | ✅ True | False | 98.9 s | **9** | 24,961 | 2,649 | False | `Setup successful` |

**Model-billing proof (no silent fallback):** `ADA_RUN_RESULT.modelUsage` is keyed on
`deepseek/deepseek-v4.1-flash` in **both** arms, each with `canonicalModel: "deepseek/deepseek-v4.1-flash"`,
`provider: "firstParty"`, and `thinkingTokens` 1565 (baseline) / 1159 (optimized) — confirming the reasoning
model actually served the run. Grep over the result JSON: 5 occurrences of the model id; **0** occurrences of
`claude-opus` / `claude-haiku` / `z-ai` / `glm-5.3-flash` / `deepseek-v4-flash`; **0** `unrecognized_model`
warnings (the cosmetic warning that appeared with the old id is now gone).

**Both arms produced full multi-turn work** — `agent_result` is a complete setup summary ending in a verified
`HTTP 200 / Hello from Gunicorn!` (baseline: 1000 chars, 17 turns; optimized: 836 chars, 9 turns). This is the
direct opposite of the original pathology (2 turns, `result:""`, `output_tokens:2`).

**Conclusion:** the root-cause fix is validated end-to-end. With the correct injected model id, the baseline
arm performs real multi-turn work and passes; the candidate arm (frozen candidate `9e6a3fe0…`) also passes,
and the comparison is now against the **intended** frozen candidate. The run is a 1-task early signal, not a
full validation — but every failure mode that blocked the original run (empty baseline, wrong candidate,
model flakiness) is now resolved.

---

## 9. Full validation run — 12 tasks × 3 reps (1200 s protocol)

Command (canonical 1200 s protocol, frozen candidate pinned via flag, model swapped):

```bash
python3 examples/setupbench_ada_eval_dsv4_smoke.py \
  --suite validation12 --candidate-workspace targets/ada-setupbench-paired \
  --timeout-seconds 1200 --grader-timeout-seconds 600 \
  --repetitions 3 --parallel-pair --pair-concurrency 3 \
  --output examples/SETUPBENCH_ADA_DSV4_VALIDATION12_RAW.json
```

Output: `examples/SETUPBENCH_ADA_DSV4_VALIDATION12_RAW.json` (1.12 MB, 72 rows = 36 pairs).
Protocol verified: `model=deepseek/deepseek-v4.1-flash`, `suite=validation12`, `timeout=1200`,
`grader=600`, `attempts_per_task_variant=3`, `pair_concurrency=3`, seed `20260904`,
`baseline_diff_sha256=e3b0c442…` (clean), `candidate_diff_sha256=9e6a3fe0…` (frozen candidate ✅).

### Headline result

| Arm | Passed | Timeouts | Invalid | Harness errors |
|-----|--------|----------|---------|----------------|
| baseline | **26/36** | 6 | 0 | 0 |
| optimized (frozen candidate) | **26/36** | 4 | 0 | 0 |

**Dead tie on pass-rate (26/36 each).** Paired breakdown over the 36 pairs:

| Outcome | Count |
|---------|-------|
| both pass | 19 |
| baseline-only pass | 7 |
| candidate-only pass | 7 |
| neither pass | 3 |

The 7-vs-7 discordant split is perfectly symmetric — **no evidence of a candidate effect** on this
suite. (McNemar with b=7, c=7 → p = 1.0.)

### Per-task pass counts (out of 3)

| Task | baseline | candidate | base TO | cand TO |
|------|----------|-----------|---------|---------|
| bgsetup-filewatcher-daemon-2 | 3/3 | 3/3 | 0 | 0 |
| dbsetup-mongodb-2 | 3/3 | 2/3 | 0 | 0 |
| dbsetup-mysql-2 | 2/3 | 0/3 | 0 | 0 |
| deps-gatsby-plugin-intl-2b7ac | 3/3 | 2/3 | 0 | 1 |
| deps-ultimate-frontrunning-bot-449d6 | 3/3 | 3/3 | 0 | 0 |
| dishait-tov-template-39c0898 | 3/3 | 3/3 | 0 | 0 |
| fsspec-filesystem_spec-3ff5fca | 2/3 | 3/3 | 0 | 0 |
| hackmdio-codimd-f00df50 | 1/3 | 2/3 | 2 | 1 |
| microsoft-azure-pipelines-tasks-bfcd4b2 | 1/3 | 1/3 | 1 | 1 |
| prometheus-bd5b2ea | 3/3 | 2/3 | 0 | 0 |
| wagtail-wagtail-28fcd01 | 0/3 | 2/3 | 3 | 1 |
| whisper-517a43e | 2/3 | 3/3 | 0 | 0 |
| **TOTAL** | **26/36** | **26/36** | **6** | **4** |

### Secondary observations

- **Timeouts:** candidate 4 vs baseline 6 — the candidate is marginally *less* timeout-prone, but
  both arms are timeout-dominated on the same hard tasks (`wagtail`, `hackmdio`, `microsoft-azure`).
  These are the tasks where the 1200 s ceiling binds, not a candidate-specific defect.
- **Duration:** baseline mean 596.2 s (max 1211.9 s) vs candidate mean 532.8 s (max 1225.9 s).
- **Tokens:** baseline 3,337,711 in / 201,589 out; candidate 3,467,927 in / **129,759 out** — the
  candidate emits ~36 % fewer output tokens for the same pass-rate (consistent with the smoke
  observation of a leaner agent loop), but this does **not** translate into more passes.
- **Validity:** 0 invalid rows, 0 harness errors, 0 `agent_is_error` rows across all 72 attempts.

### Model-id / fallback proof

- `deepseek/deepseek-v4.1-flash` appears **120×** in the result JSON.
- Fallback leakage: `claude-opus` 0, `claude-haiku` 0, `z-ai` 0, `glm-5.3-flash` 0,
  `deepseek-v4-flash"` 0, `deepseek-v4-flash-latest` 0.
- `canonicalModel:"deepseek/deepseek-v4.1-flash"` appears **60×** (one per completed agent run).
- `unrecognized_model` warnings: **0** (the cosmetic warning from the old id is gone).
- Billing: two key-wide segments, $3.9639 + $3.2173 = **$7.18** total (key-wide, not
  variant-attributable in parallel mode).

### Run-stability note

The first launch aborted at 22/36 pairs with
`RuntimeError: persistent LLM API error for task=whisper-517a43e variant=baseline`. This was a
**transient upstream API error** under 6-way concurrency, not a key/credit problem: the OpenRouter
key was healthy ($47.62 remaining, not free tier) and a live probe of the model returned HTTP 200
`PONG` immediately after. The harness aborts the whole run when a variant hits
`terminal_reason:"api_error"` on all 3 infra retries. Re-running with `--resume` retained the 44
already-completed variant results and finished the remaining 14 pairs cleanly.

### Verdict

**The frozen candidate does NOT beat the baseline on this suite under DeepSeek V4 Flash.** Both arms
score 26/36, with a perfectly symmetric 7-vs-7 discordant split. The candidate's only measurable
advantage is efficiency (fewer output tokens, marginally fewer timeouts), not correctness. This
**contradicts the 1-task smoke signal** (where the candidate looked clearly better) — confirming the
smoke was not representative and that the full run was necessary. The 26/36-vs-26/36 result also
matches the branch's own historical GLM 1200 s validation (26/36 both arms), i.e. the model swap to
DeepSeek V4 Flash did not change the outcome.

---

## Appendix — Raw evidence index

| Artifact | Path | Key content |
|----------|------|-------------|
| Baseline log | `/tmp/ada_dbg/capture_base/.ada.log` | `unrecognized_model` line; `ADA_RUN_RESULT` num_turns=2, out_tok=2, result="" |
| Baseline trace | `/tmp/ada_dbg/capture_base/.ada-trace.jsonl` | 3 lines: init → user → result (0 assistant) |
| Baseline replay 2 | `/tmp/ada_dbg/capture_base2/.ada.log` | num_turns=4, out_tok=348, result="" (anomaly) |
| Alias log | `/tmp/ada_dbg/capture_alt/.ada.log` | `~deepseek/deepseek-v4-flash-latest`, num_turns=18, out_tok=4792, full result |
| Candidate log | `/tmp/ada_dbg/capture_opt/.ada.log` | watchdog-aborted, grader "Setup successful" |
| Repro script | `/tmp/ada_dbg/run_base.sh` | exact `docker run` invocation |