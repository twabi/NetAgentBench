"""
Unit tests for Results Pydantic models.
Following TDD: Write tests first for result-related models.
"""
import pytest
from pydantic import ValidationError
from datetime import datetime


class TestPropertyEvaluationResult:
    """Test PropertyEvaluationResult model"""

    def test_property_result_creation_satisfied(self):
        """Test creating a property result that is satisfied"""
        from benchmark.models.results import PropertyEvaluationResult

        result = PropertyEvaluationResult(
            property_id="p1_reachability",
            satisfied=True,
            observation_raw="PING 192.168.1.2: 3 packets transmitted, 3 received",
            observation_parsed={"packets_sent": 3, "packets_received": 3},
            evaluation_time_seconds=2.5,
        )

        assert result.property_id == "p1_reachability"
        assert result.satisfied is True
        assert "3 received" in result.observation_raw
        assert result.observation_parsed["packets_received"] == 3
        assert result.evaluation_time_seconds == 2.5
        assert result.error_message is None

    def test_property_result_creation_failed(self):
        """Test creating a property result that failed"""
        from benchmark.models.results import PropertyEvaluationResult

        result = PropertyEvaluationResult(
            property_id="p2_bgp_session",
            satisfied=False,
            observation_raw='{"state": "Idle"}',
            observation_parsed={"state": "Idle"},
            evaluation_time_seconds=1.2,
            error_message="BGP session not established",
        )

        assert result.satisfied is False
        assert result.error_message == "BGP session not established"

    def test_property_result_requires_property_id(self):
        """Test that property_id is required"""
        from benchmark.models.results import PropertyEvaluationResult

        with pytest.raises(ValidationError) as exc_info:
            PropertyEvaluationResult(
                satisfied=True,
                observation_raw="test",
                evaluation_time_seconds=1.0,
            )

        assert "property_id" in str(exc_info.value)

    def test_property_result_optional_fields(self):
        """Test that some fields are optional"""
        from benchmark.models.results import PropertyEvaluationResult

        # Minimal creation
        result = PropertyEvaluationResult(
            property_id="p1",
            satisfied=True,
            observation_raw="test output",
            evaluation_time_seconds=1.0,
        )

        assert result.observation_parsed is None
        assert result.error_message is None


class TestScoringResult:
    """Test ScoringResult model"""

    def test_scoring_result_complete(self):
        """Test creating a complete scoring result"""
        from benchmark.models.results import ScoringResult

        scoring = ScoringResult(
            completeness=1.0,
            robustness=1.0,
            syntactic_validity=1.0,
            efficiency=0.85,
            final_score=0.96,
            weights={"completeness": 0.4, "robustness": 0.3, "syntactic_validity": 0.2, "efficiency": 0.1},
        )

        assert scoring.completeness == 1.0
        assert scoring.robustness == 1.0
        assert scoring.syntactic_validity == 1.0
        assert scoring.efficiency == 0.85
        assert scoring.final_score == 0.96
        assert scoring.weights["completeness"] == 0.4

    def test_scoring_result_without_efficiency(self):
        """Test scoring result when efficiency is not available"""
        from benchmark.models.results import ScoringResult

        scoring = ScoringResult(
            completeness=0.67,
            robustness=0.0,
            syntactic_validity=1.0,
            efficiency=None,
            final_score=0.67,
            weights={"completeness": 0.5, "robustness": 0.3, "syntactic_validity": 0.2},
        )

        assert scoring.efficiency is None
        assert scoring.final_score == 0.67

    def test_scoring_result_validates_ranges(self):
        """Test that scores are validated to be in [0, 1] range"""
        from benchmark.models.results import ScoringResult

        # Test completeness > 1
        with pytest.raises(ValidationError):
            ScoringResult(
                completeness=1.5,  # Invalid
                robustness=1.0,
                syntactic_validity=1.0,
                final_score=1.0,
                weights={},
            )

        # Test negative score
        with pytest.raises(ValidationError):
            ScoringResult(
                completeness=1.0,
                robustness=-0.5,  # Invalid
                syntactic_validity=1.0,
                final_score=1.0,
                weights={},
            )


class TestExecutionMetrics:
    """Test ExecutionMetrics model"""

    def test_execution_metrics_creation(self):
        """Test creating execution metrics"""
        from benchmark.models.results import ExecutionMetrics

        metrics = ExecutionMetrics(
            infrastructure_provision_time=15.5,
            config_execution_time=8.3,
            convergence_time=30.0,
            evaluation_time=12.7,
            total_time=66.5,
        )

        assert metrics.infrastructure_provision_time == 15.5
        assert metrics.config_execution_time == 8.3
        assert metrics.convergence_time == 30.0
        assert metrics.evaluation_time == 12.7
        assert metrics.total_time == 66.5

    def test_execution_metrics_all_required(self):
        """Test that all timing fields are required"""
        from benchmark.models.results import ExecutionMetrics

        with pytest.raises(ValidationError):
            ExecutionMetrics(
                infrastructure_provision_time=10.0,
                config_execution_time=5.0,
                # Missing other fields
            )


class TestValidityCheck:
    """Test ValidityCheck model (Theorem 1)"""

    def test_validity_check_valid_solution(self):
        """Test validity check for a valid solution"""
        from benchmark.models.results import ValidityCheck

        validity = ValidityCheck(
            is_valid_solution=True,
            condition_a_syntactic=True,
            condition_b_semantic=True,
        )

        assert validity.is_valid_solution is True
        assert validity.condition_a_syntactic is True
        assert validity.condition_b_semantic is True

    def test_validity_check_invalid_syntactic(self):
        """Test validity check when syntax is invalid"""
        from benchmark.models.results import ValidityCheck

        validity = ValidityCheck(
            is_valid_solution=False,
            condition_a_syntactic=False,  # Failed
            condition_b_semantic=True,
        )

        assert validity.is_valid_solution is False
        assert validity.condition_a_syntactic is False

    def test_validity_check_invalid_semantic(self):
        """Test validity check when semantics are invalid"""
        from benchmark.models.results import ValidityCheck

        validity = ValidityCheck(
            is_valid_solution=False,
            condition_a_syntactic=True,
            condition_b_semantic=False,  # Failed
        )

        assert validity.is_valid_solution is False
        assert validity.condition_b_semantic is False

    def test_validity_check_all_required(self):
        """Test that all validity fields are required"""
        from benchmark.models.results import ValidityCheck

        with pytest.raises(ValidationError):
            ValidityCheck(
                is_valid_solution=True,
                # Missing conditions
            )


class TestBenchmarkResult:
    """Test BenchmarkResult model (the main result model)"""

    def test_benchmark_result_creation_success(self):
        """Test creating a successful benchmark result"""
        from benchmark.models.results import (
            BenchmarkResult,
            PropertyEvaluationResult,
            ScoringResult,
            ExecutionMetrics,
            ValidityCheck,
        )

        property_results = [
            PropertyEvaluationResult(
                property_id="p1",
                satisfied=True,
                observation_raw="output",
                evaluation_time_seconds=1.0,
            )
        ]

        scoring = ScoringResult(
            completeness=1.0,
            robustness=1.0,
            syntactic_validity=1.0,
            efficiency=1.0,
            final_score=1.0,
            weights={},
        )

        metrics = ExecutionMetrics(
            infrastructure_provision_time=10.0,
            config_execution_time=5.0,
            convergence_time=20.0,
            evaluation_time=5.0,
            total_time=40.0,
        )

        validity = ValidityCheck(
            is_valid_solution=True,
            condition_a_syntactic=True,
            condition_b_semantic=True,
        )

        result = BenchmarkResult(
            run_id="run_20251013_123456",
            timestamp=datetime(2025, 10, 13, 12, 34, 56),
            task_id="bgp_basic_001",
            testee_id="gpt4_test",
            testee_type="llm",
            success=True,
            property_results=property_results,
            scoring=scoring,
            validity=validity,
            metrics=metrics,
            execution_log=["Starting benchmark", "Complete"],
            errors=[],
        )

        assert result.run_id == "run_20251013_123456"
        assert result.task_id == "bgp_basic_001"
        assert result.success is True
        assert result.validity.is_valid_solution is True
        assert len(result.property_results) == 1
        assert len(result.execution_log) == 2
        assert len(result.errors) == 0

    def test_benchmark_result_creation_failure(self):
        """Test creating a failed benchmark result"""
        from benchmark.models.results import (
            BenchmarkResult,
            PropertyEvaluationResult,
            ScoringResult,
            ExecutionMetrics,
            ValidityCheck,
        )

        property_results = [
            PropertyEvaluationResult(
                property_id="p1",
                satisfied=False,
                observation_raw="failed",
                evaluation_time_seconds=1.0,
                error_message="Property not satisfied",
            )
        ]

        scoring = ScoringResult(
            completeness=0.0,
            robustness=0.0,
            syntactic_validity=1.0,
            efficiency=None,
            final_score=0.0,
            weights={},
        )

        metrics = ExecutionMetrics(
            infrastructure_provision_time=10.0,
            config_execution_time=5.0,
            convergence_time=20.0,
            evaluation_time=5.0,
            total_time=40.0,
        )

        validity = ValidityCheck(
            is_valid_solution=False,
            condition_a_syntactic=True,
            condition_b_semantic=False,
        )

        result = BenchmarkResult(
            run_id="run_20251013_123457",
            timestamp=datetime.now(),
            task_id="bgp_basic_001",
            testee_id="baseline_v1",
            testee_type="baseline",
            success=True,  # Benchmark ran successfully
            property_results=property_results,
            scoring=scoring,
            validity=validity,
            metrics=metrics,
            execution_log=["Starting", "Config failed", "Evaluation complete"],
            errors=["Configuration error: invalid command"],
        )

        assert result.success is True  # Benchmark completed
        assert result.validity.is_valid_solution is False  # But solution invalid
        assert len(result.errors) == 1
        assert "invalid command" in result.errors[0]

    def test_benchmark_result_requires_core_fields(self):
        """Test that core fields are required"""
        from benchmark.models.results import BenchmarkResult

        with pytest.raises(ValidationError):
            BenchmarkResult(
                run_id="test",
                # Missing many required fields
            )

    def test_benchmark_result_optional_final_state(self):
        """Test that final_state is optional"""
        from benchmark.models.results import (
            BenchmarkResult,
            PropertyEvaluationResult,
            ScoringResult,
            ExecutionMetrics,
            ValidityCheck,
        )

        result = BenchmarkResult(
            run_id="test",
            timestamp=datetime.now(),
            task_id="task_001",
            testee_id="test",
            testee_type="llm",
            success=True,
            property_results=[
                PropertyEvaluationResult(
                    property_id="p1",
                    satisfied=True,
                    observation_raw="test",
                    evaluation_time_seconds=1.0,
                )
            ],
            scoring=ScoringResult(
                completeness=1.0,
                robustness=1.0,
                syntactic_validity=1.0,
                final_score=1.0,
                weights={},
            ),
            validity=ValidityCheck(
                is_valid_solution=True,
                condition_a_syntactic=True,
                condition_b_semantic=True,
            ),
            metrics=ExecutionMetrics(
                infrastructure_provision_time=1.0,
                config_execution_time=1.0,
                convergence_time=1.0,
                evaluation_time=1.0,
                total_time=4.0,
            ),
            execution_log=[],
            errors=[],
        )

        assert result.final_state is None

    def test_benchmark_result_json_serialization(self):
        """Test JSON serialization of benchmark result"""
        from benchmark.models.results import (
            BenchmarkResult,
            PropertyEvaluationResult,
            ScoringResult,
            ExecutionMetrics,
            ValidityCheck,
        )
        import json

        result = BenchmarkResult(
            run_id="test_run",
            timestamp=datetime(2025, 10, 13, 12, 0, 0),
            task_id="task_001",
            testee_id="test_testee",
            testee_type="llm",
            success=True,
            property_results=[
                PropertyEvaluationResult(
                    property_id="p1",
                    satisfied=True,
                    observation_raw="test",
                    evaluation_time_seconds=1.0,
                )
            ],
            scoring=ScoringResult(
                completeness=1.0,
                robustness=1.0,
                syntactic_validity=1.0,
                final_score=1.0,
                weights={},
            ),
            validity=ValidityCheck(
                is_valid_solution=True,
                condition_a_syntactic=True,
                condition_b_semantic=True,
            ),
            metrics=ExecutionMetrics(
                infrastructure_provision_time=1.0,
                config_execution_time=1.0,
                convergence_time=1.0,
                evaluation_time=1.0,
                total_time=4.0,
            ),
            execution_log=["test log"],
            errors=[],
        )

        # Serialize to JSON
        json_str = result.model_dump_json()
        assert "test_run" in json_str
        assert "task_001" in json_str

        # Deserialize
        json_dict = json.loads(json_str)
        result_restored = BenchmarkResult(**json_dict)

        assert result_restored.run_id == result.run_id
        assert result_restored.task_id == result.task_id


class TestIntegrationWithOtherModels:
    """Test that result models integrate well with task and submission models"""

    def test_complete_workflow_models(self):
        """Test that all models work together in a complete workflow"""
        from benchmark.models.task import (
            TaskDefinition,
            Platform,
            TopologySpecification,
            Node,
            NodeType,
            IntentSpecification,
            Property,
            PropertyType,
            EvaluationProcedure,
        )
        from benchmark.models.submission import Submission, Approach, CommandSequence
        from benchmark.models.results import (
            BenchmarkResult,
            PropertyEvaluationResult,
            ScoringResult,
            ExecutionMetrics,
            ValidityCheck,
        )

        # Create a task
        nodes = [Node(name="R1", type=NodeType.ROUTER)]
        topology = TopologySpecification(nodes=nodes, links=[], interfaces=[])

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
                type=PropertyType.REACHABILITY,
                description="Test",
                evaluation=eval_proc,
            )
        ]
        intent = IntentSpecification(properties=properties)

        task = TaskDefinition(
            task_id="workflow_test",
            description="Integration test",
            platform=Platform.FRR,
            topology=topology,
            intent=intent,
        )

        # Create a submission
        submission = Submission(
            task_id=task.task_id,
            testee_id="integration_test",
            testee_type="llm",
            approach=Approach(
                commands=[CommandSequence(node="R1", commands=["test"])]
            ),
        )

        # Create a result
        result = BenchmarkResult(
            run_id="integration_run",
            timestamp=datetime.now(),
            task_id=task.task_id,
            testee_id=submission.testee_id,
            testee_type=submission.testee_type,
            success=True,
            property_results=[
                PropertyEvaluationResult(
                    property_id=properties[0].id,
                    satisfied=True,
                    observation_raw="success",
                    evaluation_time_seconds=1.0,
                )
            ],
            scoring=ScoringResult(
                completeness=1.0,
                robustness=1.0,
                syntactic_validity=1.0,
                final_score=1.0,
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
                convergence_time=10.0,
                evaluation_time=3.0,
                total_time=20.0,
            ),
            execution_log=["Complete workflow test"],
            errors=[],
        )

        # Verify everything links correctly
        assert result.task_id == task.task_id == submission.task_id
        assert result.testee_id == submission.testee_id
        assert result.property_results[0].property_id == task.intent.properties[0].id
        assert result.validity.is_valid_solution is True

