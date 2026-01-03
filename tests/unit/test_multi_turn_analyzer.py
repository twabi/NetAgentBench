"""
Unit tests for multi-turn analyzer functionality.

Tests the analyzer's ability to compute multi-turn aggregates.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock

from benchmark.analysis.analyzer import BenchmarkAnalyzer
from benchmark.models.results import (
    BenchmarkResult,
    ExecutionMetrics,
    ScoringResult,
    ValidityCheck,
    PropertyEvaluationResult,
)
from benchmark.models.analysis import AggregateExecutionMetrics


class TestAnalyzerMultiTurn:
    """Tests for multi-turn aggregate computation in BenchmarkAnalyzer."""

    @pytest.fixture
    def mock_storage(self):
        """Create a mock storage."""
        return Mock()

    @pytest.fixture
    def analyzer(self, mock_storage):
        """Create analyzer with mock storage."""
        return BenchmarkAnalyzer(storage=mock_storage)

    def _create_mock_result(
        self,
        task_id: str = "test_task",
        testee_id: str = "test_testee",
        is_multi_turn: bool = False,
        turns_to_complete: int = None,
        time_to_complete: float = None,
        termination_reason: str = None,
        tool_usage: dict = None,
        success: bool = True,
    ) -> BenchmarkResult:
        """Create a mock BenchmarkResult with specified values."""
        return BenchmarkResult(
            run_id=f"run_{task_id}_{testee_id}",
            timestamp=datetime.now(),
            task_id=task_id,
            testee_id=testee_id,
            testee_type="llm",
            success=success,
            property_results=[
                PropertyEvaluationResult(
                    property_id="prop1",
                    satisfied=True,
                    observation_raw="output",
                    evaluation_time_seconds=0.1,
                )
            ],
            scoring=ScoringResult(
                completeness=0.8,
                robustness=0.9,
                syntactic_validity=1.0,
                final_score=0.85,
            ),
            validity=ValidityCheck(
                is_valid_solution=success,
                condition_a_syntactic=True,
                condition_b_semantic=success,
            ),
            metrics=ExecutionMetrics(
                infrastructure_provision_time=1.0,
                config_execution_time=2.0,
                convergence_time=1.0,
                evaluation_time=0.5,
                total_time=4.5,
                is_multi_turn=is_multi_turn,
                turns_to_complete=turns_to_complete,
                time_to_complete=time_to_complete,
                termination_reason=termination_reason,
                tool_usage=tool_usage,
            ),
        )

    def test_compute_execution_metrics_single_turn_only(self, analyzer):
        """Single-turn only runs should have None for multi-turn fields."""
        runs = [
            self._create_mock_result(is_multi_turn=False),
            self._create_mock_result(is_multi_turn=False),
        ]
        
        metrics = analyzer._compute_execution_metrics(runs)
        
        assert metrics.avg_total_time > 0
        assert metrics.avg_turns_to_complete is None
        assert metrics.avg_time_to_complete is None
        assert metrics.termination_breakdown is None
        assert metrics.avg_tool_usage is None
        assert metrics.turn_success_rate is None

    def test_compute_execution_metrics_multi_turn_only(self, analyzer):
        """Multi-turn runs should populate aggregate fields."""
        runs = [
            self._create_mock_result(
                is_multi_turn=True,
                turns_to_complete=10,
                time_to_complete=30.0,
                termination_reason="submitted",
                tool_usage={"exec_command": 10, "get_nodes": 1},
                success=True,
            ),
            self._create_mock_result(
                is_multi_turn=True,
                turns_to_complete=20,
                time_to_complete=60.0,
                termination_reason="submitted",
                tool_usage={"exec_command": 20, "get_nodes": 2},
                success=True,
            ),
        ]
        
        metrics = analyzer._compute_execution_metrics(runs)
        
        assert metrics.avg_turns_to_complete == 15.0  # (10 + 20) / 2
        assert metrics.avg_time_to_complete == 45.0  # (30 + 60) / 2
        assert metrics.termination_breakdown == {"submitted": 2}
        assert metrics.avg_tool_usage["exec_command"] == 15.0  # (10 + 20) / 2
        assert metrics.avg_tool_usage["get_nodes"] == 1.5  # (1 + 2) / 2
        assert metrics.turn_success_rate == 1.0  # 2/2 succeeded

    def test_compute_execution_metrics_mixed_runs(self, analyzer):
        """Mixed single and multi-turn runs should only compute multi-turn from MT runs."""
        runs = [
            self._create_mock_result(is_multi_turn=False),  # Single-turn
            self._create_mock_result(
                is_multi_turn=True,
                turns_to_complete=15,
                time_to_complete=45.0,
                termination_reason="submitted",
                success=True,
            ),
        ]
        
        metrics = analyzer._compute_execution_metrics(runs)
        
        # Base metrics from all runs
        assert metrics.avg_total_time == 4.5  # Both have same total_time
        
        # Multi-turn metrics from only the MT run
        assert metrics.avg_turns_to_complete == 15.0
        assert metrics.avg_time_to_complete == 45.0
        assert metrics.turn_success_rate == 1.0

    def test_compute_execution_metrics_termination_breakdown(self, analyzer):
        """Termination breakdown should count all reasons."""
        runs = [
            self._create_mock_result(
                is_multi_turn=True, termination_reason="submitted", success=True
            ),
            self._create_mock_result(
                is_multi_turn=True, termination_reason="submitted", success=True
            ),
            self._create_mock_result(
                is_multi_turn=True, termination_reason="timeout", success=False
            ),
            self._create_mock_result(
                is_multi_turn=True, termination_reason="turn_limit", success=False
            ),
        ]
        
        metrics = analyzer._compute_execution_metrics(runs)
        
        assert metrics.termination_breakdown["submitted"] == 2
        assert metrics.termination_breakdown["timeout"] == 1
        assert metrics.termination_breakdown["turn_limit"] == 1
        assert metrics.turn_success_rate == 0.5  # 2/4 succeeded

    def test_compute_execution_metrics_partial_multi_turn_data(self, analyzer):
        """Handles runs with partial multi-turn data gracefully."""
        runs = [
            self._create_mock_result(
                is_multi_turn=True,
                turns_to_complete=10,
                # No time_to_complete
                # No tool_usage
                termination_reason="submitted",
                success=True,
            ),
        ]
        
        metrics = analyzer._compute_execution_metrics(runs)
        
        assert metrics.avg_turns_to_complete == 10.0
        assert metrics.avg_time_to_complete is None  # No data
        assert metrics.avg_tool_usage is None  # No data
        assert metrics.termination_breakdown == {"submitted": 1}
        assert metrics.turn_success_rate == 1.0


class TestExporterMultiTurn:
    """Tests for multi-turn columns in exporter."""

    def test_testee_csv_includes_multi_turn_columns(self, tmp_path):
        """CSV export should include multi-turn columns."""
        from benchmark.analysis.exporter import AnalysisExporter
        from benchmark.models.analysis import (
            AnalysisResult,
            TesteeAnalysis,
            AggregateScores,
            AggregateExecutionMetrics,
        )
        
        exporter = AnalysisExporter()
        
        # Create analysis with multi-turn metrics
        analysis = AnalysisResult(
            analysis_id="test_analysis",
            analysis_type="testee",
            timestamp=datetime.now(),
            testee_analysis=TesteeAnalysis(
                testee_id="test_testee",
                testee_type="llm",
                total_runs=10,
                property_breakdown={},
                aggregate_scores=AggregateScores(
                    completeness=0.8,
                    robustness=0.9,
                    syntactic_validity=1.0,
                    final_score=0.85,
                ),
                execution_metrics=AggregateExecutionMetrics(
                    avg_infrastructure_provision_time=1.0,
                    avg_config_execution_time=2.0,
                    avg_convergence_time=1.0,
                    avg_evaluation_time=0.5,
                    avg_total_time=4.5,
                    avg_turns_to_complete=12.5,
                    avg_time_to_complete=45.0,
                    turn_success_rate=0.9,
                ),
            ),
        )
        
        # Export
        csv_path = exporter.export_csv_summary(analysis, tmp_path)
        
        # Read and verify
        import csv
        with open(csv_path, 'r') as f:
            reader = csv.reader(f)
            header = next(reader)
            
            # Check multi-turn columns in header
            assert "avg_turns" in header
            assert "avg_session_time" in header
            assert "turn_success_rate" in header
            
            # Check OVERALL row has multi-turn values
            rows = list(reader)
            overall_row = rows[-1]  # Last row
            assert overall_row[0] == "OVERALL"
            
            # Find indices
            avg_turns_idx = header.index("avg_turns")
            avg_time_idx = header.index("avg_session_time")
            turn_rate_idx = header.index("turn_success_rate")
            
            assert overall_row[avg_turns_idx] == "12.5"
            assert overall_row[avg_time_idx] == "45.0"
            assert overall_row[turn_rate_idx] == "0.9"

    def test_testee_csv_empty_multi_turn_when_single_turn(self, tmp_path):
        """CSV export should have empty multi-turn columns for single-turn runs."""
        from benchmark.analysis.exporter import AnalysisExporter
        from benchmark.models.analysis import (
            AnalysisResult,
            TesteeAnalysis,
            AggregateScores,
            AggregateExecutionMetrics,
        )
        
        exporter = AnalysisExporter()
        
        # Create analysis without multi-turn metrics
        analysis = AnalysisResult(
            analysis_id="test_analysis_st",
            analysis_type="testee",
            timestamp=datetime.now(),
            testee_analysis=TesteeAnalysis(
                testee_id="test_testee",
                testee_type="llm",
                total_runs=5,
                property_breakdown={},
                aggregate_scores=AggregateScores(
                    completeness=0.7,
                    robustness=0.8,
                    syntactic_validity=1.0,
                    final_score=0.75,
                ),
                execution_metrics=AggregateExecutionMetrics(
                    avg_infrastructure_provision_time=1.0,
                    avg_config_execution_time=2.0,
                    avg_convergence_time=1.0,
                    avg_evaluation_time=0.5,
                    avg_total_time=4.5,
                    # No multi-turn fields
                ),
            ),
        )
        
        # Export
        csv_path = exporter.export_csv_summary(analysis, tmp_path)
        
        # Read and verify
        import csv
        with open(csv_path, 'r') as f:
            reader = csv.reader(f)
            header = next(reader)
            rows = list(reader)
            overall_row = rows[-1]
            
            avg_turns_idx = header.index("avg_turns")
            
            # Multi-turn columns should be empty
            assert overall_row[avg_turns_idx] == ""
