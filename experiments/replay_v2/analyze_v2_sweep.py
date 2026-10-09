"""Figures and tables for the 60-run OpenRouter sweep (content-classified revision).

Reads results/v2_openrouter/runs. Terminal completeness comes from property_results,
scored after the convergence wait. Trajectory events come from the live per-command
snapshots (metrics.property_trajectory).

Revision (vs the first version of this script):
  * Commands are classified by CONTENT with analyze_process.classify, not by the
    agent-supplied read/config label. Agents sent state changes through the read
    channel (no snapshot, no turn counted) and labelled pure `show` commands as config.
  * Snapshots are aligned to the command that produced them. Snapshots taken after a
    read-only command are dropped from event shares; state changes sent as reads are
    reported separately because no snapshot exists for them.
  * Progress curves use each run's own progress (share of its state-changing commands
    issued) instead of an absolute command index, which averaged over a shrinking set of
    runs (survivorship: the tail was set by the one or two slowest runs). Every run is
    drawn and the end-of-run check (after the convergence wait) is shown.
  * Grouped mean +/- s.d. bars (n = 3) are replaced by one dot per run.
  * The terminal-pattern figure now shows the saturation directly (task x model grid)
    next to the property patterns of the runs that did not finish.

  * Snapshot alignment is shared with analyze_process.py (snapshots.py) and handles both
    harness policies: 'labelled' (untaxed cohort) and 'all' (taxed cohort, a snapshot after
    every command). The policy is detected per cohort; --snapshot-mode overrides it.

Output file names are unchanged so manuscript references keep working.
"""

from __future__ import annotations

import csv
import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

from analyze_process import classify  # noqa: E402
from snapshots import aligned, run_snapshot_mode, set_cohort_mode, snapshot_mode  # noqa: E402

# Set in main from the cohort: 'labelled' (snapshot ~2 s after config-labelled commands) or
# 'all' (taxed harness: snapshot right after every command, reads included).
COHORT_MODE = "labelled"

RUNS_DIR = REPO / "results" / "v2_openrouter" / "runs"
OUT_DIR = HERE / "out" / "v2_openrouter_analysis"
PAPER_DIR = Path.home() / "Documents" / "papers" / "benchmark_paper" / "scientific_reports"
V2_DIR = REPO / "tasks" / "multi_turn_v2"

TASK_ORDER = [
    "ccna_rip_routing_basic",
    "troubleshoot_ospf_adjacency_issue",
    "ccnp_multiarea_ospf_intermediate",
    "ccie_bgp_dual_homing_expert",
    "troubleshoot_bgp_route_filtering",
]
TASK_LABELS = {
    "ccna_rip_routing_basic": "RIP",
    "troubleshoot_ospf_adjacency_issue": "OSPF adjacency",
    "ccnp_multiarea_ospf_intermediate": "Multi-area OSPF",
    "ccie_bgp_dual_homing_expert": "BGP dual-homing",
    "troubleshoot_bgp_route_filtering": "BGP filtering",
}
MODEL_ORDER = [
    "qwen/qwen3.8-flash",
    "google/gemini-3.1-flash-lite",
    "openai/gpt-6-luna",
    "z-ai/glm-5.3",
]
MODEL_LABELS = {
    "qwen/qwen3.8-flash": "Qwen3.8 Flash",
    "google/gemini-3.1-flash-lite": "Gemini 3.1 Flash Lite",
    "openai/gpt-6-luna": "GPT-6 Luna",
    "z-ai/glm-5.3": "GLM 5.3",
}
MODEL_COLORS = {
    "qwen/qwen3.8-flash": "#E69F00",
    "google/gemini-3.1-flash-lite": "#56B4E9",
    "openai/gpt-6-luna": "#009E73",
    "z-ai/glm-5.3": "#CC79A7",
}
# second cue for the colour pair that sits in the colour-vision-deficiency floor band
MODEL_MARKERS = {
    "qwen/qwen3.8-flash": "o",
    "google/gemini-3.1-flash-lite": "s",
    "openai/gpt-6-luna": "^",
    "z-ai/glm-5.3": "D",
}
EVENT_COLORS = {"advanced": "#2b6cb0", "no visible change": "#cfcfca", "lost a property": "#D55E00"}
INK, MUTED, GRID = "#1f1f1e", "#6b6b68", "#e4e4e1"

# Palettes used when --models overrides the built-in cohort (mirrors analyze_process.py).
PROCESS_PALETTE = ["#E69F00", "#56B4E9", "#009E73", "#CC79A7", "#0072B2", "#D55E00"]
PROCESS_MARKERS = ["o", "s", "^", "D", "v", "P"]
PROPERTY_LABELS = {
    # RIP (ccna_rip_routing_basic)
    "rip_enabled": "RIP up",
    "ripv2_enforced": "RIPv2",
    "rip_authentication": "auth",
    "r4_loopback_via_rip": "R4 via RIP",
    "loopback_reachability": "ping",
    # OSPF adjacency troubleshooting (troubleshoot_ospf_adjacency_issue)
    "fault_corrected": "area fixed",
    "r2_r3_adjacency_full": "adjacency",
    "r2_uses_restored_link": "restored link",
    "topology_reconverged": "converged",
    # multi-area OSPF (ccnp_multiarea_ospf_intermediate)
    "backbone_adjacencies_full": "backbone adj",
    "area1_adjacency_full": "area1 adj",
    "area2_adjacency_full": "area2 adj",
    "interarea_routes_in_backbone": "inter-area routes",
    "area1_to_area2_reachability": "a1<->a2 ping",
    "area1_summarized": "area1 summary",
    "area2_summarized": "area2 summary",
    # BGP dual-homing (ccie_bgp_dual_homing_expert)
    "ebgp_isp1_established": "eBGP ISP1",
    "ebgp_isp2_established": "eBGP ISP2",
    "outbound_filtering": "filter",
    "primary_path_preference": "local-pref",
    "as_path_prepending": "prepend",
    "fast_failover_timers": "timers",
    # BGP route filtering (troubleshoot_bgp_route_filtering)
    "filter_applied_outbound": "filter out",
    "isp_receives_authorized_only": "authorized only",
}


def model_slug(raw: str) -> str:
    text = raw or ""
    if text.startswith("openrouter:"):
        text = text.split(":", 1)[1]
    return text


def load_property_order() -> dict[str, list[str]]:
    order = {}
    for task_id in TASK_ORDER:
        data = json.loads((V2_DIR / f"{task_id}.json").read_text())
        order[task_id] = [p["id"] for p in data["intent"]["properties"]]
    return order


def bucket(vector: dict[str, bool]) -> str:
    if not vector or not any(vector.values()):
        return "zero"
    if all(vector.values()):
        return "complete"
    return "partial"


# --------------------------------------------------------------------- alignment
def aligned_events(data: dict[str, Any]) -> dict[str, Any]:
    """One event per state-changing command that has a snapshot.

    'labelled' runs (snapshot ~2 s after each config-labelled command): snapshots after
    read-only commands are kept as observations of state but are not events. Each write
    snapshot is compared with the previous snapshot, so a change that arrived through a
    hidden write or through convergence since then is credited to the next observed write.
    State changes sent as reads have no snapshot and are counted as 'unseen'.

    'all' runs (snapshot right after every command): the effect of a write is its window,
    from the snapshot before it to the last snapshot before the next write. Changes that
    surface while the agent reads (convergence) are credited to the write that caused them.
    Every write is observed, including those sent as reads.
    """
    ct = data.get("command_transcript") or []
    al = aligned(data, classify)
    mode = snapshot_mode(data)
    events: list[dict[str, Any]] = []
    ever_true: set[str] = set()
    phantom = sum(1 for a in al if a["command"].get("command_type") == "config" and a["kind"] != "write")
    if mode == "all":
        w_pos = [a["pos"] for a in al if a["kind"] == "write"]
        for n, wp in enumerate(w_pos):
            end = (w_pos[n + 1] - 1) if n + 1 < len(w_pos) else len(al) - 1
            window = al[wp:end + 1]
            before = al[wp - 1]["properties"] if wp > 0 else {}
            ever_true |= {k for a in al[:wp] for k, v in a["properties"].items() if v}
            seq = [before] + [a["properties"] for a in window]
            lost = sorted({k for x, y in zip(seq, seq[1:]) for k, v in x.items() if v and not y.get(k)})
            gained_first = sorted({k for a in window for k, v in a["properties"].items()
                                   if v and k not in ever_true})
            kind = "lost a property" if lost else ("advanced" if gained_first else "no visible change")
            events.append({"turn": window[-1]["snapshot"].get("turn"), "kind": kind, "gained": gained_first,
                           "lost": lost, "completeness": window[-1]["completeness"]})
            ever_true |= set(gained_first)
        unseen = 0
    else:
        prev: dict[str, bool] = {}
        for a in al:
            props = a["properties"]
            if a["kind"] != "write":
                prev = props  # still a valid observation of state; not a command event
                ever_true |= {k for k, v in props.items() if v}
                continue
            gained_first = [k for k, v in props.items() if v and k not in ever_true]
            lost = [k for k, v in prev.items() if v and not props.get(k)]
            kind = "lost a property" if lost else ("advanced" if gained_first else "no visible change")
            events.append({"turn": a["snapshot"].get("turn"), "kind": kind, "gained": gained_first, "lost": lost,
                           "completeness": a["completeness"]})
            ever_true |= set(gained_first)
            prev = props
        unseen = sum(1 for c in ct if c.get("command_type") == "read" and classify(c["command"]) == "write")
    hidden = sum(1 for c in ct if c.get("command_type") == "read" and classify(c["command"]) == "write")
    writes = sum(1 for c in ct if classify(c["command"]) == "write")
    labelled = sum(1 for c in ct if c.get("command_type") == "config")
    return {"events": events, "phantom_snapshots": phantom, "hidden_writes": hidden, "unseen_writes": unseen,
            "writes": writes, "labelled_config": labelled, "snapshot_mode": mode}


def load_runs() -> list[dict[str, Any]]:
    rows = []
    for path in sorted(RUNS_DIR.glob("*/*.json")):
        data = json.loads(path.read_text())
        metrics = data.get("metrics") or {}
        vector = {
            str(item["property_id"]): bool(item.get("satisfied"))
            for item in data.get("property_results") or []
            if item.get("property_id")
        }
        completeness = float((data.get("scoring") or {}).get("completeness") or 0.0)
        al = aligned_events(data)
        n_ev = len(al["events"])
        shares = {k: (sum(e["kind"] == k for e in al["events"]) / n_ev if n_ev else 0.0) for k in EVENT_COLORS}
        rows.append({
            "run_id": data.get("run_id") or path.stem,
            "task_id": data.get("task_id") or path.parent.name,
            "model": model_slug(str(data.get("model_version") or "")),
            "completeness": completeness,
            "bucket": bucket(vector),
            "vector": vector,
            "writes": al["writes"],
            "labelled_config": al["labelled_config"],
            "hidden_writes": al["hidden_writes"],
            "unseen_writes": al["unseen_writes"],
            "snapshot_mode": al["snapshot_mode"],
            "phantom_snapshots": al["phantom_snapshots"],
            "seconds": metrics.get("time_to_complete"),
            "provision_seconds": metrics.get("infrastructure_provision_time"),
            "termination": metrics.get("termination_reason"),
            "events": al["events"],
            "shares": shares,
        })
    return rows


def _mean(values: list[float]) -> float:
    return float(np.mean(values)) if values else 0.0


def _std(values: list[float]) -> float:
    return float(np.std(values, ddof=1)) if len(values) > 1 else 0.0


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_task: dict[str, dict[str, Any]] = {}
    for task_id in TASK_ORDER:
        group = [row for row in rows if row["task_id"] == task_id]
        counts = {name: sum(1 for row in group if row["bucket"] == name) for name in ("complete", "partial", "zero")}
        by_task[task_id] = {"n": len(group), **counts,
                            "mean_c": _mean([row["completeness"] for row in group]),
                            "std_c": _std([row["completeness"] for row in group])}
    cells = []
    for task_id in TASK_ORDER:
        for model in MODEL_ORDER:
            group = [row for row in rows if row["task_id"] == task_id and row["model"] == model]
            events = [e for row in group for e in row["events"]]
            cells.append({
                "task_id": task_id, "model": model, "n": len(group),
                "complete": sum(row["bucket"] == "complete" for row in group),
                "partial": sum(row["bucket"] == "partial" for row in group),
                "zero": sum(row["bucket"] == "zero" for row in group),
                "mean_c": _mean([row["completeness"] for row in group]),
                "median_writes": float(np.median([row["writes"] for row in group])) if group else 0.0,
                "median_labelled_config": float(np.median([row["labelled_config"] for row in group])) if group else 0.0,
                "hidden_writes": sum(row["hidden_writes"] for row in group),
                "unseen_writes": sum(row["unseen_writes"] for row in group),
                "phantom_snapshots": sum(row["phantom_snapshots"] for row in group),
                "median_seconds": float(np.median([row["seconds"] for row in group if row["seconds"] is not None]))
                if group else 0.0,
                # pooled over the cell's observed write events
                "n_write_events": len(events),
                **{f"share_{k.replace(' ', '_')}": (sum(e["kind"] == k for e in events) / len(events) if events else 0.0)
                   for k in EVENT_COLORS},
            })
    return {"by_task": by_task, "cells": cells, "n_runs": len(rows)}


# --------------------------------------------------------------------- styling
def _style(ax, grid_axis="x"):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
        ax.spines[s].set_linewidth(0.6)
    ax.tick_params(colors=MUTED, labelsize=7, width=0.6, length=2.5)
    if grid_axis:
        ax.grid(axis=grid_axis, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def _model_handles(extra=()):
    hs = [Line2D([], [], marker=MODEL_MARKERS[m], color=MODEL_COLORS[m], linestyle="", markersize=6,
                 label=MODEL_LABELS[m]) for m in MODEL_ORDER]
    return hs + list(extra)


# --------------------------------------------------------------------- figures
def plot_signatures(rows, prop_order, path):
    """a: terminal completeness of every run (task x model); b: patterns of incomplete runs."""
    fig = plt.figure(figsize=(7.2, 5.2))
    gs = fig.add_gridspec(2, 1, height_ratios=[1.35, 1.0], hspace=0.5)
    ax = fig.add_subplot(gs[0])
    cmap = plt.get_cmap("Blues")
    for i, task_id in enumerate(TASK_ORDER):
        for j, model in enumerate(MODEL_ORDER):
            group = sorted([r for r in rows if r["task_id"] == task_id and r["model"] == model],
                           key=lambda r: r["run_id"])
            for k, r in enumerate(group):
                x0 = j + k / 3.0
                ax.add_patch(plt.Rectangle((x0 + 0.02, i + 0.08), 1 / 3.0 - 0.04, 0.84,
                                           color=cmap(0.15 + 0.75 * r["completeness"]), linewidth=0))
                if r["completeness"] < 1 - 1e-9:
                    ax.text(x0 + 1 / 6.0, i + 0.5, f"{r['completeness']:.2f}", ha="center", va="center",
                            fontsize=5.5, color=INK, rotation=90)
    ax.set_xlim(0, len(MODEL_ORDER))
    ax.set_ylim(len(TASK_ORDER), 0)
    ax.set_xticks([j + 0.5 for j in range(len(MODEL_ORDER))])
    ax.set_xticklabels([MODEL_LABELS[m] for m in MODEL_ORDER], fontsize=7, color=INK)
    ax.set_yticks([i + 0.5 for i in range(len(TASK_ORDER))])
    ax.set_yticklabels([TASK_LABELS[t] for t in TASK_ORDER], fontsize=7, color=INK)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    n_c = sum(r["bucket"] == "complete" for r in rows)
    ax.set_title(f"a  End-of-run completeness, every run\n({n_c}/{len(rows)} runs at C = 1.00; "
                 "numbers mark the rest)", fontsize=7.5, loc="left", color=INK)

    ax2 = fig.add_subplot(gs[1])
    incomplete = [r for r in rows if r["bucket"] != "complete"]
    y = 0
    labels = []
    for r in sorted(incomplete, key=lambda r: (TASK_ORDER.index(r["task_id"]), r["model"], r["run_id"])):
        keys = prop_order[r["task_id"]]
        for j, key in enumerate(keys):
            held = r["vector"].get(key, False)
            ax2.add_patch(plt.Rectangle((j + 0.04, y + 0.1), 0.92, 0.8,
                                        color="#2b6cb0" if held else "#eef2f7", linewidth=0))
            ax2.text(j + 0.5, y + 0.5, PROPERTY_LABELS.get(key, key), ha="center", va="center", fontsize=6.3,
                     color="white" if held else MUTED)
        labels.append(f"{TASK_LABELS[r['task_id']]}\n{MODEL_LABELS[r['model']]}, C = {r['completeness']:.2f}")
        y += 1
    ax2.set_xlim(0, max(len(prop_order[r["task_id"]]) for r in incomplete) if incomplete else 1)
    ax2.set_ylim(max(y, 1), 0)
    ax2.set_yticks([i + 0.5 for i in range(y)])
    ax2.set_yticklabels(labels, fontsize=6.3, color=INK)
    ax2.set_xticks([])
    ax2.tick_params(length=0)
    for s in ax2.spines.values():
        s.set_visible(False)
    ax2.set_title("b  Which properties the unfinished runs held\n(dark = true at the end of the run)",
                  fontsize=7.5, loc="left", color=INK)
    fig.subplots_adjust(left=0.24, right=0.98, top=0.92, bottom=0.03)
    fig.savefig(path)
    fig.savefig(path.with_suffix(".png"), dpi=220)
    plt.close(fig)


def plot_curves(rows, path):
    """Per-run progress: x = share of the run's own state-changing commands issued."""
    fig, axes = plt.subplots(1, len(TASK_ORDER), figsize=(7.4, 2.5), sharey=True)
    for ax, task_id in zip(axes, TASK_ORDER):
        _style(ax, grid_axis="y")
        for model in MODEL_ORDER:
            for r in sorted([r for r in rows if r["task_id"] == task_id and r["model"] == model],
                            key=lambda r: r["run_id"]):
                ev = r["events"]
                if not ev:
                    continue
                n = len(ev)
                xs = [0.0] + [(i + 1) / n for i in range(n)]
                ys = [0.0] + [e["completeness"] for e in ev]
                ax.step(xs, ys, where="post", color=MODEL_COLORS[model], linewidth=1.1, alpha=0.75)
                ax.plot(1.3, r["completeness"], marker=MODEL_MARKERS[model], color=MODEL_COLORS[model],
                        markerfacecolor=MODEL_COLORS[model] if r["completeness"] >= 1 - 1e-9 else "white",
                        markersize=4.5, markeredgewidth=0.9, alpha=0.9, linestyle="")
        ax.axvline(1.15, color=GRID, linewidth=0.8)
        ax.set_xlim(-0.02, 1.38)
        ax.set_ylim(-0.04, 1.06)
        ax.set_xticks([0, 0.5, 1.0, 1.3])
        ax.set_xticklabels(["0", "50%", "100%", "end"], fontsize=6)
        ax.set_title(TASK_LABELS[task_id], fontsize=7.5, color=INK)
        ax.set_xlabel("state-changing\ncommands issued", fontsize=6.5, color=INK)
    axes[0].set_ylabel("fraction of properties true", fontsize=7, color=INK)
    fig.legend(handles=_model_handles([Line2D([], [], color=MUTED, lw=1.1,
                                              label="state just before the agent's next change"
                                              if COHORT_MODE == "all" else
                                              "per-command snapshot (~2 s after the command)")]),
               loc="upper center", ncol=5, frameon=False, fontsize=6.5, bbox_to_anchor=(0.5, 1.02))
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    fig.savefig(path)
    fig.savefig(path.with_suffix(".png"), dpi=220)
    plt.close(fig)


def plot_time_turns(rows, path):
    """One dot per run. a: state-changing commands (content); x = the agent's own config count."""
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.3), sharey=True)
    for ax in axes:
        _style(ax)
    for i, task_id in enumerate(TASK_ORDER):
        for j, model in enumerate(MODEL_ORDER):
            group = sorted([r for r in rows if r["task_id"] == task_id and r["model"] == model],
                           key=lambda r: r["run_id"])
            for k, r in enumerate(group):
                y = i + (j - 1.5) * 0.18 + (k - 1) * 0.045
                face = MODEL_COLORS[model] if r["bucket"] == "complete" else "white"
                axes[0].plot(max(r["writes"], 0.8), y, marker=MODEL_MARKERS[model], color=MODEL_COLORS[model],
                             markerfacecolor=face, markersize=4.8, markeredgewidth=0.9, linestyle="")
                if r["labelled_config"] != r["writes"]:
                    axes[0].plot([max(r["writes"], 0.8), max(r["labelled_config"], 0.8)], [y, y],
                                 color=MUTED, linewidth=0.6, zorder=0)
                    axes[0].plot(max(r["labelled_config"], 0.8), y, marker="x", color=INK, markersize=3.5,
                                 markeredgewidth=0.8, linestyle="")
                axes[1].plot(r["seconds"] / 60.0, y, marker=MODEL_MARKERS[model], color=MODEL_COLORS[model],
                             markerfacecolor=face, markersize=4.8, markeredgewidth=0.9, linestyle="")
    for ax in axes:
        ax.set_xscale("log")
        ax.set_yticks(range(len(TASK_ORDER)))
        ax.set_yticklabels([TASK_LABELS[t] for t in TASK_ORDER], fontsize=7, color=INK)
        ax.set_ylim(len(TASK_ORDER) - 0.5, -0.5)
        for b in range(len(TASK_ORDER) - 1):
            ax.axhline(b + 0.5, color=GRID, linewidth=0.6)
    axes[0].set_xticks([1, 2, 5, 10, 20, 50])
    axes[0].set_xticklabels(["1", "2", "5", "10", "20", "50"])
    axes[0].set_xlabel("state-changing commands (by content, log)", fontsize=7, color=INK)
    axes[1].set_xticks([0.2, 0.5, 1, 2, 5, 10, 20, 30])
    axes[1].set_xticklabels(["0.2", "0.5", "1", "2", "5", "10", "20", "30"])
    axes[1].set_xlabel("wall time inside the session (minutes, log)", fontsize=7, color=INK)
    extra = [Line2D([], [], marker="x", color=INK, linestyle="", markersize=4,
                    label="agent's own 'config' count, where different"),
             Line2D([], [], marker="o", markerfacecolor="white", markeredgecolor=MUTED, linestyle="",
                    markersize=5, label="run ended below C = 1.0")]
    fig.legend(handles=_model_handles(extra), loc="upper center", ncol=3, frameon=False, fontsize=6.5,
               bbox_to_anchor=(0.5, 1.02))
    fig.tight_layout(rect=(0, 0, 1, 0.86))
    fig.savefig(path)
    fig.savefig(path.with_suffix(".png"), dpi=220)
    plt.close(fig)


def plot_path_events(cells, path):
    """100% bars per task x model: what each observed state-changing command did."""
    fig, axes = plt.subplots(1, len(TASK_ORDER), figsize=(7.4, 2.6), sharey=True)
    kinds = list(EVENT_COLORS)
    for ax, task_id in zip(axes, TASK_ORDER):
        _style(ax, grid_axis=None)
        for yi, model in enumerate(MODEL_ORDER):
            cell = next(c for c in cells if c["task_id"] == task_id and c["model"] == model)
            left = 0.0
            for k in kinds:
                w = cell[f"share_{k.replace(' ', '_')}"]
                ax.barh(yi, w, left=left, color=EVENT_COLORS[k], height=0.66, edgecolor="white", linewidth=1.0)
                left += w
            note = f"n={cell['n_write_events']}"
            if cell["unseen_writes"]:
                note += f" +{cell['unseen_writes']} unseen"
            ax.text(1.02, yi, note, va="center", fontsize=5.6, color=MUTED)
        ax.set_xlim(0, 1.0)
        ax.set_xticks([0, 1])
        ax.set_xticklabels(["0", "100%"], fontsize=6.5)
        ax.set_yticks(range(len(MODEL_ORDER)))
        ax.set_yticklabels([MODEL_LABELS[m] for m in MODEL_ORDER], fontsize=6.8, color=INK)
        ax.invert_yaxis()
        ax.set_title(TASK_LABELS[task_id], fontsize=7.5, color=INK)
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", length=0)
    handles = [plt.Rectangle((0, 0), 1, 1, color=EVENT_COLORS[k], label=lab) for k, lab in
               zip(kinds, ["made a property true for the first time",
                           "no visible change before the next change" if COHORT_MODE == "all"
                           else "no visible change within ~2 s",
                           "a true property became false"])]
    fig.legend(handles=handles, loc="upper center", ncol=3, frameon=False, fontsize=6.5, bbox_to_anchor=(0.5, 1.02))
    note = ("n = state-changing commands; each is judged over its window, up to the next change "
            "(snapshots after every command)" if COHORT_MODE == "all" else
            "n = state-changing commands with a snapshot; 'unseen' = state changes the agent sent "
            "as reads (no snapshot exists)")
    fig.text(0.99, 0.01, note, ha="right", fontsize=5.6, color=MUTED)
    fig.tight_layout(rect=(0, 0.04, 0.97, 0.88), w_pad=1.6)
    fig.savefig(path)
    fig.savefig(path.with_suffix(".png"), dpi=220)
    plt.close(fig)


# --------------------------------------------------------------------- tables
def write_tables(rows, summary, out_dir):
    with (out_dir / "per_run.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "run_id", "task_id", "model", "bucket", "completeness", "writes", "labelled_config",
            "hidden_writes", "unseen_writes", "snapshot_mode", "phantom_snapshots", "seconds", "provision_seconds", "termination",
            "share_advanced", "share_no_visible_change", "share_lost_a_property", "events",
        ])
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "run_id": row["run_id"], "task_id": row["task_id"], "model": row["model"],
                "bucket": row["bucket"], "completeness": f"{row['completeness']:.4f}",
                "writes": row["writes"], "labelled_config": row["labelled_config"],
                "hidden_writes": row["hidden_writes"], "unseen_writes": row["unseen_writes"],
                "snapshot_mode": row["snapshot_mode"], "phantom_snapshots": row["phantom_snapshots"],
                "seconds": None if row["seconds"] is None else f"{float(row['seconds']):.2f}",
                "provision_seconds": None if row["provision_seconds"] is None
                else f"{float(row['provision_seconds']):.2f}",
                "termination": row["termination"],
                **{f"share_{k.replace(' ', '_')}": f"{row['shares'][k]:.4f}" for k in EVENT_COLORS},
                "events": json.dumps([{k: e[k] for k in ("turn", "kind", "gained", "lost")} for e in row["events"]]),
            })
    with (out_dir / "by_task_model.csv").open("w", newline="") as handle:
        fields = list(summary["cells"][0].keys())
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summary["cells"])
    (out_dir / "numbers.json").write_text(json.dumps(
        {"n_runs": summary["n_runs"], "by_task": summary["by_task"], "cells": summary["cells"]}, indent=2))


def main() -> None:
    global RUNS_DIR, V2_DIR, COHORT_MODE, MODEL_ORDER, MODEL_LABELS, MODEL_COLORS, MODEL_MARKERS
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs-dir", type=Path, default=RUNS_DIR)
    ap.add_argument("--tasks-dir", type=Path, default=V2_DIR)
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    ap.add_argument("--paper-dir", type=Path, default=PAPER_DIR,
                    help="copy the PDFs here if the folder exists (default: the manuscript folder)")
    ap.add_argument("--snapshot-mode", choices=["auto", "all", "labelled"], default="auto",
                    help="harness snapshot policy; auto = 'all' if every run has one snapshot per command")
    ap.add_argument("--models", default=None,
                    help="comma-separated model ids, e.g. 'openai/gpt-5-mini,meta-llama/llama-3.3-70b-instruct'. "
                         "Overrides the built-in MODEL_ORDER; labels, colours and markers are assigned automatically.")
    args = ap.parse_args()
    if args.models:
        MODEL_ORDER = [m.strip() for m in args.models.split(",") if m.strip()]
        MODEL_LABELS = {m: m.split("/")[-1].replace("-", " ") for m in MODEL_ORDER}
        MODEL_COLORS = {m: PROCESS_PALETTE[i % len(PROCESS_PALETTE)] for i, m in enumerate(MODEL_ORDER)}
        MODEL_MARKERS = {m: PROCESS_MARKERS[i % len(PROCESS_MARKERS)] for i, m in enumerate(MODEL_ORDER)}
    RUNS_DIR, V2_DIR = args.runs_dir, args.tasks_dir
    COHORT_MODE = set_cohort_mode((json.loads(p.read_text()) for p in sorted(RUNS_DIR.glob("*/*.json"))),
                                  args.snapshot_mode)
    print(f"snapshot mode: {COHORT_MODE}")
    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = load_runs()
    if len(rows) != 60:
        raise SystemExit(f"expected 60 runs, found {len(rows)}")
    summary = aggregate(rows)
    prop_order = load_property_order()
    write_tables(rows, summary, out_dir)
    figures = {
        "fig2_partial_signatures.pdf": lambda p: plot_signatures(rows, prop_order, p),
        "fig3_coherence_curves.pdf": lambda p: plot_curves(rows, p),
        "fig_time_turns.pdf": lambda p: plot_time_turns(rows, p),
        "fig_path_events.pdf": lambda p: plot_path_events(summary["cells"], p),
    }
    for name, draw in figures.items():
        target = out_dir / name
        draw(target)
        if args.paper_dir and args.paper_dir.is_dir():
            shutil.copy(target, args.paper_dir / name)
    print(f"wrote {len(rows)} runs to {out_dir}")


if __name__ == "__main__":
    main()
