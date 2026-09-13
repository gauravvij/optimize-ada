# H2 cap-hook fix — provenance record (2025-09-04)

## Root cause (measured)

Two reach probes (h2-reach-probe, h2-reach-probe2) produced zero `[hook:cap]` log
hits. probe2 ran fully (18 turns, $0.197, large-scale-text-editing, cap=300) —
virtually every Bash result exceeds 300 chars, so 0 truncations proves the hook
never matched. SDK sdk.d.ts types `PostToolUseHookInput.tool_response` as
`unknown` (line 2468); for Bash tools the response is an OBJECT
(`{stdout, stderr, interrupted, isImage}`), not a plain string. The original
hook guarded with `typeof r === "string"` → never matched → silent no-op.
Secondary fault: the hook only logged on truncation, so reach was unprovable
when nothing exceeded the cap (H1 lesson: log every fire).

## Fix

`ada/agent/claude/agent.ts` (md5 ea5225ea34917de672f9543e80dd3fa8, mirrored to
eval/ada-runtime/ada/agent/claude/agent.ts, parity verified):
- `capString()` / `capToolResponse()` helpers: shape-aware truncation
  (head 60% + tail 25% + elision marker) for plain strings, objects with
  string fields (each oversized field truncated, non-string fields untouched,
  same shape returned), and content-block arrays ({type:"text", text}).
  Returns `undefined` when nothing exceeded the cap (output untouched).
- Per-fire reach log: `[hook:cap] PostToolUse <tool> fired (resp <shape>)`
  on every PostToolUse; separate `[hook:cap] ... truncated (cap N)` line on
  actual rewrites. Rewrite returned via
  `hookSpecificOutput.updatedToolOutput` (typed `unknown`, sdk.d.ts:2486 —
  object returns legal).

## Verification

- `tsc --noEmit`: 0 errors in agent/claude/agent.ts (pre-existing unrelated
  errors in adapter.ts/postgres.ts/telemetry unchanged).
- Unit test `eval/analysis/test_cap_hook.mjs` (imports the real module,
  Node 24 type-stripping): **13/13 PASS** —
  obj same-shape/truncated/marker/head+tail/non-string-untouched,
  string truncated, array preserved+truncated, under-cap no-rewrite,
  reach-log fired lines (4/4 calls), truncation lines (3/3 rewrites).
- kwarg→env binding (hook_output_cap → ADA_HOOK_OUTPUT_CAP): passed in prior
  cycle (recorded in cycle cdf14bf2 summary).

## Next gate

Reach probe h2-reach-probe3 (cap=300, large-scale-text-editing, k=1): bridge
log must show fired lines AND ≥1 truncation, cost ≤ $0.25.
