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

/** Shape of the adapter's `query()` — an async stream of CLI envelope messages. */
type QueryFn = (args: {
  prompt: string;
  options: unknown;
}) => AsyncIterable<unknown> & { interrupt?: () => void };

/**
 * Model-wait watchdog. Benchmark traces show runs that emit NO model output for
 * the entire task wall (~8 min) while healthy runs stream partial messages from
 * the first seconds (TTFT 5-8s) — i.e. the model call (or the child CLI's stream)
 * is dead, burning the whole budget for a guaranteed zero. While we are waiting
 * ON THE MODEL (not while a tool the agent started is running — those can take
 * minutes legitimately), total stream silence longer than this aborts the child
 * via the SDK's `abortController` and the run restarts fresh. Re-armed on every
 * assistant/stream_event, so a "trickle one event then hang" stall is also caught.
 */
const MODEL_WAIT_WATCHDOG_MS = 90_000;
/** Total attempts (first try + restarts after dead model waits / stream deaths). */
const MAX_RUN_ATTEMPTS = 4;
/**
 * Wall-clock age past which no NEW attempt is started, so the final attempt has
 * at least ~2 min of wall to do real work instead of restarting into the wall.
 * A run abandoned here exits gracefully — the same zero score as burning the
 * wall, but without hanging the harness.
 */
const RETRY_WALL_DEADLINE_MS = 360_000;

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

/**
 * True when an assistant message carries a `tool_use` block — i.e. the agent
 * started a tool run whose duration is legitimate (Bash self-bounds via its
 * timeout; the rest are local and fast). The watchdog pauses for these and
 * re-arms when the tool's `user` result arrives.
 */
function assistantStartsToolRun(ev: unknown): boolean {
  const content = (ev as { message?: { content?: Array<{ type?: string }> } })?.message?.content;
  return Array.isArray(content) && content.some((b) => b?.type === "tool_use");
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
    let query: QueryFn;
    try {
      ({ query } = (await import("@astropods/adapter-claude-agent-sdk")) as {
        query: QueryFn;
      });
    } catch (err) {
      throw new Error(`@astropods/adapter-claude-agent-sdk unavailable: ${(err as Error).message}`);
    }

    // Model/auth/gateway seam, plus this user's GitHub token (if connected) as
    // GH_TOKEN — git/gh use it via the image's credential helper. Telemetry is
    // handled by the adapter (OpenInference spans), so no native OTel env here.
    const childEnv: NodeJS.ProcessEnv = {
      ...claudeSpawnEnv(this.opts.model),
      // Bash-tool time economy: the CLI's Bash tool kills commands at its short
      // default timeout, so long installs (apt/npm/pip) die mid-flight and get
      // re-run from scratch, burning the task's wall clock. Raise the default
      // (still under the CLI maximum) so long operations complete instead of
      // looping; agents can still pass explicit shorter/longer per-call values.
      BASH_DEFAULT_TIMEOUT_MS: "300000",
      BASH_MAX_TIMEOUT_MS: "600000",
      ...(this.opts.githubToken ? { GH_TOKEN: this.opts.githubToken } : {}),
    };
    // On the gateway path the effective model id is bedrock/-prefixed and carried
    // in ANTHROPIC_MODEL by claudeSpawnEnv. The SDK's explicit `model` option
    // OVERRIDES that env var, so read it back and pass the same id — otherwise a
    // bare `claude-*` reaches the gateway and is rejected (401/403 "virtual key
    // not found"). Direct mode leaves ANTHROPIC_MODEL as the bare id, so this is
    // a no-op there.
    const effectiveModel = childEnv.ANTHROPIC_MODEL ?? this.opts.model.id;

    const baseOptions = {
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
      const runStart = Date.now();
      for (let attempt = 1; attempt <= MAX_RUN_ATTEMPTS; attempt++) {
        let outcome: "completed" | "stalled";
        try {
          outcome = await this.runAttempt(query, prompt, baseOptions, effectiveModel, attempt);
        } catch (err) {
          // The stream died without a result and without the watchdog (spawn/API
          // failure). The previous behavior surfaced this as spawnError + exit 1 =
          // guaranteed task failure; a fresh attempt is strictly better while wall
          // budget remains. Out of budget: rethrow to preserve that behavior.
          if (attempt >= MAX_RUN_ATTEMPTS || Date.now() - runStart > RETRY_WALL_DEADLINE_MS) {
            throw err;
          }
          console.error(
            `[claude:watchdog] attempt=${attempt} died without a result ` +
              `(${(err as Error).message}); retrying`,
          );
          outcome = "stalled";
        }
        if (outcome === "completed") return;
        if (attempt >= MAX_RUN_ATTEMPTS || Date.now() - runStart > RETRY_WALL_DEADLINE_MS) {
          console.error(
            `[claude:watchdog] giving up after attempt=${attempt} ` +
              `(elapsed=${Date.now() - runStart}ms); ending run`,
          );
          return;
        }
        // Brief settle before retrying so the killed child's resources are
        // actually released before we respawn in this small container.
        await new Promise((r) => setTimeout(r, 2_000));
      }
    });
    this.emit("exit", 0);
  }

  /**
   * One query() attempt under the model-wait watchdog. Returns "completed" when
   * a result event was seen (success OR error — either is a terminal outcome the
   * runner can grade), "stalled" when the attempt produced no result and the
   * watchdog aborted a dead model wait, and throws when the stream died on its
   * own without a result (spawn/API failure — retried by the caller while wall
   * budget remains).
   *
   * Arming discipline: the watchdog runs ONLY while awaiting model output. The
   * `system` envelopes (init, api_retry) neither arm nor disarm it — exp-6
   * evidence showed a stall surviving a first-output watchdog that fired on
   * init. Every `assistant`/`stream_event` re-arms it; an assistant message
   * carrying `tool_use` pauses it (the agent's own Bash/Grep/... can take
   * minutes legitimately and self-bound via the Bash timeout); the following
   * `user` tool_result re-arms it for the next model wait.
   */
  private async runAttempt(
    query: QueryFn,
    prompt: string,
    baseOptions: Record<string, unknown>,
    effectiveModel: string,
    attempt: number,
  ): Promise<"completed" | "stalled"> {
    const abortController = new AbortController();
    // Lets the watchdog kill a hung child cleanly (the SDK's abort listener
    // SIGTERM/SIGKILLs the spawned CLI) so the attempt can restart.
    const options = { ...baseOptions, abortController };
    const q = query({ prompt, options });
    this.q = q;
    console.error(`[claude:run] attempt=${attempt} starting model=${effectiveModel}`);

    let sawResult = false;
    let stalled = false;
    let awaitingModel = true;
    let lastModelActivity = Date.now();

    const watchdog = setInterval(() => {
      if (!awaitingModel || Date.now() - lastModelActivity <= MODEL_WAIT_WATCHDOG_MS) return;
      stalled = true;
      awaitingModel = false; // fire once per attempt
      console.error(
        `[claude:watchdog] attempt=${attempt} no model output for >` +
          `${MODEL_WAIT_WATCHDOG_MS}ms while awaiting the model; aborting for restart`,
      );
      try {
        abortController.abort();
      } catch {
        /* child already gone */
      }
    }, 5_000);

    // SDK messages mirror the CLI stream-json envelopes; the cast bridges the
    // SDK's typed union to ours so the Translator/telemetry consume them as-is.
    const consume = (async (): Promise<void> => {
      for await (const message of q) {
        const ev = message as StreamJsonEvent;
        switch (ev.type) {
          case "assistant":
            lastModelActivity = Date.now();
            if (assistantStartsToolRun(ev)) awaitingModel = false;
            break;
          case "stream_event":
            lastModelActivity = Date.now();
            break;
          case "user":
            awaitingModel = true;
            lastModelActivity = Date.now();
            break;
          case "result":
            sawResult = true;
            break;
          default:
            break; // system/init & friends: neither model output nor a tool boundary
        }
        // DEBUG: dump result / system / error-bearing events in full so a failed
        // run reveals its real cause instead of the generic "Claude Code run failed".
        if (ev.type === "result" || ev.type === "system" || (ev as { is_error?: boolean }).is_error) {
          console.error(`[claude:event ${ev.type}] ${JSON.stringify(ev)}`);
        }
        this.emit("event", ev);
      }
    })();

    try {
      await consume;
    } finally {
      clearInterval(watchdog);
    }
    if (sawResult) return "completed";
    if (stalled) return "stalled";
    throw new Error(`claude agent stream ended without a result (attempt ${attempt})`);
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
