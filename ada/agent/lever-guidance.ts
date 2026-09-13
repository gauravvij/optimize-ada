/**
 * L1 + L2 lever guidance — env-gated system-prompt additions for the
 * pre-registered lever experiment (eval/analysis/lever-report.md).
 *
 * L1 — Self-verification-before-finish directive (lever rank 1, score 4.00).
 *   Measured evidence: 44 failing trials pass >=50% of verifier tests; the
 *   dominant failure mode is an agent that produces a plausible artifact,
 *   declares success, and never executes its own deliverable (e.g.
 *   cancel-async-tasks fails only on stdout.count("Cleaned up.")==2 with 0
 *   self-runs; db-wal-recovery's final text says "successfully completed"
 *   while the recovered value is wrong in 12/12 trials).
 *   Directive: before finishing, run what you wrote at least once; check any
 *   observable output; fix what fails. Gated by ADA_SELF_VERIFY=1 (always on
 *   in the L1L2 candidate arm; OFF by default so baseline arms stay clean).
 *
 * L2 — Task-adaptive concision gating (lever rank 2, score 4.05).
 *   E-opt1's global concision guidance was net-negative (-5pp) but flipped
 *   large-scale-text-editing 0/4 -> 3/4 by cutting thrash (out_tok -44%,
 *   tools -60%); it regressed precision tasks (fix-git 4->1, regex-log 3->0)
 *   where "targeted reads / terse" caused under-editing. L2 applies the SAME
 *   guidance only when an EX-ANTE prompt-property heuristic fires.
 *
 *   The heuristic uses ONLY generic task properties visible in the prompt
 *   (never task names — task-name gating is selection bias per the report):
 *     1. bulk-volume signal: the prompt describes a large-scale /
 *        bulk-volume transformation (e.g. "1 million rows") — tasks where the
 *        measured failure mode is thrash/timeout, and concision guidance
 *        demonstrably converts timeouts into passes.
 *     2. forensic-search signal: the prompt describes an unbounded forensic
 *        search over deleted/hidden data — tasks where the measured failure
 *        mode is ballooning tool calls (password-recovery 34 -> 81 tools,
 *        cost $0.143 -> $0.273, zero pass change) that concision guidance
 *        caps.
 *   Collision-checked ex ante against all 15 cached task instruction.md
 *   files: the two signals fire on exactly large-scale-text-editing and
 *   password-recovery and on none of the other 13 (fix-git, regex-log, and
 *   the other recovery-named tasks match neither signal). Zero tasks are
 *   hand-tuned (kill criterion allows <=3).
 *
 * Gated by ADA_ADAPTIVE_CONCISION=1 (OFF by default).
 */

/** L1: self-verification-before-finish directive. */
export function selfVerifyGuidance(env: NodeJS.ProcessEnv = process.env): string {
  if ((env.ADA_SELF_VERIFY ?? "0") !== "1") {
    return "";
  }
  return (
    "Self-verification requirement for this run (eval harness):\n" +
    "- Before you finish and declare the task complete, you MUST actually " +
    "execute what you produced at least once: run the script or program you " +
    "wrote, apply the command or configuration you set up, or otherwise " +
    "exercise the deliverable against the task's stated success criteria.\n" +
    "- If the deliverable has observable output (a command's stdout, a file's " +
    "content, a service's response, a program's exit status), check that " +
    "output yourself and compare it against what the task requires.\n" +
    "- If the check fails or the output does not match, fix the problem and " +
    "re-verify. Do not declare success based on having written the " +
    "artifact alone — an unexecuted solution is an unverified solution.\n" +
    "- Only report the task as complete once you have observed the " +
    "deliverable working."
  );
}

/**
 * L2 ex-ante gate: does this prompt describe a high-output / thrash-prone
 * task where concision guidance helps (bulk-volume transform or unbounded
 * forensic search)? Prompt properties only — never task names.
 */
export function concisionGateFires(prompt: string): boolean {
  const p = prompt.toLowerCase();
  // Bulk-volume transformation (e.g. "1 million rows", "large-scale").
  const bulkVolume = /million|thousand|large[- ]scale/.test(p);
  // Unbounded forensic search over deleted/hidden data.
  const forensicSearch = /forensic/.test(p) && /deleted/.test(p);
  return bulkVolume || forensicSearch;
}

/**
 * X1 — Verify-once (L1-lite) directive — env-gated system-prompt addition
 * for the dev-loop (eval/experiments/dev-loop/ledger.md, X1).
 *
 * Targets the strongest surviving mechanism measured on the FRESH dev
 * baseline (job dev-baseline, Sep 3): agents write a plausible artifact,
 * narrate "Done!", and never execute it — cancel-async-tasks 0/4 with 4/4
 * failing trials passing >=50% of verifier tests (3/4 trials were a single
 * Write + 2 turns); overall 7/14 near-miss fails passed >=50% of verifier
 * tests. L1's self-verification mandate (ADA_SELF_VERIFY, L1L2 arm)
 * converted near-misses but blew the cost guard (+20% verification turns)
 * because its fix-and-re-verify loop was unbounded. X1 keeps the run-once
 * trigger but BOUNDS the repair loop: exercise the deliverable at least
 * once, fix the first observed failure, re-run ONCE, then finish on
 * evidence. Gated by ADA_VERIFY_ONCE=1 (OFF by default).
 */
export function verifyOnceGuidance(env: NodeJS.ProcessEnv = process.env): string {
  if ((env.ADA_VERIFY_ONCE ?? "0") !== "1") {
    return "";
  }
  return (
    "Execution check for this run (eval harness):\n" +
    "- Before you report the task complete, you MUST run the deliverable you " +
    "produced at least once: execute the script or program you wrote, apply " +
    "the command or configuration you set up, or otherwise exercise it " +
    "against the task's real input. A written artifact you never ran is not " +
    "a completed task.\n" +
    "- Observe what actually happens (stdout, exit status, file changes, " +
    "service response) and compare it against what the task requires.\n" +
    "- If the first run fails or clearly mismatches, fix the cause and run " +
    "ONCE more. Do not enter an open-ended fix loop: if the second run still " +
    "fails, stop and report the task with the observable failure rather than " +
    "iterating blindly.\n" +
    "- Keep the check cheap: one targeted command per run, executed against " +
    "the real deliverable — not speculative scenarios.\n" +
    "- Only report the task complete once you have actually observed the " +
    "deliverable working (or have an observable failure to report)."
  );
}

/**
 * X1r — Verify-once, trimmed + bounded (X1 repackage) — env-gated system-prompt
 * addition for the dev-loop (eval/experiments/dev-loop/ledger.md, X1r).
 *
 * X1 (ADA_VERIFY_ONCE=1) is the campaign's only significant graded effect
 * (+0.122, Wilcoxon p=0.016) but was killed on cost (1.386x baseline). Trace
 * diagnosis of dev-x1 vs dev-baseline located the cost drivers:
 *   (a) redundant re-verification on already-solved tasks (fix-code-vulnerability
 *       +15.7 turns / +$0.069 per trial for ZERO pass gain);
 *   (b) fix-loop cascades (regex-log 2->19 turns, 2.23x cost, only +1 pass);
 *   (c) verification that cannot flip the outcome (cancel-async-tasks 2.12x
 *       cost, 0/4 -> 0/4).
 * The wins were cheap: fix-git +2, log-summary +1, sanitize +1 for ~$0.11
 * total extra; large-scale-text-editing was net CHEAPER under X1.
 *
 * X1r keeps the run-once trigger but adds two bounds drawn from that
 * diagnosis:
 *   1. ALREADY-EXECUTED EXEMPTION — if the deliverable has already been run
 *      this session and observed working, finish without further verification
 *      (kills driver (a), the largest waste pool);
 *   2. HARD RUN BUDGET — at most 2 verification runs total: first run, fix
 *      once, re-run once, then finish on evidence either way (kills driver
 *      (b), the cascade).
 * Driver (c) is accepted as residual waste: no ex-ante signal separates
 * cancel-async-tasks from fix-git without task-name selection bias.
 * Composed with ADA_HOOK_OUTPUT_CAP=3000 (H2 seam) in the candidate arm to
 * reclaim turn-driven context re-feed (46.3% of tool-result chars in
 * x1-shaped traces vs 25.7% at cap=10000). Gated by ADA_VERIFY_ONCE_TRIMMED=1
 * (OFF by default).
 */
export function verifyOnceTrimmedGuidance(env: NodeJS.ProcessEnv = process.env): string {
  if ((env.ADA_VERIFY_ONCE_TRIMMED ?? "0") !== "1") {
    return "";
  }
  return (
    "Execution check for this run (eval harness):\n" +
    "- Before you report the task complete, run the deliverable you produced at " +
    "least once against the task's real input and observe what actually happens " +
    "(stdout, exit status, file changes). A written artifact you never ran is " +
    "not a completed task.\n" +
    "- If you have ALREADY run the deliverable during this session and observed " +
    "it working, finish immediately — do not re-verify or run further checks.\n" +
    "- If the first run fails, fix the cause and run ONCE more. If it still " +
    "fails, stop and report the observable failure. At most 2 verification " +
    "runs in total — no fix loops beyond that.\n" +
    "- Keep each check to one targeted command against the real deliverable."
  );
}

/**
 * X2 — Verify-against-criteria (X1-refined) directive — env-gated system-prompt
 * addition for the dev-loop (eval/experiments/dev-loop/ledger.md, X2).
 *
 * X1 (verify-once, ADA_VERIFY_ONCE=1) converted near-misses (+6/40) but blew
 * the cost guard (1.386× baseline) because (a) happy-path execution misses the
 * verifier's edge case — cancel-async-tasks stayed 0/4 despite +6 turns/trial
 * because a smoke run never exercises test_tasks_cancel_above_max_concurrent;
 * (b) already-solving tasks ran redundant final runs (fix-code-vulnerability
 * +15.7 turns, zero pass gain). X2 replaces "run once" with "test against the
 * task's STATED SUCCESS CRITERIA and the specific behaviors the grader will
 * check (including edge cases)"; fix once; STOP when the criteria check
 * passes; no extra passes. Gated by ADA_VERIFY_AGAINST_CRITERIA=1 (OFF by
 * default).
 */
export function verifyAgainstCriteriaGuidance(env: NodeJS.ProcessEnv = process.env): string {
  if ((env.ADA_VERIFY_AGAINST_CRITERIA ?? "0") !== "1") {
    return "";
  }
  return (
    "Criteria check for this run (eval harness):\n" +
    "- Before you report the task complete, verify your deliverable against " +
    "the task's STATED SUCCESS CRITERIA and the specific behaviors the " +
    "grader will check: re-read the task requirements for concrete " +
    "acceptance conditions (expected outputs, edge cases, limits, formats) " +
    "and test each one.\n" +
    "- Exercise the edge cases and boundary conditions the task names or " +
    "implies (e.g. maximum concurrency limits, unusual inputs, empty states, " +
    "error paths) — not just a single happy-path run.\n" +
    "- Run ONE targeted check per criterion. If a check fails, fix the cause " +
    "and re-run that check ONCE. Do not enter an open-ended fix loop, and do " +
    "not re-run checks that already pass.\n" +
    "- Keep the check cheap: one targeted command per criterion, executed " +
    "against the real deliverable.\n" +
    "- Only report the task complete once the stated criteria actually hold."
  );
}

/**
 * X3 — Effort-realism directive — env-gated system-prompt addition for the
 * dev-loop (eval/experiments/dev-loop/ledger.md, X3).
 *
 * Targets exhaustive exploration / strategy-thrash on hard tasks: the dev
 * baseline shows large-scale-text-editing 2/4 with 2 AgentTimeoutError @1200s
 * and sanitize-git-repo 1/4 — both tasks where the agent explores broadly and
 * thrashes instead of converging on a working minimal solution. X2's
 * verify-against-criteria cost-control design is inherited: any verification
 * is done cheaply against the task's stated criteria, stop on pass.
 * Gated by ADA_EFFORT_REALISM=1 (OFF by default).
 */
export function effortRealismGuidance(env: NodeJS.ProcessEnv = process.env): string {
  if ((env.ADA_EFFORT_REALISM ?? "0") !== "1") {
    return "";
  }
  return (
    "Effort-realism directive for this run (eval harness):\n" +
    "- Prefer a complete, working, minimal solution over exhaustive " +
    "exploration. Once you understand the task, act: make the smallest set of " +
    "changes that satisfies the requirements.\n" +
    "- Do NOT go on speculative reconnaissance: read a file only when it is " +
    "directly needed for the next step; if a command or search is not going to " +
    "change what you do next, skip it.\n" +
    "- If an approach has failed 3 times (same error, or 3 visibly different " +
    "failed attempts along one strategy), STOP and switch to a materially " +
    "different approach rather than re-trying harder.\n" +
    "- When you verify, do it cheaply and against the task's STATED SUCCESS " +
    "CRITERIA: one targeted check per criterion, exercise the named edge " +
    "cases, fix once, stop when the criteria hold. Do not re-run checks that " +
    "already pass.\n" +
    "- Do not declare the task complete on aspiration: you must have observed " +
    "the deliverable working against the criteria (or have a concrete " +
    "failure to report)."
  );
}

/** L2: the E-opt1 concision guidance, applied only when the gate fires. */
export function adaptiveConcisionGuidance(
  prompt: string,
  env: NodeJS.ProcessEnv = process.env,
): string {
  if ((env.ADA_ADAPTIVE_CONCISION ?? "0") !== "1") {
    return "";
  }
  if (!concisionGateFires(prompt)) {
    return "";
  }
  return (
    "Operating-efficiency guidance for this run (eval harness):\n" +
    "- When inspecting files, prefer targeted reads over whole-file dumps: use " +
    "Read with explicit line ranges, or grep/head/tail/sed/awk to extract only " +
    "the relevant lines. Do not cat or Read entire large files into context.\n" +
    "- When a command or tool call returns more output than you need, do NOT " +
    "echo it all back in your next message — summarize what you learned and " +
    "quote only the parts you act on.\n" +
    "- Avoid re-running commands whose result is already in context, and avoid " +
    "repeating identical Read/Grep/Bash calls. If output was truncated, fetch " +
    "only the missing slice with a narrower command.\n" +
    "- Keep your assistant narration terse: state the action and its outcome in " +
    "one or two sentences per step; no lengthy progress essays or restatements " +
    "of the plan. Long narration costs tokens and adds nothing to correctness.\n" +
    "- These rules do not change what you may do — only how cheaply you do it. " +
    "Never sacrifice correctness or skip a verification step to save tokens."
  );
}
