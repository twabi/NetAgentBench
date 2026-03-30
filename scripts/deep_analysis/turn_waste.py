#!/usr/bin/env python3
"""
Module 3: Turn Waste & Action Efficiency

Classifies every action in reasoning_trace as productive, diagnostic,
status_check, submit, redundant, or planning/coordination overhead.

Metrics per run:
- productive_ratio: config commands / total actions
- diagnostic_ratio: show/ping commands / total actions
- waste_ratio: redundant + status_check / total actions
- coordination_overhead: manager/planner/analyzer/reviewer steps / total steps
- action_entropy: Shannon entropy of action-type distribution
- first_productive_latency: steps before first config command
"""

import csv
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Tuple

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from .run_loader import (
    load_and_enrich, get_output_dir, setup_plotting, classify_command,
    PATTERN_COLORS, PATTERN_ORDER, PATTERN_LABELS, DEFAULT_SESSION,
)

ACTION_CATEGORIES = [
    'productive', 'diagnostic', 'status_check', 'submit',
    'redundant', 'coordination',
]
ACTION_COLORS = {
    'productive':    '#2ca02c',
    'diagnostic':    '#1f77b4',
    'status_check':  '#ff7f0e',
    'submit':        '#9467bd',
    'redundant':     '#d62728',
    'coordination':  '#bcbd22',
}


def _classify_action_content(content: str) -> str:
    """Classify an action step content string."""
    c = content.lower().strip()

    if c.startswith('get_session_status'):
        return 'status_check'
    if c.startswith('submit') or c.startswith('finish'):
        return 'submit'
    if c.startswith('get_nodes'):
        return 'status_check'

    if c.startswith('exec_command'):
        cmd_match = re.search(r"'command':\s*['\"](.+?)['\"]", content)
        if not cmd_match:
            cmd_match = re.search(r'"command":\s*["\'](.+?)["\']', content)
        if cmd_match:
            cmd_text = cmd_match.group(1)
            cmd_type = classify_command(cmd_text)
            if cmd_type == 'diagnostic':
                return 'diagnostic'
            if cmd_type in ('constructive', 'destructive'):
                return 'productive'

        if "'command_type': 'read'" in content or '"command_type": "read"' in content:
            return 'diagnostic'
        return 'productive'

    return 'productive'


def _classify_step(step_name: str, content: str) -> Tuple[str, bool]:
    """Classify a reasoning trace step.

    Returns (category, is_action).
    - is_action=True means this is a direct tool-call step
    - is_action=False means coordination/thinking overhead
    """
    s = step_name.lower()

    # Direct action steps (single-agent and sequential executor)
    if s in ('action', 'executor_action'):
        return _classify_action_content(content), True

    # Single-agent thought/observation - not counted as actions
    if s in ('thought', 'observation'):
        return 'thought', False

    # Executor step (single-agent free-form, sometimes contains action descriptions)
    if s == 'executor':
        return _classify_action_content(content), True

    # Sequential pattern: plan, executor_thought, verifier_verdict
    if s in ('plan', 'subtasks'):
        return 'coordination', False
    if s == 'executor_thought':
        return 'thought', False
    if s.startswith('verifier'):
        return 'coordination', False

    # Group chat pattern: manager_turnN, Analyzer_turnN, Planner_turnN,
    # Reviewer_turnN, Executor_turnN
    if s.startswith('manager'):
        return 'coordination', False

    base = s.split('_turn')[0] if '_turn' in s else s
    if base in ('analyzer', 'planner', 'reviewer'):
        return 'coordination', False
    if base == 'executor':
        # Executor turns in group_chat contain actual work
        return 'productive', True

    # Debate pattern: proponent_rN, opponent_rN, judgment
    if base in ('proponent', 'opponent', 'judgment'):
        return 'coordination', False

    # Concurrent pattern: worker_N steps contain actual work
    if s.startswith('worker'):
        return 'productive', True

    return 'other', False


def _shannon_entropy(counts: Counter) -> float:
    total = sum(counts.values())
    if total == 0:
        return 0.0
    probs = [c / total for c in counts.values()]
    return -sum(p * math.log2(p) for p in probs if p > 0)


def analyze_run(run: Dict) -> Dict[str, Any]:
    """Classify all steps in a run and compute efficiency metrics."""
    trace = run.get("reasoning_trace", []) or []

    action_types = Counter()
    total_steps = len(trace)
    coordination_steps = 0
    action_count = 0
    first_productive = -1
    prev_action_content = None
    step_index = 0

    for entry in trace:
        step = entry.get("step", "")
        content = str(entry.get("content", ""))

        cat, is_action = _classify_step(step, content)

        if cat == 'coordination':
            coordination_steps += 1
            action_types['coordination'] += 1
        elif cat == 'thought':
            pass  # don't count thought/observation as actions
        elif is_action:
            # Check redundancy
            if content == prev_action_content and prev_action_content is not None:
                action_types['redundant'] += 1
                action_count += 1
            else:
                action_types[cat] += 1
                action_count += 1
                if cat == 'productive' and first_productive < 0:
                    first_productive = step_index
            prev_action_content = content
        # 'other' non-action steps are ignored

        step_index += 1

    # Use tool_usage from metrics as supplementary ground truth for patterns
    # where actions are embedded in free-text steps
    tool_usage = run.get("metrics", {}).get("tool_usage", {}) or {}
    exec_cmds_from_metrics = tool_usage.get("exec_command", 0)
    status_from_metrics = tool_usage.get("get_session_status", 0)
    submit_from_metrics = (tool_usage.get("submit", 0) +
                           tool_usage.get("finish", 0) +
                           tool_usage.get("finish_execution", 0))

    # For patterns where trace doesn't capture individual tool calls well,
    # use metrics.tool_usage to supplement action counts
    pattern = run["_pattern"]
    if pattern in ('group_chat', 'concurrent') and exec_cmds_from_metrics > 0:
        # Use execution_log to classify commands as productive vs diagnostic
        from .run_loader import extract_execution_commands
        exec_pairs = extract_execution_commands(run.get("execution_log", []))
        prod_from_log = sum(1 for _, cmd in exec_pairs
                            if classify_command(cmd) in ('constructive', 'destructive'))
        diag_from_log = sum(1 for _, cmd in exec_pairs
                            if classify_command(cmd) == 'diagnostic')
        # Fill in from metrics what's not already captured
        extra_exec = exec_cmds_from_metrics - (action_types.get('productive', 0) +
                                                action_types.get('diagnostic', 0))
        if extra_exec > 0:
            action_types['productive'] += prod_from_log
            action_types['diagnostic'] += diag_from_log
            action_types['status_check'] += status_from_metrics
            action_types['submit'] += submit_from_metrics
            action_count += extra_exec + status_from_metrics + submit_from_metrics

    total_actions = max(1, action_count + coordination_steps)
    waste = action_types.get('redundant', 0) + action_types.get('status_check', 0)

    empty = {
        "run_id": run.get("run_id", ""),
        "pattern": pattern,
        "model": run["_model"],
        "task_id": run.get("task_id", ""),
        "total_steps": total_steps,
        "total_actions": total_actions,
        "productive_count": action_types.get('productive', 0),
        "diagnostic_count": action_types.get('diagnostic', 0),
        "status_check_count": action_types.get('status_check', 0),
        "submit_count": action_types.get('submit', 0),
        "redundant_count": action_types.get('redundant', 0),
        "coordination_count": action_types.get('coordination', 0),
        "productive_ratio": action_types.get('productive', 0) / total_actions,
        "diagnostic_ratio": action_types.get('diagnostic', 0) / total_actions,
        "waste_ratio": waste / total_actions,
        "coordination_ratio": coordination_steps / total_steps if total_steps else 0,
        "action_entropy": _shannon_entropy(action_types),
        "first_productive_latency": max(0, first_productive) if first_productive >= 0 else 0,
        "final_score": run.get("scoring", {}).get("final_score", 0),
    }
    return empty


def plot_action_breakdown(all_results: List[Dict], out_dir: Path) -> None:
    """Stacked bar chart of action type breakdown per pattern."""
    setup_plotting()
    fig, ax = plt.subplots(figsize=(10, 6))

    patterns = [p for p in PATTERN_ORDER
                if any(r["pattern"] == p for r in all_results)]

    x = np.arange(len(patterns))
    bottom = np.zeros(len(patterns))

    for cat in ACTION_CATEGORIES:
        means = []
        for p in patterns:
            vals = [r[f"{cat}_count"] / max(1, r["total_actions"]) * 100
                    for r in all_results
                    if r["pattern"] == p and r["total_actions"] > 0]
            means.append(np.mean(vals) if vals else 0)
        ax.bar(x, means, 0.6, bottom=bottom,
               color=ACTION_COLORS.get(cat, '#888888'),
               label=cat.replace('_', ' ').title(), alpha=0.85)
        bottom += np.array(means)

    ax.set_xticks(x)
    ax.set_xticklabels([PATTERN_LABELS.get(p, p) for p in patterns])
    ax.set_ylabel("Percentage of Actions (%)")
    ax.set_title("Action Type Breakdown by Pattern")
    ax.legend(loc='upper right', fontsize=8)
    ax.set_ylim(0, 110)
    fig.tight_layout()
    fig.savefig(out_dir / "turn_waste_breakdown.png")
    plt.close(fig)


def plot_coordination_tax(all_results: List[Dict], out_dir: Path) -> None:
    """Box plot showing coordination overhead ratio per pattern."""
    setup_plotting()
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    patterns = [p for p in PATTERN_ORDER
                if any(r["pattern"] == p for r in all_results)]
    colors = [PATTERN_COLORS.get(p, '#888888') for p in patterns]

    # Left: coordination ratio
    ax = axes[0]
    data = [[r["coordination_ratio"] * 100 for r in all_results
             if r["pattern"] == p] or [0] for p in patterns]
    bp = ax.boxplot(data, patch_artist=True, widths=0.5,
                    medianprops=dict(color='black', linewidth=2))
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    ax.set_xticks(range(1, len(patterns) + 1))
    ax.set_xticklabels([PATTERN_LABELS.get(p, p) for p in patterns])
    ax.set_ylabel("Coordination Overhead (%)")
    ax.set_title("Coordination Tax by Pattern")

    # Right: first productive action latency
    ax = axes[1]
    data = [[r["first_productive_latency"] for r in all_results
             if r["pattern"] == p and r["total_actions"] > 0] or [0]
            for p in patterns]
    bp = ax.boxplot(data, patch_artist=True, widths=0.5,
                    medianprops=dict(color='black', linewidth=2))
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    ax.set_xticks(range(1, len(patterns) + 1))
    ax.set_xticklabels([PATTERN_LABELS.get(p, p) for p in patterns])
    ax.set_ylabel("Steps Before First Config Command")
    ax.set_title("First Productive Action Latency")

    fig.tight_layout()
    fig.savefig(out_dir / "turn_waste_coordination.png")
    plt.close(fig)


def plot_waste_vs_score(all_results: List[Dict], out_dir: Path) -> None:
    """Scatter plot of waste ratio vs final score, colored by pattern."""
    setup_plotting()
    fig, ax = plt.subplots(figsize=(8, 6))

    for pattern in PATTERN_ORDER:
        runs = [r for r in all_results
                if r["pattern"] == pattern and r["total_actions"] > 0]
        if not runs:
            continue
        xs = [r["waste_ratio"] * 100 for r in runs]
        ys = [r["final_score"] for r in runs]
        ax.scatter(xs, ys, label=PATTERN_LABELS.get(pattern, pattern),
                   color=PATTERN_COLORS.get(pattern, '#888888'),
                   alpha=0.6, s=40, edgecolors='white', linewidths=0.5)

    ax.set_xlabel("Turn Waste Rate (%)")
    ax.set_ylabel("Final Score")
    ax.set_title("Turn Waste vs Performance")
    ax.legend(loc='upper right', fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "turn_waste_vs_score.png")
    plt.close(fig)


def save_csv(all_results: List[Dict], out_dir: Path) -> None:
    fields = [
        "run_id", "pattern", "model", "task_id", "total_steps",
        "total_actions", "productive_count", "diagnostic_count",
        "status_check_count", "submit_count", "redundant_count",
        "coordination_count", "productive_ratio", "diagnostic_ratio",
        "waste_ratio", "coordination_ratio", "action_entropy",
        "first_productive_latency", "final_score",
    ]
    with open(out_dir / "turn_waste.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in all_results:
            writer.writerow({k: r[k] for k in fields})


def run_analysis(session_dir: Path | None = None) -> List[Dict]:
    """Run the full turn waste analysis."""
    runs = load_and_enrich(session_dir)
    out_dir = get_output_dir(session_dir)

    print(f"  Turn Waste: analyzing {len(runs)} runs...")
    all_results = [analyze_run(r) for r in runs]

    plot_action_breakdown(all_results, out_dir)
    plot_coordination_tax(all_results, out_dir)
    plot_waste_vs_score(all_results, out_dir)
    save_csv(all_results, out_dir)

    for pattern in PATTERN_ORDER:
        pr = [r for r in all_results if r["pattern"] == pattern and r["total_actions"] > 0]
        if not pr:
            continue
        avg_prod = np.mean([r["productive_ratio"] for r in pr]) * 100
        avg_waste = np.mean([r["waste_ratio"] for r in pr]) * 100
        avg_coord = np.mean([r["coordination_ratio"] for r in pr]) * 100
        print(f"    {PATTERN_LABELS.get(pattern, pattern):>12}: "
              f"productive={avg_prod:.1f}% waste={avg_waste:.1f}% "
              f"coordination={avg_coord:.1f}%")

    return all_results


if __name__ == "__main__":
    run_analysis()
