"""Guide experiment analysis: completeness and success by arm with Wilson CIs."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any


def wilson_ci(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion."""
    if n == 0:
        return (0.0, 0.0)
    p = successes / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2.0 * n)) / denom
    margin = z * math.sqrt((p * (1.0 - p) / n + z * z / (4.0 * n * n))) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


def load_guide_runs(runs_dir: Path) -> list[dict[str, Any]]:
    """Load benchmark run JSON files that have guide_arm set."""
    runs: list[dict[str, Any]] = []
    if not runs_dir.exists():
        return runs
    for path in sorted(runs_dir.glob("*.json")):
        with path.open() as f:
            data = json.load(f)
        arm = (data.get("metrics") or {}).get("guide_arm")
        if arm:
            runs.append(data)
    return runs


def _rate(successes: int, n: int) -> float:
    return successes / n if n else 0.0


def summarize_by_arm(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate success and completeness by arm."""
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for run in runs:
        arm = run["metrics"]["guide_arm"]
        buckets[arm].append(run)

    summary: dict[str, Any] = {}
    for arm, arm_runs in sorted(buckets.items()):
        n = len(arm_runs)
        successes = sum(1 for r in arm_runs if r.get("success"))
        completeness_vals = [
            r.get("scoring", {}).get("completeness", 0.0) for r in arm_runs
        ]
        mean_completeness = sum(completeness_vals) / n if n else 0.0
        summary[arm] = {
            "n": n,
            "success_rate": _rate(successes, n),
            "success_ci": wilson_ci(successes, n),
            "mean_completeness": mean_completeness,
        }
    return summary


def contrast(summary: dict[str, Any], arm_a: str, arm_b: str) -> dict[str, Any]:
    """Simple paired contrast between two arms (pooled rates)."""
    if arm_a not in summary or arm_b not in summary:
        return {"error": f"missing arm: {arm_a} or {arm_b}"}
    a, b = summary[arm_a], summary[arm_b]
    return {
        "contrast": f"{arm_a}_vs_{arm_b}",
        "success_rate_delta": a["success_rate"] - b["success_rate"],
        "completeness_delta": a["mean_completeness"] - b["mean_completeness"],
        "n_a": a["n"],
        "n_b": b["n"],
    }


def analyze_guide(runs_dir: Path) -> dict[str, Any]:
    """Full Guide analysis with primary contrasts."""
    runs = load_guide_runs(runs_dir)
    by_arm = summarize_by_arm(runs)
    return {
        "total_runs": len(runs),
        "by_arm": by_arm,
        "contrasts": {
            "feedback_vs_blind": contrast(by_arm, "feedback", "blind"),
            "feedback_vs_declared": contrast(by_arm, "feedback", "declared"),
            "feedback_vs_placebo": contrast(by_arm, "feedback", "placebo"),
        },
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Guide experiment analysis")
    parser.add_argument(
        "--runs-dir",
        type=Path,
        default=Path("results/runs"),
        help="Directory containing benchmark run JSON files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/property_guidance/guide_summary.json"),
    )
    args = parser.parse_args()
    result = analyze_guide(args.runs_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w") as f:
        json.dump(result, f, indent=2)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
