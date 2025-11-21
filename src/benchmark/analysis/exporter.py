"""
Export analysis results to various formats.

Supports JSON (complete data) and CSV (summaries) exports.
"""
import json
import csv
from pathlib import Path
from typing import List
from datetime import datetime

from benchmark.models.analysis import AnalysisResult


class AnalysisExporter:
    """Export analysis results to JSON and CSV formats"""

    def export_json(self, analysis: AnalysisResult, output_dir: Path) -> str:
        """
        Export analysis result as JSON (detailed, complete data).

        Args:
            analysis: AnalysisResult to export
            output_dir: Directory to save the file

        Returns:
            Path to the exported JSON file
        """
        # Create output directory if it doesn't exist
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename
        filename = f"{analysis.analysis_id}.json"
        file_path = output_dir / filename

        # Convert to dict
        data = analysis.model_dump()

        # Convert datetime to ISO string
        if "timestamp" in data and isinstance(data["timestamp"], datetime):
            data["timestamp"] = data["timestamp"].isoformat()

        # Write JSON
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)

        return str(file_path)

    def export_csv_summary(self, analysis: AnalysisResult, output_dir: Path) -> str:
        """
        Export analysis result as CSV summary (for Excel/R/Python).

        Format depends on analysis type:
        - Testee: rows=properties, cols=metrics
        - Comparison: rows=testees, cols=scores+stats
        - Property: rows=testees, cols=property_metrics

        Args:
            analysis: AnalysisResult to export
            output_dir: Directory to save the file

        Returns:
            Path to the exported CSV file
        """
        # Create output directory if it doesn't exist
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename
        filename = f"{analysis.analysis_id}_summary.csv"
        file_path = output_dir / filename

        if analysis.analysis_type == "testee":
            self._export_testee_csv(analysis, file_path)
        elif analysis.analysis_type == "comparison":
            self._export_comparison_csv(analysis, file_path)
        elif analysis.analysis_type == "property":
            self._export_property_csv(analysis, file_path)
        else:
            raise ValueError(f"Unknown analysis type: {analysis.analysis_type}")

        return str(file_path)

    def _export_testee_csv(self, analysis: AnalysisResult, file_path: Path):
        """Export testee analysis to CSV"""
        testee_analysis = analysis.testee_analysis
        
        if not testee_analysis:
            raise ValueError("Testee analysis is None")

        with open(file_path, 'w', newline='') as f:
            writer = csv.writer(f)

            # Header
            writer.writerow([
                "property_type",
                "total_tasks",
                "successful_tasks",
                "completeness",
                "robustness",
                "syntactic_validity",
                "efficiency",
                "final_score",
            ])

            # Property breakdown rows
            for prop_type, stats in testee_analysis.property_breakdown.items():
                writer.writerow([
                    prop_type,
                    stats.total_tasks,
                    stats.successful_tasks,
                    stats.aggregate_scores.completeness,
                    stats.aggregate_scores.robustness,
                    stats.aggregate_scores.syntactic_validity,
                    stats.aggregate_scores.efficiency if stats.aggregate_scores.efficiency else "",
                    stats.aggregate_scores.final_score,
                ])

            # Overall aggregate row
            writer.writerow([
                "OVERALL",
                testee_analysis.total_runs,
                "-",
                testee_analysis.aggregate_scores.completeness,
                testee_analysis.aggregate_scores.robustness,
                testee_analysis.aggregate_scores.syntactic_validity,
                testee_analysis.aggregate_scores.efficiency if testee_analysis.aggregate_scores.efficiency else "",
                testee_analysis.aggregate_scores.final_score,
            ])

    def _export_comparison_csv(self, analysis: AnalysisResult, file_path: Path):
        """Export comparison analysis to CSV"""
        comparison_analysis = analysis.comparison_analysis
        
        if not comparison_analysis:
            raise ValueError("Comparison analysis is None")

        with open(file_path, 'w', newline='') as f:
            writer = csv.writer(f)

            # Header
            writer.writerow([
                "testee_id",
                "total_runs",
                "completeness",
                "robustness",
                "syntactic_validity",
                "efficiency",
                "final_score",
            ])

            # Testee rows
            for testee_id in comparison_analysis.testees:
                total_runs = comparison_analysis.total_runs_per_testee.get(testee_id, 0)
                scores = comparison_analysis.score_comparison.testee_scores.get(testee_id)
                
                if scores:
                    writer.writerow([
                        testee_id,
                        total_runs,
                        scores.completeness,
                        scores.robustness,
                        scores.syntactic_validity,
                        scores.efficiency if scores.efficiency else "",
                        scores.final_score,
                    ])

            # Statistical test results row
            writer.writerow([])  # Empty row
            writer.writerow(["Statistical Test Results"])
            
            stats = comparison_analysis.statistical_tests
            if stats.test_type == "t-test" and stats.ttest_result:
                writer.writerow(["Test Type", "t-test"])
                writer.writerow(["T-statistic", stats.ttest_result.t_statistic])
                writer.writerow(["P-value", stats.ttest_result.p_value])
                writer.writerow(["Effect Size (Cohen's d)", stats.ttest_result.effect_size])
                writer.writerow(["Mean Difference", stats.ttest_result.mean_diff])
                writer.writerow(["95% CI Lower", stats.ttest_result.confidence_interval[0]])
                writer.writerow(["95% CI Upper", stats.ttest_result.confidence_interval[1]])
            elif stats.test_type == "anova" and stats.anova_result:
                writer.writerow(["Test Type", "ANOVA"])
                writer.writerow(["F-statistic", stats.anova_result.f_statistic])
                writer.writerow(["P-value", stats.anova_result.p_value])

    def _export_property_csv(self, analysis: AnalysisResult, file_path: Path):
        """Export property analysis to CSV"""
        property_analysis = analysis.property_analysis
        
        if not property_analysis:
            raise ValueError("Property analysis is None")

        with open(file_path, 'w', newline='') as f:
            writer = csv.writer(f)

            # Header
            writer.writerow([
                "testee_id",
                "total_tasks",
                "successful_tasks",
                "completeness",
                "robustness",
                "syntactic_validity",
                "efficiency",
                "final_score",
            ])

            # Testee rows
            for testee_id, stats in property_analysis.testee_breakdown.items():
                writer.writerow([
                    testee_id,
                    stats.total_tasks,
                    stats.successful_tasks,
                    stats.aggregate_scores.completeness,
                    stats.aggregate_scores.robustness,
                    stats.aggregate_scores.syntactic_validity,
                    stats.aggregate_scores.efficiency if stats.aggregate_scores.efficiency else "",
                    stats.aggregate_scores.final_score,
                ])

            # Task difficulty section
            if property_analysis.task_difficulty:
                writer.writerow([])  # Empty row
                writer.writerow(["Task Difficulty (Average Score)"])
                writer.writerow(["task_id", "average_score"])
                
                for task_id, avg_score in sorted(
                    property_analysis.task_difficulty.items(),
                    key=lambda x: x[1]  # Sort by score
                ):
                    writer.writerow([task_id, avg_score])

    def export_csv_detailed(self, analysis: AnalysisResult, output_dir: Path) -> List[str]:
        """
        Export detailed CSVs (multiple files).

        Creates separate CSV files for:
        - Summary (same as export_csv_summary)
        - Additional details depending on analysis type

        Args:
            analysis: AnalysisResult to export
            output_dir: Directory to save the files

        Returns:
            List of paths to created CSV files
        """
        # Create output directory if it doesn't exist
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        created_files = []

        # Export summary
        summary_file = self.export_csv_summary(analysis, output_dir)
        created_files.append(summary_file)

        # Additional exports based on type can be added here in future
        # For now, just return the summary

        return created_files

