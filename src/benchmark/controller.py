"""
Benchmark Controller - Main orchestrator for the benchmark system.

The BenchmarkController ties together all components to run a complete benchmark:
1. Provision infrastructure (Containerlab topology)
2. Wait for infrastructure to be ready
3. Apply configuration approach
4. Wait for network convergence
5. Evaluate properties
6. Compute scores and validity
7. Teardown infrastructure
8. Return comprehensive results

This implements the workflow defined in Phase 6 of the implementation plan.
"""

import logging
import time
import uuid
from datetime import datetime
from typing import List, Optional

from benchmark.infrastructure.base import InfrastructureProvider
from benchmark.infrastructure.containerlab import ContainerlabProvider
from benchmark.executor.command import CommandExecutor, ExecutionLogEntry
from benchmark.executor.observation import ObservationExecutor
from benchmark.evaluator.property import PropertyEvaluator
from benchmark.scoring.metrics import ScoringCalculator
from benchmark.scoring.validity import ValidityChecker
from benchmark.models.task import TaskDefinition
from benchmark.models.submission import Submission
from benchmark.models.results import (
    BenchmarkResult,
    ExecutionMetrics,
    PropertyEvaluationResult,
)

# Setup logging
logger = logging.getLogger(__name__)


class BenchmarkController:
    """
    Main orchestrator for running network configuration benchmarks.
    
    The controller manages the complete benchmark lifecycle:
    - Infrastructure provisioning and teardown
    - Configuration application
    - Property evaluation
    - Scoring and validity checking
    - Results aggregation
    """

    def __init__(
        self,
        infrastructure: Optional[InfrastructureProvider] = None,
        command_executor: Optional[CommandExecutor] = None,
        observation_executor: Optional[ObservationExecutor] = None,
        property_evaluator: Optional[PropertyEvaluator] = None,
        scoring_calculator: Optional[ScoringCalculator] = None,
        validity_checker: Optional[ValidityChecker] = None,
    ):
        """
        Initialize the BenchmarkController with required components.
        
        Args:
            infrastructure: Provider for infrastructure provisioning (defaults to ContainerlabProvider)
            command_executor: Executor for commands (defaults to CommandExecutor)
            observation_executor: Executor for observations (defaults to ObservationExecutor)
            property_evaluator: Evaluator for properties (defaults to PropertyEvaluator)
            scoring_calculator: Calculator for scoring metrics (defaults to ScoringCalculator)
            validity_checker: Checker for validity conditions (defaults to ValidityChecker)
        """
        self.infrastructure = infrastructure or ContainerlabProvider()
        self.command_executor = command_executor or CommandExecutor()
        self.observation_executor = observation_executor or ObservationExecutor()
        self.property_evaluator = property_evaluator or PropertyEvaluator()
        self.scoring_calculator = scoring_calculator or ScoringCalculator()
        self.validity_checker = validity_checker or ValidityChecker()

    def run(
        self, task: TaskDefinition, submission: Submission
    ) -> BenchmarkResult:
        """
        Run a complete benchmark for a given task and submission.
        
        This is the main entry point for the benchmark system. It orchestrates
        the entire benchmark workflow and returns comprehensive results.
        
        Args:
            task: The task definition specifying topology, intent, and evaluation
            submission: The testee's submission with configuration approach
            
        Returns:
            BenchmarkResult with complete evaluation data and metrics
        """
        # Generate unique run ID
        run_id = f"run_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        timestamp = datetime.now()
        
        logger.info(f"Starting benchmark run: {run_id}")
        logger.info(f"Task: {task.task_id}, Testee: {submission.testee_id}")

        # Initialize tracking
        errors: List[str] = []
        execution_log: List[ExecutionLogEntry] = []
        property_results: List[PropertyEvaluationResult] = []
        topology_id: Optional[str] = None

        # Start timing
        start_time = time.time()
        provision_start = start_time
        provision_time = 0.0
        config_time = 0.0
        convergence_time = 0.0
        evaluation_time = 0.0

        try:
            # ============================================================
            # STEP 1: Provision Infrastructure
            # ============================================================
            logger.info("Step 1: Provisioning infrastructure")
            try:
                provision_start = time.time()
                topology_id = self.infrastructure.provision(task.topology)
                provision_time = time.time() - provision_start
                logger.info(
                    f"Infrastructure provisioned: {topology_id} ({provision_time:.2f}s)"
                )
            except Exception as e:
                error_msg = f"Infrastructure provision failed: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
                # Cannot continue without infrastructure
                return self._build_error_result(
                    run_id=run_id,
                    timestamp=timestamp,
                    task=task,
                    submission=submission,
                    errors=errors,
                    execution_log=execution_log,
                    property_results=property_results,
                    metrics=ExecutionMetrics(
                        infrastructure_provision_time=time.time() - provision_start,
                        config_execution_time=0.0,
                        convergence_time=0.0,
                        evaluation_time=0.0,
                        total_time=time.time() - start_time,
                    ),
                )

            # ============================================================
            # STEP 2: Wait for Infrastructure Ready
            # ============================================================
            logger.info("Step 2: Waiting for infrastructure ready")
            ready_timeout = 60  # 60 seconds timeout
            ready_start = time.time()
            ready_interval = 2  # Check every 2 seconds

            infrastructure_ready = False
            while (time.time() - ready_start) < ready_timeout:
                if self.infrastructure.is_ready(topology_id):
                    infrastructure_ready = True
                    logger.info("Infrastructure is ready")
                    break
                time.sleep(ready_interval)

            if not infrastructure_ready:
                error_msg = f"Infrastructure not ready after {ready_timeout}s timeout"
                logger.error(error_msg)
                errors.append(error_msg)
                return self._build_error_result(
                    run_id=run_id,
                    timestamp=timestamp,
                    task=task,
                    submission=submission,
                    errors=errors,
                    execution_log=execution_log,
                    property_results=property_results,
                    metrics=ExecutionMetrics(
                        infrastructure_provision_time=provision_time,
                        config_execution_time=0.0,
                        convergence_time=0.0,
                        evaluation_time=0.0,
                        total_time=time.time() - start_time,
                    ),
                    topology_id=topology_id,
                )

            # ============================================================
            # STEP 3: Initial Convergence Wait
            # ============================================================
            logger.info("Step 3: Waiting for initial convergence")
            initial_convergence = task.convergence.timeout_seconds
            time.sleep(initial_convergence)
            convergence_time += initial_convergence
            logger.info(f"Initial convergence wait: {initial_convergence}s")

            # ============================================================
            # STEP 4: Apply Configuration Approach
            # ============================================================
            logger.info("Step 4: Applying configuration approach")
            try:
                config_start = time.time()
                execution_log = self.command_executor.apply_approach(
                    infrastructure=self.infrastructure,
                    topology_id=topology_id,
                    approach=submission.approach,
                    convergence_timeout=0,  # We handle convergence separately
                )
                config_time = time.time() - config_start
                logger.info(
                    f"Configuration applied: {len(execution_log)} commands ({config_time:.2f}s)"
                )

                # Log any command failures
                failed_commands = [entry for entry in execution_log if not entry.success]
                if failed_commands:
                    logger.warning(
                        f"Configuration had {len(failed_commands)} failed commands"
                    )
                    for entry in failed_commands:
                        errors.append(
                            f"Command failed on {entry.node}: {entry.command} - {entry.stderr}"
                        )
            except Exception as e:
                error_msg = f"Configuration execution error: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
                # Continue to evaluation even if config failed

            # ============================================================
            # STEP 5: Post-Config Convergence Wait
            # ============================================================
            logger.info("Step 5: Waiting for post-config convergence")
            post_convergence = task.convergence.timeout_seconds
            time.sleep(post_convergence)
            convergence_time += post_convergence
            logger.info(f"Post-config convergence wait: {post_convergence}s")

            # ============================================================
            # STEP 6: Evaluate Properties
            # ============================================================
            logger.info("Step 6: Evaluating properties")
            try:
                evaluation_start = time.time()
                property_results = self.property_evaluator.evaluate_all_properties(
                    infrastructure=self.infrastructure,
                    topology_id=topology_id,
                    properties=task.intent.properties,
                )
                evaluation_time = time.time() - evaluation_start
                
                satisfied_count = sum(1 for p in property_results if p.satisfied)
                logger.info(
                    f"Property evaluation complete: {satisfied_count}/{len(property_results)} satisfied ({evaluation_time:.2f}s)"
                )

                # Log any property failures
                failed_properties = [p for p in property_results if not p.satisfied]
                for prop in failed_properties:
                    if prop.error_message:
                        errors.append(
                            f"Property {prop.property_id} failed: {prop.error_message}"
                        )
            except Exception as e:
                error_msg = f"Property evaluation error: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
                # Property results will be empty, leading to zero scores

            # ============================================================
            # STEP 7: Compute Scores and Validity
            # ============================================================
            logger.info("Step 7: Computing scores and validity")
            try:
                scoring_result = self.scoring_calculator.compute_all_scores(
                    property_results=property_results,
                    execution_log=execution_log,
                    approach=submission.approach,
                    optimal_solution=task.optimal_solution,
                )
                logger.info(f"Final score: {scoring_result.final_score:.3f}")

                validity_check = self.validity_checker.check_validity(
                    property_results=property_results,
                    execution_log=execution_log,
                )
                logger.info(f"Valid solution: {validity_check.is_valid_solution}")
            except Exception as e:
                error_msg = f"Scoring computation error: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
                # Use default zero scores
                from benchmark.models.results import ScoringResult, ValidityCheck

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

            # Calculate total time
            total_time = time.time() - start_time

            # Build final result
            success = validity_check.is_valid_solution and len(errors) == 0
            
            result = BenchmarkResult(
                run_id=run_id,
                timestamp=timestamp,
                task_id=task.task_id,
                testee_id=submission.testee_id,
                testee_type=submission.testee_type,
                success=success,
                property_results=property_results,
                scoring=scoring_result,
                validity=validity_check,
                metrics=ExecutionMetrics(
                    infrastructure_provision_time=provision_time,
                    config_execution_time=config_time,
                    convergence_time=convergence_time,
                    evaluation_time=evaluation_time,
                    total_time=total_time,
                ),
                execution_log=[
                    f"{entry.timestamp.isoformat()} | {entry.node} | {entry.command} | {'✓' if entry.success else '✗'}"
                    for entry in execution_log
                ],
                errors=errors,
            )

            logger.info(f"Benchmark run complete: {run_id} (success={success})")
            return result

        finally:
            # ============================================================
            # STEP 8: Teardown (ALWAYS CALLED)
            # ============================================================
            if topology_id:
                logger.info("Step 8: Tearing down infrastructure")
                try:
                    teardown_success = self.infrastructure.teardown(topology_id)
                    if teardown_success:
                        logger.info(f"Infrastructure teardown successful: {topology_id}")
                    else:
                        logger.warning(
                            f"Infrastructure teardown reported failure: {topology_id}"
                        )
                except Exception as e:
                    logger.error(f"Infrastructure teardown error: {str(e)}")
                    # Teardown errors are logged but don't affect the result

    def _build_error_result(
        self,
        run_id: str,
        timestamp: datetime,
        task: TaskDefinition,
        submission: Submission,
        errors: List[str],
        execution_log: List[ExecutionLogEntry],
        property_results: List[PropertyEvaluationResult],
        metrics: ExecutionMetrics,
        topology_id: Optional[str] = None,
    ) -> BenchmarkResult:
        """
        Build an error result when the benchmark fails early.
        
        Args:
            run_id: Unique run identifier
            timestamp: Run start timestamp
            task: Task definition
            submission: Testee submission
            errors: List of error messages
            execution_log: Execution log entries
            property_results: Property evaluation results (may be empty)
            metrics: Execution metrics
            topology_id: Topology ID for teardown (if available)
            
        Returns:
            BenchmarkResult indicating failure
        """
        from benchmark.models.results import ScoringResult, ValidityCheck

        # Attempt teardown if topology was created
        if topology_id:
            try:
                self.infrastructure.teardown(topology_id)
            except Exception:
                pass  # Best effort

        # Build error result with zero scores
        return BenchmarkResult(
            run_id=run_id,
            timestamp=timestamp,
            task_id=task.task_id,
            testee_id=submission.testee_id,
            testee_type=submission.testee_type,
            success=False,
            property_results=property_results,
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
            metrics=metrics,
            execution_log=[
                f"{entry.timestamp.isoformat()} | {entry.node} | {entry.command} | {'✓' if entry.success else '✗'}"
                for entry in execution_log
            ],
            errors=errors,
        )

