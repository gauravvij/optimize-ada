/**
 * Durable per-session trace: every AG-UI event, one JSON object per line.
 *
 * WHY `agent/traces` AND NOT A TIDIER `ada/traces`: under `ast project start`
 * the container's ONLY host bind mount is `ada/agent -> /app/agent` (verify with
 * `docker inspect ...-agent-1 --format '{{range .Mounts}}...'`). A file written
 * anywhere else lands in the container's ephemeral layer and is invisible to
 * host-side readers. Resolving relative to THIS module keeps one path correct in
 * both run modes (host `npm start` and the container). Override with ADA_TRACE_DIR.
 *
 * Consumers (e.g. the autoresearcher) can tail `<sessionId>.jsonl` while a run is
 * live — lines are appended in seq order and each is independently parseable.
 */

import { appendFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

export const TRACE_DIR =
  process.env.ADA_TRACE_DIR ?? join(dirname(fileURLToPath(import.meta.url)), "..", "traces");

mkdirSync(TRACE_DIR, { recursive: true });

let warned = false;

/**
 * Append one event. NEVER throws: a trace-write failure (full disk, read-only
 * mount) must not kill a live run, so it degrades to a single stderr warning.
 *
 * ponytail: appendFileSync preserves event order without a write queue. At one
 * line per AG-UI event that cost is noise; switch to a WriteStream per session
 * if traces ever show up in run latency.
 */
export function writeTrace(sessionId: string, seq: number, event: unknown): void {
  try {
    appendFileSync(
      join(TRACE_DIR, `${sessionId}.jsonl`),
      JSON.stringify({ seq, ts: new Date().toISOString(), event }) + "\n",
      "utf8",
    );
  } catch (err) {
    if (!warned) {
      warned = true;
      console.error(`[trace] disabled — cannot write to ${TRACE_DIR}:`, (err as Error).message);
    }
  }
}
