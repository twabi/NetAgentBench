#!/usr/bin/env python3
"""
Module 9: Pattern Deep Profiles

Investigates three pattern-specific phenomena from the brainstorm:

A) Debate Paradox -- Does debate's deliberation actually help, or does it spend
   tokens on argumentation without translating to better actions?
   Measures: debate_token_premium vs score_delta, reasoning steps that lead
   to action changes, convergence rate.

B) Group Chat Analyzer Trap -- Does the Analyzer agent in group_chat dominate
   the conversation while Executor underperforms?
   Measures: role turn share, Executor stall rate, Analyzer vs Executor
   action contribution.

C) Sequential Convergence -- How linearly does sequential pattern progress
   toward solution? Measures monotonic property gain rate.

D) Concurrent Divergence -- Do concurrent workers duplicate or conflict?
   Measures: command overlap ratio, property satisfaction overlap.
"""

import csv
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats as scipy_stats

from .run_loader import (
    load_and_enrich, get_output_dir, setup_plotting, extract_execution_commands,
    classify_command,
    PATTERN_COLORS, PATTERN_ORDER, PATTERN_LABELS, DEFAULT_SESSION,
    TASK_METADATA,
)


def _get_total_tokens(run: Dict) -> int:
    tu = (run.get("metrics", {}) or {}).get("token_usage") or {}
    return tu.get("total_tokens", 0) or 0


# ── A) Debate Paradox ─────────────────────────────────────────────

def _debate_analysis(runs: List[Dict]) -> Dict:
    """Analyze the debate paradox: token cost vs score improvement."""
    debate_runs = [r for r in runs if r["_pattern"] == "debate"]
    single_runs = [r for r in runs if r["_pattern"] == "single"]

    # Score delta per task x model vs single baseline
    baselines = defaultdict(lambda: defaultdict(list))
    for r in single_runs:
        baselines[r["_model"]][r.get("task_id", "")].append(
            r.get("scoring", {}).get("final_score", 0) or 0)

    debate_profiles = []
    for r in debate_runs:
        model = r["_model"]
        task = r.get("task_id", "")
        score = r.get("scoring", {}).get("final_score", 0) or 0
        tokens = _get_total_tokens(r)
        baseline_scores = baselines[model].get(task, [])
        baseline_mean = np.mean(baseline_scores) if baseline_scores else 0

        # Count debate-specific steps
        trace = r.get("reasoning_trace", []) or []
        proponent_steps = sum(1 for e in trace if 'proponent' in e.get("step", "").lower())
        opponent_steps = sum(1 for e in trace if 'opponent' in e.get("step", "").lower())
        judgment_steps = sum(1 for e in trace if 'judgment' in e.get("step", "").lower() or
                            'judge' in e.get("step", "").lower())
        executor_steps = sum(1 for e in trace if 'executor' in e.get("step", "").lower())

        debate_overhead = proponent_steps + opponent_steps + judgment_steps
        total_steps = len(trace)
        debate_fraction = debate_overhead / total_steps if total_steps > 0 else 0

        debate_profiles.append({
            "run_id": r.get("run_id", ""),
            "model": model,
            "task_id": task,
            "score": score,
            "baseline_score": baseline_mean,
            "score_delta": score - baseline_mean,
            "tokens": tokens,
            "token_premium": tokens - np.mean(
                [_get_total_tokens(sr) for sr in single_runs
                 if sr["_model"] == model and sr.get("task_id", "") == task]
            ) if any(sr["_model"] == model and sr.get("task_id", "") == task for sr in single_runs) else 0,
            "debate_fraction": debate_fraction,
            "proponent_steps": proponent_steps,
            "opponent_steps": opponent_steps,
            "judgment_steps": judgment_steps,
            "executor_steps": executor_steps,
        })

    return {"profiles": debate_profiles}


# ── B) Group Chat Analyzer Trap ───────────────────────────────────

def _group_chat_analysis(runs: List[Dict]) -> Dict:
    """Analyze role dominance in group_chat via reasoning_trace step names."""
    gc_runs = [r for r in runs if r["_pattern"] == "group_chat"]

    gc_profiles = []
    for r in gc_runs:
        trace = r.get("reasoning_trace", []) or []
        role_turns = Counter()
        role_tokens_est = Counter()

        for entry in trace:
            step = entry.get("step", "")
            prefix = re.sub(r'_?turn\d+$', '', step, flags=re.IGNORECASE).lower()
            if not prefix:
                prefix = "unknown"
            content = entry.get("content", "") or ""
            if not isinstance(content, str):
                content = str(content)
            role_turns[prefix] += 1
            role_tokens_est[prefix] += len(content.split())

        total_turns = sum(role_turns.values()) or 1
        total_tokens_est = sum(role_tokens_est.values()) or 1

        exec_log = r.get("execution_log", []) or []
        n_commands = len(exec_log) // 2

        score = r.get("scoring", {}).get("final_score", 0) or 0

        gc_profiles.append({
            "run_id": r.get("run_id", ""),
            "model": r["_model"],
            "task_id": r.get("task_id", ""),
            "score": score,
            "total_turns": sum(role_turns.values()),
            "manager_turn_share": role_turns.get("manager", 0) / total_turns,
            "executor_turn_share": role_turns.get("executor", 0) / total_turns,
            "analyzer_turn_share": role_turns.get("analyzer", 0) / total_turns,
            "planner_turn_share": role_turns.get("planner", 0) / total_turns,
            "manager_token_share": role_tokens_est.get("manager", 0) / total_tokens_est,
            "executor_token_share": role_tokens_est.get("executor", 0) / total_tokens_est,
            "n_commands": n_commands,
            "cmds_per_turn": n_commands / total_turns if total_turns > 0 else 0,
        })

    return {"profiles": gc_profiles}


# ── C) Sequential Convergence ─────────────────────────────────────

def _sequential_convergence(runs: List[Dict]) -> Dict:
    """Measure sequential progression efficiency using command classification.

    Since intermediate property checks aren't recorded in trace, we use
    command-level analysis: fraction of constructive commands, error rate
    trend, and how efficiently the agent sequence progresses.
    """
    seq_runs = [r for r in runs if r["_pattern"] == "sequential"]

    convergence_profiles = []
    for r in seq_runs:
        exec_log = r.get("execution_log", []) or []
        pairs = extract_execution_commands(exec_log)
        if not pairs:
            continue

        total_props = len(r.get("property_results", []))
        satisfied = sum(1 for p in r.get("property_results", [])
                        if p.get("satisfied"))

        # Classify commands in sequence and compute running constructive ratio
        classifications = [classify_command(cmd) for _, cmd in pairs]
        n = len(classifications)

        # Constructive momentum: does the run get more constructive over time?
        if n >= 4:
            first_half = classifications[:n // 2]
            second_half = classifications[n // 2:]
            c1 = sum(1 for c in first_half if c == 'constructive') / len(first_half)
            c2 = sum(1 for c in second_half if c == 'constructive') / len(second_half)
            momentum = c2 - c1
        else:
            momentum = 0.0

        constructive_pct = sum(1 for c in classifications if c == 'constructive') / n
        error_pct = sum(1 for c in classifications if c == 'diagnostic') / n

        # Efficiency: properties satisfied per command
        props_per_cmd = satisfied / max(1, n)

        score = r.get("scoring", {}).get("final_score", 0) or 0
        convergence_profiles.append({
            "run_id": r.get("run_id", ""),
            "model": r["_model"],
            "task_id": r.get("task_id", ""),
            "score": score,
            "constructive_pct": constructive_pct,
            "momentum": momentum,
            "error_pct": error_pct,
            "props_per_cmd": props_per_cmd,
            "n_commands": n,
            "total_properties": total_props,
            "satisfied_properties": satisfied,
        })

    return {"profiles": convergence_profiles}


# ── D) Concurrent Divergence ──────────────────────────────────────

def _concurrent_divergence(runs: List[Dict]) -> Dict:
    """Check if concurrent workers duplicate or conflict."""
    conc_runs = [r for r in runs if r["_pattern"] == "concurrent"]

    divergence_profiles = []
    for r in conc_runs:
        exec_log = r.get("execution_log", []) or []
        pairs = extract_execution_commands(exec_log)

        # Group commands by target router
        by_router = defaultdict(list)
        for router, cmd in pairs:
            by_router[router].append(cmd)

        # Look for overlapping command sequences across workers
        trace = r.get("reasoning_trace", []) or []
        worker_cmds = defaultdict(list)
        for entry in trace:
            step = entry.get("step", "")
            content = entry.get("content", "") or ""
            match = re.match(r'worker_(\d+)', step, re.IGNORECASE)
            if match:
                cmds = re.findall(r'(configure|show|router|interface|ip|no )\S+', content.lower())
                worker_cmds[match.group(1)].extend(cmds)

        # Command overlap: count duplicate commands across workers
        all_worker_cmd_lists = list(worker_cmds.values())
        overlap_count = 0
        total_worker_cmds = 0
        if len(all_worker_cmd_lists) > 1:
            all_flat = []
            for wl in all_worker_cmd_lists:
                total_worker_cmds += len(wl)
                all_flat.extend(wl)
            cmd_counts = Counter(all_flat)
            overlap_count = sum(v - 1 for v in cmd_counts.values() if v > 1)

        score = r.get("scoring", {}).get("final_score", 0) or 0
        n_routers = len(by_router)
        tokens = _get_total_tokens(r)

        divergence_profiles.append({
            "run_id": r.get("run_id", ""),
            "model": r["_model"],
            "task_id": r.get("task_id", ""),
            "score": score,
            "n_routers_touched": n_routers,
            "n_workers": len(worker_cmds),
            "overlap_count": overlap_count,
            "total_worker_cmds": total_worker_cmds,
            "overlap_ratio": overlap_count / max(1, total_worker_cmds),
            "tokens": tokens,
        })

    return {"profiles": divergence_profiles}


# ── Plots ─────────────────────────────────────────────────────────

def plot_debate_paradox(debate: Dict, out_dir: Path) -> None:
    """Token premium vs score delta scatter."""
    setup_plotting()
    profiles = debate["profiles"]
    if not profiles:
        return

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Left: token premium vs score delta
    ax = axes[0]
    x = [p["token_premium"] / 1000 for p in profiles]
    y = [p["score_delta"] for p in profiles]
    colors = ['green' if d > 0 else 'red' for d in y]
    ax.scatter(x, y, c=colors, alpha=0.6, edgecolors='k', linewidths=0.5, s=60)
    ax.axhline(0, color='gray', linestyle='--', alpha=0.5)
    ax.axvline(0, color='gray', linestyle='--', alpha=0.5)
    ax.set_xlabel("Token Premium over Single (K tokens)")
    ax.set_ylabel("Score Delta vs Single Baseline")
    ax.set_title("Debate Paradox: Extra Cost vs Extra Score")

    n_pos = sum(1 for d in y if d > 0)
    n_neg = sum(1 for d in y if d < 0)
    n_zero = sum(1 for d in y if d == 0)
    ax.annotate(f"+{n_pos} | ={n_zero} | {n_neg}−",
                xy=(0.05, 0.95), xycoords='axes fraction', fontsize=9,
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.7))

    # Right: debate fraction vs score
    ax = axes[1]
    x2 = [p["debate_fraction"] * 100 for p in profiles]
    y2 = [p["score"] for p in profiles]
    ax.scatter(x2, y2, alpha=0.6, edgecolors='k', linewidths=0.5, s=60,
               color=PATTERN_COLORS['debate'])
    ax.set_xlabel("Debate Overhead (% of steps)")
    ax.set_ylabel("Final Score")
    ax.set_title("Debate Overhead vs Performance")

    if len(x2) > 2:
        slope, intercept, r_val, p_val, _ = scipy_stats.linregress(x2, y2)
        ax.plot(sorted(x2), [slope * xi + intercept for xi in sorted(x2)],
                'r--', alpha=0.7, label=f"R²={r_val ** 2:.3f}")
        ax.legend(fontsize=8)

    fig.suptitle("Debate Pattern Deep Profile", fontweight='bold', y=1.02)
    fig.tight_layout()
    fig.savefig(out_dir / "pattern_debate_paradox.png")
    plt.close(fig)


def plot_gc_analyzer_trap(gc: Dict, out_dir: Path) -> None:
    """Group Chat role dominance analysis."""
    setup_plotting()
    profiles = gc["profiles"]
    if not profiles:
        return

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Left: stacked bar of role shares
    ax = axes[0]
    models = sorted(set(p["model"] for p in profiles))
    role_keys = ["manager_turn_share", "executor_turn_share", "analyzer_turn_share", "planner_turn_share"]
    role_labels = ["Manager", "Executor", "Analyzer", "Planner"]
    role_colors = ['#0173B2', '#CA9161', '#CC78BC', '#56B4E9']

    x = np.arange(len(models))
    bottoms = np.zeros(len(models))
    for key, label, color in zip(role_keys, role_labels, role_colors):
        vals = []
        for m in models:
            m_profiles = [p for p in profiles if p["model"] == m]
            vals.append(np.mean([p[key] for p in m_profiles]) * 100 if m_profiles else 0)
        ax.bar(x, vals, bottom=bottoms, label=label, color=color, alpha=0.8)
        bottoms += vals

    ax.set_xticks(x)
    ax.set_xticklabels(models, fontsize=8, rotation=20, ha='right')
    ax.set_ylabel("Turn Share (%)")
    ax.set_title("Group Chat Role Dominance")
    ax.legend(fontsize=8)

    # Right: commands per turn vs score
    ax = axes[1]
    x2 = [p["cmds_per_turn"] for p in profiles]
    y2 = [p["score"] for p in profiles]
    ax.scatter(x2, y2, alpha=0.6, edgecolors='k', linewidths=0.5, s=60,
               color=PATTERN_COLORS['group_chat'])
    ax.set_xlabel("Commands per Conversation Turn")
    ax.set_ylabel("Final Score")
    ax.set_title("Action Density vs Performance")

    if len(x2) > 2:
        slope, intercept, r_val, _, _ = scipy_stats.linregress(x2, y2)
        ax.plot(sorted(x2), [slope * xi + intercept for xi in sorted(x2)],
                'r--', alpha=0.7, label=f"R²={r_val ** 2:.3f}")
        ax.legend(fontsize=8)

    fig.suptitle("Group Chat Deep Profile: Analyzer Trap", fontweight='bold', y=1.02)
    fig.tight_layout()
    fig.savefig(out_dir / "pattern_gc_analyzer_trap.png")
    plt.close(fig)


def plot_sequential_convergence(conv: Dict, out_dir: Path) -> None:
    """Sequential convergence and momentum analysis."""
    setup_plotting()
    profiles = conv["profiles"]
    if not profiles:
        return

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Left: constructive momentum vs score
    ax = axes[0]
    x = [p["momentum"] * 100 for p in profiles]
    y = [p["score"] for p in profiles]
    colors = ['green' if m > 0 else 'red' for m in x]
    ax.scatter(x, y, c=colors, alpha=0.6, edgecolors='k', linewidths=0.5, s=60)
    ax.axvline(0, color='gray', linestyle='--', alpha=0.5)
    ax.set_xlabel("Constructive Momentum (2nd half - 1st half %)")
    ax.set_ylabel("Final Score")
    ax.set_title("Sequential: Does it get more constructive over time?")

    if len(x) > 2:
        slope, intercept, r_val, _, _ = scipy_stats.linregress(x, y)
        ax.plot(sorted(x), [slope * xi + intercept for xi in sorted(x)],
                'r--', alpha=0.7, label=f"R²={r_val ** 2:.3f}")
        ax.legend(fontsize=8)

    # Right: props per command (efficiency) vs score
    ax = axes[1]
    x2 = [p["props_per_cmd"] for p in profiles]
    y2 = [p["score"] for p in profiles]
    ax.scatter(x2, y2, alpha=0.6, edgecolors='k', linewidths=0.5, s=60,
               color=PATTERN_COLORS['sequential'])
    ax.set_xlabel("Properties Satisfied per Command")
    ax.set_ylabel("Final Score")
    ax.set_title("Sequential: Command Efficiency vs Score")

    if len(x2) > 2:
        slope, intercept, r_val, _, _ = scipy_stats.linregress(x2, y2)
        ax.plot(sorted(x2), [slope * xi + intercept for xi in sorted(x2)],
                'r--', alpha=0.7, label=f"R²={r_val ** 2:.3f}")
        ax.legend(fontsize=8)

    fig.suptitle("Sequential Pattern Convergence Profile", fontweight='bold', y=1.02)
    fig.tight_layout()
    fig.savefig(out_dir / "pattern_sequential_convergence.png")
    plt.close(fig)


def plot_concurrent_divergence(div: Dict, out_dir: Path) -> None:
    """Concurrent worker overlap and divergence analysis."""
    setup_plotting()
    profiles = div["profiles"]
    if not profiles:
        return

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Left: overlap ratio vs score
    ax = axes[0]
    x = [p["overlap_ratio"] * 100 for p in profiles]
    y = [p["score"] for p in profiles]
    ax.scatter(x, y, alpha=0.6, edgecolors='k', linewidths=0.5, s=60,
               color=PATTERN_COLORS['concurrent'])
    ax.set_xlabel("Worker Command Overlap (%)")
    ax.set_ylabel("Final Score")
    ax.set_title("Concurrent: Worker Duplication vs Score")

    # Right: n_routers vs score
    ax = axes[1]
    x2 = [p["n_routers_touched"] for p in profiles]
    y2 = [p["score"] for p in profiles]
    ax.scatter(x2, y2, alpha=0.6, edgecolors='k', linewidths=0.5, s=60,
               color=PATTERN_COLORS['concurrent'])
    ax.set_xlabel("Distinct Routers Touched")
    ax.set_ylabel("Final Score")
    ax.set_title("Concurrent: Router Coverage vs Score")

    fig.suptitle("Concurrent Pattern Divergence Profile", fontweight='bold', y=1.02)
    fig.tight_layout()
    fig.savefig(out_dir / "pattern_concurrent_divergence.png")
    plt.close(fig)


def plot_pattern_comparison_radar(runs: List[Dict], out_dir: Path) -> None:
    """Radar chart comparing pattern behavioral fingerprints."""
    setup_plotting()

    metrics_by_pattern = defaultdict(lambda: defaultdict(list))
    for r in runs:
        pat = r["_pattern"]
        score = r.get("scoring", {}).get("final_score", 0) or 0
        tokens = _get_total_tokens(r)
        trace = r.get("reasoning_trace", []) or []
        exec_log = r.get("execution_log", []) or []
        pairs = extract_execution_commands(exec_log)

        n_steps = len(trace)
        constructive = sum(1 for _, cmd in pairs if classify_command(cmd) == 'constructive')
        constr_pct = constructive / max(1, len(pairs)) * 100

        metrics_by_pattern[pat]["score"].append(score)
        metrics_by_pattern[pat]["token_k"].append(tokens / 1000)
        metrics_by_pattern[pat]["steps"].append(n_steps)
        metrics_by_pattern[pat]["constructive_pct"].append(constr_pct)
        metrics_by_pattern[pat]["n_commands"].append(len(pairs))

    dimensions = ["score", "token_k", "steps", "constructive_pct", "n_commands"]
    dim_labels = ["Score", "Tokens (K)", "Steps", "Constructive %", "Commands"]

    # Normalize each dimension to [0, 1] across patterns
    all_maxes = {}
    for dim in dimensions:
        all_vals = []
        for pat in PATTERN_ORDER:
            all_vals.extend(metrics_by_pattern[pat].get(dim, [0]))
        all_maxes[dim] = max(all_vals) if all_vals else 1

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
    angles = np.linspace(0, 2 * np.pi, len(dimensions), endpoint=False).tolist()
    angles += angles[:1]

    for pat in PATTERN_ORDER:
        if pat not in metrics_by_pattern:
            continue
        values = [np.mean(metrics_by_pattern[pat].get(dim, [0])) / max(0.001, all_maxes[dim])
                  for dim in dimensions]
        values += values[:1]
        ax.plot(angles, values, 'o-', linewidth=2, label=PATTERN_LABELS.get(pat, pat),
                color=PATTERN_COLORS.get(pat, '#888888'))
        ax.fill(angles, values, alpha=0.1, color=PATTERN_COLORS.get(pat, '#888888'))

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(dim_labels, fontsize=9)
    ax.set_ylim(0, 1.1)
    ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1), fontsize=9)
    ax.set_title("Pattern Behavioral Fingerprints (Normalized)", pad=20, fontweight='bold')

    fig.tight_layout()
    fig.savefig(out_dir / "pattern_radar_fingerprints.png")
    plt.close(fig)


def save_csv(debate: Dict, gc: Dict, convergence: Dict, divergence: Dict,
             out_dir: Path) -> None:
    """Save all pattern profile data to CSV."""
    all_rows = []

    for p in debate.get("profiles", []):
        all_rows.append({
            "pattern": "debate",
            "run_id": p["run_id"], "model": p["model"], "task_id": p["task_id"],
            "score": p["score"], "metric_name": "score_delta",
            "metric_value": p["score_delta"],
        })
        all_rows.append({
            "pattern": "debate",
            "run_id": p["run_id"], "model": p["model"], "task_id": p["task_id"],
            "score": p["score"], "metric_name": "token_premium",
            "metric_value": p["token_premium"],
        })
        all_rows.append({
            "pattern": "debate",
            "run_id": p["run_id"], "model": p["model"], "task_id": p["task_id"],
            "score": p["score"], "metric_name": "debate_fraction",
            "metric_value": p["debate_fraction"],
        })

    for p in gc.get("profiles", []):
        for role_key in ("manager_turn_share", "executor_turn_share",
                         "analyzer_turn_share", "planner_turn_share"):
            all_rows.append({
                "pattern": "group_chat",
                "run_id": p["run_id"], "model": p["model"], "task_id": p["task_id"],
                "score": p["score"], "metric_name": role_key,
                "metric_value": p[role_key],
            })
        all_rows.append({
            "pattern": "group_chat",
            "run_id": p["run_id"], "model": p["model"], "task_id": p["task_id"],
            "score": p["score"], "metric_name": "cmds_per_turn",
            "metric_value": p["cmds_per_turn"],
        })

    for p in convergence.get("profiles", []):
        for metric_key in ("constructive_pct", "momentum", "props_per_cmd"):
            all_rows.append({
                "pattern": "sequential",
                "run_id": p["run_id"], "model": p["model"], "task_id": p["task_id"],
                "score": p["score"], "metric_name": metric_key,
                "metric_value": p[metric_key],
            })

    for p in divergence.get("profiles", []):
        all_rows.append({
            "pattern": "concurrent",
            "run_id": p["run_id"], "model": p["model"], "task_id": p["task_id"],
            "score": p["score"], "metric_name": "overlap_ratio",
            "metric_value": p["overlap_ratio"],
        })

    fields = ["pattern", "run_id", "model", "task_id", "score",
              "metric_name", "metric_value"]
    with open(out_dir / "pattern_deep_profiles.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(all_rows)


def run_analysis(session_dir: Path | None = None) -> Dict:
    """Run pattern deep profile analysis."""
    runs = load_and_enrich(session_dir)
    out_dir = get_output_dir(session_dir)

    print(f"  Pattern Deep Profiles: analyzing {len(runs)} runs...")

    debate = _debate_analysis(runs)
    gc = _group_chat_analysis(runs)
    convergence = _sequential_convergence(runs)
    divergence = _concurrent_divergence(runs)

    plot_debate_paradox(debate, out_dir)
    plot_gc_analyzer_trap(gc, out_dir)
    plot_sequential_convergence(convergence, out_dir)
    plot_concurrent_divergence(divergence, out_dir)
    plot_pattern_comparison_radar(runs, out_dir)
    save_csv(debate, gc, convergence, divergence, out_dir)

    # Print summaries
    dp = debate["profiles"]
    if dp:
        pos = sum(1 for p in dp if p["score_delta"] > 0)
        neg = sum(1 for p in dp if p["score_delta"] < 0)
        avg_premium = np.mean([p["token_premium"] for p in dp])
        avg_delta = np.mean([p["score_delta"] for p in dp])
        print(f"    Debate: {pos} improved, {neg} degraded vs single | "
              f"avg delta={avg_delta:+.3f} | avg token premium={avg_premium:+.0f}")

    gcp = gc["profiles"]
    if gcp:
        avg_manager = np.mean([p["manager_turn_share"] for p in gcp]) * 100
        avg_executor = np.mean([p["executor_turn_share"] for p in gcp]) * 100
        avg_analyzer = np.mean([p["analyzer_turn_share"] for p in gcp]) * 100
        print(f"    GroupChat: manager={avg_manager:.1f}% executor={avg_executor:.1f}% "
              f"analyzer={avg_analyzer:.1f}% turn share")

    cp = convergence["profiles"]
    if cp:
        avg_const = np.mean([p["constructive_pct"] for p in cp]) * 100
        avg_mom = np.mean([p["momentum"] for p in cp]) * 100
        avg_eff = np.mean([p["props_per_cmd"] for p in cp])
        print(f"    Sequential: constructive={avg_const:.1f}% momentum={avg_mom:+.1f}% "
              f"props/cmd={avg_eff:.3f}")

    dvp = divergence["profiles"]
    if dvp:
        avg_overlap = np.mean([p["overlap_ratio"] for p in dvp]) * 100
        print(f"    Concurrent: worker cmd overlap={avg_overlap:.1f}%")

    return {
        "debate": debate,
        "group_chat": gc,
        "convergence": convergence,
        "divergence": divergence,
    }


if __name__ == "__main__":
    run_analysis()
