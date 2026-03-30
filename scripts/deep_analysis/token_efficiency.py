#!/usr/bin/env python3
"""
Module 6: Token Efficiency Dynamics

Analyzes how token consumption relates to actual progress. Multi-agent patterns
consume 3-5x more tokens -- this module quantifies where those tokens go.

Metrics per run:
- tokens_per_property: total_tokens / satisfied_properties
- tokens_per_command: total_tokens / total_commands
- marginal_return: does each additional 10K tokens improve score?
- context_utilization: prompt_tokens / estimated_context_window
- pattern_token_multiplier: pattern tokens / single-agent baseline tokens
"""

import csv
from pathlib import Path
from typing import Any, Dict, List

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats as scipy_stats

from .run_loader import (
    load_and_enrich, get_output_dir, setup_plotting,
    PATTERN_COLORS, PATTERN_ORDER, PATTERN_LABELS, DEFAULT_SESSION,
    TASK_METADATA,
)

CONTEXT_WINDOW_ESTIMATE = 128_000  # tokens, conservative estimate


def analyze_run(run: Dict) -> Dict[str, Any]:
    """Compute token efficiency metrics for a single run."""
    metrics = run.get("metrics", {}) or {}
    tu = metrics.get("token_usage", {}) or {}
    prompt_tokens = tu.get("prompt_tokens", 0) or 0
    completion_tokens = tu.get("completion_tokens", 0) or 0
    total_tokens = tu.get("total_tokens", 0) or (prompt_tokens + completion_tokens)

    scoring = run.get("scoring", {}) or {}
    final_score = scoring.get("final_score", 0) or 0

    props = run.get("property_results", []) or []
    satisfied = sum(1 for p in props if p.get("satisfied"))
    total_props = len(props)

    total_commands = (metrics.get("total_commands", 0) or 0)
    turns = metrics.get("turns_to_complete", 0) or 0

    tokens_per_property = total_tokens / max(1, satisfied) if satisfied > 0 else 0
    tokens_per_command = total_tokens / max(1, total_commands) if total_commands > 0 else 0
    score_per_1k = (final_score / (total_tokens / 1000)) if total_tokens > 0 else 0
    context_util = prompt_tokens / CONTEXT_WINDOW_ESTIMATE if prompt_tokens > 0 else 0

    return {
        "run_id": run.get("run_id", ""),
        "pattern": run["_pattern"],
        "model": run["_model"],
        "task_id": run.get("task_id", ""),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "total_commands": total_commands,
        "turns": turns,
        "satisfied_properties": satisfied,
        "total_properties": total_props,
        "final_score": final_score,
        "tokens_per_property": tokens_per_property,
        "tokens_per_command": tokens_per_command,
        "score_per_1k_tokens": score_per_1k,
        "context_utilization": context_util,
    }


def plot_tokens_vs_score(all_results: List[Dict], out_dir: Path) -> None:
    """Scatter plot of total tokens vs final score, colored by pattern."""
    setup_plotting()
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Left: tokens vs score scatter
    ax = axes[0]
    for pattern in PATTERN_ORDER:
        runs = [r for r in all_results
                if r["pattern"] == pattern and r["total_tokens"] > 0]
        if not runs:
            continue
        xs = [r["total_tokens"] / 1000 for r in runs]
        ys = [r["final_score"] for r in runs]
        ax.scatter(xs, ys, label=PATTERN_LABELS.get(pattern, pattern),
                   color=PATTERN_COLORS.get(pattern, '#888888'),
                   alpha=0.55, s=35, edgecolors='white', linewidths=0.5,
                   marker='o')

        if len(xs) > 2:
            slope, intercept, r_val, *_ = scipy_stats.linregress(xs, ys)
            xr = np.linspace(min(xs), max(xs), 50)
            ax.plot(xr, slope * xr + intercept,
                    color=PATTERN_COLORS.get(pattern, '#888888'),
                    linewidth=1.2, linestyle='--', alpha=0.5)

    ax.set_xlabel("Total Tokens (K)")
    ax.set_ylabel("Final Score")
    ax.set_title("Token Cost vs Performance by Pattern")
    ax.legend(fontsize=8)

    # Right: score per 1K tokens box plot
    ax = axes[1]
    patterns = [p for p in PATTERN_ORDER
                if any(r["pattern"] == p for r in all_results)]
    data = [[r["score_per_1k_tokens"] for r in all_results
             if r["pattern"] == p and r["total_tokens"] > 0]
            for p in patterns]
    colors = [PATTERN_COLORS.get(p, '#888888') for p in patterns]

    bp = ax.boxplot(data, patch_artist=True, widths=0.5,
                    medianprops=dict(color='black', linewidth=2))
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    ax.set_xticks(range(1, len(patterns) + 1))
    ax.set_xticklabels([PATTERN_LABELS.get(p, p) for p in patterns])
    ax.set_ylabel("Score per 1K Tokens")
    ax.set_title("Token Efficiency (Score / 1K Tokens)")

    fig.tight_layout()
    fig.savefig(out_dir / "token_efficiency_scatter.png")
    plt.close(fig)


def plot_tokens_per_property(all_results: List[Dict], out_dir: Path) -> None:
    """Box plot of tokens per satisfied property by pattern."""
    setup_plotting()
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    patterns = [p for p in PATTERN_ORDER
                if any(r["pattern"] == p for r in all_results)]
    colors = [PATTERN_COLORS.get(p, '#888888') for p in patterns]

    # Left: tokens per property
    ax = axes[0]
    data = [[r["tokens_per_property"] / 1000 for r in all_results
             if r["pattern"] == p and r["satisfied_properties"] > 0] or [0]
            for p in patterns]
    bp = ax.boxplot(data, patch_artist=True, widths=0.5,
                    medianprops=dict(color='black', linewidth=2))
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    ax.set_xticks(range(1, len(patterns) + 1))
    ax.set_xticklabels([PATTERN_LABELS.get(p, p) for p in patterns])
    ax.set_ylabel("K Tokens per Satisfied Property")
    ax.set_title("Cost per Property Satisfaction")

    # Right: context utilization
    ax = axes[1]
    data = [[r["context_utilization"] * 100 for r in all_results
             if r["pattern"] == p and r["prompt_tokens"] > 0] or [0]
            for p in patterns]
    bp = ax.boxplot(data, patch_artist=True, widths=0.5,
                    medianprops=dict(color='black', linewidth=2))
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    ax.set_xticks(range(1, len(patterns) + 1))
    ax.set_xticklabels([PATTERN_LABELS.get(p, p) for p in patterns])
    ax.set_ylabel("Context Window Usage (%)")
    ax.set_title(f"Context Utilization (of {CONTEXT_WINDOW_ESTIMATE // 1000}K window)")

    fig.tight_layout()
    fig.savefig(out_dir / "token_efficiency_per_property.png")
    plt.close(fig)


def plot_marginal_return(all_results: List[Dict], out_dir: Path) -> None:
    """Marginal return curves: binned token usage vs average score by pattern."""
    setup_plotting()
    fig, ax = plt.subplots(figsize=(10, 5))

    for pattern in PATTERN_ORDER:
        runs = sorted(
            [r for r in all_results
             if r["pattern"] == pattern and r["total_tokens"] > 0],
            key=lambda r: r["total_tokens"]
        )
        if len(runs) < 5:
            continue

        tokens = np.array([r["total_tokens"] / 1000 for r in runs])
        scores = np.array([r["final_score"] for r in runs])

        # Bin into ~8 buckets
        n_bins = min(8, len(runs) // 3)
        if n_bins < 3:
            continue
        bin_edges = np.linspace(tokens.min(), tokens.max(), n_bins + 1)
        bin_centers = []
        bin_means = []
        for i in range(n_bins):
            mask = (tokens >= bin_edges[i]) & (tokens < bin_edges[i + 1])
            if i == n_bins - 1:
                mask = (tokens >= bin_edges[i]) & (tokens <= bin_edges[i + 1])
            if mask.sum() > 0:
                bin_centers.append((bin_edges[i] + bin_edges[i + 1]) / 2)
                bin_means.append(scores[mask].mean())

        if len(bin_centers) > 1:
            color = PATTERN_COLORS.get(pattern, '#888888')
            ax.plot(bin_centers, bin_means, 'o-',
                    label=PATTERN_LABELS.get(pattern, pattern),
                    color=color, linewidth=2, markersize=6, alpha=0.8)

    ax.set_xlabel("Total Tokens (K)")
    ax.set_ylabel("Average Final Score")
    ax.set_title("Marginal Return Curve: Score vs Token Investment")
    ax.legend(loc='lower right', fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "token_efficiency_marginal_return.png")
    plt.close(fig)


def plot_token_multiplier(all_results: List[Dict], out_dir: Path) -> None:
    """Show how much more tokens each pattern uses vs single-agent baseline."""
    setup_plotting()

    # Compute per-task single-agent baseline
    single_baseline = {}
    for task in set(r["task_id"] for r in all_results):
        vals = [r["total_tokens"] for r in all_results
                if r["pattern"] == "single" and r["task_id"] == task
                and r["total_tokens"] > 0]
        if vals:
            single_baseline[task] = np.median(vals)

    if not single_baseline:
        return

    fig, ax = plt.subplots(figsize=(10, 5))
    patterns = [p for p in PATTERN_ORDER if p != "single"
                and any(r["pattern"] == p for r in all_results)]

    tasks = sorted(single_baseline.keys())
    n_patterns = len(patterns)
    n_tasks = len(tasks)
    x = np.arange(n_tasks)
    width = 0.7 / n_patterns

    for i, pattern in enumerate(patterns):
        multipliers = []
        for task in tasks:
            vals = [r["total_tokens"] for r in all_results
                    if r["pattern"] == pattern and r["task_id"] == task
                    and r["total_tokens"] > 0]
            if vals and task in single_baseline and single_baseline[task] > 0:
                multipliers.append(np.median(vals) / single_baseline[task])
            else:
                multipliers.append(0)

        offset = (i - n_patterns / 2 + 0.5) * width
        color = PATTERN_COLORS.get(pattern, '#888888')
        ax.bar(x + offset, multipliers, width * 0.9,
               label=PATTERN_LABELS.get(pattern, pattern),
               color=color, alpha=0.85)

    ax.set_xticks(x)
    ax.set_xticklabels([TASK_METADATA.get(t, {}).get("display_name", t)
                        for t in tasks], rotation=15, ha='right')
    ax.set_ylabel("Token Multiplier (vs Single Agent)")
    ax.set_title("Token Cost Multiplier by Pattern and Task")
    ax.axhline(1.0, linestyle='--', color='gray', alpha=0.5, linewidth=1)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "token_efficiency_multiplier.png")
    plt.close(fig)


def save_csv(all_results: List[Dict], out_dir: Path) -> None:
    fields = [
        "run_id", "pattern", "model", "task_id",
        "prompt_tokens", "completion_tokens", "total_tokens",
        "total_commands", "turns", "satisfied_properties", "total_properties",
        "final_score", "tokens_per_property", "tokens_per_command",
        "score_per_1k_tokens", "context_utilization",
    ]
    with open(out_dir / "token_efficiency.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in all_results:
            writer.writerow({k: r[k] for k in fields})


def run_analysis(session_dir: Path | None = None) -> List[Dict]:
    """Run the full token efficiency analysis."""
    runs = load_and_enrich(session_dir)
    out_dir = get_output_dir(session_dir)

    print(f"  Token Efficiency: analyzing {len(runs)} runs...")
    all_results = [analyze_run(r) for r in runs]

    plot_tokens_vs_score(all_results, out_dir)
    plot_tokens_per_property(all_results, out_dir)
    plot_marginal_return(all_results, out_dir)
    plot_token_multiplier(all_results, out_dir)
    save_csv(all_results, out_dir)

    for pattern in PATTERN_ORDER:
        pr = [r for r in all_results if r["pattern"] == pattern and r["total_tokens"] > 0]
        if not pr:
            continue
        avg_tok = np.mean([r["total_tokens"] for r in pr]) / 1000
        avg_eff = np.mean([r["score_per_1k_tokens"] for r in pr])
        avg_ctx = np.mean([r["context_utilization"] for r in pr]) * 100
        print(f"    {PATTERN_LABELS.get(pattern, pattern):>12}: "
              f"avg_tokens={avg_tok:.0f}K eff={avg_eff:.4f}/1K ctx={avg_ctx:.1f}%")

    return all_results


if __name__ == "__main__":
    run_analysis()
