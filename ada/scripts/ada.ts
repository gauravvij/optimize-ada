#!/usr/bin/env node
/**
 * Minimal CLI for a RUNNING Ada — the browser client's job, from a terminal.
 *
 *   node scripts/ada.ts "read package.json and tell me the version"
 *   node scripts/ada.ts -s sess_abc "now bump the patch version"   # same session
 *   node scripts/ada.ts --selftest                                 # parser check
 *
 * ADA_URL sets the base URL (default http://localhost:3200, the `ast project
 * start` port; use http://localhost:8080 for a host-side `npm start`).
 *
 * Assistant text -> stdout. Session id, tool calls and cost -> stderr, so
 * `node scripts/ada.ts "..." 2>/dev/null` pipes clean output into another tool.
 *
 * Why this exists: `curl -N .../events` never exits — the stream is kept open by
 * heartbeats and outlives the run — so a bare curl hangs after the answer. This
 * stops at RUN_FINISHED.
 */

import { strictEqual as eq, deepStrictEqual as deq } from "node:assert";

const BASE = (process.env.ADA_URL ?? "http://localhost:3200").replace(/\/$/, "");

interface Frame { id: number; data: string }

/** Split an SSE buffer into complete frames, returning the unconsumed tail. */
export function parseFrames(buf: string): { frames: Frame[]; tail: string } {
  const parts = buf.split("\n\n");
  const tail = parts.pop() ?? "";
  const frames: Frame[] = [];
  for (const part of parts) {
    let id = 0;
    let data = "";
    for (const line of part.split("\n")) {
      if (line.startsWith("id:")) id = Number(line.slice(3).trim());
      // Only strip the single space after "data:" — leading spaces are payload.
      else if (line.startsWith("data:")) data += line.slice(line[5] === " " ? 6 : 5);
    }
    if (data) frames.push({ id, data });
  }
  return { frames, tail };
}

async function openStream(sessionId: string, lastEventId: number) {
  const res = await fetch(`${BASE}/sessions/${sessionId}/events`, {
    headers: lastEventId > 0 ? { "Last-Event-ID": String(lastEventId) } : {},
  });
  if (!res.ok || !res.body) throw new Error(`GET events -> ${res.status} ${res.statusText}`);
  return res.body.getReader();
}

/**
 * Highest seq currently logged. The session is idle when we ask, so the replay
 * arrives in one burst and then goes quiet; treat a silent gap as "caught up".
 * Needed so a follow-up turn doesn't reprint the whole conversation.
 */
async function currentSeq(sessionId: string): Promise<number> {
  const reader = await openStream(sessionId, 0);
  const dec = new TextDecoder();
  let buf = "";
  let last = 0;
  for (;;) {
    const idle = Symbol("idle");
    const r = await Promise.race([
      reader.read(),
      new Promise<typeof idle>((res) => setTimeout(() => res(idle), 500)),
    ]);
    if (r === idle || r.done) {
      await reader.cancel().catch(() => {});
      return last;
    }
    buf += dec.decode(r.value, { stream: true });
    const { frames, tail } = parseFrames(buf);
    buf = tail;
    for (const f of frames) if (f.id) last = f.id;
  }
}

/** Stream events, printing assistant text, until the run finishes. */
async function follow(sessionId: string, fromSeq: number): Promise<void> {
  const reader = await openStream(sessionId, fromSeq);
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) return;
    buf += dec.decode(value, { stream: true });
    const { frames, tail } = parseFrames(buf);
    buf = tail;
    for (const f of frames) {
      let ev: any;
      try { ev = JSON.parse(f.data); } catch { continue; }
      switch (ev.type) {
        case "TEXT_MESSAGE_CONTENT":
          process.stdout.write(ev.delta ?? "");
          break;
        case "TOOL_CALL_START":
          process.stderr.write(`\n  · ${ev.toolCallName}\n`);
          break;
        case "RUN_FINISHED": {
          const cost = ev.rawEvent?.total_cost_usd;
          process.stdout.write("\n");
          process.stderr.write(
            `\n[done] session=${sessionId}` +
              (cost != null ? ` cost=$${cost.toFixed(5)}` : "") +
              `  turns=${ev.rawEvent?.num_turns ?? "?"}\n`,
          );
          await reader.cancel().catch(() => {});
          return;
        }
        case "RUN_ERROR":
          process.stderr.write(`\n[error] ${ev.message ?? JSON.stringify(ev)}\n`);
          await reader.cancel().catch(() => {});
          process.exitCode = 1;
          return;
      }
    }
  }
}

function selftest(): void {
  // Two complete frames plus a partial one that must survive as the tail.
  const { frames, tail } = parseFrames('id: 1\ndata: {"a":1}\n\nid: 2\ndata: {"b":2}\n\nid: 3\ndata: {"c"');
  eq(frames.length, 2);
  deq(frames.map((f) => f.id), [1, 2]);
  eq(frames[1].data, '{"b":2}');
  eq(tail, 'id: 3\ndata: {"c"');
  // A frame with no id (heartbeat-style) must not reset the running seq.
  eq(parseFrames('data: {"x":1}\n\n').frames[0].id, 0);
  // Leading spaces inside the payload are preserved.
  eq(parseFrames('data:  padded\n\n').frames[0].data, " padded");
  console.log("selftest ok");
}

async function main(): Promise<void> {
  const argv = process.argv.slice(2);
  if (argv[0] === "--selftest") return selftest();

  let session: string | undefined;
  const i = argv.findIndex((a) => a === "-s" || a === "--session");
  if (i >= 0) { session = argv[i + 1]; argv.splice(i, 2); }
  const prompt = argv.join(" ").trim();
  if (!prompt) {
    console.error('usage: node scripts/ada.ts [-s <sessionId>] "<prompt>"   (ADA_URL=' + BASE + ")");
    process.exitCode = 2;
    return;
  }

  if (session) {
    const from = await currentSeq(session);
    const res = await fetch(`${BASE}/sessions/${session}/messages`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ prompt }),
    });
    if (!res.ok) throw new Error(`POST messages -> ${res.status} ${await res.text()}`);
    await follow(session, from);
  } else {
    const res = await fetch(`${BASE}/sessions`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ prompt }),
    });
    if (!res.ok) throw new Error(`POST sessions -> ${res.status} ${await res.text()}`);
    const { sessionId } = (await res.json()) as { sessionId: string };
    process.stderr.write(`[session] ${sessionId}\n`);
    await follow(sessionId, 0);
  }
}

main().catch((err) => {
  console.error(`[ada] ${err.message}`);
  process.exitCode = 1;
});
