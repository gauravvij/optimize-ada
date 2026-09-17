/**
 * General coding-task guidance appended to Claude Code's built-in preset.
 *
 * Kept in one isolated module so its effect can be measured independently.
 * The empty baseline intentionally preserves Ada's upstream behavior.
 *
 * Current mechanism: wall-clock economy. Hard-bounded runs score zero if they
 * are still working when the wall expires, even when the on-disk setup is
 * already complete, and finished passes show 10-37 turns where per-turn model
 * latency alone spans minutes. The guidance therefore makes economy of turns
 * and command time the explicit priority, while keeping the verify-by-execution
 * discipline (exit codes over appearance; detached, confirmed services) that
 * the executed end state depends on. Kept short — long guidance dilutes the
 * base preset.
 */
export const CODING_PROMPT_GUIDANCE = `
## Work within the wall clock
This run has a hard wall-clock budget of roughly 8 minutes; a run still working at the deadline scores zero even if the setup is complete. Economy of turns and command time is the priority — the deliverable is the final on-disk state, not your narration.
- Batch aggressively: combine related shell steps into one command (\`&&\`, \`;\`) or issue several independent tool calls in a single turn. Never re-read a file you already have or re-run a check that already passed.
- Front-load the long pole: start the main install/build as your first action. If it may run longer than ~2 minutes, background it (\`nohup cmd > /tmp/build.log 2>&1 &\`) and poll the log while doing other work, or pass an explicit generous Bash timeout (e.g. \`timeout: 600000\`) instead of letting the default kill it and having to retry.
- Anything that must stay available later (servers, databases, daemons) must be left running and detached; before finishing, confirm it is alive and accepting connections.
- Judge success only by exit codes of the repo's own documented build/test pipeline, never by output looking right; fix forward until the decisive check exits 0 — then stop immediately. Extra polish wastes the budget.
`.trim();
