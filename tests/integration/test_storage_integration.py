"""
Integration tests for ResultsStorage.

These tests verify end-to-end functionality with real file system operations.
"""

import json
import tempfile
import pytest
from datetime import datetime
from pathlib import Path

from benchmark.storage import ResultsStorage
from benchmark.controller import BenchmarkController
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


class TestResultsStorageIntegration:
    """Test complete storage workflow with real benchmark results"""

    def test_end_to_end_storage_workflow(self):
        """Test complete workflow: run benchmark -> save -> load -> analyze"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create storage
            storage = ResultsStorage(base_dir=temp_dir)
            
            # Create a simple task
            task = TaskDefinition(
                task_id="storage_test_001",
                description="Storage integration test",
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
                            id="echo_test",
                            type=PropertyType.REACHABILITY,
                            description="Echo command works",
                            evaluation=EvaluationProcedure(
                                method="exec_and_parse",
                                target_node="TestNode1",
                                command="echo 'Storage Test Success'",
                                parser="text",
                                success_condition={"contains_text": "Storage Test Success"},
                            ),
                        )
                    ]
                ),
                convergence=ConvergenceConfig(timeout_seconds=1, check_interval_seconds=1),
                optimal_solution=OptimalSolution(
                    command_count=1, description="Single echo command"
                ),
            )

            # Create a submission
            submission = Submission(
                task_id="storage_test_001",
                testee_id="storage_testee",
                testee_type="test",
                approach=Approach(
                    description="Storage test approach",
                    commands=[
                        CommandSequence(
                            node="TestNode1",
                            commands=["echo 'Configuration applied'"],
                        )
                    ],
                ),
            )

            # Run benchmark
            controller = BenchmarkController()
            result = controller.run(task, submission)

            # Save result
            file_path = storage.save_run(result)
            assert Path(file_path).exists()

            # Load result back
            loaded_result = storage.load_run(result.run_id)
            assert loaded_result.run_id == result.run_id
            assert loaded_result.task_id == result.task_id
            assert loaded_result.testee_id == result.testee_id
            assert loaded_result.success == result.success

            # List runs
            all_runs = storage.list_runs()
            assert result.run_id in all_runs

            task_runs = storage.list_runs(task_id="storage_test_001")
            assert result.run_id in task_runs

            # Compute aggregate stats
            stats = storage.compute_aggregate_stats([result.run_id])
            assert stats["metadata"]["total_runs"] == 1
            assert stats["aggregate_stats"]["average_final_score"] > 0.0

            # Save aggregate stats
            analysis_file = storage.save_aggregate_stats("storage_test_study", stats)
            assert Path(analysis_file).exists()

            # Verify analysis file content
            with open(analysis_file, 'r') as f:
                saved_stats = json.load(f)
            assert saved_stats["metadata"]["total_runs"] == 1

    def test_storage_with_multiple_benchmark_runs(self):
        """Test storage with multiple benchmark runs"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = ResultsStorage(base_dir=temp_dir)
            
            # Create task
            task = TaskDefinition(
                task_id="multi_storage_test",
                description="Multiple runs storage test",
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
                            id="simple_check",
                            type=PropertyType.REACHABILITY,
                            description="Simple check",
                            evaluation=EvaluationProcedure(
                                method="exec_and_parse",
                                target_node="TestNode1",
                                command="echo 'OK'",
                                parser="text",
                                success_condition={"contains_text": "OK"},
                            ),
                        )
                    ]
                ),
                convergence=ConvergenceConfig(timeout_seconds=1, check_interval_seconds=1),
            )

            # Create multiple submissions
            submissions = [
                Submission(
                    task_id="multi_storage_test",
                    testee_id="testee_1",
                    testee_type="test",
                    approach=Approach(
                        description="Testee 1 approach",
                        commands=[
                            CommandSequence(node="TestNode1", commands=["echo 'Testee 1'"]),
                        ],
                    ),
                ),
                Submission(
                    task_id="multi_storage_test",
                    testee_id="testee_2",
                    testee_type="test",
                    approach=Approach(
                        description="Testee 2 approach",
                        commands=[
                            CommandSequence(node="TestNode1", commands=["echo 'Testee 2'"]),
                        ],
                    ),
                ),
            ]

            # Run benchmarks and save results
            controller = BenchmarkController()
            run_ids = []
            
            for submission in submissions:
                result = controller.run(task, submission)
                storage.save_run(result)
                run_ids.append(result.run_id)

            # Verify all runs are saved
            all_runs = storage.list_runs()
            assert len(all_runs) == 2
            for run_id in run_ids:
                assert run_id in all_runs

            # Verify task filtering
            task_runs = storage.list_runs(task_id="multi_storage_test")
            assert len(task_runs) == 2

            # Compute aggregate stats for all runs
            stats = storage.compute_aggregate_stats(run_ids)
            assert stats["metadata"]["total_runs"] == 2
            assert len(stats["grouped_by_testee_id"]) == 2
            assert "testee_1" in stats["grouped_by_testee_id"]
            assert "testee_2" in stats["grouped_by_testee_id"]

            # Save analysis
            analysis_file = storage.save_aggregate_stats("multi_test_study", stats)
            assert Path(analysis_file).exists()

    def test_storage_directory_structure(self):
        """Test that storage creates correct directory structure"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = ResultsStorage(base_dir=temp_dir)
            
            # Create a simple result manually
            from benchmark.models.results import (
                BenchmarkResult,
                PropertyEvaluationResult,
                ScoringResult,
                ValidityCheck,
                ExecutionMetrics,
            )
            
            result = BenchmarkResult(
                run_id="dir_test_001",
                timestamp=datetime.now(),
                task_id="dir_test_task",
                testee_id="dir_testee",
                testee_type="test",
                success=True,
                property_results=[
                    PropertyEvaluationResult(
                        property_id="test_prop",
                        satisfied=True,
                        observation_raw="test",
                        observation_parsed=None,
                        evaluation_time_seconds=0.1,
                        error_message=None,
                    )
                ],
                scoring=ScoringResult(
                    completeness=1.0,
                    robustness=1.0,
                    syntactic_validity=1.0,
                    efficiency=1.0,
                    final_score=1.0,
                    weights={"completeness": 0.4, "robustness": 0.3, "syntactic_validity": 0.2, "efficiency": 0.1},
                ),
                validity=ValidityCheck(
                    is_valid_solution=True,
                    condition_a_syntactic=True,
                    condition_b_semantic=True,
                ),
                metrics=ExecutionMetrics(
                    infrastructure_provision_time=1.0,
                    config_execution_time=2.0,
                    convergence_time=3.0,
                    evaluation_time=4.0,
                    total_time=10.0,
                ),
                execution_log=["test log entry"],
                errors=[],
            )

            # Save result
            file_path = storage.save_run(result)
            
            # Verify directory structure
            base_path = Path(temp_dir)
            runs_dir = base_path / "runs"
            task_dir = runs_dir / "dir_test_task"
            result_file = task_dir / "dir_test_001.json"
            
            assert runs_dir.exists()
            assert runs_dir.is_dir()
            assert task_dir.exists()
            assert task_dir.is_dir()
            assert result_file.exists()
            assert result_file.is_file()
            
            # Verify file path matches
            assert file_path == str(result_file.absolute())

    def test_storage_error_handling(self):
        """Test storage error handling with invalid data"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = ResultsStorage(base_dir=temp_dir)
            
            # Test loading nonexistent run
            with pytest.raises(FileNotFoundError):
                storage.load_run("nonexistent_run")
            
            # Test listing runs for nonexistent task
            runs = storage.list_runs(task_id="nonexistent_task")
            assert runs == []
            
            # Test computing stats for empty run list
            stats = storage.compute_aggregate_stats([])
            assert stats["metadata"]["total_runs"] == 0
            assert stats["aggregate_stats"]["average_final_score"] == 0.0
            
            # Test computing stats for nonexistent runs
            stats = storage.compute_aggregate_stats(["nonexistent_run"])
            assert stats["metadata"]["total_runs"] == 0
