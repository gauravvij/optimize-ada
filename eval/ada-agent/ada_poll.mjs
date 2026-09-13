/**
 * Ada bridge poller — runs INSIDE the task container (node 24, no deps).
 *
 * 1. Reads the task prompt from ADA_PROMPT_FILE.
 * 2. POSTs it to the running Ada bridge /sessions (with cwd=/app so the claude
 *    child works on the task's files).
 * 3. Polls the SSE event stream until RUN_FINISHED or RUN_ERROR.
 * 4. DELETEs the session (bridge state hygiene for long campaigns).
 * 5. Prints a summary JSON on stdout; writes the full event log to
 *    ADA_EVENTS_FILE (one JSON per event) for post-run trace mining.
 *
 * Exit codes: 0 = finished (RUN_FINISHED), 2 = session POST failed,
 *             3 = timeout / RUN_ERROR (summary still printed on stdout).
 */
import fs from "node:fs";

const BASE = process.env.ADA_BASE || "http://localhost:8090";
const prompt = fs.readFileSync(process.env.ADA_PROMPT_FILE, "utf8");
const cwd = process.env.ADA_CWD || "/app";
const permissionMode = process.env.ADA_PERMISSION_MODE || "bypassPermissions";
const timeoutMs = parseInt(process.env.ADA_TIMEOUT_MS || "3600000", 10);
const eventsFile = process.env.ADA_EVENTS_FILE || "/logs/agent/ada-events.jsonl";

function parseFrame(frame) {
  let seq = -1;
  let data = null;
  for (const line of frame.split("\n")) {
    if (line.startsWith("id: ")) seq = parseInt(line.slice(4), 10);
    else if (line.startsWith("data: ")) {
      try { data = JSON.parse(line.slice(6)); } catch { /* skip */ }
    }
  }
  return data ? { seq, data } : null;
}

// --- 1. start the session -------------------------------------------------
let sessionId = null;
try {
  const post = await fetch(`${BASE}/sessions`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ prompt, cwd, permissionMode }),
  });
  if (post.status !== 201) {
    console.error(`[poller] session POST failed: ${post.status} ${await post.text()}`);
    process.exit(2);
  }
  sessionId = (await post.json()).sessionId;
} catch (e) {
  console.error(`[poller] bridge unreachable: ${e.message}`);
  process.exit(2);
}
process.stderr.write(`[poller] session ${sessionId} started\n`);

// --- 2. poll the SSE stream until terminal --------------------------------
const events = [];
let last = -1;
let terminal = null;
const deadline = Date.now() + timeoutMs;

outer: while (!terminal && Date.now() < deadline) {
  const ctrl = new AbortController();
  const killTimer = setTimeout(() => ctrl.abort(), 15000);
  try {
    const resp = await fetch(`${BASE}/sessions/${sessionId}/events?lastEventId=${last}`, {
      signal: ctrl.signal,
      headers: { accept: "text/event-stream" },
    });
    if (resp.status !== 200) {
      console.error(`[poller] events stream returned ${resp.status}`);
      break;
    }
    const reader = resp.body.getReader();
    const dec = new TextDecoder();
    let buf = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let idx;
      while ((idx = buf.indexOf("\n\n")) >= 0) {
        const frame = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        const ev = parseFrame(frame);
        if (!ev) continue;
        last = ev.seq;
        events.push(ev);
        if (ev.data?.type === "RUN_FINISHED" || ev.data?.type === "RUN_ERROR") {
          terminal = ev.data;
          break outer;
        }
      }
    }
  } catch {
    // aborted by the 15s timer or connection dropped — reconnect and resume
  } finally {
    clearTimeout(killTimer);
  }
}

// --- 3. summarize + cleanup -----------------------------------------------
// Usage: RUN_FINISHED.rawEvent is authoritative (usage + total_cost_usd);
// the claude.usage CUSTOM event is appended AFTER RUN_FINISHED, so it may not
// arrive before we stop polling — use it only as a fallback.
const raw = terminal?.rawEvent || null;
let usage = null;
if (raw?.usage) {
  usage = {
    inputTokens: raw.usage.input_tokens ?? 0,
    outputTokens: raw.usage.output_tokens ?? 0,
    cacheReadTokens: raw.usage.cache_read_input_tokens ?? 0,
    cacheCreationTokens: raw.usage.cache_creation_input_tokens ?? 0,
    costUsd: raw.total_cost_usd ?? null,
    costSource: "reported",
  };
} else {
  const usageEvents = events.filter(
    (e) => e.data?.type === "CUSTOM" && e.data?.name === "claude.usage",
  );
  usage = usageEvents.length ? usageEvents[usageEvents.length - 1].data.value : null;
}
const toolCalls = {};
for (const e of events) {
  if (e.data?.type === "TOOL_CALL_START") {
    const n = e.data.toolCallName || "unknown";
    toolCalls[n] = (toolCalls[n] || 0) + 1;
  }
}

const summary = {
  sessionId,
  finished: terminal?.type === "RUN_FINISHED",
  result: terminal?.result ?? null,
  error:
    terminal?.type === "RUN_ERROR"
      ? (terminal.message || terminal.rawEvent?.result || "run error")
      : terminal ? null : "poller timeout",
  usage,
  rawEvent: raw
    ? {
        num_turns: raw.num_turns,
        ttft_ms: raw.ttft_ms,
        duration_ms: raw.duration_ms,
        total_cost_usd: raw.total_cost_usd,
        is_error: raw.is_error,
        subtype: raw.subtype,
      }
    : null,
  toolCalls,
  nEvents: events.length,
};

try {
  fs.writeFileSync(eventsFile, events.map((e) => JSON.stringify(e)).join("\n") + "\n");
} catch (e) {
  process.stderr.write(`[poller] events write failed: ${e.message}\n`);
}

console.log(JSON.stringify(summary));

// Best-effort session cleanup — keeps the in-memory registry from growing
// across a long campaign. Safe with explicit cwd: the bridge never owns /app.
try {
  await fetch(`${BASE}/sessions/${sessionId}`, { method: "DELETE" });
} catch { /* best-effort */ }

process.exit(terminal?.type === "RUN_FINISHED" ? 0 : 3);
