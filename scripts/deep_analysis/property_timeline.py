#!/usr/bin/env python3
"""
Module 1: Property Satisfaction Timeline

Parses reasoning_trace observation fields to approximate when properties
become satisfied (and broken) during a run. Produces per-pattern regression
curves showing how state evolves over time.

Metrics per run:
- peak_properties: max properties simultaneously evident at any step
- final_properties: properties satisfied at end (from property_results)
- regression_rate: (peak - final) / peak
- time_to_first: turns before first property evidence
- stability_duration: max consecutive turns with all observed props held
"""

import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from .run_loader import (
    load_and_enrich, get_output_dir, setup_plotting,
    PATTERN_COLORS, PATTERN_ORDER, PATTERN_LABELS, DEFAULT_SESSION,
)


def _build_property_search_map(run: Dict) -> Dict[str, str]:
    """Extract property_id -> search_text from property_results.

    The search_text is the string the benchmark uses to decide satisfaction.
    If we find this text in an observation, the property is likely satisfied.
    """
    search_map = {}
    for pr in run.get("property_results", []):
        pid = pr.get("property_id", "")
        obs_parsed = pr.get("observation_parsed")
        if obs_parsed and isinstance(obs_parsed, dict):
            st = obs_parsed.get("search_text", "")
            if st:
                search_map[pid] = st
    return search_map


def _build_observation_timeline(run: Dict) -> List[str]:
    """Extract ordered observation strings from reasoning_trace."""
    observations = []
    for entry in run.get("reasoning_trace", []):
        if entry.get("step") == "observation":
            content = entry.get("content", "")
            observations.append(str(content))
    return observations


def analyze_run(run: Dict) -> Dict[str, Any]:
    """Analyze a single run's property satisfaction timeline."""
    search_map = _build_property_search_map(run)
    observations = _build_observation_timeline(run)

    n_props = len(search_map)
    if n_props == 0 or len(observations) == 0:
        final_satisfied = sum(
            1 for pr in run.get("property_results", []) if pr.get("satisfied")
        )
        total_props = len(run.get("property_results", []))
        return {
            "run_id": run.get("run_id", ""),
            "pattern": run["_pattern"],
            "model": run["_model"],
            "task_id": run.get("task_id", ""),
            "n_properties": total_props,
            "n_observations": len(observations),
            "peak_properties": final_satisfied,
            "final_properties": final_satisfied,
            "regression_rate": 0.0,
            "time_to_first": 0,
            "stability_duration": 0,
            "timeline": [],
        }

    # Track which properties have evidence at each observation step
    ever_satisfied = set()
    timeline = []  # list of sets, one per observation
    for obs_text in observations:
        obs_lower = obs_text.lower()
        currently_evident = set()
        for pid, search_text in search_map.items():
            if search_text.lower() in obs_lower:
                currently_evident.add(pid)
                ever_satisfied.add(pid)
        timeline.append(currently_evident)

    # Build cumulative satisfaction curve:
    # At each step, a property is "believed satisfied" if it was found in this
    # or any previous observation AND has not been contradicted.
    # Simplified: track the high-water mark and detect regressions.
    cumulative = set()
    satisfaction_counts = []
    for step_set in timeline:
        cumulative = cumulative | step_set
        satisfaction_counts.append(len(cumulative))

    # Detect regressions: points where a property that was previously seen
    # is no longer appearing in recent observations (sliding window)
    WINDOW = 5
    regression_curve = []
    for i in range(len(timeline)):
        recent_window = set()
        for j in range(max(0, i - WINDOW + 1), i + 1):
            recent_window |= timeline[j]
        regression_curve.append(len(recent_window))

    # Use final property_results as ground truth for final count
    final_satisfied = sum(
        1 for pr in run.get("property_results", []) if pr.get("satisfied")
    )
    total_props = len(run.get("property_results", []))
    peak = max(regression_curve) if regression_curve else 0

    # Time to first property evidence
    time_to_first = 0
    for i, s in enumerate(satisfaction_counts):
        if s > 0:
            time_to_first = i
            break

    # Stability duration: longest consecutive stretch at peak
    stability = 0
    current_streak = 0
    for count in regression_curve:
        if count == peak and peak > 0:
            current_streak += 1
            stability = max(stability, current_streak)
        else:
            current_streak = 0

    regression_rate = (peak - final_satisfied) / peak if peak > 0 else 0.0

    return {
        "run_id": run.get("run_id", ""),
        "pattern": run["_pattern"],
        "model": run["_model"],
        "task_id": run.get("task_id", ""),
        "n_properties": total_props,
        "n_observations": len(observations),
        "peak_properties": peak,
        "final_properties": final_satisfied,
        "regression_rate": max(0.0, regression_rate),
        "time_to_first": time_to_first,
        "stability_duration": stability,
        "timeline": regression_curve,
    }


def plot_regression_curves(
    all_results: List[Dict], out_dir: Path
) -> None:
    """Plot average property satisfaction curves per pattern."""
    setup_plotting()

    fig, ax = plt.subplots(figsize=(10, 5))

    for pattern in PATTERN_ORDER:
        timelines = [
            r["timeline"] for r in all_results
            if r["pattern"] == pattern and len(r["timeline"]) > 1
        ]
        if not timelines:
            continue

        max_len = max(len(t) for t in timelines)
        padded = np.array([
            t + [t[-1]] * (max_len - len(t)) for t in timelines
        ], dtype=float)
        mean = np.mean(padded, axis=0)
        std = np.std(padded, axis=0)
        x = np.arange(1, max_len + 1)
        color = PATTERN_COLORS.get(pattern, '#888888')

        ax.plot(x, mean, label=PATTERN_LABELS.get(pattern, pattern),
                color=color, linewidth=2.5)
        ax.fill_between(x, np.clip(mean - std, 0, None),
                        mean + std, color=color, alpha=0.15)

    ax.set_xlabel("Observation Step")
    ax.set_ylabel("Properties with Evidence (windowed)")
    ax.set_title("Property Satisfaction Timeline by Pattern (mean +/- 1 std)")
    ax.legend(loc='upper left', framealpha=0.9)
    fig.tight_layout()
    fig.savefig(out_dir / "property_timeline_curves.png")
    plt.close(fig)


def plot_regression_by_task(all_results: List[Dict], out_dir: Path) -> None:
    """Plot regression curves per pattern, faceted by task."""
    setup_plotting()
    tasks = sorted(set(r["task_id"] for r in all_results))
    n_tasks = len(tasks)
    if n_tasks == 0:
        return

    fig, axes = plt.subplots(1, n_tasks, figsize=(5 * n_tasks, 4), sharey=True)
    if n_tasks == 1:
        axes = [axes]

    for ax, task in zip(axes, tasks):
        for pattern in PATTERN_ORDER:
            timelines = [
                r["timeline"] for r in all_results
                if r["pattern"] == pattern and r["task_id"] == task
                and len(r["timeline"]) > 1
            ]
            if not timelines:
                continue
            max_len = max(len(t) for t in timelines)
            padded = np.array([
                t + [t[-1]] * (max_len - len(t)) for t in timelines
            ], dtype=float)
            mean = np.mean(padded, axis=0)
            x = np.arange(1, max_len + 1)
            color = PATTERN_COLORS.get(pattern, '#888888')
            ax.plot(x, mean, label=PATTERN_LABELS.get(pattern, pattern),
                    color=color, linewidth=2)

        from .run_loader import TASK_METADATA
        display = TASK_METADATA.get(task, {}).get("display_name", task)
        ax.set_title(display)
        ax.set_xlabel("Observation Step")

    axes[0].set_ylabel("Properties with Evidence")
    axes[-1].legend(loc='upper left', fontsize=7, framealpha=0.9)
    fig.suptitle("Property Satisfaction Timeline by Task", fontweight='bold', y=1.02)
    fig.tight_layout()
    fig.savefig(out_dir / "property_timeline_by_task.png")
    plt.close(fig)


def plot_regression_rate_bars(all_results: List[Dict], out_dir: Path) -> None:
    """Box plot of regression rate per pattern."""
    setup_plotting()

    fig, ax = plt.subplots(figsize=(8, 5))
    patterns = [p for p in PATTERN_ORDER
                if any(r["pattern"] == p for r in all_results)]
    colors = [PATTERN_COLORS.get(p, '#888888') for p in patterns]
    data = [[r["regression_rate"] for r in all_results if r["pattern"] == p]
            or [0] for p in patterns]

    bp = ax.boxplot(data, patch_artist=True, widths=0.5,
                    medianprops=dict(color='black', linewidth=2))
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    ax.set_xticks(range(1, len(patterns) + 1))
    ax.set_xticklabels([PATTERN_LABELS.get(p, p) for p in patterns])
    ax.set_ylabel("Regression Rate (peak - final) / peak")
    ax.set_title("Property Regression Rate by Pattern")
    fig.tight_layout()
    fig.savefig(out_dir / "property_regression_rate.png")
    plt.close(fig)


def save_csv(all_results: List[Dict], out_dir: Path) -> None:
    """Save per-run property timeline metrics to CSV."""
    fields = [
        "run_id", "pattern", "model", "task_id", "n_properties",
        "n_observations", "peak_properties", "final_properties",
        "regression_rate", "time_to_first", "stability_duration",
    ]
    with open(out_dir / "property_timeline.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in all_results:
            writer.writerow({k: r[k] for k in fields})


def run_analysis(session_dir: Path | None = None) -> List[Dict]:
    """Run the full property timeline analysis."""
    runs = load_and_enrich(session_dir)
    out_dir = get_output_dir(session_dir)

    print(f"  Property Timeline: analyzing {len(runs)} runs...")
    all_results = [analyze_run(r) for r in runs]

    plot_regression_curves(all_results, out_dir)
    plot_regression_by_task(all_results, out_dir)
    plot_regression_rate_bars(all_results, out_dir)
    save_csv(all_results, out_dir)

    # Print summary
    for pattern in PATTERN_ORDER:
        pr = [r for r in all_results if r["pattern"] == pattern]
        if not pr:
            continue
        avg_reg = np.mean([r["regression_rate"] for r in pr])
        avg_peak = np.mean([r["peak_properties"] for r in pr])
        avg_final = np.mean([r["final_properties"] for r in pr])
        print(f"    {PATTERN_LABELS.get(pattern, pattern):>12}: "
              f"peak={avg_peak:.1f} final={avg_final:.1f} regression={avg_reg:.3f}")

    return all_results


if __name__ == "__main__":
    run_analysis()
