"""
Harbor adapter for the Ada bridge (rabbah/ada) — treatment arm of the
Ada harness-contribution A/B campaign.

Design (see eval/config.json + plans/plan.md):
- The Ada bridge runs INSIDE each task container, next to the task files, so
  its claude child operates on /app exactly like the reference claude-code
  agent. A fresh container per trial => no cross-trial state.
- The runtime (Node 24 + ada source + node_modules incl. the Agent SDK's
  bundled claude 2.1.258 binary + the poller script) is bind-mounted into the
  container at /ada-runtime via harbor's --mounts option. install() only
  verifies the mount; run() starts the bridge, runs the poller, and cleans up.
- Per task: POST prompt to the bridge /sessions with cwd=/app (Ada patch),
  poll /sessions/:id/events until RUN_FINISHED/RUN_ERROR, extract the result
  text + claude.usage, DELETE the session, and populate Harbor's AgentContext
  (cost_usd, token counts, latency metadata).

Usage:
  PYTHONPATH=/root/optimize_ada harbor run ... \
    --agent eval.ada-agent.ada_agent:AdaBridgeAgent \
    --model anthropic/claude-haiku-4-5 \
    --mounts '[{"type":"bind","source":"/root/optimize_ada/eval/ada-runtime","target":"/ada-runtime"}]'
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, ClassVar, override

from harbor.agents.installed.base import BaseInstalledAgent
from harbor.agents.model_connection import ModelConnectionSpec
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

RUNTIME_DIR = "/ada-runtime"
NODE_BIN = f"{RUNTIME_DIR}/node-v24.11.0-linux-x64/bin"
ADA_DIR = f"{RUNTIME_DIR}/ada"
POLLER = f"{RUNTIME_DIR}/ada_poll.mjs"
BRIDGE_PORT = 8090
BRIDGE_LOG = "/logs/agent/ada-bridge.log"
EVENTS_FILE = "/logs/agent/ada-events.jsonl"
PROMPT_FILE = "/tmp/ada-prompt.txt"


class AdaBridgeAgent(BaseInstalledAgent):
    """Treatment arm: the Ada bridge wrapping the same claude model."""

    SUPPORTS_ATIF: bool = False
    MODEL_CONNECTION = ModelConnectionSpec(
        default_provider="anthropic",
        api_key_envs=("ANTHROPIC_API_KEY",),
    )

    # Agent kwargs (settable via --ak key=value):
    #   bridge_port        - port for the in-container bridge (default 8090)
    #   poll_timeout_s     - poller hard timeout in seconds (default 3300)
    #   concision_guidance - E-opt1: set ADA_CONCISION_GUIDANCE=1 in the bridge
    #                        env so concision-guidance.ts appends its system-
    #                        prompt guidance (default False = baseline behavior)
    #   self_verify        - L1: set ADA_SELF_VERIFY=1 so lever-guidance.ts
    #                        appends the self-verification-before-finish
    #                        directive (default False = baseline behavior)
    #   adaptive_concision - L2: set ADA_ADAPTIVE_CONCISION=1 so lever-
    #                        guidance.ts appends concision guidance ONLY when
    #                        the ex-ante prompt-property heuristic fires
    #                        (default False = baseline behavior)
    #   verify_once        - X1 (dev-loop): set ADA_VERIFY_ONCE=1 so lever-
    #                        guidance.ts appends the verify-once (L1-lite)
    #                        directive — run the deliverable once, fix once,
    #                        re-run once, no open-ended fix loop
    #                        (default False = baseline behavior)
    #   verify_against_criteria - X2 (dev-loop): set
    #                        ADA_VERIFY_AGAINST_CRITERIA=1 so lever-guidance.ts
    #                        appends the verify-against-criteria directive —
    #                        test the deliverable against the task's STATED
    #                        SUCCESS CRITERIA and edge cases (not just a
    #                        happy-path run); fix once, STOP on pass
    #                        (default False = baseline behavior)
    #   effort_realism     - X3 (dev-loop): set ADA_EFFORT_REALISM=1 so lever-
    #                        guidance.ts appends the effort-realism directive —
    #                        prefer complete working minimal solution, switch
    #                        after 3 failed approaches, verify cheaply against
    #                        stated criteria (X2 cost control inherited)
    #                        (default False = baseline behavior)
    #   hook_spike         - H0: set ADA_HOOK_SPIKE=1 so agent.ts registers a
    #                        no-op PostToolUse logging hook (seam probe)
    #   hook_verify_gate    - H1: set ADA_HOOK_VERIFY_GATE=1 so agent.ts
    #                        registers the Stop-hook verification gate
    #   hook_output_cap     - H2: set ADA_HOOK_OUTPUT_CAP=<chars> so agent.ts
    #                        truncates long tool results (head+tail)
    #   hook_max_turns      - H3: set ADA_HOOK_MAX_TURNS=<n> hard turn cap
    #   lever_debug        - set ADA_LEVER_DEBUG=1 so the bridge logs the
    #                        composed systemPromptAppend (parts + chars) on
    #                        every session; console.log only, zero effect on
    #                        model behavior — evidence for auditability
    bridge_port: int = BRIDGE_PORT
    poll_timeout_s: int = 3300
    concision_guidance: bool = False
    self_verify: bool = False
    adaptive_concision: bool = False
    verify_once: bool = False
    verify_once_trimmed: bool = False
    verify_against_criteria: bool = False
    effort_realism: bool = False
    lever_debug: bool = False
    hook_spike: bool = False
    hook_verify_gate: bool = False
    hook_output_cap: int = 0
    hook_max_turns: int = 0

    def __init__(
        self,
        logs_dir: Path,
        prompt_template_path: Path | str | None = None,
        version: str | None = None,
        extra_env: dict[str, str] | None = None,
        *args,
        bridge_port: int = BRIDGE_PORT,
        poll_timeout_s: int = 3300,
        concision_guidance: bool = False,
        self_verify: bool = False,
        adaptive_concision: bool = False,
        verify_once: bool = False,
        verify_once_trimmed: bool = False,
        verify_against_criteria: bool = False,
        effort_realism: bool = False,
        lever_debug: bool = False,
        hook_spike: bool = False,
        hook_verify_gate: bool = False,
        hook_output_cap: int = 0,
        hook_max_turns: int = 0,
        config: Path | str | dict[str, Any] | None = None,
        **kwargs,
    ):
        """Bind Harbor --ak kwargs to instance attributes.

        REQUIRED because the base-class __init__ chains absorb unknown kwargs
        silently (BaseAgent.__init__(**kwargs) never setattrs them), which would
        otherwise leave every env gate False and make a candidate arm run as an
        untreated baseline re-run.
        """
        self.bridge_port = bridge_port
        self.poll_timeout_s = poll_timeout_s
        self.concision_guidance = concision_guidance
        self.self_verify = self_verify
        self.adaptive_concision = adaptive_concision
        self.verify_once = verify_once
        self.verify_once_trimmed = verify_once_trimmed
        self.verify_against_criteria = verify_against_criteria
        self.effort_realism = effort_realism
        self.lever_debug = lever_debug
        self.hook_spike = hook_spike
        self.hook_verify_gate = hook_verify_gate
        self.hook_output_cap = hook_output_cap
        self.hook_max_turns = hook_max_turns
        super().__init__(
            logs_dir,
            prompt_template_path=prompt_template_path,
            version=version,
            extra_env=extra_env,
            *args,
            config=config,
            **kwargs,
        )

    @staticmethod
    @override
    def name() -> str:
        return "ada-bridge"

    @override
    def get_version_command(self) -> str | None:
        return f"{NODE_BIN}/node --version"

    # ------------------------------------------------------------------ install

    @override
    async def install(self, environment: BaseEnvironment) -> None:
        """Verify the bind-mounted runtime is present (no network installs).

        The runtime is prepared on the host (eval/ada-runtime/) and mounted via
        harbor's --mounts; this keeps install hermetic, fast, and identical
        across trials.
        """
        result = await environment.exec(
            command=(
                f"test -x {NODE_BIN}/node && test -f {ADA_DIR}/agent/index.ts "
                f"&& test -f {POLLER} && echo ok"
            ),
        )
        if result.return_code != 0 or "ok" not in (result.stdout or ""):
            raise RuntimeError(
                "Ada runtime not found at /ada-runtime. Start the run with "
                "--mounts "
                "'[{\"type\":\"bind\",\"source\":\"/root/optimize_ada/eval/"
                "ada-runtime\",\"target\":\"/ada-runtime\"}]'"
            )

    # --------------------------------------------------------------------- run

    def _bridge_env(self) -> dict[str, str]:
        """Env for the bridge process (and, via Ada's passthrough, the claude
        child). The API key never appears in a command string — only in the
        exec env dict, which Harbor redacts in logs."""
        access = self.model_connection
        env: dict[str, str] = {
            "PORT": str(self.bridge_port),
            "ANTHROPIC_MODEL": self._resolved_model_name() or "claude-haiku-4-5",
            "IS_SANDBOX": "1",  # allow bypassPermissions as root (parity with ref arm)
            "PATH": f"{NODE_BIN}:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "HOME": "/root",
            "WORKSPACE_ROOT": "/tmp/ada-ws",
            "MAX_CONCURRENT_RUNS": "3",
        }
        if access.api_key:
            env["ANTHROPIC_API_KEY"] = access.api_key
        # E-opt1: concision guidance is OFF by default; only the candidate arm
        # sets --ak concision_guidance=1 so baseline/control arms stay clean.
        if self.concision_guidance:
            env["ADA_CONCISION_GUIDANCE"] = "1"
        # L1L2: both levers OFF by default; only the candidate arm sets
        # --ak self_verify=1 adaptive_concision=1 so baseline arms stay clean.
        if self.self_verify:
            env["ADA_SELF_VERIFY"] = "1"
        if self.adaptive_concision:
            env["ADA_ADAPTIVE_CONCISION"] = "1"
        # X1 (dev-loop): verify-once directive OFF by default; only the
        # candidate arm sets --ak verify_once=1 so baseline arms stay clean.
        if self.verify_once:
            env["ADA_VERIFY_ONCE"] = "1"
        # X1r (dev-loop): trimmed verify-once directive OFF by default; only
        # the candidate arm sets --ak verify_once_trimmed=1 so baseline arms
        # stay clean.
        if self.verify_once_trimmed:
            env["ADA_VERIFY_ONCE_TRIMMED"] = "1"
        # X2 (dev-loop): verify-against-criteria directive OFF by default;
        # only the candidate arm sets --ak verify_against_criteria=1 so
        # baseline arms stay clean.
        if self.verify_against_criteria:
            env["ADA_VERIFY_AGAINST_CRITERIA"] = "1"
        # X3 (dev-loop): effort-realism directive OFF by default; only the
        # candidate arm sets --ak effort_realism=1 so baseline arms stay clean.
        if self.effort_realism:
            env["ADA_EFFORT_REALISM"] = "1"
        if self.lever_debug:
            env["ADA_LEVER_DEBUG"] = "1"
        # Phase 1 (loop v2): SDK-hooks levers, OFF by default; only the
        # candidate arm sets --ak hook_spike=1 etc. so baseline arms stay clean.
        if self.hook_spike:
            env["ADA_HOOK_SPIKE"] = "1"
        if self.hook_verify_gate:
            env["ADA_HOOK_VERIFY_GATE"] = "1"
        if self.hook_output_cap:
            env["ADA_HOOK_OUTPUT_CAP"] = str(self.hook_output_cap)
        if self.hook_max_turns:
            env["ADA_HOOK_MAX_TURNS"] = str(self.hook_max_turns)
        return env

    def _resolved_model_name(self) -> str | None:
        if self.model_name:
            return self.model_name.split("/")[-1]
        return None

    async def _ensure_bridge(self, environment: BaseEnvironment) -> None:
        """Start the bridge if it isn't already listening (idempotent)."""
        port = self.bridge_port
        probe = (
            f"{NODE_BIN}/node -e "
            f"\"fetch('http://localhost:{port}/').then(r=>process.exit(0))"
            f".catch(()=>process.exit(1))\""
        )
        check = await environment.exec(command=probe)
        if check.return_code == 0:
            self.logger.debug("Ada bridge already up")
            return

        start = (
            f"mkdir -p /logs/agent /tmp/ada-ws && cd {ADA_DIR} && "
            f"nohup {NODE_BIN}/node agent/index.ts > {BRIDGE_LOG} 2>&1 & echo $!"
        )
        await environment.exec(command=start, env=self._bridge_env())

        # Wait for readiness (bridge binds the port within a few seconds).
        for _ in range(30):
            check = await environment.exec(command=probe)
            if check.return_code == 0:
                return
            import asyncio

            await asyncio.sleep(1)
        raise RuntimeError(
            f"Ada bridge failed to start; see {BRIDGE_LOG} in the trial logs"
        )

    @override
    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        await self._ensure_bridge(environment)

        # Transfer the prompt via file (instructions can exceed argv limits).
        with tempfile.NamedTemporaryFile(
            "w", suffix=".txt", prefix="ada-prompt-"
        ) as tmp:
            tmp.write(instruction)
            tmp.flush()
            await environment.upload_file(Path(tmp.name), PROMPT_FILE)

        poller_env = {
            "ADA_BASE": f"http://localhost:{self.bridge_port}",
            "ADA_PROMPT_FILE": PROMPT_FILE,
            "ADA_CWD": "/app",
            "ADA_PERMISSION_MODE": "bypassPermissions",
            "ADA_TIMEOUT_MS": str(self.poll_timeout_s * 1000),
            "ADA_EVENTS_FILE": EVENTS_FILE,
            "PATH": f"{NODE_BIN}:/usr/bin:/bin",
        }
        result = await environment.exec(
            command=f"{NODE_BIN}/node {POLLER}",
            env=poller_env,
            timeout_sec=self.poll_timeout_s + 120,
        )

        summary = self._parse_summary(result.stdout or "")
        self._populate_context(context, summary, result.stdout or "")

        if summary is None:
            raise RuntimeError(
                f"Ada poller produced no summary (exit {result.return_code}). "
                f"stdout: {(result.stdout or '')[:500]} "
                f"stderr: {(result.stderr or '')[:500]}"
            )
        if not summary.get("finished"):
            # RUN_ERROR or poller timeout: record it, but do NOT raise — the
            # verifier still grades the (partial) work and the usage/cost of
            # the attempt must survive into result.json.
            self.logger.warning(
                "Ada run did not finish cleanly: %s", summary.get("error")
            )

    # ----------------------------------------------------------------- helpers

    @staticmethod
    def _parse_summary(stdout: str) -> dict[str, Any] | None:
        """The poller prints exactly one JSON summary line on stdout."""
        for line in reversed(stdout.strip().splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    data = json.loads(line)
                    if isinstance(data, dict) and "sessionId" in data:
                        return data
                except json.JSONDecodeError:
                    continue
        return None

    def _populate_context(
        self, context: AgentContext, summary: dict[str, Any] | None, raw_stdout: str
    ) -> None:
        if summary is None:
            return
        usage = summary.get("usage") or {}
        inp = usage.get("inputTokens") or 0
        cache_read = usage.get("cacheReadTokens") or 0
        cache_create = usage.get("cacheCreationTokens") or 0
        context.n_input_tokens = inp + cache_read + cache_create
        context.n_cache_tokens = cache_read
        context.n_output_tokens = usage.get("outputTokens") or 0
        cost = usage.get("costUsd")
        if cost is not None:
            try:
                context.cost_usd = float(cost)
            except (TypeError, ValueError):
                pass
        raw = summary.get("rawEvent") or {}
        context.metadata = {
            "ada_session_id": summary.get("sessionId"),
            "ada_finished": summary.get("finished"),
            "ada_error": summary.get("error"),
            "num_turns": raw.get("num_turns"),
            "ttft_ms": raw.get("ttft_ms"),
            "duration_ms": raw.get("duration_ms"),
            "tool_calls": summary.get("toolCalls"),
            "n_events": summary.get("nEvents"),
            "result_text": (summary.get("result") or "")[:2000],
        }
