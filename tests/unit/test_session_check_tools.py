"""Unit tests for session check_properties and check_syntactic_validity."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from benchmark.guide.arms import CHECK_PROPERTIES_CAP
from benchmark.models.results import PropertyEvaluationResult
from benchmark.models.task import TaskDefinition
from benchmark.session.session import InteractiveSession


@pytest.fixture
def session_with_context():
    task_path = (
        Path(__file__).parent.parent.parent
        / "tasks"
        / "archive"
        / "multi_turn"
        / "guide_ospf_multiarea.json"
    )
    with task_path.open() as f:
        task = TaskDefinition.model_validate(json.load(f))
    infra = MagicMock()
    session = InteractiveSession(task, infrastructure=infra, turn_limit=5, time_limit=60.0)
    session._context = MagicMock()
    session._context.property_check_count = 0
    session._context.property_trajectory = []
    session._context.log_property_snapshots = False
    session._context.execution_results = [("R1", "cmd", True), ("R1", "bad", False)]
    session._topology_id = "topo-1"
    session._turns_used = 2
    return session


class TestCheckPropertiesLive:
    def test_returns_property_vector(self, session_with_context):
        eval_results = [
            PropertyEvaluationResult(
                property_id="area0_adjacency",
                satisfied=True,
                observation_raw="Full/",
                evaluation_time_seconds=0.1,
            ),
        ]
        session_with_context._evaluator = MagicMock()
        session_with_context._evaluator.evaluate_all_properties.return_value = eval_results

        resp = session_with_context.check_properties_live(CHECK_PROPERTIES_CAP)
        assert resp["success"] is True
        assert resp["properties"]["area0_adjacency"] is True
        assert resp["check_index"] == 1

    def test_cap_exceeded(self, session_with_context):
        session_with_context._context.property_check_count = CHECK_PROPERTIES_CAP
        session_with_context._evaluator = MagicMock()

        resp = session_with_context.check_properties_live(CHECK_PROPERTIES_CAP)
        assert resp["success"] is False
        assert resp["error"] == "check_cap_exceeded"
        session_with_context._evaluator.evaluate_all_properties.assert_not_called()

    def test_parity_with_terminal_eval_helpers(self, session_with_context):
        """check_properties uses same evaluator as terminal scoring."""
        eval_results = [
            PropertyEvaluationResult(
                property_id="area0_adjacency",
                satisfied=False,
                observation_raw="",
                evaluation_time_seconds=0.1,
            ),
        ]
        session_with_context._evaluator = MagicMock()
        session_with_context._evaluator.evaluate_all_properties.return_value = eval_results

        resp = session_with_context.check_properties_live(CHECK_PROPERTIES_CAP)
        session_with_context._evaluator.evaluate_all_properties.assert_called_once_with(
            infrastructure=session_with_context.infrastructure,
            topology_id="topo-1",
            properties=session_with_context.task.intent.properties,
        )
        assert resp["properties"]["area0_adjacency"] is False
        assert resp["completeness"] == 0.0


class TestCheckSyntacticValidityLive:
    def test_returns_success_rate_not_properties(self, session_with_context):
        resp = session_with_context.check_syntactic_validity_live(CHECK_PROPERTIES_CAP)
        assert resp["success"] is True
        assert resp["signal_type"] == "syntactic_validity"
        assert "properties" not in resp
        assert resp["commands_checked"] == 2
        assert resp["success_rate"] == 0.5

    def test_shares_cap_with_property_checks(self, session_with_context):
        session_with_context._context.property_check_count = CHECK_PROPERTIES_CAP
        resp = session_with_context.check_syntactic_validity_live(CHECK_PROPERTIES_CAP)
        assert resp["error"] == "check_cap_exceeded"

    def test_logs_trajectory_when_enabled(self, session_with_context):
        session_with_context._context.log_property_snapshots = True
        session_with_context.check_syntactic_validity_live(CHECK_PROPERTIES_CAP)
        assert len(session_with_context._context.property_trajectory) == 1
        assert session_with_context._context.property_trajectory[0]["kind"] == "syntactic_validity"
