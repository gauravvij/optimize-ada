# DeepSeek V4.1 Flash on SetupBench: baseline against best, results

> Record note: generated from the evidence by `bench/make_report_v41.py` (as `ada/results3.md`), renamed, and trimmed to this run only — an earlier cross-model comparison was removed. Re-running the script reproduces `results3.md`, not this file.

The full record of one run: two builds of Ada, each attempting all 81 SetupBench tasks once, with `deepseek/deepseek-v4.1-flash`
through OpenRouter, both builds at the same time. The overview is in [`../README.md`](../README.md) (the `Second model` section). Every number here
is rebuilt from the raw attempt files by `python3 bench/deepseek_summary.py ada/runs/deepseek-v4.1-flash/r1_all`, and the raw files are in the
run folders listed in section 1.

## 1. What was run

| | Baseline | Best |
|---|---|---|
| Ada commit | `df0c537` plus a 7-line pass-through shim | `5f4c5c0` |
| Agent tree | `7c88c8270e3b` | `dab704de524a` |
| Model | `deepseek/deepseek-v4.1-flash` (resolved by OpenRouter to `deepseek/deepseek-v4.1-flash-20260910`) | same |
| Tasks | 81 of SetupBench's 93, at `041a412` | same, same order within a part |
| Limits | 480 s for Ada, 600 s for the check | same |
| Parallelism | 3 tasks at once, both builds at the same time | same |

The run was made in parts, and merged by [`bench/merge_runs.py`](../bench/merge_runs.py):

| Part | Tasks | Started (UTC) | Finished (UTC) | Machine load (1 / 5 / 15 min) at start, at end |
|---|---:|---|---|---|
| [`r1`](runs/deepseek-v4.1-flash/r1/) | 40 | 2026-09-19T11:11:39Z | 2026-09-19T12:47:26Z | 3.72 / 5.45 / 4.63, 0.18 / 1.71 / 6.16 |
| [`r1_set41`](runs/deepseek-v4.1-flash/r1_set41/) | 41 | 2026-09-19T12:58:40Z | 2026-09-19T14:38:37Z | 0.22 / 0.96 / 4.97, 0.01 / 0.23 / 2.52 |
| [`r1_retry`](runs/deepseek-v4.1-flash/r1_retry/) | 1 | 2026-09-19T14:48:37Z | 2026-09-19T14:53:32Z | 0.06 / 0.21 / 2.42, 0.41 / 0.84 / 2.01 |

Rule of the merge: per build and per task the first valid attempt is used, and a later attempt replaces an earlier one
only when the earlier was a harness error. Attempts left out are listed in [`MERGE.md`](runs/deepseek-v4.1-flash/r1_all/MERGE.md).
The shim adds `systemPromptGuidance` as a pass-through to `systemGuidance()`, because `df0c537` does not export it and the
benchmark runner imports it. The prompt is unchanged. The patch is in
[`baseline.build.patch`](runs/deepseek-v4.1-flash/r1/baseline.build.patch).

## 2. Outcome of every attempt

| | Baseline | Best |
|---|---:|---:|
| Attempts | 81 | 81 |
| **Passed** | **34** (42.0%) | **48** (59.3%) |
| Finished on its own, passed | 34 | 42 |
| Finished on its own, failed the check | 6 | 8 |
| Interrupted by the watchdog, passed | 0 | 6 |
| Interrupted by the watchdog, failed the check | 0 | 25 |
| Timed out, never checked | 41 | 0 |
| Harness errors (no valid attempt after retries) | 0 | 0 |

The watchdog belongs to the best build only. It is recognised in each attempt's `agent.log` by its
`[claude:watchdog] ... interrupting stream` line. The two groups do not overlap in run time: every interrupted
attempt had run for at least 451.5 s (the cut-off is 450 s), and every attempt that finished on its
own had finished within 440.9 s.

## 3. Task by task

Pairs valid in both builds: **81**. Baseline passed 34, best passed 48.
**Gained 16, lost 2, exact McNemar p = 0.001.** One attempt per task per build, so this is
a description of one run, not a test of how often it would recur.

| The baseline's attempt | Pairs | Baseline passed | Best passed |
|---|---:|---:|---:|
| Timed out | 41 | 0 | 15 |
| Finished in time | 40 | 34 | 33 |

How the best build's attempts ended, by what the baseline did on the same task:

| The baseline's attempt | Best: finished on its own, passed | Best: finished on its own, failed | Best: interrupted, passed | Best: interrupted, failed |
|---|---:|---:|---:|---:|
| Timed out (41) | 10 | 2 | 5 | 24 |
| Finished in time (40) | 32 | 6 | 1 | 1 |

**Gained (16, only the best build passed):** `beautify-web-js-beautify-6de9268`, `bgsetup-autossh-reverse-tunnel`, `caddy-782a3c7`, `celery-celery-03e3359`, `danwahlin-angular-jumpstart-12fa4e4`, `dbsetup-postgresql-1`, `deps-devise-31774`, `deps-openecho-28cb7`, `deps-origen-3e2f3`, `deps-react-most-wanted-2e3f0`, `hybridgroup-cylon-0ba0301`, `monero-8468549`, `networkx-networkx-c107d25`, `pypa-packaging-4493dfc`, `ta-lib-python-0c957ed`, `whisper-517a43e`.

**Lost (2, only the baseline passed):** `microsoft-typescript-vue-starter-c451742`, `psf-black-c204232`.

## 4. Turns, time and latency

| | Baseline | Best |
|---|---:|---:|
| Turns per task (mean / median / p90 / max) | 17.4 / 16 / 28 / 37 | 15.9 / 15 / 23 / 42 |
| Wall time per attempt, s, including the check (mean / median / p90) | 414 / 489 / 532 | 382 / 391 / 558 |
| Model reply per turn, s (median / p90) | 3.44 / 17.14 | 3.46 / 17.15 |
| Tool execution per turn, s (median / p90) | 0.16 / 26.38 | 0.25 / 58.26 |
| API time to first byte, ms (median / p90) | 1356 / 5078 | 1315 / 4609 |
| API time for a whole reply, ms (median / p90) | 6120 / 23203 | 5796 / 22606 |

Model reply time is the time from a tool result to the next reply; tool execution time is the time from a reply to its
tool result. Both come from the timestamps the runner adds to every trace entry. Wall time includes the check, so a
timed-out or interrupted attempt shows more than 480 s. Turns are counted from the trace for every attempt, as tool
rounds plus the final reply. The Claude Code CLI's own count is the same for attempts that finish on their own, and is
usually one higher after a watchdog interrupt.

## 5. Tokens and cost

| | Baseline | Best |
|---|---:|---:|
| Prompt tokens, including cached | 21,238,223 | 18,164,066 |
| Of which cached | 11,855,440 | 9,742,482 |
| Completion tokens | 369,464 | 350,465 |
| **Cost, all calls** | **$1.6025** | **$1.4256** |
| Cost per task (mean / median / p90) | $0.0198 / $0.0148 / $0.0388 | $0.0176 / $0.0105 / $0.0433 |

**Where the numbers come from.** Cost and tokens are OpenRouter's own per-call records (`total_cost`, native token counts),
attributed to tasks through each attempt's Claude Code session id. The records equal what OpenRouter charges: in a 36-call
test across nine providers on an idle key, the records summed to $0.010434 and the key counter rose $0.010433 once it settled.

**What is not used.**

- The Claude Code CLI's own cost ($24.72 baseline, $53.57 best) is not used. The CLI does not know this model and prices it
  at a Claude rate, about 15x and 38x too high.
- The CLI's token counts are not used. They omit calls that were aborted or retried, and the timed-out attempts report none.
  For 40 of the 40 baseline attempts that reported usage the CLI's counts equal OpenRouter's records; for the
  best build that holds for 69 of 81, and in the others OpenRouter billed more (the request cut off at a watchdog interrupt is billed but not counted by the CLI).
- The OpenRouter key's usage counter is not used as a total: the key is shared, so the counter also includes other people's use.

**Providers set the price.** For this model OpenRouter lists prices from $0.15 per million input tokens
(the list price shown first) up to $0.38 among the providers used, and it picks a provider for every call. The mix that served each
build is below, so part of a cost difference between the builds is routing luck.

| Provider | Baseline calls | Best calls |
|---|---:|---:|
| Relace | 600 | 539 |
| DeepInfra | 508 | 505 |
| Morph | 39 | 50 |
| Wafer | 26 | 15 |
| Fireworks | 18 | 14 |
| Parasail | 17 | 10 |
| Modal | 6 | 11 |
| Phala | 1 | 12 |
| AtlasCloud | 11 | 0 |
| DigitalOcean | 5 | 5 |
| Venice | 6 | 3 |
| SiliconFlow | 3 | 3 |
| Makora | 4 | 1 |
| Together | 4 | 0 |

**Most expensive attempts.**

| Baseline | Cost | Best | Cost |
|---|---:|---|---:|
| `mampfes-hacs_waste_collection_schedule-dbab343` | $0.1027 | `deps-react-most-wanted-cbc29` | $0.1439 |
| `nedbat-coveragepy-9d0eb02` | $0.0739 | `pypa-pipenv-b895476` | $0.1173 |
| `deps-react-most-wanted-cbc29` | $0.0720 | `nedbat-coveragepy-9d0eb02` | $0.0551 |
| `beautify-web-js-beautify-6de9268` | $0.0514 | `deps-amazon-cognito-saml-idp-c076c` | $0.0523 |
| `bgsetup-autossh-reverse-tunnel` | $0.0460 | `hackmdio-codimd-f00df50` | $0.0512 |

**Calls not in the cost.** 0 request(s) were cut off before OpenRouter's id for them reached the proxy, so they have no record and may have been billed
(the most a single call cost was under a cent). Requests cut off the same way that had already received their id (8 in the baseline, 11 in the best build) are in the records.

## 6. Model calls

| | Baseline | Best |
|---|---:|---:|
| Model calls | 1,248 | 1,168 |
| Calls that carried the provider setting | 1,248 | 1,168 |
| Calls served by the excluded provider (among calls with a provider record) | 0 | 0 |
| Non-200 model calls | 0 | 0 |
| Empty replies (a finished request with no content) | 0 | 0 |
| Requests cut off by the client before finishing | 8 | 11 |

`count_tokens` requests, an endpoint OpenRouter does not have, return 404 and are free; they are not model calls.

## 7. The agent and the harness

Inside every container the agent can read the task prompt (`/testbed/.setupbench-task.txt`), a small metadata file
(`.setupbench-cache.json`: task id, repository, commit), its own log and trace, the runner's source
(`/opt/setupbench-ada-runner.ts`) and `/setupbench-fixtures`, the per-task setup scripts. None of these contains a solution or
a success command. Counting attempts whose tool calls mention any of them:

| | Baseline | Best |
|---|---:|---:|
| This run (V4.1 Flash) | 76 of 81 | 74 of 81 |
| Of which read the runner's source | 10 | 7 |

It is the same for both builds. It shows an agent exploring its environment, which is part of this benchmark as run here.

## 8. Every task

Turns and seconds are per attempt; the cost is that attempt's own OpenRouter cost. "interrupted" means the best build's watchdog
stopped Ada at 450 s and the check then ran.

| Task | Type | Baseline | Turns | s | Cost | Best | Turns | s | Cost | Pair |
|---|---|---|---:|---:|---:|---|---:|---:|---:|---|
| `beautify-web-js-beautify-6de9268` | reposetup | timed out | 34 | 531 | $0.0514 | passed | 17 | 526 | $0.0120 | gained |
| `benjaminp-six-c1b416f` | reposetup | passed | 13 | 311 | $0.0053 | passed | 8 | 212 | $0.0031 |  |
| `bgsetup-autossh-logging` | bgsetup | timed out | 24 | 532 | $0.0179 | failed (interrupted) | 22 | 473 | $0.0302 |  |
| `bgsetup-autossh-reverse-tunnel` | bgsetup | timed out | 20 | 512 | $0.0460 | passed | 13 | 213 | $0.0096 | gained |
| `bgsetup-celery-systemd` | bgsetup | timed out | 9 | 551 | $0.0055 | failed (interrupted) | 11 | 534 | $0.0034 |  |
| `bgsetup-filewatcher-daemon` | bgsetup | passed | 11 | 286 | $0.0051 | passed | 10 | 252 | $0.0034 |  |
| `bgsetup-filewatcher-daemon-2` | bgsetup | passed | 13 | 312 | $0.0091 | passed | 14 | 390 | $0.0042 |  |
| `bgsetup-gunicorn-systemd-socket` | bgsetup | failed | 13 | 252 | $0.0146 | failed | 12 | 367 | $0.0066 |  |
| `bgsetup-multiprocess-master-worker` | bgsetup | passed | 31 | 363 | $0.0318 | passed | 11 | 176 | $0.0185 |  |
| `bolsote-isoduration-ae0bd61` | reposetup | passed | 12 | 341 | $0.0102 | passed | 9 | 350 | $0.0059 |  |
| `caddy-782a3c7` | reposetup | timed out | 23 | 491 | $0.0355 | passed | 17 | 373 | $0.0230 | gained |
| `cassandra-73cd2c5` | reposetup | timed out | 15 | 499 | $0.0093 | failed (interrupted) | 18 | 558 | $0.0131 |  |
| `celery-celery-03e3359` | reposetup | timed out | 22 | 488 | $0.0388 | passed | 19 | 317 | $0.0265 | gained |
| `danwahlin-angular-jumpstart-12fa4e4` | reposetup | timed out | 13 | 552 | $0.0148 | passed (interrupted) | 11 | 639 | $0.0047 | gained |
| `dbsetup-mongodb-1` | dbsetup | passed | 10 | 242 | $0.0076 | passed | 7 | 175 | $0.0022 |  |
| `dbsetup-mongodb-2` | dbsetup | passed | 18 | 231 | $0.0161 | passed | 12 | 149 | $0.0080 |  |
| `dbsetup-mysql-1` | dbsetup | passed | 21 | 242 | $0.0407 | passed | 13 | 275 | $0.0064 |  |
| `dbsetup-mysql-2` | dbsetup | timed out | 20 | 495 | $0.0186 | failed | 27 | 266 | $0.0075 |  |
| `dbsetup-mysql-3` | dbsetup | failed | 18 | 445 | $0.0129 | failed | 13 | 242 | $0.0075 |  |
| `dbsetup-postgresql-1` | dbsetup | failed | 10 | 218 | $0.0032 | passed | 12 | 189 | $0.0091 | gained |
| `dbsetup-postgresql-2` | dbsetup | failed | 14 | 259 | $0.0072 | failed | 9 | 211 | $0.0029 |  |
| `dbsetup-postgresql-3` | dbsetup | passed | 19 | 265 | $0.0316 | passed | 10 | 158 | $0.0092 |  |
| `dbsetup-redis-1` | dbsetup | failed | 13 | 152 | $0.0073 | failed | 5 | 90 | $0.0009 |  |
| `dbsetup-redis-2` | dbsetup | passed | 16 | 287 | $0.0041 | passed | 11 | 115 | $0.0029 |  |
| `dbsetup-sqlite-1` | dbsetup | passed | 6 | 97 | $0.0080 | passed | 8 | 130 | $0.0016 |  |
| `dbsetup-sqlite-2` | dbsetup | passed | 6 | 83 | $0.0034 | passed | 9 | 131 | $0.0023 |  |
| `dbsetup-sqlite-3` | dbsetup | passed | 9 | 75 | $0.0077 | passed | 11 | 109 | $0.0079 |  |
| `deps-aether-0b82a` | dependency_resolution | passed | 13 | 255 | $0.0070 | passed | 10 | 340 | $0.0052 |  |
| `deps-amazon-cognito-saml-idp-c076c` | dependency_resolution | timed out | 33 | 504 | $0.0458 | failed (interrupted) | 25 | 458 | $0.0523 |  |
| `deps-decidim-module-navbar_links-c7ddb` | dependency_resolution | timed out | 22 | 509 | $0.0341 | failed (interrupted) | 21 | 457 | $0.0433 |  |
| `deps-devise-31774` | dependency_resolution | timed out | 23 | 484 | $0.0222 | passed | 16 | 448 | $0.0112 | gained |
| `deps-engine-34e61` | dependency_resolution | timed out | 37 | 485 | $0.0264 | failed (interrupted) | 19 | 468 | $0.0211 |  |
| `deps-gatsby-plugin-intl-2b7ac` | dependency_resolution | timed out | 23 | 503 | $0.0219 | failed (interrupted) | 19 | 520 | $0.0091 |  |
| `deps-openecho-28cb7` | dependency_resolution | timed out | 27 | 511 | $0.0266 | passed (interrupted) | 34 | 550 | $0.0434 | gained |
| `deps-origen-3e2f3` | dependency_resolution | timed out | 24 | 488 | $0.0366 | passed (interrupted) | 27 | 459 | $0.0463 | gained |
| `deps-rails-6cd76` | dependency_resolution | timed out | 28 | 550 | $0.0098 | failed (interrupted) | 31 | 555 | $0.0121 |  |
| `deps-react-most-wanted-2e3f0` | dependency_resolution | timed out | 29 | 489 | $0.0117 | passed (interrupted) | 16 | 635 | $0.0139 | gained |
| `deps-react-most-wanted-cbc29` | dependency_resolution | timed out | 35 | 494 | $0.0720 | failed (interrupted) | 42 | 494 | $0.1439 |  |
| `deps-react-virtualized-sticky-tree-32be9` | dependency_resolution | passed | 18 | 502 | $0.0099 | passed (interrupted) | 21 | 534 | $0.0095 |  |
| `deps-ultimate-frontrunning-bot-449d6` | dependency_resolution | passed | 9 | 407 | $0.0049 | passed | 10 | 351 | $0.0031 |  |
| `deps-volt-react-dashboard-3a3f3` | dependency_resolution | timed out | 23 | 512 | $0.0211 | failed (interrupted) | 19 | 593 | $0.0161 |  |
| `dishait-tov-template-39c0898` | reposetup | passed | 18 | 398 | $0.0194 | passed | 17 | 413 | $0.0161 |  |
| `dstl-stone-soup-4b6bd37` | reposetup | timed out | 14 | 505 | $0.0094 | failed (interrupted) | 13 | 503 | $0.0050 |  |
| `falconry-falcon-cae50da` | reposetup | timed out | 9 | 499 | $0.0089 | failed (interrupted) | 16 | 474 | $0.0233 |  |
| `fsspec-filesystem_spec-3ff5fca` | reposetup | timed out | 20 | 492 | $0.0287 | failed | 15 | 405 | $0.0195 |  |
| `hackmdio-codimd-f00df50` | reposetup | timed out | 18 | 545 | $0.0218 | failed (interrupted) | 18 | 475 | $0.0512 |  |
| `hoodiehq-hoodie-bd1354f` | reposetup | passed | 16 | 542 | $0.0245 | passed | 18 | 459 | $0.0199 |  |
| `hybridgroup-cylon-0ba0301` | reposetup | timed out | 10 | 498 | $0.0084 | passed | 19 | 436 | $0.0124 | gained |
| `ionelmc-python-tblib-9f6f864` | reposetup | passed | 9 | 291 | $0.0094 | passed | 10 | 230 | $0.0058 |  |
| `johnpapa-vscode-angular-snippets-1551fe1` | reposetup | passed | 23 | 433 | $0.0167 | passed | 10 | 322 | $0.0076 |  |
| `laramies-theharvester-e25c269` | reposetup | failed | 18 | 335 | $0.0070 | failed | 13 | 343 | $0.0148 |  |
| `lhartikk-naivechain-dfd2481` | reposetup | timed out | 7 | 498 | $0.0026 | failed (interrupted) | 12 | 559 | $0.0048 |  |
| `mampfes-hacs_waste_collection_schedule-dbab343` | reposetup | passed | 20 | 313 | $0.1027 | passed | 14 | 341 | $0.0180 |  |
| `marshmallow-code-marshmallow-659fed5` | reposetup | passed | 12 | 175 | $0.0039 | passed | 11 | 286 | $0.0061 |  |
| `melt-ui-melt-ui-c566aae` | reposetup | passed | 13 | 405 | $0.0115 | passed | 14 | 568 | $0.0177 |  |
| `microsoft-azure-pipelines-tasks-bfcd4b2` | reposetup | timed out | 16 | 493 | $0.0191 | failed (interrupted) | 23 | 468 | $0.0162 |  |
| `microsoft-typescript-vue-starter-c451742` | reposetup | passed | 26 | 241 | $0.0415 | failed (interrupted) | 22 | 469 | $0.0264 | lost |
| `monero-8468549` | reposetup | timed out | 10 | 490 | $0.0075 | passed | 16 | 257 | $0.0061 | gained |
| `nedbat-coveragepy-9d0eb02` | reposetup | timed out | 32 | 503 | $0.0739 | failed (interrupted) | 24 | 639 | $0.0551 |  |
| `networkx-networkx-c107d25` | reposetup | timed out | 8 | 487 | $0.0068 | passed | 11 | 592 | $0.0037 | gained |
| `openai-openai-node-8958d97` | reposetup | passed | 19 | 537 | $0.0266 | passed | 13 | 336 | $0.0081 |  |
| `ousret-charset_normalizer-816c998` | reposetup | passed | 13 | 270 | $0.0049 | passed | 15 | 306 | $0.0048 |  |
| `pallets-flask-2fec0b2` | reposetup | passed | 23 | 375 | $0.0272 | passed | 12 | 235 | $0.0181 |  |
| `prometheus-bd5b2ea` | reposetup | timed out | 10 | 550 | $0.0057 | failed (interrupted) | 17 | 490 | $0.0042 |  |
| `psf-black-c204232` | reposetup | passed | 15 | 502 | $0.0186 | failed | 16 | 345 | $0.0066 | lost |
| `public-apis-public-apis-b354ba6` | reposetup | passed | 21 | 478 | $0.0269 | passed | 17 | 343 | $0.0219 |  |
| `pypa-packaging-4493dfc` | reposetup | timed out | 19 | 500 | $0.0171 | passed | 15 | 370 | $0.0222 | gained |
| `pypa-pipenv-b895476` | reposetup | timed out | 28 | 525 | $0.0329 | failed (interrupted) | 32 | 482 | $0.1173 |  |
| `pytesseract-df9fce0` | reposetup | passed | 19 | 342 | $0.0266 | passed | 11 | 179 | $0.0068 |  |
| `python-hyper-rfc3986-75e77ba` | reposetup | passed | 11 | 240 | $0.0061 | passed | 10 | 257 | $0.0053 |  |
| `qubvel-segmentation_models-pytorch-ccccadd` | reposetup | timed out | 10 | 549 | $0.0043 | failed (interrupted) | 14 | 470 | $0.0130 |  |
| `reflex-dev-reflex-8657976` | reposetup | timed out | 15 | 495 | $0.0116 | failed (interrupted) | 18 | 564 | $0.0271 |  |
| `servo-e199a67` | reposetup | timed out | 20 | 503 | $0.0190 | failed (interrupted) | 18 | 476 | $0.0408 |  |
| `spring-petclinic-2aa53f9` | reposetup | timed out | 15 | 492 | $0.0154 | failed (interrupted) | 15 | 479 | $0.0211 |  |
| `ta-lib-python-0c957ed` | reposetup | timed out | 19 | 498 | $0.0243 | passed | 14 | 324 | $0.0238 | gained |
| `testing-cabal-testtools-ef5c465` | reposetup | passed | 16 | 381 | $0.0089 | passed | 9 | 303 | $0.0032 |  |
| `transitive-bull-chatgpt-api-811ae8f` | reposetup | passed | 11 | 512 | $0.0124 | passed | 22 | 451 | $0.0114 |  |
| `wagtail-wagtail-28fcd01` | reposetup | timed out | 12 | 506 | $0.0333 | failed (interrupted) | 21 | 514 | $0.0450 |  |
| `whisper-517a43e` | reposetup | timed out | 12 | 494 | $0.0181 | passed (interrupted) | 18 | 463 | $0.0106 | gained |
| `whisper-brokendeps-517a43e` | reposetup | timed out | 14 | 505 | $0.0135 | failed (interrupted) | 16 | 478 | $0.0104 |  |
| `yaml-pyyaml-a2d19c0` | reposetup | passed | 15 | 345 | $0.0118 | passed | 19 | 391 | $0.0105 |  |

## 9. Checks on the data

| Check | Result |
|---|---|
| Attempts with a `trace.jsonl`, `agent.log` and `result.json` | 162 of 162 (the others were harness errors with no container) |
| Models billed, from the CLI's usage and from OpenRouter's records | only `deepseek/deepseek-v4.1-flash` (`deepseek/deepseek-v4.1-flash-20260910`) |
| API key anywhere in the evidence | none (searched for `sk-or-` tokens and for the key itself) |
| `python3 bench/deepseek_summary.py ada/runs/deepseek-v4.1-flash/r1_all` run twice | byte-identical output |

## 10. What this run does not show

- One attempt per task per build.
- The run was made in parts under different machine load (section 1). Both builds always ran together, so within a part they
  faced the same load; timeouts depend on load, and the parts differ.
- The baseline includes a 7-line pass-through shim; it is not byte-for-byte `df0c537`.
- The four default-on changes of the best build are not separated by this run.
- Traces are what the runner keeps: each tool input and result is cut at 4,000 characters and each thinking block at 2,000.

## 11. Regenerating this record

```bash
python3 bench/merge_runs.py ada/runs/deepseek-v4.1-flash/r1_all ada/runs/deepseek-v4.1-flash/r1 ada/runs/deepseek-v4.1-flash/r1_set41 ada/runs/deepseek-v4.1-flash/r1_retry   # only if the folder does not exist yet
python3 bench/deepseek_summary.py ada/runs/deepseek-v4.1-flash/r1_all
```
