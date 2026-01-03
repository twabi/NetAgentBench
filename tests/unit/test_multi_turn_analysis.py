"""
Unit tests for multi-turn aggregate fields in analysis models.

Tests the new multi-turn aggregate fields added for Phase 2.5:
- AggregateExecutionMetrics multi-turn aggregates
"""

import pytest

from benchmark.models.analysis import (
    AggregateExecutionMetrics,
    AggregateScores,
)


class TestAggregateExecutionMetricsMultiTurn:
    """Tests for multi-turn fields in AggregateExecutionMetrics."""

    @pytest.fixture
    def base_metrics_data(self):
        """Base data for creating AggregateExecutionMetrics."""
        return {
            "avg_infrastructure_provision_time": 1.5,
            "avg_config_execution_time": 2.0,
            "avg_convergence_time": 3.0,
            "avg_evaluation_time": 0.5,
            "avg_total_time": 7.0,
        }

    def test_default_multi_turn_fields_are_none(self, base_metrics_data):
        """Default multi-turn fields should be None."""
        metrics = AggregateExecutionMetrics(**base_metrics_data)
        assert metrics.avg_turns_to_complete is None
        assert metrics.avg_time_to_complete is None
        assert metrics.termination_breakdown is None
        assert metrics.avg_tool_usage is None
        assert metrics.turn_success_rate is None

    def test_multi_turn_fields_populated(self, base_metrics_data):
        """Multi-turn fields can be populated."""
        base_metrics_data.update({
            "avg_turns_to_complete": 12.5,
            "avg_time_to_complete": 45.3,
            "termination_breakdown": {"submitted": 8, "timeout": 1, "turn_limit": 1},
            "avg_tool_usage": {"exec_command": 12.5, "get_nodes": 1.0, "get_session_status": 2.3},
            "turn_success_rate": 0.85,
        })
        metrics = AggregateExecutionMetrics(**base_metrics_data)
        assert metrics.avg_turns_to_complete == 12.5
        assert metrics.avg_time_to_complete == 45.3
        assert metrics.termination_breakdown["submitted"] == 8
        assert metrics.avg_tool_usage["exec_command"] == 12.5
        assert metrics.turn_success_rate == 0.85

    def test_termination_breakdown_values(self, base_metrics_data):
        """Termination breakdown can have various key-value pairs."""
        base_metrics_data["termination_breakdown"] = {
            "submitted": 10,
            "timeout": 3,
            "turn_limit": 2,
        }
        metrics = AggregateExecutionMetrics(**base_metrics_data)
        assert sum(metrics.termination_breakdown.values()) == 15
        assert metrics.termination_breakdown["submitted"] == 10
        assert metrics.termination_breakdown["timeout"] == 3
        assert metrics.termination_breakdown["turn_limit"] == 2

    def test_avg_tool_usage_float_values(self, base_metrics_data):
        """avg_tool_usage should support float values (averages)."""
        base_metrics_data["avg_tool_usage"] = {
            "exec_command": 15.7,
            "get_nodes": 1.0,
            "get_session_status": 3.5,
            "submit": 1.0,
        }
        metrics = AggregateExecutionMetrics(**base_metrics_data)
        assert metrics.avg_tool_usage["exec_command"] == 15.7
        assert metrics.avg_tool_usage["submit"] == 1.0

    def test_turn_success_rate_bounds(self, base_metrics_data):
        """turn_success_rate must be between 0 and 1."""
        # Valid values
        for rate in [0.0, 0.5, 1.0]:
            base_metrics_data["turn_success_rate"] = rate
            metrics = AggregateExecutionMetrics(**base_metrics_data)
            assert metrics.turn_success_rate == rate
        
        # Invalid values should raise validation error
        with pytest.raises(Exception):  # Pydantic ValidationError
            base_metrics_data["turn_success_rate"] = 1.5
            AggregateExecutionMetrics(**base_metrics_data)

    def test_serialization_with_multi_turn_fields(self, base_metrics_data):
        """Multi-turn fields serialize correctly."""
        base_metrics_data.update({
            "avg_turns_to_complete": 10.0,
            "termination_breakdown": {"submitted": 5},
            "turn_success_rate": 0.9,
        })
        metrics = AggregateExecutionMetrics(**base_metrics_data)
        data = metrics.model_dump()
        assert data["avg_turns_to_complete"] == 10.0
        assert data["termination_breakdown"] == {"submitted": 5}
        assert data["turn_success_rate"] == 0.9

    def test_deserialization_with_multi_turn_fields(self, base_metrics_data):
        """Multi-turn fields deserialize correctly."""
        base_metrics_data.update({
            "avg_turns_to_complete": 8.5,
            "avg_time_to_complete": 60.0,
            "termination_breakdown": {"submitted": 10, "timeout": 2},
            "avg_tool_usage": {"exec_command": 8.5},
            "turn_success_rate": 0.75,
        })
        metrics = AggregateExecutionMetrics.model_validate(base_metrics_data)
        assert metrics.avg_turns_to_complete == 8.5
        assert metrics.termination_breakdown["timeout"] == 2
        assert metrics.turn_success_rate == 0.75

    def test_backward_compatible_without_multi_turn(self, base_metrics_data):
        """Old data without multi-turn fields still works."""
        # Create instance without multi-turn fields
        metrics = AggregateExecutionMetrics(**base_metrics_data)
        # All base fields should be present
        assert metrics.avg_infrastructure_provision_time == 1.5
        assert metrics.avg_total_time == 7.0
        # Multi-turn fields default to None
        assert metrics.avg_turns_to_complete is None
        assert metrics.termination_breakdown is None

    def test_partial_multi_turn_fields(self, base_metrics_data):
        """Some multi-turn fields can be set while others remain None."""
        base_metrics_data["avg_turns_to_complete"] = 5.0
        base_metrics_data["turn_success_rate"] = 0.8
        # Not setting termination_breakdown or avg_tool_usage
        metrics = AggregateExecutionMetrics(**base_metrics_data)
        assert metrics.avg_turns_to_complete == 5.0
        assert metrics.turn_success_rate == 0.8
        assert metrics.termination_breakdown is None
        assert metrics.avg_tool_usage is None
        assert metrics.avg_time_to_complete is None
