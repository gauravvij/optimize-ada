// Unit check for the H2 cap hook (shape-aware capToolResponse).
// Run: node eval/analysis/test_cap_hook.mjs  (from /root/optimize_ada, Node 24 on PATH)
import { adaHookOptions } from "../ada-runtime/ada/agent/claude/agent.ts";

const opts = adaHookOptions({ ADA_HOOK_OUTPUT_CAP: "300" });
const hook = opts.hooks.PostToolUse[0].hooks[0];
const long = "x".repeat(5000);
const logs = [];
const orig = console.error;
console.error = (...a) => logs.push(a.join(" "));

let pass = 0, fail = 0;
const check = (name, cond) => {
  if (cond) { pass++; console.log(`PASS ${name}`); }
  else { fail++; console.log(`FAIL ${name}`); }
};

// 1. Bash-shaped object response
const res = await hook({ tool_name: "Bash", tool_response: { stdout: long, stderr: "", interrupted: false, isImage: false } });
const upd = res.hookSpecificOutput.updatedToolOutput;
check("obj: same shape keys", JSON.stringify(Object.keys(upd)) === JSON.stringify(["stdout", "stderr", "interrupted", "isImage"]));
check("obj: stdout truncated to ~cap", upd.stdout.length < 500 && upd.stdout.length > 200);
check("obj: elision marker present", upd.stdout.includes("harness: tool output truncated"));
check("obj: head+tail preserved", upd.stdout.startsWith("xxx") && upd.stdout.endsWith("xxx"));
check("obj: non-string fields untouched", upd.interrupted === false && upd.isImage === false);

// 2. Plain string response
const res2 = await hook({ tool_name: "Read", tool_response: long });
const upd2 = res2.hookSpecificOutput.updatedToolOutput;
check("str: typeof string", typeof upd2 === "string");
check("str: truncated with marker", upd2.length < 500 && upd2.includes("truncated"));

// 3. Content-block array
const res3 = await hook({ tool_name: "WebFetch", tool_response: [{ type: "text", text: long }] });
const upd3 = res3.hookSpecificOutput.updatedToolOutput;
check("arr: still array", Array.isArray(upd3));
check("arr: block type preserved", upd3[0].type === "text");
check("arr: text truncated", upd3[0].text.length < 500 && upd3[0].text.includes("truncated"));

// 4. Under cap -> no rewrite
const res4 = await hook({ tool_name: "Bash", tool_response: { stdout: "short" } });
check("under-cap: continue true, no rewrite", res4.continue === true && res4.hookSpecificOutput === undefined);

// 5. Reach log fires on every call
check("reach log: fired lines logged", logs.filter((l) => l.includes("[hook:cap] PostToolUse") && l.includes("fired")).length === 4);
check("reach log: truncation lines logged", logs.filter((l) => l.includes("truncated (cap 300)")).length === 3);

console.error = orig;
console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail === 0 ? 0 : 1);
