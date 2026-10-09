"""RQ2: terminal intent-property resolution on the single-agent cohort."""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNS_DIR = REPO_ROOT / "results" / "comparatives_all" / "runs"
DEFAULT_OUT_DIR = Path(__file__).resolve().parent / "out"
PAPER_DIR = (
    Path.home() / "Documents" / "papers" / "benchmark_paper" / "scientific_reports"
)
DEFAULT_PAPER_FIGURE = PAPER_DIR / "fig2_completeness_classes.png"

PATTERN_RE = re.compile(
    r"(single|multi_sequential|multi_debate|multi_group_chat|multi_concurrent)_mt_"
)

TASK_ORDER = [
    "ccna_rip_routing_basic",
    "troubleshoot_ospf_adjacency_issue",
    "ccnp_multiarea_ospf_intermediate",
    "ccie_bgp_dual_homing_expert",
    "troubleshoot_bgp_route_filtering",
]

TASK_LABELS = {
    "ccna_rip_routing_basic": "RIP",
    "troubleshoot_ospf_adjacency_issue": "OSPF TS",
    "ccnp_multiarea_ospf_intermediate": "Multi-area OSPF",
    "ccie_bgp_dual_homing_expert": "BGP dual-homing",
    "troubleshoot_bgp_route_filtering": "BGP filtering",
}

PROPERTY_LABELS = {
    "rip_process_running": "RIP process",
    "ripv2_configured": "RIPv2",
    "rip_routes_learned": "RIP routes",
    "full_reachability": "RIP reach.",
    "initial_problem_identified": "OSPF TS ident.",
    "root_cause_diagnosed": "OSPF TS diag.",
    "adjacency_restored": "OSPF TS adj.",
    "full_topology_convergence": "OSPF TS conv.",
    "ospf_area0_adjacency": "area-0 adj.",
    "area1_routes_visible": "area-1 routes",
    "end_to_end_reachability": "OSPF e2e",
    "route_summarization": "summarization",
    "ebgp_isp1_established": "eBGP ISP1",
    "ebgp_isp2_established": "eBGP ISP2",
    "route_filtering_outbound": "outbound filter",
    "primary_path_preference": "primary path",
    "as_path_prepending": "AS-path prepend",
    "convergence_time_optimized": "BGP conv.",
    "problem_identified": "BGP filter ident.",
    "route_map_issue_diagnosed": "BGP filter diag.",
    "route_map_applied": "route-map",
    "filtering_verified": "filtering_verified",
    "internal_routes_blocked": "internal blocked",
}

# Declared upstream -> downstream necessity relations. Diagnostic, not causal.
# BGP filtering is omitted: the chain is degenerate under the current predicates.
PREREQUISITES: dict[str, list[tuple[str, str]]] = {
    "ccna_rip_routing_basic": [
        ("rip_process_running", "rip_routes_learned"),
        ("ripv2_configured", "rip_routes_learned"),
        ("rip_routes_learned", "full_reachability"),
        ("rip_process_running", "full_reachability"),
    ],
    "ccnp_multiarea_ospf_intermediate": [
        ("ospf_area0_adjacency", "end_to_end_reachability"),
        ("ospf_area0_adjacency", "area1_routes_visible"),
        ("ospf_area0_adjacency", "route_summarization"),
    ],
    "troubleshoot_ospf_adjacency_issue": [
        ("initial_problem_identified", "root_cause_diagnosed"),
        ("root_cause_diagnosed", "adjacency_restored"),
        ("adjacency_restored", "full_topology_convergence"),
    ],
    "ccie_bgp_dual_homing_expert": [
        ("ebgp_isp1_established", "route_filtering_outbound"),
        ("ebgp_isp2_established", "as_path_prepending"),
        ("ebgp_isp1_established", "primary_path_preference"),
        ("ebgp_isp2_established", "primary_path_preference"),
    ],
}

RESOLUTION_COLORS = {
    "complete": "#2b6cb0",
    "partial": "#c05621",
    "zero": "#4a5568",
}

TASK_COLORS = {
    "ccna_rip_routing_basic": "#1b9e77",
    "troubleshoot_ospf_adjacency_issue": "#d95f02",
    "ccnp_multiarea_ospf_intermediate": "#7570b3",
    "ccie_bgp_dual_homing_expert": "#e7298a",
    "troubleshoot_bgp_route_filtering": "#66a61e",
}


def infer_pattern(run_id: str) -> str:
    match = PATTERN_RE.search(run_id or "")
    if not match:
        return "unknown"
    token = match.group(1)
    return {
        "single": "single",
        "multi_sequential": "sequential",
        "multi_debate": "debate",
        "multi_group_chat": "group_chat",
        "multi_concurrent": "concurrent",
    }.get(token, token)


def is_adaptive_pattern_run(result: dict[str, Any]) -> bool:
    return "_multi_adaptive" in str(result.get("testee_id", "")).lower()


def is_gpt5_nano_run(result: dict[str, Any]) -> bool:
    rid = str(result.get("run_id", "")).lower()
    if "gpt5nano" in rid or "gpt-5-nano" in rid:
        return True
    model_src = (
        result.get("model_version")
        or (result.get("agent_config") or {}).get("model")
        or ""
    )
    mv = str(model_src).lower()
    return "gpt5nano" in mv or "gpt-5-nano" in mv


def is_single_agent_run(result: dict[str, Any]) -> bool:
    if is_gpt5_nano_run(result) or is_adaptive_pattern_run(result):
        return False
    return infer_pattern(str(result.get("run_id", ""))) == "single"


def completeness_from_properties(property_results: Sequence[dict[str, Any]]) -> float:
    props = [p for p in property_results if p.get("property_id")]
    if not props:
        return 0.0
    satisfied = sum(1 for p in props if p.get("satisfied"))
    return satisfied / len(props)


def classify_completeness(score: float) -> str:
    if score >= 1.0 - 1e-12:
        return "complete"
    if score > 0.0:
        return "partial"
    return "zero"


def classify_run(run: dict[str, Any]) -> str:
    return classify_completeness(
        completeness_from_properties(run.get("property_results") or [])
    )


def summarize_resolution(runs: Sequence[dict[str, Any]]) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
    for run in runs:
        task_id = str(run.get("task_id") or "unknown")
        bucket = summary.setdefault(
            task_id, {"n": 0, "complete": 0, "partial": 0, "zero": 0}
        )
        label = classify_run(run)
        bucket["n"] += 1
        bucket[label] += 1
    return summary


def property_rates(
    runs: Sequence[dict[str, Any]], task_id: Optional[str] = None
) -> list[dict[str, Any]]:
    selected = [
        run for run in runs if task_id is None or run.get("task_id") == task_id
    ]
    order: list[str] = []
    counts: dict[str, list[int]] = {}
    for run in selected:
        for prop in run.get("property_results") or []:
            pid = prop.get("property_id")
            if not pid:
                continue
            if pid not in counts:
                order.append(pid)
                counts[pid] = [0, 0]
            counts[pid][1] += 1
            if prop.get("satisfied"):
                counts[pid][0] += 1
    rows: list[dict[str, Any]] = []
    for pid in order:
        satisfied, n = counts[pid]
        row: dict[str, Any] = {
            "property_id": pid,
            "satisfied": satisfied,
            "n": n,
            "rate": (satisfied / n) if n else 0.0,
        }
        if task_id is not None:
            row["task_id"] = task_id
        rows.append(row)
    return rows


def _property_map(run: dict[str, Any]) -> dict[str, bool]:
    return {
        str(prop["property_id"]): bool(prop.get("satisfied"))
        for prop in (run.get("property_results") or [])
        if prop.get("property_id")
    }


def prerequisite_stats(
    runs: Sequence[dict[str, Any]], edges: Sequence[tuple[str, str]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for upstream, downstream in edges:
        n = 0
        n_up = 0
        n_down = 0
        n_both = 0
        violations = 0
        for run in runs:
            props = _property_map(run)
            if upstream not in props or downstream not in props:
                continue
            n += 1
            up = props[upstream]
            down = props[downstream]
            n_up += int(up)
            n_down += int(down)
            n_both += int(up and down)
            violations += int(down and not up)
        p_down_given_up = (n_both / n_up) if n_up else None
        p_up_given_down = (n_both / n_down) if n_down else None
        rows.append(
            {
                "upstream": upstream,
                "downstream": downstream,
                "n": n,
                "n_upstream_true": n_up,
                "n_downstream_true": n_down,
                "n_both": n_both,
                "necessity_violations": violations,
                "necessity_holds": violations == 0,
                "p_down_given_up": p_down_given_up,
                "p_up_given_down": p_up_given_down,
            }
        )
    return rows


def cohort_prerequisite_stats(runs: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for run in runs:
        by_task[str(run.get("task_id") or "unknown")].append(run)
    rows: list[dict[str, Any]] = []
    for task_id, edges in PREREQUISITES.items():
        for row in prerequisite_stats(by_task.get(task_id, []), edges):
            row["task_id"] = task_id
            rows.append(row)
    return rows


def load_single_agent_runs(runs_dir: Path) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for path in sorted(runs_dir.glob("*/*.json")):
        with path.open() as handle:
            data = json.load(handle)
        if not is_single_agent_run(data):
            continue
        if not data.get("task_id"):
            data["task_id"] = path.parent.name
        runs.append(data)
    return runs


def _write_csv(path: Path, rows: Sequence[dict[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key)) for key in fieldnames})


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return f"{value:.6f}"
    return value


def resolution_rows(summary: dict[str, dict[str, int]], runs: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    completeness: dict[str, list[float]] = defaultdict(list)
    for run in runs:
        completeness[str(run.get("task_id") or "unknown")].append(
            completeness_from_properties(run.get("property_results") or [])
        )
    rows: list[dict[str, Any]] = []
    ordered = [tid for tid in TASK_ORDER if tid in summary] + [
        tid for tid in summary if tid not in TASK_ORDER
    ]
    for task_id in ordered:
        bucket = summary[task_id]
        n = bucket["n"] or 1
        scores = completeness.get(task_id, [])
        rows.append(
            {
                "task_id": task_id,
                "task_label": TASK_LABELS.get(task_id, task_id),
                "n": bucket["n"],
                "complete": bucket["complete"],
                "partial": bucket["partial"],
                "zero": bucket["zero"],
                "complete_rate": bucket["complete"] / n,
                "partial_rate": bucket["partial"] / n,
                "zero_rate": bucket["zero"] / n,
                "mean_completeness": (sum(scores) / len(scores)) if scores else 0.0,
            }
        )
    return rows


def all_property_rate_rows(runs: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_tasks = {str(run.get("task_id") or "unknown") for run in runs}
    ordered = [tid for tid in TASK_ORDER if tid in seen_tasks] + sorted(
        seen_tasks - set(TASK_ORDER)
    )
    for task_id in ordered:
        for row in property_rates(runs, task_id):
            row["task_label"] = TASK_LABELS.get(task_id, task_id)
            rows.append(row)
    return rows


def _save_figure(fig: plt.Figure, figure_path: Path) -> None:
    figure_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(figure_path, dpi=300, bbox_inches="tight")
    fig.savefig(figure_path.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def plot_completeness_classes(
    summary_rows: Sequence[dict[str, Any]],
    figure_path: Path,
) -> None:
    labels = [row["task_label"] for row in summary_rows]
    complete = [row["complete_rate"] for row in summary_rows]
    partial = [row["partial_rate"] for row in summary_rows]
    zero = [row["zero_rate"] for row in summary_rows]
    left_partial = complete
    left_zero = [c + p for c, p in zip(complete, partial)]

    fig, ax = plt.subplots(figsize=(8.2, 4.2))
    y = list(range(len(labels)))
    ax.barh(y, complete, color=RESOLUTION_COLORS["complete"], label="Complete", height=0.62)
    ax.barh(
        y,
        partial,
        left=left_partial,
        color=RESOLUTION_COLORS["partial"],
        label="Partial",
        height=0.62,
    )
    ax.barh(
        y,
        zero,
        left=left_zero,
        color=RESOLUTION_COLORS["zero"],
        label="Zero",
        height=0.62,
    )
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=11)
    ax.invert_yaxis()
    ax.set_xlim(0, 1.0)
    ax.set_xlabel("Proportion of runs", fontsize=11)
    ax.legend(
        frameon=False,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.18),
        ncol=3,
        fontsize=10,
    )
    fig.subplots_adjust(top=0.82)
    _save_figure(fig, figure_path)


def plot_property_rates(
    rate_rows: Sequence[dict[str, Any]],
    figure_path: Path,
) -> None:
    y_positions: list[float] = []
    y_labels: list[str] = []
    rates: list[float] = []
    colors: list[str] = []
    separators: list[float] = []
    y = 0.0
    current_task = None
    label_rank = {pid: i for i, pid in enumerate(PROPERTY_LABELS)}
    ordered_rows = sorted(
        rate_rows,
        key=lambda row: (
            TASK_ORDER.index(row["task_id"]) if row["task_id"] in TASK_ORDER else 99,
            label_rank.get(row["property_id"], 99),
        ),
    )
    for row in ordered_rows:
        task_id = row["task_id"]
        if current_task is not None and task_id != current_task:
            separators.append(y - 0.5)
            y += 0.45
        current_task = task_id
        y_positions.append(y)
        task_label = TASK_LABELS.get(task_id, task_id)
        prop_label = PROPERTY_LABELS.get(row["property_id"], row["property_id"])
        y_labels.append(f"{task_label}: {prop_label}")
        rates.append(row["rate"])
        colors.append(TASK_COLORS.get(task_id, "#4a5568"))
        y += 1.0

    fig, ax = plt.subplots(figsize=(8.6, 8.4))
    ax.barh(y_positions, rates, color=colors, height=0.72, align="center")
    ax.set_yticks(y_positions)
    ax.set_yticklabels(y_labels, fontsize=10)
    ax.set_xlim(0, 1.02)
    ax.set_xlabel("Satisfaction rate", fontsize=11)
    ax.invert_yaxis()
    for sep in separators:
        ax.axhline(sep, color="#e2e8f0", linewidth=0.9)
    for ypos, rate in zip(y_positions, rates):
        ax.text(min(rate + 0.02, 0.97), ypos, f"{rate:.2f}", va="center", fontsize=8, color="#2d3748")
    _save_figure(fig, figure_path)


def plot_intent_resolution(
    summary_rows: Sequence[dict[str, Any]],
    rate_rows: Sequence[dict[str, Any]],
    out_dir: Path,
) -> tuple[Path, Path]:
    classes_path = out_dir / "fig2_completeness_classes.png"
    rates_path = out_dir / "fig2_property_rates.png"
    plot_completeness_classes(summary_rows, classes_path)
    plot_property_rates(rate_rows, rates_path)
    return classes_path, rates_path


def headline_counts(summary: dict[str, dict[str, int]]) -> dict[str, int]:
    totals = {"n": 0, "complete": 0, "partial": 0, "zero": 0}
    for bucket in summary.values():
        for key in totals:
            totals[key] += bucket[key]
    return totals


def write_outputs(
    runs: Sequence[dict[str, Any]],
    out_dir: Path,
    paper_figure: Optional[Path] = None,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = summarize_resolution(runs)
    totals = headline_counts(summary)
    summary_rows = resolution_rows(summary, runs)
    rate_rows = all_property_rate_rows(runs)
    prereq_rows = cohort_prerequisite_stats(runs)

    _write_csv(
        out_dir / "resolution_summary.csv",
        summary_rows,
        [
            "task_id",
            "task_label",
            "n",
            "complete",
            "partial",
            "zero",
            "complete_rate",
            "partial_rate",
            "zero_rate",
            "mean_completeness",
        ],
    )
    _write_csv(
        out_dir / "property_rates.csv",
        rate_rows,
        ["task_id", "task_label", "property_id", "satisfied", "n", "rate"],
    )
    _write_csv(
        out_dir / "prerequisite_stats.csv",
        prereq_rows,
        [
            "task_id",
            "upstream",
            "downstream",
            "n",
            "n_upstream_true",
            "n_downstream_true",
            "n_both",
            "necessity_violations",
            "necessity_holds",
            "p_down_given_up",
            "p_up_given_down",
        ],
    )

    classes_path, rates_path = plot_intent_resolution(summary_rows, rate_rows, out_dir)
    dest_dir = paper_figure.parent if paper_figure is not None else None
    if dest_dir is not None:
        dest_dir.mkdir(parents=True, exist_ok=True)
        for src in (classes_path, rates_path):
            shutil.copy2(src, dest_dir / src.name)
            pdf_src = src.with_suffix(".pdf")
            if pdf_src.exists():
                shutil.copy2(pdf_src, dest_dir / pdf_src.name)

    payload = {
        "n_runs": len(runs),
        **totals,
        "strict_failures": totals["partial"] + totals["zero"],
        "partial_among_failures": totals["partial"],
    }
    (out_dir / "headline.json").write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-dir", type=Path, default=DEFAULT_RUNS_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument(
        "--paper-figure",
        type=Path,
        default=DEFAULT_PAPER_FIGURE if DEFAULT_PAPER_FIGURE.parent.exists() else None,
    )
    parser.add_argument("--no-paper-figure", action="store_true")
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Optional[Iterable[str]] = None) -> None:
    args = parse_args(argv)
    runs = load_single_agent_runs(args.runs_dir)
    if len(runs) != 70:
        raise SystemExit(f"expected 70 single-agent runs, found {len(runs)}")
    paper_figure = None if args.no_paper_figure else args.paper_figure
    payload = write_outputs(runs, args.out_dir, paper_figure=paper_figure)
    if payload["complete"] != 17 or payload["partial"] != 35 or payload["zero"] != 18:
        raise SystemExit(f"unexpected headline counts: {payload}")
    print(
        f"RQ2 single-agent cohort: {payload['n_runs']} runs; "
        f"{payload['complete']} complete, {payload['partial']} partial, "
        f"{payload['zero']} zero; "
        f"{payload['partial_among_failures']}/{payload['strict_failures']} "
        f"strict failures retain partial properties."
    )
    print(f"Wrote {args.out_dir}")
    if paper_figure is not None:
        print(f"Copied figure to {paper_figure}")


if __name__ == "__main__":
    main()
