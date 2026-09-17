import { CODING_PROMPT_GUIDANCE } from "./coding-guidance.ts";
import { githubPromptGuidance } from "./github-guidance.ts";

export function systemPromptGuidance(opts: { configured: boolean; connected: boolean }): string {
  return [CODING_PROMPT_GUIDANCE.trim(), githubPromptGuidance(opts)].filter(Boolean).join("\n\n");
}
