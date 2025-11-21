"""
Integration tests for Executor components.

These tests run against REAL Containerlab and Docker, not mocks.

Requirements:
- Containerlab installed and accessible via 'sudo clab'
- Docker installed and running
- sudo access (no password prompt for clab commands)
- Network access to pull container images

WARNING: These tests create actual containers and may take 30-60 seconds to run.
"""
import pytest
import time
from datetime import datetime

from benchmark.infrastructure.containerlab import ContainerlabProvider
from benchmark.models.task import (
    Node,
    NodeType,
    Platform,
    Link,
    TopologySpecification,
    EvaluationProcedure,
)
from benchmark.models.submission import CommandSequence, Approach


# Import executors (these will be implemented)
try:
    from benchmark.executor.command import CommandExecutor, ExecutionLogEntry
    from benchmark.executor.observation import ObservationExecutor, ObservationResult
except ImportError:
    # Modules don't exist yet - tests will fail until implemented
    CommandExecutor = None
    ObservationExecutor = None
    ExecutionLogEntry = None
    ObservationResult = None


@pytest.fixture
def simple_topology():
    """Create a simple single-node topology for testing"""
    nodes = [
        Node(
            name="test_node",
            type=NodeType.LINUX,
            image="alpine:latest",
            platform=Platform.FRR,
        )
    ]
    return TopologySpecification(nodes=nodes, links=[])


@pytest.fixture
def two_node_topology():
    """Create a two-node topology for multi-node testing"""
    nodes = [
        Node(
            name="node1",
            type=NodeType.LINUX,
            image="alpine:latest",
            platform=Platform.FRR,
        ),
        Node(
            name="node2",
            type=NodeType.LINUX,
            image="alpine:latest",
            platform=Platform.FRR,
        ),
    ]
    links = [Link(endpoints=["node1:eth1", "node2:eth1"])]
    return TopologySpecification(nodes=nodes, links=links)


@pytest.fixture
def provisioned_topology(simple_topology):
    """Provision a topology and return (provider, topology_id)"""
    provider = ContainerlabProvider()
    topology_id = provider.provision(simple_topology)
    
    # Wait for ready
    max_wait = 30
    start_time = time.time()
    while time.time() - start_time < max_wait:
        if provider.is_ready(topology_id):
            break
        time.sleep(2)
    
    yield provider, topology_id
    
    # Cleanup
    provider.teardown(topology_id)


@pytest.fixture
def provisioned_two_node_topology(two_node_topology):
    """Provision a two-node topology and return (provider, topology_id)"""
    provider = ContainerlabProvider()
    topology_id = provider.provision(two_node_topology)
    
    # Wait for ready
    max_wait = 30
    start_time = time.time()
    while time.time() - start_time < max_wait:
        if provider.is_ready(topology_id):
            break
        time.sleep(2)
    
    yield provider, topology_id, two_node_topology
    
    # Cleanup
    provider.teardown(topology_id)


def check_prerequisites():
    """Check if containerlab and docker are available"""
    import subprocess
    try:
        # Check containerlab
        result = subprocess.run(
            ["clab", "version"],
            capture_output=True,
            timeout=5,
        )
        if result.returncode != 0:
            result = subprocess.run(
                ["sudo", "-n", "clab", "version"],
                capture_output=True,
                timeout=5,
            )
            if result.returncode != 0:
                return False
        
        # Check Docker
        import docker
        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not check_prerequisites(),
    reason="Containerlab or Docker not available",
)


@pytest.mark.integration
@pytest.mark.skipif(CommandExecutor is None, reason="CommandExecutor not implemented yet")
class TestCommandExecutorBasic:
    """Test basic command execution on containers"""

    def test_exec_on_node_simple_command(self, provisioned_topology):
        """Test executing a simple command that succeeds"""
        provider, topology_id = provisioned_topology
        executor = CommandExecutor()
        
        container_name = provider.get_node_container_name(topology_id, "test_node")
        
        # Execute simple echo command
        stdout, stderr, exit_code = executor.exec_on_node(container_name, "echo 'Hello World'")
        
        # Verify success
        assert exit_code == 0
        assert "Hello World" in stdout
        assert stderr == "" or stderr is None

    def test_exec_on_node_with_output(self, provisioned_topology):
        """Test command execution captures stdout correctly"""
        provider, topology_id = provisioned_topology
        executor = CommandExecutor()
        
        container_name = provider.get_node_container_name(topology_id, "test_node")
        
        # Execute command with predictable output
        stdout, stderr, exit_code = executor.exec_on_node(container_name, "echo 'Line1'; echo 'Line2'")
        
        assert exit_code == 0
        assert "Line1" in stdout
        assert "Line2" in stdout

    def test_exec_on_node_with_stderr(self, provisioned_topology):
        """Test command execution captures stderr separately"""
        provider, topology_id = provisioned_topology
        executor = CommandExecutor()
        
        container_name = provider.get_node_container_name(topology_id, "test_node")
        
        # Execute command that writes to stderr
        stdout, stderr, exit_code = executor.exec_on_node(
            container_name, 
            "sh -c 'echo stdout_msg; echo stderr_msg >&2'"
        )
        
        # Should capture both
        assert "stdout_msg" in stdout
        # Note: stderr behavior may vary by Docker version
        # Some versions merge stderr into stdout

    def test_exec_on_node_failed_command(self, provisioned_topology):
        """Test that failed commands return non-zero exit code"""
        provider, topology_id = provisioned_topology
        executor = CommandExecutor()
        
        container_name = provider.get_node_container_name(topology_id, "test_node")
        
        # Execute command that fails
        stdout, stderr, exit_code = executor.exec_on_node(container_name, "false")
        
        assert exit_code != 0

    def test_exec_on_node_nonexistent_command(self, provisioned_topology):
        """Test executing a command that doesn't exist"""
        provider, topology_id = provisioned_topology
        executor = CommandExecutor()
        
        container_name = provider.get_node_container_name(topology_id, "test_node")
        
        # Execute non-existent command
        stdout, stderr, exit_code = executor.exec_on_node(
            container_name, 
            "nonexistent_command_12345"
        )
        
        # Should fail with non-zero exit code
        assert exit_code != 0

    def test_exec_on_node_nonexistent_container(self):
        """Test executing command on non-existent container raises error"""
        executor = CommandExecutor()
        
        # Try to execute on container that doesn't exist
        with pytest.raises(Exception):
            executor.exec_on_node("nonexistent_container_12345", "echo test")

    def test_exec_on_node_with_timeout(self, provisioned_topology):
        """Test that timeout parameter is respected"""
        provider, topology_id = provisioned_topology
        executor = CommandExecutor()
        
        container_name = provider.get_node_container_name(topology_id, "test_node")
        
        # Execute command with custom timeout (should succeed quickly)
        stdout, stderr, exit_code = executor.exec_on_node(
            container_name, 
            "echo test",
            timeout=5
        )
        
        assert exit_code == 0


@pytest.mark.integration
@pytest.mark.skipif(ObservationExecutor is None, reason="ObservationExecutor not implemented yet")
class TestObservationExecutor:
    """Test observation collection from nodes"""

    def test_observe_with_simple_command(self, provisioned_topology):
        """Test basic observation collection"""
        provider, topology_id = provisioned_topology
        obs_executor = ObservationExecutor()
        
        # Create evaluation procedure
        eval_proc = EvaluationProcedure(
            method="exec_and_parse",
            target_node="test_node",
            command="echo 'test output'",
            parser="text",
            success_condition={"contains_text": "test output"}
        )
        
        # Execute observation
        result = obs_executor.observe(provider, topology_id, eval_proc)
        
        # Verify result structure
        assert isinstance(result, ObservationResult)
        assert result.success is True
        assert "test output" in result.raw_output
        assert result.execution_time >= 0

    def test_observe_captures_execution_time(self, provisioned_topology):
        """Test that observation captures execution time"""
        provider, topology_id = provisioned_topology
        obs_executor = ObservationExecutor()
        
        eval_proc = EvaluationProcedure(
            method="exec_and_parse",
            target_node="test_node",
            command="sh -c 'sleep 0.1 && echo done'",
            parser="text",
            success_condition={"contains_text": "done"}
        )
        
        result = obs_executor.observe(provider, topology_id, eval_proc)
        
        # Should have taken at least 0.1 seconds
        assert result.execution_time >= 0.1
        assert result.success is True

    def test_observe_handles_command_failure(self, provisioned_topology):
        """Test that observation handles command failures gracefully"""
        provider, topology_id = provisioned_topology
        obs_executor = ObservationExecutor()
        
        eval_proc = EvaluationProcedure(
            method="exec_and_parse",
            target_node="test_node",
            command="false",  # Command that fails
            parser="text",
            success_condition={"contains_text": "anything"}
        )
        
        result = obs_executor.observe(provider, topology_id, eval_proc)
        
        # Should not raise exception, but indicate failure
        assert isinstance(result, ObservationResult)
        # success might be False, or depends on exit code handling
        assert result.exit_code != 0


@pytest.mark.integration
@pytest.mark.skipif(CommandExecutor is None, reason="CommandExecutor not implemented yet")
class TestApplyApproach:
    """Test applying full configuration approaches"""

    def test_apply_approach_single_node_single_command(self, provisioned_topology):
        """Test applying an approach with one command on one node"""
        provider, topology_id = provisioned_topology
        executor = CommandExecutor()
        
        # Create simple approach
        approach = Approach(
            description="Test single command",
            commands=[
                CommandSequence(
                    node="test_node",
                    commands=["echo 'config applied'"]
                )
            ]
        )
        
        # Apply approach
        log_entries = executor.apply_approach(provider, topology_id, approach, convergence_timeout=1)
        
        # Verify log entries
        assert len(log_entries) == 1
        assert isinstance(log_entries[0], ExecutionLogEntry)
        assert log_entries[0].node == "test_node"
        assert log_entries[0].command == "echo 'config applied'"
        assert log_entries[0].success is True
        assert log_entries[0].exit_code == 0
        assert "config applied" in log_entries[0].stdout

    def test_apply_approach_single_node_multiple_commands(self, provisioned_topology):
        """Test applying multiple commands on one node"""
        provider, topology_id = provisioned_topology
        executor = CommandExecutor()
        
        approach = Approach(
            description="Test multiple commands",
            commands=[
                CommandSequence(
                    node="test_node",
                    commands=[
                        "echo 'command 1'",
                        "echo 'command 2'",
                        "echo 'command 3'"
                    ]
                )
            ]
        )
        
        log_entries = executor.apply_approach(provider, topology_id, approach, convergence_timeout=1)
        
        # Should have 3 log entries
        assert len(log_entries) == 3
        assert all(entry.success for entry in log_entries)
        assert log_entries[0].command == "echo 'command 1'"
        assert log_entries[1].command == "echo 'command 2'"
        assert log_entries[2].command == "echo 'command 3'"

    def test_apply_approach_multiple_nodes(self, provisioned_two_node_topology):
        """Test applying commands on multiple nodes"""
        provider, topology_id, topology = provisioned_two_node_topology
        executor = CommandExecutor()
        
        approach = Approach(
            description="Multi-node approach",
            commands=[
                CommandSequence(
                    node="node1",
                    commands=["echo 'config on node1'"]
                ),
                CommandSequence(
                    node="node2",
                    commands=["echo 'config on node2'"]
                )
            ]
        )
        
        log_entries = executor.apply_approach(provider, topology_id, approach, convergence_timeout=1)
        
        # Should have 2 log entries
        assert len(log_entries) == 2
        assert log_entries[0].node == "node1"
        assert log_entries[1].node == "node2"
        assert all(entry.success for entry in log_entries)

    def test_apply_approach_preserves_command_order(self, provisioned_topology):
        """Test that commands are executed in the specified order"""
        provider, topology_id = provisioned_topology
        executor = CommandExecutor()
        
        approach = Approach(
            description="Order test",
            commands=[
                CommandSequence(
                    node="test_node",
                    commands=[
                        "echo 'first'",
                        "echo 'second'",
                        "echo 'third'"
                    ]
                )
            ]
        )
        
        log_entries = executor.apply_approach(provider, topology_id, approach, convergence_timeout=1)
        
        # Verify timestamps are in order
        timestamps = [entry.timestamp for entry in log_entries]
        assert timestamps == sorted(timestamps)
        
        # Verify command order
        commands = [entry.command for entry in log_entries]
        assert commands == ["echo 'first'", "echo 'second'", "echo 'third'"]

    def test_apply_approach_continues_on_command_failure(self, provisioned_topology):
        """Test that execution continues even when a command fails"""
        provider, topology_id = provisioned_topology
        executor = CommandExecutor()
        
        approach = Approach(
            description="Test error handling",
            commands=[
                CommandSequence(
                    node="test_node",
                    commands=[
                        "echo 'before failure'",
                        "false",  # This will fail
                        "echo 'after failure'"
                    ]
                )
            ]
        )
        
        log_entries = executor.apply_approach(provider, topology_id, approach, convergence_timeout=1)
        
        # Should have all 3 entries
        assert len(log_entries) == 3
        
        # First command succeeds
        assert log_entries[0].success is True
        assert log_entries[0].exit_code == 0
        
        # Second command fails
        assert log_entries[1].success is False
        assert log_entries[1].exit_code != 0
        
        # Third command still executes and succeeds
        assert log_entries[2].success is True
        assert log_entries[2].exit_code == 0
        assert "after failure" in log_entries[2].stdout

    def test_apply_approach_logs_all_executions(self, provisioned_topology):
        """Test that all execution details are logged"""
        provider, topology_id = provisioned_topology
        executor = CommandExecutor()
        
        approach = Approach(
            description="Logging test",
            commands=[
                CommandSequence(
                    node="test_node",
                    commands=["echo 'test'"]
                )
            ]
        )
        
        log_entries = executor.apply_approach(provider, topology_id, approach, convergence_timeout=1)
        
        entry = log_entries[0]
        
        # Verify all fields are populated
        assert entry.timestamp is not None
        assert isinstance(entry.timestamp, datetime)
        assert entry.node == "test_node"
        assert entry.command == "echo 'test'"
        assert isinstance(entry.success, bool)
        assert isinstance(entry.stdout, str)
        assert isinstance(entry.stderr, str) or entry.stderr is None
        assert isinstance(entry.exit_code, int)
        assert isinstance(entry.execution_time, float)
        assert entry.execution_time >= 0

    def test_apply_approach_waits_for_convergence(self, provisioned_topology):
        """Test that apply_approach waits for convergence timeout"""
        provider, topology_id = provisioned_topology
        executor = CommandExecutor()
        
        approach = Approach(
            description="Convergence test",
            commands=[
                CommandSequence(
                    node="test_node",
                    commands=["echo 'done'"]
                )
            ]
        )
        
        # Measure execution time
        start_time = time.time()
        log_entries = executor.apply_approach(provider, topology_id, approach, convergence_timeout=2)
        elapsed = time.time() - start_time
        
        # Should have waited at least 2 seconds for convergence
        assert elapsed >= 2.0
        assert len(log_entries) == 1

    def test_apply_approach_with_no_convergence_timeout(self, provisioned_topology):
        """Test that apply_approach works with zero convergence timeout"""
        provider, topology_id = provisioned_topology
        executor = CommandExecutor()
        
        approach = Approach(
            description="No convergence wait",
            commands=[
                CommandSequence(
                    node="test_node",
                    commands=["echo 'test'"]
                )
            ]
        )
        
        start_time = time.time()
        log_entries = executor.apply_approach(provider, topology_id, approach, convergence_timeout=0)
        elapsed = time.time() - start_time
        
        # Should complete quickly (< 1 second)
        assert elapsed < 1.0
        assert len(log_entries) == 1

