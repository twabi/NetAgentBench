"""
Integration tests for interactive session with Containerlab.

These tests require Containerlab to be installed and running.
Mark with @pytest.mark.integration to allow skipping in CI.
"""

import pytest
import time
from unittest.mock import Mock, patch


# Mark all tests as integration tests
pytestmark = pytest.mark.integration


class TestInteractiveSessionWithContainerlab:
    """Integration tests for InteractiveSession with real infrastructure."""

    @pytest.fixture
    def simple_task(self):
        """Create a simple 2-node task for testing."""
        from benchmark.models.task import (
            TaskDefinition,
            TopologySpecification,
            IntentSpecification,
            Node,
            Link,
            NodeType,
            Property,
            PropertyType,
            EvaluationProcedure,
            Platform,
            ConvergenceConfig,
        )

        nodes = [
            Node(name="R1", type=NodeType.ROUTER),
            Node(name="R2", type=NodeType.ROUTER),
        ]
        links = [Link(endpoints=["R1:eth1", "R2:eth1"])]
        topology = TopologySpecification(nodes=nodes, links=links, interfaces=[])
        
        eval_proc = EvaluationProcedure(
            method="exec_and_parse",
            target_node="R1",
            command="vtysh -c 'show version'",
            parser="text",
            success_condition={"contains": "FRRouting"},
        )
        properties = [
            Property(
                id="version_check",
                type=PropertyType.INTERFACE_UP,
                description="Check FRR version",
                evaluation=eval_proc,
            )
        ]
        intent = IntentSpecification(properties=properties)
        
        return TaskDefinition(
            task_id="integration_test_001",
            description="Integration test task",
            platform=Platform.FRR,
            topology=topology,
            intent=intent,
            convergence=ConvergenceConfig(timeout_seconds=5),
        )

    def test_session_lifecycle_with_real_infrastructure(self, simple_task):
        """Test complete session lifecycle with real Containerlab."""
        from benchmark.session.session import InteractiveSession
        from benchmark.session.models import CommandType, ConvergenceStatus
        from benchmark.infrastructure.containerlab import ContainerlabProvider

        infrastructure = ContainerlabProvider()
        session = InteractiveSession(
            task=simple_task,
            infrastructure=infrastructure,
            turn_limit=10,
            time_limit=300.0,
        )

        try:
            # Start session
            context = session.start()
            assert context.session_id is not None
            assert "R1" in context.nodes
            assert "R2" in context.nodes
            assert session.is_active

            # Execute command
            result = session.exec_command(
                node="R1",
                command="vtysh -c 'show version'",
                command_type=CommandType.READ,
            )
            assert result.success
            assert "FRRouting" in result.stdout or result.stdout != ""
            assert result.convergence_status == ConvergenceStatus.CONVERGED

            # Check status
            status = session.get_session_status()
            assert status.is_active
            assert status.turns_used == 0  # READ doesn't count

            # Execute config command
            config_result = session.exec_command(
                node="R1",
                command="vtysh -c 'configure terminal' -c 'hostname TestR1' -c 'end'",
                command_type=CommandType.CONFIG,
            )
            assert config_result.success

            # Verify turn counted
            status = session.get_session_status()
            assert status.turns_used == 1

            # Submit session
            submit_result = session.submit()
            assert submit_result.completed
            assert submit_result.total_turns == 1
            assert not session.is_active

        finally:
            session.teardown()

    def test_exec_command_returns_stdout(self, simple_task):
        """Test that exec_command returns actual command output."""
        from benchmark.session.session import InteractiveSession
        from benchmark.session.models import CommandType
        from benchmark.infrastructure.containerlab import ContainerlabProvider

        infrastructure = ContainerlabProvider()
        session = InteractiveSession(
            task=simple_task,
            infrastructure=infrastructure,
            turn_limit=10,
            time_limit=300.0,
        )

        try:
            session.start()

            # Execute show command
            result = session.exec_command(
                node="R1",
                command="hostname",
                command_type=CommandType.READ,
            )

            assert result.success
            assert result.stdout is not None
            assert len(result.stdout) > 0
            assert result.exit_code == 0

        finally:
            session.teardown()


class TestMCPServerIntegration:
    """Integration tests for MCP server with real session."""

    @pytest.fixture
    def simple_task(self):
        """Create a simple task for MCP server testing."""
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
            command="hostname",
            parser="text",
            success_condition={"contains": "R1"},
        )
        properties = [
            Property(
                id="hostname_check",
                type=PropertyType.INTERFACE_UP,
                description="Check hostname",
                evaluation=eval_proc,
            )
        ]
        intent = IntentSpecification(properties=properties)
        
        return TaskDefinition(
            task_id="mcp_test_001",
            description="MCP server test task",
            platform=Platform.FRR,
            topology=topology,
            intent=intent,
            convergence=ConvergenceConfig(timeout_seconds=5),
        )

    def test_mcp_server_tool_registration_with_real_session(self, simple_task):
        """Test MCP server registers all tools correctly with real session."""
        from benchmark.session.session import InteractiveSession
        from benchmark.session.mcp_server import BenchmarkMCPServer
        from benchmark.infrastructure.containerlab import ContainerlabProvider

        infrastructure = ContainerlabProvider()
        session = InteractiveSession(
            task=simple_task,
            infrastructure=infrastructure,
            turn_limit=10,
            time_limit=300.0,
        )

        try:
            session.start()

            server = BenchmarkMCPServer(session=session)
            tools = server.get_tool_list()

            assert "exec_command" in tools
            assert "submit" in tools
            assert "get_session_status" in tools
            assert "get_nodes" in tools
            assert len(tools) == 4

        finally:
            session.teardown()

    def test_mcp_server_streamable_http_app_with_real_session(self, simple_task):
        """Test MCP server can create streamable HTTP app with real session."""
        from benchmark.session.session import InteractiveSession
        from benchmark.session.mcp_server import BenchmarkMCPServer
        from benchmark.infrastructure.containerlab import ContainerlabProvider

        infrastructure = ContainerlabProvider()
        session = InteractiveSession(
            task=simple_task,
            infrastructure=infrastructure,
            turn_limit=10,
            time_limit=300.0,
        )

        try:
            session.start()

            server = BenchmarkMCPServer(session=session)
            app = server.streamable_http_app()

            assert app is not None
            # App should be a Starlette application
            assert hasattr(app, "routes")

        finally:
            session.teardown()

    def test_mcp_server_close_with_real_session(self, simple_task):
        """Test MCP server close method with real session."""
        from benchmark.session.session import InteractiveSession
        from benchmark.session.mcp_server import BenchmarkMCPServer
        from benchmark.infrastructure.containerlab import ContainerlabProvider

        infrastructure = ContainerlabProvider()
        session = InteractiveSession(
            task=simple_task,
            infrastructure=infrastructure,
            turn_limit=10,
            time_limit=300.0,
        )

        try:
            session.start()

            server = BenchmarkMCPServer(session=session)
            assert server.session is not None

            server.close()
            assert server.session is None

        finally:
            session.teardown()


class TestInteractiveControllerIntegration:
    """Integration tests for InteractiveBenchmarkController."""

    @pytest.fixture
    def simple_task(self):
        """Create a simple task for testing."""
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
                id="test_prop",
                type=PropertyType.INTERFACE_UP,
                description="Test property",
                evaluation=eval_proc,
            )
        ]
        intent = IntentSpecification(properties=properties)
        
        return TaskDefinition(
            task_id="controller_test_001",
            description="Controller integration test",
            platform=Platform.FRR,
            topology=topology,
            intent=intent,
            convergence=ConvergenceConfig(timeout_seconds=5),
        )

    def test_controller_run_id_generation(self):
        """Test controller generates proper run IDs."""
        from benchmark.interactive_controller import InteractiveBenchmarkController

        controller = InteractiveBenchmarkController()

        # Basic run ID
        run_id = controller.generate_run_id(testee_id="dagent")
        assert "dagent" in run_id
        assert "_mt_" in run_id

        # With model name
        run_id = controller.generate_run_id(testee_id="dagent", model_name="gpt-4o")
        assert "gpt4o" in run_id

        # Single mode
        run_id = controller.generate_run_id(testee_id="test", mode="single")
        assert "_st_" in run_id

    def test_controller_with_real_infrastructure(self, simple_task):
        """Test controller with real Containerlab infrastructure."""
        from benchmark.interactive_controller import InteractiveBenchmarkController
        from benchmark.infrastructure.containerlab import ContainerlabProvider
        from benchmark.models.results import BenchmarkResult

        controller = InteractiveBenchmarkController(
            infrastructure=ContainerlabProvider(),
        )

        try:
            result = controller.run_interactive(
                task=simple_task,
                testee_id="integration_test",
                wait_for_submit=False,  # Don't wait for agent - just test lifecycle
            )

            # Verify result structure
            assert isinstance(result, BenchmarkResult)
            assert result.testee_id == "integration_test"
            assert result.task_id == "controller_test_001"
            assert result.metrics.infrastructure_provision_time > 0
            assert result.run_id is not None
            assert "integration_test" in result.run_id

        except Exception as e:
            # Controller handles its own cleanup in finally block
            raise e
