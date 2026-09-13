/**
 * E-opt1 concision guidance — env-gated system-prompt addition.
 *
 * Targets the lever measured in the Ada harness baseline traces
 * (eval/analysis/trace-signals.md over 60 ada-bridge trials):
 *   - 22 tool results >10k chars accounted for 44% of ALL tool-result chars
 *     (934k chars total; largest consumers: sanitize-git-repo, fix-code-
 *     vulnerability, db-wal-recovery, password-recovery — Bash/Read dumps up
 *     to ~33k chars each).
 *   - mean 8,003 output tokens per trial (max 34,384) — verbose narration
 *     inflates the output-token bill (haiku output $5/MTok).
 *   - mean cache-read ratio 0.919 → prompt-structure changes must NOT break
 *     the ~92% prefix cache hit rate (prefix cache is the reason mean cost is
 *     only ~$0.10/trial); the guidance is appended to the system prompt only
 *     when ADA_CONCISION_GUIDANCE=1 is set, so baseline behavior is untouched
 *     unless the experiment enables it.
 *
 * The guidance steers the model toward cheaper operations WITHOUT touching the
 * tool set or permission mode (both stay identical to the reference arm):
 *   1. prefer targeted reads (grep/head/tail/sed/awk, Read with line ranges)
 *      over dumping whole files;
 *   2. truncate/summarize oversized command output instead of echoing it all
 *      back to the conversation;
 *   3. avoid re-running unchanged commands and avoid repeated identical reads;
 *   4. keep assistant narration terse (no long step-by-step essays).
 */
export function concisionGuidance(env: NodeJS.ProcessEnv = process.env): string {
  if ((env.ADA_CONCISION_GUIDANCE ?? "0") !== "1") {
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
