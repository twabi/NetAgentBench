"""Unit tests for property-guidance arms, prompts, and MCP tool gating."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from benchmark.guide import (
    FeedbackArm,
    build_system_prompt,
    format_declared_properties_block,
    sanitize_task_context_for_arm,
)
from benchmark.guide.check_helpers import (
    build_property_check_response,
    build_syntactic_validity_response,
)
from benchmark.models.results import PropertyEvaluationResult


PROPS = [
    {
        "id": "adjacency_r1",
        "description": "R1 has a full OSPF neighbor",
        "type": "ospf_configuration",
        "evaluation": {"command": "secret-eval-cmd"},
    },
    {
        "id": "reach_r1_r3",
        "description": "R1 can ping R3",
        "type": "reachability",
        "evaluation": {"command": "ping 10.0.0.3"},
    },
]


class TestSanitization:
    def test_blind_strips_intent(self):
        task = {
            "task_id": "t",
            "intent": {"properties": PROPS},
            "fault_verification": {"x": 1},
        }
        ctx = sanitize_task_context_for_arm(task, FeedbackArm.BLIND)
        assert "intent" not in ctx
        assert "fault_verification" not in ctx

    def test_declared_keeps_ids_drops_eval(self):
        task = {"task_id": "t", "intent": {"properties": PROPS}}
        ctx = sanitize_task_context_for_arm(task, FeedbackArm.DECLARED)
        props = ctx["intent"]["properties"]
        assert props[0]["id"] == "adjacency_r1"
        assert "evaluation" not in props[0]
        assert "secret-eval-cmd" not in str(ctx)


class TestSystemPrompt:
    def test_blind_has_no_property_block_or_check_tool(self):
        prompt = build_system_prompt(FeedbackArm.BLIND, "TOOLS", PROPS)
        assert "adjacency_r1" not in prompt
        assert "check_properties" not in prompt
        assert "check_syntactic_validity" not in prompt

    def test_declared_has_property_block_no_check_tool(self):
        prompt = build_system_prompt(FeedbackArm.DECLARED, "TOOLS", PROPS)
        assert "adjacency_r1" in prompt
        assert "check_properties" not in prompt

    def test_feedback_exposes_check_properties(self):
        prompt = build_system_prompt(FeedbackArm.FEEDBACK, "TOOLS", PROPS)
        assert "adjacency_r1" in prompt
        assert "check_properties" in prompt

    def test_placebo_exposes_syntactic_check_only(self):
        prompt = build_system_prompt(FeedbackArm.PLACEBO, "TOOLS", PROPS)
        assert "check_syntactic_validity" in prompt
        assert "check_properties:" not in prompt


class TestCheckHelpers:
    def _results(self, sat):
        return [
            PropertyEvaluationResult(
                property_id=f"p{i}",
                satisfied=s,
                observation_raw="",
                evaluation_time_seconds=0.0,
            )
            for i, s in enumerate(sat)
        ]

    def test_property_check_vector_and_completeness(self):
        resp = build_property_check_response(self._results([True, False, True]), 1, 20)
        assert resp["success"] is True
        assert resp["properties"] == {"p0": True, "p1": False, "p2": True}
        assert resp["completeness"] == pytest.approx(2 / 3)

    def test_syntactic_validity_is_non_property_signal(self):
        execs = [("R1", "a", True), ("R1", "b", False)]
        resp = build_syntactic_validity_response(execs, 1, 20)
        assert resp["signal_type"] == "syntactic_validity"
        assert "properties" not in resp
        assert resp["success_rate"] == pytest.approx(0.5)


def _mock_session():
    from benchmark.session.models import SessionContext

    session = Mock()
    session._context = SessionContext(
        session_id="s",
        task_id="t",
        nodes=["R1"],
        topology_id="topo",
        turn_limit=10,
        time_limit=60.0,
        start_time=datetime.now(),
        executed_commands=[],
    )
    return session


class TestMCPToolGating:
    def test_feedback_registers_check_properties(self):
        from benchmark.session.mcp_server import BenchmarkMCPServer

        server = BenchmarkMCPServer(session=_mock_session(), feedback_arm="feedback")
        assert "check_properties" in server.get_tool_list()

    def test_placebo_registers_syntactic_check(self):
        from benchmark.session.mcp_server import BenchmarkMCPServer

        server = BenchmarkMCPServer(session=_mock_session(), feedback_arm="placebo")
        assert "check_syntactic_validity" in server.get_tool_list()

    def test_legacy_none_arm_base_tools(self):
        from benchmark.session.mcp_server import BenchmarkMCPServer

        server = BenchmarkMCPServer(session=_mock_session())
        assert server.get_tool_list() == [
            "exec_command",
            "submit",
            "get_session_status",
            "get_nodes",
        ]
