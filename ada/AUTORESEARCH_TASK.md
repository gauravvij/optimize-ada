# Autoresearch target: coding-task reliability

Improve Ada's success rate on a private suite of small, automatically graded coding tasks.

Only `agent/coding-guidance.ts` may be changed. Its exported string is appended to Ada's existing `claude_code` system-prompt preset in both browser and messaging paths. Keep the guidance concise, general, and safe for arbitrary repositories.

The private development suite covers repository instruction discovery, debugging, configuration changes, multi-file consistency, edge cases, verification, and scope discipline. Grading uses exact filesystem assertions and executable checks; there is no LLM judge. Aggregate diagnostics report anonymous case IDs, skill tags, result status, and turn count. Holdout cases are unavailable during optimization.

Do not change the agent runner, evaluator integration, model routing, existing tests, or any other source file. Do not attempt to locate private tasks or reference answers.
