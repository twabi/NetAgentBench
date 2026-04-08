#!/usr/bin/env python3
"""
Shared run loader and utilities for deep analysis modules.

Provides:
- load_runs(): Load all run JSONs from a session directory
- load_and_enrich(): Load runs, drop GPT-5-nano and adaptive-pattern rows, attach derived fields
- normalize_model_name(): Consistent model name normalization
- extract_agent_config(): Extract (mode, pattern) from testee_id
- classify_command(): Classify commands as constructive/diagnostic/destructive
- setup_plotting(): Publication-quality matplotlib defaults
- TASK_METADATA: Task difficulty, protocol, depth metadata
- PATTERN_COLORS / PATTERN_MARKERS: Consistent visual identity per pattern
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from scripts.deep_analysis.run_filters import is_adaptive_pattern_run, is_gpt5_nano_run

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

RESULTS_DIR = Path(__file__).resolve().parent.parent.parent / "results"
DEFAULT_SESSION = RESULTS_DIR / "comparatives_all"

TASK_METADATA = {
    "ccna_rip_routing_basic": {
        "difficulty": "basic", "type": "configuration", "protocol": "RIP",
        "display_name": "CCNA RIP", "sequential_depth": 2, "parallelizable_breadth": 4,
    },
    "ccnp_multiarea_ospf_intermediate": {
        "difficulty": "intermediate", "type": "configuration", "protocol": "OSPF",
        "display_name": "CCNP OSPF", "sequential_depth": 3, "parallelizable_breadth": 3,
    },
    "ccie_bgp_dual_homing_expert": {
        "difficulty": "expert", "type": "configuration", "protocol": "BGP",
        "display_name": "CCIE BGP", "sequential_depth": 5, "parallelizable_breadth": 2,
    },
    "troubleshoot_ospf_adjacency_issue": {
        "difficulty": "intermediate", "type": "troubleshooting", "protocol": "OSPF",
        "display_name": "Fix OSPF", "sequential_depth": 6, "parallelizable_breadth": 1,
    },
    "troubleshoot_bgp_route_filtering": {
        "difficulty": "expert", "type": "troubleshooting", "protocol": "BGP",
        "display_name": "Fix BGP", "sequential_depth": 7, "parallelizable_breadth": 1,
    },
}

PATTERN_COLORS = {
    'single':     '#0173B2',
    'sequential': '#DE8F05',
    'debate':     '#029E73',
    'group_chat': '#CC78BC',
    'concurrent': '#CA9161',
}

PATTERN_MARKERS = {
    'single': 'o', 'sequential': 's', 'debate': '^',
    'group_chat': 'D', 'concurrent': 'v',
}

PATTERN_ORDER = ['single', 'sequential', 'debate', 'group_chat', 'concurrent']
PATTERN_LABELS = {
    'single': 'Single', 'sequential': 'Sequential', 'debate': 'Debate',
    'group_chat': 'Group Chat', 'concurrent': 'Concurrent',
}


def setup_plotting():
    """Apply publication-quality matplotlib settings."""
    plt.style.use('seaborn-v0_8-whitegrid')
    plt.rcParams.update({
        'font.size': 10, 'font.family': 'sans-serif',
        'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
        'axes.labelsize': 11, 'axes.titlesize': 12, 'axes.titleweight': 'bold',
        'axes.linewidth': 1.2, 'xtick.labelsize': 9, 'ytick.labelsize': 9,
        'legend.fontsize': 9, 'legend.frameon': True, 'legend.edgecolor': '0.8',
        'figure.dpi': 100, 'savefig.dpi': 300, 'savefig.bbox': 'tight',
        'savefig.facecolor': 'white', 'lines.linewidth': 2, 'lines.markersize': 8,
        'grid.alpha': 0.3, 'grid.linestyle': '--',
        'axes.spines.top': False, 'axes.spines.right': False,
    })


def load_runs(session_dir: Path | None = None) -> List[Dict[str, Any]]:
    """Load all run JSONs from a session directory."""
    session_dir = session_dir or DEFAULT_SESSION
    runs_dir = session_dir / "runs"
    if not runs_dir.exists():
        runs_dir = session_dir

    results = []
    for f in runs_dir.rglob("*.json"):
        if f.name == "session_info.json":
            continue
        try:
            with open(f) as fh:
                data = json.load(fh)
                if "run_id" in data or "task_id" in data:
                    results.append(data)
        except Exception:
            continue
    return results


def normalize_model_name(result: Dict) -> str:
    """Normalize model name to a short display label."""
    model = result.get("model_version") or result.get("agent_config", {}).get("model", "unknown")
    model = re.sub(r'^(openai|ollama|gemini|anthropic):', '', str(model).lower())
    model = model.replace("-2025-08-07", "").replace("2025-08-07", "")
    if "gpt5nano" in model or "gpt-5-nano" in model:
        return "GPT-5-nano"
    if "gpt5mini" in model or "gpt-5-mini" in model:
        return "GPT-5-mini"
    if "gpt-5" in model or "gpt5" in model:
        return "GPT-5-mini"
    if "gpt-4" in model:
        return "GPT-4"
    if "gemini-3" in model:
        return "Gemini-3"
    if "gemini-2" in model:
        return "Gemini-2"
    if "llama3.3" in model or "llama-3.3" in model or "llama33" in model:
        return "Llama-3.3"
    if "qwen3-coder-next" in model or "qwen3codernext" in model:
        return "Qwen3-Coder-Next"
    if "qwen3-coder" in model or "qwen3coder" in model:
        return "Qwen3-Coder"
    if "qwen3" in model:
        return "Qwen-3"
    if "kimi" in model:
        return "Kimi-K2.5"
    return model


def extract_agent_config(result: Dict) -> Tuple[str, str]:
    """Extract (mode, pattern) from result testee_id.

    Returns e.g. ('single', 'single') or ('multi', 'group_chat').
    """
    testee_id = result.get("testee_id", "").lower()

    if "_multi_sequential" in testee_id:
        return "multi", "sequential"
    if "_multi_debate" in testee_id:
        return "multi", "debate"
    if "_multi_group_chat" in testee_id:
        return "multi", "group_chat"
    if "_multi_concurrent" in testee_id:
        return "multi", "concurrent"
    if "_multi" in testee_id:
        return "multi", "sequential"
    return "single", "single"


def classify_command(cmd: str) -> str:
    """Classify a command string as constructive/diagnostic/destructive/other."""
    c = cmd.lower()
    if any(p in c for p in ['no router', 'no ip', 'no network', 'no interface', 'shutdown',
                             'clear ip ospf', 'clear ip bgp']):
        return 'destructive'
    if any(p in c for p in ['show ', 'ping ', 'traceroute', 'ip addr show',
                             'ip route get', 'ip route show']):
        return 'diagnostic'
    if any(p in c for p in ['router ', 'network ', 'ip addr add', 'interface ',
                             'vtysh', 'no shutdown', 'write memory', 'echo ']):
        return 'constructive'
    return 'other'


def extract_execution_commands(execution_log: List) -> List[Tuple[str, str]]:
    """Parse execution_log entries into (router, command) tuples."""
    pairs = []
    for entry in execution_log:
        if not isinstance(entry, str):
            continue
        if ' | ' in entry:
            router, cmd = entry.split(' | ', 1)
            pairs.append((router.strip(), cmd.strip()))
        else:
            pairs.append(('unknown', entry.strip()))
    return pairs


def get_output_dir(session_dir: Path | None = None) -> Path:
    """Create and return the deep_analysis output directory."""
    session_dir = session_dir or DEFAULT_SESSION
    out = session_dir / "deep_analysis"
    out.mkdir(exist_ok=True)
    return out


def enrich_run(run: Dict) -> Dict:
    """Add derived fields to a run dict (mode, pattern, model, task metadata)."""
    mode, pattern = extract_agent_config(run)
    model = normalize_model_name(run)
    task_id = run.get("task_id", "unknown")
    meta = TASK_METADATA.get(task_id, {})

    run["_mode"] = mode
    run["_pattern"] = pattern
    run["_model"] = model
    run["_task_display"] = meta.get("display_name", task_id)
    run["_difficulty"] = meta.get("difficulty", "unknown")
    run["_protocol"] = meta.get("protocol", "?")
    return run


def load_and_enrich(session_dir: Path | None = None) -> List[Dict]:
    """Load all runs, exclude GPT-5-nano and adaptive-pattern runs, add derived fields."""
    runs = [
        r
        for r in load_runs(session_dir)
        if not is_gpt5_nano_run(r) and not is_adaptive_pattern_run(r)
    ]
    return [enrich_run(r) for r in runs]
