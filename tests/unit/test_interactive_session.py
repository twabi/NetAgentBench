"""
Unit tests for InteractiveSession class.

Tests the session lifecycle, command execution, turn/time limits,
and approach reconstruction.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch


class TestInteractiveSessionInitialization:
    """Test InteractiveSession initialization."""

    def test_session_initialization_defaults(self):
        """Test session initializes with default values."""
        from benchmark.session.session import InteractiveSession
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

        # Create minimal task
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
        )

        # Create session with mock infrastructure
        mock_infra = Mock()
        session = InteractiveSession(task, infrastructure=mock_infra)

        assert session.task == task
        assert session.turn_limit == 50
        assert session.time_limit == 600.0
        assert session.convergence_timeout == 30
        assert session.is_active is False

    def test_session_initialization_custom_limits(self):
        """Test session initializes with custom limits."""
        from benchmark.session.session import InteractiveSession
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
        task = TaskDefinition(
            task_id="test_001",
            description="Test task",
            platform=Platform.FRR,
            topology=topology,
            intent=intent,
        )

        mock_infra = Mock()
        session = InteractiveSession(
            task,
            infrastructure=mock_infra,
            turn_limit=100,
            time_limit=1200.0,
            convergence_timeout=60,
        )

        assert session.turn_limit == 100
        assert session.time_limit == 1200.0
        assert session.convergence_timeout == 60


class TestInteractiveSessionLifecycle:
    """Test session lifecycle (start, submit)."""

    @pytest.fixture
    def mock_session(self):
        """Create a session with mock infrastructure."""
        from benchmark.session.session import InteractiveSession
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

        nodes = [Node(name="R1", type=NodeType.ROUTER), Node(name="R2", type=NodeType.ROUTER)]
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
        )

        mock_infra = Mock()
        mock_infra.provision.return_value = "test_topo_001"
        mock_infra.is_ready.return_value = True
        mock_infra.teardown.return_value = True
        mock_infra.get_node_container_name.return_value = "clab-test-R1"

        return InteractiveSession(task, infrastructure=mock_infra, turn_limit=5, time_limit=60.0)

    def test_start_creates_session_context(self, mock_session):
        """Test start() creates and returns SessionContext."""
        from benchmark.session.models import SessionContext

        ctx = mock_session.start()

        assert isinstance(ctx, SessionContext)
        assert ctx.task_id == "test_001"
        assert ctx.nodes == ["R1", "R2"]
        assert ctx.turn_limit == 5
        assert ctx.time_limit == 60.0
        assert ctx.topology_id == "test_topo_001"
        assert mock_session.is_active is True

    def test_start_provisions_topology(self, mock_session):
        """Test start() provisions the topology."""
        mock_session.start()

        mock_session.infrastructure.provision.assert_called_once()

    def test_start_waits_for_ready(self, mock_session):
        """Test start() waits for topology to be ready."""
        mock_session.start()

        mock_session.infrastructure.is_ready.assert_called()

    def test_submit_returns_result(self, mock_session):
        """Test submit() returns SubmitResult."""
        from benchmark.session.models import SubmitResult

        mock_session.start()
        result = mock_session.submit()

        assert isinstance(result, SubmitResult)
        assert result.completed is True
        assert result.termination_reason == "submitted"

    def test_submit_deactivates_session(self, mock_session):
        """Test submit() deactivates the session."""
        mock_session.start()
        assert mock_session.is_active is True

        mock_session.submit()
        assert mock_session.is_active is False

    def test_start_twice_raises_error(self, mock_session):
        """Test starting an already active session raises error."""
        from benchmark.session.session import SessionError

        mock_session.start()

        with pytest.raises(SessionError, match="already active"):
            mock_session.start()

    def test_start_executes_preconfiguration(self):
        """Test start() executes pre-configuration steps."""
        from benchmark.session.session import InteractiveSession
        from benchmark.models.task import (
            TaskDefinition,
            TopologySpecification,
            Node,
            NodeType,
            IntentSpecification,
            Platform,
            PreconfigurationStep,
            Property,
            PropertyType,
            EvaluationProcedure,
        )

        nodes = [Node(name="R1", type=NodeType.ROUTER)]
        topology = TopologySpecification(nodes=nodes, links=[], interfaces=[])
        eval_proc = EvaluationProcedure(
            method="exec_and_parse", target_node="R1", command="test", parser="text", success_condition={}
        )
        prop = Property(
            id="p1", type=PropertyType.INTERFACE_UP, description="Test", evaluation=eval_proc
        )
        task = TaskDefinition(
            task_id="test_preconfig",
            description="Test",
            platform=Platform.FRR,
            topology=topology,
            intent=IntentSpecification(properties=[prop]),
            preconfiguration=[
                PreconfigurationStep(node="R1", command="conf t"),
                PreconfigurationStep(node="R1", command="interface lo")
            ]
        )

        mock_infra = Mock()
        mock_infra.provision.return_value = "topo1"
        mock_infra.is_ready.return_value = True
        mock_infra.get_node_container_name.return_value = "clab-R1"

        session = InteractiveSession(task, infrastructure=mock_infra)
        session._executor = Mock()
        session._executor.exec_on_node.return_value = ("", "", 0)

        session.start()

        # Check executor was called for preconfig
        assert session._executor.exec_on_node.call_count == 2
        session._executor.exec_on_node.assert_any_call("clab-R1", "conf t", timeout=30)
        session._executor.exec_on_node.assert_any_call("clab-R1", "interface lo", timeout=30)

    def test_start_fails_if_fault_not_verified(self):
        """Test start() fails if fault verification property is not satisfied."""
        from benchmark.session.session import InteractiveSession, SessionError
        from benchmark.models.task import (
            TaskDefinition,
            TopologySpecification,
            Node,
            NodeType,
            IntentSpecification,
            Platform,
            Property,
            PropertyType,
            EvaluationProcedure,
        )
        from benchmark.models.results import PropertyEvaluationResult

        nodes = [Node(name="R1", type=NodeType.ROUTER)]
        topology = TopologySpecification(nodes=nodes, links=[], interfaces=[])
        prop = Property(
            id="fault1",
            type=PropertyType.OSPF_CONFIGURATION,
            description="Fault expected",
            evaluation=EvaluationProcedure(
                method="exec_and_parse", target_node="R1", command="test", parser="text", success_condition={}
            )
        )
        task = TaskDefinition(
            task_id="test_fault",
            description="Test",
            platform=Platform.FRR,
            topology=topology,
            intent=IntentSpecification(properties=[prop]),
            fault_verification=[prop]
        )

        mock_infra = Mock()
        mock_infra.provision.return_value = "topo1"
        mock_infra.is_ready.return_value = True

        session = InteractiveSession(task, infrastructure=mock_infra)
        session._evaluator = Mock()
        # Mock failed verification
        session._evaluator.evaluate_all_properties.return_value = [
            PropertyEvaluationResult(
                property_id="fault1", satisfied=False, observation_raw="", observation_parsed=None, evaluation_time_seconds=0.1
            )
        ]

        with pytest.raises(SessionError, match="Fault verification failed"):
            session.start()

        assert session.is_active is False
        mock_infra.teardown.assert_called_once_with("topo1")

    def test_start_succeeds_if_fault_verified(self):
        """Test start() succeeds if fault verification property is satisfied."""
        from benchmark.session.session import InteractiveSession
        from benchmark.models.task import (
            TaskDefinition,
            TopologySpecification,
            Node,
            NodeType,
            IntentSpecification,
            Platform,
            Property,
            PropertyType,
            EvaluationProcedure,
        )
        from benchmark.models.results import PropertyEvaluationResult

        nodes = [Node(name="R1", type=NodeType.ROUTER)]
        topology = TopologySpecification(nodes=nodes, links=[], interfaces=[])
        prop = Property(
            id="fault1",
            type=PropertyType.OSPF_CONFIGURATION,
            description="Fault expected",
            evaluation=EvaluationProcedure(
                method="exec_and_parse", target_node="R1", command="test", parser="text", success_condition={}
            )
        )
        task = TaskDefinition(
            task_id="test_fault",
            description="Test",
            platform=Platform.FRR,
            topology=topology,
            intent=IntentSpecification(properties=[prop]),
            fault_verification=[prop]
        )

        mock_infra = Mock()
        mock_infra.provision.return_value = "topo1"
        mock_infra.is_ready.return_value = True

        session = InteractiveSession(task, infrastructure=mock_infra)
        session._evaluator = Mock()
        # Mock successful verification
        session._evaluator.evaluate_all_properties.return_value = [
            PropertyEvaluationResult(
                property_id="fault1", satisfied=True, observation_raw="", observation_parsed=None, evaluation_time_seconds=0.1
            )
        ]

        session.start()
        assert session.is_active is True


class TestExecCommand:
    """Test exec_command functionality."""

    @pytest.fixture
    def active_session(self):
        """Create an active session with mocked execution."""
        from benchmark.session.session import InteractiveSession
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
        task = TaskDefinition(
            task_id="test_001",
            description="Test task",
            platform=Platform.FRR,
            topology=topology,
            intent=intent,
        )

        mock_infra = Mock()
        mock_infra.provision.return_value = "test_topo_001"
        mock_infra.is_ready.return_value = True
        mock_infra.get_node_container_name.return_value = "clab-test-R1"

        session = InteractiveSession(task, infrastructure=mock_infra, turn_limit=5, time_limit=60.0)
        
        # Mock the command executor
        session._executor = Mock()
        session._executor.exec_on_node.return_value = ("output", "", 0)

        session.start()
        return session

    def test_exec_config_command_increments_turn(self, active_session):
        """Test CONFIG command increments turn counter."""
        from benchmark.session.models import CommandType

        status_before = active_session.get_session_status()
        assert status_before.turns_used == 0

        active_session.exec_command("R1", "test command", CommandType.CONFIG)

        status_after = active_session.get_session_status()
        assert status_after.turns_used == 1

    def test_exec_read_command_no_turn_increment(self, active_session):
        """Test READ command does NOT increment turn counter."""
        from benchmark.session.models import CommandType

        active_session.exec_command("R1", "show version", CommandType.READ)

        status = active_session.get_session_status()
        assert status.turns_used == 0

    def test_exec_command_returns_result(self, active_session):
        """Test exec_command returns ExecResult."""
        from benchmark.session.models import ExecResult, CommandType

        result = active_session.exec_command("R1", "test command")

        assert isinstance(result, ExecResult)
        assert result.success is True
        assert result.exit_code == 0

    def test_exec_command_tracks_history(self, active_session):
        """Test exec_command adds to command history."""
        from benchmark.session.models import CommandType

        active_session.exec_command("R1", "config1", CommandType.CONFIG)
        active_session.exec_command("R1", "read1", CommandType.READ)
        active_session.exec_command("R1", "config2", CommandType.CONFIG)

        approach = active_session.get_approach()
        assert len(approach) == 2
        assert approach[0] == ("R1", "config1")
        assert approach[1] == ("R1", "config2")

    def test_exec_unknown_node_returns_error(self, active_session):
        """Test exec_command on unknown node returns error."""
        result = active_session.exec_command("UNKNOWN", "command")

        assert result.success is False
        assert "Unknown node" in result.error_message


class TestTurnLimitEnforcement:
    """Test turn limit enforcement."""

    @pytest.fixture
    def limited_session(self):
        """Create a session with low turn limit."""
        from benchmark.session.session import InteractiveSession
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
        task = TaskDefinition(
            task_id="test_001",
            description="Test task",
            platform=Platform.FRR,
            topology=topology,
            intent=intent,
        )

        mock_infra = Mock()
        mock_infra.provision.return_value = "test_topo_001"
        mock_infra.is_ready.return_value = True
        mock_infra.get_node_container_name.return_value = "clab-test-R1"

        session = InteractiveSession(task, infrastructure=mock_infra, turn_limit=3, time_limit=600.0)
        session._executor = Mock()
        session._executor.exec_on_node.return_value = ("output", "", 0)

        session.start()
        return session

    def test_turn_limit_exceeded_raises_error(self, limited_session):
        """Test exceeding turn limit raises error."""
        from benchmark.session.session import TurnLimitExceededError
        from benchmark.session.models import CommandType

        # Use up all turns
        limited_session.exec_command("R1", "cmd1", CommandType.CONFIG)
        limited_session.exec_command("R1", "cmd2", CommandType.CONFIG)
        limited_session.exec_command("R1", "cmd3", CommandType.CONFIG)

        # Next should fail
        with pytest.raises(TurnLimitExceededError):
            limited_session.exec_command("R1", "cmd4", CommandType.CONFIG)

    def test_read_commands_dont_count_toward_limit(self, limited_session):
        """Test READ commands don't count toward turn limit."""
        from benchmark.session.models import CommandType

        # Use all turns with CONFIG
        limited_session.exec_command("R1", "cmd1", CommandType.CONFIG)
        limited_session.exec_command("R1", "cmd2", CommandType.CONFIG)
        limited_session.exec_command("R1", "cmd3", CommandType.CONFIG)

        # READ should still work
        result = limited_session.exec_command("R1", "show status", CommandType.READ)
        assert result.success is True


class TestTimeLimitEnforcement:
    """Test time limit enforcement."""

    def test_session_becomes_inactive_after_time_limit(self):
        """Test session becomes inactive after time limit."""
        from benchmark.session.session import InteractiveSession
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
        task = TaskDefinition(
            task_id="test_001",
            description="Test task",
            platform=Platform.FRR,
            topology=topology,
            intent=intent,
        )

        mock_infra = Mock()
        mock_infra.provision.return_value = "test_topo_001"
        mock_infra.is_ready.return_value = True

        # Very short time limit
        session = InteractiveSession(task, infrastructure=mock_infra, time_limit=0.1)
        session.start()

        # Wait for time limit
        import time
        time.sleep(0.15)

        assert session.is_active is False


class TestSessionStatus:
    """Test get_session_status functionality."""

    @pytest.fixture
    def active_session(self):
        """Create an active session."""
        from benchmark.session.session import InteractiveSession
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
        task = TaskDefinition(
            task_id="test_001",
            description="Test task",
            platform=Platform.FRR,
            topology=topology,
            intent=intent,
        )

        mock_infra = Mock()
        mock_infra.provision.return_value = "test_topo_001"
        mock_infra.is_ready.return_value = True
        mock_infra.get_node_container_name.return_value = "clab-test-R1"

        session = InteractiveSession(task, infrastructure=mock_infra, turn_limit=10, time_limit=60.0)
        session._executor = Mock()
        session._executor.exec_on_node.return_value = ("output", "", 0)

        session.start()
        return session

    def test_status_shows_correct_turns(self, active_session):
        """Test status shows correct turn counts."""
        from benchmark.session.models import CommandType

        active_session.exec_command("R1", "cmd1", CommandType.CONFIG)
        active_session.exec_command("R1", "cmd2", CommandType.CONFIG)

        status = active_session.get_session_status()
        assert status.turns_used == 2
        assert status.turns_remaining == 8

    def test_status_shows_is_active(self, active_session):
        """Test status shows active state."""
        status = active_session.get_session_status()
        assert status.is_active is True

    def test_status_not_started_raises_error(self):
        """Test getting status before start raises error."""
        from benchmark.session.session import InteractiveSession, SessionNotActiveError
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
        task = TaskDefinition(
            task_id="test_001",
            description="Test task",
            platform=Platform.FRR,
            topology=topology,
            intent=intent,
        )

        mock_infra = Mock()
        session = InteractiveSession(task, infrastructure=mock_infra)

        with pytest.raises(SessionNotActiveError):
            session.get_session_status()


class TestApproachReconstruction:
    """Test get_approach functionality."""

    @pytest.fixture
    def session_with_commands(self):
        """Create session with executed commands."""
        from benchmark.session.session import InteractiveSession
        from benchmark.session.models import CommandType
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

        nodes = [Node(name="R1", type=NodeType.ROUTER), Node(name="R2", type=NodeType.ROUTER)]
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
        )

        mock_infra = Mock()
        mock_infra.provision.return_value = "test_topo_001"
        mock_infra.is_ready.return_value = True
        mock_infra.get_node_container_name.return_value = "clab-test-R1"

        session = InteractiveSession(task, infrastructure=mock_infra, turn_limit=50)
        session._executor = Mock()
        session._executor.exec_on_node.return_value = ("output", "", 0)

        session.start()

        # Execute mixed commands
        session.exec_command("R1", "ip addr add 10.0.0.1/24 dev eth1", CommandType.CONFIG)
        session.exec_command("R1", "show ip address", CommandType.READ)
        session.exec_command("R2", "ip addr add 10.0.0.2/24 dev eth1", CommandType.CONFIG)
        session.exec_command("R1", "ping 10.0.0.2", CommandType.READ)
        session.exec_command("R1", "ip route add 0.0.0.0/0 via 10.0.0.254", CommandType.CONFIG)

        return session

    def test_get_approach_returns_config_only(self, session_with_commands):
        """Test get_approach returns only CONFIG commands."""
        approach = session_with_commands.get_approach()

        assert len(approach) == 3
        assert approach[0] == ("R1", "ip addr add 10.0.0.1/24 dev eth1")
        assert approach[1] == ("R2", "ip addr add 10.0.0.2/24 dev eth1")
        assert approach[2] == ("R1", "ip route add 0.0.0.0/0 via 10.0.0.254")

    def test_submit_includes_approach(self, session_with_commands):
        """Test submit result includes correct approach."""
        result = session_with_commands.submit()

        assert len(result.approach) == 3
        assert result.approach[0][0] == "R1"
        assert result.approach[2][0] == "R1"
