/**
 * L1L2 smoke test 1: unit-check the lever-guidance gating logic.
 * - selfVerifyGuidance: ON with ADA_SELF_VERIFY=1, OFF otherwise.
 * - adaptiveConcisionGuidance: fires only with ADA_ADAPTIVE_CONCISION=1 AND
 *   the ex-ante prompt-property heuristic.
 * - Heuristic fires on exactly large-scale-text-editing + password-recovery
 *   among the 15 cached task instruction.md files (0 hand-tuned tasks).
 */
import { selfVerifyGuidance, adaptiveConcisionGuidance, concisionGateFires } from "/root/optimize_ada/eval/ada-runtime/ada/agent/lever-guidance.ts";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

const CACHE = "/root/.cache/harbor/tasks";
let fails = 0;
const check = (name, cond, detail = "") => {
  console.log(`${cond ? "PASS" : "FAIL"} ${name}${detail ? " — " + detail : ""}`);
  if (!cond) fails++;
};

// --- L1 gating ---
const on = { ADA_SELF_VERIFY: "1" };
const off = {};
check("L1 on with ADA_SELF_VERIFY=1", selfVerifyGuidance(on).includes("Self-verification requirement"));
check("L1 off by default", selfVerifyGuidance(off) === "");
check("L1 text mentions running the deliverable", selfVerifyGuidance(on).includes("execute what you produced"));

// --- L2 gating ---
const l2on = { ADA_ADAPTIVE_CONCISION: "1" };
const bulk = "Transform /app/input.csv (1 million rows) to match /app/expected.csv exactly.";
const plain = "I just made some changes to my personal site and checked out master.";
check("L2 on for bulk-volume prompt", adaptiveConcisionGuidance(bulk, l2on).includes("Operating-efficiency"));
check("L2 off for plain prompt", adaptiveConcisionGuidance(plain, l2on) === "");
check("L2 off without env gate", adaptiveConcisionGuidance(bulk, off) === "");

// --- Heuristic across all 15 cached instructions ---
const EXPECT = new Set(["large-scale-text-editing", "password-recovery"]);
const fired = [];
for (const d of readdirSync(CACHE)) {
  for (const t of readdirSync(join(CACHE, d))) {
    const f = join(CACHE, d, t, "instruction.md");
    try { readFileSync(f); } catch { continue; }
    const prompt = readFileSync(f, "utf8");
    if (concisionGateFires(prompt)) fired.push(t);
  }
}
console.log("Heuristic fired on:", fired.join(", "));
check("heuristic fires on exactly the 2 expected tasks", fired.length === EXPECT.size && fired.every(t => EXPECT.has(t)));

// --- Composed append parity check (baseline behavior when gates off) ---
const both = { ADA_SELF_VERIFY: "1", ADA_ADAPTIVE_CONCISION: "1" };
const compose = (prompt, env) => [selfVerifyGuidance(env), adaptiveConcisionGuidance(prompt, env)].filter(s => s && s.trim().length > 0).join("\n\n");
check("composed append empty when both gates off", compose(bulk, off) === "");
check("composed append = L1 only for plain prompt", compose(plain, on).includes("Self-verification") && !compose(plain, on).includes("Operating-efficiency"));
check("composed append = L1 only for plain prompt under both gates", compose(plain, both).includes("Self-verification") && !compose(plain, both).includes("Operating-efficiency"));
check("composed append = L1+L2 for bulk prompt", compose(bulk, both).includes("Self-verification") && compose(bulk, both).includes("Operating-efficiency"));

console.log(fails === 0 ? "\nALL CHECKS PASSED" : `\n${fails} CHECK(S) FAILED`);
process.exit(fails === 0 ? 0 : 1);
