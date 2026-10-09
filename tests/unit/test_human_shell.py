"""
Unit tests for human interactive shell (parse_command and HumanShell dispatch).
"""

import io
from unittest.mock import Mock, patch

import pytest
from rich.console import Console

from benchmark.human_shell import (
    CommandKind,
    HumanShell,
    parse_command,
)
from benchmark.session.models import (
    CommandType,
    ConvergenceStatus,
    ExecResult,
    SessionStatus,
    SubmitResult,
)


class TestParseCommand:
    """Tests for parse_command()."""

    def test_config_command(self):
        parsed = parse_command("R1 - ip addr add 10.0.0.1/24 dev eth1")
        assert parsed.kind == CommandKind.EXEC
        assert parsed.node == "R1"
        assert parsed.command == "ip addr add 10.0.0.1/24 dev eth1"
        assert parsed.command_type == CommandType.CONFIG

    def test_read_command(self):
        parsed = parse_command("R1 ? show ip route")
        assert parsed.kind == CommandKind.EXEC
        assert parsed.node == "R1"
        assert parsed.command == "show ip route"
        assert parsed.command_type == CommandType.READ

    def test_special_commands_case_insensitive(self):
        for cmd in ("show top", "SHOW TOP", "Status", "NODES", "submit", "HELP", "QUIT", "exit"):
            parsed = parse_command(cmd)
            assert parsed.kind != CommandKind.ERROR
            assert parsed.error is None

    def test_show_top(self):
        assert parse_command("show top").kind == CommandKind.SHOW_TOP

    def test_status(self):
        assert parse_command("status").kind == CommandKind.STATUS

    def test_nodes(self):
        assert parse_command("nodes").kind == CommandKind.NODES

    def test_submit(self):
        assert parse_command("submit").kind == CommandKind.SUBMIT

    def test_help(self):
        assert parse_command("help").kind == CommandKind.HELP

    def test_quit(self):
        assert parse_command("quit").kind == CommandKind.QUIT

    def test_exit(self):
        assert parse_command("exit").kind == CommandKind.QUIT

    def test_extra_whitespace(self):
        parsed = parse_command("  R2   -   ip link set eth1 up  ")
        assert parsed.kind == CommandKind.EXEC
        assert parsed.node == "R2"
        assert parsed.command == "ip link set eth1 up"

    def test_empty_line_returns_error(self):
        parsed = parse_command("")
        assert parsed.kind == CommandKind.ERROR
        assert parsed.error is not None

    def test_missing_operator_returns_error(self):
        parsed = parse_command("R1 show ip route")
        assert parsed.kind == CommandKind.ERROR
        assert parsed.error is not None

    def test_missing_command_after_operator_returns_error(self):
        parsed = parse_command("R1 -")
        assert parsed.kind == CommandKind.ERROR
        assert parsed.error is not None


def _make_task():
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

    nodes = [
        Node(name="R1", type=NodeType.ROUTER),
        Node(name="R2", type=NodeType.ROUTER),
    ]
    topology = TopologySpecification(
        nodes=nodes,
        links=[{"endpoints": ["R1:eth1", "R2:eth1"]}],
        interfaces=[],
    )
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
            description="Test property",
            evaluation=eval_proc,
        )
    ]
    return TaskDefinition(
        task_id="test_001",
        description="Configure R1 and R2.\nIP plan: R1 eth1=10.0.0.1/24",
        platform=Platform.FRR,
        topology=topology,
        intent=IntentSpecification(properties=properties),
        convergence=ConvergenceConfig(timeout_seconds=5),
    )


def _exec_result(success: bool = True) -> ExecResult:
    return ExecResult(
        success=success,
        stdout="ok" if success else "",
        stderr="" if success else "failed",
        exit_code=0 if success else 1,
        command_type=CommandType.CONFIG,
        convergence_status=ConvergenceStatus.CONVERGED,
        convergence_time=0.0,
        execution_time=0.1,
    )


def _session_status() -> SessionStatus:
    return SessionStatus(
        is_active=True,
        turns_used=2,
        turns_remaining=98,
        time_elapsed=30.0,
        time_remaining=1770.0,
    )


class TestHumanShellDispatch:
    """Tests for HumanShell command dispatch."""

    @pytest.fixture
    def mock_session(self):
        session = Mock()
        session._context = Mock(nodes=["R1", "R2"])
        session.exec_command.return_value = _exec_result()
        session.get_session_status.return_value = _session_status()
        session.submit.return_value = SubmitResult(
            session_id="sess-1",
            completed=True,
            total_turns=3,
            total_time=45.0,
            approach=[("R1", "ip link set eth1 up")],
            termination_reason="submitted",
        )
        return session

    @pytest.fixture
    def task(self):
        return _make_task()

    def test_config_command_calls_exec_command(self, mock_session, task):
        prompts = iter(["R1 - ip link set eth1 up", "submit"])
        shell = HumanShell(
            mock_session,
            task,
            console=Console(file=io.StringIO(), force_terminal=False),
            input_fn=lambda _: next(prompts),
        )
        result = shell.run()
        mock_session.exec_command.assert_called_once_with(
            "R1", "ip link set eth1 up", CommandType.CONFIG
        )
        assert result is not None
        assert result.completed is True

    def test_read_command_uses_read_type(self, mock_session, task):
        prompts = iter(["R1 ? show ip route", "submit"])
        shell = HumanShell(
            mock_session,
            task,
            console=Console(file=io.StringIO(), force_terminal=False),
            input_fn=lambda _: next(prompts),
        )
        shell.run()
        mock_session.exec_command.assert_called_once_with(
            "R1", "show ip route", CommandType.READ
        )

    def test_read_command_does_not_crash_on_failure(self, mock_session, task):
        mock_session.exec_command.return_value = _exec_result(success=False)
        output = io.StringIO()
        prompts = iter(["R1 ? show ip route", "submit"])
        shell = HumanShell(
            mock_session,
            task,
            console=Console(file=output, force_terminal=False),
            input_fn=lambda _: next(prompts),
        )
        result = shell.run()
        assert result is not None
        assert "failed" in output.getvalue().lower() or "✗" in output.getvalue()

    def test_show_top_does_not_call_exec_command(self, mock_session, task):
        prompts = iter(["show top", "submit"])
        shell = HumanShell(
            mock_session,
            task,
            console=Console(file=io.StringIO(), force_terminal=False),
            input_fn=lambda _: next(prompts),
        )
        shell.run()
        mock_session.exec_command.assert_not_called()

    def test_status_renders_session_status(self, mock_session, task):
        output = io.StringIO()
        prompts = iter(["status", "submit"])
        shell = HumanShell(
            mock_session,
            task,
            console=Console(file=output, force_terminal=False),
            input_fn=lambda _: next(prompts),
        )
        shell.run()
        text = output.getvalue()
        assert "2" in text
        assert "98" in text

    def test_submit_calls_session_submit_once(self, mock_session, task):
        shell = HumanShell(
            mock_session,
            task,
            console=Console(file=io.StringIO(), force_terminal=False),
            input_fn=lambda _: "submit",
        )
        result = shell.run()
        mock_session.submit.assert_called_once()
        assert result.total_turns == 3

    def test_quit_confirmed_returns_none(self, mock_session, task):
        shell = HumanShell(
            mock_session,
            task,
            console=Console(file=io.StringIO(), force_terminal=False),
            input_fn=lambda _: "quit",
            confirm_fn=lambda _: True,
        )
        result = shell.run()
        assert result is None
        mock_session.submit.assert_not_called()

    def test_quit_not_confirmed_continues(self, mock_session, task):
        prompts = iter(["quit", "submit"])

        def confirm(_):
            return False

        shell = HumanShell(
            mock_session,
            task,
            console=Console(file=io.StringIO(), force_terminal=False),
            input_fn=lambda _: next(prompts),
            confirm_fn=confirm,
        )
        result = shell.run()
        assert result is not None
        mock_session.submit.assert_called_once()

    def test_invalid_syntax_shows_error_and_continues(self, mock_session, task):
        prompts = iter(["R1 show ip route", "submit"])
        output = io.StringIO()
        shell = HumanShell(
            mock_session,
            task,
            console=Console(file=output, force_terminal=False),
            input_fn=lambda _: next(prompts),
        )
        result = shell.run()
        assert result is not None
        assert "use" in output.getvalue().lower() or "format" in output.getvalue().lower()
