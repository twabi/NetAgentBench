#!/usr/bin/env python3
"""
Module 8: Troubleshooting vs Construction Behavioral Split

Tests whether gamma_T (task type) predicts distinct behavioral signatures.
Compares CONSTRUCTION and TROUBLESHOOTING tasks across all behavioral
dimensions: productive ratio, router entropy, coordination overhead,
token usage, error density, and score.

Validates the paper's claim that task type is a meaningful factor that
changes how agents should be orchestrated.
"""

import csv
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats as scipy_stats

from .run_loader import (
    load_and_enrich, get_output_dir, setup_plotting, classify_command,
    extract_execution_commands,
    PATTERN_COLORS, PATTERN_ORDER, PATTERN_LABELS, DEFAULT_SESSION,
    TASK_METADATA,
)

TYPE_COLORS = {'configuration': '#0173B2', 'troubleshooting': '#DE8F05'}
TYPE_LABELS = {'configuration': 'Construction', 'troubleshooting': 'Troubleshooting'}


def _compute_run_metrics(run: Dict) -> Dict[str, Any]:
    """Compute behavioral metrics for a single run."""
    metrics = run.get("metrics", {}) or {}
    tu = metrics.get("token_usage", {}) or {}
    total_tokens = tu.get("total_tokens", 0) or 0
    scoring = run.get("scoring", {}) or {}
    final_score = scoring.get("final_score", 0) or 0

    exec_log = run.get("execution_log", []) or []
    pairs = extract_execution_commands(exec_log)
    total_cmds = len(pairs)

    constructive = sum(1 for _, cmd in pairs if classify_command(cmd) == 'constructive')
    diagnostic = sum(1 for _, cmd in pairs if classify_command(cmd) == 'diagnostic')
    destructive = sum(1 for _, cmd in pairs if classify_command(cmd) == 'destructive')

    # Router entropy
    from collections import Counter
    import math
    router_counts = Counter(r for r, _ in pairs)
    total_r = sum(router_counts.values())
    if total_r > 0:
        probs = [c / total_r for c in router_counts.values()]
        entropy = -sum(p * math.log2(p) for p in probs if p > 0)
    else:
        entropy = 0.0

    # Coordination steps from reasoning trace
    trace = run.get("reasoning_trace", []) or []
    total_steps = len(trace)
    coord_steps = 0
    for entry in trace:
        s = entry.get("step", "").lower()
        if any(s.startswith(prefix) for prefix in
               ('manager', 'analyzer', 'planner', 'reviewer', 'verifier',
                'proponent', 'opponent', 'judgment')):
            coord_steps += 1
    coord_ratio = coord_steps / total_steps if total_steps > 0 else 0

    satisfied = sum(1 for p in run.get("property_results", []) if p.get("satisfied"))
    total_props = len(run.get("property_results", []))
    failed_cmds = metrics.get("failed_commands", 0) or 0

    return {
        "run_id": run.get("run_id", ""),
        "pattern": run["_pattern"],
        "model": run["_model"],
        "task_id": run.get("task_id", ""),
        "task_type": run["_difficulty"],  # reuse for grouping
        "gamma_t": TASK_METADATA.get(run.get("task_id", ""), {}).get("type", "unknown"),
        "final_score": final_score,
        "total_tokens": total_tokens,
        "total_commands": total_cmds,
        "constructive_pct": constructive / max(1, total_cmds) * 100,
        "diagnostic_pct": diagnostic / max(1, total_cmds) * 100,
        "destructive_pct": destructive / max(1, total_cmds) * 100,
        "router_entropy": entropy,
        "coordination_ratio": coord_ratio * 100,
        "satisfied_properties": satisfied,
        "total_properties": total_props,
        "error_rate": failed_cmds / max(1, total_cmds) * 100,
    }


def plot_behavioral_split(all_results: List[Dict], out_dir: Path) -> None:
    """Side-by-side box plots comparing behavioral metrics by task type."""
    setup_plotting()

    metrics_to_plot = [
        ("constructive_pct", "Constructive Commands (%)"),
        ("diagnostic_pct", "Diagnostic Commands (%)"),
        ("router_entropy", "Router Entropy (bits)"),
        ("coordination_ratio", "Coordination Overhead (%)"),
        ("total_tokens", "Total Tokens"),
        ("error_rate", "Error Rate (%)"),
    ]

    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    axes = axes.flatten()

    task_types = ['configuration', 'troubleshooting']

    for ax, (metric, label) in zip(axes, metrics_to_plot):
        data_by_type = {}
        for tt in task_types:
            vals = [r[metric] for r in all_results if r["gamma_t"] == tt]
            if metric == "total_tokens":
                vals = [v / 1000 for v in vals]
            data_by_type[tt] = vals

        positions = [1, 2]
        data = [data_by_type.get(tt, [0]) for tt in task_types]
        colors = [TYPE_COLORS.get(tt, '#888888') for tt in task_types]

        bp = ax.boxplot(data, patch_artist=True, widths=0.5, positions=positions,
                        medianprops=dict(color='black', linewidth=2))
        for patch, color in zip(bp['boxes'], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)

        ax.set_xticks(positions)
        ax.set_xticklabels([TYPE_LABELS.get(tt, tt) for tt in task_types])
        ylabel = label if metric != "total_tokens" else "Total Tokens (K)"
        ax.set_ylabel(ylabel)
        ax.set_title(label)

        # Statistical test
        if len(data[0]) > 1 and len(data[1]) > 1:
            u_stat, p_val = scipy_stats.mannwhitneyu(data[0], data[1],
                                                      alternative='two-sided')
            sig = "***" if p_val < 0.001 else "**" if p_val < 0.01 else "*" if p_val < 0.05 else "ns"
            ax.set_xlabel(f"p={p_val:.4f} ({sig})", fontsize=8)

    fig.suptitle("Behavioral Signatures: Construction vs Troubleshooting",
                 fontweight='bold', y=1.01)
    fig.tight_layout()
    fig.savefig(out_dir / "task_type_behavioral_split.png")
    plt.close(fig)


def plot_pattern_x_type(all_results: List[Dict], out_dir: Path) -> None:
    """Grouped box plots: score by pattern, split by task type."""
    setup_plotting()

    task_types = ['configuration', 'troubleshooting']
    patterns = [p for p in PATTERN_ORDER
                if any(r["pattern"] == p for r in all_results)]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    for ax, tt in zip(axes, task_types):
        data = []
        colors = []
        for p in patterns:
            vals = [r["final_score"] for r in all_results
                    if r["pattern"] == p and r["gamma_t"] == tt]
            data.append(vals if vals else [0])
            colors.append(PATTERN_COLORS.get(p, '#888888'))

        bp = ax.boxplot(data, patch_artist=True, widths=0.5,
                        medianprops=dict(color='black', linewidth=2))
        for patch, color in zip(bp['boxes'], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)

        ax.set_xticks(range(1, len(patterns) + 1))
        ax.set_xticklabels([PATTERN_LABELS.get(p, p)[:6] for p in patterns],
                           fontsize=8, rotation=20, ha='right')
        ax.set_ylabel("Final Score")
        ax.set_title(f"{TYPE_LABELS[tt]} Tasks")
        ax.set_ylim(-0.05, 1.05)

    fig.suptitle("Pattern Performance by Task Type", fontweight='bold', y=1.02)
    fig.tight_layout()
    fig.savefig(out_dir / "task_type_pattern_scores.png")
    plt.close(fig)


def plot_coordination_by_pattern_type(all_results: List[Dict], out_dir: Path) -> None:
    """Coordination overhead by pattern, split by task type."""
    setup_plotting()

    task_types = ['configuration', 'troubleshooting']
    patterns = [p for p in PATTERN_ORDER
                if any(r["pattern"] == p for r in all_results)]

    n_types = len(task_types)
    n_patterns = len(patterns)
    x = np.arange(n_patterns)
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 5))
    for i, tt in enumerate(task_types):
        means = []
        for p in patterns:
            vals = [r["coordination_ratio"] for r in all_results
                    if r["pattern"] == p and r["gamma_t"] == tt]
            means.append(np.mean(vals) if vals else 0)
        offset = (i - 0.5) * width
        ax.bar(x + offset, means, width * 0.9,
               label=TYPE_LABELS[tt], color=TYPE_COLORS[tt], alpha=0.85)

    ax.set_xticks(x)
    ax.set_xticklabels([PATTERN_LABELS.get(p, p) for p in patterns])
    ax.set_ylabel("Coordination Overhead (%)")
    ax.set_title("Coordination Tax: Construction vs Troubleshooting")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "task_type_coordination.png")
    plt.close(fig)


def save_csv(all_results: List[Dict], out_dir: Path) -> None:
    fields = [
        "run_id", "pattern", "model", "task_id", "gamma_t",
        "final_score", "total_tokens", "total_commands",
        "constructive_pct", "diagnostic_pct", "destructive_pct",
        "router_entropy", "coordination_ratio", "error_rate",
        "satisfied_properties", "total_properties",
    ]
    with open(out_dir / "task_type_split.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        for r in all_results:
            writer.writerow(r)


def run_analysis(session_dir: Path | None = None) -> List[Dict]:
    """Run the task type behavioral split analysis."""
    runs = load_and_enrich(session_dir)
    out_dir = get_output_dir(session_dir)

    print(f"  Task Type Split: analyzing {len(runs)} runs...")
    all_results = [_compute_run_metrics(r) for r in runs]

    plot_behavioral_split(all_results, out_dir)
    plot_pattern_x_type(all_results, out_dir)
    plot_coordination_by_pattern_type(all_results, out_dir)
    save_csv(all_results, out_dir)

    for tt in ['configuration', 'troubleshooting']:
        subset = [r for r in all_results if r["gamma_t"] == tt]
        if not subset:
            continue
        avg_score = np.mean([r["final_score"] for r in subset])
        avg_const = np.mean([r["constructive_pct"] for r in subset])
        avg_diag = np.mean([r["diagnostic_pct"] for r in subset])
        avg_ent = np.mean([r["router_entropy"] for r in subset])
        avg_coord = np.mean([r["coordination_ratio"] for r in subset])
        print(f"    {TYPE_LABELS[tt]:>18}: score={avg_score:.3f} "
              f"const={avg_const:.1f}% diag={avg_diag:.1f}% "
              f"entropy={avg_ent:.2f} coord={avg_coord:.1f}%")

    return all_results


if __name__ == "__main__":
    run_analysis()
