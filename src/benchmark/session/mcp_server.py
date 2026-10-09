"""
MCP Server for interactive benchmark sessions.

This module provides an MCP (Model Context Protocol) server that exposes
benchmark session operations as tools for LLM agents to interact with.
"""

import asyncio
import logging
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from benchmark.session.models import (
    CommandType,
    ConvergenceStatus,
    ExecResult,
    SessionContext,
    SessionStatus,
    SubmitResult,
)
from benchmark.session.session import (
    InteractiveSession,
    SessionError,
    SessionNotActiveError,
    TurnLimitExceededError,
    TimeLimitExceededError,
)
from benchmark.guide.arms import FeedbackArm, CHECK_PROPERTIES_CAP

# Setup logging
logger = logging.getLogger(__name__)


class BenchmarkMCPServer:
    """
    MCP Server for benchmark interactive sessions.

    Exposes benchmark session operations as MCP tools:
    - exec_command: Execute a command on a network node
    - submit: Submit (complete) the session
    - get_session_status: Get current session status
    - get_nodes: Get list of available nodes
    """

    def __init__(
        self,
        session: InteractiveSession,
        name: str = "BenchmarkServer",
        feedback_arm: Optional[str] = None,
    ):
        """
        Initialize the MCP server.

        Args:
            session: The interactive session to expose via MCP
            name: Server name for MCP identification
            feedback_arm: Guide experiment arm (blind/declared/feedback/placebo).
                When None, legacy tool set only (no check tools).
        """
        self.session = session
        self._session_context: Optional[SessionContext] = None
        self._feedback_arm: Optional[FeedbackArm] = (
            FeedbackArm.from_str(feedback_arm) if feedback_arm else None
        )
        self._mcp = FastMCP(name=name, stateless_http=True, json_response=True)

        # Register tools
        self._register_tools()

    @property
    def mcp(self) -> FastMCP:
        """Get the FastMCP instance."""
        return self._mcp

    def _register_tools(self) -> None:
        """Register all MCP tools."""

        @self._mcp.tool()
        def exec_command(
            node: str,
            command: str,
            command_type: str = "config",
        ) -> Dict[str, Any]:
            """
            Execute a command on a network node.

            Args:
                node: Name of the node to execute on (e.g., 'R1', 'R2')
                command: Command string to execute (e.g., 'vtysh -c "show ip route"')
                command_type: Label stored with the command ('config' or 'read').
                              Every command counts as one turn, whichever label is sent.

            Returns:
                Execution result with stdout, stderr, exit code, convergence status
            """
            try:
                # Parse command type
                cmd_type = (
                    CommandType.CONFIG
                    if command_type.lower() == "config"
                    else CommandType.READ
                )

                result = self.session.exec_command(node, command, cmd_type)

                return {
                    "success": result.success,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "exit_code": result.exit_code,
                    "command_type": result.command_type.value,
                    "convergence_status": result.convergence_status.value,
                    "convergence_time": result.convergence_time,
                    "execution_time": result.execution_time,
                    "error_message": result.error_message,
                }
            except TurnLimitExceededError as e:
                return {
                    "success": False,
                    "error": "turn_limit_exceeded",
                    "message": str(e),
                }
            except TimeLimitExceededError as e:
                return {
                    "success": False,
                    "error": "time_limit_exceeded",
                    "message": str(e),
                }
            except SessionNotActiveError as e:
                return {
                    "success": False,
                    "error": "session_not_active",
                    "message": str(e),
                }
            except Exception as e:
                logger.error(f"Error executing command: {e}")
                return {
                    "success": False,
                    "error": "execution_error",
                    "message": str(e),
                }

        @self._mcp.tool()
        def submit() -> Dict[str, Any]:
            """
            Submit (complete) the current session.

            This ends the interactive session and triggers evaluation.
            Call this when you believe you have completed the configuration task.

            Returns:
                Submission result with total turns, time, and approach taken
            """
            try:
                result = self.session.submit()

                return {
                    "success": True,
                    "session_id": result.session_id,
                    "completed": result.completed,
                    "total_turns": result.total_turns,
                    "total_time": result.total_time,
                    "termination_reason": result.termination_reason,
                    "approach_length": len(result.approach),
                }
            except SessionNotActiveError as e:
                return {
                    "success": False,
                    "error": "session_not_active",
                    "message": str(e),
                }
            except Exception as e:
                logger.error(f"Error submitting session: {e}")
                return {
                    "success": False,
                    "error": "submission_error",
                    "message": str(e),
                }

        @self._mcp.tool()
        def get_session_status() -> Dict[str, Any]:
            """
            Get the current session status including resource constraints.

            IMPORTANT: Call this BEFORE starting extensive work to understand your resource budget!
            This helps you plan effectively by showing:
            - How many commands you've used vs. remaining (reads count too)
            - How much time has elapsed vs. remaining
            - Whether the session is still active

            Use this information to:
            - Prioritize essential configurations when resources are limited
            - Decide between thorough verification vs. quick completion
            - Avoid running out of turns before core requirements are met

            Returns:
                Session status with turns and time information:
                - success: Whether the status check succeeded
                - is_active: Whether the session is still accepting commands
                - turns_used: Number of commands executed
                - turns_remaining: Number of commands left
                - time_elapsed: Seconds elapsed since session start
                - time_remaining: Seconds remaining before timeout
            """
            try:
                status = self.session.get_session_status()

                return {
                    "success": True,
                    "is_active": status.is_active,
                    "turns_used": status.turns_used,
                    "turns_remaining": status.turns_remaining,
                    "time_elapsed": round(status.time_elapsed, 2),
                    "time_remaining": round(status.time_remaining, 2),
                }
            except SessionNotActiveError as e:
                return {
                    "success": False,
                    "error": "session_not_active",
                    "message": str(e),
                }
            except Exception as e:
                logger.error(f"Error getting session status: {e}")
                return {
                    "success": False,
                    "error": "status_error",
                    "message": str(e),
                }

        @self._mcp.tool()
        def get_nodes() -> Dict[str, Any]:
            """
            Get the list of available network nodes.

            Returns the names of all nodes in the topology that can be
            targeted by exec_command.

            Returns:
                List of node names
            """
            try:
                if self.session._context is None:
                    return {
                        "success": False,
                        "error": "session_not_started",
                        "message": "Session has not been started",
                    }

                return {
                    "success": True,
                    "nodes": self.session._context.nodes,
                    "node_count": len(self.session._context.nodes),
                }
            except Exception as e:
                logger.error(f"Error getting nodes: {e}")
                return {
                    "success": False,
                    "error": "nodes_error",
                    "message": str(e),
                }

        if self._feedback_arm == FeedbackArm.FEEDBACK:

            @self._mcp.tool()
            def check_properties() -> Dict[str, Any]:
                """
                Check live satisfaction of declared intent properties on current network state.

                Returns a boolean vector eval(s_t, P) plus completeness score.
                Does not consume a configuration turn. Capped per episode.
                """
                try:
                    return self.session.check_properties_live(CHECK_PROPERTIES_CAP)
                except SessionNotActiveError as e:
                    return {
                        "success": False,
                        "error": "session_not_active",
                        "message": str(e),
                    }
                except Exception as e:
                    logger.error(f"Error checking properties: {e}")
                    return {
                        "success": False,
                        "error": "check_properties_error",
                        "message": str(e),
                    }

        if self._feedback_arm == FeedbackArm.PLACEBO:

            @self._mcp.tool()
            def check_syntactic_validity() -> Dict[str, Any]:
                """
                Check whether recent commands executed without error (syntactic validity).

                Returns command success rate for recent exec_command calls.
                Does not consume a configuration turn. Capped per episode.
                This is NOT a property satisfaction check.
                """
                try:
                    return self.session.check_syntactic_validity_live(CHECK_PROPERTIES_CAP)
                except SessionNotActiveError as e:
                    return {
                        "success": False,
                        "error": "session_not_active",
                        "message": str(e),
                    }
                except Exception as e:
                    logger.error(f"Error checking syntactic validity: {e}")
                    return {
                        "success": False,
                        "error": "check_syntactic_validity_error",
                        "message": str(e),
                    }

    def get_tool_list(self) -> List[str]:
        """Get list of registered tool names."""
        tools = ["exec_command", "submit", "get_session_status", "get_nodes"]
        if self._feedback_arm == FeedbackArm.FEEDBACK:
            tools.append("check_properties")
        elif self._feedback_arm == FeedbackArm.PLACEBO:
            tools.append("check_syntactic_validity")
        return tools

    def run(self, transport: str = "streamable-http") -> None:
        """
        Run the MCP server.

        Args:
            transport: Transport type ('streamable-http' or 'stdio')
        """
        self._mcp.run(transport=transport)

    def close(self) -> None:
        """
        Close the MCP server and clean up resources.

        This should be called when the session ends to properly
        release any resources held by the server.
        """
        try:
            # Clear the session reference
            self.session = None
            self._session_context = None
            logger.info("MCP server closed")
        except Exception as e:
            logger.error(f"Error closing MCP server: {e}")

    def streamable_http_app(self):
        """
        Get the Starlette app for mounting in an ASGI server.

        Returns:
            Starlette app for the MCP server
        """
        return self._mcp.streamable_http_app()


def create_benchmark_mcp_server(
    session: InteractiveSession,
    name: str = "BenchmarkServer",
    feedback_arm: Optional[str] = None,
) -> BenchmarkMCPServer:
    """
    Factory function to create a BenchmarkMCPServer.

    Args:
        session: The interactive session to expose
        name: Server name
        feedback_arm: Optional guide experiment arm

    Returns:
        Configured BenchmarkMCPServer instance
    """
    return BenchmarkMCPServer(
        session=session, name=name, feedback_arm=feedback_arm
    )
