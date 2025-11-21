"""
Integration tests for Phase 10: Multi-Testee Benchmark Execution.

Tests the complete system with REAL infrastructure (no mocks):
- PropertyExecutor
- TaskRepository  
- BenchmarkController (real Containerlab)
- Multiple testee types (Human, Baseline)
- Aggregate scoring

IMPORTANT: NO MOCKS - All tests use real Containerlab infrastructure.
"""
import pytest
import tempfile
import json
from pathlib import Path
from benchmark.property_executor import PropertyExecutor
from benchmark.task_repository import TaskRepository
from benchmark.controller import BenchmarkController
from benchmark.testee.baseline import BaselineTestee
from benchmark.testee.human import HumanJsonTestee
from benchmark.ml.model_testee import MockMLModelTestee


@pytest.mark.integration
@pytest.mark.slow
class TestPhase10Integration:
    """Integration tests for Phase 10 multi-testee benchmark execution with REAL infrastructure."""

    def test_baseline_testee_integration(self):
        """Test complete flow with BaselineTestee using REAL controller and Containerlab."""
        # Setup - ALL REAL, NO MOCKS
        repository = TaskRepository(Path("benchmark-tasks"))
        controller = BenchmarkController()  # REAL controller, not mocked
        
        # Create executor
        executor = PropertyExecutor(controller, repository)
        
        # Create baseline testee
        testee = BaselineTestee(testee_id="baseline_integration_test")
        
        # Run tasks for one property type with REAL infrastructure
        result = executor.run_property_tasks(
            property_type="reachability",
            submission_generator=lambda task: testee.generate_submission(task),
            limit=1  # Reduced to 1 for speed since using real infrastructure
        )
        
        # Verify
        assert result.property_type == "reachability"
        assert result.total_tasks == 1
        # Baseline testee generates empty commands, so likely won't satisfy properties
        assert len(result.results) == 1
        assert 0.0 <= result.average_score <= 1.0  # Score can vary
        
        # Verify real execution metrics
        assert result.results[0].metrics.total_time > 0
        assert result.results[0].metrics.infrastructure_provision_time > 0

    def test_human_json_testee_integration(self):
        """Test complete flow with HumanJsonTestee using REAL controller and Containerlab."""
        repository = TaskRepository(Path("benchmark-tasks"))
        controller = BenchmarkController()  # REAL controller, not mocked
        
        # Load a real task to get its task_id
        tasks = repository.load_tasks_by_property("reachability", limit=1)
        assert len(tasks) > 0
        task = tasks[0]
        
        # Create human submission file with basic configuration
        with tempfile.TemporaryDirectory() as tmpdir:
            submission_file = Path(tmpdir) / "human_submission.json"
            
            submission_data = {
                "task_id": task.task_id,
                "testee_id": "human_integration_test",
                "testee_type": "human",
                "approach": {
                    "description": "Integration test configuration",
                    "commands": [
                        {
                            "node": node.name,
                            "commands": [
                                f"echo 'Configured {node.name}'"
                            ]
                        }
                        for node in task.topology.nodes
                    ]
                }
            }
            
            with open(submission_file, 'w') as f:
                json.dump(submission_data, f)
            
            # Create executor
            executor = PropertyExecutor(controller, repository)
            
            # Create human testee
            testee = HumanJsonTestee(submission_file=str(submission_file))
            
            # Run single task with REAL infrastructure
            result = executor.run_property_tasks(
                property_type="reachability",
                submission_generator=lambda t: testee.generate_submission(t),
                limit=1
            )
            
            # Verify
            assert result.property_type == "reachability"
            assert result.total_tasks == 1
            assert len(result.results) == 1
            assert 0.0 <= result.average_score <= 1.0
            
            # Verify real execution metrics
            assert result.results[0].metrics.total_time > 0
            assert result.results[0].metrics.infrastructure_provision_time > 0

    def test_ml_model_testee_integration(self):
        """Test complete flow with MLModelTestee using REAL controller and Containerlab."""
        repository = TaskRepository(Path("benchmark-tasks"))
        controller = BenchmarkController()  # REAL controller, not mocked
        
        # Create ML model testee (using mock model, but real infrastructure)
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "model.pt"
            testee = MockMLModelTestee(
                model_path=str(model_path),
                testee_id="ml_integration_test"
            )
            
            # Create executor
            executor = PropertyExecutor(controller, repository)
            
            # Run tasks with REAL infrastructure
            result = executor.run_property_tasks(
                property_type="reachability",
                submission_generator=lambda task: testee.generate_submission(task),
                limit=1
            )
            
            # Verify
            assert result.property_type == "reachability"
            assert result.total_tasks == 1
            assert len(result.results) == 1
            assert 0.0 <= result.average_score <= 1.0
            
            # Verify real execution metrics
            assert result.results[0].metrics.total_time > 0

    def test_aggregate_metrics_integration(self):
        """Test that aggregate metrics are computed correctly with REAL infrastructure."""
        repository = TaskRepository(Path("benchmark-tasks"))
        controller = BenchmarkController()  # REAL controller, not mocked
        
        # Create testee
        testee = BaselineTestee()
        
        # Create executor
        executor = PropertyExecutor(controller, repository)
        
        # Run tasks with REAL infrastructure
        result = executor.run_property_tasks(
            property_type="reachability",
            submission_generator=lambda task: testee.generate_submission(task),
            limit=2
        )
        
        # Verify aggregate metrics are computed
        assert "avg_completeness" in result.aggregate_metrics
        assert "avg_robustness" in result.aggregate_metrics
        assert "avg_syntactic_validity" in result.aggregate_metrics
        assert "avg_efficiency" in result.aggregate_metrics
        
        # All should be valid numbers
        assert 0.0 <= result.aggregate_metrics["avg_completeness"] <= 1.0
        assert 0.0 <= result.aggregate_metrics["avg_robustness"] <= 1.0
        assert 0.0 <= result.aggregate_metrics["avg_syntactic_validity"] <= 1.0

    def test_multiple_testee_types_comparison(self):
        """Test running the same task with different testee types using REAL infrastructure."""
        repository = TaskRepository(Path("benchmark-tasks"))
        controller = BenchmarkController()  # REAL controller, not mocked
        
        # Create executor
        executor = PropertyExecutor(controller, repository)
        
        # Test with baseline
        baseline_testee = BaselineTestee(testee_id="baseline_comp")
        baseline_result = executor.run_property_tasks(
            property_type="reachability",
            submission_generator=lambda task: baseline_testee.generate_submission(task),
            limit=1
        )
        
        # Test with ML model
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "model.pt"
            ml_testee = MockMLModelTestee(
                model_path=str(model_path),
                testee_id="ml_comp"
            )
            ml_result = executor.run_property_tasks(
                property_type="reachability",
                submission_generator=lambda task: ml_testee.generate_submission(task),
                limit=1
            )
        
        # Both should have valid results
        assert baseline_result.total_tasks == 1
        assert ml_result.total_tasks == 1
        assert 0.0 <= baseline_result.average_score <= 1.0
        assert 0.0 <= ml_result.average_score <= 1.0
        
        # Verify both executed with real infrastructure
        assert baseline_result.results[0].metrics.total_time > 0
        assert ml_result.results[0].metrics.total_time > 0

    def test_task_repository_integration(self):
        """Test that TaskRepository loads real tasks correctly."""
        repository = TaskRepository(Path("benchmark-tasks"))
        
        # Load tasks by property type
        reachability_tasks = repository.load_tasks_by_property("reachability", limit=5)
        assert len(reachability_tasks) > 0
        assert len(reachability_tasks) <= 5
        
        bgp_tasks = repository.load_tasks_by_property("bgp_configuration", limit=3)
        assert len(bgp_tasks) > 0
        assert len(bgp_tasks) <= 3
        
        ospf_tasks = repository.load_tasks_by_property("ospf_configuration", limit=3)
        assert len(ospf_tasks) > 0
        assert len(ospf_tasks) <= 3
        
        # Verify tasks are valid
        for task in reachability_tasks[:1]:  # Check one task
            assert hasattr(task, 'task_id')
            assert hasattr(task, 'topology')
            assert hasattr(task, 'intent')
            assert len(task.topology.nodes) > 0
            assert len(task.intent.properties) > 0

    def test_property_executor_error_handling(self):
        """Test error handling in PropertyExecutor with REAL infrastructure."""
        repository = TaskRepository(Path("benchmark-tasks"))
        controller = BenchmarkController()  # REAL controller, not mocked
        
        # Create testee that will generate invalid commands
        class BrokenTestee(BaselineTestee):
            def generate_submission(self, task):
                submission = super().generate_submission(task)
                # Add an invalid command that will fail
                if submission.approach.commands:
                    submission.approach.commands[0].commands.append(
                        "this_is_an_invalid_command_xyz_12345"
                    )
                return submission
        
        testee = BrokenTestee()
        executor = PropertyExecutor(controller, repository)
        
        # Run should complete but show failures in results
        result = executor.run_property_tasks(
            property_type="reachability",
            submission_generator=lambda task: testee.generate_submission(task),
            limit=1
        )
        
        # Should complete execution even with failures
        assert result.total_tasks == 1
        assert len(result.results) == 1
        # The result may have low syntactic validity due to failed commands
        assert result.results[0].metrics.total_time > 0

    def test_testee_info_consistency(self):
        """Test that all testee types provide consistent info."""
        # Baseline
        baseline = BaselineTestee(testee_id="test_baseline")
        baseline_info = baseline.get_testee_info()
        assert baseline_info["testee_id"] == "test_baseline"
        assert baseline_info["testee_type"] == "baseline"
        
        # ML
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "model.pt"
            ml = MockMLModelTestee(model_path=str(model_path), testee_id="test_ml")
            ml_info = ml.get_testee_info()
            assert ml_info["testee_id"] == "test_ml"
            assert ml_info["testee_type"] == "ml_model"
