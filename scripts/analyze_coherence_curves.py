#!/usr/bin/env python3
"""
Analyze coherence curves and long-term agent stability in multi-turn benchmark runs.

This script generates metrics and visualizations inspired by Vending-Bench's
"net worth over time" approach, adapted for network configuration tasks.

Key Metrics:
- Network Coherence Curve: Tracks cumulative progress vs destructive actions
- Meltdown Detection: Identifies agent failure patterns
- Exploration Efficiency: Diagnostic vs constructive command ratios
- Turn-by-Turn Analysis: Progress tracking over interaction turns

Usage:
    python scripts/analyze_coherence_curves.py results/comparative_study/<session_name>

Output:
    - coherence_analysis_report.md: Detailed coherence analysis
    - charts/coherence_*.png: Visualization charts
"""

import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

# Publication-quality styling
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams.update({
    'font.size': 10,
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
    'axes.labelsize': 11,
    'axes.titlesize': 12,
    'axes.titleweight': 'bold',
    'axes.linewidth': 1.2,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 9,
    'legend.frameon': True,
    'legend.edgecolor': '0.8',
    'legend.fancybox': False,
    'figure.dpi': 100,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'savefig.facecolor': 'white',
    'lines.linewidth': 2,
    'lines.markersize': 8,
    'grid.alpha': 0.3,
    'grid.linestyle': '--',
    'axes.spines.top': False,
    'axes.spines.right': False,
})

# Professional colorblind-friendly palette
COLORS = {
    'single': '#0173B2',       # Blue
    'sequential': '#DE8F05',   # Orange  
    'debate': '#029E73',       # Green
    'group_chat': '#CC78BC',   # Purple
    'concurrent': '#CA9161',   # Brown
    'constructive': '#029E73', # Green
    'diagnostic': '#0173B2',   # Blue
    'destructive': '#D55E00',  # Red-Orange
    'other': '#999999',        # Gray
}

MARKERS = {
    'single': 'o',
    'sequential': 's',
    'debate': '^',
    'group_chat': 'D',
    'concurrent': 'v',
}

# Task metadata
TASK_METADATA = {
    "ccna_rip_routing_basic": {
        "difficulty": "basic",
        "type": "configuration",
        "protocol": "RIP",
        "total_properties": 4,
        "display_name": "CCNA RIP Routing",
        "sequential_depth": 2,
        "parallelizable_breadth": 4,
    },
    "ccnp_multiarea_ospf_intermediate": {
        "difficulty": "intermediate",
        "type": "configuration",
        "protocol": "OSPF",
        "total_properties": 4,
        "display_name": "CCNP Multi-Area OSPF",
        "sequential_depth": 3,
        "parallelizable_breadth": 3,
    },
    "ccie_bgp_dual_homing_expert": {
        "difficulty": "expert",
        "type": "configuration",
        "protocol": "BGP",
        "total_properties": 5,
        "display_name": "CCIE BGP Dual-Homing",
        "sequential_depth": 5,
        "parallelizable_breadth": 2,
    },
    "troubleshoot_ospf_adjacency_issue": {
        "difficulty": "intermediate",
        "type": "troubleshooting",
        "protocol": "OSPF",
        "total_properties": 4,
        "display_name": "Troubleshoot OSPF Adjacency",
        "sequential_depth": 6,
        "parallelizable_breadth": 1,
    },
    "troubleshoot_bgp_route_filtering": {
        "difficulty": "expert",
        "type": "troubleshooting",
        "protocol": "BGP",
        "total_properties": 4,
        "display_name": "Troubleshoot BGP Route Filtering",
        "sequential_depth": 7,
        "parallelizable_breadth": 1,
    }
}


def load_session_results(session_dir: Path) -> List[Dict[str, Any]]:
    """Load all result files from a session directory."""
    results = []
    runs_dir = session_dir / "runs"
    
    if not runs_dir.exists():
        runs_dir = session_dir
    
    for result_file in runs_dir.glob("**/*.json"):
        if result_file.name == "session_info.json":
            continue
        try:
            with open(result_file) as f:
                result = json.load(f)
                if "run_id" in result or "task_id" in result:
                    results.append(result)
        except Exception as e:
            print(f"Warning: Failed to load {result_file}: {e}")
    
    return results


def extract_agent_config(result: Dict) -> Tuple[str, str]:
    """Extract (mode, structure) from result testee_id."""
    testee_id = result.get("testee_id", "").lower()
    
    mode = "single"
    structure = "sequential"
    
    if "_multi_sequential" in testee_id:
        mode, structure = "multi", "sequential"
    elif "_multi_debate" in testee_id:
        mode, structure = "multi", "debate"
    elif "_multi_group_chat" in testee_id:
        mode, structure = "multi", "group_chat"
    elif "_multi_concurrent" in testee_id:
        mode, structure = "multi", "concurrent"
    elif "_single" in testee_id:
        mode, structure = "single", "sequential"
    
    return mode, structure


def get_pattern_name(result: Dict) -> str:
    """Get pattern name (single, sequential, debate, etc)."""
    mode, structure = extract_agent_config(result)
    return "single" if mode == "single" else structure


def classify_command(cmd: str) -> str:
    """Classify a command as diagnostic, constructive, destructive, or other."""
    cmd_lower = cmd.lower()
    
    # Destructive patterns
    if any(pattern in cmd_lower for pattern in [
        'no router', 'no ip address', 'no network', 'no interface',
        'delete', 'remove', 'shutdown', 'no ospf', 'no bgp', 'no rip'
    ]):
        return 'destructive'
    
    # Diagnostic patterns
    if any(pattern in cmd_lower for pattern in [
        'show ', 'display', 'ping ', 'traceroute', 'get ',
        'ip route get', 'ip addr show', 'ip link show', 'cat '
    ]):
        return 'diagnostic'
    
    # Configuration patterns
    if any(pattern in cmd_lower for pattern in [
        'configure', 'router ospf', 'router bgp', 'router rip',
        'network ', 'ip address', 'ip addr add', 'interface ',
        'vtysh', 'router-id', 'area ', 'write', 'no shutdown'
    ]):
        return 'constructive'
    
    return 'other'


def parse_execution_log(result: Dict) -> List[Dict[str, Any]]:
    """Parse execution log entries into structured data with turn estimation."""
    log = result.get("execution_log", [])
    parsed = []
    
    for idx, entry in enumerate(log):
        if isinstance(entry, str) and ' | ' in entry:
            parts = entry.split(' | ', 1)
            node = parts[0].strip()
            cmd = parts[1].strip() if len(parts) > 1 else ""
        elif isinstance(entry, str):
            node = "unknown"
            cmd = entry
        else:
            continue
            
        parsed.append({
            "index": idx,
            "node": node,
            "command": cmd,
            "type": classify_command(cmd),
            "raw": entry,
        })
    
    return parsed


def compute_turn_metrics(result: Dict) -> Dict[str, Any]:
    """
    Compute per-turn metrics for coherence analysis.
    
    Since we don't have per-turn property evaluations, we estimate coherence
    based on command patterns and tool usage.
    """
    parsed_log = parse_execution_log(result)
    total_turns = result.get("metrics", {}).get("turns_to_complete", len(parsed_log))
    tool_usage = result.get("metrics", {}).get("tool_usage", {})
    
    # Get final property satisfaction
    property_results = result.get("property_results", [])
    properties_satisfied = sum(1 for p in property_results if p.get("satisfied", False))
    total_properties = len(property_results)
    
    # Compute cumulative command metrics
    turn_metrics = []
    cumulative_constructive = 0
    cumulative_diagnostic = 0
    cumulative_destructive = 0
    cumulative_other = 0
    
    # Estimate turns by distributing commands
    commands_per_turn = max(1, len(parsed_log) // max(1, total_turns))
    
    for turn in range(total_turns):
        start_idx = turn * commands_per_turn
        end_idx = min((turn + 1) * commands_per_turn, len(parsed_log))
        turn_commands = parsed_log[start_idx:end_idx]
        
        for cmd in turn_commands:
            if cmd["type"] == "constructive":
                cumulative_constructive += 1
            elif cmd["type"] == "diagnostic":
                cumulative_diagnostic += 1
            elif cmd["type"] == "destructive":
                cumulative_destructive += 1
            else:
                cumulative_other += 1
        
        total_commands_so_far = cumulative_constructive + cumulative_diagnostic + cumulative_destructive + cumulative_other
        destructive_ratio = cumulative_destructive / max(1, total_commands_so_far)
        
        # Estimate progress based on constructive commands
        # Assume properties are satisfied proportionally to constructive work
        estimated_progress = min(1.0, cumulative_constructive / max(1, total_properties * 3))  # ~3 commands per property
        
        # Coherence formula from Paper 1
        # Coherence(t) = (properties_satisfied(t) / total_properties) * (1 - destructive_ratio)
        coherence = estimated_progress * (1 - destructive_ratio)
        
        turn_metrics.append({
            "turn": turn + 1,
            "cumulative_constructive": cumulative_constructive,
            "cumulative_diagnostic": cumulative_diagnostic,
            "cumulative_destructive": cumulative_destructive,
            "cumulative_other": cumulative_other,
            "total_commands": total_commands_so_far,
            "destructive_ratio": destructive_ratio,
            "estimated_progress": estimated_progress,
            "coherence": coherence,
        })
    
    # Adjust final coherence based on actual results
    final_coherence = (properties_satisfied / max(1, total_properties)) * (1 - (cumulative_destructive / max(1, len(parsed_log))))
    
    return {
        "total_turns": total_turns,
        "turn_metrics": turn_metrics,
        "final_coherence": final_coherence,
        "properties_satisfied": properties_satisfied,
        "total_properties": total_properties,
        "total_constructive": cumulative_constructive,
        "total_diagnostic": cumulative_diagnostic,
        "total_destructive": cumulative_destructive,
        "total_commands": len(parsed_log),
    }


def detect_meltdown_patterns(result: Dict) -> Dict[str, Any]:
    """
    Detect meltdown patterns in agent behavior.
    
    Meltdown signals:
    1. Consecutive identical commands (>3)
    2. High destructive ratio (>15%)
    3. Coherence plateau (>10 turns without progress)
    4. Repeated status checks (>5 consecutive)
    """
    tool_usage = result.get("metrics", {}).get("tool_usage", {})
    parsed_log = parse_execution_log(result)
    turn_metrics = compute_turn_metrics(result)["turn_metrics"]
    
    meltdown_signals = {
        "repeated_status_checks": False,
        "high_destructive_ratio": False,
        "coherence_plateau": False,
        "repeated_commands": False,
        "meltdown_detected": False,
        "signals_count": 0,
        "details": [],
    }
    
    # Check for repeated status checks
    status_checks = tool_usage.get("get_session_status", 0)
    exec_commands = tool_usage.get("exec_command", 0)
    if status_checks > 5 and status_checks > exec_commands:
        meltdown_signals["repeated_status_checks"] = True
        meltdown_signals["details"].append(f"Excessive status checks: {status_checks} vs {exec_commands} exec commands")
        meltdown_signals["signals_count"] += 1
    
    # Check destructive ratio
    total_cmds = len(parsed_log)
    destructive_cmds = sum(1 for c in parsed_log if c["type"] == "destructive")
    if total_cmds > 0 and destructive_cmds / total_cmds > 0.15:
        meltdown_signals["high_destructive_ratio"] = True
        meltdown_signals["details"].append(f"High destructive ratio: {destructive_cmds}/{total_cmds} ({100*destructive_cmds/total_cmds:.1f}%)")
        meltdown_signals["signals_count"] += 1
    
    # Check for coherence plateau
    if len(turn_metrics) >= 10:
        # Look for 10-turn windows with no coherence increase
        for i in range(len(turn_metrics) - 9):
            window = turn_metrics[i:i+10]
            if window[-1]["coherence"] <= window[0]["coherence"]:
                meltdown_signals["coherence_plateau"] = True
                meltdown_signals["details"].append(f"Coherence plateau detected at turns {i+1}-{i+10}")
                meltdown_signals["signals_count"] += 1
                break
    
    # Check for repeated commands
    if len(parsed_log) >= 3:
        for i in range(len(parsed_log) - 2):
            if (parsed_log[i]["command"] == parsed_log[i+1]["command"] == parsed_log[i+2]["command"]):
                meltdown_signals["repeated_commands"] = True
                meltdown_signals["details"].append(f"Repeated command at index {i}: {parsed_log[i]['command'][:50]}...")
                meltdown_signals["signals_count"] += 1
                break
    
    # Meltdown if 2+ signals
    meltdown_signals["meltdown_detected"] = meltdown_signals["signals_count"] >= 2
    
    return meltdown_signals


def compute_exploration_metrics(result: Dict) -> Dict[str, Any]:
    """Compute exploration efficiency metrics."""
    parsed_log = parse_execution_log(result)
    
    total = len(parsed_log)
    constructive = sum(1 for c in parsed_log if c["type"] == "constructive")
    diagnostic = sum(1 for c in parsed_log if c["type"] == "diagnostic")
    destructive = sum(1 for c in parsed_log if c["type"] == "destructive")
    other = sum(1 for c in parsed_log if c["type"] == "other")
    
    exploration_rate = diagnostic / max(1, total)
    convergence_cost = diagnostic / max(1, constructive)  # Ratio of diagnostic to constructive
    destructive_ratio = destructive / max(1, total)
    
    return {
        "total_commands": total,
        "constructive": constructive,
        "diagnostic": diagnostic,
        "destructive": destructive,
        "other": other,
        "exploration_rate": exploration_rate,
        "convergence_cost": convergence_cost,
        "destructive_ratio": destructive_ratio,
        "constructive_ratio": constructive / max(1, total),
    }


def group_by_pattern(results: List[Dict]) -> Dict[str, List[Dict]]:
    """Group results by agent pattern."""
    groups = defaultdict(list)
    for result in results:
        pattern = get_pattern_name(result)
        groups[pattern].append(result)
    return dict(groups)


def group_by_task(results: List[Dict]) -> Dict[str, List[Dict]]:
    """Group results by task."""
    groups = defaultdict(list)
    for result in results:
        task_id = result.get("task_id", "unknown")
        groups[task_id].append(result)
    return dict(groups)


# =============================================================================
# Chart Generation Functions
# =============================================================================

def plot_coherence_curves_by_pattern(results: List[Dict], output_dir: Path):
    """
    Plot coherence curves comparing different agent patterns.
    Shows how coherence evolves over turns for each pattern.
    """
    fig, ax = plt.subplots(figsize=(10, 6))
    
    by_pattern = group_by_pattern(results)
    pattern_order = ["single", "sequential", "debate", "group_chat", "concurrent"]
    
    for pattern in pattern_order:
        if pattern not in by_pattern:
            continue
            
        pattern_results = by_pattern[pattern]
        
        # Aggregate coherence curves (normalize to same x-axis)
        all_coherences = []
        max_turns = max(r.get("metrics", {}).get("turns_to_complete", 1) for r in pattern_results)
        
        for result in pattern_results:
            turn_data = compute_turn_metrics(result)
            coherences = [m["coherence"] for m in turn_data["turn_metrics"]]
            
            # Interpolate to common x-axis
            if len(coherences) > 1:
                x_orig = np.linspace(0, 1, len(coherences))
                x_new = np.linspace(0, 1, max_turns)
                coherences_interp = np.interp(x_new, x_orig, coherences)
                all_coherences.append(coherences_interp)
        
        if all_coherences:
            # Plot mean with confidence band
            mean_coherence = np.mean(all_coherences, axis=0)
            std_coherence = np.std(all_coherences, axis=0)
            x = np.arange(1, max_turns + 1)
            
            ax.plot(x, mean_coherence, label=pattern.replace('_', ' ').title(), 
                   color=COLORS.get(pattern, '#333333'), marker=MARKERS.get(pattern, 'o'),
                   markevery=max(1, len(x)//10))
            ax.fill_between(x, mean_coherence - std_coherence, mean_coherence + std_coherence,
                          alpha=0.2, color=COLORS.get(pattern, '#333333'))
    
    ax.set_xlabel("Turn Number")
    ax.set_ylabel("Coherence Score")
    ax.set_title("Network Coherence Curves by Agent Pattern")
    ax.legend(loc='best')
    ax.set_ylim(0, 1.1)
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_dir / "coherence_curves_by_pattern.png", dpi=300, bbox_inches='tight')
    plt.close()


def plot_exploration_vs_success(results: List[Dict], output_dir: Path):
    """
    Scatter plot of exploration rate vs final score.
    Tests the hypothesis that higher exploration correlates with success.
    """
    fig, ax = plt.subplots(figsize=(8, 6))
    
    by_pattern = group_by_pattern(results)
    pattern_order = ["single", "sequential", "debate", "group_chat", "concurrent"]
    
    all_exploration = []
    all_scores = []
    
    for pattern in pattern_order:
        if pattern not in by_pattern:
            continue
            
        pattern_results = by_pattern[pattern]
        explorations = []
        scores = []
        
        for result in pattern_results:
            metrics = compute_exploration_metrics(result)
            score = result.get("scoring", {}).get("final_score", 0)
            explorations.append(metrics["exploration_rate"] * 100)  # As percentage
            scores.append(score)
            all_exploration.append(metrics["exploration_rate"] * 100)
            all_scores.append(score)
        
        ax.scatter(explorations, scores, label=pattern.replace('_', ' ').title(),
                  color=COLORS.get(pattern, '#333333'), marker=MARKERS.get(pattern, 'o'),
                  s=100, alpha=0.7)
    
    # Add regression line
    if len(all_exploration) > 2:
        slope, intercept, r_value, p_value, std_err = stats.linregress(all_exploration, all_scores)
        x_line = np.linspace(0, max(all_exploration) * 1.1, 100)
        y_line = slope * x_line + intercept
        ax.plot(x_line, y_line, 'k--', alpha=0.5, 
               label=f'Trend (r={r_value:.2f}, p={p_value:.3f})')
    
    ax.set_xlabel("Exploration Rate (%)")
    ax.set_ylabel("Final Score")
    ax.set_title("Exploration Rate vs Task Success")
    ax.legend(loc='best')
    ax.set_xlim(0, None)
    ax.set_ylim(0, 1.1)
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_dir / "exploration_vs_success.png", dpi=300, bbox_inches='tight')
    plt.close()


def plot_destructive_ratio_by_pattern(results: List[Dict], output_dir: Path):
    """
    Bar chart showing destructive command ratios by pattern.
    Highlights the danger of certain multi-agent configurations.
    """
    fig, ax = plt.subplots(figsize=(10, 6))
    
    by_pattern = group_by_pattern(results)
    pattern_order = ["single", "sequential", "debate", "group_chat", "concurrent"]
    
    patterns = []
    means = []
    stds = []
    success_rates = []
    
    for pattern in pattern_order:
        if pattern not in by_pattern:
            continue
            
        pattern_results = by_pattern[pattern]
        ratios = [compute_exploration_metrics(r)["destructive_ratio"] * 100 for r in pattern_results]
        successes = [1 if r.get("success", False) else 0 for r in pattern_results]
        
        patterns.append(pattern.replace('_', ' ').title())
        means.append(np.mean(ratios))
        stds.append(np.std(ratios))
        success_rates.append(np.mean(successes) * 100)
    
    x = np.arange(len(patterns))
    width = 0.35
    
    bars1 = ax.bar(x - width/2, means, width, label='Destructive %', 
                   color=[COLORS.get(p.lower().replace(' ', '_'), '#333') for p in patterns],
                   yerr=stds, capsize=5)
    bars2 = ax.bar(x + width/2, success_rates, width, label='Success Rate %',
                   color='#2CA02C', alpha=0.7)
    
    ax.set_xlabel("Agent Pattern")
    ax.set_ylabel("Percentage")
    ax.set_title("Destructive Command Ratio vs Success Rate by Pattern")
    ax.set_xticks(x)
    ax.set_xticklabels(patterns, rotation=15, ha='right')
    ax.legend(loc='upper right')
    ax.grid(True, alpha=0.3, axis='y')
    
    # Add value labels
    for bar in bars1:
        height = bar.get_height()
        ax.annotate(f'{height:.1f}%', xy=(bar.get_x() + bar.get_width() / 2, height),
                   xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=8)
    
    plt.tight_layout()
    plt.savefig(output_dir / "destructive_ratio_by_pattern.png", dpi=300, bbox_inches='tight')
    plt.close()


def plot_meltdown_heatmap(results: List[Dict], output_dir: Path):
    """
    Heatmap showing meltdown signal frequency by pattern and task.
    """
    by_pattern = group_by_pattern(results)
    by_task = group_by_task(results)
    
    pattern_order = ["single", "sequential", "debate", "group_chat", "concurrent"]
    task_order = list(TASK_METADATA.keys())
    
    # Build matrix of meltdown signal counts
    matrix = np.zeros((len(pattern_order), len(task_order)))
    
    for i, pattern in enumerate(pattern_order):
        for j, task in enumerate(task_order):
            # Find runs matching both pattern and task
            matching = [r for r in results 
                       if get_pattern_name(r) == pattern and r.get("task_id") == task]
            if matching:
                signals = [detect_meltdown_patterns(r)["signals_count"] for r in matching]
                matrix[i, j] = np.mean(signals)
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    im = ax.imshow(matrix, cmap='YlOrRd', aspect='auto')
    
    # Labels
    ax.set_xticks(np.arange(len(task_order)))
    ax.set_yticks(np.arange(len(pattern_order)))
    ax.set_xticklabels([TASK_METADATA.get(t, {}).get("display_name", t) for t in task_order],
                       rotation=45, ha='right')
    ax.set_yticklabels([p.replace('_', ' ').title() for p in pattern_order])
    
    # Add text annotations
    for i in range(len(pattern_order)):
        for j in range(len(task_order)):
            val = matrix[i, j]
            text = ax.text(j, i, f'{val:.1f}', ha="center", va="center",
                          color="white" if val > 1.5 else "black", fontsize=9)
    
    ax.set_title("Meltdown Signal Count by Pattern × Task")
    
    # Colorbar
    cbar = ax.figure.colorbar(im, ax=ax)
    cbar.ax.set_ylabel("Avg Meltdown Signals", rotation=-90, va="bottom")
    
    plt.tight_layout()
    plt.savefig(output_dir / "meltdown_heatmap.png", dpi=300, bbox_inches='tight')
    plt.close()


def plot_command_composition_stacked(results: List[Dict], output_dir: Path):
    """
    Stacked bar chart showing command type composition by pattern.
    """
    fig, ax = plt.subplots(figsize=(10, 6))
    
    by_pattern = group_by_pattern(results)
    pattern_order = ["single", "sequential", "debate", "group_chat", "concurrent"]
    
    patterns = []
    constructive = []
    diagnostic = []
    destructive = []
    other = []
    
    for pattern in pattern_order:
        if pattern not in by_pattern:
            continue
            
        pattern_results = by_pattern[pattern]
        all_metrics = [compute_exploration_metrics(r) for r in pattern_results]
        
        total = sum(m["total_commands"] for m in all_metrics)
        if total == 0:
            continue
            
        patterns.append(pattern.replace('_', ' ').title())
        constructive.append(sum(m["constructive"] for m in all_metrics) / total * 100)
        diagnostic.append(sum(m["diagnostic"] for m in all_metrics) / total * 100)
        destructive.append(sum(m["destructive"] for m in all_metrics) / total * 100)
        other.append(sum(m["other"] for m in all_metrics) / total * 100)
    
    x = np.arange(len(patterns))
    width = 0.6
    
    ax.bar(x, constructive, width, label='Constructive', color=COLORS['constructive'])
    ax.bar(x, diagnostic, width, bottom=constructive, label='Diagnostic', color=COLORS['diagnostic'])
    ax.bar(x, destructive, width, 
           bottom=[c+d for c,d in zip(constructive, diagnostic)], 
           label='Destructive', color=COLORS['destructive'])
    ax.bar(x, other, width,
           bottom=[c+d+de for c,d,de in zip(constructive, diagnostic, destructive)],
           label='Other', color=COLORS['other'])
    
    ax.set_xlabel("Agent Pattern")
    ax.set_ylabel("Command Composition (%)")
    ax.set_title("Command Type Distribution by Agent Pattern")
    ax.set_xticks(x)
    ax.set_xticklabels(patterns, rotation=15, ha='right')
    ax.legend(loc='upper right')
    ax.set_ylim(0, 105)
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    plt.savefig(output_dir / "command_composition_stacked.png", dpi=300, bbox_inches='tight')
    plt.close()


def plot_convergence_cost_vs_success(results: List[Dict], output_dir: Path):
    """
    Plot convergence cost (diagnostic/constructive ratio) vs success.
    Tests the hypothesis that cautious agents perform better.
    """
    fig, ax = plt.subplots(figsize=(8, 6))
    
    by_pattern = group_by_pattern(results)
    pattern_order = ["single", "sequential", "debate", "group_chat", "concurrent"]
    
    all_costs = []
    all_scores = []
    
    for pattern in pattern_order:
        if pattern not in by_pattern:
            continue
            
        pattern_results = by_pattern[pattern]
        costs = []
        scores = []
        
        for result in pattern_results:
            metrics = compute_exploration_metrics(result)
            score = result.get("scoring", {}).get("final_score", 0)
            # Cap convergence cost for visualization
            cost = min(2.0, metrics["convergence_cost"])
            costs.append(cost)
            scores.append(score)
            all_costs.append(cost)
            all_scores.append(score)
        
        ax.scatter(costs, scores, label=pattern.replace('_', ' ').title(),
                  color=COLORS.get(pattern, '#333333'), marker=MARKERS.get(pattern, 'o'),
                  s=100, alpha=0.7)
    
    ax.set_xlabel("Convergence Cost (Diagnostic / Constructive)")
    ax.set_ylabel("Final Score")
    ax.set_title("Convergence Cost vs Task Success")
    ax.axvline(x=0.2, color='green', linestyle='--', alpha=0.5, label='Optimal range')
    ax.axvline(x=0.4, color='green', linestyle='--', alpha=0.5)
    ax.legend(loc='best')
    ax.set_xlim(0, 2.1)
    ax.set_ylim(0, 1.1)
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_dir / "convergence_cost_vs_success.png", dpi=300, bbox_inches='tight')
    plt.close()


def plot_coherence_trajectory_best_run(results: List[Dict], output_dir: Path):
    """Plot coherence trajectory for the best-scoring run (healthy pattern)."""
    sorted_results = sorted(results, key=lambda r: r.get("scoring", {}).get("final_score", 0), reverse=True)
    best_run = sorted_results[0] if sorted_results else None
    if not best_run:
        return
    fig, ax = plt.subplots(figsize=(6, 5))
    turn_data = compute_turn_metrics(best_run)
    turns = [m["turn"] for m in turn_data["turn_metrics"]]
    coherence = [m["coherence"] for m in turn_data["turn_metrics"]]
    pattern = get_pattern_name(best_run)
    task = best_run.get("task_id", "unknown")
    score = best_run.get("scoring", {}).get("final_score", 0)
    task_display = TASK_METADATA.get(task, {}).get("display_name", task)
    ax.plot(turns, coherence, "g-", linewidth=2, marker="o")
    ax.fill_between(turns, 0, coherence, alpha=0.3, color="green")
    ax.set_title(f"Best Run: {pattern}\n({task_display}, Score: {score:.2f})")
    ax.set_xlabel("Turn")
    ax.set_ylabel("Coherence")
    ax.set_ylim(0, 1.1)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_dir / "coherence_trajectory_best_run.png", dpi=300, bbox_inches="tight")
    plt.close()


def plot_coherence_trajectory_worst_run(results: List[Dict], output_dir: Path):
    """Plot coherence trajectory for the worst-scoring run."""
    sorted_results = sorted(results, key=lambda r: r.get("scoring", {}).get("final_score", 0), reverse=True)
    worst_run = sorted_results[-1] if len(sorted_results) > 1 else None
    if not worst_run:
        return
    fig, ax = plt.subplots(figsize=(6, 5))
    turn_data = compute_turn_metrics(worst_run)
    turns = [m["turn"] for m in turn_data["turn_metrics"]]
    coherence = [m["coherence"] for m in turn_data["turn_metrics"]]
    pattern = get_pattern_name(worst_run)
    task = worst_run.get("task_id", "unknown")
    score = worst_run.get("scoring", {}).get("final_score", 0)
    task_display = TASK_METADATA.get(task, {}).get("display_name", task)
    ax.plot(turns, coherence, "r-", linewidth=2, marker="o")
    ax.fill_between(turns, 0, coherence, alpha=0.3, color="red")
    ax.set_title(f"Worst Run: {pattern}\n({task_display}, Score: {score:.2f})")
    ax.set_xlabel("Turn")
    ax.set_ylabel("Coherence")
    ax.set_ylim(0, 1.1)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_dir / "coherence_trajectory_worst_run.png", dpi=300, bbox_inches="tight")
    plt.close()


def plot_coherence_trajectory_meltdown(results: List[Dict], output_dir: Path):
    """Plot coherence and destructive ratio for a meltdown example."""
    meltdown_run = None
    for r in results:
        signals = detect_meltdown_patterns(r)
        if signals["meltdown_detected"]:
            meltdown_run = r
            break
    fig, ax1 = plt.subplots(figsize=(6, 5))
    if meltdown_run:
        turn_data = compute_turn_metrics(meltdown_run)
        turns = [m["turn"] for m in turn_data["turn_metrics"]]
        coherence = [m["coherence"] for m in turn_data["turn_metrics"]]
        destructive = [m["destructive_ratio"] for m in turn_data["turn_metrics"]]
        pattern = get_pattern_name(meltdown_run)
        task = meltdown_run.get("task_id", "unknown")
        score = meltdown_run.get("scoring", {}).get("final_score", 0)
        signals = detect_meltdown_patterns(meltdown_run)
        task_display = TASK_METADATA.get(task, {}).get("display_name", task)
        ax2 = ax1.twinx()
        ax1.plot(turns, coherence, "b-", linewidth=2, marker="o", label="Coherence")
        ax2.plot(turns, destructive, "r--", linewidth=2, marker="x", label="Destructive Ratio")
        ax1.set_title(f"Meltdown: {pattern}\n({task_display}, Signals: {signals['signals_count']})")
        ax1.set_xlabel("Turn")
        ax1.set_ylabel("Coherence", color="blue")
        ax2.set_ylabel("Destructive Ratio", color="red")
        ax1.set_ylim(0, 1.1)
        ax2.set_ylim(0, 0.5)
        ax1.grid(True, alpha=0.3)
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc="best")
    else:
        ax1.text(0.5, 0.5, "No meltdown\npatterns detected",
                 ha="center", va="center", transform=ax1.transAxes, fontsize=12)
        ax1.set_title("Meltdown Example")
    plt.tight_layout()
    plt.savefig(output_dir / "coherence_trajectory_meltdown.png", dpi=300, bbox_inches="tight")
    plt.close()


def plot_autonomy_budget_analysis(results: List[Dict], output_dir: Path):
    """
    Analyze relationship between turns used and task risk/complexity.
    Validates the autonomy budget model from Paper 1.
    """
    fig, ax = plt.subplots(figsize=(10, 6))
    
    for result in results:
        task_id = result.get("task_id", "unknown")
        metadata = TASK_METADATA.get(task_id, {})
        
        # Calculate task complexity
        depth = metadata.get("sequential_depth", 1)
        difficulty = {"basic": 1, "intermediate": 2, "expert": 3}.get(metadata.get("difficulty", "basic"), 1)
        complexity = depth * difficulty
        
        turns = result.get("metrics", {}).get("turns_to_complete", 1)
        success = result.get("success", False)
        pattern = get_pattern_name(result)
        
        color = COLORS.get(pattern, '#333333')
        marker = MARKERS.get(pattern, 'o')
        edge_color = 'green' if success else 'red'
        
        ax.scatter(complexity, turns, color=color, marker=marker, 
                  s=150, alpha=0.7, edgecolors=edge_color, linewidths=2)
    
    # Add legend for patterns
    for pattern in ["single", "sequential", "debate", "group_chat", "concurrent"]:
        ax.scatter([], [], color=COLORS.get(pattern, '#333'), marker=MARKERS.get(pattern, 'o'),
                  s=100, label=pattern.replace('_', ' ').title())
    
    # Add legend for success
    ax.scatter([], [], color='gray', marker='o', s=100, edgecolors='green', linewidths=2, label='Success')
    ax.scatter([], [], color='gray', marker='o', s=100, edgecolors='red', linewidths=2, label='Failure')
    
    # Autonomy budget line (from Paper 1)
    x_line = np.linspace(1, 25, 100)
    # Base budget / (complexity factor)
    budget_line = 20 / np.sqrt(x_line)
    ax.plot(x_line, budget_line, 'k--', alpha=0.5, label='Suggested Autonomy Budget')
    
    ax.set_xlabel("Task Complexity (Depth × Difficulty)")
    ax.set_ylabel("Turns Used")
    ax.set_title("Turns Used vs Task Complexity\n(Edge color: Green=Success, Red=Failure)")
    ax.legend(loc='upper right', ncol=2)
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_dir / "autonomy_budget_analysis.png", dpi=300, bbox_inches='tight')
    plt.close()


# =============================================================================
# Report Generation
# =============================================================================

def generate_coherence_report(results: List[Dict], output_dir: Path) -> str:
    """Generate comprehensive coherence analysis report."""
    
    by_pattern = group_by_pattern(results)
    by_task = group_by_task(results)
    
    report = []
    report.append("# Network Coherence Analysis Report")
    report.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"\nTotal Runs Analyzed: {len(results)}")
    
    # Summary statistics
    report.append("\n## 1. Executive Summary")
    
    pattern_summaries = []
    for pattern in ["single", "sequential", "debate", "group_chat", "concurrent"]:
        if pattern not in by_pattern:
            continue
        pattern_results = by_pattern[pattern]
        
        # Compute aggregates
        exploration_rates = [compute_exploration_metrics(r)["exploration_rate"] * 100 for r in pattern_results]
        destructive_ratios = [compute_exploration_metrics(r)["destructive_ratio"] * 100 for r in pattern_results]
        scores = [r.get("scoring", {}).get("final_score", 0) for r in pattern_results]
        success_rates = [1 if r.get("success") else 0 for r in pattern_results]
        meltdowns = [1 if detect_meltdown_patterns(r)["meltdown_detected"] else 0 for r in pattern_results]
        
        pattern_summaries.append({
            "pattern": pattern,
            "n": len(pattern_results),
            "avg_score": np.mean(scores),
            "success_rate": np.mean(success_rates) * 100,
            "exploration_rate": np.mean(exploration_rates),
            "destructive_ratio": np.mean(destructive_ratios),
            "meltdown_rate": np.mean(meltdowns) * 100,
        })
    
    report.append("\n| Pattern | N | Avg Score | Success % | Exploration % | Destructive % | Meltdown % |")
    report.append("|---------|---|-----------|-----------|---------------|---------------|------------|")
    for s in pattern_summaries:
        report.append(f"| {s['pattern'].title()} | {s['n']} | {s['avg_score']:.3f} | {s['success_rate']:.0f}% | {s['exploration_rate']:.1f}% | {s['destructive_ratio']:.1f}% | {s['meltdown_rate']:.0f}% |")
    
    # Key findings
    report.append("\n### Key Findings")
    
    # Find best and worst patterns
    best_pattern = max(pattern_summaries, key=lambda x: x["avg_score"])
    worst_pattern = min(pattern_summaries, key=lambda x: x["avg_score"])
    highest_destructive = max(pattern_summaries, key=lambda x: x["destructive_ratio"])
    
    report.append(f"\n- **Best performing pattern**: {best_pattern['pattern'].title()} (avg score: {best_pattern['avg_score']:.3f})")
    report.append(f"- **Worst performing pattern**: {worst_pattern['pattern'].title()} (avg score: {worst_pattern['avg_score']:.3f})")
    report.append(f"- **Highest destructive ratio**: {highest_destructive['pattern'].title()} ({highest_destructive['destructive_ratio']:.1f}%)")
    
    # Correlation analysis
    all_exploration = []
    all_scores = []
    for r in results:
        all_exploration.append(compute_exploration_metrics(r)["exploration_rate"])
        all_scores.append(r.get("scoring", {}).get("final_score", 0))
    
    if len(all_exploration) > 2:
        corr, p_value = stats.pearsonr(all_exploration, all_scores)
        report.append(f"- **Exploration-Success Correlation**: r={corr:.3f} (p={p_value:.3f})")
    
    # Detailed coherence analysis
    report.append("\n## 2. Coherence Curve Analysis")
    report.append("\nThe Network Coherence Curve tracks cumulative progress over interaction turns.")
    report.append("Coherence(t) = (Progress(t)) × (1 - Destructive_Ratio(t))")
    
    report.append("\n### 2.1 Coherence by Pattern")
    for pattern in ["single", "sequential", "debate", "group_chat", "concurrent"]:
        if pattern not in by_pattern:
            continue
        pattern_results = by_pattern[pattern]
        
        coherences = [compute_turn_metrics(r)["final_coherence"] for r in pattern_results]
        
        report.append(f"\n**{pattern.replace('_', ' ').title()}**")
        report.append(f"- Average final coherence: {np.mean(coherences):.3f} ± {np.std(coherences):.3f}")
        report.append(f"- Range: [{min(coherences):.3f}, {max(coherences):.3f}]")
    
    # Meltdown analysis
    report.append("\n## 3. Meltdown Pattern Analysis")
    report.append("\nMeltdown signals indicate agent failure patterns:")
    report.append("1. Consecutive identical commands (>3)")
    report.append("2. High destructive ratio (>15%)")
    report.append("3. Coherence plateau (>10 turns without progress)")
    report.append("4. Repeated status checks (>5 consecutive)")
    
    meltdown_cases = []
    for r in results:
        signals = detect_meltdown_patterns(r)
        if signals["meltdown_detected"]:
            meltdown_cases.append({
                "pattern": get_pattern_name(r),
                "task": r.get("task_id", "unknown"),
                "signals": signals["signals_count"],
                "details": signals["details"],
                "score": r.get("scoring", {}).get("final_score", 0),
            })
    
    report.append(f"\n### Meltdown Cases: {len(meltdown_cases)} / {len(results)} runs ({100*len(meltdown_cases)/len(results):.1f}%)")
    
    if meltdown_cases:
        report.append("\n| Pattern | Task | Signals | Score | Details |")
        report.append("|---------|------|---------|-------|---------|")
        for case in meltdown_cases[:10]:  # Limit to 10
            task_display = TASK_METADATA.get(case["task"], {}).get("display_name", case["task"])
            details_short = case["details"][0][:50] + "..." if case["details"] else "N/A"
            report.append(f"| {case['pattern'].title()} | {task_display} | {case['signals']} | {case['score']:.3f} | {details_short} |")
    
    # Exploration analysis
    report.append("\n## 4. Exploration Efficiency Analysis")
    
    report.append("\n### 4.1 Command Composition by Pattern")
    report.append("\n| Pattern | Constructive % | Diagnostic % | Destructive % | Other % |")
    report.append("|---------|----------------|--------------|---------------|---------|")
    
    for pattern in ["single", "sequential", "debate", "group_chat", "concurrent"]:
        if pattern not in by_pattern:
            continue
        pattern_results = by_pattern[pattern]
        all_metrics = [compute_exploration_metrics(r) for r in pattern_results]
        
        total = sum(m["total_commands"] for m in all_metrics)
        if total == 0:
            continue
            
        const = sum(m["constructive"] for m in all_metrics) / total * 100
        diag = sum(m["diagnostic"] for m in all_metrics) / total * 100
        dest = sum(m["destructive"] for m in all_metrics) / total * 100
        other = sum(m["other"] for m in all_metrics) / total * 100
        
        report.append(f"| {pattern.title()} | {const:.1f}% | {diag:.1f}% | {dest:.1f}% | {other:.1f}% |")
    
    report.append("\n### 4.2 Convergence Cost")
    report.append("\nConvergence Cost = Diagnostic Commands / Constructive Commands")
    report.append("Higher values indicate more cautious agents.")
    
    report.append("\n| Pattern | Avg Convergence Cost | Success Rate |")
    report.append("|---------|---------------------|--------------|")
    
    for pattern in ["single", "sequential", "debate", "group_chat", "concurrent"]:
        if pattern not in by_pattern:
            continue
        pattern_results = by_pattern[pattern]
        costs = [compute_exploration_metrics(r)["convergence_cost"] for r in pattern_results]
        success_rate = sum(1 for r in pattern_results if r.get("success")) / len(pattern_results) * 100
        report.append(f"| {pattern.title()} | {np.mean(costs):.3f} | {success_rate:.0f}% |")
    
    # Risk-Autonomy analysis
    report.append("\n## 5. Risk-Autonomy Analysis")
    report.append("\nAnalyzing the relationship between task complexity and agent autonomy usage.")
    
    report.append("\n### 5.1 Turns by Task Complexity")
    report.append("\n| Task | Complexity | Avg Turns | Success Rate |")
    report.append("|------|------------|-----------|--------------|")
    
    for task_id, metadata in TASK_METADATA.items():
        if task_id not in by_task:
            continue
        task_results = by_task[task_id]
        
        depth = metadata.get("sequential_depth", 1)
        difficulty = {"basic": 1, "intermediate": 2, "expert": 3}.get(metadata.get("difficulty", "basic"), 1)
        complexity = depth * difficulty
        
        turns = [r.get("metrics", {}).get("turns_to_complete", 0) for r in task_results]
        success_rate = sum(1 for r in task_results if r.get("success")) / len(task_results) * 100
        
        report.append(f"| {metadata.get('display_name', task_id)} | {complexity} | {np.mean(turns):.1f} | {success_rate:.0f}% |")
    
    # Recommendations
    report.append("\n## 6. Recommendations")
    report.append("\nBased on this analysis:")
    
    # Pattern recommendations
    report.append("\n### 6.1 Pattern Selection Guidelines")
    if worst_pattern["pattern"] == "group_chat":
        report.append("- **Avoid Group Chat** for network configuration tasks (0% success, high destructive ratio)")
    report.append(f"- **Prefer {best_pattern['pattern'].title()}** for general tasks (highest avg score)")
    
    for s in pattern_summaries:
        if s["meltdown_rate"] > 50:
            report.append(f"- **Caution with {s['pattern'].title()}**: {s['meltdown_rate']:.0f}% meltdown rate")
    
    # Autonomy recommendations
    report.append("\n### 6.2 Autonomy Budget Guidelines")
    report.append("- Set circuit breaker thresholds at 15% destructive ratio")
    report.append("- Implement checkpoint reviews every 5-10 turns for complex tasks")
    report.append("- Monitor for coherence plateau (>10 turns without property satisfaction)")
    
    return "\n".join(report)


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/analyze_coherence_curves.py <session_dir>")
        print("Example: python scripts/analyze_coherence_curves.py results/comparative_study/comparative_study_20260217_104418")
        sys.exit(1)
    
    session_dir = Path(sys.argv[1])
    if not session_dir.exists():
        print(f"Error: Session directory not found: {session_dir}")
        sys.exit(1)
    
    print(f"Loading results from {session_dir}...")
    results = load_session_results(session_dir)
    print(f"Loaded {len(results)} results")
    
    # Filter invalid results
    valid_results = [r for r in results if r.get("metrics", {}).get("total_commands", 0) > 0]
    print(f"Valid results (with commands): {len(valid_results)}")
    
    if not valid_results:
        print("Error: No valid results found")
        sys.exit(1)
    
    # Create charts directory
    charts_dir = session_dir / "charts"
    charts_dir.mkdir(exist_ok=True)
    
    # Generate charts
    print("\nGenerating charts...")
    
    print("  - Coherence curves by pattern")
    plot_coherence_curves_by_pattern(valid_results, charts_dir)
    
    print("  - Exploration vs success")
    plot_exploration_vs_success(valid_results, charts_dir)
    
    print("  - Destructive ratio by pattern")
    plot_destructive_ratio_by_pattern(valid_results, charts_dir)
    
    print("  - Meltdown heatmap")
    plot_meltdown_heatmap(valid_results, charts_dir)
    
    print("  - Command composition")
    plot_command_composition_stacked(valid_results, charts_dir)
    
    print("  - Convergence cost vs success")
    plot_convergence_cost_vs_success(valid_results, charts_dir)
    
    print("  - Coherence trajectory (best run)")
    plot_coherence_trajectory_best_run(valid_results, charts_dir)
    print("  - Coherence trajectory (worst run)")
    plot_coherence_trajectory_worst_run(valid_results, charts_dir)
    print("  - Coherence trajectory (meltdown)")
    plot_coherence_trajectory_meltdown(valid_results, charts_dir)
    
    print("  - Autonomy budget analysis")
    plot_autonomy_budget_analysis(valid_results, charts_dir)
    
    # Generate report
    print("\nGenerating coherence analysis report...")
    report = generate_coherence_report(valid_results, charts_dir)
    
    report_path = session_dir / "coherence_analysis_report.md"
    with open(report_path, 'w') as f:
        f.write(report)
    print(f"Report saved to: {report_path}")
    
    print(f"\nCharts saved to: {charts_dir}")
    print("\nAnalysis complete!")


if __name__ == "__main__":
    main()
