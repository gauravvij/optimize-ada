#!/usr/bin/env python3
"""Development adapter for optimizing Ada on actual SetupBench tasks."""

from __future__ import annotations

import argparse
import concurrent.futures
import collections
import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from setupbench_ada_eval import (
    BENCHMARK_RUNNER,
    HARNESS,
    MODEL,
    NODE_BINARY,
    NODE_MODULES,
    ROOT,
    SETUPBENCH,
    SETUPBENCH_DEV_12,
    SETUPBENCH_VALIDATION_12,
    command,
    image_id,
    load_scenarios,
    prepared_input,
    resolved_image,
    revision,
    run_variant,
)


# Fixed before the new optimization run. Selection used only task metadata and a
# stable SHA-256 ordering, with proportional quotas across SetupBench categories.
# Repositories sharing a repo_url never cross the development/validation split.
CACHE = HARNESS / ".setupbench_cache"
SELECTION_SEED = "setupbench-ada-v2"
ALLOWED_CHANGE_ROOTS = ("agent/",)
IGNORED_WORKSPACE_PATHS = {"AUTORESEARCH_TASK.md", "node_modules"}


def load_tasks_file(path: str, scenarios: dict[str, dict[str, Any]]) -> tuple[str, ...]:
    """Read one task ID per line from `path`, validated against the catalog.

    Unknown or duplicated IDs are hard errors: a silently-truncated or
    misspelled subset would corrupt any paired comparison built on it.
    """
    file = Path(path)
    if not file.is_file():
        raise SystemExit(f"--tasks-file not found: {path}")
    ids: list[str] = []
    for line in file.read_text().splitlines():
        task_id = line.strip()
        if not task_id or task_id.startswith("#"):
            continue
        ids.append(task_id)
    if not ids:
        raise SystemExit(f"--tasks-file contains no task IDs: {path}")
    unknown = [task_id for task_id in ids if task_id not in scenarios]
    if unknown:
        raise SystemExit(f"--tasks-file contains unknown task IDs: {unknown}")
    duplicates = sorted({task_id for task_id in ids if ids.count(task_id) > 1})
    if duplicates:
        raise SystemExit(f"--tasks-file contains duplicated task IDs: {duplicates}")
    return tuple(ids)


def split_tasks(name: str, scenarios: dict[str, dict[str, Any]]) -> tuple[str, ...]:
    if name == "dev":
        return SETUPBENCH_DEV_12
    if name == "validation":
        return SETUPBENCH_VALIDATION_12
    if name == "full93":
        return tuple(sorted(scenarios))
    held_out = set(SETUPBENCH_DEV_12)
    return tuple(task_id for task_id in sorted(scenarios) if task_id not in held_out)


def verify_split(scenarios: dict[str, dict[str, Any]]) -> None:
    if len(scenarios) != 93:
        raise RuntimeError(f"expected 93 SetupBench tasks, found {len(scenarios)}")
    if len(SETUPBENCH_DEV_12) != 12 or len(SETUPBENCH_VALIDATION_12) != 12:
        raise RuntimeError("development and validation suites must each contain 12 tasks")
    if set(SETUPBENCH_DEV_12) & set(SETUPBENCH_VALIDATION_12):
        raise RuntimeError("development and validation suites overlap")
    if any(task not in scenarios for task in SETUPBENCH_DEV_12 + SETUPBENCH_VALIDATION_12):
        raise RuntimeError("split contains an unknown SetupBench task")
    dev_urls = {scenarios[t].get("repo_url") for t in SETUPBENCH_DEV_12 if scenarios[t].get("repo_url")}
    val_urls = {
        scenarios[t].get("repo_url") for t in SETUPBENCH_VALIDATION_12 if scenarios[t].get("repo_url")
    }
    if dev_urls & val_urls:
        raise RuntimeError("a repository URL crosses the development/validation boundary")
    counts = collections.Counter(scenarios[t]["task_type"] for t in SETUPBENCH_DEV_12)
    if counts != {"reposetup": 7, "dependency_resolution": 2, "dbsetup": 2, "bgsetup": 1}:
        raise RuntimeError(f"development suite violates its category quotas: {dict(counts)}")
    used_urls: set[str] = set()
    quotas = {"reposetup": 14, "dependency_resolution": 4, "dbsetup": 4, "bgsetup": 2}
    expected_dev: list[str] = []
    expected_val: list[str] = []
    for task_type, quota in quotas.items():
        ranked = sorted(
            (task for task in scenarios.values() if task["task_type"] == task_type),
            key=lambda task: hashlib.sha256(
                f"{SELECTION_SEED}:{task['instance_id']}".encode()
            ).hexdigest(),
        )
        picked: list[dict[str, Any]] = []
        for task in ranked:
            repo_url = task.get("repo_url")
            if repo_url and repo_url in used_urls:
                continue
            picked.append(task)
            if repo_url:
                used_urls.add(repo_url)
            if len(picked) == quota:
                break
        expected_dev.extend(task["instance_id"] for task in picked[: quota // 2])
        expected_val.extend(task["instance_id"] for task in picked[quota // 2 :])
    if tuple(expected_dev) != SETUPBENCH_DEV_12 or tuple(expected_val) != SETUPBENCH_VALIDATION_12:
        raise RuntimeError("checked-in split does not match the declared metadata-only selection rule")


def cache_manifest(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "setupbench_commit": revision(SETUPBENCH),
        "instance_id": task["instance_id"],
        "repo_url": task.get("repo_url"),
        "base_commit": task.get("base_commit"),
    }


def cache_path(task_id: str) -> Path:
    return CACHE / "inputs" / task_id


def prepare_task(task: dict[str, Any]) -> Path:
    destination = cache_path(task["instance_id"])
    marker = destination / ".setupbench-cache.json"
    expected = cache_manifest(task)
    if marker.is_file() and json.loads(marker.read_text()) == expected:
        return destination
    if destination.exists():
        raise RuntimeError(f"stale cache requires manual inspection: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    building = destination.with_name(f"{destination.name}.building")
    if building.exists():
        shutil.rmtree(building)
    with prepared_input(task) as source:
        shutil.copytree(source, building, symlinks=True)
    (building / ".setupbench-cache.json").write_text(json.dumps(expected, sort_keys=True) + "\n")
    building.rename(destination)
    return destination


def require_prepared(task: dict[str, Any]) -> Path:
    destination = cache_path(task["instance_id"])
    marker = destination / ".setupbench-cache.json"
    if not marker.is_file() or json.loads(marker.read_text()) != cache_manifest(task):
        raise RuntimeError(f"task input was not prepared before measurement: {task['instance_id']}")
    image = resolved_image(task)
    if command(["docker", "image", "inspect", image], timeout=30).returncode != 0:
        raise RuntimeError(f"container image was not prepared before measurement: {image}")
    return destination


def changed_paths(workspace: Path) -> list[str]:
    status = command(
        ["git", "-C", str(workspace), "status", "--porcelain=v1", "--untracked-files=all"], check=True
    ).stdout
    paths: list[str] = []
    for line in status.splitlines():
        raw = line[3:]
        if " -> " in raw:
            raw = raw.split(" -> ", 1)[1]
        paths.append(raw.strip('"'))
    return sorted(paths)


def enforce_mutation_boundary(workspace: Path) -> list[str]:
    changes = [p for p in changed_paths(workspace) if p not in IGNORED_WORKSPACE_PATHS and not p.startswith(".autoresearch/")]
    illegal = [p for p in changes if not p.startswith(ALLOWED_CHANGE_ROOTS)]
    if illegal:
        raise RuntimeError(f"candidate changed immutable paths: {illegal}")
    return changes


def diagnostic_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: row.get(key)
        for key in (
            "task_id", "task_type", "passed", "valid", "timed_out", "turns",
            "duration_seconds", "terminal_result", "agent_is_error", "agent_stop_reason",
            "grader_returncode", "harness_error",
            # Usage/cost capture (§8.1): the runner already parses per-task
            # token usage from the agent result; surface it in diagnostics.
            "input_tokens", "output_tokens", "cache_read_tokens",
            # Evidence fields: all populated only when ADA_EVAL_EVIDENCE_DIR is set or the run reports them.
            "cache_creation_tokens", "models_seen", "cost_cli_usd", "turns_from_trace",
            "started_at_utc", "evidence_error",
        )
    }


def usage_summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "input_tokens": sum(int(row.get("input_tokens") or 0) for row in rows),
        "output_tokens": sum(int(row.get("output_tokens") or 0) for row in rows),
        "cache_read_tokens": sum(int(row.get("cache_read_tokens") or 0) for row in rows),
        "cache_creation_tokens": sum(int(row.get("cache_creation_tokens") or 0) for row in rows),
    }


def failure_detail(row: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": row["task_id"],
        "task_type": row["task_type"],
        "problem_statement": task["problem_statement"],
        "success_command": task["success_command"],
        "agent_result": row.get("agent_result"),
        "grader_output": row.get("grader_output"),
        "agent_log_tail": row.get("agent_log_tail"),
        "agent_trace_tail": str(row.get("agent_trace_tail") or "")[-6000:],
    }


def run_suite(workspace: Path, selected: tuple[str, ...], scenarios: dict[str, dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    inputs = {task_id: require_prepared(scenarios[task_id]) for task_id in selected}
    order = list(selected)
    random.Random(args.seed).shuffle(order)
    # Incremental per-task row writes (§8.3): every completed task is appended
    # to a JSONL sidecar immediately, so a killed or crashed run keeps its
    # partial results. The final diagnostic JSON is still written at the end
    # with the unchanged schema.
    run_id = os.environ.get("AUTORESEARCH_RUN_ID", "manual")
    experiment = os.environ.get("AUTORESEARCH_EXPERIMENT_NUMBER", "manual")
    # Attempt-suffix so repeated evaluations (evaluation.candidate_repetitions > 1)
    # never overwrite each other's diagnostics. Absent -> legacy filename.
    attempt = os.environ.get("AUTORESEARCH_ATTEMPT_NUMBER", "")
    suffix = f".attempt{attempt}" if attempt else ""
    partial_path = workspace / ".autoresearch" / "diagnostics" / run_id / f"{experiment}{suffix}.partial.jsonl"
    partial_path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = {
            executor.submit(
                run_variant,
                scenarios[task_id],
                inputs[task_id],
                "candidate",
                args.task_timeout_seconds,
                args.grader_timeout_seconds,
                workspace,
            ): task_id
            for task_id in order
        }
        for future in concurrent.futures.as_completed(futures):
            row = future.result()
            rows.append(row)
            with partial_path.open("a") as partial:
                partial.write(json.dumps(diagnostic_row(row), sort_keys=True) + "\n")
            print(
                f"task={row['task_id']} pass={int(row['passed'])} valid={int(row['valid'])} "
                f"timeout={int(row['timed_out'])} turns={row['turns']}",
                flush=True,
            )
    return sorted(rows, key=lambda row: row["task_id"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("suite", choices=("dev", "validation", "remaining81", "full93"), nargs="?", default="dev")
    parser.add_argument("--tasks-file", default=None,
                        help="path to a file with one task ID per line (overrides the suite selector; validated against the catalog)")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--task-timeout-seconds", type=int, default=480)
    parser.add_argument("--grader-timeout-seconds", type=int, default=600)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--seed", type=int, default=20260907)
    args = parser.parse_args()
    if not 1 <= args.concurrency <= 8:
        raise SystemExit("concurrency must be between 1 and 8")
    workspace = Path(args.workspace).resolve()
    scenarios = load_scenarios()
    verify_split(scenarios)
    if args.tasks_file:
        selected = load_tasks_file(args.tasks_file, scenarios)
    else:
        selected = split_tasks(args.suite, scenarios)

    if args.prepare_only:
        images = sorted({resolved_image(scenarios[task_id]) for task_id in selected})
        for image in images:
            pulled = command(["docker", "pull", image], timeout=600)
            if pulled.returncode != 0:
                raise RuntimeError(f"image unavailable: {image}: {pulled.stderr[-1000:]}")
            print(f"image ready: {image} ({image_id(image)})", flush=True)
        for index, task_id in enumerate(selected, 1):
            path = prepare_task(scenarios[task_id])
            print(f"input ready: {index}/{len(selected)} {task_id} -> {path}", flush=True)
        return 0

    if not os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        key = os.environ.get("OPENROUTER_API_KEY")
        if not key:
            raise SystemExit("OPENROUTER_API_KEY is missing")
        os.environ["ANTHROPIC_AUTH_TOKEN"] = key
    for required in (workspace, SETUPBENCH, NODE_MODULES, NODE_BINARY):
        if not required.exists():
            raise SystemExit(f"required path is missing: {required}")
    changes = enforce_mutation_boundary(workspace)
    rows = run_suite(workspace, selected, scenarios, args)
    invalid = [row for row in rows if not row["valid"]]
    for row in invalid:
        print(f"invalid task={row['task_id']} error={row['harness_error']}", file=sys.stderr)

    run_id = os.environ.get("AUTORESEARCH_RUN_ID", "manual")
    experiment = os.environ.get("AUTORESEARCH_EXPERIMENT_NUMBER", "manual")
    attempt = os.environ.get("AUTORESEARCH_ATTEMPT_NUMBER", "")
    suffix = f".attempt{attempt}" if attempt else ""
    diagnostic = workspace / ".autoresearch" / "diagnostics" / run_id / f"{experiment}{suffix}.json"
    diagnostic.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "protocol": {
            "suite": args.suite,
            "tasks_file": args.tasks_file,
            "tasks": list(selected),
            "selection_seed": SELECTION_SEED,
            "setupbench_commit": revision(SETUPBENCH),
            "model": MODEL,
            "task_timeout_seconds": args.task_timeout_seconds,
            "grader_timeout_seconds": args.grader_timeout_seconds,
            "concurrency": args.concurrency,
            "runner_sha256": hashlib.sha256(BENCHMARK_RUNNER.read_bytes()).hexdigest(),
            "evaluator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "grader_workdir": "/testbed",
            "metric": "number of tasks passing official executable graders",
        },
        "workspace_commit": revision(workspace),
        # HEAD can carry docs-only commits; the agent tree hash is what actually ran.
        "agent_tree": subprocess.run(["git", "-C", str(workspace), "rev-parse", "HEAD:agent"],
                                     capture_output=True, text=True, check=True).stdout.strip(),
        "changed_paths": changes,
        "summary": {
            "passed": sum(row["passed"] for row in rows),
            "total": len(rows),
            "timeouts": sum(row["timed_out"] for row in rows),
            "turns": sum(row["turns"] for row in rows),
            "invalid": len(invalid),
            "usage": usage_summary(rows),
        },
        "results": [diagnostic_row(row) for row in rows],
        "failure_details": [failure_detail(row, scenarios[row["task_id"]]) for row in rows if not row["passed"]],
    }
    diagnostic.write_text(json.dumps(report, indent=2) + "\n")
    print(
        f"summary pass={report['summary']['passed']}/{len(rows)} "
        f"timeouts={report['summary']['timeouts']} turns={report['summary']['turns']}",
        flush=True,
    )
    if invalid:
        # Diagnostics are written first so an unlucky arm keeps its per-task data;
        # the non-zero exit still stops the autoresearch loop from scoring it.
        return 2
    print(f"AUTORESEARCH_METRIC={report['summary']['passed']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
