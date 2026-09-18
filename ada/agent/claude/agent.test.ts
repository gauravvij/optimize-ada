/**
 * Unit tests for the watchdog/clean-exit paths in agent.ts (fina_run.md T0.3).
 *
 * No network, no CLI child: the SDK `query()` is replaced via the
 * AgentSessionOptions.queryFn test seam, so the interrupt/abandon/synthesize
 * logic is exercised deterministically.
 *
 * Run: cd ada && node --test agent/claude/agent.test.ts   (Node 24 strips types)
 */

import test from "node:test";
import assert from "node:assert/strict";
import { ClaudeAgentSession, clampBashTimeout, timeHintText } from "./agent.ts";

/**
 * The T0.1 step-4 force-exit fallback arms `setTimeout(process.exit(0),
 * ADA_FORCE_EXIT_AFTER_MS ?? 5000)` on every budgeted run. Inside a single
 * test process that timer would kill the remaining tests 5 s after the first
 * session finishes — push it far out so it never fires under test.
 */
process.env.ADA_FORCE_EXIT_AFTER_MS = "3600000";

// claudeSpawnEnv() throws when neither ANTHROPIC_API_KEY nor a gateway URL is
// configured; the tests never spawn the CLI, so a dummy key suffices.
process.env.ANTHROPIC_API_KEY ??= "sk-test-dummy";

type AnyEvent = Record<string, unknown>;

interface Recorded {
  events: AnyEvent[];
  results: AnyEvent[];
  spawnErrors: Error[];
  exitCode: number | null;
}

/** Run one session against a fake queryFn and record everything it emits. */
async function runSession(
  queryFn: (args: { prompt: string; options: unknown }) => AsyncIterable<unknown> & {
    interrupt?: () => unknown;
    close?: () => void;
  },
  env: Record<string, string>,
): Promise<Recorded> {
  const prev: Record<string, string | undefined> = {};
  for (const [k, v] of Object.entries(env)) {
    prev[k] = process.env[k];
    process.env[k] = v;
  }
  try {
    const rec: Recorded = { events: [], results: [], spawnErrors: [], exitCode: null };
    const session = new ClaudeAgentSession({
      model: { id: "test-model", provider: "test" },
      allowedTools: ["Bash"],
      queryFn,
    });
    session.on("event", (ev: unknown) => {
      const e = ev as AnyEvent;
      rec.events.push(e);
      if (e.type === "result") rec.results.push(e);
    });
    session.on("spawnError", (err: Error) => rec.spawnErrors.push(err));
    const done = new Promise<number | null>((resolve) => session.once("exit", resolve));
    session.start();
    session.sendUserMessage("test prompt");
    session.closeInput();
    rec.exitCode = await done;
    return rec;
  } finally {
    for (const [k, v] of Object.entries(prev)) {
      if (v === undefined) delete process.env[k];
      else process.env[k] = v;
    }
  }
}

/**
 * Fake query that yields the given prefix events, then PARKS (its next()
 * never resolves) until interrupt() is called. `then` controls what happens
 * after the park releases: "result-then-reject" (the observed SDK behavior
 * after an interrupt) or "reject" (no result at all).
 */
function parkingQuery(
  prefix: AnyEvent[],
  then: "result-then-reject" | "reject",
): (args: { prompt: string; options: unknown }) => AsyncIterable<unknown> & {
  interrupt?: () => unknown;
  close?: () => void;
} {
  let release: () => void = () => {};
  const parked = new Promise<void>((resolve) => {
    release = resolve;
  });
  let interrupted = false;
  const fn = (_args: { prompt: string; options: unknown }) => {
    const iterable = {
      async *[Symbol.asyncIterator]() {
        for (const ev of prefix) yield ev;
        await parked;
        if (then === "result-then-reject") {
          yield {
            type: "result",
            subtype: "error_during_execution",
            is_error: true,
            session_id: "fake",
            num_turns: prefix.length,
            total_cost_usd: 0,
            usage: {},
          };
        }
        throw new Error("stream aborted after interrupt (fake)");
      },
      interrupt: () => {
        interrupted = true;
        release();
      },
      close: () => {
        release();
      },
    };
    return iterable;
  };
  // Expose interruption state for assertions via a side channel.
  (fn as unknown as { wasInterrupted: () => boolean }).wasInterrupted = () => interrupted;
  return fn;
}

// ---------------------------------------------------------------------------
// Group 1: timeHintText thresholds
// ---------------------------------------------------------------------------

test("timeHintText: plain remaining-budget statement above the wrap-up window", () => {
  const budget = 480_000;
  const wrapUp = 96_000;
  // 300 s remain — far above the 96 s wrap-up window: no wrap-up sentence.
  const text = timeHintText(0, 300_000, budget, wrapUp);
  assert.equal(text, "⏱ 300 s of 480 s remain.");
  assert.ok(!text.includes("Time is nearly up"));
});

test("timeHintText: wrap-up directive appears at/below the wrap-up window", () => {
  const budget = 480_000;
  const wrapUp = 96_000;
  // Exactly at the window boundary.
  const atBoundary = timeHintText(0, 96_000, budget, wrapUp);
  assert.ok(atBoundary.startsWith("⏱ 96 s of 480 s remain."));
  assert.ok(atBoundary.includes("Time is nearly up"));
  assert.ok(atBoundary.includes("not a user refusal"));
  // Well inside the window.
  const inside = timeHintText(0, 30_000, budget, wrapUp);
  assert.ok(inside.includes("Time is nearly up"));
});

test("timeHintText: clamps at zero and rounds remaining seconds up", () => {
  assert.equal(timeHintText(0, 0, 480_000, 96_000), "⏱ 0 s of 480 s remain. Time is nearly up: stop exploring. Make the task's stated success command pass NOW (run it literally), then reply with a one-line summary and stop. If a tool call is interrupted, that is the time budget ending, not a user refusal.");
  // 500 ms remaining rounds up to 1 s.
  assert.ok(timeHintText(0, 500, 480_000, 96_000).startsWith("⏱ 1 s of 480 s remain."));
  // Past the deadline clamps to 0, never negative.
  assert.ok(timeHintText(0, -5_000, 480_000, 96_000).startsWith("⏱ 0 s of 480 s remain."));
});

// ---------------------------------------------------------------------------
// Group 2: clampBashTimeout cases
// ---------------------------------------------------------------------------

test("clampBashTimeout: requested 120 s with 50 s remaining, 20 s margin → clamped to 30000", () => {
  const out = clampBashTimeout({ command: "x", timeout: 120_000 }, 50_000, 20_000, 80_000);
  assert.ok(out, "expected a clamp");
  assert.equal(out.hookSpecificOutput.hookEventName, "PreToolUse");
  assert.equal(out.hookSpecificOutput.updatedInput.timeout, 30_000);
  assert.equal(out.hookSpecificOutput.updatedInput.command, "x");
  assert.ok(out.hookSpecificOutput.additionalContext.includes("30000 ms"));
});

test("clampBashTimeout: no requested timeout, 300 s remaining → null (default fits)", () => {
  const out = clampBashTimeout({ command: "x" }, 300_000, 20_000, 120_000);
  assert.equal(out, null);
});

test("clampBashTimeout: floor of 5000 ms when remaining minus margin is tiny", () => {
  const out = clampBashTimeout({ command: "x", timeout: 120_000 }, 10_000, 20_000, 80_000);
  assert.ok(out, "expected a clamp");
  assert.equal(out.hookSpecificOutput.updatedInput.timeout, 5_000);
});

test("clampBashTimeout: requested timeout already within the cap → null", () => {
  assert.equal(clampBashTimeout({ command: "x", timeout: 20_000 }, 50_000, 20_000, 80_000), null);
});

// ---------------------------------------------------------------------------
// Group 3: interrupt → is_error result → reject ⇒ clean end, no spawnError
// ---------------------------------------------------------------------------

test("watchdog: stream errors after our interrupt is treated as a clean end", async () => {
  const prefix: AnyEvent[] = [
    { type: "assistant", message: { content: [{ type: "text", text: "working" }] } },
    { type: "user", message: { content: [{ type: "tool_result" }] } },
  ];
  const rec = await runSession(parkingQuery(prefix, "result-then-reject"), {
    ADA_RUNNER_TIMEOUT_MS: "1500",
    ADA_DEADLINE_MARGIN_MS: "500",
    ADA_INTERRUPT_GRACE_MS: "5000",
  });
  assert.equal(rec.spawnErrors.length, 0, "no spawnError after an interrupted stream");
  assert.equal(rec.exitCode, 0);
  assert.equal(rec.results.length, 1, "exactly one result event");
  assert.equal(rec.results[0].subtype, "error_during_execution");
  assert.equal(rec.results[0].num_turns, 2, "the real interrupted result carries its own turns");
});

// ---------------------------------------------------------------------------
// Group 4: interrupt → reject with NO result ⇒ one synthetic result, exit 0
// ---------------------------------------------------------------------------

test("watchdog: reject without a result synthesizes a parseable result", async () => {
  const prefix: AnyEvent[] = [
    { type: "assistant", message: { content: [{ type: "text", text: "working" }] } },
  ];
  const rec = await runSession(parkingQuery(prefix, "reject"), {
    ADA_RUNNER_TIMEOUT_MS: "1500",
    ADA_DEADLINE_MARGIN_MS: "500",
    ADA_INTERRUPT_GRACE_MS: "5000",
  });
  assert.equal(rec.spawnErrors.length, 0, "no spawnError after an interrupted stream");
  assert.equal(rec.exitCode, 0);
  assert.equal(rec.results.length, 1, "exactly one (synthetic) result event");
  const result = rec.results[0];
  assert.equal(result.type, "result");
  assert.equal(result.subtype, "error_during_execution");
  assert.equal(result.is_error, true);
  assert.equal(result.num_turns, 1, "synthetic result counts the real assistant turn");
  assert.equal(result.total_cost_usd, 0);
  assert.deepEqual(result.usage, {});
});

// ---------------------------------------------------------------------------
// Group 5: reject BEFORE any interrupt ⇒ spawnError + exit 1 (regression guard)
// ---------------------------------------------------------------------------

test("watchdog: a genuine stream error (no interrupt) still fails the run", async () => {
  const queryFn = (_args: { prompt: string; options: unknown }) => ({
    async *[Symbol.asyncIterator]() {
      yield { type: "assistant", message: { content: [{ type: "text", text: "boom" }] } };
      throw new Error("genuine API failure");
    },
  });
  const rec = await runSession(queryFn, {
    ADA_RUNNER_TIMEOUT_MS: "60000",
    ADA_DEADLINE_MARGIN_MS: "5000",
  });
  assert.equal(rec.spawnErrors.length, 1, "real crashes stay spawnErrors");
  assert.equal(rec.exitCode, 1);
  assert.equal(rec.results.length, 0, "no result is synthesized for a genuine crash");
});
// ---------------------------------------------------------------------------
// Group 6 (T1.2): hook gating via the queryFn seam — the fake query captures
// the options literal so hook presence/shape/behavior is asserted without
// any CLI child.
// ---------------------------------------------------------------------------

interface Captured {
  options?: {
    hooks?: Record<string, { matcher?: string; hooks: unknown[] }[]>;
  };
}

/**
 * Run one session whose queryFn captures the options literal, then resolves
 * immediately with a clean result. `env` entries with value undefined are
 * DELETED from process.env (needed to prove the no-budget legacy path).
 */
async function runCapture(
  env: Record<string, string | undefined>,
): Promise<Captured> {
  const captured: Captured = {};
  const queryFn = (args: { prompt: string; options: unknown }) => {
    captured.options = args.options as Captured["options"];
    return {
      async *[Symbol.asyncIterator]() {
        yield {
          type: "result",
          subtype: "success",
          is_error: false,
          session_id: "fake",
          num_turns: 0,
          total_cost_usd: 0,
          usage: {},
        };
      },
    };
  };
  const prev: Record<string, string | undefined> = {};
  for (const [k, v] of Object.entries(env)) {
    prev[k] = process.env[k];
    if (v === undefined) delete process.env[k];
    else process.env[k] = v;
  }
  try {
    const session = new ClaudeAgentSession({
      model: { id: "test-model", provider: "test" },
      allowedTools: ["Bash"],
      queryFn,
    });
    const events: AnyEvent[] = [];
    session.on("event", (ev: unknown) => events.push(ev as AnyEvent));
    const done = new Promise<number | null>((resolve) => session.once("exit", resolve));
    session.start();
    session.sendUserMessage("test prompt");
    session.closeInput();
    const code = await done;
    assert.equal(code, 0, "capture session must exit cleanly");
    assert.ok(events.some((e) => e.type === "result"), "result event delivered");
    return captured;
  } finally {
    for (const [k, v] of Object.entries(prev)) {
      if (v === undefined) delete process.env[k];
      else process.env[k] = v;
    }
  }
}

test("T1.2 hooks: absent by default on the budgeted path (gates default off after same-day eval)", async () => {
  const cap = await runCapture({
    ADA_RUNNER_TIMEOUT_MS: "60000",
    ADA_DEADLINE_MARGIN_MS: "5000",
    ADA_TIME_HINTS: undefined,
    ADA_BASH_CLAMP_REMAINING: undefined,
  });
  assert.equal(cap.options?.hooks, undefined, "no hooks unless a gate is opted in");
});

test("T1.2 hooks: PostToolBatch hook returns the remaining-time hint", async () => {
  const cap = await runCapture({
    ADA_RUNNER_TIMEOUT_MS: "60000",
    ADA_TIME_HINTS: "1",
    ADA_BASH_CLAMP_REMAINING: "1",
    ADA_DEADLINE_MARGIN_MS: "5000",
  });
  const cb = cap.options!.hooks!.PostToolBatch![0].hooks[0] as (
    input: unknown,
  ) => Promise<{ hookSpecificOutput: { hookEventName: string; additionalContext: string } }>;
  const out = await cb({});
  assert.equal(out.hookSpecificOutput.hookEventName, "PostToolBatch");
  assert.ok(
    /^⏱ \d+ s of 60 s remain\./.test(out.hookSpecificOutput.additionalContext),
    `hint text: ${out.hookSpecificOutput.additionalContext}`,
  );
});

test("T1.2 hooks: PreToolUse hook clamps an oversized Bash timeout to remaining-20s", async () => {
  const cap = await runCapture({
    ADA_RUNNER_TIMEOUT_MS: "60000",
    ADA_TIME_HINTS: "1",
    ADA_BASH_CLAMP_REMAINING: "1",
    ADA_DEADLINE_MARGIN_MS: "5000",
  });
  const cb = cap.options!.hooks!.PreToolUse![0].hooks[0] as (
    input: unknown,
  ) => Promise<Record<string, unknown>>;
  // Requested 300 s with ~55 s remaining (60 s budget − 5 s margin), margin
  // 20 s → cap ≈ 35 s. Allow scheduling slack but demand a real clamp.
  const out = (await cb({ tool_input: { command: "sleep 300", timeout: 300000 } })) as {
    hookSpecificOutput?: {
      updatedInput?: { timeout?: number; command?: string };
      additionalContext?: string;
    };
  };
  assert.ok(out.hookSpecificOutput, "clamp applied");
  const t = out.hookSpecificOutput!.updatedInput!.timeout!;
  assert.ok(t >= 20_000 && t <= 40_000, `clamped timeout in [20000,40000], got ${t}`);
  assert.equal(out.hookSpecificOutput!.updatedInput!.command, "sleep 300");
  assert.ok(out.hookSpecificOutput!.additionalContext!.includes("clamped"));
});

test("T1.2 hooks: PreToolUse hook returns {} when the timeout already fits", async () => {
  const cap = await runCapture({
    ADA_RUNNER_TIMEOUT_MS: "60000",
    ADA_TIME_HINTS: "1",
    ADA_BASH_CLAMP_REMAINING: "1",
    ADA_DEADLINE_MARGIN_MS: "5000",
  });
  const cb = cap.options!.hooks!.PreToolUse![0].hooks[0] as (
    input: unknown,
  ) => Promise<Record<string, unknown>>;
  const out = await cb({ tool_input: { command: "echo hi", timeout: 5000 } });
  assert.deepEqual(out, {}, "no clamp output when the requested timeout fits");
});

test("T1.2 hooks: absent on the legacy no-budget path (identical to pre-T1.2)", async () => {
  const cap = await runCapture({
    ADA_RUNNER_TIMEOUT_MS: undefined,
    ADA_FINISH_TIME: undefined,
    ADA_TIME_HINTS: "1",
    ADA_BASH_CLAMP_REMAINING: "1",
  });
  assert.equal(cap.options?.hooks, undefined, "no hooks without a declared budget");
});

test("T1.2 hooks: each gate independently removes its hook", async () => {
  const noHints = await runCapture({
    ADA_RUNNER_TIMEOUT_MS: "60000",
    ADA_BASH_CLAMP_REMAINING: "1",
    ADA_TIME_HINTS: "0",
  });
  assert.ok(noHints.options!.hooks, "hooks object still present (clamp on)");
  assert.equal(noHints.options!.hooks!.PostToolBatch, undefined, "no PostToolBatch");
  assert.ok(noHints.options!.hooks!.PreToolUse, "PreToolUse still present");

  const noClamp = await runCapture({
    ADA_RUNNER_TIMEOUT_MS: "60000",
    ADA_TIME_HINTS: "1",
    ADA_BASH_CLAMP_REMAINING: "0",
  });
  assert.ok(noClamp.options!.hooks!.PostToolBatch, "PostToolBatch still present");
  assert.equal(noClamp.options!.hooks!.PreToolUse, undefined, "no PreToolUse");

  const bothOff = await runCapture({
    ADA_RUNNER_TIMEOUT_MS: "60000",
    ADA_TIME_HINTS: "0",
    ADA_BASH_CLAMP_REMAINING: "0",
  });
  assert.equal(bothOff.options?.hooks, undefined, "no hooks key when both gates are off");
});

test("T1.2 hooks: ADA_DEADLINE_ANCHOR=runner is honored (hooks still built, run clean)", async () => {
  const cap = await runCapture({
    ADA_RUNNER_TIMEOUT_MS: "60000",
    ADA_TIME_HINTS: "1",
    ADA_BASH_CLAMP_REMAINING: "1",
    ADA_DEADLINE_MARGIN_MS: "5000",
    ADA_DEADLINE_ANCHOR: "runner",
  });
  assert.ok(cap.options?.hooks?.PostToolBatch, "hooks present with runner anchor");
  assert.ok(cap.options?.hooks?.PreToolUse, "PreToolUse present with runner anchor");
});

test("T1.2 hooks: ADA_WRAP_UP_MS drives the wrap-up sentence in the hint", async () => {
  // Budget 60 s, wrap-up window forced to 200 s → remaining (~55 s) is inside
  // the window, so the wrap-up directive must appear immediately.
  const cap = await runCapture({
    ADA_RUNNER_TIMEOUT_MS: "60000",
    ADA_TIME_HINTS: "1",
    ADA_BASH_CLAMP_REMAINING: "1",
    ADA_DEADLINE_MARGIN_MS: "5000",
    ADA_WRAP_UP_MS: "200000",
  });
  const cb = cap.options!.hooks!.PostToolBatch![0].hooks[0] as (
    input: unknown,
  ) => Promise<{ hookSpecificOutput: { additionalContext: string } }>;
  const out = await cb({});
  assert.ok(out.hookSpecificOutput.additionalContext.includes("Time is nearly up"));
  // And with the default wrap-up (min(150s, max(60s, 0.2*60s)) = 60 s) the
  // same ~55 s remaining is ALSO inside the window at this small budget, so
  // assert the plain hint prefix regardless.
  const cap2 = await runCapture({
    ADA_RUNNER_TIMEOUT_MS: "60000",
    ADA_TIME_HINTS: "1",
    ADA_BASH_CLAMP_REMAINING: "1",
    ADA_DEADLINE_MARGIN_MS: "5000",
  });
  const cb2 = cap2.options!.hooks!.PostToolBatch![0].hooks[0] as typeof cb;
  const out2 = await cb2({});
  assert.ok(out2.hookSpecificOutput.additionalContext.startsWith("⏱"));
});
