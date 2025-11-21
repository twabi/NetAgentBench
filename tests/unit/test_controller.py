"""
Unit tests for BenchmarkController.

Tests the main orchestration logic using mocked dependencies.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, call
from benchmark.models.task import (
    TaskDefinition,
    TopologySpecification,
    Node,
    NodeType,
    Platform,
    IntentSpecification,
    Property,
    PropertyType,
    EvaluationProcedure,
    ConvergenceConfig,
    OptimalSolution,
)
from benchmark.models.submission import (
    Submission,
    Approach,
    CommandSequence,
)
from benchmark.models.results import (
    PropertyEvaluationResult,
    ScoringResult,
    ValidityCheck,
    ExecutionMetrics,
    BenchmarkResult,
)
from benchmark.executor.command import ExecutionLogEntry


class TestBenchmarkControllerInitialization:
    """Test BenchmarkController initialization"""

    def test_controller_initializes_with_default_dependencies(self):
        """Test that controller can be initialized with default dependencies"""
        from benchmark.controller import BenchmarkController

        controller = BenchmarkController()

        # Should have all required components
        assert controller.infrastructure is not None
        assert controller.command_executor is not None
        assert controller.observation_executor is not None
        assert controller.property_evaluator is not None
        assert controller.scoring_calculator is not None
        assert controller.validity_checker is not None

    def test_controller_initializes_with_custom_dependencies(self):
        """Test that controller can be initialized with custom dependencies"""
        from benchmark.controller import BenchmarkController

        # Create mock dependencies
        mock_infra = Mock()
        mock_cmd_exec = Mock()
        mock_obs_exec = Mock()
        mock_prop_eval = Mock()
        mock_scoring = Mock()
        mock_validity = Mock()

        controller = BenchmarkController(
            infrastructure=mock_infra,
            command_executor=mock_cmd_exec,
            observation_executor=mock_obs_exec,
            property_evaluator=mock_prop_eval,
            scoring_calculator=mock_scoring,
            validity_checker=mock_validity,
        )

        # Should use provided dependencies
        assert controller.infrastructure is mock_infra
        assert controller.command_executor is mock_cmd_exec
        assert controller.observation_executor is mock_obs_exec
        assert controller.property_evaluator is mock_prop_eval
        assert controller.scoring_calculator is mock_scoring
        assert controller.validity_checker is mock_validity


class TestBenchmarkControllerRun:
    """Test the main run() method orchestration"""

    @pytest.fixture
    def simple_task(self):
        """Create a simple task definition for testing"""
        return TaskDefinition(
            task_id="test_task_001",
            description="Test task",
            platform=Platform.FRR,
            topology=TopologySpecification(
                nodes=[
                    Node(name="R1", type=NodeType.ROUTER, image="alpine:latest", platform=Platform.FRR)
                ],
                links=[],
            ),
            intent=IntentSpecification(
                properties=[
                    Property(
                        id="prop1",
                        type=PropertyType.REACHABILITY,
                        description="Test property",
                        evaluation=EvaluationProcedure(
                            method="exec_and_parse",
                            target_node="R1",
                            command="echo test",
                            parser="text",
                            success_condition={"contains_text": "test"},
                        ),
                    )
                ]
            ),
            convergence=ConvergenceConfig(timeout_seconds=5, check_interval_seconds=1),
            optimal_solution=OptimalSolution(command_count=1, description="Optimal"),
        )

    @pytest.fixture
    def simple_submission(self):
        """Create a simple submission for testing"""
        return Submission(
            task_id="test_task_001",
            testee_id="test_testee",
            testee_type="test",
            approach=Approach(
                description="Test approach",
                commands=[
                    CommandSequence(node="R1", commands=["echo hello"])
                ],
            ),
        )

    def test_run_generates_unique_run_id(self, simple_task, simple_submission):
        """Test that each run generates a unique run_id"""
        from benchmark.controller import BenchmarkController

        # Create controller with all mocked dependencies
        mock_infra = Mock()
        mock_infra.provision.return_value = "topo_123"
        mock_infra.is_ready.return_value = True
        mock_infra.teardown.return_value = True

        mock_cmd_exec = Mock()
        mock_cmd_exec.apply_approach.return_value = []

        mock_prop_eval = Mock()
        mock_prop_eval.evaluate_all_properties.return_value = [
            PropertyEvaluationResult(
                property_id="prop1",
                satisfied=True,
                observation_raw="test",
                observation_parsed=None,
                evaluation_time_seconds=0.1,
                error_message=None,
            )
        ]

        mock_scoring = Mock()
        mock_scoring.compute_all_scores.return_value = ScoringResult(
            completeness=1.0,
            robustness=1.0,
            syntactic_validity=1.0,
            efficiency=1.0,
            final_score=1.0,
            weights={"completeness": 0.4, "robustness": 0.3, "syntactic_validity": 0.2, "efficiency": 0.1},
        )

        mock_validity = Mock()
        mock_validity.check_validity.return_value = ValidityCheck(
            is_valid_solution=True,
            condition_a_syntactic=True,
            condition_b_semantic=True,
        )

        controller = BenchmarkController(
            infrastructure=mock_infra,
            command_executor=mock_cmd_exec,
            property_evaluator=mock_prop_eval,
            scoring_calculator=mock_scoring,
            validity_checker=mock_validity,
        )

        # Run twice
        result1 = controller.run(simple_task, simple_submission)
        result2 = controller.run(simple_task, simple_submission)

        # Should have different run_ids
        assert result1.run_id != result2.run_id
        assert result1.run_id.startswith("run_")
        assert result2.run_id.startswith("run_")

    def test_run_successful_flow(self, simple_task, simple_submission):
        """Test successful execution flow through all steps"""
        from benchmark.controller import BenchmarkController

        # Create mocked dependencies
        mock_infra = Mock()
        mock_infra.provision.return_value = "topo_123"
        mock_infra.is_ready.return_value = True
        mock_infra.teardown.return_value = True

        mock_cmd_exec = Mock()
        execution_log = [
            ExecutionLogEntry(
                timestamp=datetime.now(),
                node="R1",
                command="echo hello",
                success=True,
                stdout="hello",
                stderr="",
                exit_code=0,
                execution_time=0.1,
            )
        ]
        mock_cmd_exec.apply_approach.return_value = execution_log

        mock_prop_eval = Mock()
        property_results = [
            PropertyEvaluationResult(
                property_id="prop1",
                satisfied=True,
                observation_raw="test",
                observation_parsed=None,
                evaluation_time_seconds=0.1,
                error_message=None,
            )
        ]
        mock_prop_eval.evaluate_all_properties.return_value = property_results

        mock_scoring = Mock()
        scoring_result = ScoringResult(
            completeness=1.0,
            robustness=1.0,
            syntactic_validity=1.0,
            efficiency=1.0,
            final_score=1.0,
            weights={"completeness": 0.4, "robustness": 0.3, "syntactic_validity": 0.2, "efficiency": 0.1},
        )
        mock_scoring.compute_all_scores.return_value = scoring_result

        mock_validity = Mock()
        validity_check = ValidityCheck(
            is_valid_solution=True,
            condition_a_syntactic=True,
            condition_b_semantic=True,
        )
        mock_validity.check_validity.return_value = validity_check

        controller = BenchmarkController(
            infrastructure=mock_infra,
            command_executor=mock_cmd_exec,
            property_evaluator=mock_prop_eval,
            scoring_calculator=mock_scoring,
            validity_checker=mock_validity,
        )

        # Run benchmark
        result = controller.run(simple_task, simple_submission)

        # Verify all components were called
        mock_infra.provision.assert_called_once_with(simple_task.topology)
        mock_infra.is_ready.assert_called_once_with("topo_123")
        mock_cmd_exec.apply_approach.assert_called_once()
        mock_prop_eval.evaluate_all_properties.assert_called_once()
        mock_scoring.compute_all_scores.assert_called_once()
        mock_validity.check_validity.assert_called_once()
        mock_infra.teardown.assert_called_once_with("topo_123")

        # Verify result structure
        assert isinstance(result, BenchmarkResult)
        assert result.task_id == "test_task_001"
        assert result.testee_id == "test_testee"
        assert result.testee_type == "test"
        assert result.success is True
        assert result.property_results == property_results
        assert result.scoring == scoring_result
        assert result.validity == validity_check
        assert isinstance(result.metrics, ExecutionMetrics)
        assert result.metrics.total_time > 0

    def test_run_infrastructure_provision_failure(self, simple_task, simple_submission):
        """Test that provision failure is handled gracefully"""
        from benchmark.controller import BenchmarkController

        # Mock infrastructure that fails to provision
        mock_infra = Mock()
        mock_infra.provision.side_effect = Exception("Failed to provision")

        controller = BenchmarkController(infrastructure=mock_infra)

        # Run should not crash
        result = controller.run(simple_task, simple_submission)

        # Should return error result
        assert isinstance(result, BenchmarkResult)
        assert result.success is False
        assert len(result.errors) > 0
        assert "Failed to provision" in result.errors[0]

    def test_run_infrastructure_not_ready_timeout(self, simple_task, simple_submission):
        """Test that infrastructure ready timeout is handled"""
        from benchmark.controller import BenchmarkController

        # Mock infrastructure that provisions but never becomes ready
        mock_infra = Mock()
        mock_infra.provision.return_value = "topo_123"
        mock_infra.is_ready.return_value = False  # Always not ready
        mock_infra.teardown.return_value = True

        controller = BenchmarkController(infrastructure=mock_infra)

        # Run should not hang indefinitely
        result = controller.run(simple_task, simple_submission)

        # Should return error result
        assert isinstance(result, BenchmarkResult)
        assert result.success is False
        assert len(result.errors) > 0
        # Should attempt teardown (may be called multiple times - in error handler and finally)
        assert mock_infra.teardown.called
        mock_infra.teardown.assert_called_with("topo_123")

    def test_run_configuration_failure_continues_to_evaluation(self, simple_task, simple_submission):
        """Test that configuration failures don't abort the benchmark"""
        from benchmark.controller import BenchmarkController

        # Mock executor that fails
        mock_infra = Mock()
        mock_infra.provision.return_value = "topo_123"
        mock_infra.is_ready.return_value = True
        mock_infra.teardown.return_value = True

        mock_cmd_exec = Mock()
        # Return execution log with failures
        execution_log = [
            ExecutionLogEntry(
                timestamp=datetime.now(),
                node="R1",
                command="bad command",
                success=False,
                stdout="",
                stderr="command not found",
                exit_code=1,
                execution_time=0.1,
            )
        ]
        mock_cmd_exec.apply_approach.return_value = execution_log

        mock_prop_eval = Mock()
        mock_prop_eval.evaluate_all_properties.return_value = [
            PropertyEvaluationResult(
                property_id="prop1",
                satisfied=False,
                observation_raw="",
                observation_parsed=None,
                evaluation_time_seconds=0.1,
                error_message="Property check failed",
            )
        ]

        mock_scoring = Mock()
        mock_scoring.compute_all_scores.return_value = ScoringResult(
            completeness=0.0,
            robustness=0.0,
            syntactic_validity=0.0,
            efficiency=None,
            final_score=0.0,
            weights={"completeness": 0.4, "robustness": 0.3, "syntactic_validity": 0.3},
        )

        mock_validity = Mock()
        mock_validity.check_validity.return_value = ValidityCheck(
            is_valid_solution=False,
            condition_a_syntactic=False,
            condition_b_semantic=False,
        )

        controller = BenchmarkController(
            infrastructure=mock_infra,
            command_executor=mock_cmd_exec,
            property_evaluator=mock_prop_eval,
            scoring_calculator=mock_scoring,
            validity_checker=mock_validity,
        )

        # Run should complete
        result = controller.run(simple_task, simple_submission)

        # Should still evaluate properties and compute scores
        mock_prop_eval.evaluate_all_properties.assert_called_once()
        mock_scoring.compute_all_scores.assert_called_once()
        mock_validity.check_validity.assert_called_once()

        # Result should indicate failure but have all data
        assert result.success is False
        assert result.validity.is_valid_solution is False
        assert result.scoring.final_score == 0.0

    def test_run_teardown_always_called_on_success(self, simple_task, simple_submission):
        """Test that teardown is always called even on success"""
        from benchmark.controller import BenchmarkController

        mock_infra = Mock()
        mock_infra.provision.return_value = "topo_123"
        mock_infra.is_ready.return_value = True
        mock_infra.teardown.return_value = True

        mock_cmd_exec = Mock()
        mock_cmd_exec.apply_approach.return_value = []

        mock_prop_eval = Mock()
        mock_prop_eval.evaluate_all_properties.return_value = []

        mock_scoring = Mock()
        mock_scoring.compute_all_scores.return_value = ScoringResult(
            completeness=1.0,
            robustness=1.0,
            syntactic_validity=1.0,
            efficiency=1.0,
            final_score=1.0,
            weights={"completeness": 0.4, "robustness": 0.3, "syntactic_validity": 0.2, "efficiency": 0.1},
        )

        mock_validity = Mock()
        mock_validity.check_validity.return_value = ValidityCheck(
            is_valid_solution=True,
            condition_a_syntactic=True,
            condition_b_semantic=True,
        )

        controller = BenchmarkController(
            infrastructure=mock_infra,
            command_executor=mock_cmd_exec,
            property_evaluator=mock_prop_eval,
            scoring_calculator=mock_scoring,
            validity_checker=mock_validity,
        )

        result = controller.run(simple_task, simple_submission)

        # Teardown must be called
        mock_infra.teardown.assert_called_once_with("topo_123")
        assert result.success is True

    def test_run_teardown_always_called_on_failure(self, simple_task, simple_submission):
        """Test that teardown is always called even when evaluation fails"""
        from benchmark.controller import BenchmarkController

        mock_infra = Mock()
        mock_infra.provision.return_value = "topo_123"
        mock_infra.is_ready.return_value = True
        mock_infra.teardown.return_value = True

        mock_cmd_exec = Mock()
        mock_cmd_exec.apply_approach.return_value = []

        # Mock property evaluator that raises exception
        mock_prop_eval = Mock()
        mock_prop_eval.evaluate_all_properties.side_effect = Exception("Evaluation crashed")

        controller = BenchmarkController(
            infrastructure=mock_infra,
            command_executor=mock_cmd_exec,
            property_evaluator=mock_prop_eval,
        )

        result = controller.run(simple_task, simple_submission)

        # Teardown must still be called
        mock_infra.teardown.assert_called_once_with("topo_123")
        assert result.success is False
        assert len(result.errors) > 0

    def test_run_teardown_failure_doesnt_crash(self, simple_task, simple_submission):
        """Test that teardown failure is logged but doesn't crash the run"""
        from benchmark.controller import BenchmarkController

        mock_infra = Mock()
        mock_infra.provision.return_value = "topo_123"
        mock_infra.is_ready.return_value = True
        mock_infra.teardown.side_effect = Exception("Teardown failed")

        mock_cmd_exec = Mock()
        mock_cmd_exec.apply_approach.return_value = []

        mock_prop_eval = Mock()
        mock_prop_eval.evaluate_all_properties.return_value = []

        mock_scoring = Mock()
        mock_scoring.compute_all_scores.return_value = ScoringResult(
            completeness=1.0,
            robustness=1.0,
            syntactic_validity=1.0,
            efficiency=1.0,
            final_score=1.0,
            weights={"completeness": 0.4, "robustness": 0.3, "syntactic_validity": 0.2, "efficiency": 0.1},
        )

        mock_validity = Mock()
        mock_validity.check_validity.return_value = ValidityCheck(
            is_valid_solution=True,
            condition_a_syntactic=True,
            condition_b_semantic=True,
        )

        controller = BenchmarkController(
            infrastructure=mock_infra,
            command_executor=mock_cmd_exec,
            property_evaluator=mock_prop_eval,
            scoring_calculator=mock_scoring,
            validity_checker=mock_validity,
        )

        # Should not crash
        result = controller.run(simple_task, simple_submission)

        # Should return result (teardown failure is logged but not critical)
        assert isinstance(result, BenchmarkResult)
        # The run itself was successful, teardown failure is just logged
        assert result.success is True


class TestBenchmarkControllerMetrics:
    """Test execution metrics tracking"""

    @pytest.fixture
    def simple_task(self):
        """Create a simple task definition for testing"""
        return TaskDefinition(
            task_id="test_task_001",
            description="Test task",
            platform=Platform.FRR,
            topology=TopologySpecification(
                nodes=[
                    Node(name="R1", type=NodeType.ROUTER, image="alpine:latest", platform=Platform.FRR)
                ],
                links=[],
            ),
            intent=IntentSpecification(
                properties=[
                    Property(
                        id="prop1",
                        type=PropertyType.REACHABILITY,
                        description="Test property",
                        evaluation=EvaluationProcedure(
                            method="exec_and_parse",
                            target_node="R1",
                            command="echo test",
                            parser="text",
                            success_condition={"contains_text": "test"},
                        ),
                    )
                ]
            ),
            convergence=ConvergenceConfig(timeout_seconds=1, check_interval_seconds=1),
        )

    @pytest.fixture
    def simple_submission(self):
        """Create a simple submission for testing"""
        return Submission(
            task_id="test_task_001",
            testee_id="test_testee",
            testee_type="test",
            approach=Approach(
                description="Test approach",
                commands=[
                    CommandSequence(node="R1", commands=["echo hello"])
                ],
            ),
        )

    def test_run_tracks_execution_metrics(self, simple_task, simple_submission):
        """Test that execution metrics are tracked correctly"""
        from benchmark.controller import BenchmarkController

        # Create mocked dependencies
        mock_infra = Mock()
        mock_infra.provision.return_value = "topo_123"
        mock_infra.is_ready.return_value = True
        mock_infra.teardown.return_value = True

        mock_cmd_exec = Mock()
        mock_cmd_exec.apply_approach.return_value = []

        mock_prop_eval = Mock()
        mock_prop_eval.evaluate_all_properties.return_value = []

        mock_scoring = Mock()
        mock_scoring.compute_all_scores.return_value = ScoringResult(
            completeness=1.0,
            robustness=1.0,
            syntactic_validity=1.0,
            efficiency=1.0,
            final_score=1.0,
            weights={"completeness": 0.4, "robustness": 0.3, "syntactic_validity": 0.2, "efficiency": 0.1},
        )

        mock_validity = Mock()
        mock_validity.check_validity.return_value = ValidityCheck(
            is_valid_solution=True,
            condition_a_syntactic=True,
            condition_b_semantic=True,
        )

        controller = BenchmarkController(
            infrastructure=mock_infra,
            command_executor=mock_cmd_exec,
            property_evaluator=mock_prop_eval,
            scoring_calculator=mock_scoring,
            validity_checker=mock_validity,
        )

        result = controller.run(simple_task, simple_submission)

        # Verify metrics are populated
        assert result.metrics.infrastructure_provision_time >= 0
        assert result.metrics.config_execution_time >= 0
        assert result.metrics.convergence_time >= 0
        assert result.metrics.evaluation_time >= 0
        assert result.metrics.total_time >= 0
        
        # Total time should be sum of all phases (approximately)
        assert result.metrics.total_time >= result.metrics.infrastructure_provision_time
        assert result.metrics.total_time >= result.metrics.config_execution_time

