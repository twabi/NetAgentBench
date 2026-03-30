#!/usr/bin/env python3
"""
Module 2: Cross-Router Coherence Analysis

Parses execution_log to extract which router each command targets.
Builds per-run "router touch sequences" and detects coherence violations.

Metrics per run:
- router_switch_rate: router switches / total commands
- router_entropy: Shannon entropy of router-target distribution
- protocol_reset_count: destructive protocol resets (clear ip ospf, no router bgp)
- subnet_assignments: IP addresses assigned per router (for mismatch detection)
- unique_routers_touched: number of distinct routers commanded
"""

import csv
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from .run_loader import (
    load_and_enrich, get_output_dir, setup_plotting,
    extract_execution_commands,
    PATTERN_COLORS, PATTERN_ORDER, PATTERN_LABELS, DEFAULT_SESSION,
)

RESET_PATTERNS = [
    r'clear\s+ip\s+ospf',
    r'clear\s+ip\s+bgp',
    r'no\s+router\s+ospf',
    r'no\s+router\s+bgp',
    r'no\s+router\s+rip',
]
RESET_RE = re.compile('|'.join(RESET_PATTERNS), re.IGNORECASE)

IP_ADDR_RE = re.compile(
    r'ip\s+addr(?:ess)?\s+([\d.]+/\d+)', re.IGNORECASE
)


def _shannon_entropy(counts: Counter) -> float:
    """Compute Shannon entropy of a distribution."""
    total = sum(counts.values())
    if total == 0:
        return 0.0
    probs = [c / total for c in counts.values()]
    return -sum(p * math.log2(p) for p in probs if p > 0)


def analyze_run(run: Dict) -> Dict[str, Any]:
    """Analyze cross-router coherence for a single run."""
    exec_log = run.get("execution_log", []) or []
    pairs = extract_execution_commands(exec_log)

    if not pairs:
        return {
            "run_id": run.get("run_id", ""),
            "pattern": run["_pattern"],
            "model": run["_model"],
            "task_id": run.get("task_id", ""),
            "total_commands": 0,
            "unique_routers": 0,
            "router_switch_rate": 0.0,
            "router_entropy": 0.0,
            "protocol_reset_count": 0,
            "ip_assignments": 0,
            "subnet_conflicts": 0,
            "router_sequence": [],
            "router_counts": {},
        }

    router_sequence = [r for r, _ in pairs]
    router_counts = Counter(router_sequence)

    # Router switches
    switches = sum(
        1 for i in range(1, len(router_sequence))
        if router_sequence[i] != router_sequence[i - 1]
    )
    switch_rate = switches / len(router_sequence) if router_sequence else 0.0

    entropy = _shannon_entropy(router_counts)

    # Protocol resets
    reset_count = sum(
        1 for _, cmd in pairs if RESET_RE.search(cmd)
    )

    # IP address assignments per router (for subnet conflict detection)
    router_ips: Dict[str, List[str]] = defaultdict(list)
    for router, cmd in pairs:
        for match in IP_ADDR_RE.findall(cmd):
            router_ips[router].append(match)

    total_ip_assignments = sum(len(v) for v in router_ips.values())

    # Subnet conflict detection: same subnet assigned to different routers
    # with same host address (likely a copy-paste error)
    subnet_conflicts = 0
    all_assignments = []
    for router, ips in router_ips.items():
        for ip in ips:
            all_assignments.append((router, ip))

    seen_subnets: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
    for router, ip_cidr in all_assignments:
        try:
            ip_part = ip_cidr.split('/')[0]
            # Group by /30 or /24 subnet prefix
            octets = ip_part.split('.')
            subnet_key = '.'.join(octets[:3])
            seen_subnets[subnet_key].append((router, ip_cidr))
        except (IndexError, ValueError):
            continue

    for subnet, assignments in seen_subnets.items():
        routers_in_subnet = set(r for r, _ in assignments)
        ips_in_subnet = [ip for _, ip in assignments]
        # Conflict: same exact IP on different routers
        ip_counter = Counter(ips_in_subnet)
        for ip, count in ip_counter.items():
            if count > 1:
                assigning_routers = set(r for r, i in assignments if i == ip)
                if len(assigning_routers) > 1:
                    subnet_conflicts += 1

    return {
        "run_id": run.get("run_id", ""),
        "pattern": run["_pattern"],
        "model": run["_model"],
        "task_id": run.get("task_id", ""),
        "total_commands": len(pairs),
        "unique_routers": len(router_counts),
        "router_switch_rate": switch_rate,
        "router_entropy": entropy,
        "protocol_reset_count": reset_count,
        "ip_assignments": total_ip_assignments,
        "subnet_conflicts": subnet_conflicts,
        "router_sequence": router_sequence,
        "router_counts": dict(router_counts),
    }


def plot_entropy_comparison(all_results: List[Dict], out_dir: Path) -> None:
    """Box plot comparing router entropy across patterns."""
    setup_plotting()
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    patterns = [p for p in PATTERN_ORDER
                if any(r["pattern"] == p for r in all_results)]
    colors = [PATTERN_COLORS.get(p, '#888888') for p in patterns]

    # Left: Router entropy
    ax = axes[0]
    data = [[r["router_entropy"] for r in all_results
             if r["pattern"] == p and r["total_commands"] > 0] or [0]
            for p in patterns]
    bp = ax.boxplot(data, patch_artist=True, widths=0.5,
                    medianprops=dict(color='black', linewidth=2))
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    ax.set_xticks(range(1, len(patterns) + 1))
    ax.set_xticklabels([PATTERN_LABELS.get(p, p) for p in patterns])
    ax.set_ylabel("Shannon Entropy (bits)")
    ax.set_title("Router Target Entropy by Pattern")

    # Right: Router switch rate
    ax = axes[1]
    data = [[r["router_switch_rate"] for r in all_results
             if r["pattern"] == p and r["total_commands"] > 0] or [0]
            for p in patterns]
    bp = ax.boxplot(data, patch_artist=True, widths=0.5,
                    medianprops=dict(color='black', linewidth=2))
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    ax.set_xticks(range(1, len(patterns) + 1))
    ax.set_xticklabels([PATTERN_LABELS.get(p, p) for p in patterns])
    ax.set_ylabel("Switch Rate (switches / commands)")
    ax.set_title("Router Switch Rate by Pattern")

    fig.tight_layout()
    fig.savefig(out_dir / "coherence_entropy_switches.png")
    plt.close(fig)


def plot_protocol_resets(all_results: List[Dict], out_dir: Path) -> None:
    """Box plot of protocol reset counts by pattern."""
    setup_plotting()
    fig, ax = plt.subplots(figsize=(8, 5))

    patterns = [p for p in PATTERN_ORDER
                if any(r["pattern"] == p for r in all_results)]
    colors = [PATTERN_COLORS.get(p, '#888888') for p in patterns]
    data = [[r["protocol_reset_count"] for r in all_results if r["pattern"] == p]
            or [0] for p in patterns]

    bp = ax.boxplot(data, patch_artist=True, widths=0.5,
                    medianprops=dict(color='black', linewidth=2))
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    ax.set_xticks(range(1, len(patterns) + 1))
    ax.set_xticklabels([PATTERN_LABELS.get(p, p) for p in patterns])
    ax.set_ylabel("Protocol Resets per Run")
    ax.set_title("Protocol State Reset Count by Pattern")
    fig.tight_layout()
    fig.savefig(out_dir / "coherence_protocol_resets.png")
    plt.close(fig)


def plot_router_access_heatmap(all_results: List[Dict], out_dir: Path) -> None:
    """Heatmap of router access distribution per pattern x task."""
    setup_plotting()

    tasks = sorted(set(r["task_id"] for r in all_results))
    patterns = [p for p in PATTERN_ORDER
                if any(r["pattern"] == p for r in all_results)]
    all_routers = sorted(set(
        router for r in all_results for router in r.get("router_counts", {}).keys()
    ))

    if not all_routers or not patterns:
        return

    fig, axes = plt.subplots(len(patterns), 1,
                             figsize=(max(8, len(all_routers) * 1.5),
                                      3 * len(patterns)),
                             sharex=True)
    if len(patterns) == 1:
        axes = [axes]

    for ax, pattern in zip(axes, patterns):
        mat = np.zeros((len(tasks), len(all_routers)))
        for i, task in enumerate(tasks):
            task_runs = [r for r in all_results
                         if r["pattern"] == pattern and r["task_id"] == task]
            for r in task_runs:
                for j, router in enumerate(all_routers):
                    mat[i, j] += r.get("router_counts", {}).get(router, 0)
            if task_runs:
                mat[i, :] /= len(task_runs)

        im = ax.imshow(mat, cmap="YlOrRd", aspect='auto')
        ax.set_yticks(range(len(tasks)))
        from .run_loader import TASK_METADATA
        ax.set_yticklabels([TASK_METADATA.get(t, {}).get("display_name", t)
                            for t in tasks], fontsize=8)
        ax.set_title(f"{PATTERN_LABELS.get(pattern, pattern)}", fontsize=10)

        for i in range(len(tasks)):
            for j in range(len(all_routers)):
                if mat[i, j] > 0:
                    ax.text(j, i, f"{mat[i, j]:.1f}", ha='center', va='center',
                            fontsize=7)

    axes[-1].set_xticks(range(len(all_routers)))
    axes[-1].set_xticklabels(all_routers, fontsize=8, rotation=45, ha='right')
    fig.suptitle("Average Router Command Count (per run)", fontweight='bold', y=1.01)
    fig.tight_layout()
    fig.savefig(out_dir / "coherence_router_heatmap.png")
    plt.close(fig)


def save_csv(all_results: List[Dict], out_dir: Path) -> None:
    fields = [
        "run_id", "pattern", "model", "task_id", "total_commands",
        "unique_routers", "router_switch_rate", "router_entropy",
        "protocol_reset_count", "ip_assignments", "subnet_conflicts",
    ]
    with open(out_dir / "coherence_analysis.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in all_results:
            writer.writerow({k: r[k] for k in fields})


def run_analysis(session_dir: Path | None = None) -> List[Dict]:
    """Run the full cross-router coherence analysis."""
    runs = load_and_enrich(session_dir)
    out_dir = get_output_dir(session_dir)

    print(f"  Coherence Analysis: analyzing {len(runs)} runs...")
    all_results = [analyze_run(r) for r in runs]

    plot_entropy_comparison(all_results, out_dir)
    plot_protocol_resets(all_results, out_dir)
    plot_router_access_heatmap(all_results, out_dir)
    save_csv(all_results, out_dir)

    for pattern in PATTERN_ORDER:
        pr = [r for r in all_results if r["pattern"] == pattern and r["total_commands"] > 0]
        if not pr:
            continue
        avg_ent = np.mean([r["router_entropy"] for r in pr])
        avg_sw = np.mean([r["router_switch_rate"] for r in pr])
        avg_rst = np.mean([r["protocol_reset_count"] for r in pr])
        print(f"    {PATTERN_LABELS.get(pattern, pattern):>12}: "
              f"entropy={avg_ent:.2f} switch_rate={avg_sw:.3f} resets={avg_rst:.1f}")

    return all_results


if __name__ == "__main__":
    run_analysis()
