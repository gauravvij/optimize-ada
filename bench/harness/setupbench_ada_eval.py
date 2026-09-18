#!/usr/bin/env python3
"""Matched external evaluation of baseline and optimized Ada on SetupBench."""

from __future__ import annotations

import argparse
import concurrent.futures
import contextlib
import hashlib
import json
import os
import random
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any


# Relocated layout (2026-09-18): this script lives in bench/harness/ inside the
# campaign tree. ROOT is bench/, HARNESS is bench/harness/. The SetupBench
# dataset repo and the runner TS sit beside this script; the Ada workspaces are
# configurable so replication can point them at any git worktree.
HARNESS = Path(__file__).resolve().parent
ROOT = HARNESS.parent
SETUPBENCH = HARNESS / "setupbench"
FINAL_ADA = Path(os.environ.get("ADA_WORKSPACE", str(ROOT.parent / "ada"))).resolve()
BASELINE_ADA = Path(os.environ.get("ADA_BASELINE_WORKSPACE", str(HARNESS / "worktrees" / "ada-baseline"))).resolve()
NODE_MODULES = FINAL_ADA / "node_modules"
NODE_BINARY = Path("/usr/local/bin/node")  # v24 with type-stripping; /usr/bin/node is v20 and cannot run .ts
BENCHMARK_RUNNER = HARNESS / "setupbench_ada_runner.ts"
IMAGE_OVERRIDES = {
    "codeexecservice.azurecr.io/setupbench-node-16:latest": "node:16",
}
ORIGINAL_TASKS = (
    "bgsetup-celery-systemd",
    "bgsetup-filewatcher-daemon",
    "bgsetup-filewatcher-daemon-2",
    "bgsetup-gunicorn-nginx-socket",
    "bgsetup-gunicorn-systemd-socket",
    "bgsetup-multiprocess-master-worker",
)

# Fixed metadata-only split for the clean SetupBench-specific optimization.
SETUPBENCH_DEV_12 = (
    "microsoft-vscode-remote-try-python-e351212",
    "actions-cache-81382a7",
    "pallets-click-14f735c",
    "nvbn-tf-c7e7e1d",
    "graphql-dataloader-003c045",
    "habitat-5826ff8",
    "openstack-stevedore-51134a4",
    "deps-rails-8775b",
    "deps-acts_as_bookable-45b78",
    "dbsetup-redis-3",
    "dbsetup-mongodb-3",
    "bgsetup-gunicorn-nginx-socket",
)

SETUPBENCH_VALIDATION_12 = (
    "microsoft-azure-pipelines-tasks-bfcd4b2",
    "prometheus-bd5b2ea",
    "fsspec-filesystem_spec-3ff5fca",
    "dishait-tov-template-39c0898",
    "hackmdio-codimd-f00df50",
    "whisper-517a43e",
    "wagtail-wagtail-28fcd01",
    "deps-ultimate-frontrunning-bot-449d6",
    "deps-gatsby-plugin-intl-2b7ac",
    "dbsetup-mongodb-2",
    "dbsetup-mysql-2",
    "bgsetup-filewatcher-daemon-2",
)

FRESH_24_TASKS = (
    "dbsetup-postgresql-1",
    "dbsetup-postgresql-2",
    "dbsetup-mysql-1",
    "dbsetup-mysql-2",
    "dbsetup-redis-1",
    "dbsetup-redis-2",
    "dbsetup-sqlite-1",
    "dbsetup-sqlite-2",
    "bgsetup-autossh-reverse-tunnel",
    "bgsetup-autossh-logging",
    "pytesseract-df9fce0",
    "whisper-517a43e",
    "ta-lib-python-0c957ed",
    "habitat-5826ff8",
    "monero-8468549",
    "prometheus-bd5b2ea",
    "caddy-782a3c7",
    "whisper-brokendeps-517a43e",
    "pypa-pipenv-b895476",
    "celery-celery-03e3359",
    "deps-acts_as_bookable-45b78",
    "deps-origen-3e2f3",
    "deps-decidim-module-navbar_links-c7ddb",
    "deps-devise-31774",
)


def command(args: list[str], *, timeout: int = 60, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True, timeout=timeout, check=check)


def revision(repo: Path) -> str:
    return command(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True).stdout.strip()


def tracked_diff_fingerprint(repo: Path) -> str:
    diff = command(["git", "-C", str(repo), "diff", "--binary", "--no-ext-diff"], check=True).stdout
    return hashlib.sha256(diff.encode()).hexdigest()


def load_scenarios() -> dict[str, dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted((SETUPBENCH / "setupbench" / "scenarios").glob("*.jsonl")):
        records.extend(json.loads(line) for line in path.read_text().splitlines() if line.strip())
    return {record["instance_id"]: record for record in records}


def resolved_image(task: dict[str, Any]) -> str:
    return IMAGE_OVERRIDES.get(task["base_image"], task["base_image"])


def image_id(image: str) -> str:
    inspected = command(["docker", "image", "inspect", "--format={{.Id}}", image], check=True)
    return inspected.stdout.strip()


def parse_result(log: str) -> dict[str, Any] | None:
    for line in reversed(log.splitlines()):
        if line.startswith("ADA_RUN_RESULT="):
            try:
                value = json.loads(line.split("=", 1)[1])
                return value if isinstance(value, dict) else None
            except json.JSONDecodeError:
                return None
    return None


def run_variant(
    task: dict[str, Any],
    input_dir: Path,
    variant: str,
    timeout_seconds: int,
    grader_timeout_seconds: int,
    ada_override: Path | None = None,
) -> dict[str, Any]:
    ada = ada_override or (BASELINE_ADA if variant == "baseline" else FINAL_ADA)
    name = f"setupbench-ada-{variant}-{uuid.uuid4().hex[:10]}"
    agent_started = time.monotonic()
    agent_duration = 0.0
    grader_duration = 0.0
    grader_started: float | None = None
    timed_out = False
    valid = True
    harness_error = ""
    grader_output = ""
    grader_returncode: int | None = None
    log = ""
    trace = ""
    try:
        docker_args = [
            "docker", "run", "-d", "--name", name, "--init",
            "-e", "ANTHROPIC_BASE_URL=https://openrouter.ai/api",
            "-e", "ANTHROPIC_AUTH_TOKEN",
            "-e", "ANTHROPIC_API_KEY=",
            "-e", "ANTHROPIC_MODEL=z-ai/glm-5.3-flash",
            "-e", "ASTROPOD_MODEL_PROVIDER=openrouter",
            "-e", "CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1",
            "-e", "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1",
            "-e", f"ADA_TASK={task['problem_statement']}",
            "-e", f"ADA_TASK_ID={task['instance_id']}",
            # Declare the task budget so the agent's finish-time watchdog can
            # stop the session cleanly before this cap force-kills the
            # container (iteration 2; agent/claude/agent.ts disables itself
            # entirely when this variable is absent).
            "-e", f"ADA_RUNNER_TIMEOUT_MS={timeout_seconds * 1000}",
            "-v", f"{NODE_BINARY}:/opt/ada-node:ro",
            "-v", f"{ada}:/opt/ada-src:ro",
            "-v", f"{NODE_MODULES}:/opt/node_modules:ro",
            "-v", f"{BENCHMARK_RUNNER}:/opt/setupbench-ada-runner.ts:ro",
            "-v", f"{input_dir}:/input:ro",
            "-v", f"{SETUPBENCH / 'setupbench' / 'fixtures'}:/setupbench-fixtures:ro",
            resolved_image(task), "bash", "-lc",
            "mkdir -p /testbed /opt/ada && "
            "tar -C /opt/ada-src --exclude=./node_modules --exclude=./.git "
            "--exclude=./.autoresearch -cf - . | tar -C /opt/ada -xf - && "
            "ln -s /opt/node_modules /opt/ada/node_modules && cp -a /input/. /testbed/ && "
            "if [ -f /setupbench-fixtures/prerunner-$ADA_TASK_ID/prerunner.sh ]; then "
            "bash /setupbench-fixtures/prerunner-$ADA_TASK_ID/prerunner.sh; fi && "
            "printf '%s\\n' \"$ADA_TASK\" > /testbed/.setupbench-task.txt && "
            "cd /testbed && /opt/ada-node /opt/setupbench-ada-runner.ts "
            "/testbed /testbed/.setupbench-task.txt > /testbed/.ada.log 2>&1; "
            "printf '%s\\n' $? > /testbed/.ada-exit; exec tail -f /dev/null",
        ]
        launched = command(docker_args, timeout=60)
        if launched.returncode != 0:
            raise RuntimeError(f"docker run failed: {(launched.stdout + launched.stderr)[-1000:]}")

        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            done = command(["docker", "exec", name, "test", "-f", "/testbed/.ada-exit"], timeout=10)
            if done.returncode == 0:
                break
            time.sleep(2)
        else:
            timed_out = True
        agent_duration = time.monotonic() - agent_started

        if not timed_out:
            grader_started = time.monotonic()
            graded = command(
                ["docker", "exec", "-w", "/testbed", name, "bash", "-lc", task["success_command"]],
                timeout=grader_timeout_seconds,
            )
            grader_duration = time.monotonic() - grader_started
            grader_returncode = graded.returncode
            grader_output = (graded.stdout + graded.stderr)[-4000:]
    except Exception as exc:
        if not agent_duration:
            agent_duration = time.monotonic() - agent_started
        if grader_started is not None and not grader_duration:
            grader_duration = time.monotonic() - grader_started
        valid = False
        harness_error = f"{type(exc).__name__}:{exc}"
    finally:
        try:
            logged = command(["docker", "exec", name, "tail", "-c", "50000", "/testbed/.ada.log"], timeout=20)
            log = logged.stdout + logged.stderr
            if logged.returncode != 0:
                valid = False
                harness_error = harness_error or f"agent_log_missing:{log[-500:]}"
        except Exception as exc:
            valid = False
            harness_error = harness_error or f"log_capture:{type(exc).__name__}:{exc}"
        try:
            traced = command(
                ["docker", "exec", name, "tail", "-c", "30000", "/testbed/.ada-trace.jsonl"], timeout=20
            )
            trace = traced.stdout + traced.stderr
        except Exception as exc:
            harness_error = harness_error or f"trace_capture:{type(exc).__name__}:{exc}"
        # Guarded cleanup: a slow/stuck `docker rm` must never kill the whole
        # suite (this exact failure aborted experiment 5 and one validation run).
        for attempt in range(3):
            try:
                command(["docker", "rm", "-f", name], timeout=60)
                break
            except Exception as exc:
                if attempt == 2:
                    harness_error = harness_error or f"container_cleanup:{type(exc).__name__}:{exc}"
                else:
                    time.sleep(5)

    secret = os.environ.get("OPENROUTER_API_KEY", "")
    if secret:
        log = log.replace(secret, "<redacted>")
        grader_output = grader_output.replace(secret, "<redacted>")
        harness_error = harness_error.replace(secret, "<redacted>")
        trace = trace.replace(secret, "<redacted>")
    result = parse_result(log)
    model_usage = (result or {}).get("model_usage") or (result or {}).get("modelUsage") or {}
    usage = model_usage.get("z-ai/glm-5.3-flash") or {}
    if task["task_type"] == "dependency_resolution":
        passed = valid and not timed_out and grader_returncode == 0
    else:
        passed = (
            valid
            and not timed_out
            and "Setup successful" in grader_output
        )
    return {
        "task_id": task["instance_id"],
        "task_type": task["task_type"],
        "variant": variant,
        "valid": valid,
        "passed": passed,
        "timed_out": timed_out,
        "duration_seconds": round(time.monotonic() - agent_started, 3),
        "agent_duration_seconds": round(agent_duration, 3),
        "grader_duration_seconds": round(grader_duration, 3),
        "turns": int((result or {}).get("num_turns") or 0),
        "input_tokens": int(usage.get("input_tokens") or usage.get("inputTokens") or 0),
        "output_tokens": int(usage.get("output_tokens") or usage.get("outputTokens") or 0),
        "cache_read_tokens": int(
            usage.get("cache_read_input_tokens") or usage.get("cacheReadInputTokens") or 0
        ),
        "terminal_result": result is not None,
        "agent_is_error": bool((result or {}).get("is_error")),
        "agent_stop_reason": (result or {}).get("stop_reason"),
        "agent_result": str((result or {}).get("result") or "")[-1000:],
        "grader_returncode": grader_returncode,
        "grader_output": grader_output.strip()[-1000:],
        "harness_error": harness_error[-1000:],
        "agent_log_tail": "" if passed else log[-2000:],
        "agent_trace_tail": trace[-12000:],
    }


def run_variant_with_infrastructure_retries(
    task: dict[str, Any],
    input_dir: Path,
    variant: str,
    timeout_seconds: int,
    grader_timeout_seconds: int,
    ada_override: Path | None = None,
    max_attempts: int = 3,
) -> dict[str, Any]:
    row: dict[str, Any] | None = None
    for attempt in range(1, max_attempts + 1):
        row = run_variant(task, input_dir, variant, timeout_seconds, grader_timeout_seconds, ada_override)
        row["infrastructure_attempts"] = attempt
        if row["valid"]:
            return row
        print(
            f"infrastructure retry task={task['instance_id']} variant={variant} "
            f"attempt={attempt}/{max_attempts}",
            flush=True,
        )
    assert row is not None
    return row


@contextlib.contextmanager
def prepared_input(task: dict[str, Any]):
    fixture = SETUPBENCH / "setupbench" / "fixtures" / task["instance_id"]
    with tempfile.TemporaryDirectory(prefix=f"setupbench-{task['instance_id']}-") as directory:
        root = Path(directory)
        if task.get("repo_url"):
            cloned = command(
                ["git", "clone", "--filter=blob:none", "--no-checkout", task["repo_url"], str(root)],
                timeout=300,
            )
            if cloned.returncode != 0:
                raise RuntimeError(f"clone failed for {task['instance_id']}: {cloned.stderr[-1000:]}")
            commit = task.get("base_commit")
            revision = commit or "origin/HEAD"
            if commit:
                fetched = command(["git", "-C", str(root), "fetch", "--depth=1", "origin", commit], timeout=300)
                if fetched.returncode != 0:
                    raise RuntimeError(f"fetch failed for {task['instance_id']}: {fetched.stderr[-1000:]}")
            checked = command(["git", "-C", str(root), "checkout", "--detach", revision], timeout=60)
            if checked.returncode != 0:
                raise RuntimeError(f"checkout failed for {task['instance_id']}: {checked.stderr[-1000:]}")
        elif fixture.is_dir():
            copied = command(["cp", "-a", f"{fixture}/.", str(root)], timeout=30)
            if copied.returncode != 0:
                raise RuntimeError(f"fixture copy failed for {task['instance_id']}: {copied.stderr[-1000:]}")
        yield root


def preflight(selected: tuple[str, ...], scenarios: dict[str, dict[str, Any]]) -> None:
    images = sorted({resolved_image(scenarios[task_id]) for task_id in selected})
    for image in images:
        pulled = command(["docker", "pull", image], timeout=600)
        if pulled.returncode != 0:
            raise RuntimeError(f"image unavailable: {image}: {pulled.stderr[-1000:]}")
        print(f"image ready: {image}", flush=True)
    for task_id in selected:
        repo = scenarios[task_id].get("repo_url")
        if repo:
            reachable = command(["git", "ls-remote", "--exit-code", repo, "HEAD"], timeout=60)
            if reachable.returncode != 0:
                raise RuntimeError(f"repository unavailable: {task_id}: {repo}")
    print(f"preflight passed for {len(selected)} tasks", flush=True)


def ensure_image(image: str) -> None:
    present = command(["docker", "image", "inspect", image], timeout=30)
    if present.returncode == 0:
        return
    pulled = command(["docker", "pull", image], timeout=600)
    if pulled.returncode != 0:
        raise RuntimeError(f"image unavailable: {image}: {pulled.stderr[-1000:]}")


def wait_for_capacity(min_free_gb: float = 2.5, timeout_seconds: int = 1800) -> None:
    deadline = time.monotonic() + timeout_seconds
    while shutil.disk_usage("/").free < min_free_gb * 1024**3:
        if time.monotonic() >= deadline:
            raise RuntimeError(f"less than {min_free_gb:g} GiB free for {timeout_seconds} seconds")
        free_gb = shutil.disk_usage("/").free / 1024**3
        print(f"capacity wait: {free_gb:.2f} GiB free; need {min_free_gb:.2f}", flush=True)
        time.sleep(30)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--suite", choices=("original6", "fresh24", "validation12", "remaining81", "full93"), default="original6"
    )
    parser.add_argument("--output")
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument("--grader-timeout-seconds", type=int, default=600)
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--seed", type=int, default=20260904)
    parser.add_argument("--parallel-pair", action="store_true")
    parser.add_argument("--task")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--skip-preflight", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--candidate-workspace", default=str(FINAL_ADA))
    args = parser.parse_args()
    if not 1 <= args.repetitions <= 10:
        raise SystemExit("repetitions must be between 1 and 10")
    if not os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        key = os.environ.get("OPENROUTER_API_KEY")
        if not key:
            raise SystemExit("OPENROUTER_API_KEY is missing")
        os.environ["ANTHROPIC_AUTH_TOKEN"] = key
    candidate_ada = Path(args.candidate_workspace).resolve()
    for required in (SETUPBENCH, candidate_ada, BASELINE_ADA, NODE_MODULES, NODE_BINARY, BENCHMARK_RUNNER):
        if not required.exists():
            raise SystemExit(f"required path is missing: {required}")

    scenarios = load_scenarios()
    if args.suite == "original6":
        suite = ORIGINAL_TASKS
    elif args.suite == "fresh24":
        suite = FRESH_24_TASKS
    elif args.suite == "validation12":
        suite = SETUPBENCH_VALIDATION_12
    elif args.suite == "remaining81":
        suite = tuple(task_id for task_id in sorted(scenarios) if task_id not in set(SETUPBENCH_DEV_12))
    else:
        suite = tuple(sorted(scenarios))
        if len(suite) != 93:
            raise SystemExit(f"expected 93 SetupBench tasks, found {len(suite)}")
    selected = (args.task,) if args.task else suite
    if len(set(selected)) != len(selected) or any(task_id not in scenarios for task_id in selected):
        raise SystemExit("selected task IDs must be unique and present in SetupBench")
    if not args.skip_preflight:
        preflight(selected, scenarios)
    if args.preflight_only:
        return 0
    default_outputs = {
        "original6": "SETUPBENCH_ADA_RAW.json",
        "fresh24": "SETUPBENCH_ADA_24_RAW.json",
        "validation12": "SETUPBENCH_ADA_V2_VALIDATION12_RAW.json",
        "remaining81": "SETUPBENCH_ADA_V2_REMAINING81_RAW.json",
        "full93": "SETUPBENCH_ADA_FULL93_RAW.json",
    }
    output_name = args.output or default_outputs[args.suite]
    output_path = HARNESS / output_name
    task_orders: dict[str, list[str]] = {}
    for repetition in range(1, args.repetitions + 1):
        order = list(selected)
        random.Random(args.seed + repetition).shuffle(order)
        task_orders[str(repetition)] = order
    report: dict[str, Any] = {
        "protocol": {
            "setupbench_commit": revision(SETUPBENCH),
            "baseline_ada_commit": revision(BASELINE_ADA),
            "candidate_ada_commit": revision(candidate_ada),
            "baseline_diff_sha256": tracked_diff_fingerprint(BASELINE_ADA),
            "candidate_diff_sha256": tracked_diff_fingerprint(candidate_ada),
            "model": "z-ai/glm-5.3-flash",
            "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "base_image_overrides": IMAGE_OVERRIDES,
            "resolved_image_ids": {
                image: image_id(image) for image in sorted({resolved_image(scenarios[task]) for task in selected})
            },
            "suite": args.suite,
            "timeout_seconds": args.timeout_seconds,
            "grader_timeout_seconds": args.grader_timeout_seconds,
            "tasks": list(selected),
            "task_orders": task_orders,
            "paired_concurrently": args.parallel_pair,
            "max_concurrent_agent_attempts": 2 if args.parallel_pair else 1,
            "execution_order": (
                "baseline and candidate launched as one concurrent pair; one task pair active at a time"
                if args.parallel_pair
                else "alternating baseline-first and optimized-first by task index"
            ),
            "attempts_per_task_variant": args.repetitions,
            "random_seed": args.seed,
            "max_infrastructure_attempts": 3,
            "sampling_rule": (
                "fresh verifier-bounded stratified 10 reposetup / 4 dependency / 8 database / 2 background"
                if args.suite == "fresh24"
                else (
                    "complete SetupBench dataset at the pinned revision"
                    if args.suite == "full93"
                    else (
                        "fixed metadata-only SetupBench v2 split"
                        if args.suite in {"validation12", "remaining81"}
                        else "all six fixture-backed background tasks"
                    )
                )
            ),
            "primary_analysis": (
                "per-task majority pass (at least 2 of 3), paired exact McNemar across 93 tasks"
                if args.suite == "full93" and args.repetitions == 3
                else "paired pass outcomes"
            ),
        },
        "results": [],
    }
    if args.resume and output_path.is_file():
        existing = json.loads(output_path.read_text())
        if existing.get("protocol") != report["protocol"]:
            raise SystemExit("resume output uses an incompatible protocol")
        retained = [
            row
            for row in existing.get("results", [])
            if row.get("task_id") in selected and 1 <= int(row.get("repetition", 0)) <= args.repetitions
        ]
        for row in retained:
            row.setdefault("valid", not str(row.get("grader_output", "")).startswith("harness_error:"))
            row.setdefault("agent_duration_seconds", None)
            row.setdefault("grader_duration_seconds", None)
            row.setdefault("grader_returncode", None)
            row.setdefault("harness_error", "")
        report["results"] = retained
        output_path.write_text(json.dumps(report, indent=2) + "\n")
        print(f"resume: retained {len(retained)} compatible variant results", flush=True)
    else:
        output_path.write_text(json.dumps(report, indent=2) + "\n")
    completed = {
        (repetition, task_id)
        for repetition in range(1, args.repetitions + 1)
        for task_id in selected
        if {
            row["variant"]
            for row in report["results"]
            if row["task_id"] == task_id and int(row["repetition"]) == repetition
        }
        == {"baseline", "optimized"}
    }
    for repetition in range(1, args.repetitions + 1):
        for task_index, task_id in enumerate(task_orders[str(repetition)]):
            if (repetition, task_id) in completed:
                print(f"resume: skipping completed pair repetition={repetition} task={task_id}", flush=True)
                continue
            task = scenarios[task_id]
            if revision(BASELINE_ADA) != report["protocol"]["baseline_ada_commit"] or tracked_diff_fingerprint(
                BASELINE_ADA
            ) != report["protocol"]["baseline_diff_sha256"]:
                raise SystemExit("baseline changed during external holdout evaluation")
            if revision(candidate_ada) != report["protocol"]["candidate_ada_commit"] or tracked_diff_fingerprint(
                candidate_ada
            ) != report["protocol"]["candidate_diff_sha256"]:
                raise SystemExit("candidate changed during external holdout evaluation")
            ensure_image(resolved_image(task))
            wait_for_capacity(min_free_gb=5.0 if args.parallel_pair else 2.5)
            with prepared_input(task) as input_dir:
                if args.parallel_pair:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                        futures = {
                            variant: executor.submit(
                                run_variant_with_infrastructure_retries,
                                task,
                                input_dir,
                                variant,
                                args.timeout_seconds,
                                args.grader_timeout_seconds,
                                candidate_ada if variant == "optimized" else None,
                            )
                            for variant in ("baseline", "optimized")
                        }
                        by_variant = {variant: future.result() for variant, future in futures.items()}
                else:
                    variant_order = (
                        ("baseline", "optimized") if task_index % 2 == 0 else ("optimized", "baseline")
                    )
                    by_variant = {
                        variant: run_variant_with_infrastructure_retries(
                            task,
                            input_dir,
                            variant,
                            args.timeout_seconds,
                            args.grader_timeout_seconds,
                            candidate_ada if variant == "optimized" else None,
                        )
                        for variant in variant_order
                    }
                pair = [by_variant[variant] for variant in ("baseline", "optimized")]
            for row in pair:
                row["repetition"] = repetition
            report["results"].extend(pair)
            output_path.write_text(json.dumps(report, indent=2) + "\n")
            print(
                f"repetition={repetition}/{args.repetitions} task={task_id} "
                f"baseline={'pass' if by_variant['baseline']['passed'] else 'fail'} "
                f"candidate={'pass' if by_variant['optimized']['passed'] else 'fail'} "
                f"turns={by_variant['baseline']['turns']}/{by_variant['optimized']['turns']} "
                f"timeouts={int(by_variant['baseline']['timed_out'])}/{int(by_variant['optimized']['timed_out'])} "
                f"valid={int(by_variant['baseline']['valid'])}/{int(by_variant['optimized']['valid'])}",
                flush=True,
            )

    for variant in ("baseline", "optimized"):
        rows = [row for row in report["results"] if row["variant"] == variant]
        print(f"{variant}: passed={sum(row['passed'] for row in rows)}/{len(rows)} turns={sum(row['turns'] for row in rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
