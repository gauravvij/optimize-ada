#!/usr/bin/env node
/**
 * Headless single-run Ada agent harness for autoresearcher evaluation.
 *
 *   node scripts/autoresearch-run-agent.ts <targetDir> <promptFile>
 *
 * Runs ONE ClaudeAgentSession (the real Ada agent loop through the Agent SDK)
 * against the micro-repository in <targetDir>, with the user prompt read from
 * <promptFile>. On completion prints exactly one line:
 *
 *   ADA_RUN_RESULT={"is_error":false,"num_turns":7,"total_cost_usd":0.012,"modelUsage":{...}}
 *
 * Everything else goes to stderr so the eval's stdout parser stays trivial.
 * Exit code is 0 even for agent errors (the JSON carries is_error) unless the
 * harness itself fails to start.
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { ClaudeAgentSession } from "../agent/claude/agent.ts";
import { resolveModel } from "../agent/config/model.ts";
import { systemGuidance } from "../agent/system-guidance.ts";
import type { StreamJsonEvent } from "../agent/types/streamjson.ts";

interface UsageEntry {
  inputTokens?: number;
  outputTokens?: number;
  cacheReadInputTokens?: number;
  cacheCreationInputTokens?: number;
}

interface RunResult {
  is_error: boolean;
  num_turns: number;
  total_cost_usd: number;
  modelUsage: Record<string, UsageEntry>;
}

async function main(): Promise<void> {
  const [targetDir, promptFile] = process.argv.slice(2);
  if (!targetDir || !promptFile) {
    console.error("usage: node scripts/autoresearch-run-agent.ts <targetDir> <promptFile>");
    process.exit(2);
  }
  const cwd = resolve(targetDir);
  const prompt = readFileSync(promptFile, "utf8").trim();

  const model = resolveModel();
  const session = new ClaudeAgentSession({
    model,
    allowedTools: ["Read", "Edit", "Write", "Bash", "Grep", "Glob"],
    permissionMode: "acceptEdits",
    cwd,
    systemPromptAppend: systemGuidance(),
  });

  let settled = false;
  const result: RunResult = {
    is_error: true,
    num_turns: 0,
    total_cost_usd: 0,
    modelUsage: {},
  };

  const finish = (): void => {
    if (settled) return;
    settled = true;
    session.stop();
    console.log(`ADA_RUN_RESULT=${JSON.stringify(result)}`);
  };

  session.on("event", (ev: StreamJsonEvent) => {
    const type = (ev as { type?: string }).type;
    if (type === "assistant") {
      result.num_turns += 1;
    } else if (type === "result") {
      const r = ev as {
        is_error?: boolean;
        num_turns?: number;
        total_cost_usd?: number;
        modelUsage?: Record<string, UsageEntry>;
      };
      if (typeof r.is_error === "boolean") result.is_error = r.is_error;
      if (typeof r.num_turns === "number") result.num_turns = r.num_turns;
      if (typeof r.total_cost_usd === "number") result.total_cost_usd = r.total_cost_usd;
      if (r.modelUsage && typeof r.modelUsage === "object") result.modelUsage = r.modelUsage;
    }
  });
  session.on("exit", (code) => {
    if (code !== 0) result.is_error = true;
    finish();
    process.exit(0);
  });
  session.on("spawnError", (err) => {
    console.error(`[runner] spawnError: ${err.message}`);
    result.is_error = true;
    finish();
    process.exit(0);
  });

  session.sendUserMessage(prompt);

  // Safety net: never hang forever; the eval also enforces its own timeout.
  const hardCapMs = Number(process.env.ADA_RUNNER_TIMEOUT_MS ?? 115_000);
  setTimeout(() => {
    console.error(`[runner] hard cap ${hardCapMs}ms reached — stopping session`);
    result.is_error = true;
    finish();
    process.exit(0);
  }, hardCapMs).unref();
}

main().catch((err: Error) => {
  console.error(`[runner] fatal: ${err.message}`);
  console.log(
    `ADA_RUN_RESULT=${JSON.stringify({ is_error: true, num_turns: 0, total_cost_usd: 0, modelUsage: {} })}`,
  );
  process.exit(0);
});
