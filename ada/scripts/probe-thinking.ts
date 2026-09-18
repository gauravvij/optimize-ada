/**
 * T0.2 Thinking-suppression probe (fina_run.md §2 T0.2) — decides T1.3.
 *
 * NOT under agent/ — not part of any candidate; a measurement script only.
 * Needs OPENROUTER_API_KEY in the environment.
 *
 * Layer A — raw HTTP: POST https://openrouter.ai/api/v1/messages
 *   (headers x-api-key + anthropic-version: 2023-06-01), model
 *   z-ai/glm-5.3-flash, max_tokens 256, prompt "What is 17*23? Reply with
 *   the number only." × 3 runs × 5 variants:
 *     (i)   none
 *     (ii)  thinking:{type:"disabled"}
 *     (iii) thinking:{type:"enabled",budget_tokens:1024}
 *     (iv)  output_config:{effort:"low"}
 *     (v)   reasoning:{enabled:false}   (OpenRouter-native)
 *   Record wall latency, the whole usage object, content block types, then
 *   GET https://openrouter.ai/api/v1/generation?id=<response.id> (Bearer)
 *   → native_tokens_reasoning / native_tokens_completion / latency.
 *   That endpoint is ground truth. (Known caveat: it may return no history
 *   for this key; we record whatever it gives and fall back to the
 *   response's own usage fields.)
 *
 * Layer B — SDK: query() from @astropods/adapter-claude-agent-sdk with
 *   claudeSpawnEnv(resolveModel()), settingSources: [],
 *   includePartialMessages: true, prompt "Run `echo hi` with Bash, then
 *   reply DONE"; variants none / thinking:{type:"disabled"} / effort:"low".
 *   Sum thinking_delta chars, count system/thinking_tokens events, read
 *   result.modelUsage.thinkingTokens, wall time.
 *
 * Decision rule (recorded, applied by hand in fina_run.md '## Probe results'):
 *   (ii) or (iv) gives reasoning ≈0 and lower latency → T1.3 goes live with
 *   that option. Only (v) works → CLAUDE_CODE_EXTRA_BODY in childEnv under
 *   the same gate + re-check with Layer B. Nothing works → drop T1.3.
 *
 * Run: cd ada && OPENROUTER_API_KEY=... /usr/local/bin/node scripts/probe-thinking.ts
 */

import { claudeSpawnEnv, resolveModel } from "../agent/config/model.ts";

const MODEL = "z-ai/glm-5.3-flash";
const API_BASE = "https://openrouter.ai/api";
const KEY = process.env.OPENROUTER_API_KEY ?? process.env.ANTHROPIC_API_KEY ?? "";
if (!KEY) {
  console.error("probe-thinking: OPENROUTER_API_KEY is not set");
  process.exit(1);
}

const LAYER_A_PROMPT = "What is 17*23? Reply with the number only.";
const LAYER_B_PROMPT = "Run `echo hi` with Bash, then reply DONE";

interface Variant {
  name: string;
  body: Record<string, unknown>;
}

const LAYER_A_VARIANTS: Variant[] = [
  { name: "i-none", body: {} },
  { name: "ii-thinking-disabled", body: { thinking: { type: "disabled" } } },
  { name: "iii-thinking-budget-1024", body: { thinking: { type: "enabled", budget_tokens: 1024 } } },
  { name: "iv-effort-low", body: { output_config: { effort: "low" } } },
  { name: "v-reasoning-disabled", body: { reasoning: { enabled: false } } },
];

const LAYER_B_VARIANTS: Variant[] = [
  { name: "i-none", body: {} },
  { name: "ii-thinking-disabled", body: { thinking: { type: "disabled" } } },
  { name: "iv-effort-low", body: { effort: "low" } },
  // Supplementary: Layer A showed budget_tokens is the ONLY variant that
  // suppresses reasoning at the raw HTTP layer (41→7 thinking tokens), so
  // T1.3's budget:N option needs SDK-layer evidence too.
  { name: "iii-thinking-budget-1024", body: { thinking: { type: "enabled", budgetTokens: 1024 } } },
];

interface GenInfo {
  id?: string;
  native_tokens_reasoning?: number;
  native_tokens_completion?: number;
  native_tokens_prompt?: number;
  latency?: number;
  usage?: Record<string, unknown>;
  provider_name?: string;
  status?: string;
  error?: unknown;
}

async function postMessages(body: Record<string, unknown>) {
  const res = await fetch(`${API_BASE}/v1/messages`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-api-key": KEY,
      "authorization": `Bearer ${KEY}`,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify(body),
  });
  const text = await res.text();
  let json: any;
  try {
    json = JSON.parse(text);
  } catch {
    json = { _raw: text.slice(0, 400) };
  }
  return { status: res.status, json };
}

async function getGeneration(id: string): Promise<GenInfo | null> {
  try {
    const res = await fetch(`${API_BASE}/v1/generation?id=${encodeURIComponent(id)}`, {
      headers: { authorization: `Bearer ${KEY}` },
    });
    const text = await res.text();
    const json = JSON.parse(text);
    // OpenRouter returns {data: {...}} or a bare object depending on state.
    const data = (json && typeof json === "object" && "data" in json) ? json.data : json;
    if (!data || typeof data !== "object") return null;
    return data as GenInfo;
  } catch (err) {
    return { error: String(err) } as GenInfo;
  }
}

function blockTypes(json: any): string[] {
  const blocks = json?.content;
  if (!Array.isArray(blocks)) return [];
  return blocks.map((b: any) => `${b?.type ?? "?"}${b?.thinking ? "(thinking)" : ""}`);
}

async function layerA() {
  console.log("\n=== LAYER A: raw HTTP /v1/messages, 5 variants × 3 runs ===");
  const results: Record<string, unknown>[] = [];
  for (const v of LAYER_A_VARIANTS) {
    for (let run = 1; run <= 3; run++) {
      const body = {
        model: MODEL,
        max_tokens: 256,
        messages: [{ role: "user", content: LAYER_A_PROMPT }],
        ...v.body,
      };
      const t0 = performance.now();
      const { status, json } = await postMessages(body);
      const wallMs = Math.round(performance.now() - t0);
      if (status !== 200) {
        const row = { layer: "A", variant: v.name, run, status, error: JSON.stringify(json).slice(0, 200), wall_ms: wallMs };
        console.log(JSON.stringify(row));
        results.push(row);
        continue;
      }
      // Ground truth from the generation endpoint (may be empty for this key).
      const gen = json.id ? await getGeneration(String(json.id)) : null;
      const row = {
        layer: "A",
        variant: v.name,
        run,
        status,
        wall_ms: wallMs,
        id: json.id ?? null,
        content_blocks: blockTypes(json),
        usage: json.usage ?? null,
        stop_reason: json.stop_reason ?? null,
        text: (json.content ?? []).filter((b: any) => b?.type === "text").map((b: any) => b?.text).join(" ").slice(0, 60),
        gen_native_tokens_reasoning: gen?.native_tokens_reasoning ?? null,
        gen_native_tokens_completion: gen?.native_tokens_completion ?? null,
        gen_latency: gen?.latency ?? null,
        gen_provider: gen?.provider_name ?? null,
      };
      console.log(JSON.stringify(row));
      results.push(row);
    }
  }
  return results;
}

async function layerB() {
  console.log("\n=== LAYER B: SDK query(), 3 variants × 1 run ===");
  const model = resolveModel();
  const spawnEnv = claudeSpawnEnv(model);
  const { query } = (await import("@astropods/adapter-claude-agent-sdk")) as {
    query: (args: { prompt: string; options: unknown }) => AsyncIterable<any>;
  };
  const results: Record<string, unknown>[] = [];
  for (const v of LAYER_B_VARIANTS) {
    const options: Record<string, unknown> = {
      model: MODEL,
      env: spawnEnv,
      settingSources: [],
      includePartialMessages: true,
      allowedTools: ["Bash"],
      permissionMode: "acceptEdits",
      maxTurns: 4,
      ...v.body,
    };
    let thinkingDeltaChars = 0;
    let thinkingTokenEvents = 0;
    let resultModelUsage: unknown = null;
    let resultUsage: unknown = null;
    let sawResult = false;
    let streamError: string | null = null;
    const t0 = performance.now();
    try {
      const q = query({ prompt: LAYER_B_PROMPT, options });
      for await (const ev of q) {
        const type = ev?.type ?? "";
        if (type === "stream_event" && ev?.event?.type === "content_block_delta") {
          const d = ev.event.delta;
          if (d?.type === "thinking_delta" && typeof d.thinking === "string") {
            thinkingDeltaChars += d.thinking.length;
          }
        }
        if (type === "system" && String(ev?.subtype ?? "") === "thinking_tokens") {
          thinkingTokenEvents++;
        }
        if (type === "result") {
          sawResult = true;
          resultModelUsage = ev?.modelUsage ?? null;
          resultUsage = ev?.usage ?? null;
        }
      }
    } catch (err) {
      streamError = String(err).slice(0, 200);
    }
    const wallMs = Math.round(performance.now() - t0);
    const row = {
      layer: "B",
      variant: v.name,
      wall_ms: wallMs,
      thinking_delta_chars: thinkingDeltaChars,
      thinking_token_events: thinkingTokenEvents,
      result_model_usage: resultModelUsage,
      result_usage: resultUsage,
      saw_result: sawResult,
      stream_error: streamError,
    };
    console.log(JSON.stringify(row));
    results.push(row);
  }
  return results;
}

async function main() {
  console.log(`probe-thinking: model=${MODEL} key_len=${KEY.length}`);
  const a = await layerA();
  const b = await layerB();
  const all = [...a, ...b];
  // Summary table keyed by variant for the fina_run.md record.
  const summary: Record<string, Record<string, unknown>> = {};
  for (const r of all) {
    const key = `${r.layer}-${r.variant}`;
    if (!summary[key]) summary[key] = { layer: r.layer, variant: r.variant, runs: 0 };
    const s = summary[key];
    s.runs = (Number(s.runs) || 0) + 1;
    if (r.layer === "A") {
      s.wall_ms_list = [...((s.wall_ms_list as number[]) ?? []), r.wall_ms as number];
      if (r.gen_native_tokens_reasoning != null) {
        s.gen_reasoning_list = [...((s.gen_reasoning_list as number[]) ?? []), r.gen_native_tokens_reasoning as number];
      }
      if (r.usage) s.usage_sample = r.usage;
      if (r.status !== 200) s.all_http_ok = false;
    } else {
      s.wall_ms = r.wall_ms;
      s.thinking_delta_chars = r.thinking_delta_chars;
      s.thinking_token_events = r.thinking_token_events;
      s.result_model_usage = r.result_model_usage;
    }
  }
  console.log("\n=== SUMMARY ===");
  console.log(JSON.stringify(summary, null, 2));
}

main().catch((err) => {
  console.error("probe-thinking failed:", err);
  process.exit(1);
});