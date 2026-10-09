"""
Interactive human shell for multi-turn benchmark sessions.

Provides a local REPL that drives InteractiveSession directly (no MCP).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from benchmark.models.results import BenchmarkResult
from benchmark.models.task import TaskDefinition
from benchmark.presenter import TaskPresenter
from benchmark.repl_input import create_repl_input_fn
from benchmark.session.models import CommandType, SubmitResult
from benchmark.session.session import InteractiveSession


class CommandKind(str, Enum):
    EXEC = "exec"
    SHOW_TOP = "show_top"
    STATUS = "status"
    NODES = "nodes"
    SUBMIT = "submit"
    HELP = "help"
    QUIT = "quit"
    ERROR = "error"


@dataclass
class ParsedCommand:
    kind: CommandKind
    node: Optional[str] = None
    command: Optional[str] = None
    command_type: Optional[CommandType] = None
    error: Optional[str] = None


_CONFIG_PATTERN = re.compile(r"^(\S+)\s+-\s+(.+)$")
_READ_PATTERN = re.compile(r"^(\S+)\s+\?\s+(.+)$")


def parse_command(line: str) -> ParsedCommand:
    """Parse a single REPL input line into a structured command."""
    stripped = line.strip()
    if not stripped:
        return ParsedCommand(
            kind=CommandKind.ERROR,
            error="Empty input. Type 'help' for available commands.",
        )

    lower = stripped.lower()
    if lower in ("show top",):
        return ParsedCommand(kind=CommandKind.SHOW_TOP)
    if lower == "status":
        return ParsedCommand(kind=CommandKind.STATUS)
    if lower == "nodes":
        return ParsedCommand(kind=CommandKind.NODES)
    if lower == "submit":
        return ParsedCommand(kind=CommandKind.SUBMIT)
    if lower == "help":
        return ParsedCommand(kind=CommandKind.HELP)
    if lower in ("quit", "exit"):
        return ParsedCommand(kind=CommandKind.QUIT)

    read_match = _READ_PATTERN.match(stripped)
    if read_match:
        return ParsedCommand(
            kind=CommandKind.EXEC,
            node=read_match.group(1),
            command=read_match.group(2).strip(),
            command_type=CommandType.READ,
        )

    config_match = _CONFIG_PATTERN.match(stripped)
    if config_match:
        return ParsedCommand(
            kind=CommandKind.EXEC,
            node=config_match.group(1),
            command=config_match.group(2).strip(),
            command_type=CommandType.CONFIG,
        )

    return ParsedCommand(
        kind=CommandKind.ERROR,
        error=(
            "Unrecognized command. Use 'NODE - command' (config) or "
            "'NODE ? command' (read). Type 'help' for more."
        ),
    )


HELP_TEXT = """\
Commands:
  NODE - command     Run a config command (counts as a turn)
  NODE ? command     Run a read/verify command (free)
  show top           Show topology and task description
  nodes              List available nodes
  status             Show turns and time remaining
  submit             Finish and evaluate your solution
  help               Show this help
  quit / exit        Abort without saving (confirmation required)

Use Up/Down arrows for command history (when readline is available).
"""


class HumanShell:
    """Local REPL for human multi-turn benchmark participation."""

    def __init__(
        self,
        session: InteractiveSession,
        task: TaskDefinition,
        console: Optional[Console] = None,
        input_fn: Optional[Callable[[str], str]] = None,
        confirm_fn: Optional[Callable[[str], bool]] = None,
    ):
        self.session = session
        self.task = task
        self.console = console or Console()
        self.input_fn = input_fn or create_repl_input_fn("netagentbench")
        self.confirm_fn = confirm_fn or self._default_confirm

    def _default_confirm(self, message: str) -> bool:
        answer = self.input_fn(f"{message} [y/N]: ").strip().lower()
        return answer in ("y", "yes")

    def run(self) -> Optional[SubmitResult]:
        """Run the interactive shell until submit or quit."""
        self._print_banner()
        self.console.print(
            "[dim]Type 'help' for commands. Use 'submit' when done.[/dim]\n"
        )

        while True:
            try:
                line = self.input_fn("> ")
            except (EOFError, KeyboardInterrupt):
                self.console.print("\n[yellow]Interrupted.[/yellow]")
                if self.confirm_fn("Quit without submitting?"):
                    return None
                continue

            parsed = parse_command(line)
            if parsed.kind == CommandKind.ERROR:
                self.console.print(f"[red]{parsed.error}[/red]")
                continue

            if parsed.kind == CommandKind.HELP:
                self.console.print(HELP_TEXT)
                continue

            if parsed.kind == CommandKind.SHOW_TOP:
                self._show_topology()
                continue

            if parsed.kind == CommandKind.NODES:
                self._show_nodes()
                continue

            if parsed.kind == CommandKind.STATUS:
                self._show_status()
                continue

            if parsed.kind == CommandKind.QUIT:
                if self.confirm_fn("Quit without submitting?"):
                    return None
                continue

            if parsed.kind == CommandKind.SUBMIT:
                return self.session.submit()

            if parsed.kind == CommandKind.EXEC:
                self._exec(parsed)
                continue

        return None

    def _print_banner(self) -> None:
        self.console.print(
            Panel(
                f"[bold]{self.task.task_id}[/bold]\n\n{self.task.description}",
                title="Task",
                border_style="blue",
            )
        )

    def _show_topology(self) -> None:
        presenter = TaskPresenter()
        text = presenter.present_task_text(self.task)
        self.console.print(text)

    def _show_nodes(self) -> None:
        nodes = self.session._context.nodes if self.session._context else []
        self.console.print("Nodes: " + ", ".join(nodes))

    def _show_status(self) -> None:
        status = self.session.get_session_status()
        table = Table(title="Session Status")
        table.add_column("Metric")
        table.add_column("Value")
        table.add_row("Active", str(status.is_active))
        table.add_row("Turns used", str(status.turns_used))
        table.add_row("Turns remaining", str(status.turns_remaining))
        table.add_row("Time elapsed (s)", f"{status.time_elapsed:.1f}")
        table.add_row("Time remaining (s)", f"{status.time_remaining:.1f}")
        self.console.print(table)

    def _exec(self, parsed: ParsedCommand) -> None:
        assert parsed.node is not None
        assert parsed.command is not None
        assert parsed.command_type is not None

        nodes = self.session._context.nodes if self.session._context else []
        if parsed.node not in nodes:
            self.console.print(
                f"[red]Unknown node '{parsed.node}'. Available: {', '.join(nodes)}[/red]"
            )
            return

        try:
            result = self.session.exec_command(
                parsed.node, parsed.command, parsed.command_type
            )
        except Exception as exc:
            self.console.print(f"[red]Error: {exc}[/red]")
            return

        label = "config" if parsed.command_type == CommandType.CONFIG else "read"
        if result.success:
            self.console.print(f"[green]✓[/green] {label} OK")
        else:
            self.console.print(f"[red]✗[/red] {label} failed (exit {result.exit_code})")

        if result.stdout:
            self.console.print(result.stdout.rstrip())
        if result.stderr:
            self.console.print(f"[red]{result.stderr.rstrip()}[/red]")
        if result.error_message:
            self.console.print(f"[red]{result.error_message}[/red]")


def render_results(result: BenchmarkResult, console: Optional[Console] = None) -> None:
    """Render benchmark results for human interactive mode."""
    out = console or Console()
    out.print("\n[bold]Evaluation Results[/bold]")

    table = Table(title="Properties")
    table.add_column("Property")
    table.add_column("Result")
    for prop in result.property_results:
        status = "[green]PASS[/green]" if prop.satisfied else "[red]FAIL[/red]"
        table.add_row(prop.property_id, status)
    out.print(table)

    out.print(f"\n[bold]Final Score:[/bold] {result.scoring.final_score:.3f}")
    out.print(f"  Completeness:       {result.scoring.completeness:.3f}")
    out.print(f"  Robustness:         {result.scoring.robustness:.3f}")
    out.print(f"  Syntactic validity: {result.scoring.syntactic_validity:.3f}")
    if result.scoring.efficiency is not None:
        out.print(f"  Efficiency:         {result.scoring.efficiency:.3f}")
    out.print(f"  Turns used:         {result.metrics.turns_to_complete}")
    out.print(f"  Success:            {result.success}")
    out.print(f"  Run ID:             {result.run_id}")
