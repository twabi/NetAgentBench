"""
Property-based task executor for running benchmark tasks by property type.

This module implements the execution engine that runs multiple tasks
for a given property type and aggregates the results.
"""
import logging
import time
import uuid
from datetime import datetime
from typing import Callable, Optional, Dict, List
from benchmark.controller import BenchmarkController
from benchmark.task_repository import TaskRepository
from benchmark.storage import ResultsStorage
from benchmark.models.task import TaskDefinition, PropertyType
from benchmark.models.submission import Submission
from benchmark.models.results import (
    PropertyExecutionResult,
    BenchmarkResult,
    BenchmarkRunResult,
)

logger = logging.getLogger(__name__)


class PropertyExecutor:
    """
    Execute benchmark tasks organized by property type.
    
    This class orchestrates running multiple tasks for a property type
    (e.g., all reachability tasks) and aggregates the results with
    average scoring and aggregate metrics.
    """

    def __init__(
        self, 
        controller: BenchmarkController, 
        repository: TaskRepository,
        storage: Optional[ResultsStorage] = None
    ):
        """
        Initialize the PropertyExecutor.
        
        Args:
            controller: BenchmarkController for running individual tasks
            repository: TaskRepository for loading tasks
            storage: Optional ResultsStorage for saving individual runs
        """
        self.controller = controller
        self.repository = repository
        self.storage = storage

    def run_property_tasks(
        self,
        property_type: str,
        submission_generator: Callable[[TaskDefinition], Submission],
        limit: Optional[int] = None,
        platform: Optional[str] = None,
    ) -> PropertyExecutionResult:
        """
        Run all tasks for a specific property type.
        
        Args:
            property_type: Property type identifier (e.g., "reachability")
            submission_generator: Function that generates a submission for each task
            limit: Optional limit on number of tasks (None = all tasks)
            platform: Optional platform filter (frr, cisco_ios_xe, nokia_srl)
        
        Returns:
            PropertyExecutionResult with all individual results and aggregates
        """
        platform_str = f" for {platform}" if platform else ""
        logger.info(
            f"Running tasks for property type: {property_type}{platform_str} (limit={limit})"
        )

        # Load tasks from repository
        tasks = self.repository.load_tasks_by_property(property_type, limit=limit, platform=platform)
        logger.info(f"Loaded {len(tasks)} tasks for property type: {property_type}")

        if not tasks:
            logger.warning(f"No tasks found for property type: {property_type}")
            return PropertyExecutionResult(
                property_type=property_type,
                total_tasks=0,
                successful_tasks=0,
                results=[],
                average_score=0.0,
                aggregate_metrics={},
            )

        # Run each task
        results: List[BenchmarkResult] = []
        for i, task in enumerate(tasks, 1):
            logger.info(
                f"Running task {i}/{len(tasks)}: {task.task_id} ({property_type})"
            )

            try:
                # Generate submission for this task
                submission = submission_generator(task)

                # Run the benchmark
                result = self.controller.run(task, submission)
                results.append(result)
                
                # Save individual run if storage is available
                if self.storage:
                    try:
                        self.storage.save_result(result)
                    except Exception as e:
                        logger.warning(f"Failed to save result {result.run_id}: {e}")

                logger.info(
                    f"Task {task.task_id} completed: score={result.scoring.final_score:.3f}, "
                    f"valid={result.validity.is_valid_solution}"
                )
            except Exception as e:
                logger.error(
                    f"Task {task.task_id} failed: {e}. "
                    f"Skipping and continuing with next task."
                )
                # Create a failed result for this task
                from benchmark.models.results import (
                    BenchmarkResult,
                    ScoringResult,
                    ValidityCheck,
                    ExecutionMetrics,
                )
                from datetime import datetime
                import uuid
                
                failed_result = BenchmarkResult(
                    run_id=f"failed_{uuid.uuid4().hex[:8]}",
                    timestamp=datetime.now(),
                    task_id=task.task_id,
                    testee_id="unknown",
                    testee_type="llm",
                    success=False,
                    property_results=[],
                    scoring=ScoringResult(
                        completeness=0.0,
                        robustness=0.0,
                        syntactic_validity=0.0,
                        efficiency=None,
                        final_score=0.0,
                        weights={},
                    ),
                    validity=ValidityCheck(
                        is_valid_solution=False,
                        condition_a_syntactic=False,
                        condition_b_semantic=False,
                    ),
                    metrics=ExecutionMetrics(
                        infrastructure_provision_time=0.0,
                        config_execution_time=0.0,
                        convergence_time=0.0,
                        evaluation_time=0.0,
                        total_time=0.0,
                    ),
                    execution_log=[],
                    errors=[f"Task failed: {str(e)}"],
                )
                results.append(failed_result)
                
                # Save failed result if storage is available
                if self.storage:
                    try:
                        self.storage.save_result(failed_result)
                    except Exception as e:
                        logger.warning(f"Failed to save failed result {failed_result.run_id}: {e}")

        # Aggregate results
        aggregate_metrics = self._compute_aggregate_metrics(results)
        average_score = self._calculate_average_score(results)
        successful_tasks = sum(1 for r in results if r.validity.is_valid_solution)

        logger.info(
            f"Property type {property_type} complete: {successful_tasks}/{len(tasks)} successful, "
            f"average_score={average_score:.3f}"
        )

        return PropertyExecutionResult(
            property_type=property_type,
            total_tasks=len(tasks),
            successful_tasks=successful_tasks,
            results=results,
            average_score=average_score,
            aggregate_metrics=aggregate_metrics,
        )

    def _calculate_average_score(self, results: List[BenchmarkResult]) -> float:
        """
        Calculate the average final_score across all results.
        
        Args:
            results: List of BenchmarkResult objects
        
        Returns:
            Average final_score (0.0 if no results)
        """
        if not results:
            return 0.0

        total_score = sum(r.scoring.final_score for r in results)
        return total_score / len(results)

    def _compute_aggregate_metrics(
        self, results: List[BenchmarkResult]
    ) -> Dict[str, float]:
        """
        Compute aggregate metrics across all results.
        
        Computes averages for:
        - completeness
        - robustness
        - syntactic_validity
        - efficiency (if available)
        
        Args:
            results: List of BenchmarkResult objects
        
        Returns:
            Dictionary of aggregate metrics
        """
        if not results:
            return {}

        n = len(results)

        aggregate = {
            "avg_completeness": sum(r.scoring.completeness for r in results) / n,
            "avg_robustness": sum(r.scoring.robustness for r in results) / n,
            "avg_syntactic_validity": sum(
                r.scoring.syntactic_validity for r in results
            )
            / n,
        }

        # Efficiency is optional - only average if at least one result has it
        efficiencies = [
            r.scoring.efficiency for r in results if r.scoring.efficiency is not None
        ]
        if efficiencies:
            aggregate["avg_efficiency"] = sum(efficiencies) / len(efficiencies)

        return aggregate

    def run_all_tasks(
        self,
        submission_generator: Callable[[TaskDefinition], Submission],
        limit: Optional[int] = None,
    ) -> BenchmarkRunResult:
        """
        Run tasks across ALL property types dynamically.
        
        This method iterates over all values in the PropertyType enum and runs
        tasks for each property type, then aggregates all results into a single
        BenchmarkRunResult with an overall average score.
        
        Args:
            submission_generator: Function that generates a submission for each task
            limit: Optional limit on number of tasks per property type
        
        Returns:
            BenchmarkRunResult with results for all property types
        """
        logger.info("Running tasks across all property types")
        
        # Generate unique run ID and timestamp
        run_id = f"run_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        timestamp = datetime.now()
        start_time = time.time()
        
        # Get testee info from first submission (will be consistent across all)
        testee_id = "unknown"
        testee_type = "unknown"
        
        # Iterate over all property types dynamically
        property_results: Dict[str, PropertyExecutionResult] = {}
        all_benchmark_results: List[BenchmarkResult] = []
        
        for prop_value in PropertyType.__iter__():
            # Check if prop_value is an Enum member or the value itself
            if hasattr(prop_value, 'value'):
                property_type = prop_value.value
            else:
                property_type = prop_value

            if property_type not in TaskRepository.VALID_PROPERTY_TYPES:
                continue
            
            logger.info(f"Processing property type: {property_type}")
            
            # Skip property types that don't have tasks in the repository
            try:
                # Run tasks for this property type
                prop_result = self.run_property_tasks(
                    property_type=property_type,
                    submission_generator=submission_generator,
                    limit=limit,
                )
                
                # Only include if tasks were found OR keep empty result if desired
                # Currently we only include if tasks > 0 OR if we want to show 0/0 tasks
                property_results[property_type] = prop_result
                if prop_result.results:
                    all_benchmark_results.extend(prop_result.results)
                    
                    # Extract testee info from first result
                    if testee_id == "unknown":
                        testee_id = prop_result.results[0].testee_id
                        testee_type = prop_result.results[0].testee_type
                    
            except ValueError as e:
                # Property type not in repository - skip it
                logger.warning(f"Skipping property type {property_type}: {e}")
                continue
        
        # Calculate overall metrics
        total_tasks = sum(pr.total_tasks for pr in property_results.values())
        
        # Overall average score: mean of ALL individual task final_scores
        if all_benchmark_results:
            overall_average_score = sum(
                r.scoring.final_score for r in all_benchmark_results
            ) / len(all_benchmark_results)
        else:
            overall_average_score = 0.0
        
        execution_time = time.time() - start_time
        
        logger.info(
            f"Benchmark run {run_id} complete: {total_tasks} tasks, "
            f"overall_average_score={overall_average_score:.3f}, "
            f"time={execution_time:.1f}s"
        )
        
        return BenchmarkRunResult(
            run_id=run_id,
            testee_id=testee_id,
            testee_type=testee_type,
            timestamp=timestamp,
            property_results=property_results,
            total_tasks=total_tasks,
            overall_average_score=overall_average_score,
            execution_time_seconds=execution_time,
        )
