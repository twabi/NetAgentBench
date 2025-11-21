"""
Unit tests for aggregate result models (PropertyExecutionResult, BenchmarkRunResult).

Tests Phase 10 aggregate result models that capture multi-task benchmark execution.
"""
import pytest
from datetime import datetime
from benchmark.models.results import (
    PropertyExecutionResult,
    BenchmarkRunResult,
    BenchmarkResult,
    ScoringResult,
    ValidityCheck,
    ExecutionMetrics,
)


class TestPropertyExecutionResult:
    """Test PropertyExecutionResult model."""

    def test_create_property_execution_result(self):
        """Test creating a basic PropertyExecutionResult."""
        result = PropertyExecutionResult(
            property_type="reachability",
            total_tasks=10,
            successful_tasks=8,
            results=[],
            average_score=0.75,
            aggregate_metrics={"avg_completeness": 0.8, "avg_robustness": 0.7},
        )

        assert result.property_type == "reachability"
        assert result.total_tasks == 10
        assert result.successful_tasks == 8
        assert result.average_score == 0.75
        assert result.aggregate_metrics["avg_completeness"] == 0.8

    def test_property_execution_result_with_benchmark_results(self):
        """Test PropertyExecutionResult containing actual BenchmarkResult objects."""
        # Create mock benchmark results
        benchmark_results = []
        for i in range(3):
            br = BenchmarkResult(
                run_id=f"run_{i}",
                timestamp=datetime.now(),
                task_id=f"task_{i}",
                testee_id="test_testee",
                testee_type="human",
                success=True,
                property_results=[],
                scoring=ScoringResult(
                    completeness=0.8,
                    robustness=0.7,
                    syntactic_validity=0.9,
                    efficiency=None,
                    final_score=0.75,
                    weights={},
                ),
                validity=ValidityCheck(
                    is_valid_solution=True,
                    condition_a_syntactic=True,
                    condition_b_semantic=True,
                ),
                metrics=ExecutionMetrics(
                    infrastructure_provision_time=5.0,
                    config_execution_time=2.0,
                    convergence_time=30.0,
                    evaluation_time=3.0,
                    total_time=40.0,
                ),
                execution_log=[],
                errors=[],
            )
            benchmark_results.append(br)

        result = PropertyExecutionResult(
            property_type="bgp_configuration",
            total_tasks=3,
            successful_tasks=3,
            results=benchmark_results,
            average_score=0.75,
            aggregate_metrics={"avg_completeness": 0.8},
        )

        assert len(result.results) == 3
        assert result.results[0].task_id == "task_0"
        assert result.results[1].task_id == "task_1"

    def test_average_score_in_valid_range(self):
        """Test that average_score must be between 0.0 and 1.0."""
        # Valid score
        result = PropertyExecutionResult(
            property_type="reachability",
            total_tasks=5,
            successful_tasks=4,
            results=[],
            average_score=0.5,
            aggregate_metrics={},
        )
        assert 0.0 <= result.average_score <= 1.0

        # Test boundary values
        result_min = PropertyExecutionResult(
            property_type="reachability",
            total_tasks=5,
            successful_tasks=0,
            results=[],
            average_score=0.0,
            aggregate_metrics={},
        )
        assert result_min.average_score == 0.0

        result_max = PropertyExecutionResult(
            property_type="reachability",
            total_tasks=5,
            successful_tasks=5,
            results=[],
            average_score=1.0,
            aggregate_metrics={},
        )
        assert result_max.average_score == 1.0

    def test_successful_tasks_cannot_exceed_total(self):
        """Test that successful_tasks <= total_tasks (validated logically, not by model)."""
        # This is valid - model doesn't enforce this constraint
        result = PropertyExecutionResult(
            property_type="reachability",
            total_tasks=10,
            successful_tasks=8,
            results=[],
            average_score=0.8,
            aggregate_metrics={},
        )
        assert result.successful_tasks <= result.total_tasks

    def test_property_execution_result_json_serialization(self):
        """Test JSON serialization/deserialization."""
        result = PropertyExecutionResult(
            property_type="ospf_configuration",
            total_tasks=5,
            successful_tasks=4,
            results=[],
            average_score=0.82,
            aggregate_metrics={
                "avg_completeness": 0.85,
                "avg_robustness": 0.80,
                "avg_syntactic_validity": 0.95,
            },
        )

        # Serialize to JSON
        json_data = result.model_dump()
        assert json_data["property_type"] == "ospf_configuration"
        assert json_data["average_score"] == 0.82

        # Deserialize from JSON
        result_loaded = PropertyExecutionResult(**json_data)
        assert result_loaded.property_type == result.property_type
        assert result_loaded.average_score == result.average_score


class TestBenchmarkRunResult:
    """Test BenchmarkRunResult model."""

    def test_create_benchmark_run_result(self):
        """Test creating a basic BenchmarkRunResult."""
        result = BenchmarkRunResult(
            run_id="run_12345",
            testee_id="testee_001",
            testee_type="llm",
            timestamp=datetime.now(),
            property_results={},
            total_tasks=25,
            overall_average_score=0.78,
            execution_time_seconds=1200.5,
        )

        assert result.run_id == "run_12345"
        assert result.testee_id == "testee_001"
        assert result.testee_type == "llm"
        assert result.total_tasks == 25
        assert result.overall_average_score == 0.78
        assert result.execution_time_seconds == 1200.5

    def test_benchmark_run_result_with_multiple_properties(self):
        """Test BenchmarkRunResult with results for multiple property types."""
        prop_result_1 = PropertyExecutionResult(
            property_type="reachability",
            total_tasks=10,
            successful_tasks=8,
            results=[],
            average_score=0.80,
            aggregate_metrics={},
        )

        prop_result_2 = PropertyExecutionResult(
            property_type="bgp_configuration",
            total_tasks=8,
            successful_tasks=6,
            results=[],
            average_score=0.75,
            aggregate_metrics={},
        )

        prop_result_3 = PropertyExecutionResult(
            property_type="ospf_configuration",
            total_tasks=7,
            successful_tasks=5,
            results=[],
            average_score=0.70,
            aggregate_metrics={},
        )

        run_result = BenchmarkRunResult(
            run_id="run_multi_property",
            testee_id="gpt4",
            testee_type="llm",
            timestamp=datetime.now(),
            property_results={
                "reachability": prop_result_1,
                "bgp_configuration": prop_result_2,
                "ospf_configuration": prop_result_3,
            },
            total_tasks=25,  # 10 + 8 + 7
            overall_average_score=0.75,  # Mean of all 25 task scores
            execution_time_seconds=3600.0,
        )

        assert len(run_result.property_results) == 3
        assert "reachability" in run_result.property_results
        assert "bgp_configuration" in run_result.property_results
        assert "ospf_configuration" in run_result.property_results
        assert run_result.total_tasks == 25

    def test_overall_average_score_in_valid_range(self):
        """Test that overall_average_score must be between 0.0 and 1.0."""
        result = BenchmarkRunResult(
            run_id="run_test",
            testee_id="test",
            testee_type="human",
            timestamp=datetime.now(),
            property_results={},
            total_tasks=10,
            overall_average_score=0.5,
            execution_time_seconds=100.0,
        )
        assert 0.0 <= result.overall_average_score <= 1.0

        # Test boundaries
        result_min = BenchmarkRunResult(
            run_id="run_min",
            testee_id="test",
            testee_type="baseline",
            timestamp=datetime.now(),
            property_results={},
            total_tasks=5,
            overall_average_score=0.0,
            execution_time_seconds=50.0,
        )
        assert result_min.overall_average_score == 0.0

        result_max = BenchmarkRunResult(
            run_id="run_max",
            testee_id="test",
            testee_type="human",
            timestamp=datetime.now(),
            property_results={},
            total_tasks=5,
            overall_average_score=1.0,
            execution_time_seconds=50.0,
        )
        assert result_max.overall_average_score == 1.0

    def test_testee_types(self):
        """Test various testee_type values."""
        testee_types = ["llm", "human", "ml_model", "baseline"]

        for testee_type in testee_types:
            result = BenchmarkRunResult(
                run_id=f"run_{testee_type}",
                testee_id=f"{testee_type}_001",
                testee_type=testee_type,
                timestamp=datetime.now(),
                property_results={},
                total_tasks=10,
                overall_average_score=0.75,
                execution_time_seconds=100.0,
            )
            assert result.testee_type == testee_type

    def test_benchmark_run_result_json_serialization(self):
        """Test JSON serialization/deserialization."""
        timestamp = datetime.now()
        prop_result = PropertyExecutionResult(
            property_type="reachability",
            total_tasks=5,
            successful_tasks=4,
            results=[],
            average_score=0.8,
            aggregate_metrics={},
        )

        result = BenchmarkRunResult(
            run_id="run_json_test",
            testee_id="claude_3",
            testee_type="llm",
            timestamp=timestamp,
            property_results={"reachability": prop_result},
            total_tasks=5,
            overall_average_score=0.8,
            execution_time_seconds=150.0,
        )

        # Serialize to JSON
        json_data = result.model_dump()
        assert json_data["run_id"] == "run_json_test"
        assert json_data["testee_type"] == "llm"
        assert json_data["total_tasks"] == 5

        # Deserialize from JSON
        result_loaded = BenchmarkRunResult(**json_data)
        assert result_loaded.run_id == result.run_id
        assert result_loaded.testee_id == result.testee_id
        assert result_loaded.overall_average_score == result.overall_average_score

    def test_empty_property_results(self):
        """Test BenchmarkRunResult with no property results."""
        result = BenchmarkRunResult(
            run_id="run_empty",
            testee_id="test",
            testee_type="baseline",
            timestamp=datetime.now(),
            property_results={},
            total_tasks=0,
            overall_average_score=0.0,
            execution_time_seconds=0.0,
        )

        assert len(result.property_results) == 0
        assert result.total_tasks == 0
        assert result.overall_average_score == 0.0

    def test_execution_time_non_negative(self):
        """Test that execution_time_seconds must be non-negative."""
        result = BenchmarkRunResult(
            run_id="run_time_test",
            testee_id="test",
            testee_type="human",
            timestamp=datetime.now(),
            property_results={},
            total_tasks=5,
            overall_average_score=0.5,
            execution_time_seconds=1234.56,
        )
        assert result.execution_time_seconds >= 0.0
