#!/usr/bin/env python3
"""
Module 7: Per-Model Pattern Sensitivity

Answers: does the optimal pattern change depending on which model you use?
Computes "pattern lift" (multi-agent score - single-agent score) per model
and tests whether weaker models benefit more or less from multi-agent coordination.

Metrics:
- pattern_lift: mean(multi_pattern_score) - mean(single_score) per model x pattern
- optimal_pattern: best-scoring pattern per model x task
- pattern_stability: does the pattern ranking hold across models?
- model_gap: how much does the model quality amplify pattern effects?
"""

import csv
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from .run_loader import (
    load_and_enrich, get_output_dir, setup_plotting,
    PATTERN_COLORS, PATTERN_ORDER, PATTERN_LABELS, DEFAULT_SESSION,
    TASK_METADATA,
)


def _collect_scores(runs: List[Dict]) -> Dict:
    """Group scores by model x pattern x task."""
    scores = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for r in runs:
        model = r["_model"]
        pattern = r["_pattern"]
        task = r.get("task_id", "unknown")
        score = r.get("scoring", {}).get("final_score", 0) or 0
        scores[model][pattern][task].append(score)
    return scores


def analyze_runs(runs: List[Dict]) -> Dict[str, Any]:
    """Compute per-model pattern sensitivity metrics."""
    scores = _collect_scores(runs)
    models = sorted(scores.keys())
    tasks = sorted(set(r.get("task_id", "") for r in runs))

    # Pattern lift per model: mean(pattern_score) - mean(single_score)
    lift_data = {}
    for model in models:
        single_scores = []
        for task in tasks:
            single_scores.extend(scores[model].get("single", {}).get(task, []))
        single_mean = np.mean(single_scores) if single_scores else 0

        lift_data[model] = {"single_mean": single_mean, "lifts": {}}
        for pattern in PATTERN_ORDER:
            if pattern == "single":
                continue
            pattern_scores = []
            for task in tasks:
                pattern_scores.extend(scores[model].get(pattern, {}).get(task, []))
            pattern_mean = np.mean(pattern_scores) if pattern_scores else 0
            lift_data[model]["lifts"][pattern] = pattern_mean - single_mean

    # Best pattern per model x task
    best_patterns = {}
    for model in models:
        best_patterns[model] = {}
        for task in tasks:
            best_score = -1
            best_pat = "none"
            for pattern in PATTERN_ORDER:
                vals = scores[model].get(pattern, {}).get(task, [])
                if vals:
                    m = np.mean(vals)
                    if m > best_score:
                        best_score = m
                        best_pat = pattern
            best_patterns[model][task] = (best_pat, best_score)

    # Pattern stability: count how often each pattern is "best" across models
    pattern_wins = defaultdict(lambda: defaultdict(int))
    for model in models:
        for task in tasks:
            pat, _ = best_patterns[model][task]
            pattern_wins[task][pat] += 1

    return {
        "models": models,
        "tasks": tasks,
        "scores": scores,
        "lift_data": lift_data,
        "best_patterns": best_patterns,
        "pattern_wins": pattern_wins,
    }


def plot_pattern_lift_heatmap(analysis: Dict, out_dir: Path) -> None:
    """Heatmap of pattern lift (multi - single) per model."""
    setup_plotting()
    models = analysis["models"]
    multi_patterns = [p for p in PATTERN_ORDER if p != "single"]

    mat = np.zeros((len(models), len(multi_patterns)))
    for i, model in enumerate(models):
        for j, pat in enumerate(multi_patterns):
            mat[i, j] = analysis["lift_data"][model]["lifts"].get(pat, 0)

    fig, ax = plt.subplots(figsize=(10, max(4, len(models) * 1.2)))
    cmap = plt.cm.RdYlGn
    vmax = max(0.1, np.abs(mat).max())
    im = ax.imshow(mat, cmap=cmap, vmin=-vmax, vmax=vmax, aspect='auto')
    plt.colorbar(im, ax=ax, label="Pattern Lift (multi - single score)")

    ax.set_xticks(range(len(multi_patterns)))
    ax.set_xticklabels([PATTERN_LABELS.get(p, p) for p in multi_patterns])
    ax.set_yticks(range(len(models)))
    ax.set_yticklabels(models)
    ax.set_title("Pattern Lift by Model (green = multi-agent helps, red = hurts)")

    for i in range(len(models)):
        for j in range(len(multi_patterns)):
            color = 'black' if abs(mat[i, j]) < vmax * 0.6 else 'white'
            ax.text(j, i, f"{mat[i, j]:+.3f}", ha='center', va='center',
                    fontsize=9, color=color)

    fig.tight_layout()
    fig.savefig(out_dir / "model_sensitivity_lift_heatmap.png")
    plt.close(fig)


def plot_best_pattern_stability(analysis: Dict, out_dir: Path) -> None:
    """Heatmap: best pattern per model x task."""
    setup_plotting()
    models = analysis["models"]
    tasks = analysis["tasks"]

    pattern_to_num = {p: i for i, p in enumerate(PATTERN_ORDER)}
    mat = np.zeros((len(models), len(tasks)))
    annotations = []
    for i, model in enumerate(models):
        row = []
        for j, task in enumerate(tasks):
            pat, score = analysis["best_patterns"][model][task]
            mat[i, j] = pattern_to_num.get(pat, -1)
            row.append(f"{PATTERN_LABELS.get(pat, pat)[:4]}\n{score:.2f}")
        annotations.append(row)

    fig, ax = plt.subplots(figsize=(max(10, len(tasks) * 2.5), max(4, len(models) * 1.2)))

    colors_list = [PATTERN_COLORS.get(p, '#888888') for p in PATTERN_ORDER]
    from matplotlib.colors import ListedColormap
    cmap = ListedColormap(colors_list)
    im = ax.imshow(mat, cmap=cmap, vmin=0, vmax=len(PATTERN_ORDER) - 1, aspect='auto')

    ax.set_xticks(range(len(tasks)))
    ax.set_xticklabels([TASK_METADATA.get(t, {}).get("display_name", t) for t in tasks],
                       rotation=20, ha='right')
    ax.set_yticks(range(len(models)))
    ax.set_yticklabels(models)
    ax.set_title("Best Pattern per Model x Task (color = pattern, label = score)")

    for i in range(len(models)):
        for j in range(len(tasks)):
            ax.text(j, i, annotations[i][j], ha='center', va='center',
                    fontsize=7, color='white', fontweight='bold')

    import matplotlib.patches as mpatches
    handles = [mpatches.Patch(color=PATTERN_COLORS.get(p, '#888888'),
                              label=PATTERN_LABELS.get(p, p))
               for p in PATTERN_ORDER]
    ax.legend(handles=handles, loc='upper left', bbox_to_anchor=(1.01, 1),
              fontsize=8, framealpha=0.9)

    fig.tight_layout()
    fig.savefig(out_dir / "model_sensitivity_best_pattern.png")
    plt.close(fig)


def plot_model_score_by_pattern(analysis: Dict, out_dir: Path) -> None:
    """Grouped bar chart: mean score per pattern, faceted by model."""
    setup_plotting()
    models = analysis["models"]
    scores = analysis["scores"]

    fig, axes = plt.subplots(1, len(models), figsize=(5 * len(models), 5), sharey=True)
    if len(models) == 1:
        axes = [axes]

    for ax, model in zip(axes, models):
        patterns = [p for p in PATTERN_ORDER if scores[model].get(p)]
        means, colors = [], []
        data_for_box = []
        for p in patterns:
            all_vals = []
            for task_vals in scores[model][p].values():
                all_vals.extend(task_vals)
            data_for_box.append(all_vals if all_vals else [0])
            colors.append(PATTERN_COLORS.get(p, '#888888'))

        bp = ax.boxplot(data_for_box, patch_artist=True, widths=0.5,
                        medianprops=dict(color='black', linewidth=2))
        for patch, color in zip(bp['boxes'], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)

        ax.set_xticks(range(1, len(patterns) + 1))
        ax.set_xticklabels([PATTERN_LABELS.get(p, p)[:5] for p in patterns],
                           fontsize=8, rotation=30, ha='right')
        ax.set_title(model, fontsize=10)

    axes[0].set_ylabel("Final Score")
    fig.suptitle("Score Distribution by Pattern per Model", fontweight='bold', y=1.02)
    fig.tight_layout()
    fig.savefig(out_dir / "model_sensitivity_scores.png")
    plt.close(fig)


def save_csv(analysis: Dict, out_dir: Path) -> None:
    rows = []
    for model in analysis["models"]:
        single_mean = analysis["lift_data"][model]["single_mean"]
        for pattern in PATTERN_ORDER:
            if pattern == "single":
                rows.append({
                    "model": model, "pattern": pattern,
                    "mean_score": single_mean, "pattern_lift": 0.0,
                })
            else:
                lift = analysis["lift_data"][model]["lifts"].get(pattern, 0)
                rows.append({
                    "model": model, "pattern": pattern,
                    "mean_score": single_mean + lift, "pattern_lift": lift,
                })

    fields = ["model", "pattern", "mean_score", "pattern_lift"]
    with open(out_dir / "model_sensitivity.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def run_analysis(session_dir: Path | None = None) -> Dict:
    """Run per-model pattern sensitivity analysis."""
    runs = load_and_enrich(session_dir)
    out_dir = get_output_dir(session_dir)

    print(f"  Model Sensitivity: analyzing {len(runs)} runs...")
    analysis = analyze_runs(runs)

    plot_pattern_lift_heatmap(analysis, out_dir)
    plot_best_pattern_stability(analysis, out_dir)
    plot_model_score_by_pattern(analysis, out_dir)
    save_csv(analysis, out_dir)

    for model in analysis["models"]:
        single_m = analysis["lift_data"][model]["single_mean"]
        lifts = analysis["lift_data"][model]["lifts"]
        best_lift_pat = max(lifts, key=lifts.get) if lifts else "none"
        best_lift_val = lifts.get(best_lift_pat, 0)
        print(f"    {model:>18}: single={single_m:.3f}  "
              f"best_lift={best_lift_pat}({best_lift_val:+.3f})")

    return analysis


if __name__ == "__main__":
    run_analysis()
