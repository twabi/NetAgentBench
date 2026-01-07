#!/usr/bin/env python3
"""
Analyze multi-turn benchmark study results.

Compares performance across:
- Single-agent vs Multi-agent
- Multi-agent patterns (sequential, debate, group_chat, concurrent)
- Models (GPT vs Gemini)
- Tasks (small, medium, large)

Usage:
    python scripts/analyze_multiturn_results.py results/multiturn_runs/<session_name>
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


# Academic styling
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams.update({
    'font.size': 11,
    'font.family': 'serif',
    'axes.labelsize': 12,
    'axes.titlesize': 13,
    'axes.titleweight': 'bold',
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'legend.fontsize': 9,
    'figure.dpi': 150,
    'savefig.dpi': 300,
    'axes.spines.top': False,
    'axes.spines.right': False,
})

COLORS = {
    'single': '#2E86AB',
    'sequential': '#A23B72', 
    'debate': '#F18F01',
    'group_chat': '#C73E1D',
    'concurrent': '#3B1F2B',
    'gpt': '#74AA9C',
    'gemini': '#4285F4',
}

HATCHES = ['///', '\\\\\\', 'xxx', '...', '+++', 'ooo']


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


def normalize_model_name(result: Dict) -> str:
    """Extract and normalize model name from result."""
    model = result.get("model_version") or ""
    
    # Remove provider prefix if present (e.g., "openai:" or "gemini:")
    if ":" in model:
        model = model.split(":")[-1]
    
    # Simplify long model names
    model = model.replace("-2025-08-07", "").replace("2025-08-07", "")
    
    # Standard names
    if "gpt-5-mini" in model.lower() or "gpt5mini" in model.lower():
        return "GPT-5-mini"
    elif "gemini-2.5-pro" in model.lower() or "gemini25pro" in model.lower():
        return "Gemini-2.5-Pro"
    elif "gemini" in model.lower():
        return "Gemini"
    elif "gpt" in model.lower():
        return "GPT"
    
    return model or "unknown"


def extract_agent_config(result: Dict) -> Tuple[str, str]:
    """Extract (mode, structure) from result testee_id."""
    testee_id = result.get("testee_id", "").lower()
    
    # Default
    mode = "single"
    structure = "sequential"
    
    # New format: provider_model_multi_structure or provider_model_single
    # e.g., "gemini_gemini25pro_multi_debate", "openai_gpt5_single"
    
    # Check for multi-agent patterns
    if "_multi_sequential" in testee_id:
        mode = "multi"
        structure = "sequential"
    elif "_multi_debate" in testee_id:
        mode = "multi"
        structure = "debate"
    elif "_multi_group_chat" in testee_id:
        mode = "multi"
        structure = "group_chat"
    elif "_multi_concurrent" in testee_id:
        mode = "multi"
        structure = "concurrent"
    elif "_multi" in testee_id:
        # Old format without structure - assume sequential
        mode = "multi"
        structure = "sequential"
    elif "_single" in testee_id:
        mode = "single"
        structure = "sequential"
    
    return mode, structure


def compute_metrics(results: List[Dict]) -> Dict[str, Any]:
    """Compute aggregate metrics from results."""
    if not results:
        return {"count": 0}
    
    metrics = {
        "count": len(results),
        "success_rate": sum(1 for r in results if r.get("success")) / len(results),
        "avg_final_score": np.mean([r.get("scoring", {}).get("final_score", 0) for r in results]),
        "std_final_score": np.std([r.get("scoring", {}).get("final_score", 0) for r in results]),
        "avg_completeness": np.mean([r.get("scoring", {}).get("completeness", 0) for r in results]),
        "avg_robustness": np.mean([r.get("scoring", {}).get("robustness", 0) for r in results]),
    }
    
    # Multi-turn specific
    turns = [r.get("metrics", {}).get("turns_to_complete") for r in results]
    turns = [t for t in turns if t is not None and t > 0]
    if turns:
        metrics["avg_turns"] = np.mean(turns)
        metrics["std_turns"] = np.std(turns)
    
    times = [r.get("metrics", {}).get("time_to_complete") for r in results]
    times = [t for t in times if t is not None and t > 0]
    if times:
        metrics["avg_time"] = np.mean(times)
        metrics["std_time"] = np.std(times)
    
    return metrics


def group_by_pattern(results: List[Dict]) -> Dict[str, List[Dict]]:
    """Group results by agent pattern (single, sequential, debate, etc)."""
    groups = defaultdict(list)
    
    for result in results:
        mode, structure = extract_agent_config(result)
        if mode == "single":
            key = "single"
        else:
            key = structure
        groups[key].append(result)
    
    return dict(groups)


def group_by_model(results: List[Dict]) -> Dict[str, List[Dict]]:
    """Group results by normalized model name."""
    groups = defaultdict(list)
    for result in results:
        model = normalize_model_name(result)
        groups[model].append(result)
    return dict(groups)


def group_by_task(results: List[Dict]) -> Dict[str, List[Dict]]:
    """Group results by task."""
    groups = defaultdict(list)
    for result in results:
        task_id = result.get("task_id", "unknown")
        groups[task_id].append(result)
    return dict(groups)


# =============================================================================
# NEW: Command Quality Analysis
# =============================================================================

def classify_command(cmd: str) -> str:
    """Classify a command as diagnostic, constructive, or destructive."""
    cmd_lower = cmd.lower()
    
    # Destructive patterns - removing config
    if any(pattern in cmd_lower for pattern in [
        'no router', 'no ip address', 'no network', 'no interface',
        'delete', 'remove', 'shutdown', 'no ospf', 'no bgp'
    ]):
        return 'destructive'
    
    # Diagnostic patterns - information gathering
    if any(pattern in cmd_lower for pattern in [
        'show ', 'display', 'ping ', 'traceroute', 'get ', 'list',
        'cat ', 'grep ', 'ip route', 'ip addr show', 'ip link show'
    ]):
        return 'diagnostic'
    
    # Configuration patterns - adding/modifying config
    if any(pattern in cmd_lower for pattern in [
        'configure', 'router ospf', 'router bgp', 'network ', 
        'ip address', 'ip addr add', 'interface ', 'vtysh',
        'router-id', 'area ', 'end', 'write'
    ]):
        return 'constructive'
    
    return 'other'


def parse_execution_log(result: Dict) -> List[Dict[str, Any]]:
    """Parse execution log entries into structured data."""
    log = result.get("execution_log", [])
    parsed = []
    
    for entry in log:
        if isinstance(entry, str) and ' | ' in entry:
            parts = entry.split(' | ', 1)
            node = parts[0].strip()
            cmd = parts[1].strip() if len(parts) > 1 else ""
            parsed.append({
                "node": node,
                "command": cmd,
                "type": classify_command(cmd),
                "raw": entry,
            })
        elif isinstance(entry, str):
            parsed.append({
                "node": "unknown",
                "command": entry,
                "type": classify_command(entry),
                "raw": entry,
            })
    
    return parsed


def analyze_execution_logs(results: List[Dict]) -> Dict[str, Any]:
    """Analyze execution logs across all results."""
    analysis = {
        "total_commands": 0,
        "by_type": defaultdict(int),
        "by_pattern": defaultdict(lambda: {"total": 0, "destructive": 0, "constructive": 0, "diagnostic": 0, "other": 0}),
        "by_node": defaultdict(int),
        "commands_per_run": [],
    }
    
    for result in results:
        mode, structure = extract_agent_config(result)
        pattern = "single" if mode == "single" else structure
        parsed = parse_execution_log(result)
        
        run_cmds = len(parsed)
        analysis["total_commands"] += run_cmds
        analysis["commands_per_run"].append(run_cmds)
        
        for entry in parsed:
            cmd_type = entry["type"]
            analysis["by_type"][cmd_type] += 1
            analysis["by_pattern"][pattern]["total"] += 1
            analysis["by_pattern"][pattern][cmd_type] += 1
            analysis["by_node"][entry["node"]] += 1
    
    # Compute averages
    if analysis["commands_per_run"]:
        analysis["avg_commands"] = np.mean(analysis["commands_per_run"])
        analysis["std_commands"] = np.std(analysis["commands_per_run"])
    
    return analysis


# =============================================================================
# NEW: Error Rate Analysis
# =============================================================================

def categorize_error(error: str) -> str:
    """Categorize an error message."""
    error_lower = error.lower()
    
    if 'timed out' in error_lower or 'timeout' in error_lower:
        return 'timeout'
    if 'property' in error_lower and 'failed' in error_lower:
        return 'property_failure'
    if 'syntax' in error_lower or 'parse' in error_lower:
        return 'syntax_error'
    if 'connection' in error_lower or 'refused' in error_lower:
        return 'connection_error'
    if 'exit' in error_lower and 'code' in error_lower:
        return 'command_error'
    
    return 'other'


def analyze_errors(results: List[Dict]) -> Dict[str, Any]:
    """Analyze errors across all results."""
    analysis = {
        "total_errors": 0,
        "runs_with_errors": 0,
        "by_type": defaultdict(int),
        "by_pattern": defaultdict(lambda: {"total": 0, "timeout": 0, "property_failure": 0, "syntax_error": 0, "connection_error": 0, "command_error": 0, "other": 0}),
        "error_rate_by_pattern": {},
    }
    
    by_pattern = group_by_pattern(results)
    
    for result in results:
        mode, structure = extract_agent_config(result)
        pattern = "single" if mode == "single" else structure
        errors = result.get("errors", [])
        
        if errors:
            analysis["runs_with_errors"] += 1
        
        for error in errors:
            analysis["total_errors"] += 1
            error_type = categorize_error(error)
            analysis["by_type"][error_type] += 1
            analysis["by_pattern"][pattern]["total"] += 1
            analysis["by_pattern"][pattern][error_type] += 1
    
    # Compute error rates per pattern
    for pattern, pattern_results in by_pattern.items():
        total_runs = len(pattern_results)
        runs_with_errors = sum(1 for r in pattern_results if r.get("errors"))
        analysis["error_rate_by_pattern"][pattern] = runs_with_errors / total_runs if total_runs > 0 else 0
    
    return analysis


# =============================================================================
# NEW: Property-Level Analysis
# =============================================================================

def analyze_property_results(results: List[Dict]) -> Dict[str, Any]:
    """Analyze per-property satisfaction rates."""
    analysis = {
        "properties": defaultdict(lambda: {"satisfied": 0, "total": 0}),
        "by_pattern": defaultdict(lambda: defaultdict(lambda: {"satisfied": 0, "total": 0})),
        "hardest_properties": [],
    }
    
    for result in results:
        mode, structure = extract_agent_config(result)
        pattern = "single" if mode == "single" else structure
        
        for prop in result.get("property_results", []):
            prop_id = prop.get("property_id", "unknown")
            satisfied = prop.get("satisfied", False)
            
            analysis["properties"][prop_id]["total"] += 1
            analysis["by_pattern"][pattern][prop_id]["total"] += 1
            
            if satisfied:
                analysis["properties"][prop_id]["satisfied"] += 1
                analysis["by_pattern"][pattern][prop_id]["satisfied"] += 1
    
    # Find hardest properties
    prop_rates = []
    for prop_id, data in analysis["properties"].items():
        rate = data["satisfied"] / data["total"] if data["total"] > 0 else 0
        prop_rates.append((prop_id, rate, data["total"]))
    
    analysis["hardest_properties"] = sorted(prop_rates, key=lambda x: x[1])[:5]
    
    return analysis


# =============================================================================
# NEW: Exploration Pattern Analysis (RQ4)
# =============================================================================

def analyze_exploration_patterns(results: List[Dict]) -> Dict[str, Any]:
    """Analyze exploration patterns for RQ4."""
    analysis = {
        "by_pattern": {},
        "diagnostic_ratios": [],
        "backtracking_by_pattern": defaultdict(list),
    }
    
    by_pattern = group_by_pattern(results)
    
    for pattern, pattern_results in by_pattern.items():
        total_diagnostic = 0
        total_constructive = 0
        total_destructive = 0
        total_commands = 0
        
        for result in pattern_results:
            parsed = parse_execution_log(result)
            total_commands += len(parsed)
            
            # Count command types
            for entry in parsed:
                if entry["type"] == "diagnostic":
                    total_diagnostic += 1
                elif entry["type"] == "constructive":
                    total_constructive += 1
                elif entry["type"] == "destructive":
                    total_destructive += 1
            
            # Detect backtracking (same node appears multiple times)
            node_counts = defaultdict(int)
            for entry in parsed:
                node_counts[entry["node"]] += 1
            backtrack_count = sum(1 for c in node_counts.values() if c > 1)
            analysis["backtracking_by_pattern"][pattern].append(backtrack_count)
        
        if total_commands > 0:
            analysis["by_pattern"][pattern] = {
                "exploration_rate": total_diagnostic / total_commands,
                "construction_rate": total_constructive / total_commands,
                "destruction_rate": total_destructive / total_commands,
                "total_commands": total_commands,
                "avg_backtracking": np.mean(analysis["backtracking_by_pattern"][pattern]) if analysis["backtracking_by_pattern"][pattern] else 0,
            }
    
    return analysis


# =============================================================================
# NEW: Research Metrics (RQ1-RQ3)
# =============================================================================

def compute_research_metrics(results: List[Dict]) -> Dict[str, Any]:
    """Compute metrics aligned with RQ1-RQ3."""
    by_pattern = group_by_pattern(results)
    
    metrics = {
        "rq1_architecture_comparison": {},
        "rq2_role_specialization": {},
        "rq3_parallelism": {},
    }
    
    # RQ1: Single vs Multi-Agent Scores
    single_scores = [r.get("scoring", {}).get("final_score", 0) for r in by_pattern.get("single", [])]
    multi_scores = []
    for pattern in ["sequential", "debate", "group_chat", "concurrent"]:
        multi_scores.extend([r.get("scoring", {}).get("final_score", 0) for r in by_pattern.get(pattern, [])])
    
    if single_scores and multi_scores:
        metrics["rq1_architecture_comparison"] = {
            "single_avg": np.mean(single_scores),
            "single_std": np.std(single_scores),
            "multi_avg": np.mean(multi_scores),
            "multi_std": np.std(multi_scores),
            "difference": np.mean(single_scores) - np.mean(multi_scores),
        }
    
    # RQ2: Command Success Rates (proxy for role specialization)
    for pattern, pattern_results in by_pattern.items():
        total_cmds = 0
        successful_runs = 0
        
        for result in pattern_results:
            parsed = parse_execution_log(result)
            total_cmds += len(parsed)
            if result.get("success"):
                successful_runs += 1
        
        if pattern_results:
            metrics["rq2_role_specialization"][pattern] = {
                "total_commands": total_cmds,
                "avg_commands_per_run": total_cmds / len(pattern_results),
                "success_rate": successful_runs / len(pattern_results),
            }
    
    # RQ3: Parallelism (commands per turn)
    for pattern, pattern_results in by_pattern.items():
        turns = [r.get("metrics", {}).get("turns_to_complete", 0) for r in pattern_results]
        times = [r.get("metrics", {}).get("time_to_complete", 0) for r in pattern_results]
        
        total_cmds = sum(len(parse_execution_log(r)) for r in pattern_results)
        total_turns = sum(t for t in turns if t and t > 0)
        
        if total_turns > 0:
            metrics["rq3_parallelism"][pattern] = {
                "parallelism_factor": total_cmds / total_turns,
                "avg_time": np.mean([t for t in times if t and t > 0]) if any(t > 0 for t in times) else 0,
                "avg_turns": np.mean([t for t in turns if t and t > 0]) if any(t > 0 for t in turns) else 0,
            }
    
    # Speedup: single vs multi time
    single_times = [r.get("metrics", {}).get("time_to_complete", 0) for r in by_pattern.get("single", [])]
    single_times = [t for t in single_times if t and t > 0]
    
    if single_times:
        single_avg_time = np.mean(single_times)
        for pattern in ["sequential", "debate", "group_chat", "concurrent"]:
            pattern_times = [r.get("metrics", {}).get("time_to_complete", 0) for r in by_pattern.get(pattern, [])]
            pattern_times = [t for t in pattern_times if t and t > 0]
            if pattern_times:
                if pattern not in metrics["rq3_parallelism"]:
                    metrics["rq3_parallelism"][pattern] = {}
                metrics["rq3_parallelism"][pattern]["speedup_vs_single"] = single_avg_time / np.mean(pattern_times)
    
    return metrics



def generate_report(session_dir: Path, results: List[Dict]) -> str:
    """Generate markdown analysis report."""
    lines = [
        "# Multi-Turn Benchmark Study Analysis",
        "",
        f"**Session:** {session_dir.name}",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Total Runs:** {len(results)}",
        "",
    ]
    
    # Overall metrics
    overall = compute_metrics(results)
    lines.extend([
        "## Overall Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Success Rate | {overall.get('success_rate', 0)*100:.1f}% |",
        f"| Avg Final Score | {overall.get('avg_final_score', 0):.3f} ± {overall.get('std_final_score', 0):.3f} |",
        f"| Avg Completeness | {overall.get('avg_completeness', 0):.3f} |",
        f"| Avg Robustness | {overall.get('avg_robustness', 0):.3f} |",
    ])
    if "avg_turns" in overall:
        lines.append(f"| Avg Turns | {overall['avg_turns']:.1f} ± {overall.get('std_turns', 0):.1f} |")
    if "avg_time" in overall:
        lines.append(f"| Avg Time | {overall['avg_time']:.0f}s ± {overall.get('std_time', 0):.0f}s |")
    lines.append("")
    
    # Pattern comparison (main focus!)
    by_pattern = group_by_pattern(results)
    lines.extend([
        "---",
        "",
        "## Agent Pattern Comparison",
        "",
        "| Pattern | Runs | Success | Score | Completeness | Robustness | Turns | Time |",
        "|---------|------|---------|-------|--------------|------------|-------|------|",
    ])
    
    pattern_order = ["single", "sequential", "debate", "group_chat", "concurrent"]
    for pattern in pattern_order:
        if pattern in by_pattern:
            m = compute_metrics(by_pattern[pattern])
            turns_str = f"{m.get('avg_turns', 0):.1f}" if "avg_turns" in m else "-"
            time_str = f"{m.get('avg_time', 0):.0f}s" if "avg_time" in m else "-"
            lines.append(
                f"| **{pattern}** | {m['count']} | {m['success_rate']*100:.0f}% | "
                f"{m['avg_final_score']:.3f} | {m['avg_completeness']:.3f} | "
                f"{m['avg_robustness']:.3f} | {turns_str} | {time_str} |"
            )
    lines.append("")
    
    # Model comparison  
    by_model = group_by_model(results)
    lines.extend([
        "---",
        "",
        "## Model Comparison",
        "",
        "| Model | Runs | Success | Score | Completeness | Turns |",
        "|-------|------|---------|-------|--------------|-------|",
    ])
    for model, model_results in sorted(by_model.items()):
        m = compute_metrics(model_results)
        turns_str = f"{m.get('avg_turns', 0):.1f}" if "avg_turns" in m else "-"
        lines.append(
            f"| **{model}** | {m['count']} | {m['success_rate']*100:.0f}% | "
            f"{m['avg_final_score']:.3f} | {m['avg_completeness']:.3f} | {turns_str} |"
        )
    lines.append("")
    
    # Task breakdown
    by_task = group_by_task(results)
    lines.extend([
        "---",
        "",
        "## Per-Task Breakdown",
        "",
        "| Task | Runs | Success | Score | Completeness | Turns |",
        "|------|------|---------|-------|--------------|-------|",
    ])
    for task, task_results in sorted(by_task.items()):
        m = compute_metrics(task_results)
        turns_str = f"{m.get('avg_turns', 0):.1f}" if "avg_turns" in m else "-"
        lines.append(
            f"| **{task}** | {m['count']} | {m['success_rate']*100:.0f}% | "
            f"{m['avg_final_score']:.3f} | {m['avg_completeness']:.3f} | {turns_str} |"
        )
    lines.append("")
    
    # Key findings
    lines.extend([
        "---",
        "",
        "## Key Findings",
        "",
    ])
    
    # Best pattern
    if by_pattern:
        best_pattern = max(by_pattern.items(), key=lambda x: compute_metrics(x[1])["avg_final_score"])
        worst_pattern = min(by_pattern.items(), key=lambda x: compute_metrics(x[1])["avg_final_score"])
        lines.append(f"- **Best pattern:** {best_pattern[0]} (score: {compute_metrics(best_pattern[1])['avg_final_score']:.3f})")
        lines.append(f"- **Worst pattern:** {worst_pattern[0]} (score: {compute_metrics(worst_pattern[1])['avg_final_score']:.3f})")
    
    # Best model
    if by_model:
        best_model = max(by_model.items(), key=lambda x: compute_metrics(x[1])["avg_final_score"])
        lines.append(f"- **Best model:** {best_model[0]} (score: {compute_metrics(best_model[1])['avg_final_score']:.3f})")
    
    # Hardest task
    if by_task:
        hardest_task = min(by_task.items(), key=lambda x: compute_metrics(x[1])["avg_final_score"])
        lines.append(f"- **Hardest task:** {hardest_task[0]} (score: {compute_metrics(hardest_task[1])['avg_final_score']:.3f})")
    
    lines.append("")
    
    # =========================================================================
    # NEW: Research Question Analysis
    # =========================================================================
    research_metrics = compute_research_metrics(results)
    
    lines.extend([
        "---",
        "",
        "## Research Question Analysis",
        "",
        "### RQ1: Architectural Effectiveness (Single vs Multi-Agent)",
        "",
    ])
    
    rq1 = research_metrics.get("rq1_architecture_comparison", {})
    if rq1:
        lines.extend([
            "| Architecture | Avg Score | Std Dev |",
            "|--------------|-----------|---------|",
            f"| Single-Agent | {rq1.get('single_avg', 0):.3f} | {rq1.get('single_std', 0):.3f} |",
            f"| Multi-Agent | {rq1.get('multi_avg', 0):.3f} | {rq1.get('multi_std', 0):.3f} |",
            "",
            f"**Difference:** Single outperforms multi by **{rq1.get('difference', 0):.3f}** points",
            "",
        ])
    else:
        lines.append("*Insufficient data for RQ1 analysis*")
        lines.append("")
    
    lines.extend([
        "### RQ2: Role Specialization (Command Efficiency)",
        "",
        "| Pattern | Total Commands | Avg Cmds/Run | Success Rate |",
        "|---------|----------------|--------------|--------------|",
    ])
    
    rq2 = research_metrics.get("rq2_role_specialization", {})
    for pattern in ["single", "sequential", "debate", "group_chat", "concurrent"]:
        if pattern in rq2:
            data = rq2[pattern]
            lines.append(
                f"| {pattern} | {data.get('total_commands', 0)} | "
                f"{data.get('avg_commands_per_run', 0):.1f} | "
                f"{data.get('success_rate', 0)*100:.0f}% |"
            )
    lines.append("")
    
    lines.extend([
        "### RQ3: Parallelism & Speedup",
        "",
        "| Pattern | Parallelism Factor | Avg Time (s) | Speedup vs Single |",
        "|---------|-------------------|--------------|-------------------|",
    ])
    
    rq3 = research_metrics.get("rq3_parallelism", {})
    for pattern in ["single", "sequential", "debate", "group_chat", "concurrent"]:
        if pattern in rq3:
            data = rq3[pattern]
            speedup = data.get('speedup_vs_single', '-')
            speedup_str = f"{speedup:.2f}x" if isinstance(speedup, (int, float)) else speedup
            lines.append(
                f"| {pattern} | {data.get('parallelism_factor', 0):.2f} | "
                f"{data.get('avg_time', 0):.0f} | {speedup_str} |"
            )
    lines.append("")
    
    # =========================================================================
    # NEW: Command Quality Analysis
    # =========================================================================
    cmd_analysis = analyze_execution_logs(results)
    
    lines.extend([
        "---",
        "",
        "## Command Quality Analysis",
        "",
        "Commands are classified by analyzing the execution log entries. Each entry is parsed and matched against keyword patterns:",
        "",
        "| Category | Description | Pattern Examples |",
        "|----------|-------------|------------------|",
        "| **Constructive** | Commands that add/configure routing | `router ospf`, `network X.X.X.X`, `ip address`, `vtysh -c 'configure'` |",
        "| **Diagnostic** | Commands that inspect state without changing it | `show ip ospf neighbor`, `ping`, `ip route`, `traceroute` |",
        "| **Destructive** | Commands that remove configuration | `no router ospf`, `no ip address`, `no network`, `shutdown` |",
        "| **Other** | Commands not matching above patterns | `end`, `exit`, shell utilities |",
        "",
        "**Example Execution Log Entry:**",
        "```",
        "R1 | vtysh -c 'configure terminal' -c 'router ospf' -c 'network 10.0.0.0/8 area 0'",
        "```",
        "→ Classified as **constructive** (contains `router ospf` and `network`)",
        "",
        "```",
        "R1 | vtysh -c 'configure terminal' -c 'no router ospf'",
        "```",
        "→ Classified as **destructive** (contains `no router`)",
        "",
        "### Command Type Distribution",
        "",
        "| Type | Count | Percentage |",
        "|------|-------|------------|",
    ])
    
    total_cmds = cmd_analysis.get("total_commands", 0)
    for cmd_type in ["constructive", "diagnostic", "destructive", "other"]:
        count = cmd_analysis["by_type"].get(cmd_type, 0)
        pct = (count / total_cmds * 100) if total_cmds > 0 else 0
        lines.append(f"| {cmd_type} | {count} | {pct:.1f}% |")
    
    lines.extend([
        "",
        f"**Total Commands Executed:** {total_cmds}",
        f"**Avg Commands per Run:** {cmd_analysis.get('avg_commands', 0):.1f} ± {cmd_analysis.get('std_commands', 0):.1f}",
        "",
    ])
    
    lines.extend([
        "### Command Distribution by Pattern",
        "",
        "| Pattern | Total | Constructive | Diagnostic | Destructive |",
        "|---------|-------|--------------|------------|-------------|",
    ])
    
    for pattern in ["single", "sequential", "debate", "group_chat", "concurrent"]:
        data = cmd_analysis["by_pattern"].get(pattern, {})
        if data.get("total", 0) > 0:
            lines.append(
                f"| {pattern} | {data.get('total', 0)} | "
                f"{data.get('constructive', 0)} | "
                f"{data.get('diagnostic', 0)} | "
                f"{data.get('destructive', 0)} |"
            )
    lines.append("")
    
    # =========================================================================
    # NEW: Error Analysis
    # =========================================================================
    error_analysis = analyze_errors(results)
    
    lines.extend([
        "---",
        "",
        "## Error Analysis",
        "",
        f"**Total Errors:** {error_analysis['total_errors']}",
        f"**Runs with Errors:** {error_analysis['runs_with_errors']} / {len(results)}",
        "",
        "### Error Types",
        "",
        "| Type | Count |",
        "|------|-------|",
    ])
    
    for error_type in ["timeout", "property_failure", "command_error", "syntax_error", "connection_error", "other"]:
        count = error_analysis["by_type"].get(error_type, 0)
        if count > 0:
            lines.append(f"| {error_type} | {count} |")
    
    lines.extend([
        "",
        "### Error Rate by Pattern",
        "",
        "| Pattern | Error Rate |",
        "|---------|------------|",
    ])
    
    for pattern in ["single", "sequential", "debate", "group_chat", "concurrent"]:
        rate = error_analysis["error_rate_by_pattern"].get(pattern)
        if rate is not None:
            lines.append(f"| {pattern} | {rate*100:.0f}% |")
    lines.append("")
    
    # =========================================================================
    # NEW: Exploration Pattern Analysis (RQ4)
    # =========================================================================
    exploration = analyze_exploration_patterns(results)
    
    lines.extend([
        "---",
        "",
        "## Exploration Pattern Analysis (RQ4)",
        "",
        "| Pattern | Exploration Rate | Construction Rate | Destruction Rate | Avg Backtracking |",
        "|---------|------------------|-------------------|------------------|------------------|",
    ])
    
    for pattern in ["single", "sequential", "debate", "group_chat", "concurrent"]:
        data = exploration["by_pattern"].get(pattern, {})
        if data:
            lines.append(
                f"| {pattern} | {data.get('exploration_rate', 0)*100:.1f}% | "
                f"{data.get('construction_rate', 0)*100:.1f}% | "
                f"{data.get('destruction_rate', 0)*100:.1f}% | "
                f"{data.get('avg_backtracking', 0):.1f} |"
            )
    lines.append("")
    
    # =========================================================================
    # NEW: Property-Level Analysis
    # =========================================================================
    prop_analysis = analyze_property_results(results)
    
    lines.extend([
        "---",
        "",
        "## Property-Level Analysis",
        "",
        "### Hardest Properties (Lowest Satisfaction Rate)",
        "",
        "| Property | Satisfaction Rate | Total Evaluations |",
        "|----------|-------------------|-------------------|",
    ])
    
    for prop_id, rate, total in prop_analysis["hardest_properties"]:
        lines.append(f"| {prop_id} | {rate*100:.0f}% | {total} |")
    
    lines.extend([
        "",
        "### Property Satisfaction by Pattern",
        "",
    ])
    
    # Build property list
    all_props = list(prop_analysis["properties"].keys())
    if all_props:
        header = "| Property |"
        divider = "|----------|"
        for pattern in ["single", "sequential", "debate", "group_chat", "concurrent"]:
            if pattern in prop_analysis["by_pattern"]:
                header += f" {pattern} |"
                divider += "--------|"
        
        lines.append(header)
        lines.append(divider)
        
        for prop_id in all_props:
            row = f"| {prop_id} |"
            for pattern in ["single", "sequential", "debate", "group_chat", "concurrent"]:
                if pattern in prop_analysis["by_pattern"]:
                    data = prop_analysis["by_pattern"][pattern].get(prop_id, {"satisfied": 0, "total": 0})
                    if data["total"] > 0:
                        rate = data["satisfied"] / data["total"] * 100
                        row += f" {rate:.0f}% |"
                    else:
                        row += " - |"
            lines.append(row)
    lines.append("")
    
    # =========================================================================
    # NEW: Actionable Recommendations
    # =========================================================================
    lines.extend([
        "---",
        "",
        "## Actionable Recommendations",
        "",
    ])
    
    # Generate recommendations based on data
    if rq1 and rq1.get("difference", 0) > 0.1:
        lines.append("1. **Investigate Multi-Agent Patterns**: Single-agent significantly outperforms multi-agent. Check dagent pattern implementations for timeouts or incorrect command sequences.")
    
    if cmd_analysis["by_type"].get("destructive", 0) > cmd_analysis["by_type"].get("constructive", 0) * 0.3:
        lines.append("2. **Reduce Destructive Commands**: High ratio of destructive commands (e.g., `no router ospf`) suggests agents are removing config before adding. Consider prompt engineering to prefer additive configuration.")
    
    if error_analysis["by_type"].get("timeout", 0) > 0:
        lines.append("3. **Address Timeouts**: Timeout errors indicate pattern execution is stalling. Review multi-agent coordination logic.")
    
    if any(rate < 0.5 for _, rate, _ in prop_analysis["hardest_properties"]):
        lines.append("4. **Focus on Low-Satisfaction Properties**: Several properties have <50% satisfaction. May need targeted testing or task refinement.")
    
    lines.extend([
        "",
        "---",
        "",
        "*Generated by analyze_multiturn_results.py (Enhanced Analysis)*",
    ])
    
    return "\n".join(lines)


def generate_charts(session_dir: Path, results: List[Dict]) -> List[Path]:
    """Generate comprehensive comparison charts."""
    charts_dir = session_dir / "charts"
    charts_dir.mkdir(exist_ok=True)
    chart_paths = []
    
    by_pattern = group_by_pattern(results)
    by_model = group_by_model(results)
    by_task = group_by_task(results)
    
    # ========== Chart 1: Agent Pattern Comparison ==========
    pattern_order = ["single", "sequential", "debate", "group_chat", "concurrent"]
    patterns_present = [p for p in pattern_order if p in by_pattern]
    
    if len(patterns_present) >= 2:
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))
        
        # Left: Score comparison
        ax = axes[0]
        scores = [compute_metrics(by_pattern[p])["avg_final_score"] for p in patterns_present]
        stds = [compute_metrics(by_pattern[p]).get("std_final_score", 0) for p in patterns_present]
        colors = [COLORS.get(p, '#888888') for p in patterns_present]
        
        x = np.arange(len(patterns_present))
        bars = ax.bar(x, scores, yerr=stds, color=colors, edgecolor='black', linewidth=0.8, capsize=4)
        for bar, hatch in zip(bars, HATCHES):
            bar.set_hatch(hatch)
        
        ax.set_ylabel('Final Score', fontweight='bold')
        ax.set_xlabel('Agent Pattern', fontweight='bold')
        ax.set_title('Score by Agent Pattern')
        ax.set_xticks(x)
        ax.set_xticklabels([p.replace('_', '\n') for p in patterns_present], fontsize=9)
        ax.set_ylim(0, 1.0)
        ax.axhline(y=0.5, color='gray', linestyle='--', alpha=0.5, label='50% threshold')
        
        for bar, val in zip(bars, scores):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.03, 
                   f'{val:.2f}', ha='center', va='bottom', fontsize=9, fontweight='bold')
        
        # Right: Turns comparison
        ax = axes[1]
        turns = [compute_metrics(by_pattern[p]).get("avg_turns", 0) for p in patterns_present]
        turns_std = [compute_metrics(by_pattern[p]).get("std_turns", 0) for p in patterns_present]
        
        bars = ax.bar(x, turns, yerr=turns_std, color=colors, edgecolor='black', linewidth=0.8, capsize=4)
        for bar, hatch in zip(bars, HATCHES):
            bar.set_hatch(hatch)
        
        ax.set_ylabel('Turns to Complete', fontweight='bold')
        ax.set_xlabel('Agent Pattern', fontweight='bold')
        ax.set_title('Efficiency: Turns Required')
        ax.set_xticks(x)
        ax.set_xticklabels([p.replace('_', '\n') for p in patterns_present], fontsize=9)
        
        for bar, val in zip(bars, turns):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1, 
                       f'{val:.0f}', ha='center', va='bottom', fontsize=9, fontweight='bold')
        
        plt.tight_layout()
        chart_path = charts_dir / "pattern_comparison.png"
        plt.savefig(chart_path, dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()
        chart_paths.append(chart_path)
    
    # ========== Chart 2: Model Comparison ==========
    if len(by_model) >= 2:
        fig, ax = plt.subplots(figsize=(8, 5))
        
        models = sorted(by_model.keys())
        scores = [compute_metrics(by_model[m])["avg_final_score"] for m in models]
        stds = [compute_metrics(by_model[m]).get("std_final_score", 0) for m in models]
        
        x = np.arange(len(models))
        model_colors = [COLORS.get('gpt', '#74AA9C') if 'gpt' in m.lower() else COLORS.get('gemini', '#4285F4') for m in models]
        
        bars = ax.bar(x, scores, yerr=stds, color=model_colors, edgecolor='black', linewidth=0.8, capsize=5)
        for bar, hatch in zip(bars, HATCHES):
            bar.set_hatch(hatch)
        
        ax.set_ylabel('Avg Final Score', fontweight='bold')
        ax.set_xlabel('Model', fontweight='bold')
        ax.set_title('Model Performance Comparison')
        ax.set_xticks(x)
        ax.set_xticklabels(models, fontsize=10, fontweight='bold')
        ax.set_ylim(0, 1.0)
        ax.axhline(y=0.5, color='gray', linestyle='--', alpha=0.5)
        
        for bar, val in zip(bars, scores):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.03, 
                   f'{val:.3f}', ha='center', va='bottom', fontsize=10, fontweight='bold')
        
        plt.tight_layout()
        chart_path = charts_dir / "model_comparison.png"
        plt.savefig(chart_path, dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()
        chart_paths.append(chart_path)
    
    # ========== Chart 3: Per-Task Breakdown ==========
    if len(by_task) >= 2:
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))
        
        tasks = sorted(by_task.keys())
        task_labels = [t.replace('_', '\n') for t in tasks]
        
        # Left: Score by task
        ax = axes[0]
        scores = [compute_metrics(by_task[t])["avg_final_score"] for t in tasks]
        stds = [compute_metrics(by_task[t]).get("std_final_score", 0) for t in tasks]
        
        x = np.arange(len(tasks))
        colors = plt.cm.Blues(np.linspace(0.4, 0.8, len(tasks)))
        
        bars = ax.bar(x, scores, yerr=stds, color=colors, edgecolor='black', linewidth=0.8, capsize=4)
        
        ax.set_ylabel('Final Score', fontweight='bold')
        ax.set_xlabel('Task', fontweight='bold')
        ax.set_title('Score by Task')
        ax.set_xticks(x)
        ax.set_xticklabels(task_labels, fontsize=9)
        ax.set_ylim(0, 1.0)
        
        for bar, val in zip(bars, scores):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.03, 
                   f'{val:.2f}', ha='center', va='bottom', fontsize=9, fontweight='bold')
        
        # Right: Completeness by task
        ax = axes[1]
        comp = [compute_metrics(by_task[t])["avg_completeness"] for t in tasks]
        rob = [compute_metrics(by_task[t])["avg_robustness"] for t in tasks]
        
        width = 0.35
        bars1 = ax.bar(x - width/2, comp, width, label='Completeness', color='#2E86AB', edgecolor='black')
        bars2 = ax.bar(x + width/2, rob, width, label='Robustness', color='#A23B72', edgecolor='black')
        
        ax.set_ylabel('Score', fontweight='bold')
        ax.set_xlabel('Task', fontweight='bold')
        ax.set_title('Completeness vs Robustness by Task')
        ax.set_xticks(x)
        ax.set_xticklabels(task_labels, fontsize=9)
        ax.set_ylim(0, 1.0)
        ax.legend(loc='upper right', frameon=True, fancybox=False, edgecolor='black')
        
        plt.tight_layout()
        chart_path = charts_dir / "task_breakdown.png"
        plt.savefig(chart_path, dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()
        chart_paths.append(chart_path)
    
    # ========== Chart 4: Pattern x Model Heatmap ==========
    if len(patterns_present) >= 2 and len(by_model) >= 2:
        fig, ax = plt.subplots(figsize=(8, 5))
        
        models = sorted(by_model.keys())
        
        # Build score matrix
        matrix = np.zeros((len(patterns_present), len(models)))
        for i, pattern in enumerate(patterns_present):
            pattern_results = by_pattern[pattern]
            for j, model in enumerate(models):
                matching = [r for r in pattern_results if normalize_model_name(r) == model]
                if matching:
                    matrix[i, j] = compute_metrics(matching)["avg_final_score"]
        
        im = ax.imshow(matrix, cmap='RdYlGn', aspect='auto', vmin=0, vmax=1)
        
        ax.set_xticks(np.arange(len(models)))
        ax.set_yticks(np.arange(len(patterns_present)))
        ax.set_xticklabels(models, fontsize=10, fontweight='bold')
        ax.set_yticklabels([p.replace('_', '\n') for p in patterns_present], fontsize=10)
        ax.set_xlabel('Model', fontweight='bold')
        ax.set_ylabel('Pattern', fontweight='bold')
        ax.set_title('Score: Pattern × Model')
        
        # Add text annotations
        for i in range(len(patterns_present)):
            for j in range(len(models)):
                val = matrix[i, j]
                color = 'white' if val < 0.3 or val > 0.7 else 'black'
                ax.text(j, i, f'{val:.2f}', ha='center', va='center', 
                       fontsize=11, fontweight='bold', color=color)
        
        cbar = plt.colorbar(im, ax=ax, shrink=0.8)
        cbar.set_label('Final Score', fontweight='bold')
        
        plt.tight_layout()
        chart_path = charts_dir / "pattern_model_heatmap.png"
        plt.savefig(chart_path, dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()
        chart_paths.append(chart_path)
    
    # ========== NEW Chart 5: Error Rate by Pattern ==========
    error_analysis = analyze_errors(results)
    if len(patterns_present) >= 2:
        fig, ax = plt.subplots(figsize=(8, 5))
        
        error_rates = [error_analysis["error_rate_by_pattern"].get(p, 0) * 100 for p in patterns_present]
        colors = [COLORS.get(p, '#888888') for p in patterns_present]
        
        x = np.arange(len(patterns_present))
        bars = ax.bar(x, error_rates, color=colors, edgecolor='black', linewidth=0.8)
        for bar, hatch in zip(bars, HATCHES):
            bar.set_hatch(hatch)
        
        ax.set_ylabel('Error Rate (%)', fontweight='bold')
        ax.set_xlabel('Agent Pattern', fontweight='bold')
        ax.set_title('Error Rate by Agent Pattern')
        ax.set_xticks(x)
        ax.set_xticklabels([p.replace('_', '\n') for p in patterns_present], fontsize=9)
        ax.set_ylim(0, 100)
        
        for bar, val in zip(bars, error_rates):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2, 
                   f'{val:.0f}%', ha='center', va='bottom', fontsize=9, fontweight='bold')
        
        plt.tight_layout()
        chart_path = charts_dir / "error_rates.png"
        plt.savefig(chart_path, dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()
        chart_paths.append(chart_path)
    
    # ========== NEW Chart 6: Command Type Distribution ==========
    cmd_analysis = analyze_execution_logs(results)
    if cmd_analysis.get("total_commands", 0) > 0 and len(patterns_present) >= 2:
        fig, ax = plt.subplots(figsize=(10, 5))
        
        cmd_types = ["constructive", "diagnostic", "destructive"]
        x = np.arange(len(patterns_present))
        width = 0.25
        
        type_colors = {'constructive': '#2E86AB', 'diagnostic': '#74AA9C', 'destructive': '#C73E1D'}
        
        for i, cmd_type in enumerate(cmd_types):
            counts = [cmd_analysis["by_pattern"].get(p, {}).get(cmd_type, 0) for p in patterns_present]
            bars = ax.bar(x + i * width, counts, width, label=cmd_type.capitalize(), 
                         color=type_colors[cmd_type], edgecolor='black', linewidth=0.5)
        
        ax.set_ylabel('Command Count', fontweight='bold')
        ax.set_xlabel('Agent Pattern', fontweight='bold')
        ax.set_title('Command Type Distribution by Pattern')
        ax.set_xticks(x + width)
        ax.set_xticklabels([p.replace('_', '\n') for p in patterns_present], fontsize=9)
        ax.legend(loc='upper right', frameon=True, fancybox=False, edgecolor='black')
        
        plt.tight_layout()
        chart_path = charts_dir / "command_distribution.png"
        plt.savefig(chart_path, dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()
        chart_paths.append(chart_path)
    
    # ========== NEW Chart 7: Property Satisfaction Heatmap ==========
    prop_analysis = analyze_property_results(results)
    all_props = list(prop_analysis["properties"].keys())
    
    if len(all_props) > 0 and len(patterns_present) >= 2:
        fig, ax = plt.subplots(figsize=(10, max(4, len(all_props) * 0.4)))
        
        # Build satisfaction matrix
        matrix = np.zeros((len(all_props), len(patterns_present)))
        for i, prop_id in enumerate(all_props):
            for j, pattern in enumerate(patterns_present):
                data = prop_analysis["by_pattern"].get(pattern, {}).get(prop_id, {"satisfied": 0, "total": 0})
                if data["total"] > 0:
                    matrix[i, j] = data["satisfied"] / data["total"]
        
        im = ax.imshow(matrix, cmap='RdYlGn', aspect='auto', vmin=0, vmax=1)
        
        ax.set_xticks(np.arange(len(patterns_present)))
        ax.set_yticks(np.arange(len(all_props)))
        ax.set_xticklabels([p.replace('_', '\n') for p in patterns_present], fontsize=9)
        ax.set_yticklabels(all_props, fontsize=8)
        ax.set_xlabel('Pattern', fontweight='bold')
        ax.set_ylabel('Property', fontweight='bold')
        ax.set_title('Property Satisfaction Rate: Pattern × Property')
        
        # Add text annotations
        for i in range(len(all_props)):
            for j in range(len(patterns_present)):
                val = matrix[i, j]
                color = 'white' if val < 0.3 or val > 0.7 else 'black'
                ax.text(j, i, f'{val:.0%}', ha='center', va='center', 
                       fontsize=8, fontweight='bold', color=color)
        
        cbar = plt.colorbar(im, ax=ax, shrink=0.8)
        cbar.set_label('Satisfaction Rate', fontweight='bold')
        
        plt.tight_layout()
        chart_path = charts_dir / "property_heatmap.png"
        plt.savefig(chart_path, dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()
        chart_paths.append(chart_path)
    
    # ========== NEW Chart 8: Turns vs Score Scatter ==========
    turns_data = []
    scores_data = []
    pattern_data = []
    
    for result in results:
        turns = result.get("metrics", {}).get("turns_to_complete")
        score = result.get("scoring", {}).get("final_score", 0)
        mode, structure = extract_agent_config(result)
        pattern = "single" if mode == "single" else structure
        
        if turns and turns > 0:
            turns_data.append(turns)
            scores_data.append(score)
            pattern_data.append(pattern)
    
    if turns_data and len(set(pattern_data)) >= 2:
        fig, ax = plt.subplots(figsize=(8, 6))
        
        for pattern in patterns_present:
            idx = [i for i, p in enumerate(pattern_data) if p == pattern]
            if idx:
                t = [turns_data[i] for i in idx]
                s = [scores_data[i] for i in idx]
                ax.scatter(t, s, c=COLORS.get(pattern, '#888888'), 
                          label=pattern.replace('_', ' '), s=80, alpha=0.7, edgecolors='black')
        
        ax.set_xlabel('Turns to Complete', fontweight='bold')
        ax.set_ylabel('Final Score', fontweight='bold')
        ax.set_title('Turns vs Score by Pattern')
        ax.set_ylim(-0.05, 1.05)
        ax.axhline(y=0.5, color='gray', linestyle='--', alpha=0.5)
        ax.legend(loc='upper right', frameon=True, fancybox=False, edgecolor='black')
        
        plt.tight_layout()
        chart_path = charts_dir / "turns_vs_score.png"
        plt.savefig(chart_path, dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()
        chart_paths.append(chart_path)
    
    # ========== NEW Chart 9: Exploration Patterns ==========
    exploration = analyze_exploration_patterns(results)
    if exploration["by_pattern"] and len(patterns_present) >= 2:
        fig, ax = plt.subplots(figsize=(10, 5))
        
        x = np.arange(len(patterns_present))
        width = 0.2
        
        metrics = [
            ("exploration_rate", "Exploration (Diagnostic)", "#74AA9C"),
            ("construction_rate", "Construction", "#2E86AB"),
            ("destruction_rate", "Destruction", "#C73E1D"),
        ]
        
        for i, (metric_key, label, color) in enumerate(metrics):
            values = [exploration["by_pattern"].get(p, {}).get(metric_key, 0) * 100 for p in patterns_present]
            ax.bar(x + i * width, values, width, label=label, color=color, edgecolor='black', linewidth=0.5)
        
        ax.set_ylabel('Rate (%)', fontweight='bold')
        ax.set_xlabel('Agent Pattern', fontweight='bold')
        ax.set_title('Command Strategy by Pattern (RQ4: Exploration Patterns)')
        ax.set_xticks(x + width)
        ax.set_xticklabels([p.replace('_', '\n') for p in patterns_present], fontsize=9)
        ax.legend(loc='upper right', frameon=True, fancybox=False, edgecolor='black')
        ax.set_ylim(0, 100)
        
        plt.tight_layout()
        chart_path = charts_dir / "exploration_patterns.png"
        plt.savefig(chart_path, dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()
        chart_paths.append(chart_path)
    
    return chart_paths


def main():
    if len(sys.argv) < 2:
        print("Usage: poetry run python scripts/analyze_multiturn_results.py <session_dir>")
        sys.exit(1)
    
    session_dir = Path(sys.argv[1])
    
    if not session_dir.exists():
        print(f"Error: Session directory not found: {session_dir}")
        sys.exit(1)
    
    print(f"Analyzing multi-turn results from: {session_dir}")
    print("=" * 60)
    
    results = load_session_results(session_dir)
    print(f"Loaded {len(results)} results")
    
    if not results:
        print("No results found!")
        sys.exit(1)
    
    # Print quick summary
    by_pattern = group_by_pattern(results)
    print(f"Patterns found: {list(by_pattern.keys())}")
    by_model = group_by_model(results)
    print(f"Models found: {list(by_model.keys())}")
    
    # Generate report
    report = generate_report(session_dir, results)
    report_path = session_dir / "analysis_report.md"
    with open(report_path, "w") as f:
        f.write(report)
    print(f"\nReport saved to: {report_path}")
    
    # Generate charts
    try:
        chart_paths = generate_charts(session_dir, results)
        print(f"Generated {len(chart_paths)} charts:")
        for cp in chart_paths:
            print(f"  - {cp.name}")
    except Exception as e:
        print(f"Warning: Chart generation failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("=" * 60)
    print("Analysis complete!")


if __name__ == "__main__":
    main()
