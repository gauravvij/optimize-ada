"""X3 zero-cost kwargs->env binding test for AdaBridgeAgent.

Loads eval/ada-agent/ada_agent.py via importlib.util.spec_from_file_location
(the hyphenated directory is NOT a Python package), instantiates a default
instance and an effort_realism instance, and asserts _bridge_env() carries the
expected ADA_* vars.
"""
import importlib.util
import sys
from pathlib import Path

ADA = Path("/root/optimize_ada/eval/ada-agent/ada_agent.py")
spec = importlib.util.spec_from_file_location("ada_agent_x3", ADA)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)
AdaBridgeAgent = mod.AdaBridgeAgent


def make(logs: Path, **kw):
    return AdaBridgeAgent(logs_dir=logs, **kw)


# --- default instance: all gates must be OFF (baseline clean) ----------------
d = make(Path("/tmp/x3-logs-default"))
env = d._bridge_env()
leak = {k: v for k, v in env.items() if k.startswith("ADA_")}
assert leak == {}, f"DEFAULT NOT CLEAN: {leak}"
assert d.effort_realism is False
assert d.verify_against_criteria is False
assert d.verify_once is False
assert d.concision_guidance is False
assert d.self_verify is False
assert d.adaptive_concision is False
assert d.lever_debug is False
print("X3 BINDING OK: default clean (no ADA_* keys set)")

# --- effort_realism instance ------------------------------------------------
x = make(Path("/tmp/x3-logs-treat"), effort_realism=True)
env = x._bridge_env()
assert env.get("ADA_EFFORT_REALISM") == "1", env
others = {
    k: v
    for k, v in env.items()
    if k.startswith("ADA_") and k != "ADA_EFFORT_REALISM"
}
assert others == {}, f"UNEXPECTED ADA_*: {others}"
print("X3 BINDING OK: effort_realism -> ADA_EFFORT_REALISM=1 (only ADA_* key set)")

# --- combined instance with lever_debug (probe shape) ------------------------
p = make(Path("/tmp/x3-logs-probe"), effort_realism=True, lever_debug=True)
env = p._bridge_env()
assert env.get("ADA_EFFORT_REALISM") == "1"
assert env.get("ADA_LEVER_DEBUG") == "1"
print("X3 BINDING OK: effort_realism + lever_debug both bound")

print("ALL X3 BINDING TESTS PASSED")
