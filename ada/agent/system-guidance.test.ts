// T1.1 verification: ADA_PROMPT_DOD gate behavior.
// Run: /usr/local/bin/node --test agent/system-guidance.test.ts
// (from the ada tree root). Uses only node:test + dynamic imports.
//
// Gate semantics after the 2026-09-11 default flip: ADA_PROMPT_DOD defaults
// to "0" (OFF) because the T1.1 paired eval was non-positive (dev-12 2/12 vs
// 3/12, E3 smoke 0/10 — fina_run.md §6). The default path must therefore be
// byte-identical to the pre-T1.1 prompt; explicit ADA_PROMPT_DOD=1 enables
// the DOD long-horizon string.
//
// The pre-T1.1 reference (OLD) is materialized from git at the T0.1 commit
// (6672af8 "fix(agent): exit cleanly after watchdog interrupt") — the last
// commit before the T1.1 DOD change — because the live targets/ada file now
// carries the T1.1 candidate itself. system-guidance.ts has no imports, so
// the extracted copy imports standalone.

import test from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const NEW = "/home/azureuser/adaAgent/ada/agent/system-guidance.ts";
const TARGETS_ADA = "/home/azureuser/adaAgent/autoresearcher/targets/ada";
const T01_COMMIT = "6672af854dd9be6d3290d3959c74b95808d54eec";

const oldDir = mkdtempSync(join(tmpdir(), "sg-pre-t11-"));
const OLD = join(oldDir, "system-guidance.ts");
writeFileSync(
  OLD,
  execFileSync("git", ["-C", TARGETS_ADA, "show", `${T01_COMMIT}:agent/system-guidance.ts`]),
);
test.after(() => rmSync(oldDir, { recursive: true, force: true }));

/**
 * Import the module fresh with the given env applied, and compute the
 * guidance strings WHILE the env is still applied (systemGuidance() reads
 * process.env at call time, so the env must be live during the call).
 */
async function guidanceWith(
  path: string,
  env: Record<string, string | undefined>,
): Promise<{ system: string; prompt: string }> {
  const saved: Record<string, string | undefined> = {};
  for (const k of Object.keys(env)) {
    saved[k] = process.env[k];
    if (env[k] === undefined) delete process.env[k];
    else (process.env as Record<string, string>)[k] = env[k] as string;
  }
  try {
    const mod = await import(`${path}?t=${Date.now()}-${Math.random()}`);
    return {
      system: mod.systemGuidance(),
      prompt: mod.systemPromptGuidance({ configured: true, connected: true }),
    };
  } finally {
    for (const [k, v] of Object.entries(saved)) {
      if (v === undefined) delete process.env[k];
      else (process.env as Record<string, string>)[k] = v;
    }
  }
}

test("gate OFF (default, env unset): long guidance byte-identical to pre-T1.1 build", async () => {
  const a = (await guidanceWith(NEW, { ADA_RUNNER_TIMEOUT_MS: "480000", ADA_PROMPT_DOD: undefined })).system;
  const b = (await guidanceWith(OLD, { ADA_RUNNER_TIMEOUT_MS: "480000" })).system;
  assert.equal(a, b, "default long guidance must be byte-identical to the T0.1 build");
  assert.ok(!a.includes("DEFINITION OF DONE"), "DOD block must be absent by default");
  assert.ok(a.includes("Batch independent reads/greps/globs"), "old rule 1 present");
  assert.ok(a.includes("poll its log file"), "old rule 2 present");
  assert.ok(a.includes("If a check fails twice"), "old rule 3 present");
  assert.ok(a.includes("the task's own checks pass"), "old TERMINATION present");
});

test("gate OFF via explicit ADA_PROMPT_DOD=0: byte-identical to pre-T1.1 build", async () => {
  const a = (await guidanceWith(NEW, { ADA_RUNNER_TIMEOUT_MS: "480000", ADA_PROMPT_DOD: "0" })).system;
  const b = (await guidanceWith(OLD, { ADA_RUNNER_TIMEOUT_MS: "480000" })).system;
  assert.equal(a, b, "gate-off long guidance must be byte-identical to the T0.1 build");
  assert.ok(!a.includes("DEFINITION OF DONE"));
});

test("gate ON via explicit ADA_PROMPT_DOD=1: long guidance contains the DEFINITION OF DONE block", async () => {
  const g = (await guidanceWith(NEW, { ADA_RUNNER_TIMEOUT_MS: "480000", ADA_PROMPT_DOD: "1" })).system;
  assert.ok(g.includes("DEFINITION OF DONE (grading = ONE literal success command"), "DOD header");
  assert.ok(g.includes("bash -lc"), "bash -lc");
  assert.ok(g.includes("Combine independent shell steps into ONE Bash call"), "rule 1");
  assert.ok(g.includes("tail --pid=<pid>"), "rule 2");
  assert.ok(g.includes("a partially working setup scores zero"), "rule 3");
  assert.ok(g.includes("the definition-of-done check passes"), "rule 5");
  assert.ok(!g.includes("Batch independent reads/greps/globs"), "old rule 1 gone");
  assert.ok(!g.includes("poll its log file"), "old rule 2 gone");
  assert.ok(!g.includes("If a check fails twice"), "old rule 3 gone");
});

test("gate OFF: byte-identity holds across several budgets", async () => {
  for (const budget of ["301000", "480000", "900000", "3600000"]) {
    const a = (await guidanceWith(NEW, { ADA_RUNNER_TIMEOUT_MS: budget, ADA_PROMPT_DOD: undefined })).system;
    const b = (await guidanceWith(OLD, { ADA_RUNNER_TIMEOUT_MS: budget })).system;
    assert.equal(a, b, `budget ${budget} (default gate state)`);
  }
});

test("short guidance unaffected by the gate (both states byte-identical to pre-T1.1)", async () => {
  const on = (await guidanceWith(NEW, { ADA_RUNNER_TIMEOUT_MS: "115000", ADA_PROMPT_DOD: "1" })).system;
  const off = (await guidanceWith(NEW, { ADA_RUNNER_TIMEOUT_MS: "115000", ADA_PROMPT_DOD: undefined })).system;
  const old = (await guidanceWith(OLD, { ADA_RUNNER_TIMEOUT_MS: "115000" })).system;
  assert.equal(on, old);
  assert.equal(off, old);
  assert.ok(!on.includes("DEFINITION OF DONE"));
});

test("systemPromptGuidance delegates to the same budget-adaptive logic", async () => {
  const r = await guidanceWith(NEW, { ADA_RUNNER_TIMEOUT_MS: "480000", ADA_PROMPT_DOD: undefined });
  assert.equal(r.prompt, r.system);
});

test("DOD growth is ~+900 chars (within 600..1300) when explicitly enabled", async () => {
  const on = (await guidanceWith(NEW, { ADA_RUNNER_TIMEOUT_MS: "480000", ADA_PROMPT_DOD: "1" })).system;
  const off = (await guidanceWith(NEW, { ADA_RUNNER_TIMEOUT_MS: "480000", ADA_PROMPT_DOD: undefined })).system;
  const delta = on.length - off.length;
  assert.ok(delta > 600 && delta < 1300, `delta=${delta}`);
});