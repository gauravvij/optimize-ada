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

import { readFileSync } from "node:fs";
import { EventEmitter } from "node:events";
import { claudeSpawnEnv, type ResolvedModel } from "../config/model.ts";
import type { StreamJsonEvent } from "../types/streamjson.ts";

/**
 * Best-effort wall-clock start time of this container (PID 1's start time),
 * used to anchor the watchdog's hard deadline to the SAME clock the harness
 * force-kill uses. The SetupBench harness kills at container-start + budget,
 * but the runner (and thus the watchdog) only starts after container setup
 * (input tar extract + prerunner script) — so a runner-anchored deadline can
 * land AFTER the harness kill on setup-heavy tasks. That is the exact cause
 * of the 3 force-killed timeouts in the remaining81 incumbent run
 * (servo-e199a67, microsoft-azure-pipelines-tasks-bfcd4b2: log tails end in
 * an uninterrupted thinking-token trickle, no watchdog banner — agent-time
 * hadn't reached the deadline before the wall-clock kill). Returns null when
 * not detectable or implausible (e.g. a bare-metal host where PID 1 predates
 * any task budget); callers fall back to runner start (previous behavior).
 */
function containerStartedAtMs(): number | null {
  try {
    const stat = readFileSync("/proc/1/stat", "utf8");
    const close = stat.lastIndexOf(")");
    if (close < 0) return null;
    // Fields after "(comm)": index 0 is state (field 3); starttime is field
    // 22 → index 22 - 3 = 19.
    const fields = stat.slice(close + 2).trim().split(/\s+/);
    const starttimeTicks = Number(fields[19]);
    if (!Number.isFinite(starttimeTicks) || starttimeTicks <= 0) return null;
    const procStat = readFileSync("/proc/stat", "utf8");
    const btime = procStat
      .split("\n")
      .find((line) => line.startsWith("btime"));
    if (!btime) return null;
    const bootMs = Number(btime.split(/\s+/)[1]) * 1000;
    if (!Number.isFinite(bootMs) || bootMs <= 0) return null;
    // CLK_TCK is 100 on Linux x86_64 (fixed userspace ABI constant).
    return bootMs + (starttimeTicks * 1000) / 100;
  } catch {
    return null;
  }
}

/**
 * T1.2 pure helper (unit-tested in agent.test.ts before the hooks that call
 * it are wired): the time hint injected before each model request once
 * ADA_TIME_HINTS is on. Plain remaining-budget statement, plus the wrap-up
 * directive once the remaining time drops to/below the wrap-up window —
 * the model cannot pace itself otherwise (E4: budget string computed once
 * at t=0, nothing injects remaining time mid-run).
 */
export function timeHintText(
  nowMs: number,
  deadlineMs: number,
  budgetMs: number,
  wrapUpMs: number,
): string {
  const remainingMs = Math.max(0, deadlineMs - nowMs);
  const remainingSec = Math.ceil(remainingMs / 1000);
  const budgetSec = Math.round(budgetMs / 1000);
  let text = `⏱ ${remainingSec} s of ${budgetSec} s remain.`;
  if (remainingMs <= wrapUpMs) {
    text +=
      " Time is nearly up: stop exploring. Make the task's stated success command pass NOW " +
      "(run it literally), then reply with a one-line summary and stop. If a tool call is " +
      "interrupted, that is the time budget ending, not a user refusal.";
  }
  return text;
}

/**
 * T1.2 pure helper (unit-tested in agent.test.ts before the PreToolUse hook
 * that calls it is wired): cap a Bash tool call's requested timeout so a
 * single command cannot overrun the remaining task budget. Returns the
 * PreToolUse hookSpecificOutput (updatedInput + context) when a clamp is
 * needed, or null when the requested/default timeout already fits.
 * Floor of 5000 ms keeps the clamp from making commands useless.
 */
export function clampBashTimeout(
  toolInput: Record<string, unknown>,
  remainingMs: number,
  marginMs: number,
  defaultMs: number,
): {
  hookSpecificOutput: {
    hookEventName: "PreToolUse";
    updatedInput: Record<string, unknown>;
    additionalContext: string;
  };
} | null {
  const cap = Math.max(5_000, remainingMs - marginMs);
  const requested = typeof toolInput.timeout === "number" ? toolInput.timeout : defaultMs;
  if (requested <= cap) return null;
  return {
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      updatedInput: { ...toolInput, timeout: cap },
      additionalContext: `Bash timeout clamped to ${cap} ms: only ${Math.max(0, Math.ceil(remainingMs / 1000))} s remain.`,
    },
  };
}

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
  // CLI 2.1.263 leaks these into the claude_code preset's toolset; none are
  // usable/needed for a single coding turn (verified via session init trace).
  "ListAgents",
  "Monitor",
  "PushNotification",
  "ToolSearch",
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
  /**
   * Test seam: inject a fake `query()` instead of importing the real SDK.
   * Must match the SDK query()'s surface (async iterable of stream events,
   * optional interrupt()/close() controls). Used by agent.test.ts to
   * exercise the watchdog paths with no network and no CLI child.
   */
  queryFn?: (args: { prompt: string; options: unknown }) => AsyncIterable<unknown> & {
    interrupt?: () => unknown;
    close?: () => void;
  };
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
    // Test seam: an injected queryFn (agent.test.ts) replaces the real SDK
    // import so the watchdog paths can be exercised with no network/CLI.
    // `close?` is widened in because the abandoned path must terminate the
    // CLI child (sdk.d.ts:2950) so the node process can exit (T0.1/E6).
    let query: (args: { prompt: string; options: unknown }) => AsyncIterable<unknown> & {
      interrupt?: () => unknown;
      close?: () => void;
    };
    if (this.opts.queryFn) {
      query = this.opts.queryFn;
    } else {
      try {
        ({ query } = (await import("@astropods/adapter-claude-agent-sdk")) as {
          query: typeof query;
        });
      } catch (err) {
        throw new Error(`@astropods/adapter-claude-agent-sdk unavailable: ${(err as Error).message}`);
      }
    }

    // Model/auth/gateway seam, plus this user's GitHub token (if connected) as
    // GH_TOKEN — git/gh use it via the image's credential helper. Telemetry is
    // handled by the adapter (OpenInference spans), so no native OTel env here.
    // Derive the Bash time-box from the same budget the system guidance uses
    // (mirror of system-guidance.ts's long-budget math: min(120000, budget/6)),
    // so the tool-level clamp and the prompt stay consistent. Defaults match
    // the 480s SetupBench task cap; host env can override either knob.
    const taskBudgetMs = Number(process.env.ADA_RUNNER_TIMEOUT_MS ?? 480_000);
    const budgetBashCapMs = Math.max(20_000, Math.min(120_000, Math.floor(taskBudgetMs / 6)));
    const bashDefaultTimeoutMs = Number(process.env.BASH_DEFAULT_TIMEOUT_MS ?? budgetBashCapMs);
    const bashMaxTimeoutMs = Number(process.env.BASH_MAX_TIMEOUT_MS ?? budgetBashCapMs);

    // Deterministic finish-time watchdog (iteration 2). The SetupBench harness
    // polls for the runner process to exit and force-kills the container at the
    // task cap (480s) — when the model trickles thinking tokens through the
    // slow gateway, the SDK stream below never ends, the runner never exits,
    // and the official grader NEVER RUNS (observed on validation-12: 6/12
    // timeouts, several with substantial work already done). When the harness
    // declares a budget via ADA_RUNNER_TIMEOUT_MS we enforce it INSIDE the
    // session instead: an idle-token watchdog interrupts a stalled stream (no
    // event for ADA_STREAM_IDLE_TIMEOUT_MS) and a hard wall-clock deadline
    // (budget minus ADA_DEADLINE_MARGIN_MS) interrupts a trickling one so the
    // session ends cleanly — the runner prints ADA_RUN_RESULT, writes the exit
    // marker, and the grader runs on the work completed so far. Absent
    // ADA_RUNNER_TIMEOUT_MS (and without ADA_FINISH_TIME=1) the watchdog is
    // fully disabled and behavior is identical to the previous version.
    const finishTimeEnabled =
      process.env.ADA_RUNNER_TIMEOUT_MS !== undefined || process.env.ADA_FINISH_TIME === "1";
    const idleTimeoutMs = Number(process.env.ADA_STREAM_IDLE_TIMEOUT_MS ?? 120_000);
    const deadlineMarginMs = Number(process.env.ADA_DEADLINE_MARGIN_MS ?? 30_000);
    const interruptGraceMs = Number(process.env.ADA_INTERRUPT_GRACE_MS ?? 15_000);

    // Turn-0 thinking-trickle stall recovery (final iteration). Distinct from
    // the two watchdog layers: a trickle stream emits events CONSTANTLY (so
    // the idle watchdog never fires) yet never completes its first turn —
    // only thinking deltas, no assistant message, no tool call — until the
    // whole budget is gone. Detection is per-attempt: if the attempt has made
    // zero progress (anything besides a thinking delta) for
    // ADA_STALL_DETECT_MS, abort the request and immediately RETRY the turn
    // with thinking disabled (a no-thinking retry goes straight to acting),
    // up to ADA_STALL_RETRIES times. The hard-deadline watchdog stays as the
    // final backstop on every attempt. Like the watchdog itself, this only
    // exists on the budgeted path — with no ADA_RUNNER_TIMEOUT_MS the legacy
    // path below is untouched. OPT-IN by default: stall-retry is disabled
    // unless ADA_STALL_RETRIES is explicitly set in the environment (dev-12
    // gate evidence: default-active retry showed no measurable gain and
    // carries misfire risk on healthy
    // slow-thinking turns; the container-anchored deadline fix alone is the
    // evidence-backed delta vs the prior incumbent).
    const stallDetectMs = Number(process.env.ADA_STALL_DETECT_MS ?? 90_000);
    const stallMaxRetries = Math.max(0, Number(process.env.ADA_STALL_RETRIES ?? 0));
    // Bound inference-side stalls at runtime. The task cap force-kills any
    // session that overruns; observed stall modes are (a) a runaway
    // extended-thinking stream trickling token-by-token through the slow
    // gateway (2000+ thinking tokens observed in FIRST turns alone, while
    // normal turns use only ~300-500) and (b) a request that hangs in flight.
    // MAX_THINKING_TOKENS truncates (a) — 1024 keeps every observed useful
    // per-turn thinking budget while cutting the first-turn trickle — and
    // API_TIMEOUT_MS aborts (b) so Claude Code can retry, both well under the
    // cap. Overridable via host env.
    const childEnv: NodeJS.ProcessEnv = {
      ...claudeSpawnEnv(this.opts.model),
      MAX_THINKING_TOKENS: process.env.MAX_THINKING_TOKENS ?? "1024",
      API_TIMEOUT_MS: process.env.API_TIMEOUT_MS ?? "60000",
      // Deterministically clamp the Bash tool's execution window. The system
      // prompt asks for time-boxed Bash calls, but the model sometimes requests
      // far larger explicit timeouts anyway (observed: `timeout 160000` for a
      // bundle install under a 480s task cap — 1/3 of the budget on one
      // command). BASH_DEFAULT_TIMEOUT_MS covers calls that omit `timeout`;
      // BASH_MAX_TIMEOUT_MS hard-clamps even explicitly-requested larger ones.
      // Derived from the same budget the prompt uses, capped at 120s; anything
      // genuinely longer must run in the background and be polled (as the
      // prompt directs), which keeps the agent's own elapsed time observable.
      BASH_DEFAULT_TIMEOUT_MS: String(bashDefaultTimeoutMs),
      BASH_MAX_TIMEOUT_MS: String(bashMaxTimeoutMs),
      ...(this.opts.githubToken ? { GH_TOKEN: this.opts.githubToken } : {}),
    };
    // On the gateway path the effective model id is bedrock/-prefixed and carried
    // in ANTHROPIC_MODEL by claudeSpawnEnv. The SDK's explicit `model` option
    // OVERRIDES that env var, so read it back and pass the same id — otherwise a
    // bare `claude-*` reaches the gateway and is rejected (401/403 "virtual key
    // not found"). Direct mode leaves ANTHROPIC_MODEL as the bare id, so this is
    // a no-op there.
    const effectiveModel = childEnv.ANTHROPIC_MODEL ?? this.opts.model.id;

    // AbortController for attempt 0 (sdk.d.ts:1401): when the watchdog
    // abandons a stream that ignored its interrupt, abort() kills the CLI
    // child so the node process can actually exit instead of being
    // force-killed at the harness cap (T0.1/E6 — the two true force-kills).
    // Retry attempts create their own controller inside the loop.
    const abortController = new AbortController();

    // T1.2: the deadline anchor moves ABOVE the options literal because the
    // hooks below (and the watchdog) need hardDeadlineAt at construction
    // time; it depends only on taskBudgetMs/deadlineMarginMs. Honor
    // ADA_DEADLINE_ANCHOR=runner|container (default container — current
    // behavior; the TB adapter passes runner because that harness kills on
    // exec time, E12). Falls back to runner start when /proc is unreadable or
    // PID 1 predates any plausible task budget (bare-metal host).
    const deadlineAnchorChoice = process.env.ADA_DEADLINE_ANCHOR ?? "container";
    const runnerStartMs = Date.now();
    const containerStartMs = containerStartedAtMs();
    const deadlineAnchorMs =
      deadlineAnchorChoice === "runner" ||
      containerStartMs === null ||
      runnerStartMs - containerStartMs > taskBudgetMs
        ? runnerStartMs
        : containerStartMs;
    if (finishTimeEnabled && containerStartMs !== null && deadlineAnchorMs === containerStartMs) {
      console.error(
        `[claude:watchdog] deadline anchored to container start ` +
          `(container setup consumed ${runnerStartMs - containerStartMs}ms of the budget)`,
      );
    }
    const hardDeadlineAt = deadlineAnchorMs + Math.max(0, taskBudgetMs - deadlineMarginMs);

    // T1.2 gates (E13: the candidate's defaults live in code; env still
    // overrides). ADA_TIME_HINTS injects the remaining-time hint before each
    // model request; ADA_BASH_CLAMP_REMAINING clamps Bash timeouts to the
    // remaining budget. Both hooks exist ONLY on the budgeted path
    // (finishTimeEnabled) — the legacy no-budget path gets no hooks.
    // Default OFF since the 2026-09-12 same-day paired run: time hints were −4
    // tasks vs the gate-off build (54/81 → 50/81, p = 0.42) despite cutting
    // deadline interrupts 34 → 7. Opt in with ADA_TIME_HINTS=1 / ADA_BASH_CLAMP_REMAINING=1.
    const timeHintsOn = (process.env.ADA_TIME_HINTS ?? "0") === "1";
    const bashClampOn = (process.env.ADA_BASH_CLAMP_REMAINING ?? "0") === "1";
    const clampMarginMs = Number(process.env.ADA_BASH_CLAMP_MARGIN_MS ?? 20_000);
    const wrapUpMs = Number(
      process.env.ADA_WRAP_UP_MS ??
        Math.min(150_000, Math.max(60_000, Math.floor(0.2 * taskBudgetMs))),
    );

    const options = {
      abortController,
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
      // T1.2 time-awareness hooks (fina_run.md §2 T1.2). Exist only when
      // finishTimeEnabled AND their gate is on; the legacy no-budget path
      // builds no hooks at all.
      //  - PostToolBatch fires exactly once before each model request
      //    (sdk.d.ts:2451) → inject timeHintText as additionalContext so the
      //    model knows how much budget remains (E4: the budget string is
      //    computed once at t=0; nothing injects remaining time mid-run).
      //    ~20 tokens per request, no throttling.
      //  - PreToolUse (matcher "Bash") → clampBashTimeout caps a requested
      //    (or default) timeout to max(5000, remaining − margin) via
      //    updatedInput so a single command cannot overrun the budget (E8).
      ...(finishTimeEnabled && (timeHintsOn || bashClampOn)
        ? {
            hooks: {
              ...(timeHintsOn
                ? {
                    PostToolBatch: [
                      {
                        hooks: [
                          async () => ({
                            hookSpecificOutput: {
                              hookEventName: "PostToolBatch" as const,
                              additionalContext: timeHintText(
                                Date.now(),
                                hardDeadlineAt,
                                taskBudgetMs,
                                wrapUpMs,
                              ),
                            },
                          }),
                        ],
                      },
                    ],
                  }
                : {}),
              ...(bashClampOn
                ? {
                    PreToolUse: [
                      {
                        matcher: "Bash",
                        hooks: [
                          async (input: unknown) => {
                            const { tool_input } = input as {
                              tool_input?: Record<string, unknown>;
                            };
                            return (
                              clampBashTimeout(
                                (tool_input ?? {}) as Record<string, unknown>,
                                Math.max(0, hardDeadlineAt - Date.now()),
                                clampMarginMs,
                                bashDefaultTimeoutMs,
                              ) ?? {}
                            );
                          },
                        ],
                      },
                    ],
                  }
                : {}),
            },
          }
        : {}),
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
      const handle = (message: unknown): void => {
        const ev = message as StreamJsonEvent;
        // DEBUG: dump result / system / error-bearing events in full so a failed
        // run reveals its real cause instead of the generic "Claude Code run failed".
        const t = (ev as { type?: string }).type;
        if (t === "result" || t === "system" || (ev as { is_error?: boolean }).is_error) {
          console.error(`[claude:event ${t}] ${JSON.stringify(ev)}`);
        }
        this.emit("event", ev);
      };

      // Legacy path: no declared budget → consume the stream exactly as before.
      if (!finishTimeEnabled) {
        console.error("[claude:watchdog] disabled (no ADA_RUNNER_TIMEOUT_MS / ADA_FINISH_TIME)");
        for await (const message of q) handle(message);
        return;
      }

      // Watchdog path. Three layers, all derived from the harness budget:
      //   1. idle-stream watchdog — no SDK event for ADA_STREAM_IDLE_TIMEOUT_MS
      //      means the request hung in flight (Claude Code's own API_TIMEOUT_MS
      //      retry didn't recover it); interrupt so the CLI aborts the turn and
      //      emits its interrupted-result instead of sitting silent to the cap.
      //   2. hard wall-clock deadline — the budget minus ADA_DEADLINE_MARGIN_MS;
      //      catches the observed thinking-token TRICKLE (events arrive
      //      constantly so the idle watchdog never fires, but the turn never
      //      completes). Interrupting lets Claude Code finish the turn
      //      cleanly; the margin leaves room for the runner to exit and the
      //      harness to see the exit marker, so the official grader RUNS on the
      //      work completed so far instead of the container being force-killed.
      //   3. turn-0 trickle stall-retry (this iteration) — if an attempt has
      //      streamed for ADA_STALL_DETECT_MS producing ONLY thinking deltas
      //      (no assistant message, no tool call), abort the request and retry
      //      the turn immediately with thinking disabled, up to
      //      ADA_STALL_RETRIES times. The retry goes straight to acting, and
      //      the hard-deadline watchdog remains the final backstop on every
      //      attempt. Inert when ADA_STALL_RETRIES=0.
      // If the stream still doesn't end within ADA_INTERRUPT_GRACE_MS of the
      // interrupt, the iterator is abandoned outright (best-effort return()) so
      // this process can exit rather than be killed at the cap.
      console.error(
        `[claude:watchdog] enabled budget=${taskBudgetMs}ms idle=${idleTimeoutMs}ms ` +
          `margin=${deadlineMarginMs}ms grace=${interruptGraceMs}ms ` +
          `stallDetect=${stallDetectMs}ms stallRetries=${stallMaxRetries}`,
      );
      // (T1.2) The deadline anchor + hardDeadlineAt now live ABOVE the
      // options literal — the PostToolBatch/PreToolUse hooks need them at
      // construction time. See the T1.2 block just before `const options`.

      // Progress = evidence the turn is ADVANCING: a completed assistant
      // message (text or tool_use blocks), a tool result (user), a final
      // result, or a non-thinking stream delta. Deliberately EXCLUDES the
      // SDK's `system` events — `system/init` is the session bootstrap and
      // `system/thinking_tokens` is the thinking heartbeat, and the observed
      // trickle signature is EXACTLY those heartbeats arriving continuously
      // (one every ~1-2s) with no assistant message or tool call behind them
      // (proven in the stall-retry smoke: the detector never fired while the
      // log tail showed nothing but thinking_tokens system events).
      const isProgressEvent = (message: unknown): boolean => {
        const e = message as {
          type?: string;
          event?: { delta?: { type?: string } };
          message?: { content?: { type?: string }[] };
        };
        if (e.type === "stream_event") {
          // ONLY real content counts: text deltas (the assistant saying/doing
          // something) and tool-input deltas. The stream ENVELOPE events
          // (message_start, content_block_start for the thinking block,
          // content_block_stop, message_delta) carry no delta.type or a
          // non-content one and arrive constantly during a thinking-only
          // trickle — counting them as progress is exactly why the detector
          // never fired in the first stall-retry smoke.
          const d = e.event?.delta?.type ?? "";
          return d === "text_delta" || d === "input_json_delta";
        }
        if (e.type === "assistant") {
          // An assistant message counts ONLY when it carries a text or
          // tool_use block. With includePartialMessages the SDK emits a
          // completed assistant message whose content is a LONE THINKING
          // block as soon as the thinking block stops streaming (observed
          // 1749ms into the trickle in the stall-retry smoke) — that is the
          // trickle signature itself, not progress.
          const blocks = e.message?.content ?? [];
          return blocks.some((b) => b.type === "text" || b.type === "tool_use");
        }
        return e.type === "user" || e.type === "result";
      };

      // T0.1/E5: did any attempt yield a real `result` event, and how many
      // assistant messages preceded it? After the loop, a missing result is
      // synthesized (below) so both runners always get a parseable
      // ADA_RUN_RESULT with real turn counts instead of turns=0/zero usage.
      let sawResult = false;
      let assistantTurns = 0;
      const runStartedAt = Date.now();

      // Stall-retry loop. Attempt 0 reuses the already-started query; each
      // retry starts a FRESH query with thinking disabled (the stall mode is
      // thinking-mode; a no-thinking retry goes straight to acting).
      for (let attempt = 0; ; attempt++) {
        const thinkingDisabled = attempt > 0;
        // Per-attempt AbortController (T0.1 step 3): attempt 0 shares the
        // controller created above (already inside `options`); each retry
        // gets a fresh one so aborting an abandoned retry cannot abort a
        // controller a later attempt still needs.
        const ac = attempt === 0 ? abortController : new AbortController();
        const attemptOptions: unknown = thinkingDisabled
          ? {
              ...options,
              abortController: ac,
              thinking: { type: "disabled" },
              env: { ...childEnv, MAX_THINKING_TOKENS: "0" },
            }
          : { ...options, abortController: ac };
        const attemptQuery = attempt === 0 ? q : query({ prompt, options: attemptOptions });
        this.q = attemptQuery;
        if (thinkingDisabled) {
          console.error(
            `[claude:stall-retry] attempt ${attempt}/${stallMaxRetries}: ` +
              `retrying the turn with thinking disabled`,
          );
        }

        const iterator = attemptQuery[Symbol.asyncIterator]();
        const startedAt = Date.now();
        let lastEventAt = startedAt;
        let sawProgress = false;
        let thinkingChars = 0;
        let interruptSent = false;
        let interruptAt = 0;
        let abandoned = false;
        let stalled = false;
        let abandonNow: () => void = () => {};
        const abandonedPromise = new Promise<void>((resolve) => {
          abandonNow = resolve;
        });

        const fire = (reason: string, detail: string): void => {
          if (interruptSent) return;
          interruptSent = true;
          interruptAt = Date.now();
          console.error(`[claude:watchdog] ${reason} — interrupting stream: ${detail}`);
          // T0.1 step 5: interrupt() returns a Promise (sdk.d.ts:2615) — an
          // unhandled rejection crashes Node 24, so swallow it explicitly.
          try {
            Promise.resolve(attemptQuery.interrupt?.()).catch(() => {});
          } catch {
            /* best-effort */
          }
        };

        const watchdog = setInterval(() => {
          const now = Date.now();
          if (!interruptSent) {
            if (now >= hardDeadlineAt) {
              fire(
                "hard-deadline",
                `budget ${taskBudgetMs}ms exhausted; stopping cleanly within the ` +
                  `${deadlineMarginMs}ms margin so the grader can run`,
              );
            } else if (now - lastEventAt >= idleTimeoutMs) {
              fire(
                "idle-stream",
                `no SDK event for ${now - lastEventAt}ms (>= ${idleTimeoutMs}ms)`,
              );
            } else if (
              !sawProgress &&
              stallMaxRetries > 0 &&
              attempt < stallMaxRetries &&
              now - startedAt >= stallDetectMs &&
              hardDeadlineAt - now > 30_000
            ) {
              // Turn-0 thinking-trickle stall: the request has been streaming
              // for stallDetectMs with ONLY thinking deltas — no assistant
              // message, no tool call — so it is making no real progress and
              // the idle watchdog will never fire (events keep arriving).
              // Abort this request and retry the turn with thinking disabled.
              stalled = true;
              interruptSent = true;
              interruptAt = now;
              console.error(
                `[claude:stall-retry] thinking-trickle stall on attempt ${attempt}: ` +
                  `only thinking deltas for ${now - startedAt}ms (>= ${stallDetectMs}ms), ` +
                  `~${thinkingChars} thinking chars, no assistant message/tool call — ` +
                  `aborting request to retry the turn with thinking disabled`,
              );
              // T0.1 step 5: same Promise hardening as fire().
              try {
                Promise.resolve(attemptQuery.interrupt?.()).catch(() => {});
              } catch {
                /* best-effort */
              }
              try {
                void iterator.return?.(undefined as never);
              } catch {
                /* best-effort */
              }
              abandonNow();
            }
          } else if (!abandoned && now >= interruptAt + interruptGraceMs) {
            abandoned = true;
            console.error(
              `[claude:watchdog] stream did not end within ${interruptGraceMs}ms of ` +
                `interrupt — abandoning iterator so the run can finish`,
            );
            abandonNow();
          }
        }, 1000);

        type Step =
          | { kind: "next"; state: IteratorResult<unknown> }
          | { kind: "error"; error: unknown }
          | { kind: "abandoned" };
        try {
          while (true) {
            const winner: Step = await Promise.race([
              iterator.next().then(
                (state: IteratorResult<unknown>): Step => ({ kind: "next", state }),
                (error: unknown): Step => ({ kind: "error", error }),
              ),
              abandonedPromise.then((): Step => ({ kind: "abandoned" })),
            ]);
            if (winner.kind === "abandoned") break;
            if (winner.kind === "error") {
              // T0.1 step 1 (E5/E6): after OUR interrupt the SDK iterator
              // yields the interrupted `result` and then THROWS — previously
              // that rejection escaped run() as spawnError + exit(1), so the
              // runner never printed ADA_RUN_RESULT (19/50 passing tasks
              // showed turns=0). An error after our own interrupt is the
              // expected end of an interrupted session, not a crash: treat it
              // as a clean end. Real crashes (no interrupt sent) still throw.
              if (interruptSent) {
                console.error(
                  "[claude:watchdog] stream errored after our interrupt — treating as clean end",
                );
                break;
              }
              throw winner.error;
            }
            if (winner.state.done) break;
            lastEventAt = Date.now();
            const ev = winner.state.value as {
              type?: string;
              event?: { delta?: { type?: string; thinking?: string } };
            };
            if (ev.type === "result") sawResult = true;
            if (ev.type === "assistant") assistantTurns += 1;
            if (ev.type === "stream_event" && ev.event?.delta?.type === "thinking_delta") {
              thinkingChars += ev.event.delta.thinking?.length ?? 0;
            }
            if (isProgressEvent(winner.state.value) && !sawProgress) {
              sawProgress = true;
              console.error(
                `[claude:stall-retry] first progress event on attempt ${attempt} after ` +
                  `${Date.now() - startedAt}ms: ${JSON.stringify(winner.state.value).slice(0, 200)}`,
              );
            }
            handle(winner.state.value);
          }
        } finally {
          clearInterval(watchdog);
        }
        if (stalled) {
          // Aborted by the trickle detector with retries remaining (the
          // detector never sets `stalled` otherwise) — loop straight into the
          // no-thinking retry while the budget still allows real work.
          continue;
        }
        if (abandoned) {
          // Best-effort dispose of the SDK child; do NOT await it — a stuck
          // return() must not pin this process to the cap it just escaped.
          try {
            void iterator.return?.(undefined as never);
          } catch {
            /* best-effort */
          }
          // T0.1 step 3 (E6): the two true force-kills showed that
          // return() alone does NOT stop the abandoned `claude` child —
          // it kept the event loop alive (a fresh system/init and more
          // assistant turns appeared AFTER the error result), the runner
          // never exited, and the harness force-killed the container so
          // the grader never ran. close() terminates the underlying CLI
          // process (sdk.d.ts:2950) and abort() cancels the query and
          // cleans up its resources (sdk.d.ts:1401) — together they let
          // this node process actually exit.
          try {
            attemptQuery.close?.();
          } catch {
            /* best-effort */
          }
          ac.abort();
          console.error("[claude:watchdog] session terminated by watchdog; finishing with partial work");
        }
        break;
      }

      // T0.1 step 2 (E5): if no attempt delivered a `result` event (stream
      // abandoned, or errored before yielding one), synthesize one so the
      // runner ALWAYS prints a parseable ADA_RUN_RESULT with the real turn
      // count instead of turns=0/zero-usage artifacts. The shape mirrors
      // the SDK's error result; usage is empty because the CLI never
      // reported it (the interrupted result, when delivered, carries it).
      if (!sawResult) {
        console.error(
          `[claude:watchdog] no result event received — synthesizing one ` +
            `(assistantTurns=${assistantTurns})`,
        );
        handle({
          type: "result",
          subtype: "error_during_execution",
          is_error: true,
          session_id: "",
          num_turns: assistantTurns,
          duration_ms: Date.now() - runStartedAt,
          total_cost_usd: 0,
          usage: {},
          model_usage: {},
          result: "Session terminated by the watchdog before a result was delivered.",
        });
      }
    });
    this.emit("exit", 0);

    // T0.1 step 4 (E6): last resort — if anything (a stuck SDK child, an
    // unresolved transport) still pins the event loop after the clean exit
    // event, force-exit 0 shortly. The SetupBench runner prints
    // ADA_RUN_RESULT synchronously after the promise resolves, so the
    // default 5 s is ample. .unref() keeps the timer from holding the loop
    // open itself; only armed on the budgeted path (finishTimeEnabled).
    if (finishTimeEnabled) {
      setTimeout(() => process.exit(0), Number(process.env.ADA_FORCE_EXIT_AFTER_MS ?? 5000)).unref();
    }
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
