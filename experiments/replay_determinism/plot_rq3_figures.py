"""Plot publication-quality figures for RQ3 from replayed trajectories.

Generates separate image files:
- fig3_coherence_curves: two-panel C(H_t) trajectories (model and task).
- fig4_stall_frontiers: first unsatisfied property in each chain, from original terminal vectors.
- fig4_temporal_ordering: upstream vs downstream first-satisfaction timing.
"""

from __future__ import annotations

import json
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
RQ2_DIR = REPO_ROOT / "experiments" / "rq2_intent_resolution"
for _p in (RQ2_DIR, HERE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from analyze import PREREQUISITES, PROPERTY_LABELS, TASK_COLORS, TASK_LABELS, TASK_ORDER  # noqa: E402
from analyze_trajectories import first_true_turn, snapshots  # noqa: E402

TRAJ_DIR = HERE / "out" / "trajectories"
OUT_DIR = HERE / "out"
PAPER_DIR = Path.home() / "Documents" / "papers" / "benchmark_paper" / "scientific_reports"
# Coherence curves in the paper use these four tasks.
REPORTED_TASKS = {
    "ccna_rip_routing_basic",
    "troubleshoot_ospf_adjacency_issue",
    "ccnp_multiarea_ospf_intermediate",
    "ccie_bgp_dual_homing_expert",
}

MODEL_ORDER = [
    "openai_gpt5mini20250807",
    "ollama_qwen3coder:30b",
    "ollama_llama33:70b",
    "ollama_qwen3codernext:latest",
]

MODEL_LABELS = {
    "openai_gpt5mini20250807": "GPT-5-mini",
    "ollama_qwen3coder:30b": "Qwen3-Coder-30B",
    "ollama_llama33:70b": "Llama-3.3-70B",
    "ollama_qwen3codernext:latest": "Qwen3-Coder-Next",
}

MODEL_COLORS = {
    "openai_gpt5mini20250807": "#1f77b4",
    "ollama_qwen3coder:30b": "#ff7f0e",
    "ollama_llama33:70b": "#2ca02c",
    "ollama_qwen3codernext:latest": "#d62728",
}

TASK_PREREQ_ORDER = {
    "ccna_rip_routing_basic": [
        "rip_process_running",
        "ripv2_configured",
        "rip_routes_learned",
        "full_reachability",
    ],
    "troubleshoot_ospf_adjacency_issue": [
        "initial_problem_identified",
        "root_cause_diagnosed",
        "adjacency_restored",
        "full_topology_convergence",
    ],
    "ccnp_multiarea_ospf_intermediate": [
        "ospf_area0_adjacency",
        "area1_routes_visible",
        "end_to_end_reachability",
        "route_summarization",
    ],
    "ccie_bgp_dual_homing_expert": [
        "ebgp_isp1_established",
        "ebgp_isp2_established",
        "route_filtering_outbound",
        "primary_path_preference",
        "as_path_prepending",
        "convergence_time_optimized",
    ],
}

EDGE_LABELS = {
    ("ccna_rip_routing_basic", "rip_process_running", "rip_routes_learned"): "RIP: process → routes",
    ("ccna_rip_routing_basic", "ripv2_configured", "rip_routes_learned"): "RIP: v2 → routes",
    ("ccna_rip_routing_basic", "rip_routes_learned", "full_reachability"): "RIP: routes → reach",
    ("ccna_rip_routing_basic", "rip_process_running", "full_reachability"): "RIP: process → reach",
    ("troubleshoot_ospf_adjacency_issue", "initial_problem_identified", "root_cause_diagnosed"): "OSPF TS: ident → diag",
    ("troubleshoot_ospf_adjacency_issue", "root_cause_diagnosed", "adjacency_restored"): "OSPF TS: diag → adj",
    ("troubleshoot_ospf_adjacency_issue", "adjacency_restored", "full_topology_convergence"): "OSPF TS: adj → conv",
    ("ccnp_multiarea_ospf_intermediate", "ospf_area0_adjacency", "area1_routes_visible"): "Multi-OSPF: area0 → area1",
    ("ccnp_multiarea_ospf_intermediate", "ospf_area0_adjacency", "end_to_end_reachability"): "Multi-OSPF: area0 → reach",
    ("ccnp_multiarea_ospf_intermediate", "ospf_area0_adjacency", "route_summarization"): "Multi-OSPF: area0 → summ",
    ("ccie_bgp_dual_homing_expert", "ebgp_isp1_established", "route_filtering_outbound"): "BGP: ISP1 → filter",
    ("ccie_bgp_dual_homing_expert", "ebgp_isp2_established", "as_path_prepending"): "BGP: ISP2 → prepend",
    ("ccie_bgp_dual_homing_expert", "ebgp_isp1_established", "primary_path_preference"): "BGP: ISP1 → primary",
    ("ccie_bgp_dual_homing_expert", "ebgp_isp2_established", "primary_path_preference"): "BGP: ISP2 → primary",
}


def load_stable_runs() -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for p in sorted(TRAJ_DIR.glob("*.json")):
        d = json.load(p.open())
        if d.get("error") or not d.get("stable"):
            continue
        if d.get("task_id") not in REPORTED_TASKS:
            continue
        runs.append(d)
    return runs


def load_original_cohort_runs() -> list[dict[str, Any]]:
    """All replayed traces that still carry the original terminal vector."""
    runs: list[dict[str, Any]] = []
    for p in sorted(TRAJ_DIR.glob("*.json")):
        d = json.load(p.open())
        if "original_satisfied" not in d:
            continue
        runs.append(d)
    return runs


def original_property_map(run: dict[str, Any], chain: list[str]) -> dict[str, bool]:
    satisfied = set(run.get("original_satisfied") or [])
    return {pid: pid in satisfied for pid in chain}


def stall_frontier_counts(
    runs: list[dict[str, Any]],
    task_prereq_order: dict[str, list[str]] | None = None,
) -> dict[str, Counter]:
    """First unsatisfied property in each task chain, using original terminal state."""
    order = TASK_PREREQ_ORDER if task_prereq_order is None else task_prereq_order
    frontier_counts: dict[str, Counter] = defaultdict(Counter)
    for r in runs:
        t = r.get("task_id")
        if t not in order:
            continue
        term = original_property_map(r, order[t])
        stall = "Fully Achieved"
        for pid in order[t]:
            if not term.get(pid):
                stall = PROPERTY_LABELS.get(pid, pid)
                break
        frontier_counts[t][stall] += 1
    return frontier_counts


def get_model_key(run_id: str) -> str:
    parts = run_id.split("_")
    return f"{parts[0]}_{parts[1]}"


def _save_figure(fig: plt.Figure, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    png_path = out_path.with_suffix(".png")
    pdf_path = out_path.with_suffix(".pdf")
    fig.savefig(png_path, dpi=300, bbox_inches="tight")
    fig.savefig(pdf_path, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {png_path.name} and {pdf_path.name}")


def pad_trajectories(series_list: list[list[float]], max_turns: int = 25) -> np.ndarray:
    padded = []
    for s in series_list:
        if not s:
            s = [0.0]
        if len(s) < max_turns:
            s_ext = s + [s[-1]] * (max_turns - len(s))
        else:
            s_ext = s[:max_turns]
        padded.append(s_ext)
    return np.array(padded)


def plot_figure_3_trajectories(runs: list[dict[str, Any]], out_path: Path) -> None:
    fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(12.2, 5.0), sharey=True)
    max_t = 20
    x = np.arange(1, max_t + 1)

    for model_id in MODEL_ORDER:
        model_runs = [r for r in runs if get_model_key(r["run_id"]) == model_id]
        if not model_runs:
            continue
        series = []
        for r in model_runs:
            snaps = snapshots(r)
            c_vals = [float(s.get("completeness", 0.0)) for s in snaps]
            if not c_vals:
                term = float(r.get("replay_terminal_completeness", 0.0))
                c_vals = [term]
            series.append(c_vals)
        arr = pad_trajectories(series, max_turns=max_t)
        mean = np.mean(arr, axis=0)
        std = np.std(arr, axis=0)
        color = MODEL_COLORS[model_id]
        label = f"{MODEL_LABELS[model_id]} (n={len(model_runs)})"
        ax_a.plot(x, mean, label=label, color=color, linewidth=2.2)
        ax_a.fill_between(
            x,
            np.clip(mean - std, 0.0, 1.0),
            np.clip(mean + std, 0.0, 1.0),
            color=color,
            alpha=0.15,
        )

    ax_a.set_title(r"$\mathbf{a}$  Completeness trajectory by model", fontsize=11, fontweight="bold", loc="left")
    ax_a.set_xlabel("Interaction Turn", fontsize=10)
    ax_a.set_ylabel(r"Property Completeness $C(H_t)$", fontsize=10)
    ax_a.set_xlim(1, max_t)
    ax_a.set_ylim(-0.02, 1.05)
    ax_a.grid(True, linestyle="--", alpha=0.3)
    ax_a.legend(loc="upper left", frameon=True, framealpha=0.9, fontsize=8.5)

    tasks_with_runs = [t for t in TASK_ORDER if t in TASK_PREREQ_ORDER]
    for task_id in tasks_with_runs:
        task_runs = [r for r in runs if r["task_id"] == task_id]
        if not task_runs:
            continue
        series = []
        for r in task_runs:
            snaps = snapshots(r)
            c_vals = [float(s.get("completeness", 0.0)) for s in snaps]
            if not c_vals:
                term = float(r.get("replay_terminal_completeness", 0.0))
                c_vals = [term]
            series.append(c_vals)
        arr = pad_trajectories(series, max_turns=max_t)
        mean = np.mean(arr, axis=0)
        std = np.std(arr, axis=0)
        color = TASK_COLORS[task_id]
        label = f"{TASK_LABELS[task_id]} (n={len(task_runs)})"
        ax_b.plot(x, mean, label=label, color=color, linewidth=2.2)
        ax_b.fill_between(
            x,
            np.clip(mean - std, 0.0, 1.0),
            np.clip(mean + std, 0.0, 1.0),
            color=color,
            alpha=0.15,
        )

    ax_b.set_title(r"$\mathbf{b}$  Completeness trajectory by task", fontsize=11, fontweight="bold", loc="left")
    ax_b.set_xlabel("Interaction Turn", fontsize=10)
    ax_b.set_xlim(1, max_t)
    ax_b.set_ylim(-0.02, 1.05)
    ax_b.grid(True, linestyle="--", alpha=0.3)
    ax_b.legend(loc="center right", frameon=True, framealpha=0.9, fontsize=8.5)
    _save_figure(fig, out_path)


def plot_stall_frontiers(runs: list[dict[str, Any]], out_path: Path) -> None:
    frontier_counts = stall_frontier_counts(runs)
    task_order = [t for t in TASK_ORDER if t in TASK_PREREQ_ORDER]

    y_labels: list[str] = []
    y_counts: list[int] = []
    y_colors: list[str] = []
    separators: list[float] = []
    started = False
    for t in task_order:
        counts = frontier_counts[t]
        if started:
            separators.append(len(y_labels) - 0.5)
        started = True
        chain_labels = [PROPERTY_LABELS.get(pid, pid) for pid in TASK_PREREQ_ORDER[t]]
        ordered_items = [(lab, counts[lab]) for lab in chain_labels if counts[lab]]
        if counts["Fully Achieved"]:
            ordered_items.append(("Fully Achieved", counts["Fully Achieved"]))
        for stall_label, count in ordered_items:
            y_labels.append(f"{TASK_LABELS[t]}: {stall_label}")
            y_counts.append(count)
            y_colors.append("#2ca02c" if "Achieved" in stall_label else TASK_COLORS[t])

    fig, ax = plt.subplots(figsize=(8.6, 6.4))
    ax.barh(range(len(y_labels)), y_counts, color=y_colors, height=0.68, align="center")
    ax.set_yticks(range(len(y_labels)))
    ax.set_yticklabels(y_labels, fontsize=10)
    ax.set_xlabel("Number of runs", fontsize=11)
    ax.invert_yaxis()
    ax.set_xlim(0, max(y_counts) + 2)
    for idx, count in enumerate(y_counts):
        ax.text(count + 0.15, idx, str(count), va="center", fontsize=9, color="#333333")
    for sep in separators:
        ax.axhline(sep, color="#e2e8f0", linewidth=0.9, linestyle="--")
    _save_figure(fig, out_path)


def plot_temporal_ordering(runs: list[dict[str, Any]], out_path: Path) -> None:
    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for run in runs:
        by_task[run["task_id"]].append(run)

    labels: list[str] = []
    before: list[int] = []
    simul: list[int] = []
    after: list[int] = []
    for task_id in TASK_ORDER:
        for up, down in PREREQUISITES.get(task_id, []):
            n_before = 0
            n_simul = 0
            n_after = 0
            for run in by_task.get(task_id, []):
                snaps = snapshots(run)
                if not snaps:
                    continue
                tu = first_true_turn(snaps, up)
                td = first_true_turn(snaps, down)
                if tu is None or td is None:
                    continue
                if tu < td:
                    n_before += 1
                elif tu == td:
                    n_simul += 1
                else:
                    n_after += 1
            labels.append(EDGE_LABELS.get((task_id, up, down), f"{up} → {down}"))
            before.append(n_before)
            simul.append(n_simul)
            after.append(n_after)

    fig, ax = plt.subplots(figsize=(8.8, 6.8))
    y_pos = np.arange(len(labels))
    ax.barh(
        y_pos,
        before,
        color="#2b6cb0",
        height=0.65,
        label=r"Upstream strictly before ($t_{\mathrm{up}} < t_{\mathrm{down}}$)",
    )
    ax.barh(
        y_pos,
        simul,
        left=before,
        color="#dd6b20",
        height=0.65,
        label=r"Simultaneous turn ($t_{\mathrm{up}} = t_{\mathrm{down}}$)",
    )
    ax.barh(
        y_pos,
        after,
        left=[b + s for b, s in zip(before, simul)],
        color="#e53e3e",
        height=0.65,
        label=r"Upstream after downstream (violation)",
    )
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=10)
    ax.set_xlabel("Number of jointly satisfied trajectories", fontsize=11)
    ax.invert_yaxis()
    ax.set_xlim(0, 12)
    ax.legend(loc="lower right", frameon=True, framealpha=0.9, fontsize=9)
    for idx, (b, s, a) in enumerate(zip(before, simul, after)):
        tot = b + s + a
        if tot > 0:
            ax.text(tot + 0.2, idx, f"{tot} (0 viol.)", va="center", fontsize=8.5, color="#2d3748")
        else:
            ax.text(0.15, idx, "0 (stalled)", va="center", fontsize=8.5, color="#718096", fontstyle="italic")
    _save_figure(fig, out_path)


def _copy_to_paper(stems: list[str]) -> None:
    if not PAPER_DIR.exists():
        return
    for stem in stems:
        for ext in (".png", ".pdf"):
            src = OUT_DIR / f"{stem}{ext}"
            if src.exists():
                dst = PAPER_DIR / f"{stem}{ext}"
                shutil.copy2(src, dst)
                print(f"Copied {src.name} -> {dst}")


def main() -> None:
    runs = load_stable_runs()
    print(f"Loaded {len(runs)} stable runs for plotting.")
    plot_figure_3_trajectories(runs, OUT_DIR / "fig3_coherence_curves.png")
    original_runs = load_original_cohort_runs()
    print(
        f"Loaded {len(original_runs)} runs with original terminal vectors for stall frontiers."
    )
    plot_stall_frontiers(original_runs, OUT_DIR / "fig4_stall_frontiers.png")
    plot_temporal_ordering(runs, OUT_DIR / "fig4_temporal_ordering.png")
    _copy_to_paper(
        ["fig3_coherence_curves", "fig4_stall_frontiers", "fig4_temporal_ordering"]
    )


if __name__ == "__main__":
    main()
