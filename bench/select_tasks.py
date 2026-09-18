#!/usr/bin/env python3
"""Parse terminal-bench-2 task metadata and rank for fastest-10 selection.

Ranking: difficulty (easy first, then medium, then hard), then
expert_time_estimate_min ascending, then agent.timeout_sec ascending.
"""
import os
import sys

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore

BASE = "/home/azureuser/adaAgent/bench/terminal-bench-2"
DIFF_ORDER = {"easy": 0, "medium": 1, "hard": 2, "expert": 3}

rows = []
for name in sorted(os.listdir(BASE)):
    tpath = os.path.join(BASE, name, "task.toml")
    if not os.path.isfile(tpath):
        continue
    with open(tpath, "rb") as f:
        data = tomllib.load(f)
    task = data.get("task", {})
    meta = data.get("metadata", {})
    agent = data.get("agent", {})
    env = data.get("environment", {})
    full_name = task.get("name", name)
    short = full_name.split("/")[-1] if "/" in full_name else full_name
    rows.append({
        "dir": name,
        "name": short,
        "difficulty": meta.get("difficulty", "unknown"),
        "expert_min": meta.get("expert_time_estimate_min", 9999.0),
        "junior_min": meta.get("junior_time_estimate_min", 9999.0),
        "agent_timeout": agent.get("timeout_sec", 9999.0),
        "verifier_timeout": data.get("verifier", {}).get("timeout_sec", 9999.0),
        "image": env.get("docker_image", "?"),
        "allow_internet": env.get("allow_internet", "?"),
        "cpus": env.get("cpus", "?"),
        "memory_mb": env.get("memory_mb", "?"),
        "category": meta.get("category", "?"),
    })

rows.sort(key=lambda r: (
    DIFF_ORDER.get(r["difficulty"], 9),
    r["expert_min"],
    r["agent_timeout"],
))

print(f"Total tasks: {len(rows)}")
print("\nDifficulty distribution:")
from collections import Counter
print(dict(Counter(r["difficulty"] for r in rows)))

print("\n=== Top 20 fastest (difficulty easy-first, then expert_min, then timeout) ===")
hdr = f"{'#':>2} {'name':<40} {'diff':<7} {'exp_min':>8} {'ag_timeout':>10} {'internet':>8} {'category':<25}"
print(hdr)
print("-" * len(hdr))
for i, r in enumerate(rows[:20], 1):
    print(f"{i:>2} {r['name']:<40} {r['difficulty']:<7} {r['expert_min']:>8} {r['agent_timeout']:>10} {str(r['allow_internet']):>8} {r['category']:<25}")

print("\n=== Full ranked list ===")
for i, r in enumerate(rows, 1):
    print(f"{i:>3} {r['name']:<45} {r['difficulty']:<7} exp={r['expert_min']:>6} agent_to={r['agent_timeout']:>7} net={r['allow_internet']}")
