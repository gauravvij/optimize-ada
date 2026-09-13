# L1 + L2 combined candidate arm — REJECTED (pre-registered)

Combined test of the top-two levers from `eval/analysis/lever-report.md`
against the arm-B baseline (`eval/results/baseline-armB.jsonl`), on
**claude-haiku-4-5**, 15-task subset, k=4 (60 trials), job `l1l2-arm-v2`.

**VERDICT: REJECT** — 3 of 7 pre-registered kill criteria triggered
(MIXED pass count 19 < 23; fix-git+regex-log 4 ≤ 5; mean cost $0.1248 > $0.1229).
Machine-readable verdict: `decision.json`.

---

## 1. Treatment implemented (env-gated systemPromptAppend seam)

Both levers ship through the same env-gated `systemPromptAppend` seam used by
E-opt1 (`eval/ada-runtime/ada/agent/index.ts`), with a new module
`eval/ada-runtime/ada/agent/lever-guidance.ts` (md5 `ccadffd9`, synced to
`/root/optimize_ada/ada/agent/lever-guidance.ts` with parity):

- **L1 — self-verification-before-finish directive (always on in the arm).**
  `selfVerifyGuidance(env)` returns the *"Self-verification requirement for
  this run (eval harness)"* block when `ADA_SELF_VERIFY=1`: run what you
  produced at least once, check observable output, fix and re-verify, never
  declare success from the artifact alone. Mechanism targets the dominant
  failure mode mined in the lever report (44/120 failing trials pass ≥50% of
  verifier tests but never self-test).
- **L2 — task-adaptive concision gating.** `adaptiveConcisionGuidance(prompt,
  env)` returns the E-opt1 "Operating-efficiency guidance" block only when
  `ADA_ADAPTIVE_CONCISION=1` **AND** the ex-ante heuristic
  `concisionGateFires(prompt)` fires. The gate is a **generic prompt-property
  heuristic, NOT a task-name allowlist**:
  - bulk-volume signal: `/million|thousand|large[- ]scale/i`
  - forensic-search signal: `/forensic/i` AND `/deleted/i`
  - gate = bulk-volume OR forensic-search (the forensic signal itself is the
    AND of `/forensic/` and `/deleted/`) → fires on exactly
    **large-scale-text-editing** and **password-recovery** among all 15 cached
    `instruction.md` prompts (verified by unit test; 0 hand-tuned tasks, well
    under the >3 hand-tuned kill bar).

Adapter kwargs (`self_verify`, `adaptive_concision`, `lever_debug` + existing
`concision_guidance`) are bound in an explicit `AdaBridgeAgent.__init__`
(`eval/ada-agent/ada_agent.py`) and mapped to `ADA_*` env vars in
`_bridge_env()`. A prior run (job `l1l2-arm`, parked at
`l1l2-arm-untreated-invalid`) was **untreated** because the base classes
swallowed `--ak` kwargs; the `__init__` fix + in-container probe (job
`l1l2-probe`) proved the full kwargs → env → gate → system-prompt path.

## 2. Smoke evidence (directives reach the system prompt)

- Unit test `eval/experiments/L1L2/smoke_gate_test.mjs`: 11/11 checks, exit 0 —
  heuristic fires on exactly {large-scale-text-editing, password-recovery};
  composed append empty with both gates off; L1-only on plain prompts; L1+L2 on
  bulk prompts.
- Bridge smoke `eval/experiments/L1L2/smoke_bridge_test.sh`: bulk prompt →
  3-part append (github 477 + L1 821 + L2 1018 chars); plain prompt → 2-part
  (github + L1).
- **In-container (full v2 run):** 60/60 trial `ada-bridge.log`s contain
  `[lever-debug]` and `Self-verification requirement`; `Operating-efficiency
  guidance` present in 4/4 large-scale-text-editing and 4/4 password-recovery
  logs, 0/4 in all other 13 tasks. Treatment reach is verified, including the
  adaptive gate.

## 3. Run parameters

```
harbor run --dataset terminal-bench@2.0 --agent eval.ada-agent.ada_agent:AdaBridgeAgent \
  --model anthropic/claude-haiku-4-5 -k 4 -n 2 --jobs-dir eval/jobs --job-name l1l2-arm-v2 \
  --mounts '[{"type":"bind","source":"eval/ada-runtime","target":"/ada-runtime"}]' \
  --ak self_verify=1 --ak adaptive_concision=1 --ak lever_debug=1 \
  -i <15 task names> --yes
```

60/60 trials, 0 exceptions, wall 1h33m43s, API cost **$7.49** (total),
mean **$0.1248**/trial. Results: `eval/results/l1l2-arm.jsonl`
(overwrote the invalid untreated file; schema keys identical to
`baseline-armB.jsonl`).

## 4. Results vs arm B (per-task pass/4)

| Task | B | L1L2 | Δ |
|---|---|---|---|
| cancel-async-tasks | 2 | 0 | −2 |
| configure-git-webserver | 0 | 1 | +1 |
| db-wal-recovery | 0 | 0 | 0 |
| filter-js-from-html | 0 | 0 | 0 |
| fix-code-vulnerability | 4 | 4 | 0 |
| fix-git | 4 | 2 | −2 |
| git-leak-recovery | 4 | 4 | 0 |
| git-multibranch | 3 | 3 | 0 |
| large-scale-text-editing | 0 | 2 | +2 |
| log-summary-date-ranges | 4 | 4 | 0 |
| openssl-selfsigned-cert | 3 | 4 | +1 |
| password-recovery | 0 | 0 | 0 |
| regex-log | 3 | 2 | −1 |
| sanitize-git-repo | 2 | 2 | 0 |
| vulnerable-secret | 4 | 4 | 0 |
| **Suite** | **33/60 (0.550)** | **32/60 (0.533)** | **−0.017** |
| **MIXED (8 tasks)** | **21/32** | **19/32** | **−2** |

### Paired statistics

- McNemar exact (position-paired, 60 pairs): 7 B-only vs 6 L1L2-only
  discordants, **p = 1.0000** — pass-rate change is pure noise at k=4.
- Wilson 95% CI: B [0.425, 0.669], L1L2 [0.409, 0.654] — overlapping.
- Cost (59 paired trials, arm-B large-scale-text-editing timeout trial lacks
  usage): mean delta **+$0.0211**, 95% CI [−0.0003, +0.0426] — not
  significant, but direction is up (V uses more tokens/turns: in 32.8M vs
  26.2M, out 576k vs 472k, turns 23.6 vs 20.3; L1 self-verification adds
  verification turns, and password-recovery under L2 gate ran longer).
  Turn means use different denominators: B's 20.3 = sum of turns over the 59
  non-null trials ÷ 60 (one arm-B timeout trial has null num_turns; the
  non-null-only mean is 20.678, n=59), V's 23.6 is over all 60 trials.

## 5. Pre-registered kill criteria — verdicts

Source: `eval/analysis/lever-report.md` section 3. Bar per criterion; all
measured on the v2 arm.

| # | Criterion | Bar | B | V | Kill? |
|---|---|---|---|---|---|
| L1.1 | MIXED-task pass count (8 tasks × 4) | ≥ 23 | 21 | **19** | **KILL** |
| L1.2 | ALL-PASS guards (fix-code-vulnerability, git-leak-recovery, vulnerable-secret) | no task < 4/4 in ≥ 2 trials | 4/4 each | 4/4 each | pass |
| L1.3 | Mean cost | ≤ $0.1229 | $0.1042 | **$0.1248** | **KILL** |
| L2.1 | large-scale-text-editing | ≥ 2/4 | 0 | 2 | pass (at bar) |
| L2.2 | fix-git + regex-log combined | ≥ 6 | 7 | **4** | **KILL** |
| L2.3 | Suite pass rate | ≥ 0.424 | 0.550 | 0.533 | pass |
| L2.4 | Heuristic hand-tuned tasks | ≤ 3 | — | 0 | pass |

**REJECT.** 3/7 criteria killed. The only clean L2-positive signal —
large-scale-text-editing 0/4 → 2/4 — was offset by regressions on precision
tasks (fix-git 4→2, regex-log 3→2, cancel-async-tasks 2→0), the same
regression pattern seen in E-opt1. The always-on L1 directive did not convert
the near-miss cluster at haiku-4.5 and added cost (turns 20.3→23.6, mean cost
+21%). Suite delta is inside the k=4 noise band (±0.126).

## 6. Caveats

- k=4 noise band ±0.126: a −2 MIXED delta is not distinguishable from noise;
  the kill is driven by the pre-registered bar, not by significance.
- E-opt1's earlier REJECT verdict is **suspect**: it ran through the same
  kwargs-swallowing defect (untreated). This does not change the L1L2 verdict
  (which is fully treated and self-contained), but E-opt1 remains unproven.
- No decomposition run was performed — attribution between L1 and L2 is not
  possible from this bundle, and with 3 kills the bundle is rejected as
  configured.

## 7. Files

- `eval/experiments/L1L2/decision.json` — machine-readable verdict
- `eval/experiments/L1L2/smoke_gate_test.mjs` — unit gating test
- `eval/experiments/L1L2/smoke_bridge_test.sh` — bridge smoke test
- `eval/results/l1l2-arm.jsonl` — 60 treated-trial records (arm `l1l2`)
- `eval/jobs/l1l2-arm-v2/` — full job (60 trial dirs, result.json)
- `eval/jobs/l1l2-probe/` — 4-trial treatment-reach probe
- `eval/jobs/l1l2-arm-untreated-invalid/`, `eval/jobs/l1l2-arm-wrong-aborted/`
  — superseded invalid runs (kept for audit)
- `eval/ada-runtime/ada/agent/lever-guidance.ts`, `index.ts`,
  `eval/ada-agent/ada_agent.py` — the implemented seam + adapter
