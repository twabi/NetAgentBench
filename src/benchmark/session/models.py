"""
Data models for interactive session management.

This module defines all models related to multi-turn benchmark sessions,
including command types, convergence tracking, and session state.

Based on the multi-turn extension to the FSM formalization.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Tuple


# ============================================================================
# Enumerations for Command and Convergence Types
# ============================================================================


class CommandType(str, Enum):
    """
    Type of command being executed in a session.

    Commands are classified into two categories per the formalization:
    - CONFIG (Σ_config): Configuration commands that modify network state
      and increment the turn counter
    - READ (Σ_read): State-preserving observation commands that do not
      increment the turn counter
    """

    CONFIG = "config"
    READ = "read"


class ConvergenceStatus(str, Enum):
    """
    Status of protocol convergence after command execution.

    After each configuration command, the network must converge to a
    stable state (ε-transition in the FSM formalization).
    """

    CONVERGED = "converged"  # Protocol converged within timeout
    TIMEOUT = "timeout"  # Protocol did not converge within timeout
    ERROR = "error"  # Error occurred during convergence check


# ============================================================================
# Session Context and State Models
# ============================================================================


@dataclass
class SessionContext:
    """
    Session metadata and configuration.

    Contains all information about an active benchmark session,
    including the topology, limits, and command history.
    """

    session_id: str
    task_id: str
    nodes: List[str]
    topology_id: str
    turn_limit: int
    time_limit: float  # seconds
    start_time: datetime
    # Command history: (node, command, command_type) for approach reconstruction
    executed_commands: List[Tuple[str, str, CommandType]] = field(default_factory=list)
    # Execution results: (node, command, success) for syntactic validity
    execution_results: List[Tuple[str, str, bool]] = field(default_factory=list)
    # Property-guidance experiment tracking
    property_check_count: int = 0
    property_trajectory: List[dict] = field(default_factory=list)
    log_property_snapshots: bool = False

    def get_approach(self) -> List[Tuple[str, str]]:
        """
        Reconstruct the configuration approach from command history.

        Returns only CONFIG commands (not READ commands) as the approach
        sequence A for robustness testing.

        Returns:
            List of (node, command) tuples for config commands only
        """
        return [
            (node, cmd)
            for node, cmd, cmd_type in self.executed_commands
            if cmd_type == CommandType.CONFIG
        ]


@dataclass
class ExecResult:
    """
    Result of executing a command on a node.

    Captures the outcome of command execution including output,
    convergence status, and timing information.
    """

    success: bool
    stdout: str
    stderr: str
    exit_code: int
    command_type: CommandType
    convergence_status: ConvergenceStatus
    convergence_time: float  # Time for protocol convergence (seconds)
    execution_time: float  # Time for command execution (seconds)
    error_message: str = ""


@dataclass
class SessionStatus:
    """
    Current status of an interactive session.

    Provides a snapshot of session state including turn and time usage.
    """

    is_active: bool
    turns_used: int
    turns_remaining: int
    time_elapsed: float  # seconds
    time_remaining: float  # seconds


@dataclass
class SubmitResult:
    """
    Result of submitting (completing) a session.

    Contains the final session outcome and the reconstructed approach
    for evaluation and robustness testing.
    """

    session_id: str
    completed: bool
    total_turns: int
    total_time: float  # seconds
    approach: List[Tuple[str, str]]  # Config commands only: (node, command)
    termination_reason: str = ""  # "submitted", "turn_limit", "time_limit"
