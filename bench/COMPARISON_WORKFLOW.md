# Comparison workflow: baseline vs best on DeepSeek V4.1 Flash

A runbook. It says what is being compared and why, what was run, how to read the results, find the
evidence and trace any single attempt, **without needing Claude Code**. Hand this file to any person or agent to pick the work up.

Scope is deliberately narrow: **only `deepseek/deepseek-v4.1-flash`, only `r1_all` (split 40+41+retry, merged to 81)
and `r2` (single clean 81)**. Older models and incomplete runs are out of scope and are not discussed here.

All commands are run from the repo root, `/home/azureuser/adaAgent`. All times are UTC.

## 1. Context

**The question in plain language.** Ada, the coding agent, gets a setup job (install dependencies, get tests running)
in a fresh Docker container with 480 seconds. A check command from the benchmark then decides pass or fail.
If Ada is still working at 480 s, the harness stops it and the check never runs — an automatic fail.

Two builds are compared:

| Build | What it is |
|---|---|
| **baseline** | Ada at `df0c537` plus a 7-line pass-through shim (agent tree `7c88c8270e3b`) |
| **best** | Ada at `5f4c5c0` (agent tree `dab704de524a`): a watchdog that stops Ada at 450 s so its work still gets checked, a time-aware prompt, a thinking limit |

For non-technical readers: the baseline often runs out of time and is never graded. The best build stops itself
30 seconds early so the grader still scores whatever it finished. The comparison asks whether that rescue turns
timeouts into passes, and whether anything changes on tasks the baseline already finished in time.

For technical readers: comparing builds *within* the same model and run isolates the code. `r1_all` and `r2` are
two replicates of the same 81 tasks on the same model with the same builds, run on different days and under
different load — a consistency check, not a significance retest.

**What has been done (v4.1 only)**

| Run | Tasks | Where | Result |
|---|---|---|---|
| r1 (40-task part) | fixed 40 (`tasks.set40.txt`), both builds at same time | `ada/runs/deepseek-v4.1-flash/r1/` | COMPLETE 2026-09-19 12:47: baseline 17/40, best 21/40; timeouts 18/0; watchdog 17 (3 then passed); harness errors 0/1 |
| r1_set41 (other 41) | fixed 41 (`tasks.set41.txt`), both builds at same time | `ada/runs/deepseek-v4.1-flash/r1_set41/` | COMPLETE 2026-09-19 14:38: baseline 17/41, best 26/41; timeouts 23/0; watchdog 14 (3 then passed); harness errors 0/0 |
| r1_retry | 1 retry (`pytesseract-df9fce0`) | `ada/runs/deepseek-v4.1-flash/r1_retry/` | COMPLETE 2026-09-19 14:53: 1/1 both; replaces the single best harness error from r1 |
| **r1_all (merged 81)** | **all 81, first-valid-attempt merge** | **`ada/runs/deepseek-v4.1-flash/r1_all/`** | **COMPLETE: baseline 34/81 (42.0%), best 48/81 (59.3%); 81 pairs, gained 16, lost 2, p=0.00131; timeouts 41/0; watchdog 31 (6 then passed)** |
| **r2 (single clean 81)** | **all 81 at once (`tasks.81.txt`), both builds at same time** | **`ada/runs/deepseek-v4.1-flash/r2/`** | **COMPLETE 2026-09-22 09:01:48; baseline 40/81 (49.4%), best 49/81 (60.5%); 80 pairs, gained 14, lost 5, p=0.0636; timeouts 36/0; watchdog 36 (13 then passed); harness errors 1/0** |

Paired counts leave out tasks where either attempt was a harness error: r1 has 39 pairs (one best harness error),
r1_set41 has 41, r1_all has 81, r2 has 80 (one baseline harness error: `prometheus-bd5b2ea`, Docker
`No such container ... timed out after 60 seconds`).

**Decisions already taken (do not re-litigate without reason)**
- Model is `deepseek/deepseek-v4.1-flash` through OpenRouter. No other model is in scope.
- The 81 tasks are split into a fixed **40-task set** (`ada/runs/deepseek-v4.1-flash/tasks.set40.txt`) and the **41 remaining**
  (`tasks.set41.txt`). The split is balanced by task type and made by a seeded hash, described in `ada/runs/deepseek-v4.1-flash/SPLIT.md`.
  Both builds always get exactly the same tasks. `tasks.81.txt` (81 lines, identical to `r2/tasks.txt`) is the same 81 as the merged `r1_all`.
- Both builds run **at the same time**, 3 tasks at once each (total load 6), so machine load and provider conditions are shared within a run.
- All runs keep full evidence (traces) in the `ada/` folder. Everything stays local unless deliberately committed later.
- Harness errors are re-run in a separate small run afterwards and merged by a fixed rule (section 8); a valid attempt is never replaced.
- `r2` is the clean single-run replicate of `r1_all`: same 81 tasks, same builds, same concurrency, one run instead of a split merge.

**Do not**: commit, print or paste the API key, or start a second run while one is running (the driver refuses).

## 2. What is in the repo for this work

| File | Purpose |
|---|---|
| `bench/run_pair.sh` | Runs baseline and best **together** on one task list, then builds the results by itself. The main entry point. `DIRECT=1` talks straight to the Anthropic API (no proxy); otherwise via OpenRouter. |
| `bench/haiku_summary.py` | Direct-API mode only (`DIRECT=1`): builds `summary.md` / `summary.json` from CLI token usage x list prices. Not used for OpenRouter runs. The filename is historic; it is not a model run. |
| `ada/runs/deepseek-v4.1-flash/tasks.set40.txt`, `tasks.set41.txt`, `tasks.81.txt` | The fixed 40, 41, and full 81 task lists. `tasks.81.txt` is identical to `r2/tasks.txt`. |
| `ada/runs/deepseek-v4.1-flash/SPLIT.md` | How the 40/41 split was made (by task type, seeded hash). |
| `bench/pair_status.sh` | Shows where a run is. Safe to run any time. |
| `bench/trace_attempt.py` | Prints one attempt as a readable timeline. |
| `bench/deepseek_summary.py` | Builds `summary.md` / `summary.json` from the raw attempt files (the driver runs it for you; re-running it is byte-identical). |
| `bench/harness/openrouter_proxy.py` | A small proxy the containers talk to: adds the provider setting and logs every model call. |
| `bench/harness/setupbench_ada_runner_ts.ts` | The benchmark runner, a copy of the standard one that only adds a timestamp to every trace entry. |
| `bench/harness/worktrees/ada-baseline`, `ada-best` | The two builds, as git checkouts of `ada/`. |
| `bench/merge_runs.py` | Merges the 40-task run, the 41-task run and the retry run into `r1_all` for a single 81-task analysis. |
| `bench/COMPARISON_WORKFLOW.md` | This file. |
| `bench/verify_docs.py` | Checks every `README.md` figure for the v4.1 runs against raw `result.json` / `agent.log` / `trace.jsonl` and `summary.json`. Run it after any write-up change. |
| `README.md`, `ada/RESULTS_DEEPSEEK_V41.md` | The write-ups: overview in `README.md` (`Second model` + `Repeat in one run`), full per-task record in `ada/RESULTS_DEEPSEEK_V41.md` (r1_all). |

Out of scope and ignored here: any `comparison_vs_deepseek-v4-flash*` files, `bench/run_deepseek_v4_flash.sh`,
`readme2.md` / `ada/results2.md`, and any deleted or incomplete runs. If those files exist on disk, do not cite them.

## 3. The runs

| Run | Tasks | Started (UTC) | State | Evidence folder |
|---|---:|---|---|---|
| r1 | 40 (`tasks.set40.txt`) | 2026-09-19 11:11:39 | COMPLETE 12:47:26 | `ada/runs/deepseek-v4.1-flash/r1/` |
| r1_set41 | 41 (`tasks.set41.txt`) | 2026-09-19 12:58:40 | COMPLETE 14:38:37 | `ada/runs/deepseek-v4.1-flash/r1_set41/` |
| r1_retry | 1 (`tasks.retry.txt`: `pytesseract-df9fce0`) | 2026-09-19 14:48:37 | COMPLETE 14:53:32 | `ada/runs/deepseek-v4.1-flash/r1_retry/` |
| r1_all | all 81, merged | — | COMPLETE: baseline 34/81, best 48/81 | `ada/runs/deepseek-v4.1-flash/r1_all/` |
| **r2 (full 81)** | **81 (`tasks.81.txt`)** | **2026-09-22 05:52:14** | **COMPLETE 09:01:48** | **`ada/runs/deepseek-v4.1-flash/r2/`** |

The r2 run was started with (detached, concurrent-pair design, full 81 at once):

```bash
MODEL=deepseek/deepseek-v4.1-flash \
TASKS_FILE=ada/runs/deepseek-v4.1-flash/tasks.81.txt \
EVIDENCE_DIR=ada/runs/deepseek-v4.1-flash/r2 \
CONC=3 \
setsid nohup bash bench/run_pair.sh > ada/runs/deepseek-v4.1-flash/r2.driver.log 2>&1 < /dev/null &
```

- Length: just over 3 hours for both builds together (05:52:14–09:01:48). Actual cost from OpenRouter per-call records: $1.281825 baseline + $1.244951 best = $2.526776 total.
- Preflight 2026-09-22 05:51 passed clean and is in `r2.driver.log`: baseline `05c243e` tree `7c88c8270e3b` clean,
  best `5f4c5c0` tree `dab704de524a` clean, model listed on OpenRouter with pricing snapshot saved, key valid, 81 tasks. `DRY_RUN=1` first, then live launch.
- What it does, in order: preflight checks (builds, model listed on OpenRouter, key valid), one proxy per build,
  both builds run together, wait for in-flight calls, look up every call's provider and cost at OpenRouter, write the
  protocol files, scan the evidence for API keys, then write `summary.md` and `summary.json`.
- When it is done the state line says `COMPLETE ... results=<path>/summary.md`.
- The single harness error is `baseline/prometheus-bd5b2ea` (container failed to start). No retry run was made; r2 is analysed as 80 pairs.

The split runs were started the same way (one `TASKS_FILE` / `EVIDENCE_DIR` per part, `CONC=3`, same model).
Their results live in `r1/summary.md`, `r1_set41/summary.md`, `r1_retry/summary.md`, merged into `r1_all/` (see `MERGE.md`).

## 4. How to check on a run

Both v4.1 runs are COMPLETE. Use these read-only commands to inspect them. Examples use `r2`; replace `r2` with `r1`, `r1_set41` or `r1_all` for the older folders.

**Everything at once**

```bash
bash bench/pair_status.sh ada/runs/deepseek-v4.1-flash/r2
```

It prints: the state (the first lines of `run.STATUS`), live processes and containers (expect none now), machine memory/disk/load, and for each build the tasks done out of the total in `tasks.txt` (81 for r2), passes, timeouts,
harness errors, API calls, empty replies and a rough time left. A line ending in `<<< look at this` means a harness error, a missing trace or a non-200 API response.

**By hand**

```bash
cat  ada/runs/deepseek-v4.1-flash/r2/run.STATUS                 # COMPLETE ... secret-scan=clean results=.../summary.md
tail -5 ada/runs/deepseek-v4.1-flash/r2/driver.baseline.log     # one line per finished task: task=... pass=... turns=...
tail -5 ada/runs/deepseek-v4.1-flash/r2/driver.best.log
pgrep -af 'run_pair.sh|setupbench_ada_domain_eval|openrouter_proxy'   # is anything alive? (expect nothing: run is done)
docker ps --filter name=setupbench-ada --format '{{.Names}}  {{.Status}}'   # the task containers (none now)
tail -3 ada/runs/deepseek-v4.1-flash/r2/resources.log            # memory / swap / disk, every 20 s during the run
ls  ada/runs/deepseek-v4.1-flash/r2/baseline | wc -l             # attempts finished, per build (81)
```

**States**

| `run.STATUS` starts with | Meaning | What to do |
|---|---|---|
| `COMPLETE ... secret-scan=clean` | finished, results written | read section 5 |
| `RUNNING` | in progress | wait (neither v4.1 run is in this state now) |
| `RUNNING`, with a second line `eval finished; letting in-flight calls drain...` | tasks are done, collecting costs (about 2 to 5 minutes) | wait |
| `ABORTED-resource-guard` | memory, swap or disk ran short and the run was stopped | free space or memory, then start a **new** run (section 8) |
| `SECRET-SCAN FAIL` | an API key was found in the evidence | do not share the folder; find it with `grep -rE 'sk-or-' <dir>` and remove it |
| no `run.STATUS`, or `RUNNING` but `pgrep` shows nothing | the driver died | see section 9 |

**Stopping a live run** (not needed now; this discards the run):

```bash
pkill -f run_pair.sh; pkill -f setupbench_ada_domain_eval.py; pkill -f openrouter_proxy.py
docker rm -f $(docker ps -aq --filter name=setupbench-ada)
```

## 5. Where the results are

```bash
cat ada/runs/deepseek-v4.1-flash/r2/summary.md          # the main table: baseline vs best, single clean 81
cat ada/runs/deepseek-v4.1-flash/r1_all/summary.md      # the main table: baseline vs best, merged 81
cat ada/runs/deepseek-v4.1-flash/r2/run.STATUS           # the post-run checks and the secret scan
cat ada/runs/deepseek-v4.1-flash/r1_all/MERGE.md         # which part each merged attempt came from
```

| File in `ada/runs/deepseek-v4.1-flash/r2/` (same layout in `r1`, `r1_set41`, `r1_all`) | What it holds |
|---|---|
| `summary.md`, `summary.json` | Passes, timeouts, watchdog interruptions, turns, wall time, per-turn latency, tokens, cost, providers, the paired comparison, and one entry per task. Generated by `bench/deepseek_summary.py`; re-running it is byte-identical. |
| `PROTOCOL.baseline.json`, `PROTOCOL.best.json` | Each build's commit, agent tree, limits, timestamps, exit code. |
| `PROTOCOL.run.json` | Run-level facts: machine load, and the OpenRouter key counter before and after (a rough cross-check only). |
| `pricing_snapshot.json` | The model's OpenRouter price list at the time. Canonical slug for v4.1: `deepseek/deepseek-v4.1-flash-20260910`. |

Recorded results (from the summaries; `verify_docs.py` checks the README rendering of both):

- **r1_all:** pairs=81, baseline 34, best 48, gained 16, lost 2, p=0.00131. Timeouts 41/0. Watchdog 31 (6 then passed:
  5 after a watchdog stop + 10 by finishing on their own on timed-out tasks). Finished-in-time split: 40 pairs, 34 vs 33.
  Cost $1.602515 vs $1.425645. Turns 17.4/16/28 vs 15.9/15/23. Wall 414.1/488.8/532.5 vs 382.5/390.8/558.3 s.
- **r2:** pairs=80, baseline 40, best 49, gained 14, lost 5, p=0.0636. Timeouts 36/0. Watchdog 36 (13 then passed:
  9 after a watchdog stop + 4 by finishing on their own on timed-out tasks). Finished-in-time split: 44 pairs, 40 vs 36.
  Cost $1.281825 vs $1.244951. Turns 16.1/14.0/26 vs 15.8/15/24. Wall 415.6/491.3/535.4 vs 399.2/445.6/565.5 s.
  Prompt tokens 18,766,872 vs 17,116,953; completion 343,404 vs 309,277. Gained tasks (14) and lost tasks (5) are listed
  in `summary.json:paired`.

**How to read the numbers**
- **Passed** means the task's own check succeeded. A **timed out** attempt (baseline only in these runs) is never checked and always fails.
  An attempt **interrupted by the watchdog** (best only) is checked, and can pass.
- **Gained / lost** compare the two builds task by task; **p** is an exact McNemar test. With one attempt per task and ~80 pairs, only large splits
  reach p < 0.05. r1_all (16 vs 2) does; r2 (14 vs 5) does not (p=0.0636). A task can flip between two runs by chance. Read differences of a few tasks as noise.
- **Cost** is the sum of OpenRouter's own per-call records. Do not use the Claude Code CLI's cost (it prices this model at a Claude fallback rate:
  r2 CLI reports $20.12 baseline / $42.44 best vs $1.28 / $1.24 actual) or the OpenRouter key counter (the key is shared, so it also counts other people's use).
- **Cost differs between builds partly by routing luck**: OpenRouter picks the provider per call. r2 served mostly Relace
  (745 baseline / 709 best) and DeepInfra (222 / 265), with a long tail (Wafer, Fireworks, Morph, Phala and others).
  The `Providers` row in `summary.md` shows the mix; cost per token is not directly comparable across builds unless the mix is similar.
- The full per-task tables and the plain-language write-up are in `README.md` (`Second model`, `Repeat in one run`) and `ada/RESULTS_DEEPSEEK_V41.md`.
  After any write-up edit, run `python3 bench/verify_docs.py` — it must print `ALL DOCUMENT CLAIMS VERIFIED`.

## 6. Where the evidence is, and how to trace an attempt

Every attempt has its own folder, `ada/runs/deepseek-v4.1-flash/r2/<baseline|best>/<task>/` (same for `r1_all`):

| File | What it holds |
|---|---|
| `trace.jsonl` | One JSON line per event: the model's thinking and text, each tool call, each tool result, the final result, each with a `ts` in milliseconds. Tool inputs and results are cut at 4000 characters and thinking at 2000 by the runner, so it is a faithful record but not a full transcript. |
| `agent.log` | Ada's own log, including the `[claude:watchdog] ... interrupting stream` lines and the session id. |
| `result.json` | Outcome (`passed`, `timed_out`, `valid`), turns, timings, token counts, the grader's output, and the final result event. |

In `r1_all`, `<build>/<task>` entries are symlinks into `r1`, `r1_set41` or `r1_retry` (see `MERGE.md`); unused attempts
are left out of the cost and listed there. If a merged folder must be portable, copy it with `cp -rL`.

Other evidence in the run folder: `proxy.<build>/generations.jsonl` (every model call with its provider, tokens and cost, keyed by session id),
`proxy.<build>/calls.jsonl` (the same before costs were looked up), `<build>.build.patch` (the exact code difference from the build's base commit),
`driver.<build>.log`, `resources.log`, `keyusage.log`, `tasks.txt`.

**Read one attempt as a timeline** (works for `r2` and `r1_all`):

```bash
python3 bench/trace_attempt.py ada/runs/deepseek-v4.1-flash/r2 best <task-id>            # outcome, cost, grader output, then every step
python3 bench/trace_attempt.py ada/runs/deepseek-v4.1-flash/r2 baseline <task-id> --full # do not cut long lines
python3 bench/trace_attempt.py ada/runs/deepseek-v4.1-flash/r2 best <task-id> --calls    # also one line per model call: provider, tokens, cost
ls ada/runs/deepseek-v4.1-flash/r2/best                                                   # the task ids
```

**Handy one-liners**

```bash
R=ada/runs/deepseek-v4.1-flash/r2
# every attempt: build, task, outcome, turns, seconds
python3 - <<'EOF'
import glob, json
for f in sorted(glob.glob("ada/runs/deepseek-v4.1-flash/r2/*/*/result.json")):
    r = json.load(open(f)); a, t = f.split("/")[-3:-1]
    print(f"{a:<9}{t:<44}{'pass' if r['passed'] else ('timeout' if r['timed_out'] else 'fail'):<8}{r['turns'] or r.get('turns_from_trace')!s:>4} turns {r['duration_seconds']:.0f}s")
EOF
grep -l 'interrupting stream' $R/best/*/agent.log | wc -l     # attempts the watchdog interrupted (r2 best: 36)
grep -l 'interrupting stream' $R/baseline/*/agent.log | wc -l # baseline: 0
grep -rE 'sk-or-' $R | wc -l                                  # must print 0: no API key in the evidence
```

## 7. What r1_all vs r2 shows (same model, same builds, two replicates)

There is no cross-model comparison in scope. The comparison that matters is within v4.1:

- *Code effect*: best against baseline **within** each run (r1_all: +14 net, p=0.00131; r2: +9 net, p=0.0636).
- *Consistency*: r1_all (split-merged) against r2 (single clean run) on the same 81 tasks. Same direction, same mechanism:
  the extra passes are on tasks the baseline timed out on (r1_all 15/41, r2 13/36); where the baseline finished in time,
  both builds pass about the same (r1_all 34 vs 33 on 40 pairs; r2 40 vs 36 on 44 pairs).
- One caution: the two replicates ran on different days and under different starting load (r1 parts 3.72 and 0.22,
  r2 0.15), so exact pass counts are not expected to match. Both builds within a run always shared the same load,
  so builds are compared fairly within a run but not naively across runs.

## 8. Next steps

Both v4.1 runs are COMPLETE. The only open item is whether to retry r2's single harness error.

**1. Harness errors already known.** A harness error means the harness failed (for example Docker was too slow to start the container); it says nothing about the agent.

```bash
python3 - <<'PY'
import glob, json
for f in sorted(glob.glob("ada/runs/deepseek-v4.1-flash/r2/*/*/result.json")):
    r = json.load(open(f))
    if not r["valid"]:
        print("r2", f.split("/")[-3], f.split("/")[-2], "|", (r["harness_error"] or "")[-120:].replace("\n", " "))
PY
# Expected: r2 baseline prometheus-bd5b2ea | ... timed out after 60 seconds
```

Default is **no retry**: analyse r2 as 80 pairs. Only retry if you need 81/81 pairs.

**2. Optional retry of that one task** (both builds run, but only the invalid attempt counts as replaceable).
Put the task id, one per line, in a file:

```bash
printf 'prometheus-bd5b2ea\n' > ada/runs/deepseek-v4.1-flash/tasks.r2_retry.txt
MODEL=deepseek/deepseek-v4.1-flash TASKS_FILE=ada/runs/deepseek-v4.1-flash/tasks.r2_retry.txt \
EVIDENCE_DIR=ada/runs/deepseek-v4.1-flash/r2_retry CONC=3 \
setsid nohup bash bench/run_pair.sh > ada/runs/deepseek-v4.1-flash/r2_retry.driver.log 2>&1 < /dev/null &
```

If run_pair.sh says "REFUSING: setupbench-ada containers are up" while nothing is running, a container stuck in state Created is left over from a failed launch. Remove it (this stops and deletes every setupbench-ada container, so only do it when no run is active):

```bash
docker rm -f $(docker ps -aq --filter name=setupbench-ada)
```

**3. Rebuild summaries (idempotent, byte-identical).**

```bash
python3 bench/deepseek_summary.py ada/runs/deepseek-v4.1-flash/r2
python3 bench/deepseek_summary.py ada/runs/deepseek-v4.1-flash/r1_all
python3 bench/verify_docs.py   # must print ALL DOCUMENT CLAIMS VERIFIED
```

The split design is already merged (`python3 bench/merge_runs.py ada/runs/deepseek-v4.1-flash/r1_all
ada/runs/deepseek-v4.1-flash/r1 ada/runs/deepseek-v4.1-flash/r1_set41 ada/runs/deepseek-v4.1-flash/r1_retry`);
do not re-merge unless the folder is missing.

**4. Read the results:** `r2/summary.md`, `r1_all/summary.md`, then a few failed attempts with `trace_attempt.py`.

**To get a written report** in the style of `README.md` and `ada/RESULTS_DEEPSEEK_V41.md`, point the writer at
`summary.json` for each run plus `MERGE.md` for `r1_all`. The README's `Second model` (r1_all) and
`Repeat in one run` (r2) sections are already generated from those files and checked by `verify_docs.py` — edit wording
only, never numbers, and re-run the verifier.

**Options of `bench/run_pair.sh`:** `CONC` (tasks at once per build, 3 here), `PROVIDER_IGNORE` (comma list of providers to exclude, default StreamLake; set empty for none; ignored when `DIRECT=1`), `DRY_RUN=1` (preflight only), `KEY_FILE` (default: the OpenRouter `.env`, or `ada/.env` with `ANTHROPIC_API_KEY` when `DIRECT=1`), `DIRECT=1` (straight to the Anthropic API: no proxy, cost from CLI usage). It refuses to reuse an evidence folder that already has results.

**Committing:** when ready, choose what goes into git deliberately. `ada/runs/` is about 45 MB per 81-task run, and `PROTOCOL.*.json` and `keyusage.log` contain the OpenRouter key's absolute usage and credit limit, which you may want reduced to deltas first.

## 9. If something goes wrong

| Symptom | Likely cause | Fix |
|---|---|---|
| `REFUSING: an eval is already running` | another run is active | wait, or stop it (section 4) |
| `REFUSING: setupbench-ada containers are up` | leftover containers from a killed run | `docker rm -f $(docker ps -aq --filter name=setupbench-ada)` |
| `REFUSING: ... already has content` | that evidence folder was used | use a new `EVIDENCE_DIR` |
| `REFUSING: port 8765 is busy` | a proxy from an earlier run is still up | `pkill -f openrouter_proxy.py` |
| `PREFLIGHT FAIL ... agent tree` | a build checkout was changed | `git -C bench/harness/worktrees/ada-<build> status`; restore it, do not edit the agent code |
| `no OpenRouter key in ...` / `no Anthropic key in ...` | wrong `KEY_FILE` | point `KEY_FILE` at an `.env` containing `OPENROUTER_API_KEY=` (or `ANTHROPIC_API_KEY=` with `DIRECT=1`) |
| `run.STATUS` says `RUNNING` but nothing is alive | the driver was killed (for example a reboot) | clean up (section 4 "Stopping a live run"), then start a new run in a new `EVIDENCE_DIR` |
| the run finished but there is no `summary.md` | the summary step failed | `cat <dir>/summary.stdout.txt`, then `python3 bench/deepseek_summary.py <dir>` |
| many `empty replies` in the status line | a provider is returning empty completions | look at `proxy.<build>/generations.jsonl`; exclude that provider with `PROVIDER_IGNORE` in a new run |
| `count_tokens` 404s in the proxy log | OpenRouter has no such endpoint | harmless and free; the tools already ignore them |

## 10. Facts worth remembering

- **Both runs are plain OpenRouter runs.** Both arms use the standard OpenRouter stack (proxy, provider exclusion,
  per-call cost records): model `deepseek/deepseek-v4.1-flash`, canonical slug `deepseek/deepseek-v4.1-flash-20260910`.
  The `DIRECT=1` direct-API mode in `run_pair.sh` (with cost from CLI usage via `bench/haiku_summary.py`) exists but was not used here.
- **Provider setting.** Every request in these runs is sent with `provider.ignore=["StreamLake"]`, added by the proxy.
  r2 served almost entirely Relace and DeepInfra; the exclusion is kept so all parts are configured the same.
  1188/1188 baseline and 1193/1193 best r2 calls carried the setting; 0 came from the ignored provider.
- **The baseline shim.** `df0c537` does not export `systemPromptGuidance`, which the runner needs; the 7-line shim adds it as a pass-through. The patch is in `<build>.build.patch`. Agent trees: baseline `7c88c8270e3b`, best `dab704de524a`.
- **Empty replies vs cut-off requests.** A request the watchdog interrupts arrives with no content; `summary.md` counts those separately from genuine empty replies. r2: 1 genuine empty reply (baseline, Relace) / 0 best; cut off by client 6 baseline / 12 best.
- **The machine is shared.** Other jobs can push the load above the 6 containers a pair run starts. Check `uptime` and `ps -eo pcpu,user,comm --sort=-pcpu | head`. Both builds in a pair run face the same load, so builds are compared fairly within a run, but not fairly across runs made at different times. Starting loads: r1 3.72, r1_set41 0.22, r2 0.15 (from each run's `PROTOCOL.run.json`).
- **The key is shared.** The OpenRouter key in `/home/azureuser/GLM5_2/.env` is also used by others, so its usage counter runs above our own cost. That is why cost comes from per-call records.
- **Turns are counted from the trace** for every attempt (tool rounds plus the final reply). The Claude Code CLI's own count is the same for attempts that finish on their own, one higher after a watchdog interrupt. The summary script uses trace turns.
- **Harness files are visible inside the container.** Agents can read the task prompt (`/testbed/.setupbench-task.txt`), a small metadata file (`.setupbench-cache.json`: task id, repo, commit), the runner source (`/opt/setupbench-ada-runner.ts`) and `/setupbench-fixtures` (per-task setup scripts; no solutions or success commands are in it). By the `verify_docs.py` trace regex: r1_all 76 of 81 baseline and 74 of 81 best attempts, r2 76 of 80 baseline and 73 of 81 best. It is the same for both builds and no leaked answer was found, but it is an environment quirk to keep in mind.
- **A failed container launch leaves a container in state Created**, which makes the next `run_pair.sh` refuse to start (see section 8 for the fix). This is what happened to r2's `baseline/prometheus-bd5b2ea`.
- **Host process lists show container processes too.** `ps` on the host lists commands the agents run inside the task containers (paths under `/root/.claude/`). They belong to the run; do not kill them.
