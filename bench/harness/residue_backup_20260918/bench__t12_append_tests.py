#!/usr/bin/env python3
"""Append T1.2 hook-gating test groups to agent/claude/agent.test.ts."""
PATH = "/home/azureuser/adaAgent/autoresearcher/targets/ada/agent/claude/agent.test.ts"

TESTS = r'''
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

test("T1.2 hooks: present by default on the budgeted path (gates default on, E13)", async () => {
  const cap = await runCapture({
    ADA_RUNNER_TIMEOUT_MS: "60000",
    ADA_DEADLINE_MARGIN_MS: "5000",
    ADA_TIME_HINTS: undefined,
    ADA_BASH_CLAMP_REMAINING: undefined,
  });
  const hooks = cap.options?.hooks;
  assert.ok(hooks, "hooks object present on the budgeted path");
  assert.ok(hooks!.PostToolBatch, "PostToolBatch hook present by default");
  assert.ok(hooks!.PreToolUse, "PreToolUse hook present by default");
  assert.equal(hooks!.PreToolUse![0].matcher, "Bash", "PreToolUse matcher is Bash");
  assert.equal(hooks!.PostToolBatch!.length, 1);
  assert.equal(hooks!.PreToolUse!.length, 1);
});

test("T1.2 hooks: PostToolBatch hook returns the remaining-time hint", async () => {
  const cap = await runCapture({
    ADA_RUNNER_TIMEOUT_MS: "60000",
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
    ADA_DEADLINE_MARGIN_MS: "5000",
  });
  const cb = cap.options!.hooks!.PreToolUse![0].hooks[0] as (
    input: unknown,
  ) => Promise<Record<string, unknown>>;
  // Requested 300 s with ~55 s remaining (60 s budget − 5 s margin), margin
  // 20 s → cap ≈ 35 s. Allow scheduling slack but demand a real clamp.
  const out = (await cb({ tool_input: { command: "sleep 300", timeout: 300000 } })) as {
    hookSpecificOutput?: { updatedInput?: { timeout?: number }; additionalContext?: string };
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
    ADA_TIME_HINTS: "0",
  });
  assert.ok(noHints.options!.hooks, "hooks object still present (clamp on)");
  assert.equal(noHints.options!.hooks!.PostToolBatch, undefined, "no PostToolBatch");
  assert.ok(noHints.options!.hooks!.PreToolUse, "PreToolUse still present");

  const noClamp = await runCapture({
    ADA_RUNNER_TIMEOUT_MS: "60000",
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
    ADA_DEADLINE_MARGIN_MS: "5000",
  });
  const cb2 = cap2.options!.hooks!.PostToolBatch![0].hooks[0] as typeof cb;
  const out2 = await cb2({});
  assert.ok(out2.hookSpecificOutput.additionalContext.startsWith("⏱"));
});
'''

with open(PATH, encoding="utf-8") as f:
    src = f.read()

assert src.count("export class") == 0, "unexpected class in test file"
assert "Group 6 (T1.2)" not in src, "T1.2 tests already appended"

with open(PATH, "a", encoding="utf-8") as f:
    f.write(TESTS)

print("OK: T1.2 test groups appended")