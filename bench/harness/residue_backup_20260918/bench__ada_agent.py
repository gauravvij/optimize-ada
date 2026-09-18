"""Harbor installed-agent adapter for the Ada coding agent.

Runs Ada's headless runner (scripts/autoresearch-run-agent.ts) inside the
task container against the task instruction, using the OpenRouter gateway
(ANTHROPIC_BASE_URL=https://openrouter.ai/api) with the z-ai/glm-5.3-flash
model — identical harness config for both variants; the ONLY difference is
which Ada source tarball is installed.

Usage (from /home/azureuser/adaAgent):

    harbor run -d terminal-bench/terminal-bench-2 \
        -a bench.ada_agent:AdaAgent --ak variant=best \
        --ae OPENROUTER_API_KEY=... -i terminal-bench/fix-git -n 4 \
        -o bench/results-best

Variant selection: ``--ak variant=baseline`` installs bench/ada-baseline.tgz
(git-committed df0c537 agent state); ``--ak variant=best`` installs
bench/ada-best.tgz (working tree with retained autoresearcher changes).
``--ak ada_tarball=/path/to.tgz`` overrides the tarball directly.
"""

from __future__ import annotations

import json
import re
import shlex
import tempfile
import tomllib
from pathlib import Path
from typing import Any, override

from harbor.agents.installed.base import BaseInstalledAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

BENCH_DIR = Path("/home/azureuser/adaAgent/bench")
DATASET_DIR = BENCH_DIR / "terminal-bench-2"
DEFAULT_TARBALLS = {
    "baseline": BENCH_DIR / "ada-baseline.tgz",
    "best": BENCH_DIR / "ada-best.tgz",
    "best2": BENCH_DIR / "ada-best2.tgz",
}
DEFAULT_NODE_BIN = Path("/usr/local/bin/node")

# OpenRouter gateway via the Anthropic-compatible endpoint (same config the
# autoresearcher eval used — ada_agent_eval.py lines 199-202).
ANTHROPIC_BASE_URL = "https://openrouter.ai/api"
ANTHROPIC_MODEL = "z-ai/glm-5.3-flash"

ADA_INSTALL_DIR = "/opt/ada"
REMOTE_TARBALL = "/tmp/ada-variant.tgz"
REMOTE_NODE_BIN = "/tmp/ada-node-bin"
REMOTE_PROMPT = "/tmp/ada-task-prompt.txt"
CLAUDE_CONFIG_DIR = "/tmp/ada-claude-config"
# T0.5 (fina_run.md): the agent writes per-session JSONL traces here inside
# the container; the adapter downloads them into the trial dir after the run
# so TB failure diagnosis no longer depends on timestamps alone.
ADA_TRACE_DIR_REMOTE = "/tmp/ada-trace"

# Seconds of slack between the runner's own hard cap and the harbor exec
# timeout, so the runner gets to print its ADA_RUN_RESULT line first.
RUNNER_SLACK_SEC = 60
EXEC_SLACK_SEC = 5

_RESULT_LINE = re.compile(r"^ADA_RUN_RESULT=(\{.*\})\s*$", re.MULTILINE)


def _task_timeout_sec(task_name: str) -> float:
    """Look up [agent].timeout_sec for a task from the local dataset copy."""
    toml_path = DATASET_DIR / task_name / "task.toml"
    try:
        with open(toml_path, "rb") as f:
            data = tomllib.load(f)
        return float(data.get("agent", {}).get("timeout_sec", 900.0))
    except (OSError, tomllib.TOMLDecodeError, ValueError):
        return 900.0


class AdaAgent(BaseInstalledAgent):
    """Ada coding agent, installed into the task container from a tarball."""

    @staticmethod
    def name() -> str:
        return "ada"

    def __init__(
        self,
        *args: Any,
        variant: str = "best",
        ada_tarball: str | None = None,
        node_bin: str = str(DEFAULT_NODE_BIN),
        watchdog_override_ms: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.watchdog_override_ms = watchdog_override_ms
        if ada_tarball:
            self.tarball = Path(ada_tarball)
        else:
            try:
                self.tarball = DEFAULT_TARBALLS[variant]
            except KeyError:
                raise ValueError(
                    f"Unknown variant {variant!r}; expected one of "
                    f"{sorted(DEFAULT_TARBALLS)} or ada_tarball=<path>"
                ) from None
        self.node_bin = Path(node_bin)
        self.variant = variant
        if not self.tarball.is_file():
            raise ValueError(f"Ada tarball not found: {self.tarball}")
        if not self.node_bin.is_file():
            raise ValueError(f"Node binary not found: {self.node_bin}")

    # ------------------------------------------------------------------ #
    # install
    # ------------------------------------------------------------------ #

    @override
    async def install(self, environment: BaseEnvironment) -> None:
        # 1. Ship the variant tarball and the host Node 24 binary into the
        #    container (docker compose cp — no network dependency).
        await environment.upload_file(self.tarball, REMOTE_TARBALL)
        await environment.upload_file(self.node_bin, REMOTE_NODE_BIN)

        # 2. Install Node 24 (skip if the image already ships Node >= 23).
        #    libstdc++6 is the only shared lib beyond libc that the node and
        #    bundled-claude binaries may need on slim images.
        await self.exec_as_root(
            environment,
            command=(
                "set -euo pipefail; "
                "NEED_NODE=1; "
                'if command -v node >/dev/null 2>&1; then '
                '  MAJ=$(node -p "process.versions.node.split(\'.\')[0]" 2>/dev/null || echo 0); '
                "  if [ \"$MAJ\" -ge 23 ] 2>/dev/null; then NEED_NODE=0; fi; "
                "fi; "
                "if [ \"$NEED_NODE\" = 1 ]; then "
                "  install -m 755 " + shlex.quote(REMOTE_NODE_BIN) + " /usr/local/bin/node; "
                "fi; "
                "node --version; "
                # Ensure shared libraries for node + the bundled claude binary.
                "MISSING=$( (ldd /usr/local/bin/node 2>/dev/null; "
                f"ldd {ADA_INSTALL_DIR}/node_modules/@anthropic-ai/claude-agent-sdk-linux-x64/claude 2>/dev/null) "
                " | grep 'not found' | sort -u || true); "
                'if [ -n "$MISSING" ]; then '
                "  (apt-get update -qq && apt-get install -y -qq libstdc++6 ca-certificates) "
                "  || (dnf install -y libstdc++ || apk add libstdc++ || true); "
                "fi"
            ),
            timeout_sec=300,
        )

        # 3. Extract the Ada tree (node_modules included — no npm install).
        await self.exec_as_root(
            environment,
            command=(
                "set -euo pipefail; "
                f"mkdir -p {ADA_INSTALL_DIR} {CLAUDE_CONFIG_DIR}; "
                f"tar xzf {REMOTE_TARBALL} -C {ADA_INSTALL_DIR}; "
                f"chmod -R a+rX {ADA_INSTALL_DIR}; "
                f"chmod 777 {CLAUDE_CONFIG_DIR}; "
                f"test -f {ADA_INSTALL_DIR}/scripts/autoresearch-run-agent.ts; "
                f"test -x {ADA_INSTALL_DIR}/node_modules/@anthropic-ai/claude-agent-sdk-linux-x64/claude; "
                f"rm -f {REMOTE_TARBALL} {REMOTE_NODE_BIN}; "
                "du -sh /opt/ada"
            ),
            timeout_sec=600,
        )

    def get_version_command(self) -> str | None:
        return f"node {ADA_INSTALL_DIR}/scripts/autoresearch-run-agent.ts --help 2>&1 | head -1 || node --version"

    # ------------------------------------------------------------------ #
    # run
    # ------------------------------------------------------------------ #

    def _task_name(self) -> str:
        """Derive the task name from the trial directory (<task>__<id>)."""
        # logs_dir points inside <jobs>/<timestamp>/<task>__<id>/agent/...
        for part in reversed(self.logs_dir.parts):
            m = re.match(r"^(?P<task>.+)__[A-Za-z0-9]{6,}$", part)
            if m:
                return m.group("task")
        return ""

    def _resolve_api_key(self) -> str:
        for source in (self.extra_env, dict(__import__("os").environ)):
            for key in ("OPENROUTER_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
                value = source.get(key)
                if value:
                    return value
        raise ValueError(
            "No API key: pass --ae OPENROUTER_API_KEY=... (or ANTHROPIC_AUTH_TOKEN)"
        )

    @override
    async def run(
        self, instruction: str, environment: BaseEnvironment, context: AgentContext
    ) -> None:
        task_name = self._task_name()
        agent_timeout = _task_timeout_sec(task_name) if task_name else 900.0
        runner_cap_ms = int(max(agent_timeout - RUNNER_SLACK_SEC, 60) * 1000)
        if self.watchdog_override_ms:
            runner_cap_ms = int(self.watchdog_override_ms)
        exec_timeout = int(max(agent_timeout - EXEC_SLACK_SEC, 60))

        workdir = "/"
        try:
            cfg_workdir = environment.task_env_config.workdir
            if cfg_workdir:
                workdir = str(cfg_workdir)
        except AttributeError:
            pass

        self.logger.info(
            "Ada run: task=%s variant=%s workdir=%s agent_timeout=%ss "
            "runner_cap_ms=%d",
            task_name or "<unknown>",
            self.variant,
            workdir,
            agent_timeout,
            runner_cap_ms,
        )

        # Ship the instruction as a prompt file (avoids shell-quoting issues).
        with tempfile.NamedTemporaryFile(
            "w", suffix=".txt", prefix="ada-prompt-", delete=False
        ) as f:
            f.write(instruction)
            prompt_local = Path(f.name)
        try:
            await environment.upload_file(prompt_local, REMOTE_PROMPT)
        finally:
            prompt_local.unlink(missing_ok=True)
        await self.exec_as_root(
            environment,
            command=f"chmod 644 {REMOTE_PROMPT}",
            timeout_sec=30,
        )

        env = {
            "ANTHROPIC_BASE_URL": ANTHROPIC_BASE_URL,
            "ANTHROPIC_AUTH_TOKEN": self._resolve_api_key(),
            "ANTHROPIC_MODEL": ANTHROPIC_MODEL,
            "ADA_RUNNER_TIMEOUT_MS": str(runner_cap_ms),
            # T0.5: write per-session JSONL traces to a known container path
            # so they can be pulled into the trial dir after the run.
            "ADA_TRACE_DIR": ADA_TRACE_DIR_REMOTE,
            "CLAUDE_CONFIG_DIR": CLAUDE_CONFIG_DIR,
            "HOME": "/tmp/ada-home",
            "IS_SANDBOX": "1",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        }

        command = (
            f"mkdir -p /tmp/ada-home && cd {ADA_INSTALL_DIR} && "
            f"node scripts/autoresearch-run-agent.ts {shlex.quote(workdir)} "
            f"{REMOTE_PROMPT} 2>&1"
        )

        # The runner exits 0 even on agent errors (the ADA_RUN_RESULT JSON
        # carries is_error), so a zero exit just means the harness ran.
        result = await self.exec_as_agent(
            environment,
            command=command,
            env=env,
            timeout_sec=exec_timeout,
        )

        # Persist the runner's diagnostics (watchdog banner, deadline
        # interrupts; stderr is merged into stdout via 2>&1) into
        # context.metadata so watchdog engagement is auditable in result.json.
        combined = ((getattr(result, "stdout", "") or "") + "\n"
                    + (getattr(result, "stderr", "") or ""))
        matched = [
            line for line in combined.splitlines()
            if "watchdog" in line or "deadline" in line or "[runner]" in line
        ]
        if matched:
            context.metadata = context.metadata or {}
            context.metadata["runner_stderr"] = matched[-40:]

        # T0.5 (fina_run.md): persist the agent's per-session JSONL traces
        # into the trial dir so TB failure diagnosis no longer depends on
        # timestamps alone. Best-effort: never fails the run.
        await self._persist_traces(environment, context)

        self._populate_context(result.stdout or "", context)

    async def _persist_traces(
        self, environment: BaseEnvironment, context: AgentContext
    ) -> None:
        """Copy the container's ADA_TRACE_DIR/*.jsonl into the trial dir.

        The trial dir is the ancestor of self.logs_dir named <task>__<id>.
        Traces land at <trial>/agent-trace/<sessionId>.jsonl. Any failure is
        logged and swallowed — trace persistence must not fail the run.
        """
        try:
            listing = await self.exec_as_agent(
                environment,
                command=(
                    f"sh -c 'ls -1 {ADA_TRACE_DIR_REMOTE}/*.jsonl 2>/dev/null || true'"
                ),
                timeout_sec=30,
            )
            names = [
                line.strip()
                for line in ((getattr(listing, "stdout", "") or "").splitlines())
                if line.strip().endswith(".jsonl")
            ]
            if not names:
                self.logger.info("no agent traces found in %s", ADA_TRACE_DIR_REMOTE)
                return
            trial_dir = None
            for part in reversed(self.logs_dir.parts):
                if re.match(r"^.+__[A-Za-z0-9]{6,}$", part):
                    trial_dir = self.logs_dir
                    while trial_dir is not None and trial_dir.name != part:
                        trial_dir = trial_dir.parent
                    break
            if trial_dir is None:
                self.logger.warning(
                    "could not locate trial dir from logs_dir %s", self.logs_dir
                )
                return
            dest = trial_dir / "agent-trace"
            dest.mkdir(parents=True, exist_ok=True)
            for remote in names:
                target = dest / Path(remote).name
                await environment.download_file(remote, target)
            self.logger.info("persisted %d agent trace(s) to %s", len(names), dest)
        except Exception as exc:  # noqa: BLE001 — best-effort by design
            self.logger.warning("trace persistence skipped: %s", exc)

    def _populate_context(self, stdout: str, context: AgentContext) -> None:
        """Parse the ADA_RUN_RESULT line into the harbor AgentContext."""
        match = _RESULT_LINE.search(stdout)
        if not match:
            self.logger.warning("No ADA_RUN_RESULT line in runner stdout")
            return
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            self.logger.warning("ADA_RUN_RESULT line is not valid JSON")
            return

        usage = payload.get("modelUsage") or {}
        input_tokens = 0
        output_tokens = 0
        cache_tokens = 0
        for entry in usage.values():
            input_tokens += int(entry.get("inputTokens") or 0)
            output_tokens += int(entry.get("outputTokens") or 0)
            cache_tokens += int(entry.get("cacheReadInputTokens") or 0)

        context.n_input_tokens = input_tokens
        context.n_output_tokens = output_tokens
        context.n_cache_tokens = cache_tokens
        context.cost_usd = payload.get("total_cost_usd")
        context.metadata = context.metadata or {}
        context.metadata.update(
            {
                "ada_variant": self.variant,
                "ada_is_error": payload.get("is_error"),
                "ada_num_turns": payload.get("num_turns"),
            }
        )
        self.logger.info(
            "ADA_RUN_RESULT: is_error=%s turns=%s cost_usd=%s",
            payload.get("is_error"),
            payload.get("num_turns"),
            payload.get("total_cost_usd"),
        )
