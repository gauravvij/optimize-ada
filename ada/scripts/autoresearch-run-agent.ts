/** Run one real Ada coding turn for the external autoresearch benchmark. */
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { ClaudeAgentSession } from "../agent/claude/agent.ts";
import { resolveModel } from "../agent/config/model.ts";
import { systemPromptGuidance } from "../agent/system-guidance.ts";
import type { ResultEvent } from "../agent/types/streamjson.ts";

const [workspaceArg, promptFileArg] = process.argv.slice(2);
if (!workspaceArg || !promptFileArg) {
  throw new Error("usage: node scripts/autoresearch-run-agent.ts WORKSPACE PROMPT_FILE");
}

const cwd = resolve(workspaceArg);
const prompt = await readFile(resolve(promptFileArg), "utf8");
let result: ResultEvent | null = null;

await new Promise<void>((resolveRun, rejectRun) => {
  const source = new ClaudeAgentSession({
    model: resolveModel(),
    allowedTools: ["Read", "Edit", "Write", "Bash", "Grep", "Glob"],
    permissionMode: "acceptEdits",
    cwd,
    userId: "autoresearch-benchmark",
    systemPromptAppend: systemPromptGuidance({ configured: false, connected: false }),
  });
  source.on("event", (event) => {
    if (event.type === "result") result = event as ResultEvent;
  });
  source.once("spawnError", rejectRun);
  source.once("exit", (code) => {
    if (code === 0) resolveRun();
    else rejectRun(new Error(`Ada agent exited ${code}`));
  });
  source.start();
  source.sendUserMessage(prompt);
  source.closeInput();
});

console.log(`ADA_RUN_RESULT=${JSON.stringify(result)}`);
