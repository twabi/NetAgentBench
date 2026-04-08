#!/usr/bin/env python3
"""
Deep Analysis CLI: Run all analysis modules on comparatives_all data.

Orchestrates:
1. Merge comparative study runs (if needed)
2. Module 1: Property Satisfaction Timeline
3. Module 2: Cross-Router Coherence Analysis
4. Module 3: Turn Waste & Action Efficiency
5. Module 4: Inter-Agent Communication Quality
6. Module 5: Error Cascade & Recovery
7. Module 6: Token Efficiency Dynamics
8. Module 7: Per-Model Pattern Sensitivity
9. Module 8: Troubleshooting vs Construction Behavioral Split
10. Module 9: Pattern Deep Profiles

Usage:
    python -m scripts.deep_analysis.run_deep_analysis [--force-merge] [--session-dir PATH]
"""

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.deep_analysis.merge_comparatives import merge, OUTPUT_DIR
from scripts.deep_analysis.run_filters import is_adaptive_pattern_run, is_gpt5_nano_run
from scripts.deep_analysis.run_loader import load_and_enrich, load_runs, get_output_dir


def main():
    parser = argparse.ArgumentParser(description="Run all deep analysis modules")
    parser.add_argument("--force-merge", action="store_true",
                        help="Re-merge comparative studies even if output exists")
    parser.add_argument("--session-dir", type=str, default=None,
                        help="Path to session directory (default: comparatives_all)")
    parser.add_argument("--modules", type=str, default="all",
                        help="Comma-separated module numbers to run (e.g. '1,2,3') or 'all'")
    args = parser.parse_args()

    session_dir = Path(args.session_dir) if args.session_dir else None

    # Step 0: Merge
    if session_dir is None:
        print("=" * 70)
        print("Step 0: Merge Comparative Studies")
        print("=" * 70)
        session_dir = merge(force=args.force_merge)
        print()

    # Determine which modules to run
    if args.modules == "all":
        modules_to_run = {1, 2, 3, 4, 5, 6, 7, 8, 9}
    else:
        modules_to_run = set(int(m.strip()) for m in args.modules.split(","))

    # Verify data loads (GPT-5-nano runs excluded — see run_loader.load_and_enrich)
    raw = load_runs(session_dir)
    n_nano = sum(1 for r in raw if is_gpt5_nano_run(r))
    n_adapt = sum(1 for r in raw if is_adaptive_pattern_run(r))
    if n_nano:
        print(f"GPT-5-nano exclusion: skipping {n_nano} run(s).")
    if n_adapt:
        print(f"Adaptive-pattern exclusion: skipping {n_adapt} run(s).")
    runs = load_and_enrich(session_dir)
    print(f"Loaded {len(runs)} runs from {session_dir.name}")
    out_dir = get_output_dir(session_dir)
    print(f"Output directory: {out_dir}")
    print()

    start = time.time()
    results = {}

    if 1 in modules_to_run:
        print("=" * 70)
        print("Module 1: Property Satisfaction Timeline")
        print("=" * 70)
        from scripts.deep_analysis.property_timeline import run_analysis as m1
        results["property_timeline"] = m1(session_dir)
        print()

    if 2 in modules_to_run:
        print("=" * 70)
        print("Module 2: Cross-Router Coherence Analysis")
        print("=" * 70)
        from scripts.deep_analysis.coherence_analysis import run_analysis as m2
        results["coherence"] = m2(session_dir)
        print()

    if 3 in modules_to_run:
        print("=" * 70)
        print("Module 3: Turn Waste & Action Efficiency")
        print("=" * 70)
        from scripts.deep_analysis.turn_waste import run_analysis as m3
        results["turn_waste"] = m3(session_dir)
        print()

    if 4 in modules_to_run:
        print("=" * 70)
        print("Module 4: Inter-Agent Communication Quality")
        print("=" * 70)
        from scripts.deep_analysis.agent_comms import run_analysis as m4
        results["agent_comms"] = m4(session_dir)
        print()

    if 5 in modules_to_run:
        print("=" * 70)
        print("Module 5: Error Cascade & Recovery")
        print("=" * 70)
        from scripts.deep_analysis.error_cascade import run_analysis as m5
        results["error_cascade"] = m5(session_dir)
        print()

    if 6 in modules_to_run:
        print("=" * 70)
        print("Module 6: Token Efficiency Dynamics")
        print("=" * 70)
        from scripts.deep_analysis.token_efficiency import run_analysis as m6
        results["token_efficiency"] = m6(session_dir)
        print()

    if 7 in modules_to_run:
        print("=" * 70)
        print("Module 7: Per-Model Pattern Sensitivity")
        print("=" * 70)
        from scripts.deep_analysis.model_sensitivity import run_analysis as m7
        results["model_sensitivity"] = m7(session_dir)
        print()

    if 8 in modules_to_run:
        print("=" * 70)
        print("Module 8: Troubleshooting vs Construction Split")
        print("=" * 70)
        from scripts.deep_analysis.task_type_split import run_analysis as m8
        results["task_type_split"] = m8(session_dir)
        print()

    if 9 in modules_to_run:
        print("=" * 70)
        print("Module 9: Pattern Deep Profiles")
        print("=" * 70)
        from scripts.deep_analysis.pattern_deep_profile import run_analysis as m9
        results["pattern_profiles"] = m9(session_dir)
        print()

    elapsed = time.time() - start

    # Generate combined report
    _generate_report(out_dir, modules_to_run, len(runs), elapsed)

    print("=" * 70)
    print(f"Deep analysis complete in {elapsed:.1f}s")
    print(f"Results in: {out_dir}")
    print(f"  CSVs:   {list(out_dir.glob('*.csv'))}")
    print(f"  Plots:  {len(list(out_dir.glob('*.png')))} PNG files")
    print(f"  Report: {out_dir / 'deep_analysis_report.md'}")
    print("=" * 70)


def _generate_report(out_dir: Path, modules: set, n_runs: int, elapsed: float):
    """Generate a combined markdown report."""
    sections = [
        f"# Deep Analysis Report",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Total Runs:** {n_runs}",
        f"**Analysis Time:** {elapsed:.1f}s",
        "",
        "---",
        "",
    ]

    module_info = {
        1: ("Property Satisfaction Timeline",
            "Tracks when properties become satisfied/broken during runs. "
            "Produces regression curves showing state evolution over time.",
            ["property_timeline_curves.png", "property_timeline_by_task.png",
             "property_regression_rate.png"],
            "property_timeline.csv"),
        2: ("Cross-Router Coherence Analysis",
            "Measures router access patterns, entropy, and protocol state resets. "
            "Detects cross-router coherence violations.",
            ["coherence_entropy_switches.png", "coherence_protocol_resets.png",
             "coherence_router_heatmap.png"],
            "coherence_analysis.csv"),
        3: ("Turn Waste & Action Efficiency",
            "Classifies actions as productive, diagnostic, redundant, or coordination overhead. "
            "Quantifies the coordination tax of multi-agent patterns.",
            ["turn_waste_breakdown.png", "turn_waste_coordination.png",
             "turn_waste_vs_score.png"],
            "turn_waste.csv"),
        4: ("Inter-Agent Communication Quality",
            "Analyzes agent conversations for plan redundancy, executor stalls, "
            "debate balance, and role activity distribution.",
            ["agent_comms_role_activity.png", "agent_comms_comparison.png"],
            "agent_comms.csv"),
        5: ("Error Cascade & Recovery",
            "Tracks temporal error sequences, cascade lengths, recovery times, "
            "and the relationship between error density and performance.",
            ["error_cascade_density.png", "error_cascade_recovery.png"],
            "error_cascade.csv"),
        6: ("Token Efficiency Dynamics",
            "Analyzes token consumption relative to progress: cost per property, "
            "marginal return curves, and pattern-specific token multipliers.",
            ["token_efficiency_scatter.png", "token_efficiency_per_property.png",
             "token_efficiency_marginal_return.png", "token_efficiency_multiplier.png"],
            "token_efficiency.csv"),
        7: ("Per-Model Pattern Sensitivity",
            "Tests whether the optimal agentic pattern changes depending on the model. "
            "Computes pattern lift, best pattern stability, and model-specific scores.",
            ["model_sensitivity_lift_heatmap.png", "model_sensitivity_best_pattern.png",
             "model_sensitivity_scores.png"],
            "model_sensitivity.csv"),
        8: ("Troubleshooting vs Construction Split",
            "Compares behavioral signatures (command types, entropy, coordination overhead) "
            "between construction and troubleshooting tasks with statistical tests.",
            ["task_type_behavioral_split.png", "task_type_pattern_scores.png",
             "task_type_coordination.png"],
            "task_type_split.csv"),
        9: ("Pattern Deep Profiles",
            "Investigates pattern-specific phenomena: Debate Paradox (token premium vs score delta), "
            "Group Chat role dominance, Sequential convergence momentum, Concurrent worker overlap.",
            ["pattern_debate_paradox.png", "pattern_gc_analyzer_trap.png",
             "pattern_sequential_convergence.png", "pattern_concurrent_divergence.png",
             "pattern_radar_fingerprints.png"],
            "pattern_deep_profiles.csv"),
    }

    for mod_num in sorted(modules):
        if mod_num not in module_info:
            continue
        title, desc, plots, csv_file = module_info[mod_num]
        sections.append(f"## Module {mod_num}: {title}")
        sections.append(f"\n{desc}\n")

        for plot in plots:
            if (out_dir / plot).exists():
                sections.append(f"![{plot}]({plot})\n")

        sections.append(f"**Data:** [{csv_file}]({csv_file})\n")
        sections.append("---\n")

    sections.append(
        "\n*Deep analysis supporting the multi-agent comparative study paper.*"
    )

    with open(out_dir / "deep_analysis_report.md", "w") as f:
        f.write("\n".join(sections))


if __name__ == "__main__":
    main()
