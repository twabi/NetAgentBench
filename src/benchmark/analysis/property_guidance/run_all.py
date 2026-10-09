"""Run all property-guidance analyses (Guide + Reveal)."""

from __future__ import annotations

import json
from pathlib import Path

from benchmark.analysis.property_guidance.guide_analysis import analyze_guide
from benchmark.analysis.property_guidance.reveal_analysis import analyze_reveal


def run_all(runs_dir: Path, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    guide = analyze_guide(runs_dir)
    reveal = analyze_reveal(runs_dir)
    combined = {"guide": guide, "reveal": reveal}
    out_path = output_dir / "property_guidance_summary.json"
    with out_path.open("w") as f:
        json.dump(combined, f, indent=2)
    return combined


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run property-guidance analyses")
    parser.add_argument("--runs-dir", type=Path, default=Path("results/runs"))
    parser.add_argument(
        "--output-dir", type=Path, default=Path("results/property_guidance")
    )
    args = parser.parse_args()
    result = run_all(args.runs_dir, args.output_dir)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
