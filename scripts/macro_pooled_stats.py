#!/usr/bin/env python3
"""
Equal-weight macro pooling for benchmark KPIs.

Run-weighted aggregates let high-N models and easy-task successes dominate pooled
numbers. This module reports:

- run_weighted: average over all runs (legacy / naive pool)
- model_macro: average of per-model means (each model counts equally)
- grid_macro: average of (model × task_id) cell means (each model×task cell equally)
- protocol_macro: average over protocol groups, where each group is the mean of
  cells in tasks with that protocol — each protocol (RIP / OSPF / BGP) counts equally

Profiles are the same dicts produced by analyze_model_behavior.build_profiles,
or rows compatible with those keys from all_runs.csv.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

import numpy as np

# task_id -> canonical protocol label (must match analyze_model_behavior TASK_METADATA)
TASK_PROTOCOL: Dict[str, str] = {
    "ccna_rip_routing_basic": "RIP",
    "ccnp_multiarea_ospf_intermediate": "OSPF",
    "ccie_bgp_dual_homing_expert": "BGP",
    "troubleshoot_ospf_adjacency_issue": "OSPF",
    "troubleshoot_bgp_route_filtering": "BGP",
}


def _f(x: Any) -> float:
    if x is None or x == "":
        return float("nan")
    if isinstance(x, bool):
        return float(x)
    if isinstance(x, str):
        s = x.strip().lower()
        if s in ("true", "false"):
            return float(s == "true")
    return float(x)


def _metric_arrays(
    profiles: Sequence[Mapping[str, Any]],
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    score = np.array([_f(p.get("final_score")) for p in profiles])
    succ = np.array([_f(p.get("success")) for p in profiles])
    melt = np.array([_f(p.get("meltdown")) for p in profiles])
    turns = np.array([_f(p.get("turns")) for p in profiles])
    toks = np.array([_f(p.get("total_tokens")) for p in profiles])
    eff = np.array([_f(p.get("score_per_1k_tokens")) for p in profiles])
    return score, succ, melt, turns, toks, eff


def run_weighted(profiles: Sequence[Mapping[str, Any]]) -> Dict[str, float]:
    if not profiles:
        return {}
    score, succ, melt, turns, toks, eff = _metric_arrays(profiles)
    return {
        "mean_final_score": float(np.nanmean(score)),
        "success_rate": float(np.nanmean(succ)),
        "meltdown_rate": float(np.nanmean(melt)),
        "mean_turns": float(np.nanmean(turns)),
        "mean_total_tokens": float(np.nanmean(toks)),
        "mean_score_per_1k_tokens": float(np.nanmean(eff)),
    }


def model_macro(profiles: Sequence[Mapping[str, Any]]) -> Dict[str, float]:
    """Unweighted mean of per-model run means."""
    if not profiles:
        return {}
    by_model: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    for p in profiles:
        by_model[str(p.get("model", ""))].append(p)
    keys = ("final_score", "success", "meltdown", "turns", "total_tokens", "score_per_1k_tokens")
    out: Dict[str, float] = {}
    for raw, name in zip(
        keys,
        (
            "mean_final_score",
            "success_rate",
            "meltdown_rate",
            "mean_turns",
            "mean_total_tokens",
            "mean_score_per_1k_tokens",
        ),
    ):
        m_means = []
        for _, rows in by_model.items():
            vals = np.array([_f(r.get(raw)) for r in rows])
            if np.isfinite(vals).any():
                m_means.append(float(np.nanmean(vals)))
        out[name] = float(np.mean(m_means)) if m_means else float("nan")
    return out


def grid_macro(profiles: Sequence[Mapping[str, Any]]) -> Dict[str, float]:
    """Unweighted mean of (model, task_id) cell means."""
    if not profiles:
        return {}
    cell: Dict[Tuple[str, str], List[Mapping[str, Any]]] = defaultdict(list)
    for p in profiles:
        m = str(p.get("model", ""))
        t = str(p.get("task_id", ""))
        cell[(m, t)].append(p)

    def cell_mean(key: str) -> List[float]:
        means: List[float] = []
        for rows in cell.values():
            vals = np.array([_f(r.get(key)) for r in rows])
            if np.isfinite(vals).any():
                means.append(float(np.nanmean(vals)))
        return means

    return {
        "mean_final_score": float(np.mean(cell_mean("final_score"))) if cell else float("nan"),
        "success_rate": float(np.mean(cell_mean("success"))) if cell else float("nan"),
        "meltdown_rate": float(np.mean(cell_mean("meltdown"))) if cell else float("nan"),
        "mean_turns": float(np.mean(cell_mean("turns"))) if cell else float("nan"),
        "mean_total_tokens": float(np.mean(cell_mean("total_tokens"))) if cell else float("nan"),
        "mean_score_per_1k_tokens": float(np.mean(cell_mean("score_per_1k_tokens")))
        if cell
        else float("nan"),
    }


def protocol_macro(profiles: Sequence[Mapping[str, Any]]) -> Dict[str, float]:
    """Mean over protocol groups; each group's value is mean of cells in that protocol."""
    if not profiles:
        return {}
    cell: Dict[Tuple[str, str], List[Mapping[str, Any]]] = defaultdict(list)
    for p in profiles:
        cell[(str(p.get("model", "")), str(p.get("task_id", "")))].append(p)

    def cell_means_by_metric(key: str) -> Dict[Tuple[str, str], float]:
        out_m: Dict[Tuple[str, str], float] = {}
        for k, rows in cell.items():
            vals = np.array([_f(r.get(key)) for r in rows])
            if np.isfinite(vals).any():
                out_m[k] = float(np.nanmean(vals))
        return out_m

    protocols = sorted(set(TASK_PROTOCOL.values()))
    result: Dict[str, float] = {}
    metric_specs = (
        ("final_score", "mean_final_score"),
        ("success", "success_rate"),
        ("meltdown", "meltdown_rate"),
        ("turns", "mean_turns"),
        ("total_tokens", "mean_total_tokens"),
        ("score_per_1k_tokens", "mean_score_per_1k_tokens"),
    )
    for raw, out_name in metric_specs:
        cm = cell_means_by_metric(raw)
        proto_vals: List[float] = []
        for prot in protocols:
            task_ids = [tid for tid, pr in TASK_PROTOCOL.items() if pr == prot]
            vals = [cm[(m, t)] for (m, t) in cm if t in task_ids]
            if vals:
                proto_vals.append(float(np.mean(vals)))
        result[out_name] = float(np.mean(proto_vals)) if proto_vals else float("nan")
    return result


def protocol_group_table(profiles: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Per-protocol grid-macro means (for appendix / inspection)."""
    cell: Dict[Tuple[str, str], List[Mapping[str, Any]]] = defaultdict(list)
    for p in profiles:
        cell[(str(p.get("model", "")), str(p.get("task_id", "")))].append(p)

    def mean_cell(key: str, m: str, tid: str) -> float:
        rows = cell.get((m, tid), [])
        if not rows:
            return float("nan")
        vals = np.array([_f(r.get(key)) for r in rows])
        return float(np.nanmean(vals))

    models = sorted({m for (m, _) in cell})
    rows_out: List[Dict[str, Any]] = []
    for prot in sorted(set(TASK_PROTOCOL.values())):
        tids = [tid for tid, p in TASK_PROTOCOL.items() if p == prot]
        for key, label in (
            ("final_score", "mean_final_score"),
            ("success", "success_rate"),
            ("meltdown", "meltdown_rate"),
        ):
            cells = [
                mean_cell(key, m, tid)
                for m in models
                for tid in tids
                if (m, tid) in cell
            ]
            pool = float(np.mean(cells)) if cells else float("nan")
            rows_out.append({"protocol": prot, "metric": label, "grid_macro_mean": pool, "n_cells": len(cells)})
    return rows_out


def compute_all_layers(
    profiles: Sequence[Mapping[str, Any]],
) -> Dict[str, Dict[str, float]]:
    return {
        "run_weighted": run_weighted(profiles),
        "model_macro": model_macro(profiles),
        "grid_macro": grid_macro(profiles),
        "protocol_macro": protocol_macro(profiles),
    }


def write_macro_pooled_artifacts(profiles: List[Mapping[str, Any]], out_dir: Path) -> None:
    """Write macro_pooled_kpis.csv and macro_pooled_report.md next to other behavior outputs."""
    out_dir.mkdir(parents=True, exist_ok=True)
    layers = compute_all_layers(profiles)

    csv_path = out_dir / "macro_pooled_kpis.csv"
    fieldnames = ["aggregation", "n_runs", "n_models", "n_grid_cells", "metric", "value"]
    n_models = len({str(p.get("model")) for p in profiles})
    cells = {(str(p.get("model")), str(p.get("task_id"))) for p in profiles}

    with open(csv_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        for agg_name, metrics in layers.items():
            for metric, value in sorted(metrics.items()):
                w.writerow(
                    {
                        "aggregation": agg_name,
                        "n_runs": len(profiles),
                        "n_models": n_models,
                        "n_grid_cells": len(cells),
                        "metric": metric,
                        "value": f"{value:.6g}" if np.isfinite(value) else "",
                    }
                )

    # Protocol breakdown
    proto_rows = protocol_group_table(profiles)
    proto_path = out_dir / "macro_pooled_by_protocol.csv"
    if proto_rows:
        with open(proto_path, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(proto_rows[0].keys()))
            w.writeheader()
            w.writerows(proto_rows)

    md_lines = [
        "# Macro-pooled KPIs (equal-weight aggregates)",
        "",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Runs:** {len(profiles)} | **Models:** {n_models} | **Model×task cells:** {len(cells)}",
        "",
        "## Definitions",
        "",
        "- **run_weighted**: mean over all runs (legacy; favors models and tasks with more runs).",
        "- **model_macro**: mean of per-model means — each **model** has equal weight.",
        "- **grid_macro**: mean of (model×task) cell means — each **model×task** combination has equal weight (no extra GPT repeats, no easy-task frequency bias across tasks).",
        "- **protocol_macro**: for each protocol (RIP, OSPF, BGP), mean of all cells in tasks with that protocol; then mean over protocols — each **protocol family** has equal weight in the headline scalar.",
        "",
        "## Summary table",
        "",
        "| Metric | run_weighted | model_macro | grid_macro | protocol_macro |",
        "|---|---:|---:|---:|---:|",
    ]
    metric_order = (
        "mean_final_score",
        "success_rate",
        "meltdown_rate",
        "mean_turns",
        "mean_total_tokens",
        "mean_score_per_1k_tokens",
    )
    nice = {
        "mean_final_score": "Mean final score",
        "success_rate": "Success rate",
        "meltdown_rate": "Meltdown rate",
        "mean_turns": "Mean turns",
        "mean_total_tokens": "Mean total tokens",
        "mean_score_per_1k_tokens": "Mean score / 1k tok",
    }
    for m in metric_order:
        rw = layers["run_weighted"].get(m, float("nan"))
        mm = layers["model_macro"].get(m, float("nan"))
        gm = layers["grid_macro"].get(m, float("nan"))
        pm = layers["protocol_macro"].get(m, float("nan"))
        md_lines.append(
            f"| {nice[m]} | {rw:.4f} | {mm:.4f} | {gm:.4f} | {pm:.4f} |"
        )
    mm0 = layers["model_macro"].get("mean_final_score", float("nan"))
    gm0 = layers["grid_macro"].get("mean_final_score", float("nan"))
    if np.isfinite(mm0) and np.isfinite(gm0) and abs(mm0 - gm0) < 1e-9:
        md_lines.extend(
            [
                "",
                "**Note:** **model_macro** and **grid_macro** match whenever every model runs the same "
                "task grid (each model’s global mean equals the mean of its per-task cell means). "
                "They still differ from **run_weighted** when some models have more repeats.",
            ]
        )
    md_lines.extend(
        [
            "",
            "**Interpretation:** Prefer **model_macro** for model-fair pooled rates; **grid_macro** for task-fair cohort summaries; **protocol_macro** when protocol families must contribute equally to a single headline number.",
            "",
            f"CSV: `{csv_path.name}`; per-protocol helper: `{proto_path.name}`.",
        ]
    )
    with open(out_dir / "macro_pooled_report.md", "w") as fh:
        fh.write("\n".join(md_lines))


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Macro-pooled KPIs from all_runs.csv or session JSONs.")
    parser.add_argument(
        "input_path",
        type=str,
        help="Path to behavior_analysis/all_runs.csv or a session directory (loads JSONs, single-only)",
    )
    parser.add_argument(
        "--pattern",
        type=str,
        default="single",
        help="When loading CSV: filter pattern column (default single). Use 'all' to disable.",
    )
    args = parser.parse_args()
    path = Path(args.input_path)

    profiles: List[Dict[str, Any]] = []
    if path.is_file() and path.suffix.lower() == ".csv":
        with open(path, newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                if args.pattern and args.pattern != "all":
                    if row.get("pattern") != args.pattern:
                        continue
                profiles.append(dict(row))
    elif path.is_dir():
        from scripts.analyze_model_behavior import build_profiles, load_results

        raw = load_results(path, single_only=True)
        profiles = build_profiles(raw)
    else:
        raise SystemExit(f"Invalid input: {path}")

    out_dir = path.parent if path.is_file() else path / "behavior_analysis"
    write_macro_pooled_artifacts(profiles, out_dir)
    print(f"Wrote macro_pooled_* under {out_dir}")


if __name__ == "__main__":
    main()
