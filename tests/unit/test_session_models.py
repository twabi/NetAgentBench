"""
Unit tests for session data models.

Tests the enums and dataclasses in benchmark.session.models.
"""

import pytest
from datetime import datetime


class TestCommandTypeEnum:
    """Test CommandType enum."""

    def test_command_type_config_value(self):
        """Test CONFIG command type has correct value."""
        from benchmark.session.models import CommandType

        assert CommandType.CONFIG == "config"
        assert CommandType.CONFIG.value == "config"

    def test_command_type_read_value(self):
        """Test READ command type has correct value."""
        from benchmark.session.models import CommandType

        assert CommandType.READ == "read"
        assert CommandType.READ.value == "read"

    def test_command_type_is_string_enum(self):
        """Test CommandType is a string enum for JSON serialization."""
        from benchmark.session.models import CommandType

        # String enum allows direct string comparison
        assert CommandType.CONFIG == "config"
        assert CommandType.READ == "read"


class TestConvergenceStatusEnum:
    """Test ConvergenceStatus enum."""

    def test_convergence_status_converged(self):
        """Test CONVERGED status has correct value."""
        from benchmark.session.models import ConvergenceStatus

        assert ConvergenceStatus.CONVERGED == "converged"
        assert ConvergenceStatus.CONVERGED.value == "converged"

    def test_convergence_status_timeout(self):
        """Test TIMEOUT status has correct value."""
        from benchmark.session.models import ConvergenceStatus

        assert ConvergenceStatus.TIMEOUT == "timeout"
        assert ConvergenceStatus.TIMEOUT.value == "timeout"

    def test_convergence_status_error(self):
        """Test ERROR status has correct value."""
        from benchmark.session.models import ConvergenceStatus

        assert ConvergenceStatus.ERROR == "error"
        assert ConvergenceStatus.ERROR.value == "error"


class TestSessionContext:
    """Test SessionContext dataclass."""

    def test_session_context_creation(self):
        """Test basic SessionContext creation."""
        from benchmark.session.models import SessionContext

        start = datetime.now()
        ctx = SessionContext(
            session_id="test_session_001",
            task_id="task_001",
            nodes=["R1", "R2", "R3"],
            topology_id="topo_001",
            turn_limit=50,
            time_limit=600.0,
            start_time=start,
        )

        assert ctx.session_id == "test_session_001"
        assert ctx.task_id == "task_001"
        assert ctx.nodes == ["R1", "R2", "R3"]
        assert ctx.topology_id == "topo_001"
        assert ctx.turn_limit == 50
        assert ctx.time_limit == 600.0
        assert ctx.start_time == start
        assert ctx.executed_commands == []

    def test_session_context_with_commands(self):
        """Test SessionContext with executed commands."""
        from benchmark.session.models import SessionContext, CommandType

        ctx = SessionContext(
            session_id="test_001",
            task_id="task_001",
            nodes=["R1"],
            topology_id="topo_001",
            turn_limit=50,
            time_limit=600.0,
            start_time=datetime.now(),
            executed_commands=[
                ("R1", "vtysh -c 'conf t'", CommandType.CONFIG),
                ("R1", "show version", CommandType.READ),
            ],
        )

        assert len(ctx.executed_commands) == 2
        assert ctx.executed_commands[0] == ("R1", "vtysh -c 'conf t'", CommandType.CONFIG)
        assert ctx.executed_commands[1] == ("R1", "show version", CommandType.READ)

    def test_session_context_get_approach_config_only(self):
        """Test get_approach returns only CONFIG commands."""
        from benchmark.session.models import SessionContext, CommandType

        ctx = SessionContext(
            session_id="test_001",
            task_id="task_001",
            nodes=["R1", "R2"],
            topology_id="topo_001",
            turn_limit=50,
            time_limit=600.0,
            start_time=datetime.now(),
            executed_commands=[
                ("R1", "config1", CommandType.CONFIG),
                ("R1", "show ip route", CommandType.READ),
                ("R2", "config2", CommandType.CONFIG),
                ("R2", "show status", CommandType.READ),
                ("R1", "config3", CommandType.CONFIG),
            ],
        )

        approach = ctx.get_approach()

        # Should only include CONFIG commands
        assert len(approach) == 3
        assert approach[0] == ("R1", "config1")
        assert approach[1] == ("R2", "config2")
        assert approach[2] == ("R1", "config3")

    def test_session_context_get_approach_empty(self):
        """Test get_approach with no commands."""
        from benchmark.session.models import SessionContext

        ctx = SessionContext(
            session_id="test_001",
            task_id="task_001",
            nodes=["R1"],
            topology_id="topo_001",
            turn_limit=50,
            time_limit=600.0,
            start_time=datetime.now(),
        )

        assert ctx.get_approach() == []


class TestExecResult:
    """Test ExecResult dataclass."""

    def test_exec_result_success(self):
        """Test ExecResult for successful command."""
        from benchmark.session.models import ExecResult, CommandType, ConvergenceStatus

        result = ExecResult(
            success=True,
            stdout="command output",
            stderr="",
            exit_code=0,
            command_type=CommandType.CONFIG,
            convergence_status=ConvergenceStatus.CONVERGED,
            convergence_time=1.5,
            execution_time=0.5,
        )

        assert result.success is True
        assert result.stdout == "command output"
        assert result.stderr == ""
        assert result.exit_code == 0
        assert result.command_type == CommandType.CONFIG
        assert result.convergence_status == ConvergenceStatus.CONVERGED
        assert result.convergence_time == 1.5
        assert result.execution_time == 0.5
        assert result.error_message == ""

    def test_exec_result_failure(self):
        """Test ExecResult for failed command."""
        from benchmark.session.models import ExecResult, CommandType, ConvergenceStatus

        result = ExecResult(
            success=False,
            stdout="",
            stderr="command not found",
            exit_code=127,
            command_type=CommandType.CONFIG,
            convergence_status=ConvergenceStatus.ERROR,
            convergence_time=0.0,
            execution_time=0.1,
            error_message="Command failed",
        )

        assert result.success is False
        assert result.exit_code == 127
        assert result.stderr == "command not found"
        assert result.error_message == "Command failed"

    def test_exec_result_timeout(self):
        """Test ExecResult for timeout."""
        from benchmark.session.models import ExecResult, CommandType, ConvergenceStatus

        result = ExecResult(
            success=False,
            stdout="",
            stderr="",
            exit_code=-1,
            command_type=CommandType.CONFIG,
            convergence_status=ConvergenceStatus.TIMEOUT,
            convergence_time=30.0,
            execution_time=30.0,
            error_message="Command timed out",
        )

        assert result.success is False
        assert result.convergence_status == ConvergenceStatus.TIMEOUT

    def test_exec_result_read_command(self):
        """Test ExecResult for READ command type."""
        from benchmark.session.models import ExecResult, CommandType, ConvergenceStatus

        result = ExecResult(
            success=True,
            stdout="router status: running",
            stderr="",
            exit_code=0,
            command_type=CommandType.READ,
            convergence_status=ConvergenceStatus.CONVERGED,
            convergence_time=0.0,
            execution_time=0.2,
        )

        assert result.command_type == CommandType.READ
        assert result.convergence_time == 0.0  # No convergence wait for READ


class TestSessionStatus:
    """Test SessionStatus dataclass."""

    def test_session_status_active(self):
        """Test SessionStatus for active session."""
        from benchmark.session.models import SessionStatus

        status = SessionStatus(
            is_active=True,
            turns_used=5,
            turns_remaining=45,
            time_elapsed=120.0,
            time_remaining=480.0,
        )

        assert status.is_active is True
        assert status.turns_used == 5
        assert status.turns_remaining == 45
        assert status.time_elapsed == 120.0
        assert status.time_remaining == 480.0

    def test_session_status_inactive(self):
        """Test SessionStatus for inactive session."""
        from benchmark.session.models import SessionStatus

        status = SessionStatus(
            is_active=False,
            turns_used=50,
            turns_remaining=0,
            time_elapsed=600.0,
            time_remaining=0.0,
        )

        assert status.is_active is False
        assert status.turns_used == 50
        assert status.turns_remaining == 0


class TestSubmitResult:
    """Test SubmitResult dataclass."""

    def test_submit_result_success(self):
        """Test SubmitResult for successful submission."""
        from benchmark.session.models import SubmitResult

        result = SubmitResult(
            session_id="session_001",
            completed=True,
            total_turns=25,
            total_time=300.5,
            approach=[("R1", "config1"), ("R2", "config2")],
            termination_reason="submitted",
        )

        assert result.session_id == "session_001"
        assert result.completed is True
        assert result.total_turns == 25
        assert result.total_time == 300.5
        assert len(result.approach) == 2
        assert result.termination_reason == "submitted"

    def test_submit_result_turn_limit(self):
        """Test SubmitResult with turn limit termination."""
        from benchmark.session.models import SubmitResult

        result = SubmitResult(
            session_id="session_002",
            completed=True,
            total_turns=50,
            total_time=450.0,
            approach=[("R1", f"cmd{i}") for i in range(50)],
            termination_reason="turn_limit",
        )

        assert result.termination_reason == "turn_limit"
        assert result.total_turns == 50

    def test_submit_result_time_limit(self):
        """Test SubmitResult with time limit termination."""
        from benchmark.session.models import SubmitResult

        result = SubmitResult(
            session_id="session_003",
            completed=True,
            total_turns=30,
            total_time=600.0,
            approach=[],
            termination_reason="time_limit",
        )

        assert result.termination_reason == "time_limit"

    def test_submit_result_empty_approach(self):
        """Test SubmitResult with empty approach."""
        from benchmark.session.models import SubmitResult

        result = SubmitResult(
            session_id="session_004",
            completed=True,
            total_turns=0,
            total_time=10.0,
            approach=[],
        )

        assert result.approach == []
        assert result.total_turns == 0
        assert result.termination_reason == ""
