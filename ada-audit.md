# Ada — Architecture Audit, Profiling & Optimization Guide

Repo: https://github.com/rabbah/ada (cloned to `/root/optimize_ada/ada`)
Audit date: 2026-09-02 · ~4,700 LOC TypeScript, Node ≥23 (type-stripping, no build step)

---

## 1. How It Works

Ada is a **supervisory bridge around Claude Code**, not an agent loop of its own. All intelligence lives in the `claude` CLI child process; Ada owns everything *around* it: sessions, workspaces, auth, transport, telemetry, and cost accounting.

### The pipeline (one turn)

```
Client (browser / Slack / web chat)
   │  POST /sessions {prompt}            (browser)      or gRPC message (sidecar)
   ▼
agent/index.ts  ── startSession()/continueSession()
   │   mints bridgeId, creates per-session workspace (mkdtemp), resolves
   │   GitHub OAuth token for the user (Postgres store, refresh if expiring)
   ▼
runTurn()  ──►  ClaudeAgentSession (agent/claude/agent.ts)
   │   wraps Claude Agent SDK query()  → spawns `claude` child process
   │   - sandboxed env: allowlist-only passthrough (PATH/HOME/TZ/proxy/Go+npm
   │     cache vars) + ANTHROPIC_* + per-user GH_TOKEN. Host secrets dropped.
   │   - resume: prior Claude session_id → multi-turn context
   │   - lean startup: settingSources:[], skills:[], mcpServers:{} (no FS scan)
   │   - tool policy: allowedTools auto-approve (Read/Edit/Write/Bash/Grep/Glob)
   │     + disallowedTools deny-list (WebSearch, WebFetch, Task, Workflow, …)
   ▼
stream-json events (system/init, assistant, user, stream_event, result)
   │   fanned out to three independent consumers:
   ├──► Translator (translate/translator.ts)  → AG-UI events
   │        system/init → RUN_STARTED + STATE_SNAPSHOT
   │        content_block_* → TEXT_MESSAGE_* / TOOL_CALL_* (partials 1:1)
   │        user tool_result → TOOL_CALL_RESULT
   │        result → RUN_FINISHED / RUN_ERROR
   ├──► Telemetry (telemetry/otel.ts) → OTel GenAI spans + token/cost metrics
   │        (root span per turn, child span per tool call, cost histogram)
   └──► SessionRegistry (session/registry.ts) → per-session monotonic-seq
            event log → SSE with Last-Event-ID replay = lossless reconnect
   ▼
SSE stream (GET /sessions/:id/events)  →  AG-UI client / CopilotKit / Slack
```

On `result`, Ada appends a `CUSTOM claude.usage` event (input/output/cache tokens + `total_cost_usd`) so the client can display per-turn and session-total cost.

### Key architectural seams

| Seam | File | What it isolates |
|---|---|---|
| Model/auth/gateway | `agent/config/model.ts` | Model id, pricing table, direct-vs-gateway (Bifrost `x-bf-vk` header, `bedrock/`-prefixed ids, beta-flag stripping). The ONLY file to change to swap providers. |
| Event source | `agent/claude/agent.ts` vs `supervisor.ts` | SDK `query()` (default, typed) vs hand-spawned `claude -p` NDJSON (fallback). Same EventEmitter surface. |
| Translation | `agent/translate/translator.ts` | Pure, I/O-free, unit-testable stream-json → AG-UI mapping. |
| Session state | `agent/session/registry.ts` | In-memory event log + pub/sub; transport-agnostic. |
| Execution | `sandbox/index.ts` | Optional separate sandbox container (control plane ↔ sandbox over HTTP/SSE); sandbox has zero access to DB/tokens/secrets. |
| Concurrency | `agent/concurrency.ts` | FIFO semaphore, `MAX_CONCURRENT_RUNS` (default 3) + `SANDBOX_MAX_CONCURRENT` in the sandbox. |

### Deployment modes

1. **Local**: `node agent/index.ts` → test client at :8080. Needs `ANTHROPIC_API_KEY` + `claude` CLI for live runs; `npm run demo` needs nothing.
2. **Astropods/K8s**: `frontend: true` (port 80) + `messaging: true` (sidecar gRPC → Slack/web chat) + `astro_ai_gateway: true` (Bedrock-backed Bifrost gateway with virtual keys).
3. **Sandboxed split**: control plane calls `sandbox/index.ts` over HTTP; raw stream-json relayed over SSE with 15s heartbeats (works around undici's ~5m idle body timeout).

---

## 2. What It Is Capable Of

**Working today:**
- Multi-turn coding sessions with context resume (Claude session_id mapping per bridge session)
- Streaming AG-UI events over SSE with lossless reconnect (Last-Event-ID replay)
- Slack + web chat via the platform messaging sidecar; per-thread isolation (own workspace, repo checkout, session); superseded-message abort (`source.stop()`)
- Per-user GitHub App OAuth (App-Manifest provisioning flow, install-based connect, token refresh, `GH_TOKEN` injection, git credential helper via `gh`) → authenticated clone/push/PR work
- Repo binding per thread (`work on owner/repo` directive)
- Cost/usage accounting: prefers Claude's `result.total_cost_usd`, falls back to a pinned pricing table; surfaced as replayable `claude.usage` events
- OTel GenAI-semconv traces + metrics (tool spans, token counters, cost histogram), user-attributed via a parent span (`langfuse.user.id`)
- Conversation review UI (admin-gated `/conversations`)
- Deliberate tool restriction for cost/predictability (no WebSearch/WebFetch/Task/Workflow/sub-agents)
- Lean child startup (no skills/MCP/CLAUDE.md scanning) to cut cold-start and memory

**Known gaps (self-declared SCAFFOLD TODOs):**
- In-memory session registry: unbounded, no TTL/GC, no disk spill → memory growth + lost sessions on restart
- `pendingStates` OAuth CSRF map: no TTL/GC
- Cookie not signed (`bridge_uid` spoofable), tokens not encrypted at rest
- No SSE backpressure handling
- No MQ transport

**Constraints:**
- Sandbox container ceiling ~1 GiB / 100m CPU → OOM risk on large builds (mitigated via baked Go + `GOMEMLIMIT`/`GOMAXPROCS`, npm/pip cache dirs on /data)
- `claude` CLI version unpinned by default (`CLAUDE_CODE_VERSION=latest`) — the stream-json contract is explicitly not stable across releases
- Default model `claude-opus-4-8` (premium tier) — expensive default

---

## 3. Profiling for a Baseline

Ada already emits nearly everything a baseline needs; the work is *capturing and structuring* it. Three layers:

### Layer 1 — Deterministic, no credentials (validated in this audit)

`npm run demo` runs the recorded read→edit→report fixture through the real Translator and prints the AG-UI event list, SSE frames, and a cost summary. This is the **regression baseline for the translation layer**: 23 events, exact ordering, exact wire frames. Any translator change must reproduce this byte-for-byte (modulo ids). The repo also has Playwright e2e tests (`client-*.spec.ts`, `server-sse.spec.ts`) and a CI workflow (`.github/workflows/e2e.yml`) — run `npx playwright test` for the transport/session baseline.

### Layer 2 — Live-run telemetry (the real baseline)

Per turn, capture from the `result` event + `claude.usage` CUSTOM event:

| Metric | Source | Why |
|---|---|---|
| `total_cost_usd` / computed fallback | result event | Cost per turn, per session, per user |
| input/output/cache-read/cache-write tokens | result usage | Token efficiency; cache-hit ratio is the #1 cost lever |
| Turn count (agent loop iterations) | count of assistant events | Fewer turns = fewer round trips = cheaper + faster |
| Tool invocations by name | OTel tool counter / user tool_result events | Which tools dominate; tool_result size → context bloat |
| Wall-clock per turn, time-to-first-token | timestamps of RUN_STARTED vs first TEXT_MESSAGE_CONTENT | Latency baseline |
| `claude.api_retry` CUSTOM events | translator | Gateway/API instability signal |
| Error rate (`is_error` results) | result events | Reliability baseline |
| Child RSS / event-loop lag | process metrics (needs adding — see gaps) | Resource baseline under the 1 GiB ceiling |

**How to run it:** set `OTEL_EXPORTER_OTLP_ENDPOINT` (+ `BRIDGE_SELF_TELEMETRY=1`, `OTEL_METRICS_ENABLED=1` for wrapper-level spans) and point at any OTLP collector (Jaeger/Langfuse/Grafana). Ada's OTel sink already emits GenAI-semconv traces and metrics; the SDK adapter adds OpenInference spans per query/tool/model call. Alternatively — no collector needed — log the `claude.usage` events straight out of the SSE stream and aggregate offline.

**Benchmark task set:** define ~10–20 fixed prompts (read-only Q&A, small edit, multi-file refactor, repo onboarding via `work on`, a build+fix loop) and run them against a pinned `CLAUDE_CODE_VERSION` and pinned model id. Record cost, tokens, turns, tools, latency per task. That table is the baseline every optimization is measured against.

### Layer 3 — Load/soak profiling

- Concurrency: N parallel sessions vs `MAX_CONCURRENT_RUNS` — measure queue wait (semaphore `stats()`), child memory, and whether the 1 GiB ceiling holds
- Soak: long-running session with many turns → watch registry log growth (unbounded today), workspace disk usage, `pendingStates` growth
- Reconnect: kill SSE mid-run, reconnect with Last-Event-ID, verify zero-loss replay (the e2e specs already assert parts of this)

---

## 4. How to Optimize It

Ordered by leverage (cost/quality first, then resource, then robustness). Each item notes the exact seam.

### A. Cost (usually the dominant lever)

1. **Right-size the default model.** Default is `claude-opus-4-8` ($5/$25 per Mtok). Most coding turns (read/edit/report, small fixes) are sonnet-class work. Set `ANTHROPIC_MODEL=claude-sonnet-5` ($3/$15) as the default and keep opus opt-in per session; or route by task type at `resolveModel()`. This is a one-env-var change at the isolated seam (`config/model.ts`) — no code changes. Expected: ~40–70% cost reduction on typical turns with negligible quality loss for routine edits. Validate against the Layer-2 baseline before/after.
2. **Exploit prompt caching.** Resume already reuses the Claude session, but check `cache_read_input_tokens` share in the baseline. If low: keep system prompt + tool definitions stable across turns (they are), avoid `systemPromptAppend` churn, and prefer continuing a session over starting new ones (the UI already does this). Cache reads are 10% of input price — a high cache-hit ratio is the cheapest optimization available.
3. **Trim tool_result content into context.** Large tool outputs (file dumps, build logs) flow back into the model's context and get re-billed every subsequent turn. Consider capping/summarizing oversized tool results at the translator or via the SDK's context-management options. Measure with the tool-result-size metric from Layer 2.
4. **Keep the deny-list tight.** `Task`/`Workflow` (sub-agent cost multipliers) and `WebSearch`/`WebFetch` are already removed — good. Audit the allowlist: `Bash` auto-approve is the riskiest (arbitrary commands); consider splitting into a safer set for untrusted users.

### B. Latency

5. **Time-to-first-token**: the lean startup (`settingSources: []`, no MCP/skills scan) is already the big win. Remaining cold-start cost is the `claude` child spawn itself (~1–3s). If turns are frequent, a warm pool of children is possible but complex; measure first — TTFT is likely dominated by model API latency, not spawn.
6. **Queueing under load**: with `MAX_CONCURRENT_RUNS=3`, the 4th+ session waits invisibly. Surface `runLimiter.stats()` (available/queued) as a CUSTOM event or `/health` field so clients see queue position instead of silence.

### C. Resource / stability (the 1 GiB ceiling)

7. **Bound the session registry.** Today: unbounded in-memory log per session, no GC. Add a ring buffer cap + spill-to-disk (or Redis) and TTL eviction of terminated sessions. This is the biggest production-readness gap and a memory-leak class bug under soak. The registry is transport-agnostic and well-isolated (`session/registry.ts`) — the change is contained.
8. **GC the `pendingStates` map** (OAuth CSRF nonces): trivial TTL sweep, same pattern as `startWorkspaceGc()`.
9. **Pin `CLAUDE_CODE_VERSION`** in the Dockerfile (default is `latest`). The repo's own #1 pin rule says the stream-json contract is unstable across releases — an unpinned CLI is a silent-corruption risk for the Translator. Pin it and bump deliberately with the demo/e2e suite as the gate.
10. **Sandbox memory**: Go/npm/pip tuning is already baked in. If builds still OOM at 1 GiB, the durable fix is platform-side (bump the ceiling) or moving builds to the sandbox container rather than the agent pod.

### D. Security hardening (flagged, not urgent for perf)

11. Sign the `bridge_uid` cookie (spoofable identity today — the code has a TODO).
12. Encrypt GitHub tokens at rest in Postgres.
13. Add SSE backpressure handling (a slow client currently can't stall the source, but writes are unbounded-buffered).

### Suggested optimization sequence

1. Pin CLI version + model id (config-only, zero risk)
2. Capture Layer-2 baseline on the benchmark task set
3. Switch default model to sonnet-class → re-run baseline → compare cost/quality
4. Bound the registry + GC pendingStates (stability)
5. Re-measure cache-hit ratio and tool-result sizes → context trimming if warranted
6. Load/soak test at target concurrency → tune `MAX_CONCURRENT_RUNS`

---

## Verification performed in this audit

- Repo cloned and all core modules read (`index.ts`, `claude/agent.ts`, `config/model.ts`, `translate/translator.ts`, `session/registry.ts`, `session/workspace.ts`, `concurrency.ts`, `sandbox/index.ts`, `messaging/adapter.ts`, `telemetry/otel.ts`, `Dockerfile`, `astropods.yml`, `package.json`)
- `npm run demo` executed successfully with zero dependencies and no API key — the full stream-json → AG-UI → SSE → cost-summary pipeline validated end-to-end (23 events, correct ordering, cost accounting from both `total_cost_usd` and the pricing-table fallback)
