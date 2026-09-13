# E-opt1: Env-gated concision guidance (systemPromptAppend)

## Hypothesis

Baseline trace mining (eval/analysis/trace-signals.md over 60 ada-bridge trials)
found two cost levers the bridge can influence without touching the tool set or
permission mode:
- 22 tool results >10k chars accounted for **44% of ALL tool-result chars**
  (largest consumers: sanitize-git-repo 103K/20 tools, fix-code-vulnerability
  84K/56, db-wal-recovery 44K/35, password-recovery 35K/52).
- mean **8,003 output tokens/trial** (max 34,384) — verbose narration on the
  output-token bill.

Hypothesis: appending terse "operating-efficiency" guidance to the system prompt
(via `systemPromptAppend`) steers the model to cheaper operations (targeted
reads, summarize-not-echo, no re-runs, terse narration) → lower cost per trial
with no pass-rate regression.

## Change

- New module `ada/agent/concision-guidance.ts` — `concisionGuidance(env)` returns
  the guidance string ONLY when `ADA_CONCISION_GUIDANCE=1`, else `""`.
- `ada/agent/index.ts` `runTurn()` — `systemPromptAppend` is now an
  array-join of `githubPromptGuidance(...)` + `concisionGuidance()`,
  `.filter(s => s && s.trim().length > 0).join("\n\n")`.
  When the env gate is off the join equals the prior single string → baseline
  behavior byte-identical.
- Adapter `eval/ada-agent/ada_agent.py` — new agent kwarg
  `concision_guidance: bool = False`; `_bridge_env()` sets
  `ADA_CONCISION_GUIDANCE="1"` only when enabled (`--ak concision_guidance=1`).
  Default OFF keeps control/baseline arms clean.
- Synced to both the source repo (`/root/optimize_ada/ada/agent/`) and the
  harness runtime bundle (`/root/optimize_ada/eval/ada-runtime/ada/agent/`);
  md5 parity verified: index.ts `18ea37b1561eb353dd4d43c3c59d74fa`,
  concision-guidance.ts `024e4b492a75774e6ddb4b026806b01a` on both copies.

Full diff vs `ada` HEAD (includes the earlier cwd-patch hunks from adapter work):

```diff
--- a/agent/index.ts
+++ b/agent/index.ts
@@ import
+import { concisionGuidance } from "./concision-guidance.ts";
@@ runTurn()
     systemPromptAppend: [
       githubPromptGuidance({ configured: githubConfigured(), connected: !!githubToken }),
       concisionGuidance(),
     ]
       .filter((s) => s && s.trim().length > 0)
       .join("\n\n"),
```

## Dev probe (3 tasks x k=2, gate ON) — job `e-opt1-probe`

- 6/6 trials, 0 exceptions, mean reward 0.667, Pass@2 1.000, 4m27s.
- Direction vs arm B on same 3 tasks: aggregate cost $0.0575 vs $0.0582,
  out_tok 7421 vs 7561, wall 51.3s vs 53.2s → cost/latency direction down,
  no gross pass regression (every task solved ≥1/2).
- Verdict: PROMISING → proceeded to full arm.

## Full arm (15 tasks x k=4, gate ON) — job `e-opt1-arm`

- 60/60 trials, **0 exceptions**, mean reward **0.500** (30 pass/30 fail),
  Pass@2 0.622, Pass@4 0.733, 1h21m51s.
- Results: `eval/results/e-opt1-arm.jsonl` (60 records, 60 with cost).

## Decision (pre-registered rule; vs BASELINE ARM B only)

| Metric | Arm B | E-opt1 | Delta (E-opt1 − B) | 95% CI | Sig? |
|---|---|---|---|---|---|
| Pass rate | 0.550 (33/60) | 0.500 (30/60) | −0.050 | Wilson B [0.425,0.669]; E [0.377,0.623] | in noise band ✓ |
| Mean cost | $0.1024 | $0.1018 | +$0.0074 (paired, 14 tasks) | [−0.0074, +0.0221] | no |
| Mean wall | 296s | 187s→ new | −27.6s (paired, 15 tasks) | [−100.1s, +44.9s] | no |

- Per-task solved discordants: 1 B-only (regex-log), 2 E-only
  (large-scale-text-editing, password-recovery) → McNemar exact p = 1.0000.
- Cost pairing excluded large-scale-text-editing (arm B has only 3 usable
  costs there — one AgentTimeoutError with no usage). Wall pairing included all
  15 tasks (driver-measured duration exists for every trial in both arms).
- Decision rule: ACCEPT iff (cost OR wall delta significant at 95%) AND
  pass-rate delta within B's noise band. Cost and wall both NOT significant;
  pass delta within noise. → **VERDICT: REJECT** (no significant cost/latency
  delta; the guidance does not measurably move the needle at k=4).

## Re-test (v2, TREATED arm) — job `e-opt1-arm-v2` (replaces the invalidated v1)

### Why the re-test was required

The v1 full arm above (`e-opt1-arm`, Sep 2) was **silently invalidated**: it
ran through the same kwargs-swallowing adapter defect discovered during L1L2 —
harbor's `BaseAgent.__init__(**kwargs)` dropped `--ak concision_guidance`, so
`ADA_CONCISION_GUIDANCE` never reached the bridge and the "treated" run was
actually an **untreated baseline re-run** (0 treatment markers in its bridge
logs). `eval/results/e-opt1-arm.jsonl` is therefore NOT evidence against
concision guidance.

**Adapter fix (verified):** `eval/ada-agent/ada_agent.py` now has an explicit
`AdaBridgeAgent.__init__` that binds `--ak` kwargs to instance attributes and
`_bridge_env()` sets `ADA_CONCISION_GUIDANCE=1` only when
`concision_guidance=True` (default OFF keeps baseline arms clean). The same fix
also binds `self_verify`/`adaptive_concision`/`lever_debug` → `ADA_*` env vars.

### Zero-cost pre-flight (per L1L2 failed-approaches rule)

1. **Importlib kwargs-binding test** (host, no API spend): instantiating
   `AdaBridgeAgent(logs_dir, concision_guidance=True, lever_debug=True)`
   yields `_bridge_env()` with `ADA_CONCISION_GUIDANCE=1` and
   `ADA_LEVER_DEBUG=1`; default instance has neither key → gate OFF by
   default. `KWARGS BINDING VERIFIED`.
2. **md5 parity** between `/root/optimize_ada/ada/agent/` and
   `/root/optimize_ada/eval/ada-runtime/ada/agent/`: concision-guidance.ts
   `024e4b492a75774e6ddb4b026806b01a`, index.ts
   `37fd53b1c7e8dc15c61eb166910661d1` (post-L1L2 state), lever-guidance.ts
   `ccadffd92bfb5cfad02ccf2dd1fae277` — identical on both copies.
3. **In-container probe** `e-opt1-probe-v2` (2 tasks × k=1:
   fix-git + log-summary-date-ranges, `--ak concision_guidance=1
   lever_debug=1`): 2/2 trials, 0 exceptions, $0.0895. **Both** bridge logs
   contain the `Operating-efficiency guidance` marker and the lever-debug line
   `systemPromptAppend (2 part(s), 477+1018 chars)` → the guidance text
   reaches the composed system prompt. Treatment reach CONFIRMED before any
   paid spend.

### Full arm (15 tasks x k=4, gate ON) — job `e-opt1-arm-v2`

- 60/60 trials, 1 exception (large-scale-text-editing
  `AgentTimeoutError` @1200s — same task/kind as arm B's known exception),
  mean reward **0.483** (29 pass/31 fail), Pass@2 0.644, Pass@4 0.733,
  1h37m52s, started 2026-09-03T16:56:22Z → finished 2026-09-03T18:34:14Z.
- Results: `eval/results/e-opt1-arm-v2.jsonl` (60 records, arm=`e-opt1-v2`,
  59 with cost, total spend **$6.0042**; probe $0.0895).
- Treatment reach (post-run): **60/60 bridge logs** contain the
  `Operating-efficiency guidance` marker (see
  `verification-provenance-v2.md`).

### Decision v2 (pre-registered rule; vs BASELINE ARM B only)

Same rule as v1: ACCEPT iff (cost OR wall paired delta significant at 95%)
AND pass-rate delta within B's noise band. McNemar uses **position-based
within-task pairing** (the `trial` field is NOT comparable across arms).

| Metric | Arm B | E-opt1 v2 | Delta (v2 − B) | 95% CI | Sig? |
|---|---|---|---|---|---|
| Pass rate | 0.550 (33/60) | 0.483 (29/60) | −0.067 | Wilson B [0.425,0.669]; V2 [0.362,0.607] | in noise band ✓ |
| Mean cost | $0.1024 | $0.1018 | +$0.0091 (paired, 14 tasks) | [−0.0149, +0.0330] | no |
| Mean wall | 125s | 131s | +5.6s (paired, 15 tasks) | [−43.6s, +54.7s] | no |

- Position-based within-task McNemar (60 paired positions): 24 both-pass, 22
  both-fail, **9 B-only regressions, 5 V2-only improvements** → exact p =
  0.4240. Task-level solved McNemar: 0 B-only, 1 V2-only
  (large-scale-text-editing) → p = 1.0 (secondary reference).
- Cost pairing excluded large-scale-text-editing (arm B has only 3 usable
  costs there; v2 has its own AgentTimeoutError there too). Wall pairing
  included all 15 tasks.
- Cost and wall both NOT significant; pass delta within noise →
  **VERDICT: REJECT** (no measurable cost/latency effect at k=4).

### v2 vs v1 (treated vs untreated) reading

- v1's 0.500 (30/60) vs v2's 0.483 (29/60) — a 0.017 difference between two
  runs on the same 15-task subset, consistent with k=4 noise; confirms v1 was
  statistically indistinguishable from an untreated re-run.
- The v2 treated arm still shows the same **task-adaptive direction** the
  lever-report predicted: large-scale-text-editing 0/4 → 2/4 (thrash-limited
  task helped; mean cost $0.368→$0.151, wall 907s→627s) while precision tasks
  regressed (fix-git 4→2, regex-log 3→1, vulnerable-secret 4→3).
- **Resolution:** the original E-opt1 REJECT is now backed by a valid treated
  measurement — concision guidance, delivered correctly, does not clear the
  pre-registered bar (no cost/latency significance) at haiku-4.5 k=4.

## Notes

- Cost pairing verdict would be identical under the strict 14-task exclusion
  used for both metrics in an earlier revision (+$0.0074 [−0.0074,+0.0221]).
- Per-task direction is mixed at k=4 (fix-git 4/4→1/4, regex-log 3/4→0/4 are
  regressions; large-scale-text-editing 0/4→3/4 and password-recovery 0/4→1/4
  are gains) — consistent with run-to-run variance at k=4, not a treatment
  effect the current sample can resolve.
- Code stays in-tree but the env gate is OFF by default → E-opt1 is inert for
  all non-candidate runs. Reverting the source diff is optional; the gate
  provides the same isolation.

## Artifacts

- `eval/results/e-opt1-probe.jsonl` (probe), `eval/results/e-opt1-arm.jsonl`
  (INVALIDATED v1 full arm, untreated), `eval/results/e-opt1-arm-v2.jsonl`
  (v2 TREATED full arm)
- `eval/experiments/E-opt1/decision.json` (v1 structured decision, invalidated),
  `eval/experiments/E-opt1/decision-v2.json` (v2 structured decision)
- `eval/experiments/E-opt1/verification-provenance-v2.md` (treatment-reach
  evidence for v2)
- `eval/analysis/analyze_eopt1.py`, `eval/analysis/analyze_eopt1_v2.py`,
  `eval/analysis/compare_probe.py`
- Source: `ada/agent/concision-guidance.ts`, `ada/agent/index.ts` (patched),
  `eval/ada-agent/ada_agent.py` (kwargs + explicit `__init__` binding)
