"""
Unit tests for Executor components.

These tests use mocked Docker client for fast execution.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
import time

from benchmark.models.task import EvaluationProcedure
from benchmark.models.submission import CommandSequence, Approach

# Import executors (will fail until implemented)
try:
    from benchmark.executor.command import CommandExecutor, ExecutionLogEntry
    from benchmark.executor.observation import ObservationExecutor, ObservationResult
except ImportError:
    CommandExecutor = None
    ObservationExecutor = None
    ExecutionLogEntry = None
    ObservationResult = None


@pytest.mark.skipif(CommandExecutor is None, reason="CommandExecutor not implemented yet")
class TestCommandExecutorUnit:
    """Unit tests for CommandExecutor with mocked Docker"""

    def test_exec_on_node_success_with_mock(self):
        """Test successful command execution with mocked Docker"""
        executor = CommandExecutor()
        
        # Mock Docker client and container
        mock_container = Mock()
        mock_container.exec_run.return_value = (0, b"test output")
        
        with patch('docker.from_env') as mock_docker:
            mock_client = Mock()
            mock_client.containers.get.return_value = mock_container
            mock_docker.return_value = mock_client
            
            stdout, stderr, exit_code = executor.exec_on_node("test_container", "echo test")
            
            # Verify Docker was called correctly
            mock_client.containers.get.assert_called_once_with("test_container")
            mock_container.exec_run.assert_called_once()
            
            # Verify results
            assert exit_code == 0
            assert "test output" in stdout

    def test_exec_on_node_returns_stdout(self):
        """Test that stdout is returned correctly"""
        executor = CommandExecutor()
        
        mock_container = Mock()
        mock_container.exec_run.return_value = (0, b"expected output")
        
        with patch('docker.from_env') as mock_docker:
            mock_client = Mock()
            mock_client.containers.get.return_value = mock_container
            mock_docker.return_value = mock_client
            
            stdout, stderr, exit_code = executor.exec_on_node("test_container", "test_cmd")
            
            assert "expected output" in stdout
            assert exit_code == 0

    def test_exec_on_node_captures_stderr_separately(self):
        """Test stderr capture (when supported by Docker)"""
        executor = CommandExecutor()
        
        mock_container = Mock()
        # Docker exec_run can return output and stderr separately in some cases
        mock_container.exec_run.return_value = (0, b"stdout content")
        
        with patch('docker.from_env') as mock_docker:
            mock_client = Mock()
            mock_client.containers.get.return_value = mock_container
            mock_docker.return_value = mock_client
            
            stdout, stderr, exit_code = executor.exec_on_node("test_container", "test_cmd")
            
            # Should capture stdout
            assert isinstance(stdout, str)
            assert isinstance(stderr, str)

    def test_exec_on_node_handles_docker_errors(self):
        """Test that Docker errors are handled appropriately"""
        executor = CommandExecutor()
        
        with patch('docker.from_env') as mock_docker:
            mock_client = Mock()
            # Simulate container not found
            import docker.errors
            mock_client.containers.get.side_effect = docker.errors.NotFound("Container not found")
            mock_docker.return_value = mock_client
            
            # Should raise exception
            with pytest.raises(Exception):
                executor.exec_on_node("nonexistent_container", "test_cmd")

    def test_exec_on_node_handles_non_zero_exit_code(self):
        """Test handling of commands that fail"""
        executor = CommandExecutor()
        
        mock_container = Mock()
        mock_container.exec_run.return_value = (1, b"error message")
        
        with patch('docker.from_env') as mock_docker:
            mock_client = Mock()
            mock_client.containers.get.return_value = mock_container
            mock_docker.return_value = mock_client
            
            stdout, stderr, exit_code = executor.exec_on_node("test_container", "false")
            
            assert exit_code == 1

    def test_exec_on_node_respects_timeout(self):
        """Test that timeout raises TimeoutError"""
        executor = CommandExecutor()
        
        mock_container = Mock()
        # Simulate long running command
        def long_running(*args, **kwargs):
            time.sleep(0.2)
            return (0, b"output")
            
        mock_container.exec_run.side_effect = long_running
        
        with patch('docker.from_env') as mock_docker:
            mock_client = Mock()
            mock_client.containers.get.return_value = mock_container
            mock_docker.return_value = mock_client
            
            with pytest.raises(TimeoutError):
                executor.exec_on_node("test_container", "test_cmd", timeout=0.1)


@pytest.mark.skipif(CommandExecutor is None, reason="CommandExecutor not implemented yet")
class TestApplyApproachUnit:
    """Unit tests for apply_approach with mocked dependencies"""

    def test_apply_approach_calls_exec_for_each_command(self):
        """Test that each command results in an exec call"""
        executor = CommandExecutor()
        
        # Mock infrastructure
        mock_infrastructure = Mock()
        mock_infrastructure.get_node_container_name.return_value = "test_container"
        
        # Mock Docker
        mock_container = Mock()
        mock_container.exec_run.return_value = (0, b"success")
        
        with patch('docker.from_env') as mock_docker:
            mock_client = Mock()
            mock_client.containers.get.return_value = mock_container
            mock_docker.return_value = mock_client
            
            approach = Approach(
                commands=[
                    CommandSequence(
                        node="test_node",
                        commands=["cmd1", "cmd2", "cmd3"]
                    )
                ]
            )
            
            with patch('time.sleep'):  # Skip convergence wait in tests
                log_entries = executor.apply_approach(
                    mock_infrastructure,
                    "topology_123",
                    approach,
                    convergence_timeout=0
                )
            
            # Should have 3 log entries
            assert len(log_entries) == 3
            
            # Verify all commands were executed
            assert mock_container.exec_run.call_count == 3

    def test_apply_approach_returns_execution_log(self):
        """Test that apply_approach returns proper ExecutionLogEntry objects"""
        executor = CommandExecutor()
        
        mock_infrastructure = Mock()
        mock_infrastructure.get_node_container_name.return_value = "test_container"
        
        mock_container = Mock()
        mock_container.exec_run.return_value = (0, b"output")
        
        with patch('docker.from_env') as mock_docker:
            mock_client = Mock()
            mock_client.containers.get.return_value = mock_container
            mock_docker.return_value = mock_client
            
            approach = Approach(
                commands=[
                    CommandSequence(
                        node="test_node",
                        commands=["echo test"]
                    )
                ]
            )
            
            with patch('time.sleep'):
                log_entries = executor.apply_approach(
                    mock_infrastructure,
                    "topology_123",
                    approach,
                    convergence_timeout=0
                )
            
            assert len(log_entries) == 1
            entry = log_entries[0]
            
            # Verify ExecutionLogEntry structure
            assert isinstance(entry, ExecutionLogEntry)
            assert entry.node == "test_node"
            assert entry.command == "echo test"
            assert isinstance(entry.timestamp, datetime)
            assert isinstance(entry.success, bool)
            assert isinstance(entry.exit_code, int)
            assert isinstance(entry.execution_time, float)

    def test_apply_approach_continues_on_failure(self):
        """Test that execution continues even when commands fail"""
        executor = CommandExecutor()
        
        mock_infrastructure = Mock()
        mock_infrastructure.get_node_container_name.return_value = "test_container"
        
        mock_container = Mock()
        # First command succeeds, second fails, third succeeds
        mock_container.exec_run.side_effect = [
            (0, b"success 1"),
            (1, b"failed"),
            (0, b"success 2")
        ]
        
        with patch('docker.from_env') as mock_docker:
            mock_client = Mock()
            mock_client.containers.get.return_value = mock_container
            mock_docker.return_value = mock_client
            
            approach = Approach(
                commands=[
                    CommandSequence(
                        node="test_node",
                        commands=["cmd1", "cmd2", "cmd3"]
                    )
                ]
            )
            
            with patch('time.sleep'):
                log_entries = executor.apply_approach(
                    mock_infrastructure,
                    "topology_123",
                    approach,
                    convergence_timeout=0
                )
            
            # All 3 commands should have been executed
            assert len(log_entries) == 3
            assert log_entries[0].success is True
            assert log_entries[1].success is False
            assert log_entries[2].success is True

    def test_apply_approach_handles_multiple_nodes(self):
        """Test apply_approach with commands for multiple nodes"""
        executor = CommandExecutor()
        
        mock_infrastructure = Mock()
        mock_infrastructure.get_node_container_name.side_effect = lambda tid, node: f"container_{node}"
        
        mock_container = Mock()
        mock_container.exec_run.return_value = (0, b"output")
        
        with patch('docker.from_env') as mock_docker:
            mock_client = Mock()
            mock_client.containers.get.return_value = mock_container
            mock_docker.return_value = mock_client
            
            approach = Approach(
                commands=[
                    CommandSequence(node="node1", commands=["cmd1"]),
                    CommandSequence(node="node2", commands=["cmd2"]),
                ]
            )
            
            with patch('time.sleep'):
                log_entries = executor.apply_approach(
                    mock_infrastructure,
                    "topology_123",
                    approach,
                    convergence_timeout=0
                )
            
            assert len(log_entries) == 2
            assert log_entries[0].node == "node1"
            assert log_entries[1].node == "node2"

    def test_apply_approach_waits_for_convergence(self):
        """Test that convergence timeout is respected"""
        executor = CommandExecutor()
        
        mock_infrastructure = Mock()
        mock_infrastructure.get_node_container_name.return_value = "test_container"
        
        mock_container = Mock()
        mock_container.exec_run.return_value = (0, b"output")
        
        with patch('docker.from_env') as mock_docker:
            mock_client = Mock()
            mock_client.containers.get.return_value = mock_container
            mock_docker.return_value = mock_client
            
            approach = Approach(
                commands=[
                    CommandSequence(node="test_node", commands=["echo test"])
                ]
            )
            
            # Mock time.sleep to verify it's called
            with patch('time.sleep') as mock_sleep:
                executor.apply_approach(
                    mock_infrastructure,
                    "topology_123",
                    approach,
                    convergence_timeout=5
                )
                
                # Should have called sleep with convergence timeout
                mock_sleep.assert_called_once_with(5)


@pytest.mark.skipif(ObservationExecutor is None, reason="ObservationExecutor not implemented yet")
class TestObservationExecutorUnit:
    """Unit tests for ObservationExecutor with mocked dependencies"""

    def test_observe_calls_command_executor(self):
        """Test that observe uses CommandExecutor"""
        mock_infrastructure = Mock()
        mock_infrastructure.get_node_container_name.return_value = "test_container"
        
        eval_proc = EvaluationProcedure(
            method="exec_and_parse",
            target_node="test_node",
            command="show status",
            parser="json",
            success_condition={}
        )
        
        # Mock CommandExecutor before creating ObservationExecutor
        with patch('benchmark.executor.observation.CommandExecutor') as mock_cmd_executor_class:
            mock_cmd_executor = Mock()
            mock_cmd_executor.exec_on_node.return_value = ("output", "", 0)
            mock_cmd_executor_class.return_value = mock_cmd_executor
            
            obs_executor = ObservationExecutor()
            result = obs_executor.observe(mock_infrastructure, "topology_123", eval_proc)
            
            # Verify CommandExecutor was used
            mock_cmd_executor.exec_on_node.assert_called_once()

    def test_observe_measures_execution_time(self):
        """Test that observe measures execution time"""
        mock_infrastructure = Mock()
        mock_infrastructure.get_node_container_name.return_value = "test_container"
        
        eval_proc = EvaluationProcedure(
            method="exec_and_parse",
            target_node="test_node",
            command="test_cmd",
            parser="text",
            success_condition={}
        )
        
        with patch('benchmark.executor.observation.CommandExecutor') as mock_cmd_executor_class:
            mock_cmd_executor = Mock()
            mock_cmd_executor.exec_on_node.return_value = ("output", "", 0)
            mock_cmd_executor_class.return_value = mock_cmd_executor
            
            obs_executor = ObservationExecutor()
            result = obs_executor.observe(mock_infrastructure, "topology_123", eval_proc)
            
            # Should have measured execution time
            assert isinstance(result.execution_time, float)
            assert result.execution_time >= 0

    def test_observe_returns_observation_result(self):
        """Test that observe returns proper ObservationResult"""
        mock_infrastructure = Mock()
        mock_infrastructure.get_node_container_name.return_value = "test_container"
        
        eval_proc = EvaluationProcedure(
            method="exec_and_parse",
            target_node="test_node",
            command="test_cmd",
            parser="text",
            success_condition={}
        )
        
        with patch('benchmark.executor.observation.CommandExecutor') as mock_cmd_executor_class:
            mock_cmd_executor = Mock()
            mock_cmd_executor.exec_on_node.return_value = ("test output", "test stderr", 0)
            mock_cmd_executor_class.return_value = mock_cmd_executor
            
            obs_executor = ObservationExecutor()
            result = obs_executor.observe(mock_infrastructure, "topology_123", eval_proc)
            
            # Verify ObservationResult structure
            assert isinstance(result, ObservationResult)
            assert result.raw_output == "test output"
            assert result.stderr == "test stderr"
            assert result.exit_code == 0
            assert result.success is True
            assert result.error is None

    def test_observe_handles_failures(self):
        """Test that observe handles command failures gracefully"""
        mock_infrastructure = Mock()
        mock_infrastructure.get_node_container_name.return_value = "test_container"
        
        eval_proc = EvaluationProcedure(
            method="exec_and_parse",
            target_node="test_node",
            command="failing_cmd",
            parser="text",
            success_condition={}
        )
        
        with patch('benchmark.executor.observation.CommandExecutor') as mock_cmd_executor_class:
            mock_cmd_executor = Mock()
            # Command fails with non-zero exit code
            mock_cmd_executor.exec_on_node.return_value = ("", "error message", 1)
            mock_cmd_executor_class.return_value = mock_cmd_executor
            
            obs_executor = ObservationExecutor()
            result = obs_executor.observe(mock_infrastructure, "topology_123", eval_proc)
            
            # Should return result, not raise exception
            assert isinstance(result, ObservationResult)
            assert result.success is False
            assert result.exit_code == 1

    def test_observe_handles_exceptions(self):
        """Test that observe handles exceptions during execution"""
        mock_infrastructure = Mock()
        mock_infrastructure.get_node_container_name.return_value = "test_container"
        
        eval_proc = EvaluationProcedure(
            method="exec_and_parse",
            target_node="test_node",
            command="test_cmd",
            parser="text",
            success_condition={}
        )
        
        with patch('benchmark.executor.observation.CommandExecutor') as mock_cmd_executor_class:
            mock_cmd_executor = Mock()
            # Simulate exception during execution
            mock_cmd_executor.exec_on_node.side_effect = Exception("Docker error")
            mock_cmd_executor_class.return_value = mock_cmd_executor
            
            obs_executor = ObservationExecutor()
            result = obs_executor.observe(mock_infrastructure, "topology_123", eval_proc)
            
            # Should return result with error, not propagate exception
            assert isinstance(result, ObservationResult)
            assert result.success is False
            assert result.error is not None
            assert "Docker error" in result.error

