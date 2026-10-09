"""
Unit tests for InteractiveBenchmarkController.

Tests the interactive controller initialization, run_id generation,
and run_interactive workflow.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch
import re


class TestRunIdGeneration:
    """Test run_id generation."""

    def test_generate_run_id_basic(self):
        """Test basic run_id generation."""
        from benchmark.interactive_controller import InteractiveBenchmarkController

        controller = InteractiveBenchmarkController()
        run_id = controller.generate_run_id(testee_id="dagent")

        # Check format: testee_mode_timestamp_uuid
        assert run_id.startswith("dagent_mt_")
        assert len(run_id) > 20  # Should include timestamp and uuid

    def test_generate_run_id_with_model_name(self):
        """run_id embeds testee_id; model is folded into CLI-built testee_id, not duplicated here."""
        from benchmark.interactive_controller import InteractiveBenchmarkController

        controller = InteractiveBenchmarkController()
        run_id = controller.generate_run_id(
            testee_id="dagent",
            model_name="gpt-4o",
        )

        assert run_id.startswith("dagent_mt_")

    def test_generate_run_id_with_model_name_special_chars(self):
        from benchmark.interactive_controller import InteractiveBenchmarkController

        controller = InteractiveBenchmarkController()
        run_id = controller.generate_run_id(
            testee_id="openai_gpt4omini20250807",
            model_name="gpt-4o-mini",
        )

        assert run_id.startswith("openai_gpt4omini20250807_mt_")

    def test_generate_run_id_single_mode(self):
        """Test run_id with single-turn mode."""
        from benchmark.interactive_controller import InteractiveBenchmarkController

        controller = InteractiveBenchmarkController()
        run_id = controller.generate_run_id(
            testee_id="baseline",
            mode="single",
        )

        assert "_st_" in run_id

    def test_generate_run_id_multi_mode(self):
        """Test run_id with multi-turn mode."""
        from benchmark.interactive_controller import InteractiveBenchmarkController

        controller = InteractiveBenchmarkController()
        run_id = controller.generate_run_id(
            testee_id="dagent",
            mode="multi",
        )

        assert "_mt_" in run_id

    def test_generate_run_id_timestamp_format(self):
        """Test run_id has correct timestamp format."""
        from benchmark.interactive_controller import InteractiveBenchmarkController

        controller = InteractiveBenchmarkController()
        run_id = controller.generate_run_id(testee_id="test")

        # Extract and validate timestamp portion
        # Format: testee_mt_YYYYMMDD_HHMMSS_uuid
        parts = run_id.split("_")
        # Find the timestamp parts (should be YYYYMMDD and HHMMSS)
        timestamp_pattern = r"\d{8}_\d{6}"
        assert re.search(timestamp_pattern, run_id)


class TestInteractiveControllerInitialization:
    """Test InteractiveBenchmarkController initialization."""

    def test_default_initialization(self):
        """Test controller initializes with defaults."""
        from benchmark.interactive_controller import InteractiveBenchmarkController

        controller = InteractiveBenchmarkController()

        assert controller.infrastructure is not None
        assert controller.property_evaluator is not None
        assert controller.scoring_calculator is not None
        assert controller.validity_checker is not None

    def test_custom_initialization(self):
        """Test controller with custom components."""
        from benchmark.interactive_controller import InteractiveBenchmarkController

        mock_infra = Mock()
        mock_evaluator = Mock()

        controller = InteractiveBenchmarkController(
            infrastructure=mock_infra,
            property_evaluator=mock_evaluator,
        )

        assert controller.infrastructure == mock_infra
        assert controller.property_evaluator == mock_evaluator

    def test_session_initially_none(self):
        """Test session is initially None."""
        from benchmark.interactive_controller import InteractiveBenchmarkController

        controller = InteractiveBenchmarkController()

        assert controller.get_session() is None
        assert controller.get_mcp_server() is None


class TestRunInteractiveWorkflow:
    """Test run_interactive workflow."""

    @pytest.fixture
    def mock_task(self):
        """Create a mock task definition."""
        from benchmark.models.task import (
            TaskDefinition,
            TopologySpecification,
            IntentSpecification,
            Node,
            NodeType,
            Property,
            PropertyType,
            EvaluationProcedure,
            Platform,
            ConvergenceConfig,
        )

        nodes = [Node(name="R1", type=NodeType.ROUTER)]
        topology = TopologySpecification(nodes=nodes, links=[], interfaces=[])
        eval_proc = EvaluationProcedure(
            method="exec_and_parse",
            target_node="R1",
            command="test",
            parser="text",
            success_condition={},
        )
        properties = [
            Property(
                id="p1",
                type=PropertyType.INTERFACE_UP,
                description="Test",
                evaluation=eval_proc,
            )
        ]
        intent = IntentSpecification(properties=properties)
        task = TaskDefinition(
            task_id="test_001",
            description="Test task",
            platform=Platform.FRR,
            topology=topology,
            intent=intent,
            convergence=ConvergenceConfig(timeout_seconds=5),
        )
        return task

    @pytest.fixture
    def mock_controller(self):
        """Create a controller with mock components."""
        from benchmark.interactive_controller import InteractiveBenchmarkController
        from benchmark.models.results import PropertyEvaluationResult

        mock_infra = Mock()
        mock_infra.provision.return_value = "test_topo_001"
        mock_infra.is_ready.return_value = True
        mock_infra.teardown.return_value = True
        mock_infra.get_node_container_name.return_value = "clab-test-R1"

        mock_evaluator = Mock()
        mock_evaluator.evaluate_all_properties.return_value = [
            PropertyEvaluationResult(
                property_id="p1",
                satisfied=True,
                observation_raw="success",
                observation_parsed={"result": "success"},
                evaluation_time_seconds=0.5,
            )
        ]

        return InteractiveBenchmarkController(
            infrastructure=mock_infra,
            property_evaluator=mock_evaluator,
        )

    def test_run_interactive_returns_result(self, mock_controller, mock_task):
        """Test run_interactive returns BenchmarkResult."""
        from benchmark.models.results import BenchmarkResult

        # Patch the InteractiveSession to avoid actual provisioning
        with patch("benchmark.interactive_controller.InteractiveSession") as MockSession:
            mock_session = Mock()
            mock_session.start.return_value = Mock(
                session_id="test_session",
                nodes=["R1"],
                topology_id="test_topo_001",
            )
            mock_session.is_active = False  # Session immediately ends
            mock_session.get_approach.return_value = [("R1", "test command")]
            mock_session.get_session_status.return_value = Mock(turns_used=1)
            mock_session.teardown.return_value = True
            MockSession.return_value = mock_session

            result = mock_controller.run_interactive(
                task=mock_task,
                testee_id="test",
                wait_for_submit=False,
            )

        assert isinstance(result, BenchmarkResult)
        assert result.testee_id == "test"
        assert result.task_id == "test_001"

    def test_run_interactive_generates_run_id(self, mock_controller, mock_task):
        """Test run_interactive generates proper run_id."""
        with patch("benchmark.interactive_controller.InteractiveSession") as MockSession:
            mock_session = Mock()
            mock_session.start.return_value = Mock(
                session_id="test_session",
                nodes=["R1"],
                topology_id="test_topo_001",
            )
            mock_session.is_active = False
            mock_session.get_approach.return_value = []
            mock_session.get_session_status.return_value = Mock(turns_used=0)
            mock_session.teardown.return_value = True
            MockSession.return_value = mock_session

            result = mock_controller.run_interactive(
                task=mock_task,
                testee_id="dagent",
                model_name="gpt-4o",
            )

        assert result.run_id.startswith("dagent_mt_")

    def test_run_interactive_with_turn_limit(self, mock_controller, mock_task):
        """Test run_interactive respects turn limit."""
        with patch("benchmark.interactive_controller.InteractiveSession") as MockSession:
            mock_session = Mock()
            mock_session.start.return_value = Mock(
                session_id="test_session",
                nodes=["R1"],
                topology_id="test_topo_001",
            )
            mock_session.is_active = False
            mock_session.get_approach.return_value = []
            mock_session.get_session_status.return_value = Mock(turns_used=0)
            mock_session.teardown.return_value = True
            MockSession.return_value = mock_session

            mock_controller.run_interactive(
                task=mock_task,
                testee_id="test",
                turn_limit=100,
            )

            # Check that InteractiveSession was called with correct turn_limit
            MockSession.assert_called_once()
            call_kwargs = MockSession.call_args[1]
            assert call_kwargs["turn_limit"] == 100

    def test_run_interactive_with_time_limit(self, mock_controller, mock_task):
        """Test run_interactive respects time limit."""
        with patch("benchmark.interactive_controller.InteractiveSession") as MockSession:
            mock_session = Mock()
            mock_session.start.return_value = Mock(
                session_id="test_session",
                nodes=["R1"],
                topology_id="test_topo_001",
            )
            mock_session.is_active = False
            mock_session.get_approach.return_value = []
            mock_session.get_session_status.return_value = Mock(turns_used=0)
            mock_session.teardown.return_value = True
            MockSession.return_value = mock_session

            mock_controller.run_interactive(
                task=mock_task,
                testee_id="test",
                time_limit=1200.0,
            )

            # Check that InteractiveSession was called with correct time_limit
            call_kwargs = MockSession.call_args[1]
            assert call_kwargs["time_limit"] == 1200.0


class TestRunInteractiveErrorHandling:
    """Test error handling in run_interactive."""

    @pytest.fixture
    def mock_task(self):
        """Create a mock task definition."""
        from benchmark.models.task import (
            TaskDefinition,
            TopologySpecification,
            IntentSpecification,
            Node,
            NodeType,
            Property,
            PropertyType,
            EvaluationProcedure,
            Platform,
        )

        nodes = [Node(name="R1", type=NodeType.ROUTER)]
        topology = TopologySpecification(nodes=nodes, links=[], interfaces=[])
        eval_proc = EvaluationProcedure(
            method="exec_and_parse",
            target_node="R1",
            command="test",
            parser="text",
            success_condition={},
        )
        properties = [
            Property(
                id="p1",
                type=PropertyType.INTERFACE_UP,
                description="Test",
                evaluation=eval_proc,
            )
        ]
        intent = IntentSpecification(properties=properties)
        return TaskDefinition(
            task_id="test_001",
            description="Test task",
            platform=Platform.FRR,
            topology=topology,
            intent=intent,
        )

    def test_run_interactive_handles_session_error(self, mock_task):
        """Test run_interactive handles session start error gracefully."""
        from benchmark.interactive_controller import InteractiveBenchmarkController
        from benchmark.models.results import BenchmarkResult

        mock_infra = Mock()
        mock_infra.provision.side_effect = Exception("Provision failed")

        controller = InteractiveBenchmarkController(infrastructure=mock_infra)

        with patch("benchmark.interactive_controller.InteractiveSession") as MockSession:
            MockSession.return_value.start.side_effect = Exception("Session failed")
            MockSession.return_value.teardown.return_value = True

            result = controller.run_interactive(
                task=mock_task,
                testee_id="test",
            )

        assert isinstance(result, BenchmarkResult)
        assert result.success is False
        assert len(result.errors) > 0

    def test_run_interactive_handles_evaluation_error(self, mock_task):
        """Test run_interactive handles evaluation error gracefully."""
        from benchmark.interactive_controller import InteractiveBenchmarkController
        from benchmark.models.results import BenchmarkResult

        mock_infra = Mock()
        mock_infra.provision.return_value = "test_topo"
        mock_infra.is_ready.return_value = True

        mock_evaluator = Mock()
        mock_evaluator.evaluate_all_properties.side_effect = Exception("Eval failed")

        controller = InteractiveBenchmarkController(
            infrastructure=mock_infra,
            property_evaluator=mock_evaluator,
        )

        with patch("benchmark.interactive_controller.InteractiveSession") as MockSession:
            mock_session = Mock()
            mock_session.start.return_value = Mock(
                session_id="test",
                nodes=["R1"],
                topology_id="test_topo",
            )
            mock_session.is_active = False
            mock_session.get_approach.return_value = []
            mock_session.get_session_status.return_value = Mock(turns_used=0)
            mock_session.teardown.return_value = True
            MockSession.return_value = mock_session

            result = controller.run_interactive(
                task=mock_task,
                testee_id="test",
                wait_for_submit=False,
            )

        assert isinstance(result, BenchmarkResult)
        assert any("evaluation" in e.lower() for e in result.errors)


class TestMCPServerAccess:
    """Test MCP server access methods."""

    def test_get_mcp_server_before_run(self):
        """Test get_mcp_server returns None before run."""
        from benchmark.interactive_controller import InteractiveBenchmarkController

        controller = InteractiveBenchmarkController()
        assert controller.get_mcp_server() is None

    def test_get_session_before_run(self):
        """Test get_session returns None before run."""
        from benchmark.interactive_controller import InteractiveBenchmarkController

        controller = InteractiveBenchmarkController()
        assert controller.get_session() is None


class TestInteractiveHumanMode:
    """Tests for human interactive shell integration."""

    @pytest.fixture
    def mock_task(self):
        from benchmark.models.task import (
            ConvergenceConfig,
            EvaluationProcedure,
            IntentSpecification,
            Node,
            NodeType,
            Platform,
            Property,
            PropertyType,
            TaskDefinition,
            TopologySpecification,
        )

        nodes = [Node(name="R1", type=NodeType.ROUTER)]
        topology = TopologySpecification(nodes=nodes, links=[], interfaces=[])
        eval_proc = EvaluationProcedure(
            method="exec_and_parse",
            target_node="R1",
            command="test",
            parser="text",
            success_condition={},
        )
        properties = [
            Property(
                id="p1",
                type=PropertyType.INTERFACE_UP,
                description="Test",
                evaluation=eval_proc,
            )
        ]
        intent = IntentSpecification(properties=properties)
        return TaskDefinition(
            task_id="test_001",
            description="Test task",
            platform=Platform.FRR,
            topology=topology,
            intent=intent,
            convergence=ConvergenceConfig(timeout_seconds=5),
        )

    @pytest.fixture
    def mock_controller(self, mock_task):
        from benchmark.interactive_controller import InteractiveBenchmarkController
        from benchmark.models.results import PropertyEvaluationResult

        mock_infra = Mock()
        mock_infra.provision.return_value = "test_topo_001"
        mock_infra.is_ready.return_value = True
        mock_infra.teardown.return_value = True
        mock_infra.get_node_container_name.return_value = "clab-test-R1"

        mock_evaluator = Mock()
        mock_evaluator.evaluate_all_properties.return_value = [
            PropertyEvaluationResult(
                property_id="p1",
                satisfied=True,
                observation_raw="success",
                observation_parsed={"result": "success"},
                evaluation_time_seconds=0.5,
            )
        ]

        return InteractiveBenchmarkController(
            infrastructure=mock_infra,
            property_evaluator=mock_evaluator,
        )

    def test_human_mode_skips_mcp_server(self, mock_controller, mock_task):
        from benchmark.session.models import CommandType, SubmitResult

        submit = SubmitResult(
            session_id="sess-1",
            completed=True,
            total_turns=2,
            total_time=10.0,
            approach=[("R1", "cmd")],
            termination_reason="submitted",
        )

        with patch("benchmark.interactive_controller.InteractiveSession") as MockSession:
            mock_session = Mock()
            mock_session.start.return_value = Mock(
                session_id="test_session",
                nodes=["R1"],
                topology_id="test_topo_001",
            )
            mock_session.get_approach.return_value = [("R1", "test command")]
            mock_session.get_execution_log.return_value = [("R1", "test command", True)]
            mock_session.get_command_transcript.return_value = [
                ("R1", "test command", CommandType.CONFIG, True),
            ]
            mock_session._context = None
            mock_session.get_session_status.return_value = Mock(turns_used=2)
            mock_session.teardown.return_value = True
            MockSession.return_value = mock_session

            with patch("benchmark.human_shell.HumanShell") as MockShell:
                MockShell.return_value.run.return_value = submit

                result = mock_controller.run_interactive(
                    task=mock_task,
                    testee_id="alice",
                    testee_type="human",
                    interactive_human=True,
                    wait_for_submit=False,
                )

        assert mock_controller.get_mcp_server() is None
        assert result is not None
        assert result.testee_type == "human"
        assert result.metrics.turns_to_complete == 2

    def test_human_mode_quit_returns_none(self, mock_controller, mock_task):
        with patch("benchmark.interactive_controller.InteractiveSession") as MockSession:
            mock_session = Mock()
            mock_session.start.return_value = Mock(
                session_id="test_session",
                nodes=["R1"],
                topology_id="test_topo_001",
            )
            mock_session.teardown.return_value = True
            MockSession.return_value = mock_session

            with patch("benchmark.human_shell.HumanShell") as MockShell:
                MockShell.return_value.run.return_value = None

                result = mock_controller.run_interactive(
                    task=mock_task,
                    testee_id="alice",
                    testee_type="human",
                    interactive_human=True,
                    wait_for_submit=False,
                )

        assert result is None

    def test_pre_eval_wait_uses_full_convergence_budget(self, mock_controller, mock_task):
        """Final scoring waits the task's full convergence budget, not a 30s cap."""
        mock_task.convergence.timeout_seconds = 120
        with patch("benchmark.interactive_controller.InteractiveSession") as MockSession, patch(
            "benchmark.interactive_controller.time.sleep"
        ) as mock_sleep:
            mock_session = Mock()
            mock_session.start.return_value = Mock(
                session_id="test_session",
                nodes=["R1"],
                topology_id="test_topo_001",
            )
            mock_session.is_active = False
            mock_session.get_approach.return_value = []
            mock_session.get_session_status.return_value = Mock(turns_used=0)
            mock_session.teardown.return_value = True
            MockSession.return_value = mock_session

            mock_controller.run_interactive(
                task=mock_task,
                testee_id="test",
                wait_for_submit=False,
            )

        waited = [call.args[0] for call in mock_sleep.call_args_list if call.args]
        assert 120 in waited

    def test_run_interactive_persists_agent_actions(self, mock_controller, mock_task):
        """The action list returned by dagent is stored on the result."""
        payload = {
            "model_version": "openrouter:openai/gpt-6-luna",
            "reasoning_trace": [],
            "actions": [
                {"action": "exec_command", "input": {"node": "R1", "command": "show ip route"}, "result": {"success": True}},
                {"action": "submit", "input": {}, "result": {"success": True}},
            ],
            "token_usage": {"prompt_tokens": 1, "completion_tokens": 1},
            "tool_usage": {"exec_command": 1},
        }
        mock_response = Mock()
        mock_response.json.return_value = payload
        mock_client = MagicMock()
        mock_client.__enter__.return_value.post.return_value = mock_response

        with patch("benchmark.interactive_controller.InteractiveSession") as MockSession, patch(
            "benchmark.interactive_controller.time.sleep"
        ), patch("httpx.Client", return_value=mock_client):
            mock_session = Mock()
            mock_session.start.return_value = Mock(
                session_id="test_session",
                nodes=["R1"],
                topology_id="test_topo_001",
            )
            mock_session.is_active = False
            mock_session.get_approach.return_value = []
            mock_session.get_session_status.return_value = Mock(turns_used=1)
            mock_session.get_command_transcript.return_value = []
            mock_session.get_execution_log.return_value = []
            mock_session.teardown.return_value = True
            mock_session._context = None
            MockSession.return_value = mock_session

            result = mock_controller.run_interactive(
                task=mock_task,
                testee_id="openrouter_openaigpt6luna_single",
                dagent_endpoint="http://localhost:8000",
                wait_for_submit=False,
            )

        assert [a["action"] for a in result.actions] == ["exec_command", "submit"]


class TestInferTerminationReason:
    def test_time_limit_is_not_labeled_submitted(self):
        from benchmark.interactive_controller import infer_termination_reason

        actions = [
            {"action": "exec_command", "result": {"success": True}},
            {"action": "exec_command", "result": {"success": False, "error": "time_limit_exceeded"}},
        ]
        assert infer_termination_reason(actions, True, 24, []) == "time_limit_exceeded"

    def test_submit_action_is_labeled_submitted(self):
        from benchmark.interactive_controller import infer_termination_reason

        actions = [
            {"action": "exec_command", "result": {"success": True}},
            {"action": "submit", "result": {"success": True}},
        ]
        assert infer_termination_reason(actions, True, 5, []) == "submitted"
