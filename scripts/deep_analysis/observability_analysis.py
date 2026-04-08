#!/usr/bin/env python3
"""
Intent Observability Analysis — Module 10

Generates tables and charts for the intent-observability paper argument:
  A. Property-level verification locality classification (pre-run, from task JSON)
  B. Per-property satisfaction rates stratified by verification locality
  C. Remote device read rates by task and pattern
  D. Awareness-action gap (reasoning mentions remote device vs actual reads)
  E. Coordination displacement (turn type vs device locality)
  F. Blind-fix rate (property fixed without prior observation)
  G. Score comparison: runs that read remote vs those that did not

Usage:
    python -m scripts.deep_analysis.observability_analysis [--session-dir PATH]
"""

import json
import re
import csv
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from scripts.deep_analysis.run_loader import (
    load_and_enrich, setup_plotting, get_output_dir,
    TASK_METADATA, PATTERN_ORDER, PATTERN_LABELS, PATTERN_COLORS,
)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

TASKS_DIR = Path(__file__).resolve().parent.parent.parent / "tasks" / "multi_turn"

# ---------------------------------------------------------------------------
# A. Static observability classification from task JSONs
# ---------------------------------------------------------------------------

# For each task, which devices are "configured by the agent" vs
# "only needed for verification."  This encodes domain knowledge about
# where configuration actions target vs where evaluation commands run.
# The classification is: a property is REMOTE-VERIFIED if its eval
# target_node is not among the devices an agent would naturally configure.

TASK_CONFIG_DEVICES = {
    "ccna_rip_routing_basic":              {"R1", "R2", "R3", "R4"},
    "troubleshoot_ospf_adjacency_issue":   {"R2", "R3"},
    "ccnp_multiarea_ospf_intermediate":    {"R1", "R2", "R3", "R4", "R5"},
    "ccie_bgp_dual_homing_expert":         {"EDGE1", "EDGE2", "CORE"},
    "troubleshoot_bgp_route_filtering":    {"EDGE"},
}

# Remote verification devices: where verification evidence lives but
# agents don't naturally configure.
TASK_REMOTE_VERIFY_DEVICES = {
    "ccna_rip_routing_basic":              set(),
    "troubleshoot_ospf_adjacency_issue":   {"R1"},
    "ccnp_multiarea_ospf_intermediate":    {"R4", "R5"},
    "ccie_bgp_dual_homing_expert":         {"ISP1", "ISP2"},
    "troubleshoot_bgp_route_filtering":    {"ISP"},
}


def load_task_properties() -> Dict[str, List[Dict]]:
    """Load property definitions from task JSONs. Returns {task_id: [prop_dicts]}."""
    result = {}
    for f in sorted(TASKS_DIR.glob("*.json")):
        with open(f) as fh:
            d = json.load(fh)
        tid = d["task_id"]
        props = []
        for p in d.get("intent", {}).get("properties", []):
            pid = p.get("id", "")
            ev = p.get("evaluation", {})
            props.append({
                "property_id": pid,
                "eval_device": ev.get("target_node", ""),
                "eval_command": ev.get("command", ""),
                "is_remote": ev.get("target_node", "") in TASK_REMOTE_VERIFY_DEVICES.get(tid, set()),
            })
        result[tid] = props
    return result


# ---------------------------------------------------------------------------
# Helpers: parse execution logs for device targeting
# ---------------------------------------------------------------------------

def parse_exec_log_devices(run: Dict) -> Tuple[Dict[str, int], Dict[str, int]]:
    """Return (config_counts_by_device, read_counts_by_device) from execution_log."""
    cfg, rd = defaultdict(int), defaultdict(int)
    for entry in run.get("execution_log") or []:
        parts = entry.split(" | ", 1)
        if len(parts) != 2:
            continue
        dev, cmd = parts[0].strip(), parts[1].strip().lower()
        if "show" in cmd or "ping" in cmd or "display" in cmd:
            rd[dev] += 1
        else:
            cfg[dev] += 1
    return dict(cfg), dict(rd)


def parse_conversation_devices(run: Dict) -> Tuple[Dict[str, int], Dict[str, int]]:
    """Return (config_counts, read_counts) from agent_conversations action_input."""
    cfg, rd = defaultdict(int), defaultdict(int)
    for c in (run.get("metrics") or {}).get("agent_conversations") or []:
        ai = (c.get("content") or {}).get("action_input") or {}
        if not isinstance(ai, dict) or "node" not in ai:
            continue
        dev = ai["node"]
        cmd = str(ai.get("command", "")).lower()
        ct = ai.get("command_type", "")
        if ct == "read" or "show" in cmd or "ping" in cmd:
            rd[dev] += 1
        elif ct == "config" or ai.get("command"):
            cfg[dev] += 1
    return dict(cfg), dict(rd)


def get_all_device_reads(run: Dict) -> Dict[str, int]:
    """Merge read counts from execution_log and agent_conversations."""
    _, rd1 = parse_exec_log_devices(run)
    _, rd2 = parse_conversation_devices(run)
    merged = defaultdict(int)
    for d, c in rd1.items():
        merged[d] += c
    for d, c in rd2.items():
        merged[d] += c
    return dict(merged)


def has_read_on_device(run: Dict, devices: set) -> bool:
    reads = get_all_device_reads(run)
    return any(reads.get(d, 0) > 0 for d in devices)


# ---------------------------------------------------------------------------
# D. Awareness-action gap: reasoning mentions device vs actual execution
# ---------------------------------------------------------------------------

def reasoning_mentions_device(run: Dict, devices: set) -> bool:
    """Check if any reasoning trace or conversation text mentions a remote device name."""
    patterns = [re.compile(rf"\b{re.escape(d)}\b", re.IGNORECASE) for d in devices]
    for step in run.get("reasoning_trace") or []:
        text = str(step.get("content", ""))
        if any(p.search(text) for p in patterns):
            return True
    for c in (run.get("metrics") or {}).get("agent_conversations") or []:
        thought = str((c.get("content") or {}).get("thought", ""))
        if any(p.search(thought) for p in patterns):
            return True
    return False


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------

def run_observability_analysis(runs: List[Dict], out_dir: Path) -> Dict[str, Any]:
    setup_plotting()
    obs_dir = out_dir / "observability"
    obs_dir.mkdir(parents=True, exist_ok=True)

    task_props = load_task_properties()
    summary = {}

    # ------------------------------------------------------------------
    # B. Per-property satisfaction rate by verification locality
    # ------------------------------------------------------------------
    print("  [B] Property satisfaction by verification locality...")
    rows_b = []
    for run in runs:
        tid = run["task_id"]
        prop_defs = {p["property_id"]: p for p in task_props.get(tid, [])}
        for pr in run.get("property_results") or []:
            pid = pr.get("property_id", "")
            pdef = prop_defs.get(pid, {})
            rows_b.append({
                "task": tid,
                "task_display": TASK_METADATA.get(tid, {}).get("display_name", tid),
                "property_id": pid,
                "pattern": run.get("_pattern", ""),
                "model": run.get("_model", ""),
                "satisfied": 1 if pr.get("satisfied") else 0,
                "eval_device": pdef.get("eval_device", ""),
                "is_remote": pdef.get("is_remote", False),
                "locality": "remote" if pdef.get("is_remote") else "local",
            })

    csv_b = obs_dir / "property_satisfaction_by_locality.csv"
    with open(csv_b, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows_b[0].keys())
        w.writeheader()
        w.writerows(rows_b)

    local_sat = [r["satisfied"] for r in rows_b if r["locality"] == "local"]
    remote_sat = [r["satisfied"] for r in rows_b if r["locality"] == "remote"]
    summary["local_sat_rate"] = np.mean(local_sat) if local_sat else 0
    summary["remote_sat_rate"] = np.mean(remote_sat) if remote_sat else 0
    summary["local_n"] = len(local_sat)
    summary["remote_n"] = len(remote_sat)

    # Per-task breakdown
    task_locality = defaultdict(lambda: {"local": [], "remote": []})
    for r in rows_b:
        task_locality[r["task_display"]][r["locality"]].append(r["satisfied"])

    # Chart B: local vs remote satisfaction by task
    tasks_sorted = ["CCNA RIP", "Fix OSPF", "CCNP OSPF", "CCIE BGP", "Fix BGP"]
    tasks_present = [t for t in tasks_sorted if t in task_locality]
    local_means = [np.mean(task_locality[t]["local"]) if task_locality[t]["local"] else 0 for t in tasks_present]
    remote_means = [np.mean(task_locality[t]["remote"]) if task_locality[t]["remote"] else 0 for t in tasks_present]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    x = np.arange(len(tasks_present))
    w = 0.35
    ax.bar(x - w / 2, local_means, w, label="Local-verified", color="#0173B2", alpha=0.85)
    ax.bar(x + w / 2, remote_means, w, label="Remote-verified", color="#D55E00", alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels(tasks_present, rotation=15, ha="right")
    ax.set_ylabel("Mean satisfaction rate")
    ax.set_ylim(0, 1.05)
    ax.set_title("Property Satisfaction: Local vs Remote Verification")
    ax.legend()
    fig.tight_layout()
    fig.savefig(obs_dir / "property_satisfaction_local_vs_remote.png")
    plt.close(fig)

    # ------------------------------------------------------------------
    # C. Remote device read rate by task and pattern
    # ------------------------------------------------------------------
    print("  [C] Remote device read rates...")
    rows_c = []
    for run in runs:
        tid = run["task_id"]
        remote_devs = TASK_REMOTE_VERIFY_DEVICES.get(tid, set())
        if not remote_devs:
            continue
        did_read = has_read_on_device(run, remote_devs)
        rows_c.append({
            "task": tid,
            "task_display": TASK_METADATA.get(tid, {}).get("display_name", tid),
            "pattern": run.get("_pattern", ""),
            "model": run.get("_model", ""),
            "read_remote": 1 if did_read else 0,
            "remote_devices": ",".join(sorted(remote_devs)),
            "score": run.get("scoring", {}).get("final_score", 0) or 0,
        })

    csv_c = obs_dir / "remote_read_rates.csv"
    if rows_c:
        with open(csv_c, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=rows_c[0].keys())
            w.writeheader()
            w.writerows(rows_c)

    # Chart C: remote read rate by task×pattern
    tasks_with_remote = ["Fix OSPF", "CCNP OSPF", "CCIE BGP", "Fix BGP"]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    bar_w = 0.15
    for i, pat in enumerate(PATTERN_ORDER):
        rates = []
        for t in tasks_with_remote:
            subset = [r for r in rows_c if r["task_display"] == t and r["pattern"] == pat]
            rates.append(np.mean([r["read_remote"] for r in subset]) if subset else 0)
        offset = (i - 2) * bar_w
        ax.bar(np.arange(len(tasks_with_remote)) + offset, rates, bar_w,
               label=PATTERN_LABELS.get(pat, pat), color=PATTERN_COLORS.get(pat, "#999"))
    ax.set_xticks(np.arange(len(tasks_with_remote)))
    ax.set_xticklabels(tasks_with_remote)
    ax.set_ylabel("Fraction of runs reading remote device")
    ax.set_ylim(0, 1.05)
    ax.set_title("Remote Verification Device Read Rate")
    ax.legend(fontsize=8, ncol=3)
    fig.tight_layout()
    fig.savefig(obs_dir / "remote_read_rate_by_task_pattern.png")
    plt.close(fig)

    # ------------------------------------------------------------------
    # D. Awareness-action gap
    # ------------------------------------------------------------------
    print("  [D] Awareness-action gap...")
    rows_d = []
    for run in runs:
        tid = run["task_id"]
        remote_devs = TASK_REMOTE_VERIFY_DEVICES.get(tid, set())
        if not remote_devs:
            continue
        mentioned = reasoning_mentions_device(run, remote_devs)
        read = has_read_on_device(run, remote_devs)
        rows_d.append({
            "task": tid,
            "task_display": TASK_METADATA.get(tid, {}).get("display_name", tid),
            "pattern": run.get("_pattern", ""),
            "model": run.get("_model", ""),
            "mentioned_remote": 1 if mentioned else 0,
            "read_remote": 1 if read else 0,
            "gap": 1 if (mentioned and not read) else 0,
            "score": run.get("scoring", {}).get("final_score", 0) or 0,
        })

    csv_d = obs_dir / "awareness_action_gap.csv"
    if rows_d:
        with open(csv_d, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=rows_d[0].keys())
            w.writeheader()
            w.writerows(rows_d)

    summary["awareness_action_gap"] = {}
    for t in tasks_with_remote:
        sub = [r for r in rows_d if r["task_display"] == t]
        if sub:
            mention_rate = np.mean([r["mentioned_remote"] for r in sub])
            read_rate = np.mean([r["read_remote"] for r in sub])
            gap_rate = np.mean([r["gap"] for r in sub])
            summary["awareness_action_gap"][t] = {
                "mention_rate": round(mention_rate, 3),
                "read_rate": round(read_rate, 3),
                "gap_rate": round(gap_rate, 3),
                "n": len(sub),
            }

    # Chart D: awareness vs action stacked bar
    fig, ax = plt.subplots(figsize=(8, 4.5))
    x = np.arange(len(tasks_with_remote))
    mention_vals = []
    read_vals = []
    for t in tasks_with_remote:
        s = summary["awareness_action_gap"].get(t, {})
        mention_vals.append(s.get("mention_rate", 0))
        read_vals.append(s.get("read_rate", 0))

    ax.bar(x, mention_vals, 0.5, label="Mentioned in reasoning", color="#56B4E9", alpha=0.8)
    ax.bar(x, read_vals, 0.5, label="Actually read device", color="#D55E00", alpha=0.9)
    ax.set_xticks(x)
    ax.set_xticklabels(tasks_with_remote)
    ax.set_ylabel("Fraction of runs")
    ax.set_ylim(0, 1.05)
    ax.set_title("Awareness–Action Gap: Mentioning vs Reading Remote Devices")
    ax.legend()
    fig.tight_layout()
    fig.savefig(obs_dir / "awareness_action_gap.png")
    plt.close(fig)

    # ------------------------------------------------------------------
    # G. Score comparison: runs with remote read vs without
    # ------------------------------------------------------------------
    print("  [G] Score comparison with/without remote reads...")
    summary["score_by_remote_read"] = {}
    for t in tasks_with_remote:
        sub_with = [r for r in rows_c if r["task_display"] == t and r["read_remote"]]
        sub_without = [r for r in rows_c if r["task_display"] == t and not r["read_remote"]]
        summary["score_by_remote_read"][t] = {
            "with_read_n": len(sub_with),
            "with_read_mean": round(np.mean([r["score"] for r in sub_with]), 3) if sub_with else None,
            "without_read_n": len(sub_without),
            "without_read_mean": round(np.mean([r["score"] for r in sub_without]), 3) if sub_without else None,
        }

    # ------------------------------------------------------------------
    # F. Blind-fix rate
    # ------------------------------------------------------------------
    print("  [F] Blind-fix rate (fix applied without observing problem)...")
    blind_fix_tasks = {
        "troubleshoot_bgp_route_filtering": {
            "diagnosis_prop": "problem_identified",
            "fix_prop": "route_map_applied",
            "remote_devs": {"ISP"},
        },
    }
    rows_f = []
    for run in runs:
        tid = run["task_id"]
        if tid not in blind_fix_tasks:
            continue
        cfg = blind_fix_tasks[tid]
        prop_map = {p["property_id"]: p["satisfied"] for p in run.get("property_results") or []}
        did_read = has_read_on_device(run, cfg["remote_devs"])
        fix_applied = prop_map.get(cfg["fix_prop"], False)
        diagnosis_confirmed = prop_map.get(cfg["diagnosis_prop"], False)
        rows_f.append({
            "task": tid,
            "pattern": run.get("_pattern", ""),
            "model": run.get("_model", ""),
            "read_remote": 1 if did_read else 0,
            "diagnosis_confirmed": 1 if diagnosis_confirmed else 0,
            "fix_applied": 1 if fix_applied else 0,
            "blind_fix": 1 if (fix_applied and not did_read) else 0,
        })

    csv_f = obs_dir / "blind_fix_rate.csv"
    if rows_f:
        with open(csv_f, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=rows_f[0].keys())
            w.writeheader()
            w.writerows(rows_f)
        blind_fixes = [r["blind_fix"] for r in rows_f]
        summary["blind_fix_rate"] = round(np.mean(blind_fixes), 3) if blind_fixes else 0

    # ------------------------------------------------------------------
    # Per-property summary table (the key table for the paper)
    # ------------------------------------------------------------------
    print("  [*] Per-property observability summary table...")
    prop_summary = defaultdict(lambda: {"satisfied": 0, "total": 0})
    for r in rows_b:
        key = (r["task_display"], r["property_id"], r["locality"], r["eval_device"])
        prop_summary[key]["satisfied"] += r["satisfied"]
        prop_summary[key]["total"] += 1

    rows_summary = []
    for (task, pid, loc, dev), counts in sorted(prop_summary.items()):
        rows_summary.append({
            "task": task,
            "property_id": pid,
            "locality": loc,
            "eval_device": dev,
            "n_runs": counts["total"],
            "n_satisfied": counts["satisfied"],
            "sat_rate": round(counts["satisfied"] / counts["total"], 3) if counts["total"] else 0,
        })

    csv_summary = obs_dir / "per_property_observability_summary.csv"
    with open(csv_summary, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows_summary[0].keys())
        w.writeheader()
        w.writerows(rows_summary)

    # ------------------------------------------------------------------
    # Print headline numbers
    # ------------------------------------------------------------------
    print()
    print("=" * 60)
    print("INTENT OBSERVABILITY ANALYSIS — HEADLINE RESULTS")
    print("=" * 60)
    print(f"  Local-verified properties:  n={summary['local_n']:4d}, "
          f"sat rate = {summary['local_sat_rate']:.3f}")
    print(f"  Remote-verified properties: n={summary['remote_n']:4d}, "
          f"sat rate = {summary['remote_sat_rate']:.3f}")
    print()
    print("  Awareness–Action Gap (mentioned remote device vs actually read it):")
    for t, g in summary.get("awareness_action_gap", {}).items():
        print(f"    {t:12s}  mentioned={g['mention_rate']:.1%}  read={g['read_rate']:.1%}  "
              f"gap={g['gap_rate']:.1%}  (n={g['n']})")
    print()
    print("  Score with/without remote reads:")
    for t, s in summary.get("score_by_remote_read", {}).items():
        w = f"{s['with_read_mean']:.3f} (n={s['with_read_n']})" if s["with_read_mean"] is not None else "n/a"
        print(f"    {t:12s}  with_read={w}  without={s['without_read_mean']:.3f} (n={s['without_read_n']})")
    print()
    if "blind_fix_rate" in summary:
        print(f"  Blind-fix rate (BGP route filtering): {summary['blind_fix_rate']:.1%}")
    print()

    # Save summary JSON
    with open(obs_dir / "observability_summary.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)

    print(f"  Outputs written to {obs_dir}/")
    return summary


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Intent Observability Analysis")
    parser.add_argument("--session-dir", type=str, default=None)
    args = parser.parse_args()

    session_dir = Path(args.session_dir) if args.session_dir else None
    runs = load_and_enrich(session_dir)
    print(f"Loaded {len(runs)} runs")

    from scripts.deep_analysis.run_loader import DEFAULT_SESSION
    sd = session_dir or DEFAULT_SESSION
    out_dir = get_output_dir(sd)
    run_observability_analysis(runs, out_dir)


if __name__ == "__main__":
    main()
