#!/usr/bin/env python3
"""
Comprehensive model behavioral analysis for IEEE CNSM paper.

Analyzes:
- Per-model performance distributions with statistical tests
- Property-level satisfaction (which network properties block models)
- Token efficiency (score per token; convergence cost)
- Task difficulty breakdown (CCNA/CCNP/CCIE = basic/intermediate/expert)
- Network coherence curves with variance bands
- Meltdown detection (loops, spirals, stagnation, fixation)
- Multi-agent conversation depth (debate pattern support)
- Case study automation (best/worst run narratives)

Usage:
    poetry run python scripts/analyze_model_behavior.py <session_dir>
"""

import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.deep_analysis.run_filters import is_adaptive_pattern_run, is_gpt5_nano_run
from scripts.macro_pooled_stats import write_macro_pooled_artifacts

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from scipy import stats

# ─── Publication-quality style ────────────────────────────────────────────────
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

# ─── Constants ─────────────────────────────────────────────────────────────────
MODEL_COLORS = {
    'GPT-5':    '#74AA9C', 'GPT-4':    '#A1C3BA',
    'Gemini-3': '#4285F4', 'Gemini-2': '#8AB4F8',
    'Llama-3.3':'#0064E0', 'Qwen-3':   '#722ED1',
    'Qwen3-Coder-Next': '#9B59B6', 'Qwen3-Coder-30b': '#8E44AD',
    'Llama-3.3':'#0064E0', 'Qwen3-Coder': '#722ED1', 'Qwen3-Coder-Next': '#B37FEB',
    'Kimi-K2.5':'#F5222D',
}
DEFAULT_COLOR = '#888888'

DIFFICULTY_ORDER   = ['basic', 'intermediate', 'expert']
DIFFICULTY_COLORS  = {'basic': '#43A047', 'intermediate': '#FB8C00', 'expert': '#E53935'}

TASK_METADATA = {
    "ccna_rip_routing_basic":          {"difficulty": "basic",        "type": "configuration",    "protocol": "RIP",  "display_name": "CCNA RIP",  "depth": 2},
    "ccnp_multiarea_ospf_intermediate":{"difficulty": "intermediate", "type": "configuration",    "protocol": "OSPF", "display_name": "CCNP OSPF", "depth": 3},
    "ccie_bgp_dual_homing_expert":     {"difficulty": "expert",       "type": "configuration",    "protocol": "BGP",  "display_name": "CCIE BGP",  "depth": 5},
    "troubleshoot_ospf_adjacency_issue":{"difficulty":"intermediate", "type": "troubleshooting",  "protocol": "OSPF", "display_name": "Fix OSPF",  "depth": 6},
    "troubleshoot_bgp_route_filtering":{"difficulty": "expert",       "type": "troubleshooting",  "protocol": "BGP",  "display_name": "Fix BGP",   "depth": 7},
}

# ─── Helpers ──────────────────────────────────────────────────────────────────

def load_results(session_dir: Path, single_only: bool = False) -> List[Dict]:
    results = []
    runs_dir = session_dir / "runs"
    if not runs_dir.exists():
        runs_dir = session_dir
    for f in runs_dir.glob("**/*.json"):
        if f.name == "session_info.json":
            continue
        try:
            with open(f) as fh:
                data = json.load(fh)
                if single_only:
                    testee_id = data.get("testee_id", "")
                    if "single" not in testee_id.lower():
                        continue
                if is_gpt5_nano_run(data) or is_adaptive_pattern_run(data):
                    continue
                results.append(data)
        except Exception:
            continue
    return results


def normalize_model_name(result: Dict) -> str:
    model = result.get("model_version") or result.get("agent_config", {}).get("model", "unknown")
    model = re.sub(r'^(openai|ollama|gemini|anthropic):', '', str(model).lower())
    if "gpt5nano" in model or "gpt-5-nano" in model:
        return "GPT-5-nano"
    if "gpt5mini" in model or "gpt-5-mini" in model:
        return "GPT-5-mini"
    if "gpt-5" in model or "gpt5" in model:
        return "GPT-5-mini"
    if "gpt-4" in model:    return "GPT-4"
    if "gemini-3" in model: return "Gemini-3"
    if "gemini-2" in model: return "Gemini-2"
    if "llama3.3" in model or "llama-3.3" in model: return "Llama-3.3"
    if "qwen3" in model:
        if "codernext" in model or "coder-next" in model:
            return "Qwen3-Coder-Next"
        if "qwen3-coder" in model or "coder:30b" in model:
            return "Qwen3-Coder"
        return "Qwen3-Coder"  # fallback for other qwen3
    if "kimi" in model:     return "Kimi-K2.5"
    return model


def model_color(name: str) -> str:
    return MODEL_COLORS.get(name, DEFAULT_COLOR)


def classify_command(cmd: str) -> str:
    c = cmd.lower()
    if any(p in c for p in ['no router', 'no ip', 'no network', 'no interface', 'shutdown']):
        return 'destructive'
    if any(p in c for p in ['show ', 'ping ', 'traceroute', 'ip addr show', 'ip route get', 'ip route show']):
        return 'diagnostic'
    if any(p in c for p in ['router ', 'network ', 'ip addr add', 'interface ', 'vtysh', 'no shutdown', 'echo ']):
        return 'constructive'
    return 'other'


def _get_cmds(log: List) -> List[str]:
    """Extract bare commands from execution_log entries."""
    cmds = []
    for entry in log:
        if not isinstance(entry, str):
            continue
        parts = entry.split(" | ", 3)
        if (
            len(parts) == 4
            and parts[1] in ("config", "read")
            and parts[3] in ("ok", "fail")
        ):
            cmds.append(parts[2].strip())
            continue
        cmds.append(entry.split(" | ", 1)[-1].strip() if " | " in entry else entry.strip())
    return cmds


def _token_data(result: Dict) -> Tuple[int, int, int]:
    """Return (prompt, completion, total) tokens."""
    m = result.get("metrics", {}) or {}
    tu = m.get("token_usage") or {}
    p = tu.get("prompt_tokens", 0) or 0
    c = tu.get("completion_tokens", 0) or 0
    t = tu.get("total_tokens", 0) or p + c
    return p, c, t


# ─── Core Metrics ─────────────────────────────────────────────────────────────

def compute_metrics(result: Dict) -> Dict:
    log   = result.get("execution_log", []) or []
    cmds  = _get_cmds(log)
    types = [classify_command(c) for c in cmds]

    total  = len(cmds)
    diag   = types.count('diagnostic')
    const  = types.count('constructive')
    dest   = types.count('destructive')
    other  = types.count('other')

    # Property satisfaction
    props      = result.get("property_results", []) or []
    satisfied  = [p for p in props if p.get("satisfied", False)]
    n_props    = max(1, len(props))
    progress   = len(satisfied) / n_props

    m_data  = result.get("metrics", {}) or {}
    turns   = m_data.get("turns_to_complete") or max(1, total)
    p_tok, c_tok, tot_tok = _token_data(result)
    failed_cmds = m_data.get("failed_commands") or 0

    # Execution time
    exec_time = m_data.get("config_execution_time") or m_data.get("time_to_complete") or 0

    # Coherence trajectory (per-turn estimate)
    cmds_per_turn = max(1, total // turns)
    coherence = []
    cum_const, cum_dest = 0, 0
    for t in range(turns):
        window = types[t * cmds_per_turn: (t + 1) * cmds_per_turn]
        cum_const += window.count('constructive')
        cum_dest  += window.count('destructive')
        t_prog = (cum_const / max(1, const)) * progress if const else 0
        d_ratio = cum_dest / max(1, (t + 1) * cmds_per_turn)
        coherence.append(t_prog * (1.0 - d_ratio))

    final_score = result.get("scoring", {}).get("final_score", 0) or 0

    return {
        "total_commands":    total,
        "failed_commands":   failed_cmds,
        "syntax_error_rate": failed_cmds / max(1, total),
        "diagnostic_count":  diag,
        "constructive_count":const,
        "destructive_count": dest,
        "other_count":       other,
        "exploration_rate":  diag / max(1, const) if const else diag,
        "destructive_ratio": dest / max(1, total),
        "success":           bool(result.get("success", False)),
        "final_score":       final_score,
        "final_progress":    progress,
        "n_props":           n_props,
        "n_satisfied":       len(satisfied),
        "turns":             turns,
        "exec_time":         exec_time,
        "prompt_tokens":     p_tok,
        "completion_tokens": c_tok,
        "total_tokens":      tot_tok,
        "tokens_per_turn":   tot_tok / turns if turns else 0,
        "score_per_1k_tokens": (final_score / (tot_tok / 1000)) if tot_tok else 0,
        "coherence_trajectory": coherence,
        "final_coherence":   coherence[-1] if coherence else 0,
        "property_results":  props,
        "termination_reason": m_data.get("termination_reason", "unknown"),
        "agent_conversations": result.get("metrics", {}).get("agent_conversations"),
    }


def detect_meltdowns(result: Dict) -> Dict:
    cmds  = _get_cmds(result.get("execution_log", []) or [])
    types = [classify_command(c) for c in cmds]
    signals: List[str] = []

    # 1. Command loop (same cmd 4+ times consecutively)
    for i in range(len(cmds) - 3):
        if len(set(cmds[i:i+4])) == 1:
            signals.append("Command Loop")
            break

    # 2. Destructive spiral (3+ destructive in sliding window of 5)
    for i in range(len(types) - 4):
        if types[i:i+5].count('destructive') >= 3:
            signals.append("Destructive Spiral")
            break

    # 3. Cognitive stagnation (many turns, score < 0.1)
    m = result.get("metrics", {}) or {}
    turns = m.get("turns_to_complete") or 0
    score = result.get("scoring", {}).get("final_score", 0) or 0
    if turns > 25 and score < 0.1:
        signals.append("Cognitive Stagnation")

    # 4. Diagnostic fixation (10 consecutive only-diagnostics)
    for i in range(max(0, len(types) - 9)):
        if all(t == 'diagnostic' for t in types[i:i+10]):
            signals.append("Diagnostic Fixation")
            break

    # 5. Premature termination (submitted with < 30% score)
    reason = (m.get("termination_reason") or "").lower()
    if reason == "submitted" and score < 0.3:
        signals.append("Premature Submission")

    return {"meltdown_detected": len(signals) > 0, "signals": signals}


def _pattern_from_testee(testee_id: str) -> str:
    """Map testee_id to pattern name (single, sequential, debate, group_chat, concurrent)."""
    t = (testee_id or "").lower()
    if "_multi_adaptive" in t:
        return "adaptive"
    if "_multi_sequential" in t:
        return "sequential"
    if "_multi_debate" in t:
        return "debate"
    if "_multi_group_chat" in t:
        return "group_chat"
    if "_multi_concurrent" in t:
        return "concurrent"
    if "_multi" in t:
        return "sequential"
    return "single"


def build_profiles(results: List[Dict]) -> List[Dict]:
    profiles = []
    for r in results:
        m   = compute_metrics(r)
        md  = detect_meltdowns(r)
        tid = r.get("task_id", "unknown")
        meta = TASK_METADATA.get(tid, {})
        profiles.append({
            "run_id":           r.get("run_id", ""),
            "model":            normalize_model_name(r),
            "pattern":          _pattern_from_testee(r.get("testee_id", "")),
            "task_id":          tid,
            "task":             meta.get("display_name", tid),
            "difficulty":       meta.get("difficulty", "unknown"),
            "task_type":        meta.get("type", "unknown"),
            "protocol":         meta.get("protocol", "?"),
            "depth":            meta.get("depth", 0),
            "meltdown":         md["meltdown_detected"],
            "meltdown_signals": md["signals"],
            **m,
        })
    return profiles


def agg(vals: List[float]) -> Dict:
    if not vals:
        return {"mean": 0, "std": 0, "median": 0, "q25": 0, "q75": 0, "n": 0}
    a = np.array(vals, dtype=float)
    return {
        "mean":   float(np.nanmean(a)),
        "std":    float(np.nanstd(a)),
        "median": float(np.nanmedian(a)),
        "q25":    float(np.nanpercentile(a, 25)),
        "q75":    float(np.nanpercentile(a, 75)),
        "n":      len(a),
    }


# ─── Plots ─────────────────────────────────────────────────────────────────────

def plot_score_boxplot(profiles: List[Dict], models: List[str], out: Path) -> None:
    """Figure 1: Score distribution per model with individual run dots."""
    fig, ax = plt.subplots(figsize=(max(7, len(models) * 1.8), 5))

    data = [[p["final_score"] for p in profiles if p["model"] == m] for m in models]
    colors = [model_color(m) for m in models]

    bp = ax.boxplot(data, patch_artist=True, notch=False, widths=0.5,
                    medianprops=dict(color='black', linewidth=2),
                    whiskerprops=dict(linewidth=1.5),
                    capprops=dict(linewidth=1.5),
                    flierprops=dict(marker='o', markersize=4, alpha=0.5))

    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)

    # Jitter individual points
    for i, (vals, color) in enumerate(zip(data, colors), 1):
        jitter = np.random.normal(0, 0.05, len(vals))
        ax.scatter([i] * len(vals) + jitter, vals, color=color,
                   alpha=0.6, zorder=5, s=25, edgecolors='white', linewidths=0.5)

    ax.set_xticks(range(1, len(models) + 1))
    ax.set_xticklabels(models, rotation=20, ha='right')
    ax.set_ylabel("Final Score (0–1)")
    ax.set_title("Score Distribution by Model (per run)")
    ax.set_ylim(-0.05, 1.05)
    ax.axhline(0.5, linestyle='--', color='gray', alpha=0.4, linewidth=1)
    fig.tight_layout()
    fig.savefig(out / "fig1_score_distribution.png")
    plt.close(fig)


def plot_difficulty_breakdown(profiles: List[Dict], models: List[str], out: Path) -> None:
    """Figure 2: Score by task difficulty for each model."""
    diffs = [d for d in DIFFICULTY_ORDER if any(p['difficulty'] == d for p in profiles)]
    if not diffs:
        return

    n_models = len(models)
    n_diffs  = len(diffs)
    x = np.arange(n_models)
    width = 0.7 / n_diffs

    fig, ax = plt.subplots(figsize=(max(8, n_models * 2.2), 5))
    for i, d in enumerate(diffs):
        means = []
        for m in models:
            vals = [p["final_score"] for p in profiles if p["model"] == m and p["difficulty"] == d]
            means.append(np.mean(vals) if vals else 0)
        offset = (i - n_diffs / 2 + 0.5) * width
        bars = ax.bar(x + offset, means, width * 0.9,
                      label=d.capitalize(), color=DIFFICULTY_COLORS[d], alpha=0.85)
        for bar, val in zip(bars, means):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                    f"{val:.2f}", ha='center', va='bottom', fontsize=7)

    ax.set_xticks(x)
    ax.set_xticklabels(models, rotation=20, ha='right')
    ax.set_ylabel("Mean Final Score")
    ax.set_title("Performance by Task Difficulty (CCNA→CCNP→CCIE)")
    ax.legend(title="Difficulty", loc='upper right')
    ax.set_ylim(0, 1.15)
    fig.tight_layout()
    fig.savefig(out / "fig2_difficulty_breakdown.png")
    plt.close(fig)


def plot_coherence_curves(profiles: List[Dict], models: List[str], results: List[Dict], out: Path) -> None:
    """Figure 3: Coherence trajectory with ±1σ shading per model."""
    fig, ax = plt.subplots(figsize=(10, 5))

    for model in models:
        trajs = [p["coherence_trajectory"] for p in profiles
                 if p["model"] == model and p["coherence_trajectory"]]
        if not trajs:
            continue
        max_len = max(len(t) for t in trajs)
        padded  = np.array([t + [t[-1]] * (max_len - len(t)) for t in trajs])
        mean    = np.mean(padded, axis=0)
        std     = np.std(padded, axis=0)
        x       = np.arange(1, max_len + 1)
        color   = model_color(model)

        ax.plot(x, mean, label=model, color=color, linewidth=2.5)
        ax.fill_between(x, np.clip(mean - std, 0, 1), np.clip(mean + std, 0, 1),
                        color=color, alpha=0.15)

    ax.set_xlabel("Interaction Turn")
    ax.set_ylabel("Network Coherence Score")
    ax.set_title("Network Coherence Trajectory (mean ± 1σ across runs)")
    ax.set_ylim(-0.05, 1.05)
    ax.legend(loc='upper left', framealpha=0.9)
    fig.tight_layout()
    fig.savefig(out / "fig3_coherence_curves.png")
    plt.close(fig)


def plot_token_efficiency(profiles: List[Dict], models: List[str], out: Path) -> None:
    """Figure 4: Score vs token cost scatter + regression (efficiency frontier)."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Left: score vs total tokens (scatter)
    ax = axes[0]
    for m in models:
        ps = [p for p in profiles if p["model"] == m and p["total_tokens"] > 0]
        if not ps:
            continue
        xs = [p["total_tokens"] / 1000 for p in ps]   # in K tokens
        ys = [p["final_score"] for p in ps]
        color = model_color(m)
        ax.scatter(xs, ys, label=m, color=color, alpha=0.65, s=60,
                   edgecolors='white', linewidths=0.5)
        # Regression line
        if len(xs) > 1:
            slope, intercept, r, *_ = stats.linregress(xs, ys)
            xr = np.linspace(min(xs), max(xs), 80)
            ax.plot(xr, slope * xr + intercept, color=color, linewidth=1.2,
                    linestyle='--', alpha=0.5)

    ax.set_xlabel("Total Tokens (K)")
    ax.set_ylabel("Final Score")
    ax.set_title("Score vs Token Cost per Run")
    ax.legend(fontsize=8)

    # Right: box plot of score per 1K tokens (efficiency)
    ax = axes[1]
    eff_data = [[p["score_per_1k_tokens"] for p in profiles
                 if p["model"] == m and p["total_tokens"] > 0] for m in models]
    colors = [model_color(m) for m in models]

    bp = ax.boxplot(eff_data, patch_artist=True, widths=0.5,
                    medianprops=dict(color='black', linewidth=2))
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)

    ax.set_xticks(range(1, len(models) + 1))
    ax.set_xticklabels(models, rotation=20, ha='right')
    ax.set_ylabel("Score per 1K Tokens")
    ax.set_title("Token Efficiency (Score/1K Tokens)")

    fig.tight_layout()
    fig.savefig(out / "fig4_token_efficiency.png")
    plt.close(fig)


def plot_property_satisfaction_heatmap(profiles: List[Dict], models: List[str], out: Path) -> None:
    """Figure 5: Property satisfaction rates (which properties block each model)."""
    # Collect all property IDs
    prop_ids = sorted(list(set(
        p_res["property_id"]
        for prof in profiles
        for p_res in (prof.get("property_results") or [])
        if "property_id" in p_res
    )))
    if not prop_ids or not models:
        return

    mat = np.full((len(models), len(prop_ids)), np.nan)
    for i, m in enumerate(models):
        for j, pid in enumerate(prop_ids):
            vals = []
            for prof in profiles:
                if prof["model"] != m:
                    continue
                for p_res in (prof.get("property_results") or []):
                    if p_res.get("property_id") == pid:
                        vals.append(1 if p_res.get("satisfied") else 0)
            if vals:
                mat[i, j] = np.mean(vals)

    fig, ax = plt.subplots(figsize=(max(10, len(prop_ids) * 1.5), max(4, len(models) + 1)))
    cmap = plt.cm.RdYlGn
    cmap.set_bad('lightgrey')
    im = ax.imshow(mat, cmap=cmap, vmin=0, vmax=1, aspect='auto')
    plt.colorbar(im, ax=ax, label="Satisfaction Rate (0→1)")

    ax.set_xticks(range(len(prop_ids)))
    ax.set_xticklabels([p.replace('_', '\n') for p in prop_ids],
                       fontsize=7, rotation=45, ha='right')
    ax.set_yticks(range(len(models)))
    ax.set_yticklabels(models)
    ax.set_title("Property-Level Satisfaction Rates by Model\n(grey = no data)")

    for i in range(len(models)):
        for j in range(len(prop_ids)):
            if not np.isnan(mat[i, j]):
                color = 'black' if 0.2 < mat[i, j] < 0.8 else 'white'
                ax.text(j, i, f"{mat[i, j]:.2f}", ha='center', va='center',
                        fontsize=7, color=color)

    fig.tight_layout()
    fig.savefig(out / "fig5_property_heatmap.png")
    plt.close(fig)


def plot_meltdown_analysis(profiles: List[Dict], models: List[str], out: Path) -> None:
    """Figure 6: Meltdown probability heatmap + signal breakdown."""
    tasks = sorted(set(p['task'] for p in profiles))

    fig, axes = plt.subplots(1, 2, figsize=(16, max(4, len(models) + 1)))

    # Left: Meltdown probability heatmap
    ax = axes[0]
    mat = np.zeros((len(models), len(tasks)))
    for i, m in enumerate(models):
        for j, t in enumerate(tasks):
            vals = [p["meltdown"] for p in profiles if p["model"] == m and p["task"] == t]
            mat[i, j] = np.mean(vals) if vals else 0

    im = ax.imshow(mat, cmap="YlOrRd", vmin=0, vmax=1)
    plt.colorbar(im, ax=ax, label="Meltdown Rate")
    ax.set_xticks(range(len(tasks)))
    ax.set_xticklabels(tasks, rotation=35, ha='right', fontsize=8)
    ax.set_yticks(range(len(models)))
    ax.set_yticklabels(models)
    ax.set_title("Meltdown Probability (Model × Task)")
    for i in range(len(models)):
        for j in range(len(tasks)):
            ax.text(j, i, f"{mat[i, j]:.2f}", ha='center', va='center', fontsize=8)

    # Right: Meltdown signal breakdown (stacked bar)
    ax = axes[1]
    all_signal_types = ["Command Loop", "Destructive Spiral", "Cognitive Stagnation",
                        "Diagnostic Fixation", "Premature Submission"]
    signal_colors = ['#e53935', '#fb8c00', '#fdd835', '#8e24aa', '#1e88e5']

    signal_counts = {m: Counter() for m in models}
    for prof in profiles:
        for sig in prof["meltdown_signals"]:
            signal_counts[prof["model"]][sig] += 1

    x = np.arange(len(models))
    bottom = np.zeros(len(models))
    for sig_type, color in zip(all_signal_types, signal_colors):
        vals = [signal_counts[m][sig_type] for m in models]
        ax.bar(x, vals, bottom=bottom, color=color, label=sig_type, alpha=0.85)
        bottom += np.array(vals, dtype=float)

    ax.set_xticks(x)
    ax.set_xticklabels(models, rotation=20, ha='right')
    ax.set_ylabel("Count")
    ax.set_title("Meltdown Signal Frequency by Type")
    ax.legend(fontsize=7, loc='upper right')

    fig.tight_layout()
    fig.savefig(out / "fig6_meltdown_analysis.png")
    plt.close(fig)


def plot_command_composition(profiles: List[Dict], models: List[str], out: Path) -> None:
    """Figure 7: Command composition profiles + syntax error rate."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Left: stacked bar for command types
    ax = axes[0]
    comp_fields = ['constructive_count', 'diagnostic_count', 'destructive_count', 'other_count']
    comp_labels = ['Constructive', 'Diagnostic', 'Destructive', 'Other']
    comp_colors = ['#2ca02c', '#1f77b4', '#d62728', '#9467bd']

    x = np.arange(len(models))
    totals = []
    for m in models:
        ps = [p for p in profiles if p["model"] == m]
        total = sum(np.mean([p[f] for p in ps]) for f in comp_fields)
        totals.append(max(1, total))

    bottom = np.zeros(len(models))
    for field, label, color in zip(comp_fields, comp_labels, comp_colors):
        means = []
        for idx, m in enumerate(models):
            ps = [p for p in profiles if p["model"] == m]
            means.append(np.mean([p[field] for p in ps]) / totals[idx] * 100 if ps else 0)
        ax.bar(x, means, 0.6, bottom=bottom, color=color, label=label, alpha=0.85)
        bottom += np.array(means)

    ax.set_xticks(x)
    ax.set_xticklabels(models, rotation=20, ha='right')
    ax.set_ylabel("Percentage of Commands (%)")
    ax.set_title("Command Composition by Model")
    ax.legend(fontsize=8)

    # Right: syntax error rate
    ax = axes[1]
    err_data = [[p["syntax_error_rate"] * 100 for p in profiles if p["model"] == m] for m in models]
    colors = [model_color(m) for m in models]

    bp = ax.boxplot(err_data, patch_artist=True, widths=0.5,
                    medianprops=dict(color='black', linewidth=2))
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)

    ax.set_xticks(range(1, len(models) + 1))
    ax.set_xticklabels(models, rotation=20, ha='right')
    ax.set_ylabel("Failed Commands (%)")
    ax.set_title("Syntax Error Rate Distribution")

    fig.tight_layout()
    fig.savefig(out / "fig7_command_analysis.png")
    plt.close(fig)


def plot_convergence_cost(profiles: List[Dict], models: List[str], out: Path) -> None:
    """Figure 8: Cumulative token spend vs score (convergence cost curve)."""
    fig, ax = plt.subplots(figsize=(10, 5))

    for m in models:
        ps = sorted([p for p in profiles if p["model"] == m and p["total_tokens"] > 0],
                    key=lambda p: p["total_tokens"])
        if not ps:
            continue
        cum_tokens = np.array([p["total_tokens"] / 1000 for p in ps]).cumsum()
        scores     = np.array([p["final_score"] for p in ps])
        ax.plot(cum_tokens, scores, 'o-', label=m, color=model_color(m),
                linewidth=2, markersize=5, alpha=0.8)

    ax.set_xlabel("Cumulative Tokens (K)")
    ax.set_ylabel("Final Score")
    ax.set_title("Convergence Cost Curve (cumulative token vs. per-run score)")
    ax.legend(loc='lower right')
    fig.tight_layout()
    fig.savefig(out / "fig8_convergence_cost.png")
    plt.close(fig)


def plot_context_vs_performance(profiles: List[Dict], models: List[str], out: Path) -> None:
    """Figure 9: Context management — performance vs context size and turns."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Left: Score vs total tokens (context size at completion)
    ax = axes[0]
    for m in models:
        ps = [p for p in profiles if p["model"] == m and p["total_tokens"] > 0]
        if not ps:
            continue
        xs = [p["total_tokens"] / 1000 for p in ps]
        ys = [p["final_score"] for p in ps]
        ax.scatter(xs, ys, label=m, color=model_color(m), alpha=0.65, s=50,
                   edgecolors='white', linewidths=0.5)
    ax.set_xlabel("Total Context (K tokens)")
    ax.set_ylabel("Final Score")
    ax.set_title("Score vs Context Size (as it accumulates)")
    ax.legend(fontsize=8)
    ax.set_ylim(-0.05, 1.05)
    ax.axhline(0.5, linestyle='--', color='gray', alpha=0.4)

    # Right: Score vs turns (context length via interaction depth)
    ax = axes[1]
    for m in models:
        ps = [p for p in profiles if p["model"] == m and p["turns"] > 0]
        if not ps:
            continue
        xs = [p["turns"] for p in ps]
        ys = [p["final_score"] for p in ps]
        ax.scatter(xs, ys, label=m, color=model_color(m), alpha=0.65, s=50,
                   edgecolors='white', linewidths=0.5)
    ax.set_xlabel("Turns to Complete (history length)")
    ax.set_ylabel("Final Score")
    ax.set_title("Score vs Turn Count (context accumulation)")
    ax.legend(fontsize=8)
    ax.set_ylim(-0.05, 1.05)
    ax.axhline(0.5, linestyle='--', color='gray', alpha=0.4)

    fig.suptitle("Context Management: Does accumulated context affect performance?",
                 fontsize=12, fontweight='bold', y=1.02)
    fig.tight_layout()
    fig.savefig(out / "fig9_context_vs_performance.png")
    plt.close(fig)


def plot_context_verbosity_efficiency(profiles: List[Dict], models: List[str], out: Path) -> None:
    """Figure 10: Tokens per turn (verbosity) vs score — do verbose runs perform differently?"""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Left: Tokens per turn vs score scatter by model
    ax = axes[0]
    for m in models:
        ps = [p for p in profiles if p["model"] == m and p["turns"] > 0 and p["total_tokens"] > 0]
        if not ps:
            continue
        tpt = [p["tokens_per_turn"] for p in ps]
        ys = [p["final_score"] for p in ps]
        ax.scatter(tpt, ys, label=m, color=model_color(m), alpha=0.65, s=50,
                   edgecolors='white', linewidths=0.5)
    ax.set_xlabel("Tokens per Turn (verbosity)")
    ax.set_ylabel("Final Score")
    ax.set_title("Score vs Verbosity (tokens/turn)")
    ax.legend(fontsize=8)
    ax.set_ylim(-0.05, 1.05)
    ax.axhline(0.5, linestyle='--', color='gray', alpha=0.4)

    # Right: Binned context size — mean score per bin
    ax = axes[1]
    all_tokens = [p["total_tokens"] / 1000 for p in profiles if p["total_tokens"] > 0]
    if all_tokens:
        bins = [0, 25, 50, 100, 200, 500, 10000]  # 500K+ catches large contexts
        bin_labels = ["0–25K", "25–50K", "50–100K", "100–200K", "200–500K", "500K+"]
        for m in models:
            ps = [p for p in profiles if p["model"] == m and p["total_tokens"] > 0]
            if not ps:
                continue
            bin_means, bin_stds, bin_counts = [], [], []
            for i in range(len(bins) - 1):
                in_bin = [p for p in ps if bins[i] <= p["total_tokens"] / 1000 < bins[i + 1]]
                if in_bin:
                    bin_means.append(np.mean([p["final_score"] for p in in_bin]))
                    bin_stds.append(np.std([p["final_score"] for p in in_bin]))
                    bin_counts.append(len(in_bin))
                else:
                    bin_means.append(np.nan)
                    bin_stds.append(0)
                    bin_counts.append(0)
            x = np.arange(len(bin_labels))
            valid = ~np.isnan(bin_means)
            if np.any(valid):
                ax.plot(x[valid], np.array(bin_means)[valid], 'o-', label=m,
                        color=model_color(m), linewidth=2, markersize=8)
        ax.set_xticks(range(len(bin_labels)))
        ax.set_xticklabels(bin_labels, rotation=20, ha='right')
        ax.set_xlabel("Context Size Bin (tokens)")
        ax.set_ylabel("Mean Final Score")
        ax.set_title("Performance by Context Size Bin")
        ax.legend(fontsize=8)
        ax.set_ylim(-0.05, 1.05)

    fig.suptitle("Context Management: Verbosity and context-size bins",
                 fontsize=12, fontweight='bold', y=1.02)
    fig.tight_layout()
    fig.savefig(out / "fig10_context_verbosity.png")
    plt.close(fig)


# ─── Statistical Tests ─────────────────────────────────────────────────────────

def run_statistical_tests(profiles: List[Dict], models: List[str]) -> List[Dict]:
    """Pairwise Mann-Whitney U test on final scores."""
    rows = []
    for i in range(len(models)):
        for j in range(i + 1, len(models)):
            a = [p["final_score"] for p in profiles if p["model"] == models[i]]
            b = [p["final_score"] for p in profiles if p["model"] == models[j]]
            if len(a) < 2 or len(b) < 2:
                continue
            u_stat, p_val = stats.mannwhitneyu(a, b, alternative='two-sided')
            rows.append({
                "model_a": models[i], "model_b": models[j],
                "n_a": len(a), "n_b": len(b),
                "mean_a": np.mean(a), "mean_b": np.mean(b),
                "U_statistic": round(u_stat, 2), "p_value": round(p_val, 4),
                "significant": p_val < 0.05,
            })
    return rows


# ─── Case Studies ─────────────────────────────────────────────────────────────

def generate_case_studies(profiles: List[Dict], results: List[Dict], models: List[str]) -> str:
    """Return markdown for best and worst run narratives."""
    sections = []
    for m in models:
        m_profs = [p for p in profiles if p["model"] == m]
        if not m_profs:
            continue
        best  = max(m_profs, key=lambda p: p["final_score"])
        worst = min(m_profs, key=lambda p: p["final_score"])

        def narrative(prof: Dict, label: str) -> str:
            sigs = ", ".join(prof["meltdown_signals"]) if prof["meltdown_signals"] else "None"
            lines = [
                f"#### {label} Run – Task: {prof['task']} ({prof['difficulty']})",
                f"- **Score**: {prof['final_score']:.3f} | **Success**: {prof['success']}",
                f"- **Turns**: {prof['turns']} | **Tokens**: {prof['total_tokens']:,}",
                f"- **Exploration Rate**: {prof['exploration_rate']:.2f} | **Destructive Ratio**: {prof['destructive_ratio']:.2f}",
                f"- **Meltdown Signals**: {sigs}",
                f"- **Properties Satisfied**: {prof['n_satisfied']}/{prof['n_props']}",
                f"- **Termination**: {prof['termination_reason']}",
            ]
            return "\n".join(lines)

        sections.append(f"\n### {m}")
        sections.append(narrative(best, "✅ Best"))
        sections.append(narrative(worst, "❌ Worst"))

    return "\n".join(sections)


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Analyze model behavioral results.")
    parser.add_argument("session_dir", type=str, help="Path to the session directory")
    parser.add_argument("--single", action="store_true", help="Only analyze single agent results")
    
    if len(sys.argv) < 2:
        parser.print_help()
        sys.exit(1)
        
    args = parser.parse_args()
    session_dir = Path(args.session_dir)

    results     = load_results(session_dir, single_only=args.single)
    print(f"✓ Loaded {len(results)} results from {session_dir}")

    if not results:
        print("✗ No valid results found.")
        sys.exit(1)

    profiles = build_profiles(results)
    models   = sorted(set(p["model"] for p in profiles))
    print(f"✓ Models found: {', '.join(models)}")

    out = session_dir / "behavior_analysis"
    out.mkdir(exist_ok=True)

    # ── Aggregate statistics ────────────────────────────────────────────────
    model_agg = {}
    for m in models:
        ps = [p for p in profiles if p["model"] == m]
        model_agg[m] = {
            "n":            len(ps),
            "score":        agg([p["final_score"] for p in ps]),
            "success_rate": np.mean([p["success"] for p in ps]),
            "exploration":  agg([p["exploration_rate"] for p in ps]),
            "destructive":  agg([p["destructive_ratio"] for p in ps]),
            "meltdown_rate":np.mean([p["meltdown"] for p in ps]),
            "turns":        agg([p["turns"] for p in ps]),
            "total_tokens": agg([p["total_tokens"] for p in ps]),
            "eff_score_1k": agg([p["score_per_1k_tokens"] for p in ps if p["total_tokens"] > 0]),
            "exec_time":    agg([p["exec_time"] for p in ps if p["exec_time"] > 0]),
            "tokens_per_turn": agg([p["tokens_per_turn"] for p in ps if p["turns"] > 0 and p["total_tokens"] > 0]),
            "prompt_tokens":   agg([p["prompt_tokens"] for p in ps if p.get("prompt_tokens", 0) > 0]),
        }

    # ── Print summary table ─────────────────────────────────────────────────
    print("\n" + "─" * 80)
    print(f"{'Model':<12} {'N':>4} {'Score μ':>8} {'σ':>6} {'Success':>8} {'Explor':>7} {'Dest':>6} {'Melt':>6} {'Turns':>7} {'Eff/1K':>8}")
    print("─" * 80)
    for m, a in sorted(model_agg.items(), key=lambda x: -x[1]["score"]["mean"]):
        print(f"{m:<12} {a['n']:>4} {a['score']['mean']:>8.3f} {a['score']['std']:>6.3f} "
              f"{a['success_rate']:>8.3f} {a['exploration']['mean']:>7.3f} "
              f"{a['destructive']['mean']:>6.3f} {a['meltdown_rate']:>6.3f} "
              f"{a['turns']['mean']:>7.1f} {a['eff_score_1k']['mean']:>8.4f}")
    print("─" * 80)

    # ── Generate all figures ─────────────────────────────────────────────────
    print("\nGenerating figures...")
    plot_score_boxplot(profiles, models, out)
    print("  ✓ fig1_score_distribution.png")
    plot_difficulty_breakdown(profiles, models, out)
    print("  ✓ fig2_difficulty_breakdown.png")
    plot_coherence_curves(profiles, models, results, out)
    print("  ✓ fig3_coherence_curves.png")
    plot_token_efficiency(profiles, models, out)
    print("  ✓ fig4_token_efficiency.png")
    plot_property_satisfaction_heatmap(profiles, models, out)
    print("  ✓ fig5_property_heatmap.png")
    plot_meltdown_analysis(profiles, models, out)
    print("  ✓ fig6_meltdown_analysis.png")
    plot_command_composition(profiles, models, out)
    print("  ✓ fig7_command_analysis.png")
    plot_convergence_cost(profiles, models, out)
    print("  ✓ fig8_convergence_cost.png")
    plot_context_vs_performance(profiles, models, out)
    print("  ✓ fig9_context_vs_performance.png")
    plot_context_verbosity_efficiency(profiles, models, out)
    print("  ✓ fig10_context_verbosity.png")

    # ── Statistical tests ────────────────────────────────────────────────────
    stat_rows = run_statistical_tests(profiles, models)

    # ── Case studies ─────────────────────────────────────────────────────────
    case_md = generate_case_studies(profiles, results, models)

    # ── CSV export ───────────────────────────────────────────────────────────
    csv_fields = [k for k in profiles[0].keys()
                  if k not in ("coherence_trajectory", "property_results",
                               "agent_conversations", "meltdown_signals")]
    with open(out / "all_runs.csv", "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=csv_fields)
        writer.writeheader()
        for p in profiles:
            writer.writerow({k: p.get(k, "") for k in csv_fields})

    write_macro_pooled_artifacts(profiles, out)
    print("  ✓ macro_pooled_report.md, macro_pooled_kpis.csv, macro_pooled_by_protocol.csv")

    # ── Markdown report ──────────────────────────────────────────────────────
    def summary_table() -> str:
        hdr = ("| Model | N | Score μ±σ | Median | Success | Explor | Dest | Melt | "
               "Turns | Tokens K | Eff/1K |")
        sep = "|---|---|---|---|---|---|---|---|---|---|---|"
        rows = []
        for m, a in sorted(model_agg.items(), key=lambda x: -x[1]["score"]["mean"]):
            rows.append(
                f"| {m} | {a['n']} | "
                f"{a['score']['mean']:.3f}±{a['score']['std']:.3f} | "
                f"{a['score']['median']:.3f} | "
                f"{a['success_rate']:.3f} | "
                f"{a['exploration']['mean']:.3f} | "
                f"{a['destructive']['mean']:.3f} | "
                f"{a['meltdown_rate']:.3f} | "
                f"{a['turns']['mean']:.1f} | "
                f"{a['total_tokens']['mean']/1000:.1f} | "
                f"{a['eff_score_1k']['mean']:.4f} |"
            )
        return "\n".join([hdr, sep] + rows)

    def stat_table() -> str:
        if not stat_rows:
            return "*Insufficient data for statistical comparison.*"
        hdr = "| Model A | Model B | N_A | N_B | Mean A | Mean B | U | p | Sig |"
        sep = "|---|---|---|---|---|---|---|---|---|"
        rows = [f"| {r['model_a']} | {r['model_b']} | {r['n_a']} | {r['n_b']} | "
                f"{r['mean_a']:.3f} | {r['mean_b']:.3f} | {r['U_statistic']} | "
                f"{r['p_value']} | {'✓' if r['significant'] else '✗'} |"
                for r in stat_rows]
        return "\n".join([hdr, sep] + rows)

    # Build difficulty section
    diff_section_lines = []
    for d in DIFFICULTY_ORDER:
        d_profs = [p for p in profiles if p["difficulty"] == d]
        if not d_profs:
            continue
        diff_section_lines.append(f"\n#### {d.capitalize()} Tasks")
        diff_header = "| Model | Mean Score | Success Rate | Meltdown Rate |"
        diff_sep    = "|---|---|---|---|"
        diff_rows = []
        for m in models:
            mp = [p for p in d_profs if p["model"] == m]
            if not mp:
                continue
            diff_rows.append(f"| {m} | {np.mean([p['final_score'] for p in mp]):.3f} | "
                             f"{np.mean([p['success'] for p in mp]):.3f} | "
                             f"{np.mean([p['meltdown'] for p in mp]):.3f} |")
        diff_section_lines.append("\n".join([diff_header, diff_sep] + diff_rows))

    report = f"""# Model Behavioral Analysis — IEEE CNSM Paper
**Session:** {session_dir.name}
**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}
**Models:** {', '.join(models)} | **Total Runs:** {len(profiles)}

---

## 1. Executive Summary

{summary_table()}

> **Metrics:** Score = weighted property satisfaction (0→1). Explor = diagnostic/constructive ratio.
> Dest = fraction of destructive commands. Melt = catastrophic failure rate. Eff/1K = score per 1k tokens.

---

## 2. Task Difficulty Breakdown
{chr(10).join(diff_section_lines)}

---

## 3. Statistical Comparisons (Mann-Whitney U)

{stat_table()}

---

## 4. Analysis Figures

### Fig 1 – Score Distribution
![Score Distribution](fig1_score_distribution.png)

### Fig 2 – Difficulty Breakdown
![Difficulty Breakdown](fig2_difficulty_breakdown.png)

### Fig 3 – Network Coherence Trajectories (mean ± 1σ)
![Coherence Curves](fig3_coherence_curves.png)

### Fig 4 – Token Efficiency
![Token Efficiency](fig4_token_efficiency.png)

### Fig 5 – Property-Level Satisfaction
![Property Heatmap](fig5_property_heatmap.png)

### Fig 6 – Meltdown Analysis
![Meltdown Analysis](fig6_meltdown_analysis.png)

### Fig 7 – Command Composition & Syntax Error Rate
![Command Composition](fig7_command_analysis.png)

### Fig 8 – Convergence Cost Curves
![Convergence Cost](fig8_convergence_cost.png)

### Fig 9 – Context vs Performance (context accumulation impact)
![Context vs Performance](fig9_context_vs_performance.png)

### Fig 10 – Context Verbosity & Size Bins
![Context Verbosity](fig10_context_verbosity.png)

---

## 5. Case Studies (Best / Worst Runs per Model)
{case_md}

---

*Behavioral analysis supporting the NetAgentBench paper (IEEE CNSM 2026).*
"""

    with open(out / "model_behavior_report.md", "w") as fh:
        fh.write(report)

    # Save stat tests CSV
    if stat_rows:
        with open(out / "statistical_tests.csv", "w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=stat_rows[0].keys())
            writer.writeheader()
            writer.writerows(stat_rows)

    print(f"\n✓ Analysis complete. Results in: {out}")


if __name__ == "__main__":
    main()
