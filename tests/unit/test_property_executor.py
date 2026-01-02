"""
Unit tests for PropertyExecutor.

Tests property-based task execution with aggregate scoring.
"""
import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch
from benchmark.property_executor import PropertyExecutor
from benchmark.models.task import TaskDefinition, PropertyType
from benchmark.models.submission import Submission, Approach, CommandSequence
from benchmark.models.results import (
    BenchmarkResult,
    PropertyExecutionResult,
    BenchmarkRunResult,
    ScoringResult,
    ValidityCheck,
    ExecutionMetrics,
)


class TestPropertyExecutor:
    """Test PropertyExecutor class."""

    def create_mock_task(self, task_id: str) -> TaskDefinition:
        """Create a minimal mock task for testing."""
        return Mock(spec=TaskDefinition, task_id=task_id)

    def create_mock_submission(self, task_id: str) -> Submission:
        """Create a minimal mock submission for testing."""
        return Submission(
            task_id=task_id,
            testee_id="test_testee",
            testee_type="human",
            approach=Approach(
                description="Test approach",
                commands=[
                    CommandSequence(node="R1", commands=["echo test"]),
                ],
            ),
        )

    def create_mock_benchmark_result(
        self, task_id: str, final_score: float = 0.8, success: bool = True
    ) -> BenchmarkResult:
        """Create a mock BenchmarkResult for testing."""
        return BenchmarkResult(
            run_id=f"run_{task_id}",
            timestamp=datetime.now(),
            task_id=task_id,
            testee_id="test_testee",
            testee_type="human",
            success=success,
            property_results=[],
            scoring=ScoringResult(
                completeness=0.8,
                robustness=0.7,
                syntactic_validity=0.9,
                efficiency=None,
                final_score=final_score,
                weights={},
            ),
            validity=ValidityCheck(
                is_valid_solution=success,
                condition_a_syntactic=True,
                condition_b_semantic=success,
            ),
            metrics=ExecutionMetrics(
                infrastructure_provision_time=5.0,
                config_execution_time=2.0,
                convergence_time=30.0,
                evaluation_time=3.0,
                total_time=40.0,
            ),
            execution_log=[],
            errors=[],
        )

    def test_create_property_executor(self):
        """Test creating a PropertyExecutor instance."""
        mock_controller = Mock()
        mock_repository = Mock()

        executor = PropertyExecutor(
            controller=mock_controller, repository=mock_repository
        )

        assert executor.controller == mock_controller
        assert executor.repository == mock_repository

    def test_run_property_tasks_single_task(self):
        """Test running a single task for a property type."""
        mock_controller = Mock()
        mock_repository = Mock()

        # Setup repository to return one task
        task = self.create_mock_task("task_1")
        mock_repository.load_tasks_by_property.return_value = [task]

        # Setup controller to return a result
        result = self.create_mock_benchmark_result("task_1", final_score=0.85)
        mock_controller.run.return_value = result

        # Create submission generator
        def submission_generator(task):
            return self.create_mock_submission(task.task_id)

        executor = PropertyExecutor(
            controller=mock_controller, repository=mock_repository
        )

        # Run the test
        prop_result = executor.run_property_tasks(
            property_type="reachability", submission_generator=submission_generator
        )

        # Verify
        assert prop_result.property_type == "reachability"
        assert prop_result.total_tasks == 1
        assert prop_result.successful_tasks == 1
        assert len(prop_result.results) == 1
        assert prop_result.average_score == 0.85
        mock_repository.load_tasks_by_property.assert_called_once_with(
            "reachability", limit=None, platform=None
        )
        mock_controller.run.assert_called_once()

    def test_run_property_tasks_multiple_tasks(self):
        """Test running multiple tasks for a property type."""
        mock_controller = Mock()
        mock_repository = Mock()

        # Setup repository to return multiple tasks
        tasks = [
            self.create_mock_task("task_1"),
            self.create_mock_task("task_2"),
            self.create_mock_task("task_3"),
        ]
        mock_repository.load_tasks_by_property.return_value = tasks

        # Setup controller to return results with different scores
        results = [
            self.create_mock_benchmark_result("task_1", final_score=0.9, success=True),
            self.create_mock_benchmark_result("task_2", final_score=0.7, success=True),
            self.create_mock_benchmark_result("task_3", final_score=0.8, success=True),
        ]
        mock_controller.run.side_effect = results

        def submission_generator(task):
            return self.create_mock_submission(task.task_id)

        executor = PropertyExecutor(
            controller=mock_controller, repository=mock_repository
        )

        prop_result = executor.run_property_tasks(
            property_type="bgp_configuration", submission_generator=submission_generator
        )

        # Verify
        assert prop_result.property_type == "bgp_configuration"
        assert prop_result.total_tasks == 3
        assert prop_result.successful_tasks == 3
        assert len(prop_result.results) == 3
        # Average score: (0.9 + 0.7 + 0.8) / 3 = 0.8
        assert abs(prop_result.average_score - 0.8) < 0.001
        assert mock_controller.run.call_count == 3

    def test_run_property_tasks_with_limit(self):
        """Test running tasks with a limit parameter."""
        mock_controller = Mock()
        mock_repository = Mock()

        # Repository returns limited tasks
        tasks = [
            self.create_mock_task("task_1"),
            self.create_mock_task("task_2"),
        ]
        mock_repository.load_tasks_by_property.return_value = tasks

        results = [
            self.create_mock_benchmark_result("task_1", final_score=0.8),
            self.create_mock_benchmark_result("task_2", final_score=0.75),
        ]
        mock_controller.run.side_effect = results

        def submission_generator(task):
            return self.create_mock_submission(task.task_id)

        executor = PropertyExecutor(
            controller=mock_controller, repository=mock_repository
        )

        prop_result = executor.run_property_tasks(
            property_type="ospf_configuration",
            submission_generator=submission_generator,
            limit=2,
        )

        # Verify limit was passed to repository
        mock_repository.load_tasks_by_property.assert_called_once_with(
            "ospf_configuration", limit=2, platform=None
        )
        assert prop_result.total_tasks == 2

    def test_run_property_tasks_with_failures(self):
        """Test running tasks where some fail."""
        mock_controller = Mock()
        mock_repository = Mock()

        tasks = [
            self.create_mock_task("task_1"),
            self.create_mock_task("task_2"),
            self.create_mock_task("task_3"),
        ]
        mock_repository.load_tasks_by_property.return_value = tasks

        # Mix of successful and failed tasks
        results = [
            self.create_mock_benchmark_result("task_1", final_score=0.9, success=True),
            self.create_mock_benchmark_result(
                "task_2", final_score=0.3, success=False
            ),
            self.create_mock_benchmark_result("task_3", final_score=0.8, success=True),
        ]
        mock_controller.run.side_effect = results

        def submission_generator(task):
            return self.create_mock_submission(task.task_id)

        executor = PropertyExecutor(
            controller=mock_controller, repository=mock_repository
        )

        prop_result = executor.run_property_tasks(
            property_type="reachability", submission_generator=submission_generator
        )

        assert prop_result.total_tasks == 3
        assert prop_result.successful_tasks == 2  # Only 2 successful
        # Average includes failed task: (0.9 + 0.3 + 0.8) / 3 = 0.667
        assert abs(prop_result.average_score - 0.667) < 0.01

    def test_run_property_tasks_computes_aggregate_metrics(self):
        """Test that aggregate metrics are computed correctly."""
        mock_controller = Mock()
        mock_repository = Mock()

        tasks = [
            self.create_mock_task("task_1"),
            self.create_mock_task("task_2"),
        ]
        mock_repository.load_tasks_by_property.return_value = tasks

        # Create results with known metrics
        result1 = self.create_mock_benchmark_result("task_1", final_score=0.8)
        result1.scoring.completeness = 0.9
        result1.scoring.robustness = 0.7
        result1.scoring.syntactic_validity = 0.95

        result2 = self.create_mock_benchmark_result("task_2", final_score=0.75)
        result2.scoring.completeness = 0.8
        result2.scoring.robustness = 0.6
        result2.scoring.syntactic_validity = 0.85

        mock_controller.run.side_effect = [result1, result2]

        def submission_generator(task):
            return self.create_mock_submission(task.task_id)

        executor = PropertyExecutor(
            controller=mock_controller, repository=mock_repository
        )

        prop_result = executor.run_property_tasks(
            property_type="reachability", submission_generator=submission_generator
        )

        # Check aggregate metrics
        assert "avg_completeness" in prop_result.aggregate_metrics
        assert "avg_robustness" in prop_result.aggregate_metrics
        assert "avg_syntactic_validity" in prop_result.aggregate_metrics

        # Verify values
        assert abs(prop_result.aggregate_metrics["avg_completeness"] - 0.85) < 0.001
        assert abs(prop_result.aggregate_metrics["avg_robustness"] - 0.65) < 0.001
        assert abs(prop_result.aggregate_metrics["avg_syntactic_validity"] - 0.90) < 0.001

    def test_run_property_tasks_empty_task_list(self):
        """Test running with no tasks."""
        mock_controller = Mock()
        mock_repository = Mock()

        mock_repository.load_tasks_by_property.return_value = []

        def submission_generator(task):
            return self.create_mock_submission(task.task_id)

        executor = PropertyExecutor(
            controller=mock_controller, repository=mock_repository
        )

        prop_result = executor.run_property_tasks(
            property_type="reachability", submission_generator=submission_generator
        )

        assert prop_result.total_tasks == 0
        assert prop_result.successful_tasks == 0
        assert len(prop_result.results) == 0
        assert prop_result.average_score == 0.0
        mock_controller.run.assert_not_called()


class TestPropertyExecutorRunAll:
    """Test PropertyExecutor.run_all_tasks() method."""

    def create_mock_task(self, task_id: str) -> TaskDefinition:
        """Create a minimal mock task for testing."""
        return Mock(spec=TaskDefinition, task_id=task_id)

    def create_mock_submission(self, task_id: str) -> Submission:
        """Create a minimal mock submission for testing."""
        return Submission(
            task_id=task_id,
            testee_id="test_testee",
            testee_type="human",
            approach=Approach(
                description="Test approach",
                commands=[
                    CommandSequence(node="R1", commands=["echo test"]),
                ],
            ),
        )

    def create_mock_benchmark_result(
        self, task_id: str, final_score: float = 0.8
    ) -> BenchmarkResult:
        """Create a mock BenchmarkResult for testing."""
        return BenchmarkResult(
            run_id=f"run_{task_id}",
            timestamp=datetime.now(),
            task_id=task_id,
            testee_id="test_testee",
            testee_type="human",
            success=True,
            property_results=[],
            scoring=ScoringResult(
                completeness=0.8,
                robustness=0.7,
                syntactic_validity=0.9,
                efficiency=None,
                final_score=final_score,
                weights={},
            ),
            validity=ValidityCheck(
                is_valid_solution=True,
                condition_a_syntactic=True,
                condition_b_semantic=True,
            ),
            metrics=ExecutionMetrics(
                infrastructure_provision_time=5.0,
                config_execution_time=2.0,
                convergence_time=30.0,
                evaluation_time=3.0,
                total_time=40.0,
            ),
            execution_log=[],
            errors=[],
        )

    @patch("benchmark.property_executor.PropertyType")
    def test_run_all_tasks_across_all_properties(self, mock_property_type):
        """Test running tasks across all property types dynamically."""
        # Mock PropertyType enum to return specific values
        mock_property_type.__iter__ = Mock(
            return_value=iter(
                [
                    Mock(value="reachability"),
                    Mock(value="bgp_configuration"),
                    Mock(value="ospf_configuration"),
                ]
            )
        )

        mock_controller = Mock()
        mock_repository = Mock()

        # Setup repository to return different tasks for each property
        def load_tasks_side_effect(property_type, limit=None, platform=None):
            if property_type == "reachability":
                return [
                    self.create_mock_task("reach_1"),
                    self.create_mock_task("reach_2"),
                ]
            elif property_type == "bgp_configuration":
                return [self.create_mock_task("bgp_1")]
            elif property_type == "ospf_configuration":
                return [
                    self.create_mock_task("ospf_1"),
                    self.create_mock_task("ospf_2"),
                ]
            return []

        mock_repository.load_tasks_by_property.side_effect = load_tasks_side_effect

        # Setup controller to return results
        def run_side_effect(task, submission):
            scores = {
                "reach_1": 0.9,
                "reach_2": 0.8,
                "bgp_1": 0.7,
                "ospf_1": 0.85,
                "ospf_2": 0.75,
            }
            return self.create_mock_benchmark_result(
                task.task_id, final_score=scores.get(task.task_id, 0.8)
            )

        mock_controller.run.side_effect = run_side_effect

        def submission_generator(task):
            return self.create_mock_submission(task.task_id)

        executor = PropertyExecutor(
            controller=mock_controller, repository=mock_repository
        )

        # Run all tasks
        run_result = executor.run_all_tasks(submission_generator=submission_generator)

        # Verify
        assert isinstance(run_result, BenchmarkRunResult)
        assert len(run_result.property_results) == 3
        assert "reachability" in run_result.property_results
        assert "bgp_configuration" in run_result.property_results
        assert "ospf_configuration" in run_result.property_results

        # Total tasks: 2 + 1 + 2 = 5
        assert run_result.total_tasks == 5

        # Overall average: (0.9 + 0.8 + 0.7 + 0.85 + 0.75) / 5 = 0.8
        assert abs(run_result.overall_average_score - 0.8) < 0.001

        # Verify controller was called 5 times
        assert mock_controller.run.call_count == 5

    @patch("benchmark.property_executor.PropertyType")
    def test_run_all_tasks_with_limit(self, mock_property_type):
        """Test running all tasks with a global limit."""
        mock_property_type.__iter__ = Mock(
            return_value=iter(
                [
                    Mock(value="reachability"),
                    Mock(value="bgp_configuration"),
                ]
            )
        )

        mock_controller = Mock()
        mock_repository = Mock()

        # Return limited tasks
        def load_tasks_side_effect(property_type, limit=None, platform=None):
            if property_type == "reachability":
                return [self.create_mock_task("reach_1")]
            elif property_type == "bgp_configuration":
                return [self.create_mock_task("bgp_1")]
            return []

        mock_repository.load_tasks_by_property.side_effect = load_tasks_side_effect

        mock_controller.run.side_effect = lambda task, sub: (
            self.create_mock_benchmark_result(task.task_id, final_score=0.8)
        )

        def submission_generator(task):
            return self.create_mock_submission(task.task_id)

        executor = PropertyExecutor(
            controller=mock_controller, repository=mock_repository
        )

        run_result = executor.run_all_tasks(
            submission_generator=submission_generator, limit=1
        )

        # Limit was applied per property
        assert run_result.total_tasks == 2  # 1 per property
        assert mock_repository.load_tasks_by_property.call_count == 2

    @patch("benchmark.property_executor.PropertyType")
    def test_run_all_tasks_empty_results(self, mock_property_type):
        """Test running all tasks when no tasks are found."""
        mock_property_type.__iter__ = Mock(
            return_value=iter([Mock(value="reachability")])
        )

        mock_controller = Mock()
        mock_repository = Mock()
        mock_repository.load_tasks_by_property.return_value = []

        def submission_generator(task):
            return self.create_mock_submission(task.task_id)

        executor = PropertyExecutor(
            controller=mock_controller, repository=mock_repository
        )

        run_result = executor.run_all_tasks(submission_generator=submission_generator)

        assert run_result.total_tasks == 0
        assert run_result.overall_average_score == 0.0
        assert len(run_result.property_results) == 1
        assert run_result.property_results["reachability"].total_tasks == 0

    @patch("benchmark.property_executor.PropertyType")
    def test_run_all_tasks_testee_metadata(self, mock_property_type):
        """Test that testee metadata is extracted correctly."""
        mock_property_type.__iter__ = Mock(
            return_value=iter([Mock(value="reachability")])
        )

        mock_controller = Mock()
        mock_repository = Mock()

        mock_repository.load_tasks_by_property.return_value = [
            self.create_mock_task("task_1")
        ]

        result = self.create_mock_benchmark_result("task_1", final_score=0.8)
        result.testee_id = "gpt4_turbo"
        result.testee_type = "llm"
        mock_controller.run.return_value = result

        def submission_generator(task):
            sub = self.create_mock_submission(task.task_id)
            sub.testee_id = "gpt4_turbo"
            sub.testee_type = "llm"
            return sub

        executor = PropertyExecutor(
            controller=mock_controller, repository=mock_repository
        )

        run_result = executor.run_all_tasks(submission_generator=submission_generator)

        assert run_result.testee_id == "gpt4_turbo"
        assert run_result.testee_type == "llm"
