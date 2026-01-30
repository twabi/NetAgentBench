"""
Interactive Benchmark Controller for multi-turn sessions.

This controller orchestrates multi-turn interactive benchmarks where an agent
can execute commands iteratively and receive feedback before submitting.
"""

import asyncio
import contextlib
import logging
import time
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import uvicorn
from starlette.applications import Starlette
from starlette.routing import Mount

from benchmark.infrastructure.base import InfrastructureProvider
from benchmark.infrastructure.containerlab import ContainerlabProvider
from benchmark.evaluator.property import PropertyEvaluator
from benchmark.scoring.metrics import ScoringCalculator
from benchmark.scoring.validity import ValidityChecker
from benchmark.models.task import TaskDefinition
from benchmark.models.results import (
    BenchmarkResult,
    ExecutionMetrics,
    PropertyEvaluationResult,
    ScoringResult,
    ValidityCheck,
)
from benchmark.session.session import InteractiveSession
from benchmark.session.mcp_server import BenchmarkMCPServer
from benchmark.session.models import SubmitResult

# Setup logging
logger = logging.getLogger(__name__)

# Suppress noisy MCP library errors (ClosedResourceError on normal session close)
logging.getLogger("mcp.server.streamable_http").setLevel(logging.CRITICAL)



class InteractiveBenchmarkController:
    """
    Controller for multi-turn interactive benchmark sessions.

    Unlike the standard BenchmarkController which applies a complete approach
    at once, this controller:
    1. Provisions infrastructure
    2. Starts an MCP server for agent interaction
    3. Allows the agent to execute commands iteratively
    4. Waits for submission or timeout
    5. Evaluates properties and computes scores
    6. Tears down infrastructure
    """

    def __init__(
        self,
        infrastructure: Optional[InfrastructureProvider] = None,
        property_evaluator: Optional[PropertyEvaluator] = None,
        scoring_calculator: Optional[ScoringCalculator] = None,
        validity_checker: Optional[ValidityChecker] = None,
    ):
        """
        Initialize the interactive controller.

        Args:
            infrastructure: Provider for infrastructure provisioning
            property_evaluator: Evaluator for properties
            scoring_calculator: Calculator for scoring metrics
            validity_checker: Checker for validity conditions
        """
        self.infrastructure = infrastructure or ContainerlabProvider()
        self.property_evaluator = property_evaluator or PropertyEvaluator()
        self.scoring_calculator = scoring_calculator or ScoringCalculator()
        self.validity_checker = validity_checker or ValidityChecker()

        # Session and server state
        self._session: Optional[InteractiveSession] = None
        self._mcp_server: Optional[BenchmarkMCPServer] = None
        self._server_thread: Optional[threading.Thread] = None

    def generate_run_id(
        self,
        testee_id: str,
        model_name: Optional[str] = None,
        mode: str = "multi",
    ) -> str:
        """
        Generate a descriptive run ID.

        Args:
            testee_id: Identifier for the testee
            model_name: Optional model name (e.g., 'gpt-4o')
            mode: Benchmark mode ('single' or 'multi')

        Returns:
            Descriptive run ID with timestamp and UUID
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        short_uuid = str(uuid.uuid4())[:8]

        # Add mode suffix
        mode_suffix = "mt" if mode == "multi" else "st"
        
        # testee_id already contains provider+model (e.g., "gemini_gemini25flash")
        # so just use it directly without appending model_name again
        return f"{testee_id}_{mode_suffix}_{timestamp}_{short_uuid}"

    def run_interactive(
        self,
        task: TaskDefinition,
        testee_id: str,
        testee_type: str = "interactive",
        model_name: Optional[str] = None,
        turn_limit: int = 50,
        time_limit: float = 600.0,
        mcp_port: int = 8001,
        mcp_host: str = "localhost",
        wait_for_submit: bool = True,
        dagent_endpoint: Optional[str] = None,
        dagent_provider: Optional[str] = None,
        dagent_model: Optional[str] = None,
        dagent_host: Optional[str] = None,
        dagent_mode: str = "single",
        dagent_structure: str = "sequential",
        verbose: bool = False,
    ) -> BenchmarkResult:
        """
        Run an interactive benchmark session.

        This method:
        1. Provisions the topology
        2. Creates an interactive session
        3. Starts an MCP server for agent interaction
        4. Triggers dagent (if endpoint provided) or waits for submission
        5. Evaluates properties
        6. Computes scores
        7. Tears down infrastructure

        Args:
            task: Task definition
            testee_id: Identifier for the testee
            testee_type: Type of testee ('interactive', 'dagent', etc.)
            model_name: Optional model name for run_id generation
            turn_limit: Maximum number of config commands
            time_limit: Maximum session time in seconds
            mcp_port: Port for MCP server
            wait_for_submit: Wait for agent to call submit
            dagent_endpoint: Optional dagent HTTP endpoint to trigger
            dagent_provider: LLM provider for dagent (openai, gemini, anthropic, ollama)
            dagent_model: Model name for dagent (e.g., gpt-4o, gemini-2.0-flash)
            dagent_host: Optional host for the provider (e.g., Ollama URL)
            dagent_mode: Agent mode ('single' for single-agent, 'multi' for multi-agent)
            dagent_structure: Multi-agent structure ('sequential', 'concurrent', 'debate', 'group_chat')
            verbose: Print each agent action as it executes

        Returns:
            BenchmarkResult with evaluation and scores
        """
        # Generate run ID
        run_id = self.generate_run_id(testee_id, model_name, "multi")
        timestamp = datetime.now()

        logger.info(f"Starting interactive benchmark: {run_id}")
        logger.info(f"Task: {task.task_id}, Testee: {testee_id}")

        # Initialize tracking
        errors: List[str] = []
        property_results: List[PropertyEvaluationResult] = []
        submit_result: Optional[SubmitResult] = None
        reasoning_trace: List[Dict[str, Any]] = []

        # Timing
        start_time = time.time()
        provision_time = 0.0
        session_time = 0.0
        evaluation_time = 0.0

        try:
            # ============================================================
            # STEP 1: Create Interactive Session
            # ============================================================
            logger.info("Step 1: Creating interactive session")
            provision_start = time.time()

            self._session = InteractiveSession(
                task=task,
                infrastructure=self.infrastructure,
                turn_limit=turn_limit,
                time_limit=time_limit,
            )

            # Start session (provisions topology)
            session_context = self._session.start()
            provision_time = time.time() - provision_start

            logger.info(
                f"Session started: {session_context.session_id} "
                f"({len(session_context.nodes)} nodes, {provision_time:.2f}s)"
            )

            # ============================================================
            # STEP 2: Create and Configure MCP Server
            # ============================================================
            logger.info("Step 2: Setting up MCP server")
            self._mcp_server = BenchmarkMCPServer(
                session=self._session,
                name=f"Benchmark_{task.task_id}",
            )

            # Start the MCP server on HTTP port in background thread
            mcp_app = self._mcp_server.streamable_http_app()
            config = uvicorn.Config(
                mcp_app,
                host="0.0.0.0",
                port=mcp_port,
                log_level="warning",
            )
            self._uvicorn_server = uvicorn.Server(config)
            
            def run_server():
                asyncio.run(self._uvicorn_server.serve())
            
            self._server_thread = threading.Thread(target=run_server, daemon=True)
            self._server_thread.start()
            
            # Give the server time to start
            time.sleep(0.5)

            logger.info(f"MCP server running on http://0.0.0.0:{mcp_port}")

            # ============================================================
            # STEP 3: Trigger Dagent (if endpoint provided)
            # ============================================================
            dagent_result = None
            token_usage = None
            tool_usage = None
            agent_conversations = None
            total_commands = None
            failed_commands = None
            if dagent_endpoint:
                logger.info(f"Step 3: Triggering dagent at {dagent_endpoint}")
                import httpx
                
                # Prepare task info for dagent
                dagent_request = {
                    # COMPLETE task definition for model context
                    "task_definition": task.model_dump() if hasattr(task, 'model_dump') else task.dict(),
                    # Individual fields (backwards compatibility)
                    "task_id": task.task_id,
                    "description": task.description,
                    "nodes": [n.name for n in task.topology.nodes],
                    "properties": [
                        {
                            "id": p.id, 
                            "type": p.type.value if hasattr(p.type, 'value') else str(p.type), 
                            "description": p.description,
                            "evaluation": p.evaluation.model_dump() if hasattr(p.evaluation, 'model_dump') else (p.evaluation.dict() if hasattr(p.evaluation, 'dict') else None)
                        }
                        for p in task.intent.properties
                    ],
                    "mcp_url": f"http://{mcp_host}:{mcp_port}/mcp",
                    "turn_limit": turn_limit,
                    "time_limit": time_limit,
                    # Pass provider and model to dagent
                    "provider": dagent_provider or "openai",
                    "model": dagent_model,
                    "host": dagent_host,
                    "agent_mode": dagent_mode,
                    "structure": dagent_structure,

                }
                
                try:
                    with httpx.Client(timeout=time_limit + 30) as client:
                        response = client.post(
                            f"{dagent_endpoint}/benchmark/solve",
                            json=dagent_request,
                        )
                        dagent_result = response.json()
                        # Extract model_version from dagent response
                        model_name = dagent_result.get("model_version", "unknown")
                        reasoning_trace = dagent_result.get("reasoning_trace", [])
                        # Extract new tracking metrics
                        token_usage = dagent_result.get("token_usage", None)
                        tool_usage = dagent_result.get("tool_usage", None)
                        agent_conversations = dagent_result.get("agent_conversations", None)
                        # Calculate failed commands from actions
                        actions_list = dagent_result.get("actions", [])
                        total_commands = len(actions_list)
                        failed_commands = sum(
                            1 for a in actions_list 
                            if not a.get("result", {}).get("success", True)
                        )
                        logger.info(f"Dagent response: {dagent_result}")
                        logger.info(f"Agent model: {model_name}")
                        if token_usage:
                            logger.info(f"Token usage: {token_usage}")
                        
                        # Verbose: print each action
                        if verbose:
                            actions = dagent_result.get("actions", [])
                            print(f"\n{'='*60}")
                            print(f"Agent Actions ({len(actions)} total)")
                            print(f"{'='*60}")
                            for i, action in enumerate(actions, 1):
                                act_type = action.get("action", "unknown")
                                inp = action.get("input", {})
                                res = action.get("result", {})
                                node = inp.get("node", "?")
                                cmd = inp.get("command", "?")[:60]
                                success = "✓" if res.get("success") else "✗"
                                cmd_type = inp.get("command_type", "config")[:4]
                                print(f"{i:3}. [{success}] {node} ({cmd_type}) {cmd}")
                                # Show error or first line of output for failures
                                if not res.get("success") and res.get("stdout"):
                                    first_line = res["stdout"].split("\n")[0][:50]
                                    print(f"     └─ {first_line}")
                            print(f"{'='*60}\n")
                except Exception as e:
                    logger.error(f"Dagent call failed: {e}")
                    errors.append(f"Dagent call failed: {e}")
                    
                    # RECOVERY: Try to get metrics from session if dagent failed/timed out
                    try:
                        exec_log_tuples = self._session.get_execution_log()
                        if exec_log_tuples:
                            total_commands = len(exec_log_tuples)
                            failed_commands = sum(1 for _, _, success in exec_log_tuples if not success)
                            tool_usage = {"exec_command": total_commands}
                            logger.info(f"Recovered partial metrics from session: {total_commands} commands")
                    except Exception as recovery_err:
                        logger.warning(f"Could not recover metrics from session: {recovery_err}")
                
                session_time = time.time() - provision_start - provision_time

            # ============================================================
            # STEP 4: Wait for Session Completion (manual mode)
            # ============================================================
            elif wait_for_submit:
                logger.info("Step 4: Waiting for session completion")
                session_start = time.time()

                # Poll for session completion
                while self._session.is_active:
                    time.sleep(1.0)

                    # Check time limit
                    elapsed = time.time() - session_start
                    if elapsed >= time_limit:
                        logger.info(f"Time limit reached: {elapsed:.1f}s")
                        break

                session_time = time.time() - session_start

                # Get submit result if session was submitted
                if not self._session.is_active:
                    try:
                        submit_result = self._session.submit()
                    except Exception:
                        # Session may have already been submitted
                        pass

                logger.info(f"Session completed after {session_time:.2f}s")
            else:
                logger.info("Step 3: Skipping wait (wait_for_submit=False)")
                session_time = 0.0

            # ============================================================
            # STEP 4: Evaluate Properties
            # ============================================================
            # Wait for protocol convergence before evaluation (especially for BGP/OSPF)
            convergence_wait = getattr(task.convergence, 'timeout_seconds', 10) if task.convergence else 10
            # For multi-turn, use a portion of the convergence timeout after agent submits
            pre_eval_wait = min(convergence_wait, 30)  # Cap at 30 seconds
            logger.info(f"Step 4: Waiting {pre_eval_wait}s for protocol convergence before evaluation")
            time.sleep(pre_eval_wait)
            
            logger.info("Step 4.5: Evaluating properties")
            try:
                evaluation_start = time.time()
                property_results = self.property_evaluator.evaluate_all_properties(
                    infrastructure=self.infrastructure,
                    topology_id=session_context.topology_id,
                    properties=task.intent.properties,
                )
                evaluation_time = time.time() - evaluation_start

                satisfied_count = sum(1 for p in property_results if p.satisfied)
                logger.info(
                    f"Property evaluation: {satisfied_count}/{len(property_results)} "
                    f"satisfied ({evaluation_time:.2f}s)"
                )

                # Log failures
                for prop in property_results:
                    if not prop.satisfied:
                        logger.info(f"  FAILED: {prop.property_id}")
                        logger.info(f"    Raw output: {prop.observation_raw[:200] if prop.observation_raw else 'None'}...")
                        if prop.error_message:
                            logger.info(f"    Error: {prop.error_message}")
                            errors.append(
                                f"Property {prop.property_id} failed: {prop.error_message}"
                            )
            except Exception as e:
                error_msg = f"Property evaluation error: {e}"
                logger.error(error_msg)
                errors.append(error_msg)

            # ============================================================
            # STEP 5: Compute Scores
            # ============================================================
            logger.info("Step 5: Computing scores")
            try:
                # Get approach from session
                approach_tuples = self._session.get_approach()
                # Convert to Approach format for scoring
                from benchmark.models.submission import Approach, CommandSequence
                from benchmark.executor.command import ExecutionLogEntry

                # Handle empty approach (no commands executed)
                if approach_tuples:
                    command_sequences = [
                        CommandSequence(node=node, commands=[cmd])
                        for node, cmd in approach_tuples
                    ]
                else:
                    # No commands - use a placeholder for scoring
                    command_sequences = [
                        CommandSequence(node="none", commands=["# no commands executed"])
                    ]

                approach = Approach(commands=command_sequences)

                # Build execution log from session
                exec_log_tuples = self._session.get_execution_log()
                execution_log = [
                    ExecutionLogEntry(
                        timestamp=datetime.now(),
                        node=node,
                        command=cmd,
                        success=success,
                        stdout="",
                        stderr="",
                        exit_code=0 if success else 1,
                        execution_time=0.0,
                    )
                    for node, cmd, success in exec_log_tuples
                ]

                scoring_result = self.scoring_calculator.compute_all_scores(
                    property_results=property_results,
                    execution_log=execution_log,
                    approach=approach,
                    optimal_solution=task.optimal_solution,
                )
                logger.info(f"Final score: {scoring_result.final_score:.3f}")

                validity_check = self.validity_checker.check_validity(
                    property_results=property_results,
                    execution_log=execution_log,
                    final_score=scoring_result.final_score,
                )
                logger.info(f"Valid solution: {validity_check.is_valid_solution}")

            except Exception as e:
                error_msg = f"Scoring error: {e}"
                logger.error(error_msg)
                errors.append(error_msg)

                scoring_result = ScoringResult(
                    completeness=0.0,
                    robustness=0.0,
                    syntactic_validity=0.0,
                    efficiency=None,
                    final_score=0.0,
                    weights=ScoringCalculator.DEFAULT_WEIGHTS,
                )
                validity_check = ValidityCheck(
                    is_valid_solution=False,
                    condition_a_syntactic=False,
                    condition_b_semantic=False,
                )

            # ============================================================
            total_time = time.time() - start_time
            success = validity_check.is_valid_solution and len(errors) == 0

            # Get turn info and termination reason from session
            try:
                status = self._session.get_session_status()
                turns_used = status.turns_used
                # Get termination reason from submit_result or session
                if submit_result:
                    termination_reason = submit_result.reason
                elif not self._session.is_active:
                    termination_reason = "submitted"
                else:
                    termination_reason = "unknown"
            except Exception:
                turns_used = 0
                termination_reason = "error"

            result = BenchmarkResult(
                run_id=run_id,
                timestamp=timestamp,
                task_id=task.task_id,
                testee_id=testee_id,
                testee_type=testee_type,
                evaluation_mode="multi_turn",  # This is multi-turn mode
                model_version=model_name,  # Pass model name if provided
                success=success,
                property_results=property_results,
                scoring=scoring_result,
                validity=validity_check,
                metrics=ExecutionMetrics(
                    infrastructure_provision_time=provision_time,
                    config_execution_time=session_time,  # Session time as config time
                    convergence_time=0.0,  # Handled within session
                    evaluation_time=evaluation_time,
                    total_time=total_time,
                    # Multi-turn specific fields
                    is_multi_turn=True,
                    turns_to_complete=turns_used,
                    time_to_complete=session_time,
                    termination_reason=termination_reason,
                    tool_usage=tool_usage if dagent_endpoint else None,
                    total_commands=total_commands,
                    failed_commands=failed_commands,
                    token_usage=token_usage if dagent_endpoint else None,
                    agent_conversations=agent_conversations if dagent_endpoint else None,
                ),
                execution_log=[
                    f"{node} | {cmd}" for node, cmd in approach_tuples
                ],
                errors=errors,
                reasoning_trace=reasoning_trace,
            )

            logger.info(
                f"Interactive benchmark complete: {run_id} "
                f"(success={success}, turns={turns_used})"
            )
            return result

        except Exception as e:
            logger.error(f"Interactive benchmark failed: {e}")
            errors.append(f"Benchmark error: {e}")

            return BenchmarkResult(
                run_id=run_id,
                timestamp=timestamp,
                task_id=task.task_id,
                testee_id=testee_id,
                testee_type=testee_type,
                success=False,
                property_results=[],
                scoring=ScoringResult(
                    completeness=0.0,
                    robustness=0.0,
                    syntactic_validity=0.0,
                    efficiency=None,
                    final_score=0.0,
                    weights=ScoringCalculator.DEFAULT_WEIGHTS,
                ),
                validity=ValidityCheck(
                    is_valid_solution=False,
                    condition_a_syntactic=False,
                    condition_b_semantic=False,
                ),
                metrics=ExecutionMetrics(
                    infrastructure_provision_time=provision_time,
                    config_execution_time=0.0,
                    convergence_time=0.0,
                    evaluation_time=0.0,
                    total_time=time.time() - start_time,
                ),
                execution_log=[],
                errors=errors,
            )

        finally:
            # ============================================================
            # STEP 7: Teardown
            # ============================================================
            logger.info("Step 7: Tearing down")
            
            # Clean up uvicorn server
            if hasattr(self, '_uvicorn_server') and self._uvicorn_server:
                try:
                    logger.info("Shutting down uvicorn server")
                    self._uvicorn_server.should_exit = True
                    self._uvicorn_server = None
                except Exception as e:
                    logger.error(f"Uvicorn shutdown error: {e}")
            
            # Clean up MCP server
            if self._mcp_server:
                try:
                    logger.info("Closing MCP server")
                    self._mcp_server.close()
                    self._mcp_server = None
                except Exception as e:
                    logger.error(f"MCP server cleanup error: {e}")
            
            # Teardown session (infrastructure)
            if self._session:
                try:
                    self._session.teardown()
                    self._session = None
                except Exception as e:
                    logger.error(f"Session teardown error: {e}")

    def get_mcp_server(self) -> Optional[BenchmarkMCPServer]:
        """Get the MCP server instance (if running)."""
        return self._mcp_server

    def get_session(self) -> Optional[InteractiveSession]:
        """Get the current session (if active)."""
        return self._session
