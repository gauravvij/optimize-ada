# P3 Candidate — Paired Gate Report (VERDICT: REVERT)

**Candidate:** P3 "late wrap-up" — `ADA_TIME_HINTS` default flipped ON and
`ADA_WRAP_UP_MS` default flipped to 96,000 ms (wrap-up fires at ~96 s remaining
= 80% of a 480 s budget consumed). Env overrides preserved. Two code-default
flips only, in `agent/claude/agent.ts` (+ test file).

- Branch `p3-late-wrapup`, commit `9f2e34d` (agent tree `811a16e4a67e`); the
  `ada-p3` worktree was removed 2026-09-18 after its diagnostics were archived to
  `bench/p3_evidence/` — the branch is preserved in the repo as the experiment record
- Unit tests: 18/18; no new `tsc` errors
- Shipped arm: `ada/` @ `ada-best-61pct-20260916` (former mirror commit `c6f917e` —
  historical pin, mirror removed 2026-09-18;
  agent tree `dab704de524a`), `agent/` clean throughout

## Run

- Driver: `bench/run_p3_paired.sh`, ts `20260917T0602Z`, launched 2026-09-17 06:02 UTC,
  completed 12:35:58 UTC (~6.5 h)
- 2 replicates, both arms run concurrently minute-for-minute; 25 tasks from
  `bench/FAILING25.txt`; 480 s task / 600 s grader; concurrency 1 per arm; seed 20260907
- Machine artifact of record: `bench/P3_PAIRED_20260917T0602Z.json`
- Note: an earlier attempt (ts `20260916T1340Z`) was **voided by a host reboot** at
  ~14:49 UTC Sep 16 mid-replicate-1 (8/25 partial rows) — that data is excluded and
  must not be quoted as evidence.

## Results (exact McNemar, paired, same-day)

| Rep | n (valid pairs) | shipped pass | p3 pass | net | gained | lost | p |
|-----|----|----|----|----|----|----|----|
| 1 | 25 | 4 | 3 | **−1** | 1 | 2 | 1.0 |
| 2 | 21 | 2 | 5 | **+3** | 3 | 0 | 0.25 |
| **Pooled** | 46 | 6 | 8 | **+2** | 4 | 2 | 0.6875 |

Invalid rows (excluded from n): rep-2 shipped arm 3, p3 arm 1. Zero task timeouts
in both arms — no 480 s clock-outs either side.

### Flips (valid pairs only)

| Rep | Direction | Task |
|-----|-----------|------|
| 1 | GAINED | hackmdio-codimd-f00df50 |
| 1 | LOST | networkx-networkx-c107d25 |
| 1 | LOST | reflex-dev-reflex-8657976 |
| 2 | GAINED | deps-amazon-cognito-saml-idp-c076c |
| 2 | GAINED | networkx-networkx-c107d25 |
| 2 | GAINED | whisper-brokendeps-517a43e |

(hackmdio-codimd-f00df50 also passed on the p3 arm in rep 2, but the shipped-arm row
for that task was invalid, so the pair is excluded.)

### Reading

- `networkx-networkx-c107d25` flips **both directions** across replicates — classic
  noise-floor behavior (~11 flips / 79 tasks established previously). It contributes
  nothing to the causal claim.
- The pooled +2 is entirely below both the pre-registered gate (+5) and the noise
  floor; p = 0.69 means the sign itself is unresolvable at this n.
- Rep 1 was negative (−1), independently violating the "no negative replicate" clause.
- No efficiency claim is possible either: P3 did not reduce turns or clock-outs
  observably, and both arms produced zero 480 s timeouts.

## Pre-registered gate (fixed before spend)

Keep P3 only if ALL of:

1. every replicate completes with both diagnostics files — **PASS** (both complete)
2. pooled net (p3 − shipped) ≥ +5 tasks over the paired pool — **FAIL** (+2)
3. no replicate has a negative net — **FAIL** (rep 1 = −1)

## Verdict: **REVERT — P3 does not ship**

- Shipped build is untouched (tag `ada-best-61pct-20260916`, agent tree `dab704d`, clean).
- The `ada-p3` worktree was removed 2026-09-18 after its diagnostics were archived to
  `bench/p3_evidence/`; branch `p3-late-wrapup` @ `9f2e34d` is preserved in the repo as
  the un-promoted experiment record. No defaults from it propagate.
- Late wrap-up + default-on time hints are **not effective levers on this pool at 480 s**.
  Combined with the budget probe's MIXED verdict (7/25 convert at 960 s), the evidence
  now says the FAILING25 pool is mostly **hard**, not merely slow.
