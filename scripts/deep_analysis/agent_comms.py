#!/usr/bin/env python3
"""
Module 4: Inter-Agent Communication Quality

Analyzes agent_conversations from multi-agent runs to measure communication
efficiency, plan redundancy, role activity distribution, and coordination overhead.

Pattern-specific analysis:
- Sequential: plan quality, execution_summary, plan-to-execution ratio
- Debate: argument rounds, convergence, proponent/opponent balance
- Group Chat: role activity distribution, executor stall rate, plan redundancy
- Concurrent: (no agent_conversations available; skip)
"""

import csv
import re
from collections import Counter, defaultdict
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


def _edit_distance_ratio(s1: str, s2: str) -> float:
    """Normalized edit distance between two strings (0=identical, 1=completely different).

    Uses a simplified ratio: 1 - (common_chars / max_len). Not true Levenshtein
    but fast enough for plan redundancy detection.
    """
    if not s1 and not s2:
        return 0.0
    if not s1 or not s2:
        return 1.0
    # Use set-based Jaccard similarity on word level for speed
    w1 = set(s1.lower().split())
    w2 = set(s2.lower().split())
    if not w1 and not w2:
        return 0.0
    intersection = len(w1 & w2)
    union = len(w1 | w2)
    return 1.0 - (intersection / union) if union > 0 else 0.0


def analyze_sequential(convos: List[Dict]) -> Dict[str, Any]:
    """Analyze sequential pattern conversations (planner -> executor -> verifier)."""
    plans = [c for c in convos if c.get("content_type") == "plan"]
    summaries = [c for c in convos if c.get("content_type") == "execution_summary"]

    plan_lengths = []
    for p in plans:
        content = p.get("content", {})
        if isinstance(content, dict):
            plan_steps = content.get("plan", [])
            plan_lengths.append(len(plan_steps) if isinstance(plan_steps, list) else 1)

    exec_turns = 0
    exec_actions = 0
    for s in summaries:
        content = s.get("content", {})
        if isinstance(content, dict):
            exec_turns += content.get("turns", 0)
            exec_actions += content.get("actions_count", 0)

    return {
        "n_plans": len(plans),
        "avg_plan_steps": np.mean(plan_lengths) if plan_lengths else 0,
        "n_summaries": len(summaries),
        "executor_turns": exec_turns,
        "executor_actions": exec_actions,
        "plan_to_exec_ratio": len(plans) / max(1, exec_turns),
    }


def analyze_debate(convos: List[Dict]) -> Dict[str, Any]:
    """Analyze debate pattern conversations (proponent vs opponent rounds)."""
    proponent_msgs = [c for c in convos if c.get("from_agent") == "proponent"]
    opponent_msgs = [c for c in convos if c.get("from_agent") == "opponent"]
    judgments = [c for c in convos if c.get("content_type") == "judgment"
                 or c.get("from_agent") == "judge"]

    n_rounds = max(
        max((c.get("round", 0) for c in convos if "round" in c), default=0),
        len(proponent_msgs),
    )

    # Argument lengths (word count) as proxy for depth
    pro_lengths = []
    opp_lengths = []
    for c in proponent_msgs:
        content = c.get("content", {})
        arg = content.get("argument", "") if isinstance(content, dict) else str(content)
        pro_lengths.append(len(str(arg).split()))
    for c in opponent_msgs:
        content = c.get("content", {})
        arg = content.get("argument", "") if isinstance(content, dict) else str(content)
        opp_lengths.append(len(str(arg).split()))

    return {
        "n_rounds": n_rounds,
        "proponent_messages": len(proponent_msgs),
        "opponent_messages": len(opponent_msgs),
        "n_judgments": len(judgments),
        "avg_proponent_length": np.mean(pro_lengths) if pro_lengths else 0,
        "avg_opponent_length": np.mean(opp_lengths) if opp_lengths else 0,
        "balance_ratio": min(len(proponent_msgs), len(opponent_msgs)) /
                         max(1, max(len(proponent_msgs), len(opponent_msgs))),
    }


def analyze_group_chat(convos: List[Dict]) -> Dict[str, Any]:
    """Analyze group chat conversations (Analyzer, Planner, Executor, Reviewer)."""
    role_counts = Counter(c.get("from_agent", "unknown") for c in convos)
    total = len(convos)

    executor_msgs = [c for c in convos if c.get("from_agent", "").lower() == "executor"]
    planner_msgs = [c for c in convos if c.get("from_agent", "").lower() == "planner"]

    # Executor stall: messages where executor takes no tool action
    stalls = 0
    for c in executor_msgs:
        content = c.get("content", {})
        if isinstance(content, dict):
            action = content.get("action", "none")
            if action in ("none", "", None):
                stalls += 1
    executor_stall_rate = stalls / max(1, len(executor_msgs))

    # Plan redundancy: edit distance between consecutive planner messages
    plan_texts = []
    for c in planner_msgs:
        content = c.get("content", {})
        if isinstance(content, dict):
            thought = content.get("thought", "")
            plan_texts.append(str(thought))
        else:
            plan_texts.append(str(content))

    plan_drifts = []
    for i in range(1, len(plan_texts)):
        dist = _edit_distance_ratio(plan_texts[i - 1], plan_texts[i])
        plan_drifts.append(dist)
    avg_plan_drift = np.mean(plan_drifts) if plan_drifts else 0
    plan_redundancy = 1.0 - avg_plan_drift  # high redundancy = low drift

    return {
        "total_messages": total,
        "role_distribution": dict(role_counts),
        "executor_messages": len(executor_msgs),
        "planner_messages": len(planner_msgs),
        "executor_stall_rate": executor_stall_rate,
        "plan_redundancy": plan_redundancy,
        "avg_plan_drift": avg_plan_drift,
    }


def analyze_run(run: Dict) -> Dict[str, Any]:
    """Analyze inter-agent communication for a single run."""
    convos = run.get("metrics", {}).get("agent_conversations") or []
    pattern = run["_pattern"]

    base = {
        "run_id": run.get("run_id", ""),
        "pattern": pattern,
        "model": run["_model"],
        "task_id": run.get("task_id", ""),
        "n_conversations": len(convos),
        "final_score": run.get("scoring", {}).get("final_score", 0),
    }

    if not convos or pattern == "single":
        base["analysis_type"] = "none"
        return base

    if pattern == "sequential":
        base["analysis_type"] = "sequential"
        base.update(analyze_sequential(convos))
    elif pattern == "debate":
        base["analysis_type"] = "debate"
        base.update(analyze_debate(convos))
    elif pattern == "group_chat":
        base["analysis_type"] = "group_chat"
        base.update(analyze_group_chat(convos))
    else:
        base["analysis_type"] = "other"

    return base


def plot_role_activity(all_results: List[Dict], out_dir: Path) -> None:
    """Bar chart of message counts per role for group_chat pattern."""
    setup_plotting()

    gc_results = [r for r in all_results
                  if r["analysis_type"] == "group_chat" and r.get("role_distribution")]
    if not gc_results:
        return

    # Aggregate role counts
    role_totals = Counter()
    for r in gc_results:
        for role, count in r.get("role_distribution", {}).items():
            role_totals[role] += count

    # Normalize to per-run average
    roles = sorted(role_totals.keys())
    avgs = [role_totals[r] / len(gc_results) for r in roles]

    fig, ax = plt.subplots(figsize=(8, 5))
    colors = ['#CC78BC', '#0173B2', '#DE8F05', '#029E73', '#CA9161']
    bars = ax.bar(range(len(roles)), avgs,
                  color=colors[:len(roles)], alpha=0.85)
    ax.set_xticks(range(len(roles)))
    ax.set_xticklabels(roles)
    ax.set_ylabel("Average Messages per Run")
    ax.set_title("Group Chat: Role Activity Distribution")
    for bar, m in zip(bars, avgs):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.2,
                f"{m:.1f}", ha='center', va='bottom', fontsize=9)
    fig.tight_layout()
    fig.savefig(out_dir / "agent_comms_role_activity.png")
    plt.close(fig)


def plot_pattern_comparison(all_results: List[Dict], out_dir: Path) -> None:
    """Comparison of key communication metrics across multi-agent patterns."""
    setup_plotting()

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))

    multi_patterns = ['sequential', 'debate', 'group_chat']
    colors = [PATTERN_COLORS.get(p, '#888888') for p in multi_patterns]

    # Left: messages per run
    ax = axes[0]
    means = []
    for p in multi_patterns:
        vals = [r["n_conversations"] for r in all_results
                if r["pattern"] == p and r["n_conversations"] > 0]
        means.append(np.mean(vals) if vals else 0)
    bars = ax.bar(range(len(multi_patterns)), means, color=colors, alpha=0.85)
    ax.set_xticks(range(len(multi_patterns)))
    ax.set_xticklabels([PATTERN_LABELS[p] for p in multi_patterns])
    ax.set_ylabel("Messages per Run")
    ax.set_title("Inter-Agent Messages")
    for bar, m in zip(bars, means):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.2,
                f"{m:.1f}", ha='center', va='bottom', fontsize=9)

    # Middle: group_chat specific - executor stall rate vs plan redundancy
    ax = axes[1]
    gc = [r for r in all_results if r["analysis_type"] == "group_chat"]
    if gc:
        stall_rates = [r.get("executor_stall_rate", 0) * 100 for r in gc]
        redundancy = [r.get("plan_redundancy", 0) * 100 for r in gc]
        ax.scatter(stall_rates, redundancy,
                   color=PATTERN_COLORS['group_chat'], alpha=0.6, s=40)
        ax.set_xlabel("Executor Stall Rate (%)")
        ax.set_ylabel("Plan Redundancy (%)")
        ax.set_title("Group Chat: Stall vs Redundancy")

    # Right: debate balance and rounds
    ax = axes[2]
    db = [r for r in all_results if r["analysis_type"] == "debate"]
    if db:
        rounds = [r.get("n_rounds", 0) for r in db]
        scores = [r.get("final_score", 0) for r in db]
        ax.scatter(rounds, scores,
                   color=PATTERN_COLORS['debate'], alpha=0.6, s=40)
        ax.set_xlabel("Debate Rounds")
        ax.set_ylabel("Final Score")
        ax.set_title("Debate: Rounds vs Performance")

    fig.tight_layout()
    fig.savefig(out_dir / "agent_comms_comparison.png")
    plt.close(fig)


def save_csv(all_results: List[Dict], out_dir: Path) -> None:
    fields = [
        "run_id", "pattern", "model", "task_id", "n_conversations",
        "analysis_type", "final_score",
    ]
    with open(out_dir / "agent_comms.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        for r in all_results:
            writer.writerow(r)


def run_analysis(session_dir: Path | None = None) -> List[Dict]:
    """Run the full inter-agent communication analysis."""
    runs = load_and_enrich(session_dir)
    out_dir = get_output_dir(session_dir)

    # Only analyze multi-agent runs
    multi_runs = [r for r in runs if r["_pattern"] != "single"]
    print(f"  Agent Comms: analyzing {len(multi_runs)} multi-agent runs...")

    all_results = [analyze_run(r) for r in multi_runs]

    plot_role_activity(all_results, out_dir)
    plot_pattern_comparison(all_results, out_dir)
    save_csv(all_results, out_dir)

    for pattern in ['sequential', 'debate', 'group_chat', 'concurrent']:
        pr = [r for r in all_results if r["pattern"] == pattern]
        if not pr:
            continue
        has_convos = [r for r in pr if r["n_conversations"] > 0]
        avg_msgs = np.mean([r["n_conversations"] for r in has_convos]) if has_convos else 0
        print(f"    {PATTERN_LABELS.get(pattern, pattern):>12}: "
              f"{len(has_convos)}/{len(pr)} runs with conversations, "
              f"avg={avg_msgs:.1f} messages")

        if pattern == "group_chat" and has_convos:
            stall = np.mean([r.get("executor_stall_rate", 0) for r in has_convos])
            redun = np.mean([r.get("plan_redundancy", 0) for r in has_convos])
            print(f"               executor_stall={stall:.2f} plan_redundancy={redun:.2f}")

    return all_results


if __name__ == "__main__":
    run_analysis()
