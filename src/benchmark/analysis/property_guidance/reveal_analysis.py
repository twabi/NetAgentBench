"""Reveal analysis: per-turn property trajectories from guide runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_trajectory_runs(runs_dir: Path) -> list[dict[str, Any]]:
    """Load runs that logged property_trajectory snapshots."""
    runs: list[dict[str, Any]] = []
    if not runs_dir.exists():
        return runs
    for path in sorted(runs_dir.glob("*.json")):
        with path.open() as f:
            data = json.load(f)
        trajectory = (data.get("metrics") or {}).get("property_trajectory")
        if trajectory:
            runs.append(
                {
                    "run_id": data.get("run_id"),
                    "task_id": data.get("task_id"),
                    "guide_arm": data.get("metrics", {}).get("guide_arm"),
                    "trajectory": trajectory,
                    "terminal_completeness": data.get("scoring", {}).get("completeness"),
                    "success": data.get("success"),
                }
            )
    return runs


def trajectory_stats(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize trajectory length and final-vs-terminal completeness."""
    if not runs:
        return {"n": 0}
    lengths = [len(r["trajectory"]) for r in runs]
    final_snap_completeness = []
    for run in runs:
        traj = run["trajectory"]
        prop_snaps = [s for s in traj if s.get("kind") == "property_eval"]
        if prop_snaps:
            final_snap_completeness.append(prop_snaps[-1].get("completeness", 0.0))
    return {
        "n": len(runs),
        "mean_snapshots": sum(lengths) / len(lengths),
        "mean_final_snapshot_completeness": (
            sum(final_snap_completeness) / len(final_snap_completeness)
            if final_snap_completeness
            else None
        ),
        "runs": runs,
    }


def analyze_reveal(runs_dir: Path) -> dict[str, Any]:
    runs = load_trajectory_runs(runs_dir)
    return trajectory_stats(runs)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Reveal trajectory analysis")
    parser.add_argument("--runs-dir", type=Path, default=Path("results/runs"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/property_guidance/reveal_trajectories.json"),
    )
    args = parser.parse_args()
    result = analyze_reveal(args.runs_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w") as f:
        json.dump(result, f, indent=2)
    print(f"Wrote {args.output} ({result.get('n', 0)} runs with trajectories)")


if __name__ == "__main__":
    main()
