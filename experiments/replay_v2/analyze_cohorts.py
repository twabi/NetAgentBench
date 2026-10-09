"""Compare two cohorts of the same 60-cell sweep run under different harness rules.

Default: the untaxed cohort (results/v2_openrouter: only config-labelled commands cost a turn,
~2 s pause and a snapshot after each of them) against the taxed cohort
(results/v2_openrouter_taxed: every command costs a turn and is followed by a snapshot).

Inputs are the per_run_process.csv files written by analyze_process.py for each cohort, plus
the replay summaries. Outputs:
  cohort_comparison.csv   one row per model x metric: value in cohort A and cohort B
  fig_cohort_shift.pdf/.png   per model, how each behaviour moved from A to B

The two cohorts were run on different days against hosted models, so a shift mixes the
harness change with provider-side variation. Shifts that follow the incentive the harness
change creates (label use, read-channel changes) are the ones to read causally.

Usage:
  python experiments/replay_v2/analyze_cohorts.py \
      --a out/process_analysis --b out/v2_openrouter_taxed_process \
      --replay-a out/v2_openrouter_replay/summary.json --replay-b out/v2_openrouter_taxed_replay/summary.json \
      --out-dir out/v2_openrouter_taxed_process
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics as st
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from analyze_process import GRID, INK, MODELS, MUTED, save  # noqa: E402

# key, label, aggregate over the model's 15 runs
METRICS = [
    ("complete", "runs at C = 1.0\n(of 15)", "count"),
    ("turns", "turns used\n(median)", "median"),
    ("commands", "commands\n(median)", "median"),
    ("reads", "read-only\ncommands (median)", "median"),
    ("writes", "state-changing\ncommands (median)", "median"),
    ("verify_reads", "reads after\nlast change (median)", "median"),
    ("hidden_writes", "changes sent\nas reads (total)", "sum"),
    ("phantom_writes", "reads sent\nas changes (total)", "sum"),
    ("disruptive_ops", "disruptive\nactions (total)", "sum"),
    ("regressions", "properties lost\nmid-run (total)", "sum"),
    ("wall_time_s", "wall time\n(median, s)", "median"),
    ("tokens", "tokens\n(median, k)", "median_k"),
]


def load(path: Path) -> list[dict]:
    with path.open() as fh:
        return list(csv.DictReader(fh))


def value(rows: list[dict], key: str, agg: str):
    if key == "complete":
        return sum(r["complete"] == "True" for r in rows)
    vals = [float(r[key]) for r in rows if r.get(key) not in (None, "")]
    if not vals:
        return None
    if agg == "sum":
        return sum(vals)
    m = st.median(vals)
    return m / 1000 if agg == "median_k" else m


def replay_line(path: Path | None) -> str:
    if not path or not path.exists():
        return "n/a"
    s = json.loads(path.read_text())
    return f"{s['n_stable_v2_vector']}/{s['n_scored']} stable, {s['n_matches_original_v2']}/{s['n_scored']} match live"


def fig_shift(table, labels, path):
    ncol = 6
    nrow = (len(METRICS) + ncol - 1) // ncol
    fig, grid = plt.subplots(nrow, ncol, figsize=(7.4, 1.9 * nrow + 0.5), sharey=True)
    axes = list(grid.flat)
    for ax, (key, label, agg) in zip(axes, METRICS):
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
        ax.spines["bottom"].set_color(MUTED)
        ax.spines["bottom"].set_linewidth(0.6)
        ax.tick_params(colors=MUTED, labelsize=6.2, width=0.6, length=2)
        ax.tick_params(axis="y", length=0)
        ax.grid(axis="x", color=GRID, linewidth=0.5)
        ax.set_axisbelow(True)
        vals = []
        for yi, (mid, _, color, mk) in enumerate(MODELS):
            a, b = table[(mid, key)]
            if a is None or b is None:
                continue
            vals += [a, b]
            ax.plot([a, b], [yi, yi], color=color, linewidth=1.2, alpha=0.6, zorder=1)
            ax.plot(a, yi, marker=mk, color=color, markerfacecolor="white", markersize=4.6,
                    markeredgewidth=0.9, linestyle="", zorder=2)
            ax.plot(b, yi, marker=mk, color=color, markersize=4.6, markeredgewidth=0.9, linestyle="", zorder=3)
        lo, hi = (min(vals), max(vals)) if vals else (0, 1)
        pad = (hi - lo) * 0.18 or 1
        ax.set_xlim(max(lo - pad, 0) if lo >= 0 else lo - pad, hi + pad)
        ax.xaxis.set_major_locator(plt.MaxNLocator(3, integer=agg in ("count", "sum")))
        ax.set_title(label, fontsize=6.6, color=INK)
        ax.set_ylim(len(MODELS) - 0.5, -0.5)
    for row in grid:
        row[0].set_yticks(range(len(MODELS)))
        row[0].set_yticklabels([l for _, l, _, _ in MODELS], fontsize=6.8, color=INK)
    handles = [Line2D([], [], marker="o", markerfacecolor="white", markeredgecolor=MUTED, linestyle="",
                      markersize=5, label=labels[0]),
               Line2D([], [], marker="o", color=MUTED, linestyle="", markersize=5, label=labels[1])]
    fig.legend(handles=handles, loc="upper center", ncol=2, frameon=False, fontsize=6.8, bbox_to_anchor=(0.5, 1.0))
    fig.tight_layout(rect=(0, 0, 1, 0.94), w_pad=0.6, h_pad=1.2)
    save(fig, path)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--a", type=Path, required=True, help="analyze_process.py output dir, cohort A")
    ap.add_argument("--b", type=Path, required=True, help="analyze_process.py output dir, cohort B")
    ap.add_argument("--label-a", default="untaxed (only config-labelled commands cost a turn)")
    ap.add_argument("--label-b", default="taxed (every command costs a turn)")
    ap.add_argument("--replay-a", type=Path, default=None)
    ap.add_argument("--replay-b", type=Path, default=None)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    A, B = load(args.a / "per_run_process.csv"), load(args.b / "per_run_process.csv")
    table, out = {}, []
    for mid, mlabel, _, _ in MODELS:
        ra = [r for r in A if r["model"] == mid]
        rb = [r for r in B if r["model"] == mid]
        for key, label, agg in METRICS:
            a, b = value(ra, key, agg), value(rb, key, agg)
            table[(mid, key)] = (a, b)
            out.append({"model": mlabel, "metric": label.replace("\n", " "), "a": a, "b": b})
    for key, label, agg in METRICS:
        a, b = value(A, key, agg), value(B, key, agg)
        out.append({"model": "all models", "metric": label.replace("\n", " ").replace("(of 15)", "(of 60)"),
                    "a": a, "b": b})
    out.append({"model": "all models", "metric": "replay (3 repeats per run)",
                "a": replay_line(args.replay_a), "b": replay_line(args.replay_b)})
    with (args.out_dir / "cohort_comparison.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["model", "metric", "a", "b"])
        w.writeheader()
        w.writerows(out)
    fig_shift(table, (args.label_a, args.label_b), args.out_dir / "fig_cohort_shift")
    print(f"wrote cohort comparison to {args.out_dir}")


if __name__ == "__main__":
    main()
