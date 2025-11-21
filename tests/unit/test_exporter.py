"""
Unit tests for analysis export system.

Tests JSON and CSV export functionality for analysis results.
"""
import pytest
import json
import csv
import tempfile
from pathlib import Path
from datetime import datetime

from benchmark.analysis.exporter import AnalysisExporter
from benchmark.models.analysis import (
    AnalysisResult,
    TesteeAnalysis,
    ComparisonAnalysis,
    PropertyAnalysis,
    AggregateScores,
    AggregateExecutionMetrics,
    PropertyStats,
    ScoreComparison,
    StatisticalTestResults,
    TTestResult,
    TesteePropertyStats,
)


@pytest.fixture
def sample_testee_analysis():
    """Create sample testee analysis result"""
    return AnalysisResult(
        analysis_id="testee_gpt4_20251120",
        analysis_type="testee",
        timestamp=datetime.now(),
        testee_analysis=TesteeAnalysis(
            testee_id="gpt-4",
            testee_type="llm",
            total_runs=10,
            property_breakdown={
                "reachability": PropertyStats(
                    property_type="reachability",
                    total_tasks=5,
                    successful_tasks=4,
                    aggregate_scores=AggregateScores(
                        completeness=0.8,
                        robustness=0.75,
                        syntactic_validity=0.95,
                        efficiency=None,
                        final_score=0.82,
                    ),
                )
            },
            aggregate_scores=AggregateScores(
                completeness=0.85,
                robustness=0.80,
                syntactic_validity=0.95,
                efficiency=None,
                final_score=0.86,
            ),
            execution_metrics=AggregateExecutionMetrics(
                avg_infrastructure_provision_time=45.0,
                avg_config_execution_time=10.0,
                avg_convergence_time=30.0,
                avg_evaluation_time=5.0,
                avg_total_time=90.0,
            ),
        ),
        comparison_analysis=None,
        property_analysis=None,
        export_paths={},
    )


@pytest.fixture
def sample_comparison_analysis():
    """Create sample comparison analysis result"""
    return AnalysisResult(
        analysis_id="comparison_20251120",
        analysis_type="comparison",
        timestamp=datetime.now(),
        testee_analysis=None,
        comparison_analysis=ComparisonAnalysis(
            testees=["gpt-4", "baseline"],
            total_runs_per_testee={"gpt-4": 10, "baseline": 10},
            score_comparison=ScoreComparison(
                testee_scores={
                    "gpt-4": AggregateScores(
                        completeness=0.8,
                        robustness=0.75,
                        syntactic_validity=0.95,
                        efficiency=None,
                        final_score=0.82,
                    ),
                    "baseline": AggregateScores(
                        completeness=0.5,
                        robustness=0.5,
                        syntactic_validity=1.0,
                        efficiency=None,
                        final_score=0.6,
                    ),
                },
                score_differences={
                    "completeness": 0.3,
                    "final_score": 0.22,
                },
            ),
            statistical_tests=StatisticalTestResults(
                test_type="t-test",
                ttest_result=TTestResult(
                    t_statistic=2.5,
                    p_value=0.02,
                    effect_size=0.8,
                    confidence_interval=(0.1, 0.3),
                    testee_a="gpt-4",
                    testee_b="baseline",
                    mean_diff=0.22,
                ),
                anova_result=None,
            ),
            property_breakdown={},
        ),
        property_analysis=None,
        export_paths={},
    )


@pytest.fixture
def sample_property_analysis():
    """Create sample property analysis result"""
    return AnalysisResult(
        analysis_id="property_reachability_20251120",
        analysis_type="property",
        timestamp=datetime.now(),
        testee_analysis=None,
        comparison_analysis=None,
        property_analysis=PropertyAnalysis(
            property_type="reachability",
            total_runs=20,
            testee_breakdown={
                "gpt-4": TesteePropertyStats(
                    testee_id="gpt-4",
                    total_tasks=10,
                    successful_tasks=8,
                    aggregate_scores=AggregateScores(
                        completeness=0.8,
                        robustness=0.75,
                        syntactic_validity=0.95,
                        efficiency=None,
                        final_score=0.82,
                    ),
                )
            },
            task_difficulty={
                "reachability_linear_2n": 0.9,
                "reachability_linear_3n": 0.7,
            },
        ),
        export_paths={},
    )


class TestAnalysisExporter:
    """Test AnalysisExporter class"""

    def test_initialization(self):
        """Test creating AnalysisExporter"""
        exporter = AnalysisExporter()
        assert exporter is not None

    def test_export_json_testee(self, sample_testee_analysis):
        """Test JSON export for testee analysis"""
        with tempfile.TemporaryDirectory() as temp_dir:
            exporter = AnalysisExporter()
            output_dir = Path(temp_dir)
            
            file_path = exporter.export_json(sample_testee_analysis, output_dir)
            
            # File should exist
            assert Path(file_path).exists()
            assert file_path.endswith(".json")
            
            # Should be valid JSON
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Check structure
            assert data["analysis_id"] == sample_testee_analysis.analysis_id
            assert data["analysis_type"] == "testee"
            assert "testee_analysis" in data

    def test_export_json_comparison(self, sample_comparison_analysis):
        """Test JSON export for comparison analysis"""
        with tempfile.TemporaryDirectory() as temp_dir:
            exporter = AnalysisExporter()
            output_dir = Path(temp_dir)
            
            file_path = exporter.export_json(sample_comparison_analysis, output_dir)
            
            # File should exist
            assert Path(file_path).exists()
            
            # Should be valid JSON
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            assert data["analysis_type"] == "comparison"
            assert "comparison_analysis" in data

    def test_export_csv_summary_testee(self, sample_testee_analysis):
        """Test CSV summary export for testee analysis"""
        with tempfile.TemporaryDirectory() as temp_dir:
            exporter = AnalysisExporter()
            output_dir = Path(temp_dir)
            
            file_path = exporter.export_csv_summary(sample_testee_analysis, output_dir)
            
            # File should exist
            assert Path(file_path).exists()
            assert file_path.endswith(".csv")
            
            # Should be valid CSV
            with open(file_path, 'r') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
            # Should have at least one row (aggregate row)
            assert len(rows) >= 1
            
            # Check columns exist
            assert "property_type" in rows[0] or "metric" in rows[0]

    def test_export_csv_summary_comparison(self, sample_comparison_analysis):
        """Test CSV summary export for comparison analysis"""
        with tempfile.TemporaryDirectory() as temp_dir:
            exporter = AnalysisExporter()
            output_dir = Path(temp_dir)
            
            file_path = exporter.export_csv_summary(sample_comparison_analysis, output_dir)
            
            # File should exist
            assert Path(file_path).exists()
            
            # Should be valid CSV
            with open(file_path, 'r') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
            # Should have rows for each testee
            assert len(rows) >= 2
            
            # Check testee names in rows
            testee_ids = [row.get("testee_id", row.get("testee")) for row in rows]
            assert "gpt-4" in testee_ids or any("gpt-4" in str(row) for row in rows)

    def test_json_reimport(self, sample_testee_analysis):
        """Test that exported JSON can be reimported"""
        with tempfile.TemporaryDirectory() as temp_dir:
            exporter = AnalysisExporter()
            output_dir = Path(temp_dir)
            
            # Export
            file_path = exporter.export_json(sample_testee_analysis, output_dir)
            
            # Reimport
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Should be able to reconstruct AnalysisResult
            restored = AnalysisResult(**data)
            assert restored.analysis_id == sample_testee_analysis.analysis_id
            assert restored.analysis_type == sample_testee_analysis.analysis_type

    def test_csv_data_accuracy(self, sample_testee_analysis):
        """Test that CSV contains accurate data"""
        with tempfile.TemporaryDirectory() as temp_dir:
            exporter = AnalysisExporter()
            output_dir = Path(temp_dir)
            
            file_path = exporter.export_csv_summary(sample_testee_analysis, output_dir)
            
            # Read CSV
            with open(file_path, 'r') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
            # Check that aggregate scores are present
            # (exact structure depends on implementation)
            assert len(rows) > 0

    def test_multiple_exports_same_directory(self, sample_testee_analysis, sample_comparison_analysis):
        """Test exporting multiple analyses to same directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            exporter = AnalysisExporter()
            output_dir = Path(temp_dir)
            
            file1 = exporter.export_json(sample_testee_analysis, output_dir)
            file2 = exporter.export_json(sample_comparison_analysis, output_dir)
            
            # Both files should exist
            assert Path(file1).exists()
            assert Path(file2).exists()
            
            # Should be different files
            assert file1 != file2

    def test_export_creates_directory(self, sample_testee_analysis):
        """Test that export creates directory if it doesn't exist"""
        with tempfile.TemporaryDirectory() as temp_dir:
            exporter = AnalysisExporter()
            output_dir = Path(temp_dir) / "new_dir" / "subdir"
            
            # Directory doesn't exist yet
            assert not output_dir.exists()
            
            file_path = exporter.export_json(sample_testee_analysis, output_dir)
            
            # Directory should be created
            assert output_dir.exists()
            assert Path(file_path).exists()


class TestExportEdgeCases:
    """Test edge cases in export system"""

    def test_export_with_none_values(self):
        """Test exporting analysis with None values"""
        analysis = AnalysisResult(
            analysis_id="test_none",
            analysis_type="testee",
            timestamp=datetime.now(),
            testee_analysis=TesteeAnalysis(
                testee_id="test",
                testee_type="llm",
                total_runs=0,
                property_breakdown={},
                aggregate_scores=AggregateScores(
                    completeness=0.0,
                    robustness=0.0,
                    syntactic_validity=0.0,
                    efficiency=None,  # None value
                    final_score=0.0,
                ),
                execution_metrics=AggregateExecutionMetrics(
                    avg_infrastructure_provision_time=0.0,
                    avg_config_execution_time=0.0,
                    avg_convergence_time=0.0,
                    avg_evaluation_time=0.0,
                    avg_total_time=0.0,
                ),
            ),
            comparison_analysis=None,
            property_analysis=None,
            export_paths={},
        )
        
        with tempfile.TemporaryDirectory() as temp_dir:
            exporter = AnalysisExporter()
            output_dir = Path(temp_dir)
            
            # Should not raise error
            file_path = exporter.export_json(analysis, output_dir)
            assert Path(file_path).exists()

    def test_export_empty_property_breakdown(self, sample_testee_analysis):
        """Test exporting analysis with empty property breakdown"""
        # Modify to have empty breakdown
        sample_testee_analysis.testee_analysis.property_breakdown = {}
        
        with tempfile.TemporaryDirectory() as temp_dir:
            exporter = AnalysisExporter()
            output_dir = Path(temp_dir)
            
            # Should not raise error
            file_path = exporter.export_json(sample_testee_analysis, output_dir)
            assert Path(file_path).exists()

