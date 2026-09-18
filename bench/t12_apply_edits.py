#!/usr/bin/env python3
"""T1.2 wiring edits for agent/claude/agent.ts (fina_run.md §2 T1.2).

Three surgical, anchor-exact replacements:
  A) insert the deadline-anchor block + T1.2 gate constants above `const options = {`
  B) insert the gated PostToolBatch / PreToolUse hooks into the options literal
  C) remove the now-duplicated deadline block inside withUserTrace

Verifies each anchor occurs exactly once before replacing, and validates the
result afterwards (single class export, expected line-count delta).
"""
import sys

# Historical one-shot edit script (T1.2 wiring, now committed at 2e495bb in ada/).
# Path repointed to the canonical repo during final packaging 2026-09-18.
PATH = "/home/azureuser/adaAgent/ada/agent/claude/agent.ts"

with open(PATH, encoding="utf-8") as f:
    src = f.read()

def replace_once(src: str, anchor: str, replacement: str, label: str) -> str:
    n = src.count(anchor)
    if n != 1:
        print(f"FAIL: anchor {label!r} occurs {n} times (expected 1)")
        sys.exit(1)
    return src.replace(anchor, replacement, 1)

# --- Edit A: deadline anchor + T1.2 gates above the options literal ---------
anchor_a = """    const abortController = new AbortController();

    const options = {"""
block_a = """    const abortController = new AbortController();

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
    const timeHintsOn = (process.env.ADA_TIME_HINTS ?? "1") === "1";
    const bashClampOn = (process.env.ADA_BASH_CLAMP_REMAINING ?? "1") === "1";
    const clampMarginMs = Number(process.env.ADA_BASH_CLAMP_MARGIN_MS ?? 20_000);
    const wrapUpMs = Number(
      process.env.ADA_WRAP_UP_MS ??
        Math.min(150_000, Math.max(60_000, Math.floor(0.2 * taskBudgetMs))),
    );

    const options = {"""
src = replace_once(src, anchor_a, block_a, "A: options literal preamble")

# --- Edit B: gated hooks inside the options literal -------------------------
anchor_b = """      env: childEnv,
      // DEBUG: capture the CLI's stderr — gateway/API failures (Bifrost "model"""
block_b = """      env: childEnv,
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
      // DEBUG: capture the CLI's stderr — gateway/API failures (Bifrost "model"""
src = replace_once(src, anchor_b, block_b, "B: hooks in options literal")

# --- Edit C: remove the old deadline block inside withUserTrace -------------
anchor_c = """      // Anchor the hard deadline to the CONTAINER's wall-clock start when
      // detectable. The harness force-kills at container-start + budget, but
      // this runner (and thus the watchdog) only starts after container setup
      // (input tar extract + prerunner), so a runner-anchored deadline can
      // land AFTER the harness kill on setup-heavy tasks — the exact cause of
      // the 3 force-killed timeouts in the remaining81 incumbent run. Falls
      // back to runner start when /proc is unreadable or PID 1 predates any
      // plausible task budget (bare-metal host) — previous behavior.
      const containerStartMs = containerStartedAtMs();
      const deadlineAnchorMs =
        containerStartMs !== null && Date.now() - containerStartMs <= taskBudgetMs
          ? containerStartMs
          : Date.now();
      if (containerStartMs !== null && deadlineAnchorMs === containerStartMs) {
        console.error(
          `[claude:watchdog] deadline anchored to container start ` +
            `(container setup consumed ${Date.now() - containerStartMs}ms of the budget)`,
        );
      }
      const hardDeadlineAt = deadlineAnchorMs + Math.max(0, taskBudgetMs - deadlineMarginMs);
"""
block_c = """      // (T1.2) The deadline anchor + hardDeadlineAt now live ABOVE the
      // options literal — the PostToolBatch/PreToolUse hooks need them at
      // construction time. See the T1.2 block just before `const options`.
"""
src = replace_once(src, anchor_c, block_c, "C: old deadline block removal")

with open(PATH, "w", encoding="utf-8") as f:
    f.write(src)

# --- Validation --------------------------------------------------------------
assert src.count("export class ClaudeAgentSession") == 1, "class duplicated!"
assert src.count("const options = {") == 1, "options literal duplicated!"
assert src.count("const hardDeadlineAt =") == 1, "hardDeadlineAt computed twice!"
assert src.count("PostToolBatch") >= 2, "PostToolBatch hook missing!"
assert src.count('matcher: "Bash"') == 1, "PreToolUse Bash matcher missing!"
assert "ADA_DEADLINE_ANCHOR" in src, "anchor gate missing!"
print("OK: all three edits applied and validated")
print(f"lines: {src.count(chr(10)) + 1}")