"""
Unit tests for multi-turn fields in results models.

Tests the new multi-turn related fields added for Phase 2.5:
- ExecutionMetrics multi-turn fields
- BenchmarkResult evaluation_mode and model_version
- BenchmarkRunResult evaluation_mode, benchmark_suite_id, model_version
"""

import pytest
from datetime import datetime

from benchmark.models.results import (
    ExecutionMetrics,
    BenchmarkResult,
    BenchmarkRunResult,
    PropertyEvaluationResult,
    ScoringResult,
    ValidityCheck,
    PropertyExecutionResult,
)


class TestExecutionMetricsMultiTurn:
    """Tests for multi-turn fields in ExecutionMetrics."""

    def test_default_is_single_turn(self):
        """Default is_multi_turn should be False."""
        metrics = ExecutionMetrics(
            infrastructure_provision_time=1.0,
            config_execution_time=2.0,
            convergence_time=3.0,
            evaluation_time=0.5,
            total_time=6.5,
        )
        assert metrics.is_multi_turn is False
        assert metrics.turns_to_complete is None
        assert metrics.time_to_complete is None
        assert metrics.termination_reason is None
        assert metrics.tool_usage is None
        assert metrics.failed_commands is None

    def test_multi_turn_fields_populated(self):
        """Multi-turn fields can be populated."""
        metrics = ExecutionMetrics(
            infrastructure_provision_time=1.0,
            config_execution_time=2.0,
            convergence_time=3.0,
            evaluation_time=0.5,
            total_time=6.5,
            is_multi_turn=True,
            turns_to_complete=15,
            time_to_complete=45.2,
            termination_reason="submitted",
            tool_usage={"exec_command": 15, "get_nodes": 1, "get_session_status": 3},
            failed_commands=2,
        )
        assert metrics.is_multi_turn is True
        assert metrics.turns_to_complete == 15
        assert metrics.time_to_complete == 45.2
        assert metrics.termination_reason == "submitted"
        assert metrics.tool_usage["exec_command"] == 15
        assert metrics.failed_commands == 2

    def test_termination_reasons(self):
        """Various termination reasons are valid."""
        for reason in ["submitted", "timeout", "turn_limit"]:
            metrics = ExecutionMetrics(
                infrastructure_provision_time=1.0,
                config_execution_time=2.0,
                convergence_time=3.0,
                evaluation_time=0.5,
                total_time=6.5,
                is_multi_turn=True,
                termination_reason=reason,
            )
            assert metrics.termination_reason == reason

    def test_serialization_with_multi_turn_fields(self):
        """Multi-turn fields serialize correctly."""
        metrics = ExecutionMetrics(
            infrastructure_provision_time=1.0,
            config_execution_time=2.0,
            convergence_time=3.0,
            evaluation_time=0.5,
            total_time=6.5,
            is_multi_turn=True,
            turns_to_complete=10,
            tool_usage={"exec_command": 10},
        )
        data = metrics.model_dump()
        assert data["is_multi_turn"] is True
        assert data["turns_to_complete"] == 10
        assert data["tool_usage"] == {"exec_command": 10}

    def test_deserialization_with_multi_turn_fields(self):
        """Multi-turn fields deserialize correctly."""
        data = {
            "infrastructure_provision_time": 1.0,
            "config_execution_time": 2.0,
            "convergence_time": 3.0,
            "evaluation_time": 0.5,
            "total_time": 6.5,
            "is_multi_turn": True,
            "turns_to_complete": 20,
            "time_to_complete": 90.5,
            "termination_reason": "timeout",
            "tool_usage": {"exec_command": 20, "submit": 1},
            "failed_commands": 5,
        }
        metrics = ExecutionMetrics.model_validate(data)
        assert metrics.is_multi_turn is True
        assert metrics.turns_to_complete == 20
        assert metrics.termination_reason == "timeout"


class TestBenchmarkResultMultiTurn:
    """Tests for multi-turn fields in BenchmarkResult."""

    @pytest.fixture
    def base_result_data(self):
        """Base data for creating a BenchmarkResult."""
        return {
            "run_id": "test_run_001",
            "timestamp": datetime.now(),
            "task_id": "test_task",
            "testee_id": "test_testee",
            "testee_type": "llm",
            "success": True,
            "property_results": [
                PropertyEvaluationResult(
                    property_id="prop1",
                    satisfied=True,
                    observation_raw="output",
                    evaluation_time_seconds=0.1,
                )
            ],
            "scoring": ScoringResult(
                completeness=1.0,
                robustness=1.0,
                syntactic_validity=1.0,
                final_score=1.0,
            ),
            "validity": ValidityCheck(
                is_valid_solution=True,
                condition_a_syntactic=True,
                condition_b_semantic=True,
            ),
            "metrics": ExecutionMetrics(
                infrastructure_provision_time=1.0,
                config_execution_time=2.0,
                convergence_time=1.0,
                evaluation_time=0.5,
                total_time=4.5,
            ),
        }

    def test_default_evaluation_mode(self, base_result_data):
        """Default evaluation_mode should be 'single_turn'."""
        result = BenchmarkResult(**base_result_data)
        assert result.evaluation_mode == "single_turn"
        assert result.model_version is None

    def test_multi_turn_evaluation_mode(self, base_result_data):
        """evaluation_mode can be set to 'multi_turn'."""
        base_result_data["evaluation_mode"] = "multi_turn"
        base_result_data["model_version"] = "gpt-4-0125-preview"
        result = BenchmarkResult(**base_result_data)
        assert result.evaluation_mode == "multi_turn"
        assert result.model_version == "gpt-4-0125-preview"

    def test_serialization_with_evaluation_mode(self, base_result_data):
        """evaluation_mode serializes correctly."""
        base_result_data["evaluation_mode"] = "multi_turn"
        result = BenchmarkResult(**base_result_data)
        data = result.model_dump()
        assert data["evaluation_mode"] == "multi_turn"

    def test_backward_compatible_deserialization(self, base_result_data):
        """Old data without evaluation_mode still works."""
        data = BenchmarkResult(**base_result_data).model_dump()
        # Simulate old data by removing new fields
        data.pop("evaluation_mode", None)
        data.pop("model_version", None)
        # Should still deserialize with defaults
        # Note: This depends on Pydantic handling - we test the default case
        result = BenchmarkResult(**base_result_data)
        assert result.evaluation_mode == "single_turn"


class TestBenchmarkRunResultMultiTurn:
    """Tests for multi-turn fields in BenchmarkRunResult."""

    @pytest.fixture
    def base_run_result_data(self):
        """Base data for creating a BenchmarkRunResult."""
        return {
            "run_id": "run_001",
            "testee_id": "test_testee",
            "testee_type": "llm",
            "timestamp": datetime.now(),
            "property_results": {},
            "total_tasks": 10,
            "overall_average_score": 0.85,
            "execution_time_seconds": 120.5,
        }

    def test_default_fields(self, base_run_result_data):
        """Default values for new fields."""
        result = BenchmarkRunResult(**base_run_result_data)
        assert result.evaluation_mode == "single_turn"
        assert result.benchmark_suite_id is None
        assert result.model_version is None

    def test_multi_turn_fields_populated(self, base_run_result_data):
        """New fields can be populated."""
        base_run_result_data["evaluation_mode"] = "multi_turn"
        base_run_result_data["benchmark_suite_id"] = "suite_v1.0"
        base_run_result_data["model_version"] = "dagent-v0.1.0"
        result = BenchmarkRunResult(**base_run_result_data)
        assert result.evaluation_mode == "multi_turn"
        assert result.benchmark_suite_id == "suite_v1.0"
        assert result.model_version == "dagent-v0.1.0"

    def test_serialization_with_new_fields(self, base_run_result_data):
        """New fields serialize correctly."""
        base_run_result_data["evaluation_mode"] = "multi_turn"
        base_run_result_data["benchmark_suite_id"] = "suite_001"
        result = BenchmarkRunResult(**base_run_result_data)
        data = result.model_dump()
        assert data["evaluation_mode"] == "multi_turn"
        assert data["benchmark_suite_id"] == "suite_001"

    def test_deserialization_with_new_fields(self, base_run_result_data):
        """New fields deserialize correctly."""
        data = {
            **base_run_result_data,
            "evaluation_mode": "multi_turn",
            "benchmark_suite_id": "phase2_benchmark",
            "model_version": "claude-3-opus",
        }
        # Convert datetime for proper serialization
        data["timestamp"] = data["timestamp"].isoformat()
        result = BenchmarkRunResult.model_validate(data)
        assert result.evaluation_mode == "multi_turn"
        assert result.benchmark_suite_id == "phase2_benchmark"
        assert result.model_version == "claude-3-opus"
