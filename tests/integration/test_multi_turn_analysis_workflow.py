"""
Integration tests for multi-turn analysis workflow.

Tests the complete workflow without mocks:
1. Create multi-turn BenchmarkResult
2. Save to storage
3. Analyze with BenchmarkAnalyzer
4. Export to CSV and JSON
5. Verify output
"""

import pytest
import tempfile
import csv
import json
from pathlib import Path
from datetime import datetime

from benchmark.storage import ResultsStorage
from benchmark.analysis.analyzer import BenchmarkAnalyzer
from benchmark.analysis.exporter import AnalysisExporter
from benchmark.models.results import (
    BenchmarkResult,
    ExecutionMetrics,
    ScoringResult,
    ValidityCheck,
    PropertyEvaluationResult,
)
from benchmark.models.analysis import AnalysisResult


class TestMultiTurnAnalysisWorkflow:
    """End-to-end integration tests for multi-turn analysis."""

    @pytest.fixture
    def temp_results_dir(self, tmp_path):
        """Create temporary results directory."""
        results_dir = tmp_path / "results"
        results_dir.mkdir()
        return results_dir

    @pytest.fixture
    def storage(self, temp_results_dir):
        """Create ResultsStorage with temp directory."""
        return ResultsStorage(base_dir=temp_results_dir)

    def _create_result(
        self,
        task_id: str,
        testee_id: str,
        is_multi_turn: bool = True,
        turns: int = 10,
        time: float = 30.0,
        reason: str = "submitted",
        success: bool = True,
        final_score: float = 0.85,
    ) -> BenchmarkResult:
        """Create a BenchmarkResult with specified parameters."""
        return BenchmarkResult(
            run_id=f"run_{task_id}_{testee_id}_{datetime.now().strftime('%H%M%S')}",
            timestamp=datetime.now(),
            task_id=task_id,
            testee_id=testee_id,
            testee_type="dagent",
            evaluation_mode="multi_turn" if is_multi_turn else "single_turn",
            success=success,
            property_results=[
                PropertyEvaluationResult(
                    property_id="reachability_01",
                    satisfied=success,
                    observation_raw="ping output",
                    evaluation_time_seconds=0.5,
                )
            ],
            scoring=ScoringResult(
                completeness=final_score,
                robustness=0.9,
                syntactic_validity=1.0,
                final_score=final_score,
            ),
            validity=ValidityCheck(
                is_valid_solution=success,
                condition_a_syntactic=True,
                condition_b_semantic=success,
            ),
            metrics=ExecutionMetrics(
                infrastructure_provision_time=0.5,
                config_execution_time=2.0,
                convergence_time=1.0,
                evaluation_time=0.5,
                total_time=4.0,
                is_multi_turn=is_multi_turn,
                turns_to_complete=turns if is_multi_turn else None,
                time_to_complete=time if is_multi_turn else None,
                termination_reason=reason if is_multi_turn else None,
                tool_usage={"exec_command": turns, "get_nodes": 1} if is_multi_turn else None,
            ),
        )

    def test_save_and_load_multi_turn_result(self, storage):
        """Test saving and loading a multi-turn result preserves all fields."""
        # Create result
        result = self._create_result(
            task_id="reachability_2n_test",
            testee_id="dagent_test",
            is_multi_turn=True,
            turns=15,
            time=45.0,
            reason="submitted",
        )
        
        # Save
        storage.save_result(result)
        
        # Load
        loaded_results = storage.get_runs_by_testee("dagent_test")
        assert len(loaded_results) == 1
        
        loaded = loaded_results[0]
        
        # Verify multi-turn fields
        assert loaded.evaluation_mode == "multi_turn"
        assert loaded.metrics.is_multi_turn is True
        assert loaded.metrics.turns_to_complete == 15
        assert loaded.metrics.time_to_complete == 45.0
        assert loaded.metrics.termination_reason == "submitted"
        assert loaded.metrics.tool_usage["exec_command"] == 15

    def test_analyze_multi_turn_testee(self, storage):
        """Test analyzing a testee with multi-turn results."""
        testee_id = "dagent_multiturn"
        
        # Create and save multiple results
        results = [
            self._create_result("reachability_2n_01", testee_id, turns=10, time=30.0, success=True),
            self._create_result("reachability_2n_02", testee_id, turns=15, time=45.0, success=True),
            self._create_result("reachability_3n_01", testee_id, turns=20, time=60.0, success=False, reason="timeout"),
        ]
        for r in results:
            storage.save_result(r)
        
        # Analyze
        analyzer = BenchmarkAnalyzer(storage)
        analysis = analyzer.analyze_testee(testee_id)
        
        # Verify multi-turn aggregates
        metrics = analysis.execution_metrics
        assert metrics.avg_turns_to_complete == 15.0  # (10 + 15 + 20) / 3
        assert metrics.avg_time_to_complete == 45.0  # (30 + 45 + 60) / 3
        assert metrics.termination_breakdown["submitted"] == 2
        assert metrics.termination_breakdown["timeout"] == 1
        assert metrics.turn_success_rate == pytest.approx(2/3)  # 2/3 succeeded
        
        # Verify tool usage average
        assert metrics.avg_tool_usage["exec_command"] == 15.0  # (10 + 15 + 20) / 3
        assert metrics.avg_tool_usage["get_nodes"] == 1.0  # All have 1

    def test_analyze_mixed_single_and_multi_turn(self, storage):
        """Test analyzing mixed single-turn and multi-turn results."""
        testee_id = "dagent_mixed"
        
        # Create mixed results
        results = [
            self._create_result("task_01", testee_id, is_multi_turn=False),
            self._create_result("task_02", testee_id, is_multi_turn=True, turns=10, time=30.0),
            self._create_result("task_03", testee_id, is_multi_turn=True, turns=20, time=60.0),
        ]
        for r in results:
            storage.save_result(r)
        
        # Analyze
        analyzer = BenchmarkAnalyzer(storage)
        analysis = analyzer.analyze_testee(testee_id)
        
        # Multi-turn aggregates should only include MT runs
        metrics = analysis.execution_metrics
        assert metrics.avg_turns_to_complete == 15.0  # (10 + 20) / 2 (only MT runs)
        assert metrics.avg_time_to_complete == 45.0  # (30 + 60) / 2

    def test_export_multi_turn_csv(self, storage, temp_results_dir):
        """Test exporting multi-turn analysis to CSV."""
        testee_id = "dagent_export"
        
        # Create and save results
        results = [
            self._create_result("task_01", testee_id, turns=12, time=36.0, success=True),
            self._create_result("task_02", testee_id, turns=18, time=54.0, success=True),
        ]
        for r in results:
            storage.save_result(r)
        
        # Analyze
        analyzer = BenchmarkAnalyzer(storage)
        testee_analysis = analyzer.analyze_testee(testee_id)
        
        # Create AnalysisResult wrapper
        analysis = AnalysisResult(
            analysis_id=f"analysis_{testee_id}",
            analysis_type="testee",
            timestamp=datetime.now(),
            testee_analysis=testee_analysis,
        )
        
        # Export
        exporter = AnalysisExporter()
        output_dir = temp_results_dir / "exports"
        csv_path = exporter.export_csv_summary(analysis, output_dir)
        
        # Verify CSV contents
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        # Find OVERALL row
        overall = next(r for r in rows if r["property_type"] == "OVERALL")
        
        # Verify multi-turn columns
        assert float(overall["avg_turns"]) == 15.0  # (12 + 18) / 2
        assert float(overall["avg_session_time"]) == 45.0  # (36 + 54) / 2
        assert float(overall["turn_success_rate"]) == 1.0  # Both succeeded

    def test_export_multi_turn_json(self, storage, temp_results_dir):
        """Test exporting multi-turn analysis to JSON."""
        testee_id = "dagent_json"
        
        # Create and save result
        result = self._create_result("task_01", testee_id, turns=25, time=75.0)
        storage.save_result(result)
        
        # Analyze
        analyzer = BenchmarkAnalyzer(storage)
        testee_analysis = analyzer.analyze_testee(testee_id)
        
        # Create AnalysisResult wrapper
        analysis = AnalysisResult(
            analysis_id=f"analysis_{testee_id}",
            analysis_type="testee",
            timestamp=datetime.now(),
            testee_analysis=testee_analysis,
        )
        
        # Export
        exporter = AnalysisExporter()
        output_dir = temp_results_dir / "exports"
        json_path = exporter.export_json(analysis, output_dir)
        
        # Verify JSON contents
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        # Navigate to execution_metrics
        exec_metrics = data["testee_analysis"]["execution_metrics"]
        
        # Verify multi-turn fields
        assert exec_metrics["avg_turns_to_complete"] == 25.0
        assert exec_metrics["avg_time_to_complete"] == 75.0
        assert exec_metrics["termination_breakdown"] == {"submitted": 1}
        assert exec_metrics["avg_tool_usage"]["exec_command"] == 25.0
        assert exec_metrics["turn_success_rate"] == 1.0

    def test_single_turn_only_has_none_multi_turn_fields(self, storage):
        """Test that single-turn only analysis has None for multi-turn fields."""
        testee_id = "baseline_single"
        
        # Create single-turn results only
        results = [
            self._create_result("task_01", testee_id, is_multi_turn=False),
            self._create_result("task_02", testee_id, is_multi_turn=False),
        ]
        for r in results:
            storage.save_result(r)
        
        # Analyze
        analyzer = BenchmarkAnalyzer(storage)
        analysis = analyzer.analyze_testee(testee_id)
        
        # Verify multi-turn fields are None
        metrics = analysis.execution_metrics
        assert metrics.avg_turns_to_complete is None
        assert metrics.avg_time_to_complete is None
        assert metrics.termination_breakdown is None
        assert metrics.avg_tool_usage is None
        assert metrics.turn_success_rate is None
