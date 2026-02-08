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
    'gpt': '#74AA9C',          # Teal
    'gemini': '#4285F4',       # Google Blue
}

MARKERS = {
    'single': 'o',       # Circle
    'sequential': 's',   # Square
    'debate': '^',       # Triangle up
    'group_chat': 'D',   # Diamond
    'concurrent': 'v',   # Triangle down
}

HATCHES = ['///', '\\\\\\\\\\\\', 'xxx', '...', '+++', 'ooo']


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
    
    # Remove provider prefix if present
    for provider in ["ollama:", "openai:", "gemini:"]:
        if model.lower().startswith(provider):
            model = model[len(provider):]
            break
            
    # Simplify long model names by removing date suffixes
    model = model.replace("-2025-08-07", "").replace("2025-08-07", "")
    
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


# Task metadata for cross-task analysis
TASK_METADATA = {
    "ccna_rip_routing_basic": {
        "difficulty": "basic",
        "type": "configuration",
        "protocol": "RIP",
        "complexity_score": 1,
        "display_name": "CCNA RIP Routing",
        # Research-driven metrics (from "Towards a Science of Scaling Agent Systems")
        "sequential_depth": 2,  # Set IP → Enable RIP
        "parallelizable_breadth": 4,  # 4 independent routers can be configured in parallel
        "tool_reasoning_ratio": "low"  # Reasoning-heavy task
    },
    "ccnp_multiarea_ospf_intermediate": {
        "difficulty": "intermediate",
        "type": "configuration",
        "protocol": "OSPF",
        "complexity_score": 2,
        "display_name": "CCNP Multi-Area OSPF",
        "sequential_depth": 3,  # Set IP → OSPF process → Area configuration
        "parallelizable_breadth": 3,  # 3 areas can be configured in parallel
        "tool_reasoning_ratio": "medium"
    },
    "ccie_bgp_dual_homing_expert": {
        "difficulty": "expert",
        "type": "configuration",
        "protocol": "BGP",
        "complexity_score": 3,
        "display_name": "CCIE BGP Dual-Homing",
        "sequential_depth": 5,  # IP → EBGP → Verify adjacency → Route-map → Policy verification
        "parallelizable_breadth": 2,  # 2 ISP connections with some parallel config potential
        "tool_reasoning_ratio": "medium"
    },
    "troubleshoot_ospf_adjacency_issue": {
        "difficulty": "intermediate",
        "type": "troubleshooting",
        "protocol": "OSPF",
        "complexity_score": 2,
        "display_name": "Troubleshoot OSPF Adjacency",
        "sequential_depth": 6,  # Diagnose → Identify problem → Apply fix → Verify → Re-diagnose if needed
        "parallelizable_breadth": 1,  # Troubleshooting must be sequential (no parallelism)
        "tool_reasoning_ratio": "high"  # Heavy diagnostic reasoning required
    },
    "troubleshoot_bgp_route_filtering": {
        "difficulty": "expert",
        "type": "troubleshooting",
        "protocol": "BGP",
        "complexity_score": 3,
        "display_name": "Troubleshoot BGP Route Filtering",
        "sequential_depth": 7,  # Deep diagnostic chain: check routes → analyze policy → test filters → verify
        "parallelizable_breadth": 1,  # Must be sequential
        "tool_reasoning_ratio": "high"  # Very reasoning-heavy
    }
}


def filter_valid_results(results: List[Dict]) -> Tuple[List[Dict], int]:
    """Filter out results where syntactic_validity == 0 (timeout/error cases).
    
    Returns:
        (valid_results, filtered_count)
    """
    valid = []
    filtered = 0
    
    for r in results:
        syntactic_validity = r.get("scoring", {}).get("syntactic_validity", 1.0)
        if syntactic_validity == 0.0:
            filtered += 1
        else:
            valid.append(r)
    
    return valid, filtered


def compute_metrics(results: List[Dict]) -> Dict[str, Any]:
    """Compute aggregate metrics from results."""
    if not results:
        return {"count": 0, "valid_count": 0, "filtered_count": 0}
    
    # Filter invalid results (syntactic_validity == 0 means timeout/error)
    valid_results, filtered_count = filter_valid_results(results)
    
    if not valid_results:
        return {
            "count": len(results),
            "valid_count": 0,
            "filtered_count": filtered_count
        }
    
    metrics = {
        "count": len(results),
        "valid_count": len(valid_results),
        "filtered_count": filtered_count,
        "success_rate": sum(1 for r in valid_results if r.get("success")) / len(valid_results),
        "avg_final_score": np.mean([r.get("scoring", {}).get("final_score", 0) for r in valid_results]),
        "std_final_score": np.std([r.get("scoring", {}).get("final_score", 0) for r in valid_results]),
        "avg_completeness": np.mean([r.get("scoring", {}).get("completeness", 0) for r in valid_results]),
        "avg_robustness": np.mean([r.get("scoring", {}).get("robustness", 0) for r in valid_results]),
    }
    
    # Multi-turn specific
    turns = [r.get("metrics", {}).get("turns_to_complete") for r in valid_results]
    turns = [t for t in turns if t is not None and t > 0]
    if turns:
        metrics["avg_turns"] = np.mean(turns)
        metrics["std_turns"] = np.std(turns)
    
    times = [r.get("metrics", {}).get("time_to_complete") for r in valid_results]
    times = [t for t in times if t is not None and t > 0]
    if times:
        metrics["avg_time"] = np.mean(times)
        metrics["std_time"] = np.std(times)
        
    # NEW: Token Usage Metrics
    total_tokens = []
    for r in valid_results:
        usage = r.get("metrics", {}).get("token_usage", {})
        if usage and "total_tokens" in usage:
            total_tokens.append(usage["total_tokens"])
    
    if total_tokens:
        metrics["avg_tokens"] = np.mean(total_tokens)
        metrics["std_tokens"] = np.std(total_tokens)
        metrics["total_tokens_consumed"] = sum(total_tokens)
        
        # Estimated cost (blended rate placeholder: $5/1M tokens)
        metrics["est_cost"] = (sum(total_tokens) / 1_000_000) * 5.0
    
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
        turns = [r.get("metrics", {}).get("turns_to_complete") for r in pattern_results]
        times = [r.get("metrics", {}).get("time_to_complete") for r in pattern_results]
        
        total_cmds = sum(len(parse_execution_log(r)) for r in pattern_results)
        
        # Filter None values for calculations
        valid_turns = [t for t in turns if t is not None and t > 0]
        valid_times = [t for t in times if t is not None and t > 0]
        
        total_turns = sum(valid_turns)
        
        if total_turns > 0:
            metrics["rq3_parallelism"][pattern] = {
                "parallelism_factor": total_cmds / total_turns,
                "avg_time": np.mean(valid_times) if valid_times else 0,
                "avg_turns": np.mean(valid_turns) if valid_turns else 0,
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



# =============================================================================
# NEW: Cross-Task Analysis
# =============================================================================

def analyze_by_task_type(results: List[Dict]) -> Dict[str, Any]:
    """Analyze performance by task characteristics (difficulty, type, protocol)."""
    analysis = {
        "by_difficulty": defaultdict(list),
        "by_type": defaultdict(list),
        "by_protocol": defaultdict(list),
        "by_task": defaultdict(list),
    }
    
    for result in results:
        task_id = result.get("task_id", "unknown")
        metadata = TASK_METADATA.get(task_id, {})
        
        difficulty = metadata.get("difficulty", "unknown")
        task_type = metadata.get("type", "unknown")
        protocol = metadata.get("protocol", "unknown")
        
        analysis["by_difficulty"][difficulty].append(result)
        analysis["by_type"][task_type].append(result)
        analysis["by_protocol"][protocol].append(result)
        analysis["by_task"][task_id].append(result)
    
    # Compute metrics for each grouping
    metrics_summary = {}
    for grouping, group_results in analysis.items():
        metrics_summary[grouping] = {}
        for group_key, group_data in group_results.items():
            metrics_summary[grouping][group_key] = compute_metrics(group_data)
    
    return metrics_summary


def analyze_failure_modes(results: List[Dict]) -> Dict[str, Any]:
    """Detailed failure analysis per task type."""
    analysis = {
        "by_task": defaultdict(lambda: {
            "total": 0,
            "failed": 0,
            "timeout": 0,
            "syntax_error": 0,
            "property_failure": 0,
            "zero_validity": 0,
            "error_details": defaultdict(int)
        })
    }
    
    for result in results:
        task_id = result.get("task_id", "unknown")
        task_stats = analysis["by_task"][task_id]
        
        task_stats["total"] += 1
        
        # Check for zero validity (timeout/error)
        syntactic_validity = result.get("scoring", {}).get("syntactic_validity", 1.0)
        if syntactic_validity == 0.0:
            task_stats["zero_validity"] += 1
        
        # Check success
        if not result.get("success", False):
            task_stats["failed"] += 1
        
        # Categorize errors
        errors = result.get("errors", [])
        for error in errors:
            error_cat = categorize_error(error)
            task_stats["error_details"][error_cat] += 1
            
            if error_cat == "timeout":
                task_stats["timeout"] += 1
            elif error_cat == "syntax_error":
                task_stats["syntax_error"] += 1
            elif error_cat == "property_failure":
                task_stats["property_failure"] += 1
    
    # Calculate failure rates
    for task_id, stats in analysis["by_task"].items():
        total = stats["total"]
        if total > 0:
            stats["failure_rate"] = stats["failed"] / total
            stats["zero_validity_rate"] = stats["zero_validity"] / total
    
    return analysis


def analyze_pattern_task_fit(results: List[Dict]) -> Dict[str, Any]:
    """Analyze which patterns work best for which task types."""
    analysis = {
        "pattern_x_task": {},
        "pattern_x_difficulty": {},
        "pattern_x_type": {},
        "best_pattern_by_task": {},
    }
    
    # Build pattern × task matrix
    by_task = group_by_task(results)
    by_pattern = group_by_pattern(results)
    
    pattern_order = ["single", "sequential", "debate", "group_chat", "concurrent"]
    
    for task_id, task_results in by_task.items():
        analysis["pattern_x_task"][task_id] = {}
        
        best_score = -1
        best_pattern = None
        
        for pattern in pattern_order:
            pattern_task_results = [r for r in task_results 
                                   if extract_agent_config(r)[0] == "single" and pattern == "single"
                                   or extract_agent_config(r)[1] == pattern and pattern != "single"]
            
            if pattern_task_results:
                metrics = compute_metrics(pattern_task_results)
                analysis["pattern_x_task"][task_id][pattern] = metrics
                
                avg_score = metrics.get("avg_final_score", 0)
                if avg_score > best_score:
                    best_score = avg_score
                    best_pattern = pattern
            else:
                analysis["pattern_x_task"][task_id][pattern] = None
        
        analysis["best_pattern_by_task"][task_id] = {
            "pattern": best_pattern,
            "score": best_score
        }
    
    # Pattern × difficulty
    for difficulty in ["basic", "intermediate", "expert"]:
        analysis["pattern_x_difficulty"][difficulty] = {}
        difficulty_results = [r for r in results 
                            if TASK_METADATA.get(r.get("task_id", ""), {}).get("difficulty") == difficulty]
        
        for pattern in pattern_order:
            pattern_diff_results = [r for r in difficulty_results
                                   if (extract_agent_config(r)[0] == "single" and pattern == "single")
                                   or (extract_agent_config(r)[1] == pattern and pattern != "single")]
            if pattern_diff_results:
                analysis["pattern_x_difficulty"][difficulty][pattern] = compute_metrics(pattern_diff_results)
    
    # Pattern × type (configuration vs troubleshooting)
    for task_type in ["configuration", "troubleshooting"]:
        analysis["pattern_x_type"][task_type] = {}
        type_results = [r for r in results 
                       if TASK_METADATA.get(r.get("task_id", ""), {}).get("type") == task_type]
        
        for pattern in pattern_order:
            pattern_type_results = [r for r in type_results
                                   if (extract_agent_config(r)[0] == "single" and pattern == "single")
                                   or (extract_agent_config(r)[1] == pattern and pattern != "single")]
            if pattern_type_results:
                analysis["pattern_x_type"][task_type][pattern] = compute_metrics(pattern_type_results)
    
    return analysis


def compute_effect_size(group1: List[float], group2: List[float]) -> float:
    """Calculate Cohen's d effect size."""
    if not group1 or not group2:
        return 0.0
    
    mean1 = np.mean(group1)
    mean2 = np.mean(group2)
    std1 = np.std(group1, ddof=1)
    std2 = np.std(group2, ddof=1)
    n1 = len(group1)
    n2 = len(group2)
    
    # Pooled standard deviation
    pooled_std = np.sqrt(((n1 - 1) * std1**2 + (n2 - 1) * std2**2) / (n1 + n2 - 2))
    
    if pooled_std == 0:
        return 0.0
    
    return (mean1 - mean2) / pooled_std


def bootstrap_confidence_interval(data: List[float], n_bootstrap: int = 1000, confidence: float = 0.95) -> Tuple[float, float]:
    """Calculate confidence interval via bootstrap."""
    if not data:
        return (0.0, 0.0)
    
    data_array = np.array(data)
    bootstrapped_means = []
    
    for _ in range(n_bootstrap):
        sample = np.random.choice(data_array, size=len(data_array), replace=True)
        bootstrapped_means.append(np.mean(sample))
    
    alpha = 1 - confidence
    lower_percentile = (alpha / 2) * 100
    upper_percentile = (1 - alpha / 2) * 100
    
    ci_lower = np.percentile(bootstrapped_means, lower_percentile)
    ci_upper = np.percentile(bootstrapped_means, upper_percentile)
    
    return (ci_lower, ci_upper)


def format_with_ci(mean: float, ci_lower: float, ci_upper: float) -> str:
    """Format value with confidence interval."""
    return f"{mean:.3f} [{ci_lower:.3f}, {ci_upper:.3f}]"


def calculate_context_loss_rate(results: List[Dict]) -> Dict[str, Any]:
    """
    Analyze execution logs to measure information fragmentation (context loss).
    
    Detects three types of context loss:
    1. Redundant queries: Same show/diagnostic command executed multiple times
    2. Conflicting actions: Commands that undo or contradict previous work
    3. Missing dependencies: Configuration attempted before prerequisites exist
    
    Returns analysis by pattern with context loss rates.
    """
    analysis = {
        "by_pattern": {},
        "overall": {
            "redundant_queries": 0,
            "conflicting_actions": 0,
            "missing_dependencies": 0,
            "total_actions": 0
        }
    }
    
    pattern_order = ["single", "sequential", "debate", "group_chat", "concurrent"]
    by_pattern = group_by_pattern(results)
    
    for pattern in pattern_order:
        pattern_results = by_pattern.get(pattern, [])
        if not pattern_results:
            continue
            
        pattern_stats = {
            "redundant_queries": 0,
            "conflicting_actions": 0,
            "missing_dependencies": 0,
            "total_actions": 0,
            "runs_analyzed": 0,
            "context_loss_rate": 0.0
        }
        
        for result in pattern_results:
            execution_log = result.get("execution_log", [])
            if not execution_log:
                continue
                
            pattern_stats["runs_analyzed"] += 1
            pattern_stats["total_actions"] += len(execution_log)
            
            # Track commands by node and type
            command_history = {}  # {node: {command_type: [indexes]}}
            
            for idx, cmd in enumerate(execution_log):
                if not cmd or "|" not in cmd:
                    continue
                    
                try:
                    node, command = cmd.split("|", 1)
                    node = node.strip()
                    command = command.strip()
                    
                    if node not in command_history:
                        command_history[node] = {}
                    
                    # Detect redundant queries
                    if is_diagnostic_command(command):
                        cmd_type = get_command_signature(command)
                        
                        if cmd_type not in command_history[node]:
                            command_history[node][cmd_type] = []
                        command_history[node][cmd_type].append(idx)
                        
                        # If same diagnostic appears 3+ times, it's redundant
                        if len(command_history[node][cmd_type]) >= 3:
                            pattern_stats["redundant_queries"] += 1
                    
                    # Detect conflicting actions
                    if is_config_command(command):
                        # Check for "no" commands that undo previous config
                        if "no router" in command or "no network" in command or "shutdown" in command:
                            # Look back to see if we configured this before
                            positive_cmd = command.replace("no ", "").replace("shutdown", "no shutdown")
                            for prev_idx in range(idx):
                                if prev_idx < len(execution_log):
                                    prev_cmd = execution_log[prev_idx]
                                    if node in prev_cmd and positive_cmd in prev_cmd:
                                        pattern_stats["conflicting_actions"] += 1
                                        break
      
                    # Detect missing dependencies
                    # Example: configuring RIP before IP addresses are set
                    if "router rip" in command or "router ospf" in command or "router bgp" in command:
                        # Check if node has IP configured
                        has_ip = False
                        for prev_idx in range(idx):
                            if prev_idx < len(execution_log):
                                prev_cmd = execution_log[prev_idx]
                                if node in prev_cmd and "ip addr add" in prev_cmd:
                                    has_ip = True
                                    break
                        if not has_ip:
                            pattern_stats["missing_dependencies"] += 1
                            
                except Exception as e:
                    # Skip malformed commands
                    continue
        
        # Calculate context loss rate
        total_errors = (pattern_stats["redundant_queries"] + 
                       pattern_stats["conflicting_actions"] + 
                       pattern_stats["missing_dependencies"])
        
        if pattern_stats["total_actions"] > 0:
            pattern_stats["context_loss_rate"] = total_errors / pattern_stats["total_actions"]
        
        analysis["by_pattern"][pattern] = pattern_stats
        
        # Update overall stats
        analysis["overall"]["redundant_queries"] += pattern_stats["redundant_queries"]
        analysis["overall"]["conflicting_actions"] += pattern_stats["conflicting_actions"]
        analysis["overall"]["missing_dependencies"] += pattern_stats["missing_dependencies"]
        analysis["overall"]["total_actions"] += pattern_stats["total_actions"]
    
    return analysis


def is_diagnostic_command(cmd: str) -> bool:
    """Check if command is diagnostic/read-only."""
    diagnostic_patterns = ["show", "ping", "traceroute", "ip route get", "ip addr show"]
    return any(pattern in cmd.lower() for pattern in diagnostic_patterns)


def is_config_command(cmd: str) -> bool:
    """Check if command is configuration (write)."""
    config_patterns = ["vtysh -c", "ip addr add", "ip link set", "router ", "network "]
    return any(pattern in cmd.lower() for pattern in config_patterns)


def get_command_signature(cmd: str) -> str:
    """Extract command signature for deduplication."""
    # Remove variable parts like timestamps, but keep structure
    cmd_lower = cmd.lower()
    if "show ip route" in cmd_lower:
        return "show_ip_route"
    elif "show ip ospf" in cmd_lower:
        return "show_ip_ospf"
    elif "show ip rip" in cmd_lower:
        return "show_ip_rip"
    elif "show ip bgp" in cmd_lower:
        return "show_ip_bgp"
    elif "ping" in cmd_lower:
        # Extract destination IP/host
        parts = cmd.split()
        for i, part in enumerate(parts):
            if part == "ping" and i+1 < len(parts):
                return f"ping_{parts[i+1]}"
        return "ping_unknown"
    else:
        return "other_diagnostic"


def analyze_sequential_depth_correlation(results: List[Dict]) -> Dict[str, Any]:
    """
    Analyze correlation between task sequential depth and pattern performance.
    
    Returns depth-stratified performance metrics for each pattern.
    """
    analysis = {
        "by_depth": {},  # {depth: {pattern: metrics}}
        "correlation": {},  # {pattern: correlation_coefficient}
    }
    
    pattern_order = ["single", "sequential", "debate", "group_chat", "concurrent"]
    
    # Group results by sequential depth
    for task_id, metadata in TASK_METADATA.items():
        depth = metadata.get("sequential_depth", 0)
        if depth not in analysis["by_depth"]:
            analysis["by_depth"][depth] = {}
        
        task_results = [r for r in results if r.get("task_id") == task_id]
        
        for pattern in pattern_order:
            pattern_results = [r for r in task_results
                             if (extract_agent_config(r)[0] == "single" and pattern == "single")
                             or (extract_agent_config(r)[1] == pattern and pattern != "single")]
            
            if pattern_results:
                metrics = compute_metrics(pattern_results)
                if pattern not in analysis["by_depth"][depth]:
                    analysis["by_depth"][depth] = {}
                analysis["by_depth"][depth][pattern] = metrics
    
    # Calculate correlation for each pattern
    for pattern in pattern_order:
        depths = []
        success_rates = []
        
        for depth, pattern_metrics in analysis["by_depth"].items():
            if pattern in pattern_metrics:
                metrics = pattern_metrics[pattern]
                if metrics.get("valid_count", 0) > 0:
                    depths.append(depth)
                    success_rates.append(metrics.get("success_rate", 0))
        
        if len(depths) >= 2:
            # Calculate Pearson correlation
            correlation = np.corrcoef(depths, success_rates)[0, 1] if len(depths) > 1 else 0
            analysis["correlation"][pattern] = correlation
        else:
            analysis["correlation"][pattern] = None
    
    return analysis


def generate_task_property_matrix_data(results: List[Dict]) -> Dict[str, Any]:
    """
    Generate data for task property matrix visualization.
    
    Returns task positioning by parallelizable breadth and sequential depth,
    with best-performing pattern for each task.
    """
    matrix_data = {
        "tasks": [],  # List of {task, breadth, depth, best_pattern, max_score}
        "pattern_regions": {}  # {pattern: [(breadth, depth)]} for region highlighting
    }
    
    pattern_order = ["single", "sequential", "debate", "group_chat", "concurrent"]
    
    for task_id, metadata in TASK_METADATA.items():
        depth = metadata.get("sequential_depth", 0)
        breadth = metadata.get("parallelizable_breadth", 0)
        display_name = metadata.get("display_name", task_id)
        
        # Find best pattern for this task
        task_results = [r for r in results if r.get("task_id") == task_id]
        best_pattern = None
        max_score = -1
        
        for pattern in pattern_order:
            pattern_results = [r for r in task_results
                             if (extract_agent_config(r)[0] == "single" and pattern == "single")
                             or (extract_agent_config(r)[1] == pattern and pattern != "single")]
            
            if pattern_results:
                metrics = compute_metrics(pattern_results)
                avg_score = metrics.get("avg_final_score", 0)
                if avg_score > max_score:
                    max_score = avg_score
                    best_pattern = pattern
        
        if best_pattern:
            task_entry = {
                "task_id": task_id,
                "display_name": display_name,
                "breadth": breadth,
                "depth": depth,
                "best_pattern": best_pattern,
                "max_score": max_score
            }
            matrix_data["tasks"].append(task_entry)
            
            # Add to pattern region
            if best_pattern not in matrix_data["pattern_regions"]:
                matrix_data["pattern_regions"][best_pattern] = []
            matrix_data["pattern_regions"][best_pattern].append((breadth, depth))
    
    return matrix_data

def compute_academic_metrics(results: List[Dict]) -> Dict[str, Any]:
    """Compute rigorous academic metrics with effect sizes and CIs."""
    metrics = {}
    
    by_pattern = group_by_pattern(results)
    
    # Single vs Multi comparison with effect size
    single_scores = [r.get("scoring", {}).get("final_score", 0) 
                    for r in by_pattern.get("single", [])]
    multi_scores = []
    for pattern in ["sequential", "debate", "group_chat", "concurrent"]:
        multi_scores.extend([r.get("scoring", {}).get("final_score", 0) 
                            for r in by_pattern.get(pattern, [])])
    
    if single_scores and multi_scores:
        # Filter valid results
        single_valid = [s for s in single_scores if s > 0 or s == 0]  # Keep all
        multi_valid = [s for s in multi_scores if s > 0 or s == 0]
        
        effect_size = compute_effect_size(single_valid, multi_valid)
        single_ci = bootstrap_confidence_interval(single_valid)
        multi_ci = bootstrap_confidence_interval(multi_valid)
        
        metrics["single_vs_multi"] = {
            "single_mean": np.mean(single_valid),
            "single_ci": single_ci,
            "multi_mean": np.mean(multi_valid),
            "multi_ci": multi_ci,
            "effect_size": effect_size,
            "interpretation": "large" if abs(effect_size) > 0.8 else "medium" if abs(effect_size) > 0.5 else "small"
        }
    
    # Pattern comparisons with CIs
    metrics["patterns"] = {}
    for pattern, pattern_results in by_pattern.items():
        scores = [r.get("scoring", {}).get("final_score", 0) for r in pattern_results]
        valid_scores = [s for s in scores if isinstance(s, (int, float))]
        
        if valid_scores:
            ci = bootstrap_confidence_interval(valid_scores)
            metrics["patterns"][pattern] = {
                "mean": np.mean(valid_scores),
                "ci": ci,
                "n": len(valid_scores)
            }
    
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
    
    # Data Quality Summary
    overall = compute_metrics(results)
    lines.extend([
        "## Data Quality Summary",
        "",
        "> [!NOTE]",
        "> **Error Filtering**: Results with `syntactic_validity == 0.0` are excluded from averages.",
        "> These indicate timeout/execution failures where no commands were executed.",
        "",
        "| Metric | Count |",
        "|--------|-------|",
        f"| Total Runs | {overall.get('count', 0)} |",
        f"| Valid Runs | {overall.get('valid_count', 0)} |",
        f"| Filtered (Errors) | {overall.get('filtered_count', 0)} |",
        f"| Error Rate | {overall.get('filtered_count', 0) / max(overall.get('count', 1), 1) * 100:.1f}% |",
        "",
    ])
    
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
    if "avg_tokens" in overall:
        lines.append(f"| Avg Tokens | {overall['avg_tokens']:.0f} ± {overall.get('std_tokens', 0):.0f} |")
        lines.append(f"| Total Tokens | {overall['total_tokens_consumed']:,} |")
        lines.append(f"| Est. Cost | ${overall['est_cost']:.2f} |")
    lines.append("")
    
    # Pattern comparison (main focus!)
    by_pattern = group_by_pattern(results)
    lines.extend([
        "---",
        "",
        "## Agent Pattern Comparison",
        "",
        "| Pattern | Runs | Success | Score | Completeness | Robustness | Turns | Time | Tokens |",
        "|---------|------|---------|-------|--------------|------------|-------|------|--------|",
    ])
    
    pattern_order = ["single", "sequential", "debate", "group_chat", "concurrent"]
    for pattern in pattern_order:
        if pattern in by_pattern:
            m = compute_metrics(by_pattern[pattern])
            turns_str = f"{m.get('avg_turns', 0):.1f}" if "avg_turns" in m else "-"
            time_str = f"{m.get('avg_time', 0):.0f}s" if "avg_time" in m else "-"
            tokens_str = f"{m.get('avg_tokens', 0):.0f}" if "avg_tokens" in m else "-"
            lines.append(
                f"| **{pattern}** | {m['count']} | {m['success_rate']*100:.0f}% | "
                f"{m['avg_final_score']:.3f} | {m['avg_completeness']:.3f} | "
                f"{m['avg_robustness']:.3f} | {turns_str} | {time_str} | {tokens_str} |"
            )
    lines.append("")
    
    # Model comparison  
    by_model = group_by_model(results)
    lines.extend([
        "---",
        "",
        "## Model Comparison",
        "",
        "| Model | Runs | Success | Score | Completeness | Turns | Tokens |",
        "|-------|------|---------|-------|--------------|-------|--------|",
    ])
    for model, model_results in sorted(by_model.items()):
        m = compute_metrics(model_results)
        turns_str = f"{m.get('avg_turns', 0):.1f}" if "avg_turns" in m else "-"
        tokens_str = f"{m.get('avg_tokens', 0):.0f}" if "avg_tokens" in m else "-"
        lines.append(
            f"| **{model}** | {m['count']} | {m['success_rate']*100:.0f}% | "
            f"{m['avg_final_score']:.3f} | {m['avg_completeness']:.3f} | {turns_str} | {tokens_str} |"
        )
    lines.append("")
    
    # Task breakdown
    by_task = group_by_task(results)
    lines.extend([
        "---",
        "",
        "## Per-Task Breakdown",
        "",
        "| Task | Runs | Success | Score | Completeness | Turns | Tokens |",
        "|------|------|---------|-------|--------------|-------|--------|",
    ])
    for task, task_results in sorted(by_task.items()):
        m = compute_metrics(task_results)
        turns_str = f"{m.get('avg_turns', 0):.1f}" if "avg_turns" in m else "-"
        tokens_str = f"{m.get('avg_tokens', 0):.0f}" if "avg_tokens" in m else "-"
        lines.append(
            f"| **{task}** | {m['count']} | {m['success_rate']*100:.0f}% | "
            f"{m['avg_final_score']:.3f} | {m['avg_completeness']:.3f} | {turns_str} | {tokens_str} |"
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
    # Cross-Task Analysis
    # =========================================================================
    task_analysis = analyze_by_task_type(results)
    failure_analysis = analyze_failure_modes(results)
    pattern_task_fit = analyze_pattern_task_fit(results)
    academic_metrics = compute_academic_metrics(results)
    
    lines.extend([
        "---",
        "",
        "## Task-Level Performance Analysis",
        "",
        "### Performance by Task",
        "",
        "| Task | Difficulty | Type | Protocol | Valid/Total | Success | Avg Score | Best Pattern |",
        "|------|-----------|------|----------|-------------|---------|-----------|--------------|",
    ])
    
    for task_id in sorted(TASK_METADATA.keys()):
        if task_id in task_analysis["by_task"]:
            metadata = TASK_METADATA[task_id]
            metrics = task_analysis["by_task"][task_id]
            display_name = metadata.get("display_name", task_id)
            difficulty = metadata.get("difficulty", "-")
            task_type = metadata.get("type", "-")
            protocol = metadata.get("protocol", "-")
            
            valid_count = metrics.get("valid_count", 0)
            total_count = metrics.get("count", 0)
            success_rate = metrics.get("success_rate", 0)
            avg_score = metrics.get("avg_final_score", 0)
            
            best_info = pattern_task_fit["best_pattern_by_task"].get(task_id, {})
            best_pattern = best_info.get("pattern", "-")
            
            lines.append(
                f"| {display_name} | {difficulty} | {task_type} | {protocol} | "
                f"{valid_count}/{total_count} | {success_rate*100:.0f}% | {avg_score:.3f} | {best_pattern} |"
            )
    
    lines.extend([
        "",
        "### Performance by Task Characteristics",
        "",
        "#### By Difficulty Level",
        "",
        "| Difficulty | Valid Runs | Avg Score | Success Rate |",
        "|-----------|-----------|-----------|--------------|",
    ])
    
    for difficulty in ["basic", "intermediate", "expert"]:
        if difficulty in task_analysis["by_difficulty"]:
            metrics = task_analysis["by_difficulty"][difficulty]
            lines.append(
                f"| {difficulty.capitalize()} | {metrics.get('valid_count', 0)} | "
                f"{metrics.get('avg_final_score', 0):.3f} | {metrics.get('success_rate', 0)*100:.0f}% |"
            )
    
    lines.extend([
        "",
        "#### By Task Type",
        "",
        "| Type | Valid Runs | Avg Score | Success Rate |",
        "|------|-----------|-----------|--------------|",
    ])
    
    for task_type in ["configuration", "troubleshooting"]:
        if task_type in task_analysis["by_type"]:
            metrics = task_analysis["by_type"][task_type]
            lines.append(
                f"| {task_type.capitalize()} | {metrics.get('valid_count', 0)} | "
                f"{metrics.get('avg_final_score', 0):.3f} | {metrics.get('success_rate', 0)*100:.0f}% |"
            )
    
    lines.extend([
        "",
        "#### By Protocol",
        "",
        "| Protocol | Valid Runs | Avg Score | Success Rate |",
        "|----------|-----------|-----------|--------------|",
    ])
    
    for protocol in ["RIP", "OSPF", "BGP"]:
        if protocol in task_analysis["by_protocol"]:
            metrics = task_analysis["by_protocol"][protocol]
            lines.append(
                f"| {protocol} | {metrics.get('valid_count', 0)} | "
                f"{metrics.get('avg_final_score', 0):.3f} | {metrics.get('success_rate', 0)*100:.0f}% |"
            )
    
    lines.extend([
        "",
        "---",
        "",
        "## Failure Mode Analysis",
        "",
        "### Failure Breakdown by Task",
        "",
        "| Task | Total | Failed | Zero Validity | Timeout | Failure Rate |",
        "|------|-------|--------|---------------|---------|--------------|",
    ])
    
    for task_id in sorted(TASK_METADATA.keys()):
        if task_id in failure_analysis["by_task"]:
            stats = failure_analysis["by_task"][task_id]
            display_name = TASK_METADATA[task_id].get("display_name", task_id)
            lines.append(
                f"| {display_name} | {stats['total']} | {stats['failed']} | "
                f"{stats['zero_validity']} | {stats['timeout']} | {stats['failure_rate']*100:.0f}% |"
            )
    
    lines.extend([
        "",
        "> [!NOTE]",
        "> **Zero Validity**: Runs where syntactic_validity=0 (timeout or no commands executed)",
        "> These runs are excluded from performance averages.",
        "",
        "---",
        "",
        "## Pattern-Task Fit Analysis",
        "",
        "### Best Pattern by Task",
        "",
    ])
    
    for task_id in sorted(TASK_METADATA.keys()):
        if task_id in pattern_task_fit["best_pattern_by_task"]:
            best_info = pattern_task_fit["best_pattern_by_task"][task_id]
            display_name = TASK_METADATA[task_id].get("display_name", task_id)
            pattern = best_info.get("pattern", "-")
            score = best_info.get("score", 0)
            lines.append(f"- **{display_name}**: {pattern} (score: {score:.3f})")
    
    lines.extend([
        "",
        "### Pattern Performance Matrix (Score by Task)",
        "",
        "| Task | Single | Sequential | Debate | Group Chat | Concurrent |",
        "|------|--------|-----------|--------|-----------|-------------|",
    ])
    
    sorted_tasks = sorted(TASK_METADATA.items(), key=lambda x: x[1]['complexity_score'])
    for task_id, metadata in sorted_tasks:
        display_name = metadata.get('display_name', task_id)
        row = f"| {display_name} |"
        
        for pattern in pattern_order:
            pattern_metrics = pattern_task_fit["pattern_x_task"].get(task_id, {}).get(pattern)
            if pattern_metrics and pattern_metrics.get("valid_count", 0) > 0:
                score = pattern_metrics.get("avg_final_score", 0)
                row += f" {score:.3f} |"
            else:
                row += " - |"
        
        lines.append(row)
    
    lines.extend([
        "",
        "### Pattern Performance by Difficulty",
        "",
        "| Pattern | Basic | Intermediate | Expert |",
        "|---------|-------|--------------|--------|",
    ])
    
    pattern_order = ["single", "sequential", "debate", "group_chat", "concurrent"]
    for pattern in pattern_order:
        row = f"| {pattern} |"
        for difficulty in ["basic", "intermediate", "expert"]:
            diff_data = pattern_task_fit["pattern_x_difficulty"].get(difficulty, {})
            pattern_metrics = diff_data.get(pattern)
            if pattern_metrics and pattern_metrics.get("valid_count", 0) > 0:
                score = pattern_metrics.get("avg_final_score", 0)
                row += f" {score:.3f} |"
            else:
                row += " - |"
        lines.append(row)
    
    lines.extend([
        "",
        "### Pattern Performance by Task Type",
        "",
        "| Pattern | Configuration | Troubleshooting |",
        "|---------|---------------|-----------------|",
    ])
    
    for pattern in pattern_order:
        row = f"| {pattern} |"
        for task_type in ["configuration", "troubleshooting"]:
            type_data = pattern_task_fit["pattern_x_type"].get(task_type, {})
            pattern_metrics = type_data.get(pattern)
            if pattern_metrics and pattern_metrics.get("valid_count", 0) > 0:
                score = pattern_metrics.get("avg_final_score", 0)
                row += f" {score:.3f} |"
            else:
                row += " - |"
        lines.append(row)
    
    lines.extend([
        "",
        "---",
        "",
        "## Statistical Analysis",
        "",
        "### Single vs Multi-Agent (with Confidence Intervals)",
        "",
    ])
    
    if "single_vs_multi" in academic_metrics:
        svm = academic_metrics["single_vs_multi"]
        single_mean = svm["single_mean"]
        single_ci = svm["single_ci"]
        multi_mean = svm["multi_mean"]
        multi_ci = svm["multi_ci"]
        effect_size = svm["effect_size"]
        interpretation = svm["interpretation"]
        
        lines.extend([
            "| Architecture | Mean Score | 95% CI | N |",
            "|--------------|-----------|--------|---|",
            f"| Single-Agent | {single_mean:.3f} | [{single_ci[0]:.3f}, {single_ci[1]:.3f}] | {academic_metrics['patterns'].get('single', {}).get('n', 0)} |",
            f"| Multi-Agent | {multi_mean:.3f} | [{multi_ci[0]:.3f}, {multi_ci[1]:.3f}] | - |",
            "",
            f"**Effect Size (Cohen's d):** {effect_size:.3f} ({interpretation})",
            "",
        ])
    
    lines.extend([
        "### Pattern Performance with Confidence Intervals",
        "",
        "| Pattern | Mean Score | 95% CI | N |",
        "|---------|-----------|--------|---|",
    ])
    
    for pattern in pattern_order:
        if pattern in academic_metrics.get("patterns", {}):
            p_data = academic_metrics["patterns"][pattern]
            mean = p_data["mean"]
            ci = p_data["ci"]
            n = p_data["n"]
            lines.append(f"| {pattern} | {mean:.3f} | [{ci[0]:.3f}, {ci[1]:.3f}] | {n} |")
    
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
                    metrics = compute_metrics(matching)
                    if metrics.get("valid_count", 0) > 0:
                        matrix[i, j] = metrics.get("avg_final_score", 0)
        
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
    
    # ========== NEW Chart 10: Performance vs Task Complexity (Line Plot) ==========
    # Similar to reference image style
    task_analysis = analyze_by_task_type(results)
    pattern_task_fit = analyze_pattern_task_fit(results)
    
    # Build complexity data
    complexity_data = {}
    for pattern in patterns_present:
        complexity_data[pattern] = []
    
    # Sort tasks by complexity
    sorted_tasks = sorted(TASK_METADATA.items(), key=lambda x: x[1]['complexity_score'])
    
    for task_id, metadata in sorted_tasks:
        complexity = metadata['complexity_score']
        
        for pattern in patterns_present:
            pattern_metrics = pattern_task_fit["pattern_x_task"].get(task_id, {}).get(pattern)
            if pattern_metrics and pattern_metrics.get("valid_count", 0) > 0:
                score = pattern_metrics.get("avg_final_score", 0) * 100  # Convert to percentage
                complexity_data[pattern].append((complexity, score))
    
    # Create line plot
    if any(len(data) > 0 for data in complexity_data.values()):
        fig, ax = plt.subplots(figsize=(8, 6))
        
        for pattern in patterns_present:
            data = complexity_data[pattern]
            if len(data) >= 2:  # Need at least 2 points for a line
                x_vals = [d[0] for d in data]
                y_vals = [d[1] for d in data]
                
                ax.plot(x_vals, y_vals, 
                       marker=MARKERS.get(pattern, 'o'),
                       color=COLORS.get(pattern, '#888888'),
                       label=pattern.replace('_', ' ').title(),
                       linewidth=2, markersize=10, alpha=0.8)
        
        ax.set_xlabel('Task Complexity Score', fontweight='bold', fontsize=11)
        ax.set_ylabel('Performance (%)', fontweight='bold', fontsize=11)
        ax.set_title('Performance vs Task Complexity', fontsize=12, fontweight='bold', pad=15)
        ax.set_xticks([1, 2, 3])
        ax.set_xticklabels(['Basic\n(CCNA)', 'Intermediate\n(CCNP)', 'Expert\n(CCIE)'], fontsize=9)
        ax.set_ylim(0, 100)
        ax.grid(True, alpha=0.3, linestyle='--')
        ax.legend(loc='best', frameon=True, fancybox=False, edgecolor='0.8', fontsize=9)
        
        plt.tight_layout()
        chart_path = charts_dir / "performance_vs_complexity.png"
        plt.savefig(chart_path, dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()
        chart_paths.append(chart_path)
    
    # ========== NEW Chart 11: Task-Pattern Fit Heatmap ==========
    if len(sorted_tasks) > 0 and len(patterns_present) >= 2:
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Build matrix
        matrix = np.zeros((len(sorted_tasks), len(patterns_present)))
        task_labels = []
        
        for i, (task_id, metadata) in enumerate(sorted_tasks):
            task_labels.append(metadata.get('display_name', task_id))
            
            for j, pattern in enumerate(patterns_present):
                pattern_metrics = pattern_task_fit["pattern_x_task"].get(task_id, {}).get(pattern)
                if pattern_metrics and pattern_metrics.get("valid_count", 0) > 0:
                    matrix[i, j] = pattern_metrics.get("avg_final_score", 0)
        
        im = ax.imshow(matrix, cmap='RdYlGn', aspect='auto', vmin=0, vmax=1)
        
        ax.set_xticks(np.arange(len(patterns_present)))
        ax.set_yticks(np.arange(len(sorted_tasks)))
        ax.set_xticklabels([p.replace('_', ' ').title() for p in patterns_present], 
                          fontsize=10, fontweight='bold')
        ax.set_yticklabels(task_labels, fontsize=9)
        ax.set_xlabel('Agent Pattern', fontweight='bold', fontsize=11)
        ax.set_ylabel('Task', fontweight='bold', fontsize=11)
        ax.set_title('Pattern Performance by Task', fontsize=12, fontweight='bold', pad=15)
        
        # Add text annotations
        for i in range(len(sorted_tasks)):
            for j in range(len(patterns_present)):
                val = matrix[i, j]
                if val > 0:  # Only show non-zero values
                    color = 'white' if val < 0.3 or val > 0.7 else 'black'
                    ax.text(j, i, f'{val:.2f}', ha='center', va='center',
                           fontsize=9, fontweight='bold', color=color)
                else:
                    ax.text(j, i, '-', ha='center', va='center',
                           fontsize=9, color='gray')
        
        cbar = plt.colorbar(im, ax=ax, shrink=0.8)
        cbar.set_label('Final Score', fontweight='bold', fontsize=10)
        
        plt.tight_layout()
        chart_path = charts_dir / "task_pattern_heatmap.png"
        plt.savefig(chart_path, dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()
        chart_paths.append(chart_path)
    
    # ========== NEW Chart 12: Difficulty Comparison (Line Plot with CI) ==========
    if "pattern_x_difficulty" in pattern_task_fit:
        fig, ax = plt.subplots(figsize=(8, 6))
        
        difficulties = ["basic", "intermediate", "expert"]
        x_pos = [1, 2, 3]
        
        for pattern in patterns_present:
            scores = []
            for difficulty in difficulties:
                diff_data = pattern_task_fit["pattern_x_difficulty"].get(difficulty, {})
                pattern_metrics = diff_data.get(pattern)
                if pattern_metrics and pattern_metrics.get("valid_count", 0) > 0:
                    scores.append(pattern_metrics.get("avg_final_score", 0) * 100)
                else:
                    scores.append(None)
            
            # Filter out None values for plotting
            valid_x = [x_pos[i] for i in range(len(scores)) if scores[i] is not None]
            valid_scores = [s for s in scores if s is not None]
            
            if len(valid_scores) >= 2:
                ax.plot(valid_x, valid_scores,
                       marker=MARKERS.get(pattern, 'o'),
                       color=COLORS.get(pattern, '#888888'),
                       label=pattern.replace('_', ' ').title(),
                       linewidth=2.5, markersize=10, alpha=0.85)
        
        ax.set_xlabel('Task Difficulty', fontweight='bold', fontsize=12)
        ax.set_ylabel('Performance (%)', fontweight='bold', fontsize=12)
        ax.set_title('Agent Performance Across Difficulty Levels', 
                    fontsize=13, fontweight='bold', pad=15)
        ax.set_xticks(x_pos)
        ax.set_xticklabels(['Basic', 'Intermediate', 'Expert'], fontsize=10)
        ax.set_ylim(0, 100)
        ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.8)
        ax.legend(loc='best', frameon=True, fancybox=False, edgecolor='0.8', 
                 fontsize=10, ncol=1)
        
        # Add difficulty labels with task info
        for i, (pos, diff) in enumerate(zip(x_pos, difficulties)):
            tasks_at_level = [t for t, m in TASK_METADATA.items() 
                            if m.get('difficulty') == diff]
            ax.text(pos, -8, f'({len(tasks_at_level)} tasks)', 
                   ha='center', va='top', fontsize=8, style='italic', color='gray')
        
        plt.tight_layout()
        chart_path = charts_dir / "difficulty_performance.png"
        plt.savefig(chart_path, dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()
        chart_paths.append(chart_path)

    # ========== NEW Chart 13: Tokens vs Score Scatter ==========
    tokens_data = []
    scores_data = []
    pattern_data = []
    
    for result in results:
        usage = result.get("metrics", {}).get("token_usage")
        tokens = usage.get("total_tokens") if usage else None
        score = result.get("scoring", {}).get("final_score", 0)
        mode, structure = extract_agent_config(result)
        pattern = "single" if mode == "single" else structure
        
        if tokens and tokens > 0:
            tokens_data.append(tokens)
            scores_data.append(score)
            pattern_data.append(pattern)
    
    if tokens_data and len(set(pattern_data)) >= 2:
        fig, ax = plt.subplots(figsize=(8, 6))
        
        for pattern in patterns_present:
            idx = [i for i, p in enumerate(pattern_data) if p == pattern]
            if idx:
                t = [tokens_data[i] for i in idx]
                s = [scores_data[i] for i in idx]
                ax.scatter(t, s, c=COLORS.get(pattern, '#888888'), 
                          label=pattern.replace('_', ' ').title(), s=80, alpha=0.7, edgecolors='black')
        
        ax.set_xlabel('Total Tokens Consumed', fontweight='bold', fontsize=11)
        ax.set_ylabel('Final Score', fontweight='bold', fontsize=11)
        ax.set_title('Token Consumption vs Score by Pattern', fontsize=12, fontweight='bold', pad=15)
        ax.set_ylim(-0.05, 1.05)
        ax.axhline(y=0.5, color='gray', linestyle='--', alpha=0.5)
        ax.legend(loc='upper right', frameon=True, fancybox=False, edgecolor='0.8', fontsize=9)
        ax.grid(True, alpha=0.3, linestyle='--')
        
        plt.tight_layout()
        chart_path = charts_dir / "tokens_vs_score.png"
        plt.savefig(chart_path, dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()
        chart_paths.append(chart_path)

    # ========== NEW Chart 14: Average Token Consumption per Pattern ==========
    if len(patterns_present) >= 2:
        fig, ax = plt.subplots(figsize=(8, 6))
        
        avg_tokens = []
        token_stds = []
        
        for pattern in patterns_present:
            m = compute_metrics(by_pattern[pattern])
            avg_tokens.append(m.get("avg_tokens", 0))
            token_stds.append(m.get("std_tokens", 0))
            
        x = np.arange(len(patterns_present))
        colors = [COLORS.get(p, '#888888') for p in patterns_present]
        
        bars = ax.bar(x, avg_tokens, yerr=token_stds, color=colors, edgecolor='black', linewidth=0.8, capsize=4)
        for bar, hatch in zip(bars, HATCHES):
            bar.set_hatch(hatch)
            
        ax.set_ylabel('Average Tokens Consumed', fontweight='bold', fontsize=11)
        ax.set_xlabel('Agent Pattern', fontweight='bold', fontsize=11)
        ax.set_title('Average Token Consumption by Pattern', fontsize=12, fontweight='bold', pad=15)
        ax.set_xticks(x)
        ax.set_xticklabels([p.replace('_', '\n').title() for p in patterns_present], fontsize=9)
        ax.grid(True, alpha=0.3, axis='y', linestyle='--')
        
        # Add value labels on top of bars
        for i, (bar, val) in enumerate(zip(bars, avg_tokens)):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + token_stds[i] * 0.1 + 1000, 
                       f'{val:,.0f}', ha='center', va='bottom', fontsize=9, fontweight='bold')
        
        plt.tight_layout()
        chart_path = charts_dir / "avg_tokens_by_pattern.png"
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
