"""
Interactive session management for multi-turn benchmarks.

This module provides the InteractiveSession class for managing
multi-turn interactive benchmark sessions with turn and time limits.
"""

import logging
import time
import uuid
from datetime import datetime
from typing import List, Optional, Tuple

from benchmark.executor.command import CommandExecutor
from benchmark.infrastructure.base import InfrastructureProvider
from benchmark.infrastructure.containerlab import ContainerlabProvider
from benchmark.models.task import TaskDefinition, Property
from benchmark.evaluator.property import PropertyEvaluator
from benchmark.session.models import (
    CommandType,
    ConvergenceStatus,
    ExecResult,
    SessionContext,
    SessionStatus,
    SubmitResult,
)

# Setup logging
logger = logging.getLogger(__name__)

# Seconds to wait after vtysh first answers. Zebra can still reject config for a moment.
SHELL_SETTLE_SECONDS = 3


class SessionError(Exception):
    """Exception raised for session-related errors."""

    pass


class SessionNotActiveError(SessionError):
    """Exception raised when attempting operations on an inactive session."""

    pass


class TurnLimitExceededError(SessionError):
    """Exception raised when turn limit is exceeded."""

    pass


class TimeLimitExceededError(SessionError):
    """Exception raised when time limit is exceeded."""

    pass


class InteractiveSession:
    """
    Manages multi-turn interactive benchmark sessions.

    The InteractiveSession class handles the lifecycle of an interactive
    benchmark session, including:
    - Provisioning the network topology
    - Executing commands on nodes with turn/time tracking
    - Distinguishing between config and read commands
    - Tracking convergence status
    - Recording command history for approach reconstruction
    """

    def __init__(
        self,
        task: TaskDefinition,
        infrastructure: Optional[InfrastructureProvider] = None,
        turn_limit: int = 50,
        time_limit: float = 600.0,
        convergence_timeout: int = 30,
        log_property_snapshots: bool = False,
    ):
        """
        Initialize an interactive session.

        Args:
            task: The task definition for this benchmark
            infrastructure: Infrastructure provider (defaults to ContainerlabProvider)
            turn_limit: Maximum number of config commands allowed (default: 50)
            time_limit: Maximum session duration in seconds (default: 600)
            convergence_timeout: Timeout for protocol convergence in seconds (default: 30)
        """
        self.task = task
        self.infrastructure = infrastructure or ContainerlabProvider()
        self.turn_limit = turn_limit
        self.time_limit = time_limit
        self.convergence_timeout = convergence_timeout
        self.log_property_snapshots = log_property_snapshots

        # Session state
        self._context: Optional[SessionContext] = None
        self._is_active: bool = False
        self._turns_used: int = 0
        self._start_time: Optional[datetime] = None
        self._topology_id: Optional[str] = None

        # Command executor and evaluator
        self._executor = CommandExecutor()
        self._evaluator = PropertyEvaluator()

    @property
    def is_active(self) -> bool:
        """Check if the session is currently active."""
        if not self._is_active:
            return False
        # Check time limit
        if self._start_time and self._get_elapsed_time() >= self.time_limit:
            self._is_active = False
            logger.info(f"Session {self._context.session_id} timed out")
        return self._is_active

    def _get_elapsed_time(self) -> float:
        """Get elapsed time since session start in seconds."""
        if self._start_time is None:
            return 0.0
        return (datetime.now() - self._start_time).total_seconds()

    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        short_uuid = str(uuid.uuid4())[:8]
        return f"session_{timestamp}_{short_uuid}"

    def start(self) -> SessionContext:
        """
        Start the interactive session.

        Provisions the network topology and initializes the session state.

        Returns:
            SessionContext with session metadata

        Raises:
            SessionError: If session is already active or provisioning fails
        """
        if self._is_active:
            raise SessionError("Session is already active")

        logger.info(f"Starting interactive session for task {self.task.task_id}")

        # Provision topology
        try:
            self._topology_id = self.infrastructure.provision(self.task.topology)
            logger.info(f"Provisioned topology: {self._topology_id}")
        except Exception as e:
            logger.error(f"Failed to provision topology: {e}")
            raise SessionError(f"Failed to provision topology: {e}") from e

        # Wait for topology to be ready
        max_wait = 120  # 2 minutes
        wait_interval = 2
        total_wait = 0
        while not self.infrastructure.is_ready(self._topology_id):
            time.sleep(wait_interval)
            total_wait += wait_interval
            if total_wait >= max_wait:
                self.infrastructure.teardown(self._topology_id)
                raise SessionError("Topology failed to become ready within timeout")

        # Container "running" precedes zebra. Preconfiguration must not start until vtysh answers.
        self._wait_for_shell()

        # 1. Apply Pre-configuration
        self._apply_preconfiguration()

        # 2. Verify Fault State
        self._verify_fault_state()

        # Initialize session state
        self._start_time = datetime.now()
        self._is_active = True
        self._turns_used = 0

        # Get node names from topology
        nodes = [node.name for node in self.task.topology.nodes]

        # Create session context
        self._context = SessionContext(
            session_id=self._generate_session_id(),
            task_id=self.task.task_id,
            nodes=nodes,
            topology_id=self._topology_id,
            turn_limit=self.turn_limit,
            time_limit=self.time_limit,
            start_time=self._start_time,
            executed_commands=[],
            log_property_snapshots=self.log_property_snapshots,
        )

        logger.info(f"Session {self._context.session_id} started successfully")
        return self._context

    def _wait_for_shell(self, timeout: float = 90.0) -> None:
        """Block until vtysh answers on every node."""
        nodes = [node.name for node in self.task.topology.nodes]
        probe = "vtysh -c 'show ip route'"
        start = time.time()
        while time.time() - start < timeout:
            ready = True
            for node in nodes:
                container_name = self.infrastructure.get_node_container_name(
                    self._topology_id, node
                )
                try:
                    stdout, stderr, exit_code = self._executor.exec_on_node(
                        container_name, probe, timeout=self.convergence_timeout
                    )
                except Exception:
                    ready = False
                    break
                text = f"{stdout or ''}{stderr or ''}"
                if exit_code != 0 or "not running" in text.lower():
                    ready = False
                    break
            if ready:
                if SHELL_SETTLE_SECONDS:
                    time.sleep(SHELL_SETTLE_SECONDS)
                return
            time.sleep(2)
        self.infrastructure.teardown(self._topology_id)
        raise SessionError("vtysh not ready before pre-configuration")

    def _apply_preconfiguration(self):
        """Apply pre-configuration steps to the network."""
        if not self.task.preconfiguration:
            return

        logger.info(f"Applying pre-configuration for task {self.task.task_id}")
        for step in self.task.preconfiguration:
            container_name = self.infrastructure.get_node_container_name(
                self._topology_id, step.node
            )
            try:
                # Use executor directly to avoid turn tracking and convergence delays during setup
                stdout, stderr, exit_code = self._executor.exec_on_node(
                    container_name, step.command, timeout=self.convergence_timeout
                )
                text = f"{stdout or ''}{stderr or ''}"
                if exit_code != 0 and "not running" in text.lower():
                    self._wait_for_shell()
                    stdout, stderr, exit_code = self._executor.exec_on_node(
                        container_name, step.command, timeout=self.convergence_timeout
                    )
                if exit_code != 0:
                    raise SessionError(
                        f"Pre-configuration command failed on {step.node} (exit {exit_code}): "
                        f"{step.command}\n{stdout}{stderr}"
                    )
                else:
                    logger.info(f"Pre-configuration command succeeded on {step.node}")
                    logger.debug(f"Pre-config Output:\n{stdout}")
            except Exception as e:
                logger.error(f"Error applying pre-configuration step on {step.node}: {e}")
                raise SessionError(f"Pre-configuration failed: {e}") from e

    def _verify_fault_state(self):
        """Verify that the network is in the expected faulty state."""
        if not self.task.fault_verification:
            return

        logger.info(f"Verifying fault state for task {self.task.task_id}")
        
        # Give some initial time for protocols to start after pre-config
        initial_wait = min(5.0, self.convergence_timeout / 4)
        time.sleep(initial_wait)

        max_retries = 5
        retry_interval = self.convergence_timeout / max_retries
        
        last_results = []
        for attempt in range(max_retries):
            last_results = self._evaluator.evaluate_all_properties(
                self.infrastructure, self._topology_id, self.task.fault_verification
            )

            all_satisfied = True
            for result in last_results:
                if not result.satisfied:
                    all_satisfied = False
                    logger.debug(
                        f"Fault verification attempt {attempt + 1}/{max_retries} failed for {result.property_id}"
                    )
                    break

            if all_satisfied:
                logger.info("Fault state verified successfully")
                return

            if attempt < max_retries - 1:
                time.sleep(retry_interval)

        # If we reached here, verification failed all attempts
        for result in last_results:
            if not result.satisfied:
                error_prefix = f"Fault verification failed for property {result.property_id} after {max_retries} attempts"
                error_msg = f"{error_prefix}: {result.error_message}" if result.error_message else error_prefix
                
                # Log the raw observation for debugging
                if result.observation_raw:
                    logger.error(f"Raw observation for {result.property_id}:\n{result.observation_raw}")
                else:
                    logger.error(f"No raw observation captured for {result.property_id}")
                
                logger.error(error_msg)
                
                # Cleanup if verification fails
                self.infrastructure.teardown(self._topology_id)
                self._topology_id = None
                
                raise SessionError(error_msg)

    def exec_command(
        self,
        node: str,
        command: str,
        command_type: CommandType = CommandType.CONFIG,
    ) -> ExecResult:
        """
        Execute a command on a node.

        Args:
            node: Name of the node to execute on
            command: Command string to execute
            command_type: Type of command (CONFIG or READ)

        Returns:
            ExecResult with execution outcome

        Raises:
            SessionNotActiveError: If session is not active
            TurnLimitExceededError: If turn limit exceeded
            TimeLimitExceededError: If time limit exceeded
        """
        # Check session is active
        if not self.is_active:
            if self._start_time and self._get_elapsed_time() >= self.time_limit:
                raise TimeLimitExceededError(
                    f"Time limit of {self.time_limit}s exceeded"
                )
            raise SessionNotActiveError("Session is not active")

        # Every command spends a turn. command_type is recorded, not priced.
        if self._turns_used >= self.turn_limit:
            raise TurnLimitExceededError(
                f"Turn limit of {self.turn_limit} exceeded"
            )

        # Validate node exists
        if node not in self._context.nodes:
            return ExecResult(
                success=False,
                stdout="",
                stderr=f"Unknown node: {node}",
                exit_code=-1,
                command_type=command_type,
                convergence_status=ConvergenceStatus.ERROR,
                convergence_time=0.0,
                execution_time=0.0,
                error_message=f"Unknown node: {node}",
            )

        # Get container name for node
        container_name = self.infrastructure.get_node_container_name(
            self._topology_id, node
        )

        # Execute command
        exec_start = time.time()
        try:
            stdout, stderr, exit_code = self._executor.exec_on_node(
                container_name, command, timeout=self.convergence_timeout
            )
            success = exit_code == 0
            execution_time = time.time() - exec_start
            # The convergence budget is waited once, at the end of the session.
            # A per-command pause would price reads and hide the pre-convergence vector.
            convergence_time = 0.0
            convergence_status = ConvergenceStatus.CONVERGED

        except TimeoutError as e:
            execution_time = time.time() - exec_start
            return ExecResult(
                success=False,
                stdout="",
                stderr=str(e),
                exit_code=-1,
                command_type=command_type,
                convergence_status=ConvergenceStatus.TIMEOUT,
                convergence_time=0.0,
                execution_time=execution_time,
                error_message=str(e),
            )
        except Exception as e:
            execution_time = time.time() - exec_start
            logger.error(f"Error executing command on {node}: {e}")
            return ExecResult(
                success=False,
                stdout="",
                stderr=str(e),
                exit_code=-1,
                command_type=command_type,
                convergence_status=ConvergenceStatus.ERROR,
                convergence_time=0.0,
                execution_time=execution_time,
                error_message=str(e),
            )

        # Log command to history
        self._context.executed_commands.append((node, command, command_type))
        # Track execution result for syntactic validity scoring
        self._context.execution_results.append((node, command, success))

        self._turns_used += 1
        logger.debug(
            f"Executed {command_type.value} command on {node}, "
            f"turn {self._turns_used}/{self.turn_limit}"
        )
        # Immediate property vector after the command. The agent never sees it.
        if self.log_property_snapshots and self._topology_id and self.task.intent.properties:
            try:
                snap = self._evaluator.evaluate_all_properties(
                    infrastructure=self.infrastructure,
                    topology_id=self._topology_id,
                    properties=self.task.intent.properties,
                )
                self._context.property_trajectory.append({
                    "turn": self._turns_used,
                    "kind": "passive_reveal",
                    "properties": {r.property_id: r.satisfied for r in snap},
                    "completeness": sum(1 for r in snap if r.satisfied) / len(snap) if snap else 0.0,
                })
            except Exception as exc:
                logger.debug(f"Passive reveal snapshot failed at turn {self._turns_used}: {exc}")

        return ExecResult(
            success=success,
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            command_type=command_type,
            convergence_status=convergence_status,
            convergence_time=convergence_time,
            execution_time=execution_time,
        )

    def submit(self) -> SubmitResult:
        """
        Submit (complete) the session.

        Ends the session and returns the final result with the
        reconstructed approach for evaluation.

        Returns:
            SubmitResult with session outcome

        Raises:
            SessionNotActiveError: If session is not active
        """
        if not self._is_active and self._context is None:
            raise SessionNotActiveError("No session to submit")

        # Determine termination reason
        elapsed = self._get_elapsed_time()
        if elapsed >= self.time_limit:
            termination_reason = "time_limit"
        elif self._turns_used >= self.turn_limit:
            termination_reason = "turn_limit"
        else:
            termination_reason = "submitted"

        # Get approach (config commands only)
        approach = self._context.get_approach()

        # Create result
        result = SubmitResult(
            session_id=self._context.session_id,
            completed=True,
            total_turns=self._turns_used,
            total_time=elapsed,
            approach=approach,
            termination_reason=termination_reason,
        )

        # Mark session as inactive
        self._is_active = False
        logger.info(
            f"Session {self._context.session_id} submitted: "
            f"{self._turns_used} turns, {elapsed:.2f}s, reason={termination_reason}"
        )

        return result

    def get_session_status(self) -> SessionStatus:
        """
        Get current session status.

        Returns:
            SessionStatus with current state

        Raises:
            SessionNotActiveError: If no session has been started
        """
        if self._context is None:
            raise SessionNotActiveError("No session has been started")

        elapsed = self._get_elapsed_time()
        remaining_time = max(0.0, self.time_limit - elapsed)
        remaining_turns = max(0, self.turn_limit - self._turns_used)

        return SessionStatus(
            is_active=self.is_active,
            turns_used=self._turns_used,
            turns_remaining=remaining_turns,
            time_elapsed=elapsed,
            time_remaining=remaining_time,
        )

    def get_approach(self) -> List[Tuple[str, str]]:
        """
        Get the reconstructed configuration approach.

        Returns only CONFIG commands from the session history,
        suitable for robustness testing.

        Returns:
            List of (node, command) tuples for config commands

        Raises:
            SessionNotActiveError: If no session has been started
        """
        if self._context is None:
            raise SessionNotActiveError("No session has been started")

        return self._context.get_approach()

    def get_execution_log(self) -> List[Tuple[str, str, bool]]:
        """
        Get the execution log with success/failure for each command.

        Returns:
            List of (node, command, success) tuples

        Raises:
            SessionNotActiveError: If no session has been started
        """
        if self._context is None:
            raise SessionNotActiveError("No session has been started")

        return self._context.execution_results

    def get_command_transcript(self) -> List[Tuple[str, str, CommandType, bool]]:
        """
        Get the full ordered command transcript with types and outcomes.

        Returns:
            List of (node, command, command_type, success) tuples

        Raises:
            SessionNotActiveError: If no session has been started
        """
        if self._context is None:
            raise SessionNotActiveError("No session has been started")

        if len(self._context.executed_commands) != len(self._context.execution_results):
            logger.warning(
                "Session command history length mismatch: executed=%s results=%s",
                len(self._context.executed_commands),
                len(self._context.execution_results),
            )

        return [
            (node, command, command_type, success)
            for (node, command, command_type), (_, _, success) in zip(
                self._context.executed_commands,
                self._context.execution_results,
            )
        ]

    def _increment_check_count(self) -> int:
        """Increment and return the per-episode check tool call count."""
        if self._context is None:
            raise SessionNotActiveError("No session has been started")
        self._context.property_check_count += 1
        return self._context.property_check_count

    def check_properties_live(self, cap: int) -> dict:
        """
        Evaluate all intent properties on live network state (Feedback arm).

        Raises SessionNotActiveError if session not started.
        Returns dict suitable for MCP check_properties tool.
        """
        from benchmark.guide.check_helpers import build_property_check_response
        from benchmark.guide.arms import CHECK_PROPERTIES_CAP

        if self._context is None or self._topology_id is None:
            raise SessionNotActiveError("No active session")

        check_index = self._increment_check_count()
        effective_cap = cap or CHECK_PROPERTIES_CAP
        if check_index > effective_cap:
            return {
                "success": False,
                "error": "check_cap_exceeded",
                "message": f"Maximum {effective_cap} check calls per episode",
                "check_index": check_index,
                "cap": effective_cap,
            }

        results = self._evaluator.evaluate_all_properties(
            infrastructure=self.infrastructure,
            topology_id=self._topology_id,
            properties=self.task.intent.properties,
        )
        response = build_property_check_response(results, check_index, effective_cap)

        if self._context.log_property_snapshots:
            self._context.property_trajectory.append(
                {
                    "turn": self._turns_used,
                    "check_index": check_index,
                    "kind": "property_eval",
                    "properties": response["properties"],
                    "completeness": response["completeness"],
                }
            )

        return response

    def check_syntactic_validity_live(self, cap: int, window: int = 10) -> dict:
        """
        Return recent command success rate (Placebo arm).

        Uses the same per-episode call cap as check_properties.
        """
        from benchmark.guide.check_helpers import build_syntactic_validity_response
        from benchmark.guide.arms import CHECK_PROPERTIES_CAP

        if self._context is None:
            raise SessionNotActiveError("No active session")

        check_index = self._increment_check_count()
        effective_cap = cap or CHECK_PROPERTIES_CAP
        if check_index > effective_cap:
            return {
                "success": False,
                "error": "check_cap_exceeded",
                "message": f"Maximum {effective_cap} check calls per episode",
                "check_index": check_index,
                "cap": effective_cap,
            }

        response = build_syntactic_validity_response(
            self._context.execution_results,
            check_index,
            effective_cap,
            window=window,
        )

        if self._context.log_property_snapshots:
            self._context.property_trajectory.append(
                {
                    "turn": self._turns_used,
                    "check_index": check_index,
                    "kind": "syntactic_validity",
                    "success_rate": response["success_rate"],
                    "commands_checked": response["commands_checked"],
                }
            )

        return response

    def teardown(self) -> bool:
        """
        Teardown the session infrastructure.

        Should be called after session completion to clean up resources.

        Returns:
            True if teardown successful, False otherwise
        """
        if self._topology_id is None:
            return True

        try:
            success = self.infrastructure.teardown(self._topology_id)
            if success:
                logger.info(f"Topology {self._topology_id} torn down successfully")
            else:
                logger.warning(f"Topology {self._topology_id} teardown returned False")
            return success
        except Exception as e:
            logger.error(f"Error during teardown: {e}")
            return False
