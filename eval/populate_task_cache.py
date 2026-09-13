#!/usr/bin/env python3
"""Pre-populate Harbor's task cache for terminal-bench@2.0.

Harbor 0.22.0 resolves `terminal-bench@2.0` via registry.json, which pins
git_url=https://github.com/laude-institute/terminal-bench-2.git (dead, repo moved
to harbor-framework/terminal-bench-2) at commit 69671fbaac6d67a7ef0dfec016cc38a64ef7a77c.

TaskClient._download_git_tasks skips any task whose cache path already exists:
    TASK_CACHE_DIR / shortuuid.uuid(str(GitTaskId)) / task_name
So we clone the live repo at the pinned commit and copy each needed task dir
into its deterministic cache path. No harbor code is modified.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

GIT_URL = "https://github.com/harbor-framework/terminal-bench-2.git"
COMMIT = "69671fbaac6d67a7ef0dfec016cc38a64ef7a77c"
CLONE_DIR = Path("/tmp/tb2-clone")
CACHE = Path.home() / ".cache/harbor/tasks"
CONFIG = Path("/root/optimize_ada/eval/config.json")


def main():
    tasks = json.loads(CONFIG.read_text())["task_subset"]["tasks"]
    print(f"[1/4] Subset tasks ({len(tasks)}): {tasks}")

    # 1. Clone the live repo at the pinned commit
    if not (CLONE_DIR / ".git").exists():
        CLONE_DIR.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "clone", "--filter=blob:none", "--no-checkout", GIT_URL, str(CLONE_DIR)],
            check=True,
        )
    subprocess.run(["git", "fetch", "--depth", "1", "origin", COMMIT], cwd=CLONE_DIR, check=True)
    subprocess.run(["git", "checkout", COMMIT], cwd=CLONE_DIR, check=True)
    print(f"[2/4] Cloned {GIT_URL} @ {COMMIT[:12]}")

    # 2. Compute deterministic cache paths (must match harbor's shortuuid scheme)
    sys.path.insert(0, "/root/optimize_ada/venv/lib/python3.12/site-packages")
    from harbor.models.task.id import GitTaskId
    import shortuuid

    missing_src, populated, already = [], [], []
    for name in tasks:
        src = CLONE_DIR / name
        if not src.exists():
            missing_src.append(name)
            continue
        tid = GitTaskId(
            git_url="https://github.com/laude-institute/terminal-bench-2.git",
            git_commit_id=COMMIT,
            path=Path(name),
        )
        target = CACHE / shortuuid.uuid(str(tid)) / name
        if target.exists() and any(target.iterdir()):
            already.append(name)
            continue
        if target.exists():
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, target)
        populated.append(name)

    print(f"[3/4] Populated {len(populated)}: {populated}")
    print(f"      Already cached {len(already)}: {already}")
    if missing_src:
        print(f"      MISSING IN REPO {len(missing_src)}: {missing_src}")
        sys.exit(1)

    # 3. Verify each cache dir has the expected task structure
    bad = []
    for name in tasks:
        tid = GitTaskId(
            git_url="https://github.com/laude-institute/terminal-bench-2.git",
            git_commit_id=COMMIT,
            path=Path(name),
        )
        d = CACHE / shortuuid.uuid(str(tid)) / name
        has_task = (d / "task.yaml").exists() or (d / "task.toml").exists()
        if not has_task:
            bad.append((name, sorted(p.name for p in d.iterdir())[:6]))
    if bad:
        print(f"[4/4] FAIL - dirs without task manifest: {bad}")
        sys.exit(1)
    print(f"[4/4] All {len(tasks)} cache dirs verified (task manifest present).")


if __name__ == "__main__":
    main()