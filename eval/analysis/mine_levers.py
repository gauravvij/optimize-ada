#!/usr/bin/env python3
"""Mine the 180-trial Ada eval trace corpus for optimization levers.

ANALYSIS ONLY: reads job dirs + results JSONLs, writes lever-data.json and
prints a structured digest. No API spend, no harbor runs, no code changes.

Corpus:
  eval/jobs/baseline-armA  (60 trials, reference claude-code agent)
  eval/jobs/baseline-armB  (60 trials, Ada bridge)
  eval/jobs/e-opt1-arm     (60 trials, Ada bridge + concision guidance)
  eval/results/*.jsonl     (per-trial pass/cost/token records)

Covers 8 mining areas:
  1. failure taxonomy (ctrf.json per-test status/trace -> failure modes)
  2. near-miss distance-to-pass
  3. timeout forensics (phase timings, mid-progress-at-cutoff detection)
  4. loop/stall detection (dup tool calls in ada-events; >=120s gaps arm A)
  5. turn economics + arm-B wall-time mechanism (phase decomposition)
  6. cache-break forensics (cache-read ratio < 0.8)
  7. E-opt1 flip mechanisms (per-task B vs E flips + failed-test detail)
  8. arm-A ALL-FAIL session forensics (tool histograms, final text)
"""
import json, os, re, glob
from collections import Counter, defaultdict
from datetime import datetime

ROOT = "/root/optimize_ada/eval"
ARMS = {
    "A": {"jobs": f"{ROOT}/jobs/baseline-armA", "jsonl": f"{ROOT}/results/baseline-armA.jsonl"},
    "B": {"jobs": f"{ROOT}/jobs/baseline-armB", "jsonl": f"{ROOT}/results/baseline-armB.jsonl"},
    "E": {"jobs": f"{ROOT}/jobs/e-opt1-arm", "jsonl": f"{ROOT}/results/e-opt1-arm.jsonl"},
}
OUT = f"{ROOT}/analysis/lever-data.json"


def ts(s):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def dur(a, b):
    x, y = ts(a), ts(b)
    if x and y:
        return round((y - x).total_seconds(), 1)
    return None


def load_jsonl(path):
    recs = []
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if line:
                try:
                    recs.append(json.loads(line))
                except Exception:
                    pass
    return recs


# ------------------------------------------------------------- ctrf parsing
def classify_fail(t):
    trace = t.get("trace") or ""
    msg = t.get("message") or ""
    blob = trace + " " + msg
    if re.search(r"FileNotFoundError|No such file or directory", blob):
        return "missing_file"
    if re.search(r"HTTP 000|curl \(\d+\)|Connection refused|Failed to connect", blob, re.I):
        return "connection/http-000"
    if re.search(r"Timeout|timed out", blob, re.I):
        return "timeout"
    if re.search(r"assert", blob, re.I):
        return "assertion_mismatch"
    return "other"


def parse_ctrf(path):
    if not os.path.exists(path):
        return None, None, []
    try:
        d = json.load(open(path))
    except Exception:
        return None, None, []
    summ = d.get("results", {}).get("summary", {})
    tests = d.get("results", {}).get("tests", [])
    out = []
    for t in tests:
        out.append({
            "name": t.get("name"), "status": t.get("status"),
            "mode": "passed" if t.get("status") == "passed" else classify_fail(t),
            "message": (t.get("message") or "")[:250],
            "trace_head": (t.get("trace") or "")[:250],
        })
    return summ.get("passed"), summ.get("failed"), out


def parse_result_json(path):
    if not os.path.exists(path):
        return {}
    try:
        d = json.load(open(path))
    except Exception:
        return {}
    ph = {}
    for k in ("environment_setup", "agent_setup", "agent_execution", "verifier"):
        v = d.get(k) or {}
        ph[k] = dur(v.get("started_at"), v.get("finished_at"))
    exc = d.get("exception_info")
    ar = d.get("agent_result") or {}
    return {
        "phases": ph,
        "total": dur(d.get("started_at"), d.get("finished_at")),
        "cost": ar.get("cost_usd"),
        "in_tok": ar.get("n_input_tokens"),
        "cache_tok": ar.get("n_cache_tokens"),
        "out_tok": ar.get("n_output_tokens"),
        "exception": (exc or {}).get("exception_type") if exc else None,
        "agent_exec_started": (d.get("agent_execution") or {}).get("started_at"),
        "agent_exec_finished": (d.get("agent_execution") or {}).get("finished_at"),
    }


# ------------------------------------------------- ada-events (arms B / E)
def parse_ada_events(path):
    if not os.path.exists(path):
        return {}
    calls = []            # (name, args-prefix)
    cur = {}              # toolCallId -> [name, args]
    n_text = 0
    finished = None
    n_events = 0
    for line in open(path, errors="replace"):
        n_events += 1
        try:
            d = json.loads(line)
        except Exception:
            continue
        dd = d.get("data", {})
        t = dd.get("type")
        if t == "TOOL_CALL_START":
            cur[dd.get("toolCallId")] = [dd.get("toolCallName", "?"), ""]
        elif t == "TOOL_CALL_ARGS":
            if dd.get("toolCallId") in cur:
                cur[dd.get("toolCallId")][1] += dd.get("delta", "")
        elif t == "TOOL_CALL_END":
            tid = dd.get("toolCallId")
            name, args = cur.pop(tid, ["?", ""])
            calls.append((name, args[:200]))
        elif t == "TEXT_MESSAGE_START":
            n_text += 1
        elif t == "RUN_FINISHED":
            finished = (dd.get("result") or "")[:1500]
    sig = Counter(calls)
    dups = {f"{n}({a[:60]})": c for (n, a), c in sig.items() if c >= 3}
    max_run, run = 0, 1
    for i in range(1, len(calls)):
        if calls[i] == calls[i - 1]:
            run += 1
            max_run = max(max_run, run)
        else:
            run = 1
    return {
        "n_tool_calls": len(calls),
        "n_assistant_msgs": n_text,
        "tool_hist": dict(Counter(n for n, _ in calls)),
        "dup_calls_3plus": dups,
        "max_consecutive_identical": max_run,
        "n_events": n_events,
        "final_result": finished,
    }


# ------------------------------------------- session log (arm A, timestamped)
def parse_session_log(path):
    if not os.path.exists(path):
        return {}
    msgs = []
    for line in open(path, errors="replace"):
        try:
            d = json.loads(line)
        except Exception:
            continue
        t = d.get("timestamp")
        if not t:
            continue
        m = d.get("message") or {}
        msgs.append({"ts": t, "rec": d.get("type"), "mt": m.get("type"),
                     "content": m.get("content")})
    if not msgs:
        return {}
    times = [ts(m["ts"]) for m in msgs]
    times = [x for x in times if x]
    gaps = []
    for i in range(1, len(times)):
        g = (times[i] - times[i - 1]).total_seconds()
        if g > 0:
            gaps.append((round(g, 1), msgs[i]["ts"]))
    gaps.sort(reverse=True)
    tools = Counter()
    n_assistant = 0
    last_text = ""
    for m in msgs:
        # claude-code session logs: record type 'assistant', message.type 'message'
        if m["rec"] == "assistant" or m["mt"] == "assistant":
            n_assistant += 1
            c = m["content"]
            if isinstance(c, list):
                for blk in c:
                    if isinstance(blk, dict):
                        if blk.get("type") == "tool_use":
                            tools[blk.get("name")] += 1
                        elif blk.get("type") == "text" and blk.get("text"):
                            last_text = blk["text"][:1500]
    return {
        "n_msgs": len(msgs), "n_assistant": n_assistant,
        "tool_hist": dict(tools), "n_tool_calls": sum(tools.values()),
        "max_gap_s": gaps[0][0] if gaps else 0,
        "top_gaps": gaps[:5],
        "first_ts": msgs[0]["ts"], "last_ts": msgs[-1]["ts"],
        "final_text": last_text,
    }


# --------------------------- stream-json capture (arm A fallback, no timestamps)
def parse_streamjson(path):
    """claude-code.txt stream-json: same schema as session log minus timestamps."""
    tools = Counter()
    n_assistant = 0
    last_text = ""
    for line in open(path, errors="replace"):
        try:
            d = json.loads(line)
        except Exception:
            continue
        m = d.get("message") or {}
        if d.get("type") == "assistant" or m.get("type") == "assistant":
            n_assistant += 1
            c = m.get("content")
            if isinstance(c, list):
                for blk in c:
                    if isinstance(blk, dict):
                        if blk.get("type") == "tool_use":
                            tools[blk.get("name")] += 1
                        elif blk.get("type") == "text" and blk.get("text"):
                            last_text = blk["text"][:1500]
    return {
        "n_msgs": None, "n_assistant": n_assistant,
        "tool_hist": dict(tools), "n_tool_calls": sum(tools.values()),
        "max_gap_s": None, "top_gaps": [],
        "first_ts": None, "last_ts": None,
        "final_text": last_text, "source": "streamjson",
    }


# ------------------------------------------------------------- trial scan
def scan_arm(arm):
    cfg = ARMS[arm]
    recs = {r["trial"]: r for r in load_jsonl(cfg["jsonl"])}
    trials = {}
    for tdir in sorted(glob.glob(f"{cfg['jobs']}/*__*")):
        tname = os.path.basename(tdir)
        rec = recs.get(tname, {})
        rj = parse_result_json(f"{tdir}/result.json")
        p, f, tests = parse_ctrf(f"{tdir}/verifier/ctrf.json")
        tr = {
            "task": rec.get("task", tname.rsplit("__", 1)[0]),
            "pass": rec.get("pass"), "cost": rec.get("cost_usd"),
            "in_tok": rec.get("n_input_tokens"),
            "cache_tok": rec.get("n_cache_tokens"),
            "out_tok": rec.get("n_output_tokens"),
            "num_turns": rec.get("num_turns"),
            "ttft_ms": rec.get("ttft_ms"), "duration_ms": rec.get("duration_ms"),
            "error": rec.get("error"), "error_info": rec.get("error_info"),
            "tests_passed": p, "tests_failed": f, "tests": tests,
        }
        tr.update(rj)
        ev = f"{tdir}/agent/ada-events.jsonl"
        if os.path.exists(ev):
            tr["ada"] = parse_ada_events(ev)
        sess = glob.glob(f"{tdir}/agent/sessions/projects/-app/*.jsonl")
        if sess:
            tr["sess"] = parse_session_log(sess[0])
        else:
            # fallback: stream-json capture (no timestamps -> gaps unavailable)
            cc = f"{tdir}/agent/claude-code.txt"
            if os.path.exists(cc):
                tr["sess"] = parse_streamjson(cc)
        trials[tname] = tr
    return trials


def main():
    data = {arm: scan_arm(arm) for arm in ARMS}
    S = {}

    # ---- 0. counts
    S["trial_counts"] = {a: len(t) for a, t in data.items()}

    # ---- 1. failure taxonomy
    tax = defaultdict(Counter)
    for arm, trials in data.items():
        for tn, tr in trials.items():
            if tr["pass"] == 1.0:
                continue
            for t in tr.get("tests", []):
                if t["status"] != "passed":
                    tax[f"{tr['task']}/{arm}"][t["mode"]] += 1
    S["failure_taxonomy"] = {k: dict(v) for k, v in tax.items()}
    S["failure_mode_totals_by_arm"] = {
        arm: dict(sum((Counter() if tr["pass"] == 1.0 else
                       Counter(t["mode"] for t in tr.get("tests", []) if t["status"] != "passed")
                       for tr in trials.values()), Counter()))
        for arm, trials in data.items()}

    # ---- 2. near-miss distance-to-pass
    nm = []
    for arm, trials in data.items():
        for tn, tr in trials.items():
            if tr["pass"] == 1.0 or tr["tests_passed"] is None:
                continue
            tot = (tr["tests_passed"] or 0) + (tr["tests_failed"] or 0)
            if tot and tr["tests_failed"]:
                nm.append({
                    "arm": arm, "task": tr["task"], "trial": tn,
                    "passed": tr["tests_passed"], "failed": tr["tests_failed"],
                    "frac": round(tr["tests_passed"] / tot, 3),
                    "failed_tests": [t["name"] for t in tr["tests"] if t["status"] != "passed"],
                    "modes": [t["mode"] for t in tr["tests"] if t["status"] != "passed"],
                    "messages": [t["message"] for t in tr["tests"] if t["status"] != "passed"][:2],
                })
    nm.sort(key=lambda x: -x["frac"])
    S["near_misses"] = nm
    S["near_misses_ge_0.5"] = [n for n in nm if n["frac"] >= 0.5]
    S["near_misses_ge_0.34_lt_0.5"] = [n for n in nm if 0.34 <= n["frac"] < 0.5]
    # per-task near-miss aggregation
    agg = defaultdict(list)
    for n in nm:
        agg[f"{n['task']}/{n['arm']}"].append(n["frac"])
    S["near_miss_frac_by_task_arm"] = {k: sorted(v, reverse=True) for k, v in agg.items()}

    # ---- 3. timeout forensics
    tmo = []
    for arm, trials in data.items():
        for tn, tr in trials.items():
            ae = (tr.get("phases") or {}).get("agent_execution")
            sess = tr.get("sess", {})
            ada = tr.get("ada", {})
            mid = None
            if sess.get("last_ts") and tr.get("agent_exec_finished"):
                lt, ft = ts(sess["last_ts"]), ts(tr["agent_exec_finished"])
                if lt and ft:
                    mid = round((ft - lt).total_seconds(), 1)
            tmo.append({
                "arm": arm, "task": tr["task"], "trial": tn,
                "pass": tr["pass"],
                "agent_exec_s": ae, "total_s": tr.get("total"),
                "exception": tr.get("exception"),
                "error": tr.get("error"),
                "last_msg_before_finish_s": mid,
                "n_tool_calls": (ada or sess or {}).get("n_tool_calls"),
                "has_RUN_FINISHED": bool(ada.get("final_result")),
                "n_msgs": sess.get("n_msgs"),
            })
    S["longest_agent_exec"] = sorted(
        [t for t in tmo if t["agent_exec_s"] is not None],
        key=lambda x: -x["agent_exec_s"])[:15]
    S["exception_trials"] = [t for t in tmo if t["exception"] or t["error"]]

    # ---- 4. loop/stall detection
    loops = []
    for arm in ("B", "E"):
        for tn, tr in data[arm].items():
            a = tr.get("ada") or {}
            if a.get("max_consecutive_identical", 0) >= 3 or a.get("dup_calls_3plus"):
                loops.append({
                    "arm": arm, "task": tr["task"], "trial": tn,
                    "pass": tr["pass"],
                    "max_run": a.get("max_consecutive_identical"),
                    "dups": a.get("dup_calls_3plus"),
                    "n_tool_calls": a.get("n_tool_calls"),
                })
    S["loop_trials_BE"] = loops
    stalls = []
    for tn, tr in data["A"].items():
        s = tr.get("sess", {})
        if (s.get("max_gap_s") or 0) >= 120:
            stalls.append({
                "task": tr["task"], "trial": tn, "pass": tr["pass"],
                "max_gap_s": s["max_gap_s"],
                "top_gaps": [(g, t) for g, t in s.get("top_gaps", [])[:3]],
            })
    stalls.sort(key=lambda x: -x["max_gap_s"])
    S["armA_stalls_ge_120s"] = stalls

    # ---- 5. turn economics + wall-time mechanism
    ph = defaultdict(list)
    for arm, trials in data.items():
        for tn, tr in trials.items():
            for k, v in (tr.get("phases") or {}).items():
                if v is not None:
                    ph[f"{arm}.{k}"].append(v)
            if tr.get("total") is not None:
                ph[f"{arm}.total"].append(tr["total"])
    S["phase_means_s"] = {k: round(sum(v) / len(v), 1) for k, v in ph.items()}
    S["phase_n"] = {k: len(v) for k, v in ph.items()}
    S["phase_max_s"] = {k: max(v) for k, v in ph.items()}
    for arm in ARMS:
        turns = [tr.get("num_turns") for tr in data[arm].values() if tr.get("num_turns")]
        if turns:
            S[f"{arm}_num_turns_mean"] = round(sum(turns) / len(turns), 2)
        tc = [((tr.get("ada") or tr.get("sess") or {}).get("n_tool_calls"))
              for tr in data[arm].values()
              if (tr.get("ada") or tr.get("sess") or {}).get("n_tool_calls") is not None]
        if tc:
            S[f"{arm}_tool_calls_mean"] = round(sum(tc) / len(tc), 1)
            S[f"{arm}_tool_calls_max"] = max(tc)
        ttft = [tr.get("ttft_ms") for tr in data[arm].values() if tr.get("ttft_ms")]
        if ttft:
            S[f"{arm}_ttft_ms_mean"] = round(sum(ttft) / len(ttft))
        dms = [tr.get("duration_ms") for tr in data[arm].values() if tr.get("duration_ms")]
        if dms:
            S[f"{arm}_duration_ms_mean"] = round(sum(dms) / len(dms))

    # ---- 6. cache-break forensics
    cb = []
    ratios = defaultdict(list)
    for arm, trials in data.items():
        for tn, tr in trials.items():
            if tr.get("in_tok") and tr.get("cache_tok") is not None:
                r = tr["cache_tok"] / tr["in_tok"]
                ratios[arm].append(r)
                if r < 0.8:
                    cb.append({
                        "arm": arm, "task": tr["task"], "trial": tn,
                        "ratio": round(r, 3), "cost": tr.get("cost"),
                        "pass": tr["pass"], "out_tok": tr.get("out_tok"),
                        "in_tok": tr.get("in_tok"),
                        "n_tool_calls": ((tr.get("ada") or tr.get("sess") or {}) or {}).get("n_tool_calls"),
                    })
    cb.sort(key=lambda x: x["ratio"])
    S["cache_break_lt_0.8"] = cb
    S["cache_ratio_by_arm"] = {
        a: {"mean": round(sum(v) / len(v), 3), "min": round(min(v), 3),
            "n_lt_0.8": sum(1 for x in v if x < 0.8), "n": len(v)}
        for a, v in ratios.items()}

    # ---- 7. E-opt1 flip mechanisms
    matrix = {}
    for task in sorted({tr["task"] for tr in data["A"].values()}):
        matrix[task] = {}
        for arm in ARMS:
            trs = [tr for tr in data[arm].values() if tr["task"] == task]
            matrix[task][arm] = {
                "pass_n": sum(1 for t in trs if t["pass"] == 1.0),
                "n": len(trs),
                "mean_cost": round(sum(t["cost"] for t in trs if t["cost"] is not None) /
                                   max(1, sum(1 for t in trs if t["cost"] is not None)), 4),
            }
    S["pass_matrix"] = matrix
    flips = []
    for task, row in matrix.items():
        if row["B"]["pass_n"] != row["E"]["pass_n"]:
            flips.append({"task": task,
                          "A": row["A"]["pass_n"], "B": row["B"]["pass_n"],
                          "E": row["E"]["pass_n"]})
    S["eopt1_flips"] = flips
    # failed-test detail for flipped tasks
    detail = []
    for fl in flips:
        task = fl["task"]
        for arm in ("B", "E"):
            for tn, tr in data[arm].items():
                if tr["task"] == task and tr["pass"] != 1.0 and tr.get("tests"):
                    detail.append({
                        "task": task, "arm": arm, "trial": tn,
                        "passed": tr["tests_passed"], "failed": tr["tests_failed"],
                        "failed_tests": [t["name"] for t in tr["tests"] if t["status"] != "passed"][:4],
                        "modes": [t["mode"] for t in tr["tests"] if t["status"] != "passed"][:4],
                        "n_tool_calls": ((tr.get("ada") or tr.get("sess") or {}) or {}).get("n_tool_calls"),
                        "out_tok": tr.get("out_tok"),
                    })
    S["eopt1_flip_fail_detail"] = detail

    # ---- 8. arm-A ALL-FAIL forensics
    allfail_tasks = []
    for task, row in matrix.items():
        if row["A"]["pass_n"] == 0:
            allfail_tasks.append(task)
    S["armA_allfail_tasks"] = allfail_tasks
    forensics = []
    for task in allfail_tasks:
        for tn, tr in [(k, v) for k, v in data["A"].items() if v["task"] == task][:2]:
            s = tr.get("sess", {})
            forensics.append({
                "task": task, "trial": tn,
                "n_tool_calls": s.get("n_tool_calls"),
                "tool_hist": s.get("tool_hist"),
                "n_assistant": s.get("n_assistant"),
                "max_gap_s": s.get("max_gap_s"),
                "final_text": (s.get("final_text") or "")[:800],
                "failed_tests": [t["name"] for t in tr.get("tests", []) if t["status"] != "passed"][:6],
                "modes": [t["mode"] for t in tr.get("tests", []) if t["status"] != "passed"][:6],
                "messages": [t["message"] for t in tr.get("tests", []) if t["status"] != "passed"][:2],
            })
    S["armA_allfail_forensics"] = forensics

    # persist (trials without bulky per-test detail to keep file sane)
    slim = {arm: {tn: {k: v for k, v in tr.items() if k != "tests"}
                 for tn, tr in trials.items()} for arm, trials in data.items()}
    json.dump({"summary": S, "trials": slim}, open(OUT, "w"), indent=1, default=str)

    # ---- console digest
    print("=== TRIAL COUNTS ===", S["trial_counts"])
    print("\n=== PASS MATRIX (pass_n / n, mean cost) ===")
    for t, r in matrix.items():
        print(f"  {t:30s} A {r['A']['pass_n']}/{r['A']['n']} ${r['A']['mean_cost']}  "
              f"B {r['B']['pass_n']}/{r['B']['n']} ${r['B']['mean_cost']}  "
              f"E {r['E']['pass_n']}/{r['E']['n']} ${r['E']['mean_cost']}")
    print("\n=== PHASE MEANS (s) ===")
    for k in sorted(S["phase_means_s"]):
        print(f"  {k:26s} mean={S['phase_means_s'][k]:>7} max={S['phase_max_s'][k]:>7} n={S['phase_n'][k]}")
    print("\n=== TURN ECONOMICS ===")
    for k in ("A_num_turns_mean", "B_num_turns_mean", "E_num_turns_mean",
              "A_tool_calls_mean", "B_tool_calls_mean", "E_tool_calls_mean",
              "A_tool_calls_max", "B_tool_calls_max", "E_tool_calls_max",
              "B_ttft_ms_mean", "E_ttft_ms_mean", "B_duration_ms_mean", "E_duration_ms_mean"):
        print(f"  {k:26s} {S.get(k)}")
    print("\n=== CACHE RATIO BY ARM ===")
    for a, v in S["cache_ratio_by_arm"].items():
        print(f"  {a}: {v}")
    print(f"\n=== CACHE-BREAK TRIALS (<0.8): {len(cb)} ===")
    for c in cb[:15]:
        print(f"  {c['arm']}/{c['task']:28s} ratio={c['ratio']:<6} pass={c['pass']} cost=${c['cost']} tools={c['n_tool_calls']}")
    print(f"\n=== NEAR-MISSES frac>=0.5: {len(S['near_misses_ge_0.5'])} ===")
    for n in S["near_misses_ge_0.5"]:
        print(f"  {n['arm']}/{n['task']:28s} {n['passed']}/{n['passed']+n['failed']} modes={n['modes']}")
        for m in n["messages"][:1]:
            print(f"      msg: {m[:160]}")
    print(f"\n=== NEAR-MISSES 0.34<=frac<0.5: {len(S['near_misses_ge_0.34_lt_0.5'])} ===")
    for n in S["near_misses_ge_0.34_lt_0.5"]:
        print(f"  {n['arm']}/{n['task']:28s} {n['passed']}/{n['passed']+n['failed']} modes={n['modes']}")
    print("\n=== FAILURE MODE TOTALS BY ARM ===")
    for a, v in S["failure_mode_totals_by_arm"].items():
        print(f"  {a}: {v}")
    print("\n=== FAILURE TAXONOMY (task/arm) ===")
    for k, v in sorted(S["failure_taxonomy"].items()):
        print(f"  {k:44s} {v}")
    print(f"\n=== EXCEPTION TRIALS: {len(S['exception_trials'])} ===")
    for t in S["exception_trials"]:
        print(f"  {t['arm']}/{t['task']}/{t['trial']} exc={t['exception']} err={t['error']}")
    print("\n=== LONGEST agent_execution ===")
    for t in S["longest_agent_exec"][:12]:
        print(f"  {t['arm']}/{t['task']:28s} exec={t['agent_exec_s']}s total={t['total_s']}s "
              f"lastmsg_before_finish={t['last_msg_before_finish_s']}s tools={t['n_tool_calls']} "
              f"RUN_FINISHED={t['has_RUN_FINISHED']}")
    print(f"\n=== LOOP TRIALS (B/E): {len(loops)} ===")
    for l in loops[:15]:
        print(f"  {l['arm']}/{l['task']:28s} pass={l['pass']} maxrun={l['max_run']} "
              f"tools={l['n_tool_calls']} dups={list(l['dups'].items())[:2]}")
    print(f"\n=== ARM A STALLS >=120s: {len(stalls)} ===")
    for s in stalls:
        print(f"  {s['task']:28s} pass={s['pass']} maxgap={s['max_gap_s']}s")
    print("\n=== E-OPT1 FLIPS ===")
    for f in flips:
        print(f"  {f['task']:30s} A={f['A']} B={f['B']} E={f['E']}")
    print("\n=== ARM A ALL-FAIL FORENSICS ===")
    for a in forensics:
        print(f"  --- {a['task']} ({a['trial'][:40]}) tools={a['n_tool_calls']} hist={a['tool_hist']} maxgap={a['max_gap_s']}s")
        print(f"      failed={a['failed_tests']}")
        print(f"      modes={a['modes']}")
        for m in a["messages"][:1]:
            print(f"      msg: {m[:200]}")
        print(f"      final: {(a['final_text'] or '')[:280].replace(chr(10), ' ')}")
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
