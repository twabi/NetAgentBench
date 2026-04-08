#!/usr/bin/env python3
"""
Generate MDPI / paper table metrics from deep_analysis outputs.

- Primary outcomes (turn_waste / final_score): score, success_pct (full completion),
  meltdown_zero_pct (zero final score), coordination tax, entropy, mean total_steps.
- Spatial coverage (paper): Shannon entropy of per-router command counts divided by
  log2(N) for N routers in the task, mean per pattern; from coherence_analysis.csv
  joined on run_id (column sp_cov in printed tables when coherence file exists).
- Secondary / benchmark-aligned (behavior_analysis/all_runs.csv, joined on run_id):
  success_bench_pct, meltdown_bench_pct, turns (agent turns), tokens_k.

GPT-5-nano runs are excluded by substring match on run_id (defense in depth; deep
analysis already drops them when regenerating turn_waste.csv).

Bootstrap 95% percentile CIs (optional): for each task×pattern cell, resample runs
with replacement (B replicates, default 10_000) and take the 2.5th/97.5th percentile
of the per-replicate mean intent-property score. Lift vs single uses independent
resampling of single and pattern runs each replicate. Seeds are deterministic
(score: 10_000 + task_index*50 + pattern_index; lift: 50_000 + task_index*50 +
pattern_index) so regenerated paper values stay stable.

Usage:
  python -m scripts.deep_analysis.mdpi_paper.generate_mdpi_tables \\
      [--data-dir results/comparatives_all/deep_analysis]
  python -m scripts.deep_analysis.mdpi_paper.generate_mdpi_tables --bootstrap-cis
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Repo root on path when run as script
_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _strip_gpt5_nano(df: pd.DataFrame) -> pd.DataFrame:
    if "run_id" not in df.columns:
        return df
    rid = df["run_id"].astype(str).str.lower()
    return df[~rid.str.contains("gpt5nano", na=False)]


def _session_root(data_dir: Path) -> Path:
    return data_dir.resolve().parent


def _load_turn_waste(data_dir: Path) -> pd.DataFrame:
    path = data_dir / "turn_waste.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}")
    tw = pd.read_csv(path)
    return _strip_gpt5_nano(tw)


def _load_behavior(session_root: Path) -> pd.DataFrame | None:
    p = session_root / "behavior_analysis" / "all_runs.csv"
    if not p.exists():
        return None
    ar = pd.read_csv(p)
    return _strip_gpt5_nano(ar)


def _merge(tw: pd.DataFrame, ar: pd.DataFrame | None) -> pd.DataFrame:
    if ar is None or "run_id" not in ar.columns:
        return tw
    if ar["run_id"].astype(str).str.len().eq(0).all():
        return tw
    cols = [c for c in ("run_id", "success", "meltdown", "turns", "total_tokens") if c in ar.columns]
    if len(cols) <= 1:
        return tw
    return tw.merge(ar[cols], on="run_id", how="left")


# Routers in task topology (must match paper Table tasks / coherence_analysis task_id)
_TASK_ROUTER_COUNT: dict[str, int] = {
    "ccna_rip_routing_basic": 4,
    "troubleshoot_ospf_adjacency_issue": 4,
    "ccnp_multiarea_ospf_intermediate": 5,
    "ccie_bgp_dual_homing_expert": 5,
    "troubleshoot_bgp_route_filtering": 4,
}

PATTERN_ORDER = ["single", "sequential", "debate", "group_chat", "concurrent"]
TASK_IDS_IN_PAPER_ORDER = [
    "ccna_rip_routing_basic",
    "troubleshoot_ospf_adjacency_issue",
    "ccnp_multiarea_ospf_intermediate",
    "ccie_bgp_dual_homing_expert",
    "troubleshoot_bgp_route_filtering",
]
BOOTSTRAP_REPLICATES_DEFAULT = 10_000
SCORE_CI_SEED_BASE = 10_000
LIFT_CI_SEED_BASE = 50_000


def _bootstrap_score_ci(
    values: np.ndarray, *, n_boot: int, seed: int
) -> tuple[float, float, float]:
    """Return (mean, lo, hi) for mean(values) via percentile bootstrap."""
    arr = np.asarray(values, dtype=float)
    n = len(arr)
    rng = np.random.default_rng(seed)
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    if n == 1:
        m = float(arr[0])
        return m, m, m
    idx = rng.integers(0, n, size=(n_boot, n))
    means = arr[idx].mean(axis=1)
    return float(arr.mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def _bootstrap_lift_ci(
    single_scores: np.ndarray,
    pattern_scores: np.ndarray,
    *,
    n_boot: int,
    seed: int,
) -> tuple[float, float, float]:
    """Return (point lift, lo, hi) with independent resampling of each arm."""
    s = np.asarray(single_scores, dtype=float)
    p = np.asarray(pattern_scores, dtype=float)
    ns, n_p = len(s), len(p)
    rng = np.random.default_rng(seed)
    if ns < 1 or n_p < 1:
        return float("nan"), float("nan"), float("nan")
    is_ = rng.integers(0, ns, size=(n_boot, ns))
    ip = rng.integers(0, n_p, size=(n_boot, n_p))
    lifts = p[ip].mean(axis=1) - s[is_].mean(axis=1)
    return float(p.mean() - s.mean()), float(np.percentile(lifts, 2.5)), float(np.percentile(lifts, 97.5))


def _task_index(task_id: str | None) -> int:
    if task_id is None:
        return len(TASK_IDS_IN_PAPER_ORDER)
    return TASK_IDS_IN_PAPER_ORDER.index(task_id)


def _pattern_index(pattern: str) -> int:
    return PATTERN_ORDER.index(pattern)


def print_bootstrap_cis(
    merged: pd.DataFrame, *, n_boot: int = BOOTSTRAP_REPLICATES_DEFAULT
) -> None:
    """Print mean score and lift vs single with 95% bootstrap CIs for paper tables."""
    tasks: list[str | None] = [*TASK_IDS_IN_PAPER_ORDER, None]
    for task_id in tasks:
        sub = merged if task_id is None else merged[merged["task_id"] == task_id]
        label = task_id or "ALL_TASKS"
        tix = _task_index(task_id)
        single_s = sub[sub["pattern"] == "single"]["final_score"].values.astype(float)
        print(f"\n### {label} (task_index={tix}) ###")
        for pat in PATTERN_ORDER:
            g = sub[sub["pattern"] == pat]["final_score"].values.astype(float)
            seed_s = SCORE_CI_SEED_BASE + tix * 50 + _pattern_index(pat)
            m, lo, hi = _bootstrap_score_ci(g, n_boot=n_boot, seed=seed_s)
            if pat == "single":
                l, ll, lh = 0.0, 0.0, 0.0
            else:
                seed_l = LIFT_CI_SEED_BASE + tix * 50 + _pattern_index(pat)
                l, ll, lh = _bootstrap_lift_ci(single_s, g, n_boot=n_boot, seed=seed_l)
            print(
                f"{pat:12s}  score {m:.3f} [{lo:.3f}, {hi:.3f}]   "
                f"lift {l:+.3f} [{ll:+.3f}, {lh:+.3f}]"
            )


def _attach_spatial_coverage(df: pd.DataFrame, data_dir: Path) -> pd.DataFrame:
    """Join normalized spatial coverage from coherence_analysis.csv on run_id."""
    path = data_dir / "coherence_analysis.csv"
    if not path.exists() or "run_id" not in df.columns:
        return df
    co = pd.read_csv(path)
    co = _strip_gpt5_nano(co)
    if "router_entropy" not in co.columns or "task_id" not in co.columns:
        return df

    def norm(row: pd.Series) -> float:
        tid = str(row["task_id"])
        n = _TASK_ROUTER_COUNT.get(tid, 5)
        if n <= 1:
            return 0.0
        return float(row["router_entropy"]) / math.log2(n)

    co = co.copy()
    co["sp_cov"] = co.apply(norm, axis=1)
    keep = co[["run_id", "sp_cov"]].drop_duplicates(subset=["run_id"])
    return df.merge(keep, on="run_id", how="left")


def _agg_task(df: pd.DataFrame) -> pd.DataFrame:
    def zero_score(s: pd.Series) -> float:
        return (np.isclose(s.astype(float), 0.0)).mean() * 100

    rows = []
    for pat in df["pattern"].unique():
        g = df[df["pattern"] == pat]
        row: dict = {
            "pattern": pat,
            "score": g["final_score"].mean(),
            "success_pct": (g["final_score"] >= 0.999).mean() * 100,
            "meltdown_zero_pct": zero_score(g["final_score"]),
            "ct": g["coordination_ratio"].mean() * 100,
            "waste": g["waste_ratio"].mean() * 100,
            "prod": g["productive_ratio"].mean(),
            "entropy": g["action_entropy"].mean(),
            "total_steps": g["total_steps"].mean(),
        }
        if "success" in g.columns and g["success"].notna().any():
            row["success_bench_pct"] = g["success"].astype(float).mean() * 100
        if "meltdown" in g.columns and g["meltdown"].notna().any():
            row["meltdown_bench_pct"] = g["meltdown"].astype(float).mean() * 100
        if "turns" in g.columns and g["turns"].notna().any():
            row["turns_bench"] = g["turns"].mean()
        if "total_tokens" in g.columns and g["total_tokens"].notna().any():
            row["tokens_k"] = g["total_tokens"].mean() / 1000.0
        if "sp_cov" in g.columns and g["sp_cov"].notna().any():
            row["sp_cov"] = g["sp_cov"].mean()
        rows.append(row)
    out = pd.DataFrame(rows)
    single_score = out.loc[out["pattern"] == "single", "score"]
    base = float(single_score.iloc[0]) if len(single_score) else 0.0
    out["lift"] = out["score"] - base
    out["pattern"] = pd.Categorical(out["pattern"], categories=PATTERN_ORDER, ordered=True)
    return out.sort_values("pattern")


def print_table(df: pd.DataFrame, title: str) -> None:
    print(f"\n=== {title} ===")
    pd.options.display.float_format = "{:.3f}".format
    cols = [c for c in df.columns if c != "pattern"]
    print(df[["pattern"] + cols].to_string(index=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate MDPI table metrics from deep_analysis CSVs")
    parser.add_argument(
        "--data-dir",
        type=str,
        default="results/comparatives_all/deep_analysis",
        help="Path to deep_analysis output directory (contains turn_waste.csv)",
    )
    parser.add_argument(
        "--bootstrap-cis",
        action="store_true",
        help="Print 95%% bootstrap percentile CIs for mean score and lift vs single",
    )
    parser.add_argument(
        "--bootstrap-replicates",
        type=int,
        default=BOOTSTRAP_REPLICATES_DEFAULT,
        help="Bootstrap replicate count (default: 10000)",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    tw = _load_turn_waste(data_dir)
    ar = _load_behavior(_session_root(data_dir))
    merged = _attach_spatial_coverage(_merge(tw, ar), data_dir)
    if not (data_dir / "coherence_analysis.csv").exists():
        print("No coherence_analysis.csv — run deep analysis with coherence module for sp_cov.")
    if ar is None:
        print("No behavior_analysis/all_runs.csv — run: python scripts/analyze_model_behavior.py <session_dir>")
    elif "run_id" not in ar.columns or ar["run_id"].astype(str).str.len().eq(0).all():
        print("behavior_analysis/all_runs.csv missing run_id — re-run analyze_model_behavior.py for tokens/turns join.")
    else:
        n_join = merged["success"].notna().sum() if "success" in merged.columns else 0
        print(f"Joined behavior_analysis on run_id: {n_join} / {len(merged)} rows with benchmark fields.")

    pd.options.display.float_format = "{:.3f}".format

    if args.bootstrap_cis:
        print_bootstrap_cis(merged, n_boot=args.bootstrap_replicates)
        return

    tasks = [
        ("ccna_rip_routing_basic", "5.1 RIP - Control Baseline"),
        ("troubleshoot_ospf_adjacency_issue", "5.2.1 Single-Area OSPF"),
        ("ccnp_multiarea_ospf_intermediate", "5.2.2 Multi-Area OSPF"),
        ("ccie_bgp_dual_homing_expert", "5.3.1 BGP Dual-Homing"),
        ("troubleshoot_bgp_route_filtering", "5.3.2 BGP Route Filtering"),
    ]
    for task_id, name in tasks:
        sub = merged[merged["task_id"] == task_id]
        if sub.empty:
            print(f"\n=== {name} (`{task_id}`) ===\nNo data.")
            continue
        print_table(_agg_task(sub), f"{name} (`{task_id}`)")

    print("\n=== 5.4 Cross-Protocol Synthesis (ALL TASKS) ===")
    print_table(_agg_task(merged), "All tasks × patterns")


if __name__ == "__main__":
    main()
