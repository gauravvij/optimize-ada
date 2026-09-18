# Final-iteration stall diagnosis (subtask 1) — evidence-based, 2026-09-10

## Premise under test

Task premise: "22 of 31 remaining81 failures are turn-0 thinking-trickle stalls
(stream trickles thinking tokens continuously, never completes turn 0, burns the
full 480s budget; NOT idle so the 120s idle watchdog never fires)."

## VERDICT: DISCONFIRMED. The 22 are not turn-0 stalls.

Cross-checked `remaining81_incumbent.json` failure_details (agent_trace_tail =
last 30 KB of `/testbed/.ada-trace.jsonl`, agent_log_tail = last 50 KB of
`/testbed/.ada.log`) for all 22 rows with `turns=0, duration>400s, timed_out=False`.

### Evidence per row (all 22)

| task | wall dur | SDK num_turns | thinking tokens | api_ms | s/turn | terminal_reason |
|---|---|---|---|---|---|---|
| cassandra-73cd2c5 | 541 | 21 | 2300 | 194610 | 9.3 | aborted_tools |
| dbsetup-mysql-3 | 482 | 23 | 3276 | 260497 | 11.3 | aborted_streaming |
| deps-amazon-cognito-saml-idp-c076c | 524 | 23 | 4067 | 250568 | 10.9 | aborted_tools |
| deps-engine-34e61 | 457 | 26 | 11963 | 403135 | 15.5 | aborted_streaming |
| deps-gatsby-plugin-intl-2b7ac | 524 | 22 | 10201 | 409934 | 18.6 | aborted_tools |
| deps-openecho-28cb7 | 626 | 15 | 2115 | 200394 | 13.4 | aborted_tools |
| deps-origen-3e2f3 | 461 | 23 | 5812 | 329793 | 14.3 | aborted_tools |
| deps-rails-6cd76 | 467 | 12 | 7795 | 342247 | 28.5 | aborted_streaming |
| deps-react-most-wanted-2e3f0 | 469 | 22 | 10749 | 409988 | 18.6 | aborted_streaming |
| deps-react-most-wanted-cbc29 | 464 | 26 | 15776 | 382617 | 14.7 | aborted_streaming |
| deps-volt-react-dashboard-3a3f3 | 468 | 22 | 6411 | 375258 | 17.1 | aborted_streaming |
| dstl-stone-soup-4b6bd37 | 533 | 15 | 1599 | 142823 | 9.5 | aborted_streaming |
| falconry-falcon-cae50da | 455 | 23 | 2431 | 241828 | 10.5 | aborted_tools |
| fsspec-filesystem_spec-3ff5fca | 499 | 22 | 2627 | 216335 | 9.8 | aborted_streaming |
| hackmdio-codimd-f00df50 | 499 | 27 | 5701 | 341746 | 12.7 | aborted_streaming |
| laramies-theharvester-e25c269 | 464 | 21 | 2538 | 199855 | 9.5 | aborted_streaming |
| lhartikk-naivechain-dfd2481 | 550 | 17 | 2222 | 144499 | 8.5 | aborted_streaming |
| monero-8468549 | 459 | 16 | 7644 | 348777 | 21.8 | aborted_streaming |
| psf-black-c204232 | 569 | 26 | 5300 | 292002 | 11.2 | aborted_streaming |
| qubvel-segmentation_models-pytorch | 464 | 13 | 1620 | 125536 | 9.7 | aborted_streaming |
| reflex-dev-reflex-8657976 | 555 | 19 | 3041 | 216836 | 11.4 | aborted_tools |
| spring-petclinic-2aa53f9 | 476 | 13 | 1255 | 135752 | 10.4 | aborted_tools |

Every one of the 22 shows: real tool calls (Bash/Edit/Read results in the trace),
12–38 completed SDK turns, and the watchdog's clean interrupt at the 450 s
hard deadline (480 s budget − 30 s margin). The grader RAN on all 22
(grader_returncode recorded) and failed them on the merits of partial work.

## Why the diagnostics say turns=0 — a metric artifact, not "no work"

Chain (verified in code):

1. `agent/claude/agent.ts` watchdog fires at the hard deadline → `q.interrupt()` →
   Claude Code emits a `result` event with `is_error: true` (subtype
   `error_during_execution`, terminal_reason `aborted_tools`/`aborted_streaming`).
2. The SDK's `readMessages` THROWS on an error result ("Claude Code returned an
   error result: [ede_diagnostic] ..."). The throw surfaces through the
   watchdog path's `winner.kind === "error"` → `throw` → `run()` rejects →
   `sendUserMessage`'s catch emits `spawnError` + `exit(1)`.
3. `examples/setupbench_ada_runner.ts` rejects its run promise on `spawnError`
   and exits 1 WITHOUT printing `ADA_RUN_RESULT=...` (the `result` variable WAS
   set — the event arrived before the throw — but the print is after the await).
4. `examples/setupbench_ada_eval.py` `parse_result(log)` finds no
   `ADA_RUN_RESULT` line → `turns = 0`, `terminal_result = False`.

**Proof that turns=0 ≠ no work: 19 of the 50 PASSED tasks also have turns=0**
(same SDK-throw artifact; their partial work satisfied the grader). turns=0
means "harness could not count turns", not "the agent did nothing".

## Corrected taxonomy of the incumbent's 31 remaining81 failures

| Mode | Count | Nature |
|---|---|---|
| Watchdog-interrupted mid-work (turns=0 artifact) | 22 | Real work for 450 s; task genuinely needs more time/turns; grader ran and failed on merit |
| Harness force-kill (timed_out=True) | 3 | microsoft-azure-pipelines-tasks-bfcd4b2, servo-e199a67, yaml-pyyaml-a2d19c0 |
| Genuine graded failures (completed runs) | 6 | e.g. bgsetup-autossh-logging (8 turns), dbsetup-redis-1 (5 turns), prometheus-bd5b2ea (19 turns) |

### The 3 timeouts — the only true trickle-adjacent evidence

- servo-e199a67 and microsoft-azure-pipelines-tasks-bfcd4b2: log tails end with
  continuous `{"subtype":"thinking_tokens","estimated_tokens":N,...}` events
  (1 token per event) — the stream WAS trickling thinking at kill time.
- Root cause of these 3: the watchdog deadline is `runner-start + (budget − 30s
  margin)`, but the harness kills at `container-start + 480s`. Container setup
  (tar extract of a large repo input + prerunner script) consumes part of the
  budget BEFORE the runner starts; when setup > ~30 s the watchdog fires after
  the harness kill → force-kill → timed_out. The watchdog banner never appears
  in servo's log tail because agent-time hadn't yet reached 450 s at wall-480 s.

## Insertion points for the trickle detector (in agent/claude/agent.ts run())

In the watchdog path of `run()`:

- **Per-request state**: reset `requestStartedAt`, `sawAssistantContent`,
  `thinkingEventCount` on each `assistant` message (a new API request begins
  after each tool_result batch); update in the consume loop where
  `handle(winner.state.value)` is called.
- **Detection criteria** (in the existing `setInterval` watchdog callback):
  `now - requestStartedAt > ADA_STALL_DETECT_MS (default 90000)` AND no assistant
  text/tool_use block seen in the current request AND only
  thinking_delta/thinking_tokens events with low cumulative token count →
  abort the stalled iterator.
- **Retry hook**: issue a new `query()` for the same prompt with thinking
  disabled (`MAX_THINKING_TOKENS=0` / `thinking: {type:'disabled'}`), up to
  `ADA_STALL_RETRIES` (default 2) retries per turn; log a
  `[claude:stall-retry]` banner to stderr.

## Honest expectation for the planned fix

The 22 complete turns every 8.5–28.5 s with tool calls. A detector requiring
">90 s on one request with only thinking tokens" never fires on them. They are
budget-limited (slow gateway: ~10–20 s/turn), not stall-limited. **Expected
conversion of the 22 by the specified trickle-retry: ≈ 0.**

The specified trickle-retry is still the correct cheap backstop for the true
trickle mode seen in the 3 force-kills (env-gated, inert by default), and the
force-kills are additionally addressable by anchoring the watchdog deadline to
wall-clock container start (or increasing the margin) so the clean interrupt
always precedes the harness kill.