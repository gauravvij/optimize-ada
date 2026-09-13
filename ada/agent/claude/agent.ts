/**
 * Claude Agent SDK session source (default).
 *
 * Runs the Claude agent loop via the Claude Agent SDK's `query()` with the
 * `claude_code` system-prompt preset, instead of hand-spawning `claude -p` and
 * parsing NDJSON (see supervisor.ts for that fallback).
 *
 * We import the SDK through `@astropods/adapter-claude-agent-sdk` — a drop-in
 * re-export of `@anthropic-ai/claude-agent-sdk` whose `query()` is patched with
 * OpenInference OTel instrumentation wired to Astro's tracer provider. So
 * observability (query / sub-agent / tool / model spans) flows to the Astro
 * dashboard automatically when `OTEL_EXPORTER_OTLP_ENDPOINT` is set, and is a
 * no-op locally — no native-CLI telemetry env needed.
 *
 * Why the SDK: a TYPED message stream instead of an unversioned stdout contract
 * (our #1 pin). NB it is NOT in-process — it still spawns the Claude Code binary
 * as a child (image must contain `claude`); its messages mirror the CLI's
 * stream-json envelopes (system/init, assistant, user, stream_event, result),
 * so the existing `Translator` consumes them unchanged.
 *
 * Presents the same surface as ClaudeSupervisor (start / sendUserMessage /
 * closeInput / stop + "event"/"exit"/"spawnError") so index.ts wires it identically.
 */

import { EventEmitter } from "node:events";
import { claudeSpawnEnv, type ResolvedModel } from "../config/model.ts";
import type { StreamJsonEvent } from "../types/streamjson.ts";

/**
 * Tools REMOVED from the model's context (bare deny rules). `allowedTools` only
 * auto-approves — it does NOT limit availability — so without this the claude_code
 * preset exposes its full toolset. We keep the coding essentials (Read/Edit/Write/
 * Bash/Grep/Glob/NotebookEdit) and strip:
 *   - WebSearch/WebFetch — Anthropic server tools, dead on the Bedrock-backed gateway
 *   - Task/Workflow — sub-agent + multi-agent orchestration (cost multipliers)
 *   - platform/harness tools irrelevant to one coding turn (cron, scheduling,
 *     messaging, skills, worktree, design, the Task* board tools)
 * Applied by default in BOTH paths: the in-process session and the sandbox (which
 * constructs this same class). Override via AgentSessionOptions.disallowedTools.
 */
export const DEFAULT_DISALLOWED_TOOLS = [
  "WebSearch",
  "WebFetch",
  "Task",
  "Workflow",
  "Skill",
  "SendMessage",
  "DesignSync",
  "ReportFindings",
  "ScheduleWakeup",
  "CronCreate",
  "CronDelete",
  "CronList",
  "EnterWorktree",
  "ExitWorktree",
  "TaskCreate",
  "TaskGet",
  "TaskList",
  "TaskOutput",
  "TaskStop",
  "TaskUpdate",
];


/**
 * SDK-hooks seam (autoresearch loop v2, Phase 1) — deterministic levers at
 * ~zero prompt-token cost, env-gated OFF by default (mirrors lever-guidance.ts).
 * The installed claude-agent-sdk (0.3.193) declares
 * `hooks?: Partial<Record<HookEvent, HookCallbackMatcher[]>>` and `maxTurns?`;
 * the astropods adapter is a passthrough, so these reach the CLI unmodified.
 *
 * Gates (read from the BRIDGE process env, set by ada_agent.py _bridge_env):
 *   ADA_HOOK_SPIKE=1        H0: no-op PostToolUse logging hook (seam probe).
 *   ADA_HOOK_VERIFY_GATE=1  H1: Stop-hook verification gate — block the stop
 *                           ONCE if a file write happened with no
 *                           execution-class tool call (Bash) since it.
 *   ADA_HOOK_OUTPUT_CAP=N   H2: PostToolUse output capping — truncate tool
 *                           results longer than N chars (head+tail, elision
 *                           marker) via updatedToolOutput.
 *   ADA_HOOK_MAX_TURNS=N    H3: hard maxTurns cap on the agentic loop.
 */
interface HookRunState {
  seq: number;
  lastWriteSeq: number;
  lastBashSeq: number;
  blockedOnce: boolean;
}

type AdaHookFn = (input: unknown) => Promise<Record<string, unknown>>;

/**
 * H2: truncate a tool response above `cap` chars (head+tail, elision marker),
 * preserving the ORIGINAL shape so the SDK can substitute it back via
 * updatedToolOutput. tool_response is typed `unknown` and in practice is:
 *   - a plain string (Read/Grep-style tools), or
 *   - an object with string fields (Bash: {stdout, stderr, ...}), or
 *   - an array of content blocks ({type: "text", text: "..."}).
 * Returns undefined when nothing needed truncating (leave output untouched).
 */
function capString(s: string, cap: number): string | undefined {
  if (s.length <= cap) return undefined;
  const head = Math.floor(cap * 0.6);
  const tail = Math.floor(cap * 0.25);
  return (
    s.slice(0, head) +
    `\n[... harness: tool output truncated, ${s.length} chars -> head ${head} + tail ${tail}, middle elided ...]\n` +
    s.slice(s.length - tail)
  );
}

function capToolResponse(r: unknown, cap: number): unknown {
  if (typeof r === "string") return capString(r, cap);
  if (Array.isArray(r)) {
    let changed = false;
    const out = r.map((b) => {
      if (b && typeof b === "object" && typeof (b as { text?: unknown }).text === "string") {
        const t = capString((b as { text: string }).text, cap);
        if (t !== undefined) {
          changed = true;
          return { ...b, text: t };
        }
      }
      return b;
    });
    return changed ? out : undefined;
  }
  if (r && typeof r === "object") {
    let changed = false;
    const src = r as Record<string, unknown>;
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(src)) {
      if (typeof v === "string") {
        const t = capString(v, cap);
        if (t !== undefined) {
          changed = true;
          out[k] = t;
          continue;
        }
      }
      out[k] = v;
    }
    return changed ? out : undefined;
  }
  return undefined;
}

export function adaHookOptions(env: NodeJS.ProcessEnv = process.env): {
  hooks?: Record<string, { hooks: AdaHookFn[] }[]>;
  maxTurns?: number;
} {
  const spike = (env.ADA_HOOK_SPIKE ?? "0") === "1";
  const gate = (env.ADA_HOOK_VERIFY_GATE ?? "0") === "1";
  const capRaw = parseInt(env.ADA_HOOK_OUTPUT_CAP ?? "0", 10);
  const cap = Number.isFinite(capRaw) && capRaw > 0 ? capRaw : 0;
  const turnsRaw = parseInt(env.ADA_HOOK_MAX_TURNS ?? "0", 10);
  const maxTurns = Number.isFinite(turnsRaw) && turnsRaw > 0 ? turnsRaw : undefined;

  const state: HookRunState = { seq: 0, lastWriteSeq: 0, lastBashSeq: 0, blockedOnce: false };
  const postToolUse: AdaHookFn[] = [];

  if (spike) {
    postToolUse.push(async (input: unknown) => {
      const i = input as { tool_name?: string };
      console.error(`[hook:spike] PostToolUse ${i?.tool_name} fired`);
      return { continue: true };
    });
  }
  if (gate) {
    // Track write vs execution ordering for the Stop gate (H1).
    postToolUse.push(async (input: unknown) => {
      const i = input as { tool_name?: string };
      state.seq += 1;
      const n = i?.tool_name ?? "";
      if (n === "Write" || n === "Edit" || n === "NotebookEdit") state.lastWriteSeq = state.seq;
      if (n === "Bash") state.lastBashSeq = state.seq;
      return { continue: true };
    });
  }
  if (cap > 0) {
    postToolUse.push(async (input: unknown) => {
      const i = input as { tool_name?: string; tool_response?: unknown };
      const r = i?.tool_response;
      // Reach log: prove the hook fired even when nothing exceeds the cap.
      // tool_response is `unknown` — log its actual shape for diagnosis.
      const shape =
        typeof r === "string"
          ? `str:${r.length}`
          : r && typeof r === "object"
            ? Array.isArray(r)
              ? `arr[${r.length}]`
              : `obj[${Object.keys(r as Record<string, unknown>).join(",")}]`
            : `${typeof r}`;
      console.error(`[hook:cap] PostToolUse ${i?.tool_name} fired (resp ${shape})`);
      const updated = capToolResponse(r, cap);
      if (updated !== undefined) {
        console.error(`[hook:cap] PostToolUse ${i?.tool_name} truncated (cap ${cap})`);
        return {
          hookSpecificOutput: { hookEventName: "PostToolUse", updatedToolOutput: updated },
        };
      }
      return { continue: true };
    });
  }

  const hooks: Record<string, { hooks: AdaHookFn[] }[]> = {};
  if (postToolUse.length > 0) hooks.PostToolUse = [{ hooks: postToolUse }];
  if (gate) {
    hooks.Stop = [
      {
        hooks: [
          async (input: unknown) => {
            const i = input as { stop_hook_active?: boolean };
            // Fire at most once per session: respect the SDK's own re-entrancy
            // flag AND our own latch.
            console.error(
              `[hook:gate] Stop fired (writeSeq=${state.lastWriteSeq}, bashSeq=${state.lastBashSeq}, alreadyBlocked=${state.blockedOnce})`,
            );
            if (i?.stop_hook_active || state.blockedOnce) return { continue: true };
            state.blockedOnce = true;
            if (state.lastWriteSeq > 0 && state.lastBashSeq < state.lastWriteSeq) {
              console.error(
                "[hook:gate] Stop blocked once: no execution-class tool call since last write",
              );
              return {
                decision: "block",
                reason:
                  "You wrote or edited files but nothing has been executed since the last write. " +
                  "Run your solution against the task's real input (e.g. via Bash) and check the " +
                  "observable output before finishing.",
              };
            }
            return { continue: true };
          },
        ],
      },
    ];
  }

  const out: { hooks?: Record<string, { hooks: AdaHookFn[] }[]>; maxTurns?: number } = {};
  if (Object.keys(hooks).length > 0) out.hooks = hooks;
  if (maxTurns !== undefined) out.maxTurns = maxTurns;
  return out;
}

export interface AgentSessionOptions {
  model: ResolvedModel;
  allowedTools: string[];
  /** Tools removed from the model's context; defaults to DEFAULT_DISALLOWED_TOOLS. */
  disallowedTools?: string[];
  permissionMode?: string;
  resumeSessionId?: string;
  includePartialMessages?: boolean;
  cwd?: string;
  /** Extra instructions appended to the claude_code preset. */
  systemPromptAppend?: string;
  /** Per-user GitHub token (from OAuth) → injected as GH_TOKEN for git/gh. */
  githubToken?: string;
  /**
   * End user this run acts for (messaging StreamOptions.userId, or the resolved
   * web identity). Tagged on the run's trace as `langfuse.user.id` so the Astro
   * Traces page shows a User; empty/absent backfills "anonymous".
   */
  userId?: string;
}

type Events = {
  event: [StreamJsonEvent];
  exit: [number | null];
  spawnError: [Error];
};

/**
 * Minimal slice of `@opentelemetry/api` used to tag a run's trace with the end
 * user. Imported dynamically (see withUserTrace) so the bridge still runs when
 * the telemetry deps aren't installed, matching telemetry/otel.ts.
 */
interface OtelTraceApi {
  trace: {
    getTracer: (name: string) => {
      startSpan: (name: string) => { setAttribute: (k: string, v: unknown) => void; end: () => void };
    };
    setSpan: (ctx: unknown, span: unknown) => unknown;
  };
  context: {
    active: () => unknown;
    with: <T>(ctx: unknown, fn: () => T) => T;
  };
}

export class ClaudeAgentSession extends EventEmitter<Events> {
  private readonly opts: AgentSessionOptions;
  private q: { interrupt?: () => void } | null = null;

  constructor(opts: AgentSessionOptions) {
    super();
    this.opts = opts;
  }

  start(): void {
    /* no-op: the run begins on sendUserMessage (single-turn scaffold). */
  }

  /** Kick off a single-turn agent run. */
  sendUserMessage(text: string): void {
    void this.run(text).catch((err) => {
      this.emit("spawnError", err as Error);
      this.emit("exit", 1);
    });
  }

  closeInput(): void {
    /* no-op: a string-prompt query() runs to completion on its own. */
  }

  stop(): void {
    try {
      this.q?.interrupt?.();
    } catch {
      /* best-effort */
    }
  }

  private async run(prompt: string): Promise<void> {
    let query: (args: { prompt: string; options: unknown }) => AsyncIterable<unknown> & {
      interrupt?: () => void;
    };
    try {
      ({ query } = (await import("@astropods/adapter-claude-agent-sdk")) as {
        query: typeof query;
      });
    } catch (err) {
      throw new Error(`@astropods/adapter-claude-agent-sdk unavailable: ${(err as Error).message}`);
    }

    // Model/auth/gateway seam, plus this user's GitHub token (if connected) as
    // GH_TOKEN — git/gh use it via the image's credential helper. Telemetry is
    // handled by the adapter (OpenInference spans), so no native OTel env here.
    const childEnv: NodeJS.ProcessEnv = {
      ...claudeSpawnEnv(this.opts.model),
      ...(this.opts.githubToken ? { GH_TOKEN: this.opts.githubToken } : {}),
    };
    // On the gateway path the effective model id is bedrock/-prefixed and carried
    // in ANTHROPIC_MODEL by claudeSpawnEnv. The SDK's explicit `model` option
    // OVERRIDES that env var, so read it back and pass the same id — otherwise a
    // bare `claude-*` reaches the gateway and is rejected (401/403 "virtual key
    // not found"). Direct mode leaves ANTHROPIC_MODEL as the bare id, so this is
    // a no-op there.
    const effectiveModel = childEnv.ANTHROPIC_MODEL ?? this.opts.model.id;
    const hookOpts = adaHookOptions();

    const options = {
      model: effectiveModel,
      allowedTools: this.opts.allowedTools,
      disallowedTools: this.opts.disallowedTools ?? DEFAULT_DISALLOWED_TOOLS,
      permissionMode: this.opts.permissionMode ?? "acceptEdits",
      includePartialMessages: this.opts.includePartialMessages ?? true,
      // Run LEAN to cut the child's cold-start + memory: don't scan the filesystem
      // for skills / subagents / slash-commands / CLAUDE.md (settingSources: []),
      // load no skills, and skip MCP discovery. Ada is a code agent (Read/Edit/
      // Write/Bash/Grep/Glob) — none of that is used. The claude_code preset,
      // model, and agentic loop (maxTurns) are deliberately KEPT.
      settingSources: [],
      skills: [],
      mcpServers: {},
      strictMcpConfig: true,
      systemPrompt: {
        type: "preset",
        preset: "claude_code",
        ...(this.opts.systemPromptAppend ? { append: this.opts.systemPromptAppend } : {}),
      },
      ...(this.opts.resumeSessionId ? { resume: this.opts.resumeSessionId } : {}),
      ...(this.opts.cwd ? { cwd: this.opts.cwd } : {}),
      env: childEnv,
      // SDK-hooks seam (loop v2 Phase 1): env-gated, OFF by default — the
      // options object simply omits hooks/maxTurns unless a gate is set.
      ...(hookOpts.hooks ? { hooks: hookOpts.hooks } : {}),
      ...(hookOpts.maxTurns ? { maxTurns: hookOpts.maxTurns } : {}),
      // DEBUG: capture the CLI's stderr — gateway/API failures (Bifrost "model
      // not found", 4xx, auth) print here and don't always reach the result event.
      stderr: (data: unknown) =>
        console.error(`[claude:stderr] ${typeof data === "string" ? data : JSON.stringify(data)}`),
    };

    // Attach the end user to this run's trace so it shows up in Astro's "Traces"
    // page. The claude-agent-sdk adapter emits OpenInference spans but exposes no
    // hook for user identity, so we open a parent span carrying `langfuse.user.id`
    // and run query() inside its context: the adapter's spans nest under it (the
    // shared tracer provider registers a global context manager), Langfuse reads
    // the trace's user from the root span, and the OTLP ingester leaves the
    // attribute intact. Mirrors the langchain/mastra adapters.
    await this.withUserTrace(async () => {
      const q = query({ prompt, options });
      this.q = q;
      console.error(`[claude:run] starting model=${effectiveModel}`);
      // SDK messages mirror the CLI stream-json envelopes; the cast bridges the
      // SDK's typed union to ours so the Translator/telemetry consume them as-is.
      for await (const message of q) {
        const ev = message as StreamJsonEvent;
        // DEBUG: dump result / system / error-bearing events in full so a failed
        // run reveals its real cause instead of the generic "Claude Code run failed".
        const t = (ev as { type?: string }).type;
        if (t === "result" || t === "system" || (ev as { is_error?: boolean }).is_error) {
          console.error(`[claude:event ${t}] ${JSON.stringify(ev)}`);
        }
        this.emit("event", ev);
      }
    });
    this.emit("exit", 0);
  }

  /**
   * Run `fn` inside an OTel span whose `langfuse.user.id` is this run's end user,
   * so the adapter's nested spans inherit it and the run shows a User in the
   * Traces page. Backfills "anonymous" for an empty id (keeps unauthenticated
   * runs out of the "No user" bucket, matching the langchain/mastra adapters).
   * Degrades to calling `fn` directly when `@opentelemetry/api` is absent.
   */
  private async withUserTrace(fn: () => Promise<void>): Promise<void> {
    let otel: OtelTraceApi;
    try {
      otel = (await import("@opentelemetry/api")) as unknown as OtelTraceApi;
    } catch {
      await fn();
      return;
    }
    const span = otel.trace.getTracer("ada").startSpan("ada.agent.run");
    span.setAttribute("langfuse.user.id", this.opts.userId || "anonymous");
    const ctx = otel.trace.setSpan(otel.context.active(), span);
    try {
      await otel.context.with(ctx, fn);
    } finally {
      span.end();
    }
  }
}
