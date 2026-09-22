/** Immutable SetupBench adapter entry point for one Ada attempt.
 *  Copy of setupbench_ada_runner.ts whose only change is a `ts` (epoch ms) on every trace entry,
 *  for per-turn latency. The original stays byte-identical to the runner R1-R10 recorded. */
import { appendFileSync, writeFileSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { ClaudeAgentSession } from "/opt/ada/agent/claude/agent.ts";
import { resolveModel } from "/opt/ada/agent/config/model.ts";
import { systemPromptGuidance } from "/opt/ada/agent/system-guidance.ts";
import type { ResultEvent, StreamJsonEvent } from "/opt/ada/agent/types/streamjson.ts";

const [workspaceArg, promptFileArg] = process.argv.slice(2);
if (!workspaceArg || !promptFileArg) {
  throw new Error("usage: node setupbench_ada_runner.ts WORKSPACE PROMPT_FILE");
}

const cwd = resolve(workspaceArg);
const prompt = await readFile(resolve(promptFileArg), "utf8");
let result: ResultEvent | null = null;
const tracePath = "/testbed/.ada-trace.jsonl";
writeFileSync(tracePath, "", "utf8");

function bounded(value: unknown, max = 4000): unknown {
  if (typeof value === "string") return value.length > max ? `${value.slice(0, max)}...[truncated]` : value;
  const rendered = JSON.stringify(value);
  if (rendered.length <= max) return value;
  return `${rendered.slice(0, max)}...[truncated]`;
}

function normalize(event: StreamJsonEvent): unknown | null {
  if (event.type === "assistant") {
    return {
      type: event.type,
      content: event.message.content.map((block) => {
        if (block.type === "text") return { type: block.type, text: bounded(block.text) };
        if (block.type === "thinking") return { type: block.type, thinking: bounded(block.thinking, 2000) };
        if (block.type === "tool_use") return { type: block.type, name: block.name, input: bounded(block.input) };
        return { type: block.type };
      }),
      usage: event.message.usage,
    };
  }
  if (event.type === "user") {
    return {
      type: event.type,
      content: event.message.content.map((block) =>
        block.type === "tool_result"
          ? { type: block.type, is_error: block.is_error, content: bounded(block.content) }
          : { type: block.type },
      ),
    };
  }
  if (event.type === "system") {
    if (event.subtype !== "init" && event.subtype !== "api_retry") return null;
    return { type: event.type, subtype: event.subtype, error: bounded((event as { error?: unknown }).error ?? "") };
  }
  if (event.type === "result") return event;
  return null;
}

await new Promise<void>((resolveRun, rejectRun) => {
  const source = new ClaudeAgentSession({
    model: resolveModel(),
    allowedTools: ["Read", "Edit", "Write", "Bash", "Grep", "Glob"],
    permissionMode: "acceptEdits",
    cwd,
    userId: "autoresearch-setupbench",
    systemPromptAppend: systemPromptGuidance({ configured: false, connected: false }),
  });
  source.on("event", (event) => {
    if (event.type === "result") result = event as ResultEvent;
    const item = normalize(event);
    if (item !== null) appendFileSync(tracePath, `${JSON.stringify({ ts: Date.now(), ...(item as object) })}\n`, "utf8");
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
