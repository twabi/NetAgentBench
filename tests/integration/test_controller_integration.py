"""
Integration tests for BenchmarkController.

These tests use real Containerlab environments to verify end-to-end functionality.
"""

import pytest
from benchmark.controller import BenchmarkController
from benchmark.models.task import (
    TaskDefinition,
    TopologySpecification,
    Node,
    NodeType,
    Platform,
    Link,
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


class TestBenchmarkControllerEndToEnd:
    """Test complete benchmark workflow with real infrastructure"""

    def test_simple_successful_benchmark(self):
        """Test a complete benchmark run with a simple successful submission"""
        # Create a simple task: single Alpine container, check if echo works
        task = TaskDefinition(
            task_id="integration_test_001",
            description="Simple echo test",
            platform=Platform.FRR,
            topology=TopologySpecification(
                nodes=[
                    Node(
                        name="TestNode1",
                        type=NodeType.ROUTER,
                        image="alpine:latest",
                        platform=Platform.FRR,
                    )
                ],
                links=[],
            ),
            intent=IntentSpecification(
                properties=[
                    Property(
                        id="echo_works",
                        type=PropertyType.REACHABILITY,
                        description="Echo command produces output",
                        evaluation=EvaluationProcedure(
                            method="exec_and_parse",
                            target_node="TestNode1",
                            command="echo 'Integration Test Success'",
                            parser="text",
                            success_condition={"contains_text": "Integration Test Success"},
                        ),
                    )
                ]
            ),
            convergence=ConvergenceConfig(timeout_seconds=2, check_interval_seconds=1),
            optimal_solution=OptimalSolution(
                command_count=1, description="Single echo command"
            ),
        )

        # Create a valid submission
        submission = Submission(
            task_id="integration_test_001",
            testee_id="integration_testee",
            testee_type="test",
            approach=Approach(
                description="Simple echo approach",
                commands=[
                    CommandSequence(
                        node="TestNode1",
                        commands=["echo 'Setup complete'"],
                    )
                ],
            ),
        )

        # Run the benchmark
        controller = BenchmarkController()
        result = controller.run(task, submission)

        # Verify result structure
        assert result.run_id.startswith("run_")
        assert result.task_id == "integration_test_001"
        assert result.testee_id == "integration_testee"
        assert result.testee_type == "test"

        # Verify property evaluation
        assert len(result.property_results) == 1
        assert result.property_results[0].property_id == "echo_works"
        assert result.property_results[0].satisfied is True

        # Verify scoring
        assert result.scoring.completeness == 1.0  # All properties satisfied
        assert result.scoring.syntactic_validity == 1.0  # All commands succeeded
        assert result.scoring.final_score > 0.0

        # Verify validity
        assert result.validity.is_valid_solution is True
        assert result.validity.condition_a_syntactic is True
        assert result.validity.condition_b_semantic is True

        # Verify metrics
        assert result.metrics.infrastructure_provision_time > 0
        assert result.metrics.config_execution_time > 0
        assert result.metrics.convergence_time >= 4  # 2s initial + 2s post-config
        assert result.metrics.evaluation_time > 0
        assert result.metrics.total_time > 0

        # Verify success
        assert result.success is True
        assert len(result.errors) == 0

    def test_benchmark_with_failed_command(self):
        """Test benchmark handles failed commands gracefully"""
        task = TaskDefinition(
            task_id="integration_test_002",
            description="Test with failed command",
            platform=Platform.FRR,
            topology=TopologySpecification(
                nodes=[
                    Node(
                        name="TestNode1",
                        type=NodeType.ROUTER,
                        image="alpine:latest",
                        platform=Platform.FRR,
                    )
                ],
                links=[],
            ),
            intent=IntentSpecification(
                properties=[
                    Property(
                        id="check_file",
                        type=PropertyType.REACHABILITY,
                        description="Check for nonexistent file",
                        evaluation=EvaluationProcedure(
                            method="exec_and_parse",
                            target_node="TestNode1",
                            command="cat /nonexistent/file.txt",
                            parser="text",
                            success_condition={"contains_text": "content"},
                        ),
                    )
                ]
            ),
            convergence=ConvergenceConfig(timeout_seconds=1, check_interval_seconds=1),
        )

        submission = Submission(
            task_id="integration_test_002",
            testee_id="integration_testee",
            testee_type="test",
            approach=Approach(
                description="Approach with bad command",
                commands=[
                    CommandSequence(
                        node="TestNode1",
                        commands=["nonexistent_command_that_will_fail"],
                    )
                ],
            ),
        )

        controller = BenchmarkController()
        result = controller.run(task, submission)

        # Benchmark should complete despite failed command
        assert result.run_id.startswith("run_")
        
        # Property should not be satisfied
        assert len(result.property_results) == 1
        assert result.property_results[0].satisfied is False

        # Scoring should reflect failures
        assert result.scoring.completeness == 0.0  # No properties satisfied
        assert result.scoring.syntactic_validity == 0.0  # Command failed

        # Should not be a valid solution
        assert result.validity.is_valid_solution is False
        assert result.success is False

        # But execution should have completed
        assert result.metrics.total_time > 0

    def test_benchmark_with_two_nodes(self):
        """Test benchmark with multi-node topology"""
        task = TaskDefinition(
            task_id="integration_test_003",
            description="Two node test",
            platform=Platform.FRR,
            topology=TopologySpecification(
                nodes=[
                    Node(
                        name="Node1",
                        type=NodeType.ROUTER,
                        image="alpine:latest",
                        platform=Platform.FRR,
                    ),
                    Node(
                        name="Node2",
                        type=NodeType.ROUTER,
                        image="alpine:latest",
                        platform=Platform.FRR,
                    ),
                ],
                links=[
                    Link(endpoints=["Node1:eth1", "Node2:eth1"]),
                ],
            ),
            intent=IntentSpecification(
                properties=[
                    Property(
                        id="node1_check",
                        type=PropertyType.REACHABILITY,
                        description="Node1 responds",
                        evaluation=EvaluationProcedure(
                            method="exec_and_parse",
                            target_node="Node1",
                            command="echo 'Node1 OK'",
                            parser="text",
                            success_condition={"contains_text": "Node1 OK"},
                        ),
                    ),
                    Property(
                        id="node2_check",
                        type=PropertyType.REACHABILITY,
                        description="Node2 responds",
                        evaluation=EvaluationProcedure(
                            method="exec_and_parse",
                            target_node="Node2",
                            command="echo 'Node2 OK'",
                            parser="text",
                            success_condition={"contains_text": "Node2 OK"},
                        ),
                    ),
                ]
            ),
            convergence=ConvergenceConfig(timeout_seconds=2, check_interval_seconds=1),
        )

        submission = Submission(
            task_id="integration_test_003",
            testee_id="integration_testee",
            testee_type="test",
            approach=Approach(
                description="Configure both nodes",
                commands=[
                    CommandSequence(node="Node1", commands=["echo 'Configuring Node1'"]),
                    CommandSequence(node="Node2", commands=["echo 'Configuring Node2'"]),
                ],
            ),
        )

        controller = BenchmarkController()
        result = controller.run(task, submission)

        # Both properties should be satisfied
        assert len(result.property_results) == 2
        assert all(p.satisfied for p in result.property_results)

        # Should be a valid solution
        assert result.scoring.completeness == 1.0
        assert result.validity.is_valid_solution is True
        assert result.success is True

        # Execution log should have entries for both nodes
        assert len(result.execution_log) >= 2

