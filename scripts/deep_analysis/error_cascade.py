#!/usr/bin/env python3
"""
Module 5: Error Cascade & Recovery Analysis

Tracks temporal error sequences within runs. Measures how quickly agents
recover from errors, whether errors compound, and whether recovery attempts
introduce new errors.

Metrics per run:
- error_count: total failed observations/commands
- error_density: errors / total observations
- max_cascade_length: longest consecutive error streak
- avg_recovery_time: mean steps between error and next success
- error_clustering: Gini coefficient of error distribution over time
"""

import csv
from pathlib import Path
from typing import Any, Dict, List

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from .run_loader import (
    load_and_enrich, get_output_dir, setup_plotting,
    PATTERN_COLORS, PATTERN_ORDER, PATTERN_LABELS, DEFAULT_SESSION,
)


def _parse_observation_success(content) -> bool | None:
    """Determine if an observation indicates success or failure.

    Returns True (success), False (failure), or None (not determinable).
    """
    if isinstance(content, dict):
        if 'success' in content:
            return bool(content['success'])
        if 'exit_code' in content:
            return content['exit_code'] == 0
        return None

    s = str(content).lower()

    # Try to detect dict-like string from repr
    if "'success': false" in s or "'success': False" in s:
        return False
    if "'success': true" in s or "'success': True" in s:
        return True
    if "'exit_code': 1" in s or "exit_code': 1" in s:
        return False
    if 'error' in s and ('command' in s or 'failed' in s):
        return False
    return None


def _gini_coefficient(values: List[float]) -> float:
    """Compute Gini coefficient (0=uniform, 1=concentrated)."""
    if not values or sum(values) == 0:
        return 0.0
    arr = np.array(sorted(values), dtype=float)
    n = len(arr)
    index = np.arange(1, n + 1)
    return float((2 * np.sum(index * arr) - (n + 1) * np.sum(arr)) / (n * np.sum(arr)))


def analyze_run(run: Dict) -> Dict[str, Any]:
    """Analyze error cascade patterns in a single run."""
    trace = run.get("reasoning_trace", []) or []

    # Extract observation outcomes in order
    outcomes = []  # list of (step_index, success_bool)
    for i, entry in enumerate(trace):
        if entry.get("step") == "observation":
            success = _parse_observation_success(entry.get("content"))
            if success is not None:
                outcomes.append((i, success))

    if not outcomes:
        failed_cmds = run.get("metrics", {}).get("failed_commands", 0) or 0
        total_cmds = run.get("metrics", {}).get("total_commands", 0) or 0
        return {
            "run_id": run.get("run_id", ""),
            "pattern": run["_pattern"],
            "model": run["_model"],
            "task_id": run.get("task_id", ""),
            "total_observations": 0,
            "error_count": failed_cmds,
            "error_density": failed_cmds / max(1, total_cmds),
            "max_cascade_length": 0,
            "avg_recovery_time": 0.0,
            "error_clustering": 0.0,
            "final_score": run.get("scoring", {}).get("final_score", 0),
        }

    total_obs = len(outcomes)
    errors = [(idx, s) for idx, s in outcomes if not s]
    error_count = len(errors)
    error_density = error_count / total_obs if total_obs > 0 else 0

    # Max cascade: longest consecutive failure streak
    max_cascade = 0
    current_cascade = 0
    for _, success in outcomes:
        if not success:
            current_cascade += 1
            max_cascade = max(max_cascade, current_cascade)
        else:
            current_cascade = 0

    # Recovery time: steps between each error and the next success
    recovery_times = []
    for i, (_, success) in enumerate(outcomes):
        if not success:
            # Find next success
            for j in range(i + 1, len(outcomes)):
                if outcomes[j][1]:
                    recovery_times.append(j - i)
                    break
    avg_recovery = np.mean(recovery_times) if recovery_times else 0.0

    # Error clustering: divide run into quartiles, compute Gini of error counts
    if total_obs >= 4:
        q_size = total_obs // 4
        quartile_errors = []
        for q in range(4):
            start = q * q_size
            end = start + q_size if q < 3 else total_obs
            q_errors = sum(1 for _, s in outcomes[start:end] if not s)
            quartile_errors.append(float(q_errors))
        clustering = _gini_coefficient(quartile_errors)
    else:
        clustering = 0.0

    return {
        "run_id": run.get("run_id", ""),
        "pattern": run["_pattern"],
        "model": run["_model"],
        "task_id": run.get("task_id", ""),
        "total_observations": total_obs,
        "error_count": error_count,
        "error_density": error_density,
        "max_cascade_length": max_cascade,
        "avg_recovery_time": avg_recovery,
        "error_clustering": clustering,
        "final_score": run.get("scoring", {}).get("final_score", 0),
    }


def plot_error_density(all_results: List[Dict], out_dir: Path) -> None:
    """Box plot of error density per pattern."""
    setup_plotting()
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    patterns = [p for p in PATTERN_ORDER
                if any(r["pattern"] == p for r in all_results)]
    colors = [PATTERN_COLORS.get(p, '#888888') for p in patterns]

    # Left: error density
    ax = axes[0]
    data = [[r["error_density"] * 100 for r in all_results
             if r["pattern"] == p and r["total_observations"] > 0] or [0]
            for p in patterns]
    bp = ax.boxplot(data, patch_artist=True, widths=0.5,
                    medianprops=dict(color='black', linewidth=2))
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    ax.set_xticks(range(1, len(patterns) + 1))
    ax.set_xticklabels([PATTERN_LABELS.get(p, p) for p in patterns])
    ax.set_ylabel("Error Density (%)")
    ax.set_title("Error Density by Pattern")

    # Right: max cascade length
    ax = axes[1]
    data = [[r["max_cascade_length"] for r in all_results if r["pattern"] == p]
            or [0] for p in patterns]
    bp = ax.boxplot(data, patch_artist=True, widths=0.5,
                    medianprops=dict(color='black', linewidth=2))
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    ax.set_xticks(range(1, len(patterns) + 1))
    ax.set_xticklabels([PATTERN_LABELS.get(p, p) for p in patterns])
    ax.set_ylabel("Max Consecutive Errors")
    ax.set_title("Max Error Cascade Length by Pattern")

    fig.tight_layout()
    fig.savefig(out_dir / "error_cascade_density.png")
    plt.close(fig)


def plot_recovery_and_clustering(all_results: List[Dict], out_dir: Path) -> None:
    """Recovery time and clustering analysis."""
    setup_plotting()
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    patterns = [p for p in PATTERN_ORDER
                if any(r["pattern"] == p for r in all_results)]
    colors = [PATTERN_COLORS.get(p, '#888888') for p in patterns]

    # Left: recovery time
    ax = axes[0]
    data = [[r["avg_recovery_time"] for r in all_results
             if r["pattern"] == p and r["error_count"] > 0] or [0]
            for p in patterns]
    bp = ax.boxplot(data, patch_artist=True, widths=0.5,
                    medianprops=dict(color='black', linewidth=2))
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    ax.set_xticks(range(1, len(patterns) + 1))
    ax.set_xticklabels([PATTERN_LABELS.get(p, p) for p in patterns])
    ax.set_ylabel("Steps to Recover")
    ax.set_title("Average Recovery Time by Pattern")

    # Right: error density vs final score scatter
    ax = axes[1]
    for p in patterns:
        runs = [r for r in all_results
                if r["pattern"] == p and r["total_observations"] > 0]
        if not runs:
            continue
        xs = [r["error_density"] * 100 for r in runs]
        ys = [r["final_score"] for r in runs]
        ax.scatter(xs, ys, label=PATTERN_LABELS.get(p, p),
                   color=PATTERN_COLORS.get(p, '#888888'),
                   alpha=0.5, s=35, edgecolors='white', linewidths=0.5)
    ax.set_xlabel("Error Density (%)")
    ax.set_ylabel("Final Score")
    ax.set_title("Error Density vs Performance")
    ax.legend(fontsize=8)

    fig.tight_layout()
    fig.savefig(out_dir / "error_cascade_recovery.png")
    plt.close(fig)


def save_csv(all_results: List[Dict], out_dir: Path) -> None:
    fields = [
        "run_id", "pattern", "model", "task_id", "total_observations",
        "error_count", "error_density", "max_cascade_length",
        "avg_recovery_time", "error_clustering", "final_score",
    ]
    with open(out_dir / "error_cascade.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in all_results:
            writer.writerow({k: r[k] for k in fields})


def run_analysis(session_dir: Path | None = None) -> List[Dict]:
    """Run the full error cascade analysis."""
    runs = load_and_enrich(session_dir)
    out_dir = get_output_dir(session_dir)

    print(f"  Error Cascade: analyzing {len(runs)} runs...")
    all_results = [analyze_run(r) for r in runs]

    plot_error_density(all_results, out_dir)
    plot_recovery_and_clustering(all_results, out_dir)
    save_csv(all_results, out_dir)

    for pattern in PATTERN_ORDER:
        pr = [r for r in all_results if r["pattern"] == pattern]
        if not pr:
            continue
        avg_dens = np.mean([r["error_density"] for r in pr]) * 100
        avg_casc = np.mean([r["max_cascade_length"] for r in pr])
        avg_recov = np.mean([r["avg_recovery_time"] for r in pr
                             if r["error_count"] > 0]) if any(r["error_count"] > 0 for r in pr) else 0
        print(f"    {PATTERN_LABELS.get(pattern, pattern):>12}: "
              f"density={avg_dens:.1f}% cascade={avg_casc:.1f} recovery={avg_recov:.1f}")

    return all_results


if __name__ == "__main__":
    run_analysis()
