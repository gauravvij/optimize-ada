# SetupBench frozen candidate — historical 900-second evidence index

This index describes the earlier 900-second validation. For the separate
1200-second validation and its results, see the [current branch README](../../README.md).

This branch archives the exact Ada candidate evaluated in the accompanying
12-task SetupBench validation reports. It is separate from the Terminal-Bench
campaign on `main` and must not be presented as an accuracy-proven release.

## Candidate provenance

- Upstream Ada base: `rabbah/ada@ebaeb9a`
- Local evaluation-seam commit: `0c5e1da7342ff86147b217a09c243cf17bf6c50d`
- Candidate changes: `ada/agent/claude/agent.ts` and
  `ada/agent/coding-guidance.ts`
- Frozen patch SHA-256:
  `e874056498af109118170aab8e2bc02237e9a23ee6378188dbaf06fb3a577903`
- `agent/claude/agent.ts` SHA-256:
  `ec71bbe75f1b0d8cfedb7f86fd6661c546fe320286ba2e0d0d9a6db5ed51e73c`
- `agent/coding-guidance.ts` SHA-256:
  `1eea11541692663e3e32a4301746bd87636f7756637c8973e6141b26ff46925c`

The complete frozen Ada source is under `ada/`. The standalone candidate diff
is `frozen-candidate.patch`.

## Measured outcome

Across three repetitions on 12 validation tasks, original Ada passed 23/36 and
the candidate passed 24/36. This was not statistically significant. The
candidate was descriptively faster and recorded fewer timeouts, turns, and
tokens in the measured sample.

See `ADA_SETUPBENCH_DIRECT_OUTCOME.md` for the numbers and
`ADA_SETUPBENCH_EVALUATION_REPORT.md` for protocol details and limitations.

## 1200-second validation (two models)

The canonical 1200-second validation is documented in the [branch README](../../README.md). It was
run twice under the identical protocol, once per model:

- **`z-ai/glm-5.3-flash`** — `ADA_SETUPBENCH_VALIDATION_1200S_PARALLEL3_REPORT.md` +
  `ADA_SETUPBENCH_VALIDATION_1200S_COMPACT.json`. Result: 26/36 vs 26/36 (tie).
- **`deepseek/deepseek-v4.1-flash`** — `ADA_SETUPBENCH_DSV4_VALIDATION12_REPORT.md` +
  `ADA_SETUPBENCH_DSV4_VALIDATION12_COMPACT.json`. Result: 26/36 vs 26/36 (tie) — the same outcome,
  confirming the tie is not model-specific.

The DeepSeek baseline root-cause and model-validity investigation is in
`ADA_SETUPBENCH_DSV4_BASELINE_ROOTCAUSE.md`.
