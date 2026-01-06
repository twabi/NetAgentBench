"""
Session Analyzer for benchmark study sessions.

Analyzes all runs within a session folder, compares models, 
generates charts, and creates explanatory markdown reports.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class ModelStats:
    """Statistics for a single model."""
    model_name: str
    total_runs: int = 0
    successful_runs: int = 0
    avg_final_score: float = 0.0
    avg_completeness: float = 0.0
    avg_robustness: float = 0.0
    avg_syntactic_validity: float = 0.0
    avg_efficiency: float = 0.0
    # Per-property breakdown with full metrics
    property_scores: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # Per-task difficulty scores (task_id -> avg_score)
    task_difficulty: Dict[str, float] = field(default_factory=dict)


@dataclass
class SessionAnalysis:
    """Complete analysis of a benchmark session."""
    session_name: str
    session_path: Path
    models: List[str]
    property_types: List[str]
    model_stats: Dict[str, ModelStats]
    comparison_table: List[Dict[str, Any]]
    insights: List[str]
    


class SessionAnalyzer:
    """Analyzer for benchmark study sessions."""
    
    def __init__(self, session_path: str):
        """
        Initialize session analyzer.
        
        Args:
            session_path: Path to session folder (e.g., results/sessions/baseline_study_xxx)
        """
        self.session_path = Path(session_path)
        self.property_results_dir = self.session_path / "property_results"
        self.runs_dir = self.session_path / "runs"
        self.session_info = self._load_session_info()
        
    def _load_session_info(self) -> Dict[str, Any]:
        """Load session metadata."""
        info_path = self.session_path / "session_info.json"
        if info_path.exists():
            with open(info_path) as f:
                return json.load(f)
        return {}
    
    def _load_property_results(self) -> List[Dict[str, Any]]:
        """Load all property result files."""
        results = []
        if not self.property_results_dir.exists():
            logger.warning(f"No property_results dir in {self.session_path}")
            return results
            
        for file in self.property_results_dir.glob("*.json"):
            with open(file) as f:
                data = json.load(f)
                # Tag with filename for identification
                data["_source_file"] = file.name
                results.append(data)
        return results
    
    def _extract_model_from_run(self, run: Dict[str, Any]) -> str:
        """Extract model name from a run result."""
        # Try model_version first
        model_version = run.get("model_version")
        if model_version:
            # Format: "provider:model_name" or just model name
            if ":" in model_version:
                return model_version.split(":", 1)[1]
            return model_version
        
        # Fallback: try to infer from testee_id
        testee_id = run.get("testee_id", "unknown")
        return testee_id
    
    def _infer_model_from_filename(self, filename: str, models: List[str]) -> str:
        """Infer which model produced a result based on ordering in session."""
        # Property results are saved in order of execution
        # First half is first model, second half is second model
        # This is a heuristic based on the session structure
        return "unknown"
    
    def analyze(self) -> SessionAnalysis:
        """
        Perform complete session analysis.
        
        Returns:
            SessionAnalysis with all metrics and comparisons
        """
        property_results = self._load_property_results()
        
        if not property_results:
            raise ValueError(f"No property results found in {self.session_path}")
        
        # Group runs by model and property type
        models_data: Dict[str, Dict[str, List[Dict]]] = defaultdict(lambda: defaultdict(list))
        
        for prop_result in property_results:
            property_type = prop_result.get("property_type", "unknown")
            
            for run in prop_result.get("results", []):
                model = self._extract_model_from_run(run)
                models_data[model][property_type].append(run)
        
        # If we only got one model from run data but session_info lists multiple models,
        # try to split by file ordering (files are created in execution order)
        session_models = self.session_info.get("models", [])
        if len(models_data) == 1 and len(session_models) >= 2:
            # Use file-based splitting since model_version is likely null
            models_data = self._split_by_ordering(property_results, session_models)
        
        # Compute stats for each model
        model_stats = {}
        for model_name, property_runs in models_data.items():
            stats = self._compute_model_stats(model_name, property_runs)
            model_stats[model_name] = stats
        
        # Generate comparison table
        comparison_table = self._generate_comparison_table(model_stats)
        
        # Generate insights
        insights = self._generate_insights(model_stats, comparison_table)
        
        return SessionAnalysis(
            session_name=self.session_info.get("session_name", self.session_path.name),
            session_path=self.session_path,
            models=list(model_stats.keys()),
            property_types=list(set(
                pt for stats in model_stats.values() 
                for pt in stats.property_scores.keys()
            )),
            model_stats=model_stats,
            comparison_table=comparison_table,
            insights=insights,
        )
    
    def _split_by_ordering(
        self, 
        property_results: List[Dict], 
        session_models: List[str]
    ) -> Dict[str, Dict[str, List[Dict]]]:
        """Split results by file ordering when model info is missing."""
        models_data: Dict[str, Dict[str, List[Dict]]] = defaultdict(lambda: defaultdict(list))
        
        # Group files by property type
        files_by_property: Dict[str, List[Dict]] = defaultdict(list)
        for prop_result in property_results:
            pt = prop_result.get("property_type", "unknown")
            files_by_property[pt].append(prop_result)
        
        # For each property type, first file is model[0], second is model[1]
        for pt, files in files_by_property.items():
            # Sort by source filename (contains timestamp)
            files.sort(key=lambda x: x.get("_source_file", ""))
            
            for i, prop_result in enumerate(files):
                if i < len(session_models):
                    model = session_models[i]
                else:
                    model = f"model_{i}"
                    
                for run in prop_result.get("results", []):
                    models_data[model][pt].append(run)
        
        return models_data
    
    def _compute_model_stats(
        self, 
        model_name: str, 
        property_runs: Dict[str, List[Dict]]
    ) -> ModelStats:
        """Compute aggregate statistics for a model."""
        stats = ModelStats(model_name=model_name)
        
        all_scores = []
        all_completeness = []
        all_robustness = []
        all_validity = []
        all_efficiency = []
        
        # Track per-task scores for difficulty calculation
        task_scores: Dict[str, List[float]] = defaultdict(list)
        
        for property_type, runs in property_runs.items():
            prop_scores = []
            prop_completeness = []
            prop_robustness = []
            prop_validity = []
            prop_efficiency = []
            prop_success = 0
            
            for run in runs:
                stats.total_runs += 1
                if run.get("success"):
                    stats.successful_runs += 1
                    prop_success += 1
                
                scoring = run.get("scoring", {})
                final_score = scoring.get("final_score", 0)
                completeness = scoring.get("completeness", 0)
                robustness = scoring.get("robustness", 0)
                validity = scoring.get("syntactic_validity", 0)
                efficiency = scoring.get("efficiency")
                
                all_scores.append(final_score)
                all_completeness.append(completeness)
                all_robustness.append(robustness)
                all_validity.append(validity)
                if efficiency is not None:
                    all_efficiency.append(efficiency)
                
                prop_scores.append(final_score)
                prop_completeness.append(completeness)
                prop_robustness.append(robustness)
                prop_validity.append(validity)
                if efficiency is not None:
                    prop_efficiency.append(efficiency)
                
                # Track per-task scores
                task_id = run.get("task_id", "unknown")
                task_scores[task_id].append(final_score)
            
            # Store per-property stats with full metrics
            if prop_scores:
                stats.property_scores[property_type] = {
                    "avg_score": sum(prop_scores) / len(prop_scores),
                    "avg_completeness": sum(prop_completeness) / len(prop_completeness),
                    "avg_robustness": sum(prop_robustness) / len(prop_robustness),
                    "avg_syntactic_validity": sum(prop_validity) / len(prop_validity),
                    "avg_efficiency": sum(prop_efficiency) / len(prop_efficiency) if prop_efficiency else None,
                    "success_rate": prop_success / len(runs) if runs else 0,
                    "total_runs": len(runs),
                    "successful_runs": prop_success,
                }
        
        # Compute task difficulty (average score per task)
        for task_id, scores in task_scores.items():
            stats.task_difficulty[task_id] = sum(scores) / len(scores)
        
        # Compute overall averages
        if all_scores:
            stats.avg_final_score = sum(all_scores) / len(all_scores)
            stats.avg_completeness = sum(all_completeness) / len(all_completeness)
            stats.avg_robustness = sum(all_robustness) / len(all_robustness)
            stats.avg_syntactic_validity = sum(all_validity) / len(all_validity)
        if all_efficiency:
            stats.avg_efficiency = sum(all_efficiency) / len(all_efficiency)
        
        return stats
    
    def _generate_comparison_table(
        self, 
        model_stats: Dict[str, ModelStats]
    ) -> List[Dict[str, Any]]:
        """Generate comparison table data."""
        rows = []
        
        # Get all property types
        all_properties = set()
        for stats in model_stats.values():
            all_properties.update(stats.property_scores.keys())
        
        # Overall row
        overall_row = {"metric": "Overall"}
        for model, stats in model_stats.items():
            overall_row[f"{model}_score"] = stats.avg_final_score
            overall_row[f"{model}_success"] = f"{stats.successful_runs}/{stats.total_runs}"
        rows.append(overall_row)
        
        # Per-property rows
        for prop in sorted(all_properties):
            row = {"metric": prop}
            for model, stats in model_stats.items():
                prop_stats = stats.property_scores.get(prop, {})
                row[f"{model}_score"] = prop_stats.get("avg_score", 0)
                row[f"{model}_completeness"] = prop_stats.get("avg_completeness", 0)
                success = prop_stats.get("successful_runs", 0)
                total = prop_stats.get("total_runs", 0)
                row[f"{model}_success"] = f"{success}/{total}"
            rows.append(row)
        
        return rows
    
    def _generate_insights(
        self, 
        model_stats: Dict[str, ModelStats],
        comparison_table: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate analytical insights from the data."""
        insights = []
        
        if len(model_stats) < 2:
            insights.append("Only one model tested - no comparison available.")
            return insights
        
        models = list(model_stats.keys())
        
        # Compare overall scores
        scores = [(m, s.avg_final_score) for m, s in model_stats.items()]
        scores.sort(key=lambda x: x[1], reverse=True)
        
        best_model, best_score = scores[0]
        worst_model, worst_score = scores[-1]
        
        if best_score > worst_score:
            diff_pct = ((best_score - worst_score) / worst_score * 100) if worst_score > 0 else 0
            insights.append(
                f"**{best_model}** outperformed **{worst_model}** by {diff_pct:.1f}% overall "
                f"(avg score: {best_score:.3f} vs {worst_score:.3f})."
            )
        else:
            insights.append(f"Models performed similarly with average scores around {best_score:.3f}.")
        
        # Analyze per-property differences
        all_properties = set()
        for stats in model_stats.values():
            all_properties.update(stats.property_scores.keys())
        
        for prop in all_properties:
            prop_scores = []
            for model, stats in model_stats.items():
                if prop in stats.property_scores:
                    prop_scores.append((model, stats.property_scores[prop]["avg_score"]))
            
            if len(prop_scores) >= 2:
                prop_scores.sort(key=lambda x: x[1], reverse=True)
                best_m, best_s = prop_scores[0]
                worst_m, worst_s = prop_scores[-1]
                
                if best_s > worst_s + 0.1:  # Significant difference
                    insights.append(
                        f"For **{prop}**: {best_m} scored {best_s:.3f} vs {worst_m}'s {worst_s:.3f}."
                    )
        
        # Success rate analysis
        success_rates = [
            (m, s.successful_runs / s.total_runs if s.total_runs > 0 else 0) 
            for m, s in model_stats.items()
        ]
        success_rates.sort(key=lambda x: x[1], reverse=True)
        
        best_success_model, best_rate = success_rates[0]
        insights.append(
            f"Highest success rate: **{best_success_model}** at {best_rate*100:.1f}%."
        )
        
        return insights


def generate_session_report(session_path: str) -> Path:
    """
    Generate comprehensive analysis report for a session.
    
    Args:
        session_path: Path to session folder
        
    Returns:
        Path to generated report
    """
    analyzer = SessionAnalyzer(session_path)
    analysis = analyzer.analyze()
    
    # Generate markdown report
    report_path = analysis.session_path / "analysis_report.md"
    
    report_lines = [
        f"# Benchmark Analysis Report",
        f"",
        f"**Session:** {analysis.session_name}",
        f"**Generated:** {datetime.now().isoformat()}",
        f"**Models Tested:** {', '.join(analysis.models)}",
        f"**Property Types:** {', '.join(analysis.property_types)}",
        f"",
        f"---",
        f"",
        f"## Executive Summary",
        f"",
    ]
    
    # Add insights
    for insight in analysis.insights:
        report_lines.append(f"- {insight}")
    
    report_lines.extend([
        f"",
        f"---",
        f"",
        f"## Detailed Results",
        f"",
        f"### Overall Model Comparison",
        f"",
    ])
    
    # Create comparison table
    models = list(analysis.model_stats.keys())
    if models:
        header = "| Metric |"
        sep = "|--------|"
        for m in models:
            header += f" {m} |"
            sep += "--------|"
        report_lines.append(header)
        report_lines.append(sep)
        
        for row in analysis.comparison_table:
            line = f"| {row['metric']} |"
            for m in models:
                score = row.get(f"{m}_score", 0)
                success = row.get(f"{m}_success", "N/A")
                if isinstance(score, float):
                    line += f" {score:.3f} ({success}) |"
                else:
                    line += f" {score} |"
            report_lines.append(line)
    
    report_lines.extend([
        f"",
        f"---",
        f"",
        f"## Per-Model Breakdown",
        f"",
    ])
    
    for model_name, stats in analysis.model_stats.items():
        report_lines.extend([
            f"### {model_name}",
            f"",
            f"- **Total Runs:** {stats.total_runs}",
            f"- **Successful Runs:** {stats.successful_runs} ({stats.successful_runs/stats.total_runs*100:.1f}%)" if stats.total_runs > 0 else "- **Successful Runs:** 0",
            f"- **Average Final Score:** {stats.avg_final_score:.3f}",
            f"- **Average Completeness:** {stats.avg_completeness:.3f}",
            f"- **Average Robustness:** {stats.avg_robustness:.3f}",
            f"- **Syntactic Validity:** {stats.avg_syntactic_validity:.3f}",
            f"",
            f"#### Property Breakdown",
            f"",
            f"| Property Type | Avg Score | Completeness | Robustness | Syntactic Validity | Success Rate |",
            f"|--------------|-----------|--------------|------------|-------------------|--------------|",
        ])
        
        for prop, prop_stats in stats.property_scores.items():
            success_rate = prop_stats.get("success_rate", 0) * 100
            robustness = prop_stats.get("avg_robustness", 0)
            validity = prop_stats.get("avg_syntactic_validity", 0)
            report_lines.append(
                f"| {prop} | {prop_stats['avg_score']:.3f} | "
                f"{prop_stats['avg_completeness']:.3f} | {robustness:.3f} | "
                f"{validity:.3f} | {success_rate:.1f}% |"
            )
        
        # Add task difficulty section if available
        if stats.task_difficulty:
            report_lines.extend([
                f"",
                f"#### Task Difficulty Analysis",
                f"",
                f"Average scores per task (higher = easier):",
                f"",
                f"| Task ID | Avg Score |",
                f"|---------|-----------|",
            ])
            
            # Sort tasks by score (lowest first = hardest)
            sorted_tasks = sorted(stats.task_difficulty.items(), key=lambda x: x[1])
            for task_id, score in sorted_tasks[:10]:  # Show top 10 hardest
                report_lines.append(f"| {task_id} | {score:.3f} |")
            
            if len(sorted_tasks) > 10:
                report_lines.append(f"| ... | ({len(sorted_tasks) - 10} more tasks) |")
        
        report_lines.append("")
    
    report_lines.extend([
        f"---",
        f"",
        f"## Interpretation & Implications",
        f"",
        f"### Score Metrics Explained",
        f"",
        f"- **Final Score**: Weighted combination of all metrics (completeness 50%, robustness 30%, syntactic validity 20%)",
        f"- **Completeness**: Percentage of required properties satisfied",
        f"- **Robustness**: Resistance to evaluation noise (always 0 for single-turn)",
        f"- **Syntactic Validity**: Whether generated commands have correct syntax",
        f"- **Efficiency**: Command count relative to optimal solution (not included in final score)",
        f"",
        f"### Key Observations",
        f"",
    ])
    
    # Add contextual analysis
    for model_name, stats in analysis.model_stats.items():
        if stats.avg_completeness < 0.5:
            report_lines.append(
                f"- **{model_name}** struggled with completeness ({stats.avg_completeness:.1%}), "
                f"indicating difficulty generating correct network configurations."
            )
        elif stats.avg_completeness > 0.8:
            report_lines.append(
                f"- **{model_name}** showed strong completeness ({stats.avg_completeness:.1%}), "
                f"successfully configuring most network properties."
            )
        
        if stats.avg_syntactic_validity > 0.95:
            report_lines.append(
                f"- **{model_name}** produced syntactically valid commands ({stats.avg_syntactic_validity:.1%})."
            )
    
    report_lines.extend([
        f"",
        f"### Recommendations",
        f"",
        f"1. Focus debugging on property types with lowest completeness scores",
        f"2. Review failed runs to identify common configuration mistakes",
        f"3. Consider prompt engineering to improve LLM understanding of network topology",
        f"",
        f"---",
        f"",
        f"*Report generated automatically by benchmark session analyzer*",
    ])
    
    # Write report
    with open(report_path, "w") as f:
        f.write("\n".join(report_lines))
    
    logger.info(f"Analysis report saved to {report_path}")
    return report_path


def generate_session_charts(session_path: str) -> List[Path]:
    """
    Generate comparison charts for a session.
    
    Args:
        session_path: Path to session folder
        
    Returns:
        List of paths to generated chart files
    """
    try:
        import matplotlib.pyplot as plt
        import matplotlib
        matplotlib.use('Agg')  # Non-interactive backend
        import numpy as np
    except ImportError:
        logger.warning("matplotlib not available, skipping charts")
        return []
    
    # Academic/publication-quality styling
    plt.style.use('seaborn-v0_8-whitegrid')
    plt.rcParams.update({
        'font.size': 11,
        'font.family': 'serif',
        'axes.labelsize': 12,
        'axes.titlesize': 13,
        'axes.titleweight': 'bold',
        'xtick.labelsize': 10,
        'ytick.labelsize': 10,
        'legend.fontsize': 10,
        'figure.dpi': 150,
        'savefig.dpi': 300,
        'axes.spines.top': False,
        'axes.spines.right': False,
        'axes.grid': True,
        'grid.alpha': 0.3,
        'grid.linestyle': '--',
    })
    
    # Academic color palette (colorblind-friendly, print-safe)
    ACADEMIC_COLORS = ['#2E86AB', '#A23B72', '#F18F01', '#C73E1D', '#3B1F2B']
    HATCHES = ['///', '\\\\\\', 'xxx', '...', '+++']
    
    analyzer = SessionAnalyzer(session_path)
    analysis = analyzer.analyze()
    
    charts_dir = analysis.session_path / "charts"
    charts_dir.mkdir(exist_ok=True)
    
    chart_paths = []
    models = list(analysis.model_stats.keys())
    
    # Shorten model names for display
    def shorten_name(name: str, max_len: int = 20) -> str:
        if len(name) <= max_len:
            return name
        return name[:max_len-3] + "..."
    
    model_labels = [shorten_name(m) for m in models]
    
    if len(models) < 1:
        return chart_paths
    
    # Chart 1: Overall scores comparison
    fig, ax = plt.subplots(figsize=(8, 5))
    
    scores = [analysis.model_stats[m].avg_final_score for m in models]
    colors = ACADEMIC_COLORS[:len(models)]
    
    bars = ax.bar(model_labels, scores, color=colors, edgecolor='black', linewidth=0.8)
    
    # Add hatching for print compatibility
    for bar, hatch in zip(bars, HATCHES[:len(bars)]):
        bar.set_hatch(hatch)
    
    ax.set_ylabel('Average Final Score', fontweight='bold')
    ax.set_xlabel('Model', fontweight='bold')
    ax.set_title('Overall Model Performance Comparison')
    ax.set_ylim(0, 1.05)
    
    # Add value labels on bars
    for bar, score in zip(bars, scores):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                f'{score:.3f}', ha='center', va='bottom', fontsize=9, fontweight='bold')
    
    # Add horizontal reference lines
    ax.axhline(y=0.5, color='gray', linestyle=':', alpha=0.5, label='50% threshold')
    
    plt.tight_layout()
    chart_path = charts_dir / "overall_comparison.png"
    plt.savefig(chart_path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()
    chart_paths.append(chart_path)
    
    # Chart 2: Per-property comparison
    properties = list(analysis.property_types)
    if properties:
        fig, ax = plt.subplots(figsize=(10, 5))
        
        x = np.arange(len(properties))
        width = 0.35
        
        for i, model in enumerate(models):
            stats = analysis.model_stats[model]
            prop_scores = [
                stats.property_scores.get(p, {}).get("avg_score", 0) 
                for p in properties
            ]
            offset = (i - len(models)/2 + 0.5) * width
            bars = ax.bar([xi + offset for xi in x], prop_scores, width, 
                         label=shorten_name(model), color=colors[i % len(colors)],
                         edgecolor='black', linewidth=0.5, hatch=HATCHES[i % len(HATCHES)])
        
        ax.set_ylabel('Average Score', fontweight='bold')
        ax.set_xlabel('Property Type', fontweight='bold')
        ax.set_title('Performance by Property Type')
        ax.set_xticks(x)
        ax.set_xticklabels([p.replace('_', ' ').title() for p in properties], rotation=30, ha='right')
        ax.legend(loc='upper right', frameon=True, fancybox=False, edgecolor='black')
        ax.set_ylim(0, 1.05)
        ax.axhline(y=0.5, color='gray', linestyle=':', alpha=0.5)
        
        plt.tight_layout()
        chart_path = charts_dir / "property_comparison.png"
        plt.savefig(chart_path, dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()
        chart_paths.append(chart_path)
    
    # Chart 3: Metric breakdown bar chart
    fig, ax = plt.subplots(figsize=(9, 5))
    
    metrics = ['Completeness', 'Robustness', 'Syntactic\nValidity']
    x = np.arange(len(metrics))
    width = 0.35
    
    for i, model in enumerate(models):
        stats = analysis.model_stats[model]
        values = [
            stats.avg_completeness,
            stats.avg_robustness,
            stats.avg_syntactic_validity,
        ]
        offset = (i - len(models)/2 + 0.5) * width
        bars = ax.bar([xi + offset for xi in x], values, width, 
               label=shorten_name(model), color=colors[i % len(colors)],
               edgecolor='black', linewidth=0.5, hatch=HATCHES[i % len(HATCHES)])
        
        # Add value labels
        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                    f'{val:.2f}', ha='center', va='bottom', fontsize=8)
    
    ax.set_ylabel('Score', fontweight='bold')
    ax.set_xlabel('Metric', fontweight='bold')
    ax.set_title('Scoring Metric Breakdown')
    ax.set_xticks(x)
    ax.set_xticklabels(metrics)
    ax.legend(loc='upper right', frameon=True, fancybox=False, edgecolor='black')
    ax.set_ylim(0, 1.15)
    
    plt.tight_layout()
    chart_path = charts_dir / "metric_breakdown.png"
    plt.savefig(chart_path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()
    chart_paths.append(chart_path)
    
    # Chart 4: Per-property robustness comparison
    if properties:
        fig, ax = plt.subplots(figsize=(10, 5))
        
        x = np.arange(len(properties))
        width = 0.35
        
        for i, model in enumerate(models):
            stats = analysis.model_stats[model]
            robustness_scores = [
                stats.property_scores.get(p, {}).get("avg_robustness", 0) 
                for p in properties
            ]
            offset = (i - len(models)/2 + 0.5) * width
            ax.bar([xi + offset for xi in x], robustness_scores, width, 
                   label=shorten_name(model), color=colors[i % len(colors)],
                   edgecolor='black', linewidth=0.5, hatch=HATCHES[i % len(HATCHES)])
        
        ax.set_ylabel('Robustness Score', fontweight='bold')
        ax.set_xlabel('Property Type', fontweight='bold')
        ax.set_title('Robustness by Property Type')
        ax.set_xticks(x)
        ax.set_xticklabels([p.replace('_', ' ').title() for p in properties], rotation=30, ha='right')
        ax.legend(loc='upper right', frameon=True, fancybox=False, edgecolor='black')
        ax.set_ylim(0, 1.05)
        
        plt.tight_layout()
        chart_path = charts_dir / "property_robustness_comparison.png"
        plt.savefig(chart_path, dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()
        chart_paths.append(chart_path)
    
    # Chart 5: Per-property syntactic validity comparison
    if properties:
        fig, ax = plt.subplots(figsize=(10, 5))
        
        x = np.arange(len(properties))
        width = 0.35
        
        for i, model in enumerate(models):
            stats = analysis.model_stats[model]
            validity_scores = [
                stats.property_scores.get(p, {}).get("avg_syntactic_validity", 0) 
                for p in properties
            ]
            offset = (i - len(models)/2 + 0.5) * width
            ax.bar([xi + offset for xi in x], validity_scores, width, 
                   label=shorten_name(model), color=colors[i % len(colors)],
                   edgecolor='black', linewidth=0.5, hatch=HATCHES[i % len(HATCHES)])
        
        ax.set_ylabel('Syntactic Validity Score', fontweight='bold')
        ax.set_xlabel('Property Type', fontweight='bold')
        ax.set_title('Syntactic Validity by Property Type')
        ax.set_xticks(x)
        ax.set_xticklabels([p.replace('_', ' ').title() for p in properties], rotation=30, ha='right')
        ax.legend(loc='upper right', frameon=True, fancybox=False, edgecolor='black')
        ax.set_ylim(0, 1.05)
        
        plt.tight_layout()
        chart_path = charts_dir / "property_syntactic_validity_comparison.png"
        plt.savefig(chart_path, dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()
        chart_paths.append(chart_path)
    
    # Chart 6: Task difficulty distribution
    all_task_scores = []
    for model in models:
        stats = analysis.model_stats[model]
        all_task_scores.extend(stats.task_difficulty.values())
    
    if all_task_scores:
        fig, ax = plt.subplots(figsize=(9, 5))
        
        bins = np.linspace(0, 1, 21)  # 20 bins from 0 to 1
        n, bins_out, patches = ax.hist(all_task_scores, bins=bins, 
                                        color=ACADEMIC_COLORS[0], edgecolor='black', 
                                        linewidth=0.5, alpha=0.8)
        
        mean_score = np.mean(all_task_scores)
        std_score = np.std(all_task_scores)
        
        ax.set_xlabel('Average Score (Higher = Easier)', fontweight='bold')
        ax.set_ylabel('Number of Tasks', fontweight='bold')
        ax.set_title('Task Difficulty Distribution')
        ax.axvline(x=mean_score, color='#C73E1D', linestyle='--', linewidth=2,
                   label=f'Mean: {mean_score:.3f}')
        ax.axvline(x=mean_score - std_score, color='#A23B72', linestyle=':', linewidth=1.5,
                   label=f'±1 SD: {std_score:.3f}')
        ax.axvline(x=mean_score + std_score, color='#A23B72', linestyle=':', linewidth=1.5)
        ax.legend(loc='upper left', frameon=True, fancybox=False, edgecolor='black')
        
        # Add summary statistics text box
        textstr = f'n = {len(all_task_scores)}\nμ = {mean_score:.3f}\nσ = {std_score:.3f}'
        props = dict(boxstyle='round', facecolor='white', edgecolor='black', alpha=0.8)
        ax.text(0.95, 0.95, textstr, transform=ax.transAxes, fontsize=9,
                verticalalignment='top', horizontalalignment='right', bbox=props)
        
        plt.tight_layout()
        chart_path = charts_dir / "task_difficulty_distribution.png"
        plt.savefig(chart_path, dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()
        chart_paths.append(chart_path)
    
    logger.info(f"Generated {len(chart_paths)} charts in {charts_dir}")
    return chart_paths

