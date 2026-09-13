# Ada Eval Trace-Corpus Lever Report

**Corpus:** 180 trials — `baseline-armA` (reference claude-code agent, 60), `baseline-armB`
(Ada bridge, 60), `e-opt1-arm` (Ada bridge + concision guidance, 60) — 15 Terminal-Bench 2.0
tasks × k=4, all on `claude-haiku-4-5`, CLI 2.1.258.
**Scope:** ANALYSIS ONLY. No API spend, no harbor runs, no harness code changes. Everything
below is mined from the existing job dirs (`eval/jobs/{baseline-armA,baseline-armB,e-opt1-arm}/*/`)
and results JSONLs (`eval/results/*.jsonl`) by `eval/analysis/mine_levers.py`
→ `eval/analysis/lever-data.json` (the machine-readable companion to this report).

---

## 1. Structural context (already measured, restated for framing)

| Bucket | Tasks | Why they matter |
|---|---|---|
| ALL-PASS ceiling (3) | fix-code-vulnerability, git-leak-recovery, vulnerable-secret (4/4 in all arms) | No headroom; excluded from lever space. Any lever that regresses them is auto-killed. |
| ALL-FAIL floor (4) | configure-git-webserver (0/0/0), db-wal-recovery (0/0/0), filter-js-from-html (0/0/0), password-recovery (0/0/1) | Capability floor on haiku-4.5. Floor-lifting levers are higher-risk; treated separately. |
| MIXED (8) — **the lever space** | cancel-async-tasks (1/2/1), fix-git (3/4/1), git-multibranch (3/3/3), large-scale-text-editing (1/0/3), log-summary-date-ranges (1/4/3), openssl-selfsigned-cert (4/3/4), regex-log (2/3/0), sanitize-git-repo (0/2/2) | Run-to-run variance lives here; levers must move these to matter. |

Pass counts above are A/B/E (out of 4). Aggregate: A 27/60 (0.450), B 33/60 (0.550),
E 30/60 (0.500); McNemar A-vs-B p=1.0, B-vs-E p=1.0 — **all pass-rate deltas at k=4 are
within noise (±0.126)**. Wall time is the only significant baseline delta (B−A = −109.2s,
CI [−157.1, −61.3]).

## 2. New measured findings (the mining output)

1. **Failure taxonomy (90 failing trials, per-test modes from ctrf.json):**
   assertion_mismatch 90 (A 32, B 26, E 32), timeout 28 (10/10/8), connection/http-000 12
   (4/4/4 — all configure-git-webserver), missing_file 2 (A password-recovery).
   Assertion mismatches dominate: the agent *does something*, but the artifact doesn't match spec.
2. **Near-miss distance-to-pass:** 44 failing trials pass ≥50% of their tests
   (`near_misses_ge_0.5`). Largest clusters: db-wal-recovery 12/12 trials at 5/7;
   cancel-async-tasks 8/12 failing trials at 5/6; large-scale-text-editing 9/12 at 3–4/5;
   password-recovery 9/12 at 1/2; log-summary-date-ranges 4/12 at 1/2; openssl 1/12 at 5/6.
3. **Deterministic root causes inside near-misses:**
   - db-wal-recovery: all 12 trials fail the *same two* tests (`test_recovered_data_completeness`,
     `test_wal_was_decrypted`) on the *same assertion*: `id=1 value == 150`, got `100`. The agent
     reconstructs missing rows by pattern inference (fruits, +100 increments) instead of
     decrypting the WAL — its final text even says the WAL "had been corrupted/emptied" and
     declares success.
   - cancel-async-tasks: failing test wants `stdout.count("Cleaned up.") == 2`, agent's solution
     emits 0 — a one-line behavioral difference; agent never runs its own script.
   - configure-git-webserver: verifier gets `HTTP 000` (web server never running) in 12/12;
     arm A made **0 tool calls in 4/4 trials** (final message is a markdown *setup guide*, not
     actions); arm B 0.5 tool calls/trial mean; arm E acted (10 tools/trial mean, one trial 30)
     but still never left a live server.
4. **Timeout forensics:** exactly 1 exception trial (B large-scale-text-editing,
   AgentTimeoutError @1200s, 74 tool calls mid-progress, no RUN_FINISHED). Arm A's 4
   large-scale trials ran 425–1001s with the last session message 0.1–5.3s before cutoff —
   the agent was *still working* at cutoff in 3 of 4. Verdict: large-scale-text-editing is
   thrash-limited, not budget-limited — E finished 3/4 passes in ≤852s with 60% fewer tool calls.
5. **Loop/stall detection:** only 5/120 B/E trials have ≥3 duplicate identical tool calls
   (max run 2 consecutive; e.g. B password-recovery trial with 104 tools re-Writing
   `/app/recovered_passwords.txt` 4×). Arm A stalls ≥120s: 3 trials, all large-scale
   (127–172s gaps). Loops/stalls are **rare** — not a primary lever.
6. **Turn economics & arm B's 1.6× wall win — mechanism found:** phase decomposition shows
   A.agent_setup mean **112.3s** vs B.agent_setup **0.4s** (CLI cold-start per trial vs
   long-lived bridge). Agent execution is comparable (A 105.1s vs B 118.3s). The entire
   −109.2s significant wall delta **is the setup phase**. Verifier: A 61.0s vs B 52.4s.
   Tool calls/trial: A 17.5, B 19.7, E 18.9; turns: B 20.7, E 19.9.
7. **Cache-break forensics:** 17 trials with cache-read ratio <0.8; **12 of 17 are regex-log**
   (ratio 0.55–0.70). Mechanism: the agent solves regex-log in **1 tool call** (a single giant
   Write, ~16k output tokens/trial, 12/12 trials) — one huge turn means almost nothing to
   cache-read. This is structural to the task, not a harness defect.
8. **E-opt1 flip mechanisms (per-task, B→E):** large-scale-text-editing 0→3 (out_tok −44%
   29.8k→16.8k, tools −60% 44→17.8, cost $0.368→$0.163), password-recovery 0→1 (but tools
   ballooned to 81.2/trial, cost $0.236→$0.273); **regressions:** fix-git 4→1 (file-content
   hash mismatches — agent under-edits patch files), regex-log 3→0 (regex returns tuples not
   strings / misses 3 dates), log-summary 4→3, cancel-async 2→1. Net −5pp → rejected. The
   guidance is **task-adaptive**: it helps thrash-limited tasks and hurts precision tasks.
9. **Arm-A ALL-FAIL forensics:** configure-git-webserver = explanation-not-action (above);
   db-wal-recovery = pattern-inference-not-decryption (above, 31–42 Bash calls/trial spent
   probing); filter-js-from-html = 1 Write/trial then stops (verifier times out on the
   agent's own test run — solution never exercised); password-recovery = 60–76 tool calls
   of forensic searching, finds a candidate, writes it, still fails `test_password_match`
   (wrong candidate — capability, not effort); sanitize-git-repo (A 0/4, B/E 2/4) = 22 tool
   calls/trial, fails `test_removal_of_secret_information` + `test_correct_replacement` —
   leaves secrets in a config diff (partial-sanitize).

---

## 3. Ranked lever list

**Ranking formula (pre-registered):** `score = (expected gain × confidence) / effort`,
where *expected gain* = expected pass-rate delta on the 15-task suite in percentage points
(pp), plus cost savings converted at 1 pp per 10% suite-wide cost cut; *confidence* ∈ [0,1]
is discounted for the k=4 noise band (±0.126) and counter-evidence; *effort* S=1, M=2, L=3.
All A/B costs assume the existing harness (15 tasks × k=4 ≈ $6–7 per arm at measured
per-trial means; baseline arm B data already exists, so most experiments need only the
candidate arm ≈ $6–7, plus optional B re-runs for drift control).

| # | Lever | Gain (pp) | Conf. | Effort | Score |
|---|---|---|---|---|---|
| 1 | L1 Self-verification-before-finish directive | +8 | 0.50 | S | **4.00** |
| 2 | L2 Task-adaptive concision gating (E-opt1 refined) | +9 | 0.45 | S | **4.05** → ranked below L1 on robustness grounds (see note) |
| 3 | L3 db-wal-recovery source-over-inference guidance | +5 | 0.40 | S | **2.00** |
| 4 | L4 configure-git-webserver act-and-verify-liveness directive | +4 | 0.35 | S | **1.40** |
| 5 | L6 regex-log iterate-don't-one-shot | +2 | 0.20 | S | **0.40** |
| 6 | L5 Search-effort cap for forensic tasks (password-recovery) | +0.3 (cost) | 0.60 | S | **0.18** |
| 7 | L7 Loop/stall breaker | +1 | 0.30 | L | **0.10** |

Note on the L1/L2 tie: L2's raw score (4.05) edges L1 (4.00), but L2's evidence is a single
arm's per-task heterogeneity at k=4 and carries selection-bias risk (gating chosen by looking
at the same outcomes it will be judged on). L1's mechanism (agents never self-test) is
corroborated across 5 tasks and 44 near-miss trials. We rank L1 first on robustness; both
should be run — they are mechanistically independent and composable.

---

### L1 — Self-verification-before-finish directive (highest priority)

- **Mechanism:** In near-miss trials the agent produces a plausible artifact, declares success
  in its final message, and never executes the deliverable against even an ad-hoc check. A
  system-prompt directive ("before finishing, run the script/program you wrote or produced at
  least once; if its observable output can be checked, check it; fix what fails") converts
  near-misses into passes because the distance-to-pass is one self-test away.
- **Measured evidence:** 44 failing trials pass ≥50% of verifier tests
  (`summary.near_misses_ge_0.5`). Concrete instances: cancel-async-tasks — 8/12 failing trials
  at 5/6, failing only on `stdout.count("Cleaned up.") == 2` vs 0 emitted (agent wrote the
  solution in 2 turns, 0 self-runs); db-wal-recovery — final text says "successfully
  completed" while `id=1 value` is 100 vs required 150 in 12/12 trials; log-summary-date-ranges
  4/12 at 1/2; openssl 1/12 at 5/6. Arm A configure-git-webserver final texts are setup
  *guides* — the extreme form of describe-don't-verify.
- **Expected effect:** Converting half of the 5/6-and-4/5 near-miss clusters (cancel-async,
  large-scale, openssl, log-summary) ≈ +2–3 trials on the 32 MIXED trials ≈ **+6–9 pp suite
  pass rate**; stated conservatively as +8 pp.
- **Pre-registered numeric kill criterion:** KILL if MIXED-task pass count (candidate arm,
  k=4) is < B's MIXED count + 2 (i.e. < +2 trials, below the +4 pp bar), OR if any ALL-PASS
  task (fix-code-vulnerability, git-leak-recovery, vulnerable-secret) drops below 4/4 in ≥2
  trials, OR if mean cost rises > 20% vs arm B ($0.1024).
- **Estimated A/B cost:** candidate arm only ≈ **$6–7** (15 × 4 × ~$0.10 mean; B baseline
  reusable). Optional B re-run for drift: +$6.
- **Effort:** **S** — same env-gated `systemPromptAppend` seam as E-opt1
  (`ada/agent/concision-guidance.ts` pattern), default OFF.

### L2 — Task-adaptive concision gating (E-opt1 refined)

- **Mechanism:** E-opt1's global concision guidance was net-negative (−5 pp) but flipped
  large-scale-text-editing 0/4→3/4 by cutting thrash (out_tok −44%, tool calls −60%). The
  regression tasks (fix-git 4→1, regex-log 3→0) are precision tasks where "targeted reads /
  terse" caused under-editing. Gate the SAME guidance on only for high-output/thrash-prone
  tasks (heuristic: expected output size or task family), off elsewhere.
- **Measured evidence:** large-scale-text-editing: B 0/4 (incl. 1 AgentTimeoutError @1200s
  with 74 tools mid-progress; A trials still working 0.1–5.3s before cutoff) → E 3/4 with
  16.8k out_tok and 17.8 tools/trial, cost $0.368→$0.163. Regressions: fix-git 4→1
  (2/2 tests fail on file-hash mismatches = under-applied patches), regex-log 3→0 (regex
  returns tuples, misses 3 dates), log-summary 4→3, cancel-async 2→1. `summary.eopt1_flips`.
- **Expected effect:** Capture large-scale (+3 trials) and password-recovery (+1) without the
  −7 trials of regressions ≈ **+9 pp on MIXED** if gating is clean.
- **Pre-registered numeric kill criterion:** KILL if large-scale-text-editing < 2/4 on the
  gated arm, OR if fix-git + regex-log combined pass count drops ≥ 2 vs arm B (7 → ≤5), OR
  if suite pass rate < arm B's 0.550 − 0.126 (noise band). Also kill if the gating heuristic
  requires per-task hand-tuning of >3 tasks (that is overfitting, not a lever).
- **Estimated A/B cost:** ≈ **$6–7** (candidate arm; B and E arms already exist for comparison).
- **Effort:** **S** — env-gate exists; add a task-conditional (e.g. gate on prompt/output-size
  heuristic, not task-name allowlist, to avoid selection bias).
- **Caveat that lowers confidence:** the +3 flip is measured at k=4 where the noise band is
  ±0.126; and gating chosen by inspecting E's own outcomes is selection-biased. The heuristic
  must be definable ex ante (task property, not task name).

### L3 — db-wal-recovery: extract-from-source-over-inference guidance

- **Mechanism:** All 12 db-wal-recovery trials fail the same two tests on the same assertion
  (`id=1 value 150`, got 100): the agent treats the encrypted WAL as unrecoverable and
  *infers* missing rows from naming/numeric patterns. A directive ("in recovery tasks,
  treat unexplained/corrupted data as recoverable evidence — look for the encryption
  mechanism (keys, headers, XOR patterns) and extract the true values; never fabricate
  records by pattern extrapolation") aims at the exact failure.
- **Measured evidence:** 12/12 trials at 5/7 tests; both failures are the id=1 value
  assertion; arm A spent 31–42 Bash calls probing but concluded the WAL was "corrupted/
  emptied"; final texts declare success. `summary.near_misses` (db-wal-recovery entries),
  `armA_allfail_forensics`.
- **Expected effect:** This is a floor task (0/12 across arms) — if the directive gets the
  agent to attempt decryption, 2–3 of 12 could convert ≈ **+5 pp suite** (3/60). Floor-lifting
  is the least certain category: E acted on configure-git-webserver and still failed.
- **Pre-registered numeric kill criterion:** KILL if db-wal-recovery pass count is 0/4 on the
  candidate arm, OR if the two target tests still fail on the id=1 value assertion in ≥3/4
  trials (mechanism not engaged).
- **Estimated A/B cost:** targeted: 1 task × k=4 ≈ **$0.60–0.90** (db-wal mean cost $0.15–0.21/
  trial) + guard against ceiling regressions on 3 ALL-PASS tasks × k=4 ≈ **$2.50** → ~$3.50.
- **Effort:** **S** (prompt-only, same seam).

### L4 — configure-git-webserver: act-and-leave-services-running directive

- **Mechanism:** Arm A never acts (0 tool calls in 4/4 trials — it writes a setup guide);
  arm E acts but the verifier still gets HTTP 000 — services aren't left running/installed
  as daemons. A directive ("execute every setup step yourself; start long-running services
  in the background (nohup/systemd) and verify liveness with a curl before finishing")
  targets both the action gap and the liveness gap.
- **Measured evidence:** HTTP 000 in 12/12 trials (`failure_taxonomy` configure-git-webserver
  = connection/http-000 ×4 per arm); arm A 0 tool calls, final text = markdown guide; arm B
  0.5 tools/trial; arm E 10 tools/trial mean (one trial 30, incl. repeated `rm -rf` cleanup)
  yet still 0/4. Verifier also shows `git clone git@localhost:/git/server` failing.
- **Expected effect:** floor task; even with action + liveness, ssh-based git service setup
  may exceed haiku capability. Expected 1–2 of 12 convert ≈ **+4 pp suite**, low certainty.
- **Pre-registered numeric kill criterion:** KILL if configure-git-webserver is 0/4 AND mean
  tool calls on the candidate arm < 5 (mechanism not engaged), or 0/4 with tools ≥5 across
  two probe repeats (engaged but capability-blocked — report as floor confirmation).
- **Estimated A/B cost:** cheapest lever: 1 task × k=4 ≈ **$0.04–0.25** (mean cost $0.01–0.06/
  trial) + ALL-PASS guard ≈ $2.50 → ~$2.75.
- **Effort:** **S**.

### L6 — regex-log: iterate-don't-one-shot (rank 5; counter-evidence caps confidence)

- **Mechanism:** The agent writes one giant regex in a single Write (1 tool call in 12/12
  trials, ~16k output tokens) without testing it against the log; 12 of the suite's 17
  cache-break trials (<0.8 ratio) are this task. Iterate-then-refine would both raise pass
  odds and cache efficiency.
- **Measured evidence:** 1 tool call/trial in 12/12; out_tok mean 15.7k–16.4k; cache ratio
  0.55–0.70 (`cache_break_lt_0.8`); A 2/4, B 3/4, E 0/4.
- **Expected effect:** +2 pp if 1–2 trials convert. **Counter-evidence:** E-opt1's guidance
  (which includes targeted-verification language) *regressed* regex-log 3→0 — the failures
  were regex correctness (tuples vs strings, missed dates), suggesting capability, not
  process. Confidence 0.20.
- **Pre-registered numeric kill criterion:** KILL if regex-log < 2/4 on the candidate arm.
- **Estimated A/B cost:** 1 task × k=4 ≈ **$0.43**.
- **Effort:** **S**.

### L5 — Search-effort cap for forensic tasks (rank 6; cost lever, pass-neutral)

- **Mechanism:** Unbounded exploratory search inflates cost without pass gain: password-recovery
  tool calls grew A 34 → B 76.5 → E 81.2 per trial with cost $0.143 → $0.236 → $0.273 and pass
  0/0/1 — the B trial with 104 tools included 4 re-Writes of the same output file (thrash).
  A soft cap/directive ("after N failed search strategies, commit to the best candidate")
  cuts cost; pass effect expected ~neutral (the task fails on wrong candidate, not effort).
- **Measured evidence:** per-task economics above (`trials` records; `loop_trials_BE`
  password-recovery entry: 104 tools, Write×4). db-wal-recovery shows the same shape
  (31–42 Bash calls/trial).
- **Expected effect:** ~25% cost cut on 2 bloat tasks ≈ 3% suite-wide ≈ **0.3 pp-equivalent**;
  possibly +1 trial if early commitment stops thrash (not counted).
- **Pre-registered numeric kill criterion:** KILL if password-recovery + db-wal-recovery mean
  cost is not ≥15% below arm B ($0.236 + $0.185 → ≤ $0.179 combined mean), OR if pass count
  on those tasks drops below arm B's (0 and 0).
- **Estimated A/B cost:** 2 tasks × k=4 ≈ **$1.70**.
- **Effort:** **S**.

### L7 — Loop/stall breaker (ranked last; likely infeasible at harness layer)

- **Mechanism:** Detect repeated identical tool calls / long stalls and inject a nudge or
  budget warning. **Prevalence is too low to matter:** 5/120 B/E trials with ≥3 duplicate
  calls (max consecutive run 2), 3/60 arm-A stalls ≥120s (all large-scale, 127–172s).
- **Measured evidence:** `loop_trials_BE` (5 entries), `armA_stalls_ge_120s` (3 entries).
- **Expected effect:** ≤ +1 pp. Additionally, E2-literal established there is **no mid-loop
  seam** without forking `@astropods/adapter-claude-agent-sdk` → effort L.
- **Pre-registered numeric kill criterion:** KILL if duplicate-call prevalence on the
  candidate arm is unchanged (≥4/60 trials) — i.e., the detector fires but changes nothing.
- **Estimated A/B cost:** full arm ≈ **$6–7** (only worth bundling with another lever's run).
- **Effort:** **L** (SDK fork) — do not run standalone.

---

## 4. Findings that are NOT levers (recorded to prevent re-litigation)

- **Arm B's 1.6× wall win is fully explained:** agent_setup 112.3s (A) vs 0.4s (B) — CLI
  cold start vs long-lived bridge. Already realized; nothing further to optimize at the
  harness layer. Keep the bridge alive across trials (current design) and document this
  as the harness's headline advantage.
- **Cache stabilization (E3):** cache-read ratio is 0.917/0.919/0.927 by arm — near ceiling.
  The only sub-0.8 cluster (regex-log) is structural to a 1-turn task. Rejected pre-run;
  stays rejected.
- **Registry cap (E1) / build-cache prewarm (E5):** N/A and out of scope as previously
  established (fresh container+bridge per trial; image-level change).
- **filter-js-from-html:** 1 Write then stop; the verifier times out running the agent's own
  test suite. The agent never exercises its solution — L1's self-verification directive is
  the only harness-layer handle; the task otherwise looks like a floor task on haiku.

## 5. Evidence traceability

All numbers above are reproducible from:
- `eval/analysis/lever-data.json` — keys: `summary.pass_matrix` (A/B/E per-task pass + mean
  cost), `summary.near_misses*` (44 ≥0.5 clusters with failed-test names/modes),
  `summary.failure_taxonomy` + `failure_mode_totals_by_arm`, `summary.phase_means_s`
  (agent_setup 112.3 vs 0.4), `summary.cache_break_lt_0.8` + `cache_ratio_by_arm`,
  `summary.eopt1_flips` + `eopt1_flip_fail_detail`, `summary.loop_trials_BE`,
  `summary.armA_stalls_ge_120s`, `summary.longest_agent_exec` (timeout forensics),
  `summary.armA_allfail_forensics` (tool histograms + final texts), `trials` (per-trial
  records incl. `sess.tool_hist` with `source: streamjson` fallback).
- Raw corpus: `eval/jobs/<arm>/<trial>/verifier/ctrf.json` (per-test status/trace),
  `.../result.json` (phase timings, tokens, cost), `.../agent/ada-events.jsonl` (B/E tool
  streams), `.../agent/claude-code.txt` + `agent/sessions/projects/-app/*.jsonl` (A),
  `eval/results/{baseline-armA,baseline-armB,e-opt1-arm}.jsonl`.
- Generator: `eval/analysis/mine_levers.py` (rerunnable, analysis-only).

## 6. Caveats (read before acting on any lever)

1. **k=4 noise band:** every pass-rate delta at k=4 carries a ±0.126 band; the E-opt1
   rejection showed a plausible-looking lever can be indistinguishable from noise. All
   confidence values above are discounted accordingly; all kill criteria are numeric and
   pre-registered *before* any candidate run.
2. **Lever space = the 8 MIXED tasks.** The 3 ALL-PASS tasks are regression guards only;
   the 4 ALL-FAIL tasks are floor-lifting (L3, L4) with explicitly lower confidence —
   E's configure-git-webserver result (acted, still failed) is the cautionary precedent.
3. **Selection bias risk on L2:** gating concision by looking at E's own per-task outcomes
   is overfitting unless the gate is defined by an ex-ante task property (output size /
   thrash heuristic), not task name.
4. **Single model, single CLI:** all findings are on claude-haiku-4-5 + CLI 2.1.258.
   Prompt-directive levers (L1–L4, L6) may transfer poorly to stronger models; the wall-time
   mechanism (setup phase) is model-independent.
5. **Cost estimates** use measured per-task means from the results JSONLs; actual spend
   varies ±19% CV per trial (variance probe). Total for all 7 levers if run ≈ $25–30 —
   well within the remaining ~$133 budget.
6. **Composability:** L1 (self-verification) and L2 (adaptive concision) are mechanistically
   independent and can be A/B'd in one candidate arm against the existing B arm, halving
   spend — provided each has its own kill criterion evaluated on its target task set.

_Generated by trace mining (`eval/analysis/mine_levers.py`); analysis-only, no API spend,
no harbor runs, no harness code changes._
