# Terminal-Bench 2.0 — 40-Task Selection (Final Comparison Set)

**Dataset:** `terminal-bench/terminal-bench-2` (89 tasks). Selection script: `bench/select_tasks.py` (deterministic).

## Selection rule (identical to the 10-task run)
Rank all 89 tasks by: (1) `difficulty` ascending (easy → medium → hard); (2) `expert_time_estimate_min` ascending; (3) `agent.timeout_sec` ascending (tie-break). Take the first 40.

Difficulty distribution of the 40: 4 easy / 36 medium / 0 hard. All 10 tasks from the original 10-task comparison are included (they are ranks 1–10). The 30 NEW tasks (ranks 11–40) need fresh baseline runs; the 10 originals reuse `bench/results-baseline/2026-09-07__14-32-12`.

## Selected tasks (in ranked order)

| # | Task | Difficulty | Expert min | Agent timeout (s) | Category | Docker image |
|---|------|-----------|-----------:|------------------:|----------|--------------|
| 1 | fix-git | easy | 5 | 900 | software-engineering | alexgshaw/fix-git:20251031 |
| 2 | prove-plus-comm | easy | 5 | 900 | software-engineering | alexgshaw/prove-plus-comm:20251031 |
| 3 | cobol-modernization | easy | 20 | 900 | software-engineering | alexgshaw/cobol-modernization:20251031 |
| 4 | overfull-hbox | easy | 60 | 750 | debugging | alexgshaw/overfull-hbox:20251031 |
| 5 | crack-7z-hash | medium | 5 | 900 | security | alexgshaw/crack-7z-hash:20251031 |
| 6 | raman-fitting | medium | 5 | 900 | scientific-computing | alexgshaw/raman-fitting:20251031 |
| 7 | mteb-leaderboard | medium | 5 | 3600 | data-science | alexgshaw/mteb-leaderboard:20251031 |
| 8 | kv-store-grpc | medium | 15 | 900 | software-engineering | alexgshaw/kv-store-grpc:20251031 |
| 9 | pytorch-model-recovery | medium | 15 | 900 | model-training | alexgshaw/pytorch-model-recovery:20251031 |
| 10 | constraints-scheduling | medium | 15 | 1200 | personal-assistant | alexgshaw/constraints-scheduling:20251031 |
| 11 | mteb-retrieve | medium | 15 | 1800 | data-science | alexgshaw/mteb-retrieve:20251031 |
| 12 | hf-model-inference | medium | 20 | 900 | data-science | alexgshaw/hf-model-inference:20251031 |
| 13 | merge-diff-arc-agi-task | medium | 20 | 900 | debugging | alexgshaw/merge-diff-arc-agi-task:20251031 |
| 14 | nginx-request-logging | medium | 20 | 900 | system-administration | alexgshaw/nginx-request-logging:20251031 |
| 15 | openssl-selfsigned-cert | medium | 20 | 900 | security | alexgshaw/openssl-selfsigned-cert:20251031 |
| 16 | polyglot-c-py | medium | 20 | 900 | software-engineering | alexgshaw/polyglot-c-py:20251031 |
| 17 | vulnerable-secret | medium | 20 | 900 | security | alexgshaw/vulnerable-secret:20251031 |
| 18 | break-filter-js-from-html | medium | 20 | 1200 | security | alexgshaw/break-filter-js-from-html:20251031 |
| 19 | count-dataset-tokens | medium | 30 | 900 | model-training | alexgshaw/count-dataset-tokens:20251031 |
| 20 | extract-elf | medium | 30 | 900 | file-operations | alexgshaw/extract-elf:20251031 |
| 21 | git-leak-recovery | medium | 30 | 900 | software-engineering | alexgshaw/git-leak-recovery:20251031 |
| 22 | multi-source-data-merger | medium | 30 | 900 | data-processing | alexgshaw/multi-source-data-merger:20251031 |
| 23 | pytorch-model-cli | medium | 30 | 900 | model-training | alexgshaw/pytorch-model-cli:20251031 |
| 24 | qemu-alpine-ssh | medium | 30 | 900 | system-administration | alexgshaw/qemu-alpine-ssh:20251031 |
| 25 | qemu-startup | medium | 30 | 900 | system-administration | alexgshaw/qemu-startup:20251031 |
| 26 | sanitize-git-repo | medium | 30 | 900 | security | alexgshaw/sanitize-git-repo:20251031 |
| 27 | sqlite-with-gcov | medium | 30 | 900 | system-administration | alexgshaw/sqlite-with-gcov:20251031 |
| 28 | tune-mjcf | medium | 30 | 900 | scientific-computing | alexgshaw/tune-mjcf:20251031 |
| 29 | code-from-image | medium | 30 | 1200 | software-engineering | alexgshaw/code-from-image:20251031 |
| 30 | financial-document-processor | medium | 30 | 1200 | data-processing | alexgshaw/financial-document-processor:20251031 |
| 31 | custom-memory-heap-crash | medium | 30 | 1800 | debugging | alexgshaw/custom-memory-heap-crash:20251031 |
| 32 | dna-insert | medium | 30 | 1800 | scientific-computing | alexgshaw/dna-insert:20251031 |
| 33 | reshard-c4-data | medium | 30 | 3600 | data-science | alexgshaw/reshard-c4-data:20251031 |
| 34 | large-scale-text-editing | medium | 40 | 1200 | file-operations | alexgshaw/large-scale-text-editing:20251031 |
| 35 | chess-best-move | medium | 45 | 900 | games | alexgshaw/chess-best-move:20251031 |
| 36 | db-wal-recovery | medium | 45 | 900 | file-operations | alexgshaw/db-wal-recovery:20251031 |
| 37 | regex-log | medium | 45 | 900 | data-processing | alexgshaw/regex-log:20251031 |
| 38 | filter-js-from-html | medium | 45 | 1800 | security | alexgshaw/filter-js-from-html:20251031 |
| 39 | build-cython-ext | medium | 60 | 900 | debugging | alexgshaw/build-cython-ext:20251031 |
| 40 | gcode-to-text | medium | 60 | 900 | file-operations | alexgshaw/gcode-to-text:20251031 |

## Reuse plan

- **Baseline (ada-baseline.tgz, df0c537):** run the 30 NEW tasks into `bench/results-baseline-40/`; reuse the 10 original trials from `bench/results-baseline/2026-09-07__14-32-12`.
- **Best2 (ada-best2.tgz):** run all 40 into `bench/results-best2-40/`; the 8 pilot trials (`bench/results-best2-pilot/2026-09-07__17-56-49`) are reusable for their tasks (identical conditions: variant=best2, -n 4, same runner_cap_ms per task) — merged explicitly in the final report.
