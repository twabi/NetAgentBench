"""
Comprehensive failure scenario tests with REAL infrastructure (no mocks).

Tests all failure modes:
- Infrastructure failures
- Configuration failures
- Evaluation failures
- Task repository failures
- Resource failures

All tests use REAL Containerlab - NO MOCKS.
"""
import pytest
import json
import tempfile
from pathlib import Path
from benchmark.controller import BenchmarkController
from benchmark.task_repository import TaskRepository
from benchmark.infrastructure.containerlab import ContainerlabProvider
from benchmark.testee.baseline import BaselineTestee
from benchmark.property_executor import PropertyExecutor
from benchmark.models.task import (
    Node, NodeType, Platform, Link, TopologySpecification,
    Property, PropertyType, EvaluationProcedure, TaskDefinition
)
from benchmark.models.submission import CommandSequence, Approach, Submission


@pytest.mark.integration
@pytest.mark.slow
class TestInfrastructureFailures:
    """Test infrastructure-related failure scenarios with REAL Containerlab."""

    def test_invalid_image_fails_gracefully(self):
        """Test that invalid container image fails with clear error."""
        # Create topology with invalid image
        topology = TopologySpecification(
            nodes=[
                Node(
                    name="badnode",
                    type=NodeType.LINUX,
                    image="this-image-does-not-exist:never",
                    platform=Platform.FRR
                )
            ],
            links=[]
        )
        
        provider = ContainerlabProvider()
        
        # Provision should fail
        with pytest.raises(Exception) as exc_info:
            provider.provision(topology, topology_id="test_bad_image")
        
        # Should get a meaningful error
        assert exc_info.value is not None
        
        # Cleanup if somehow it partially succeeded
        try:
            provider.teardown("test_bad_image")
        except:
            pass

    def test_missing_interface_handled(self):
        """Test configuration on non-existent interface handled gracefully."""
        repository = TaskRepository(Path("benchmark-tasks"))
        tasks = repository.load_tasks_by_property("reachability", limit=1)
        assert len(tasks) > 0
        task = tasks[0]
        
        # Create submission with commands for non-existent interface
        submission = Submission(
            task_id=task.task_id,
            testee_id="test_missing_iface",
            testee_type="test",
            approach=Approach(
                description="Test with non-existent interface",
                commands=[
                    CommandSequence(
                        node=task.topology.nodes[0].name,
                        commands=[
                            "ip addr add 10.0.0.1/24 dev eth999",  # Non-existent interface
                            "ip link set eth999 up"
                        ]
                    )
                ]
            )
        )
        
        # Run benchmark - should complete but commands will fail
        controller = BenchmarkController()
        result = controller.run(task, submission)
        
        # Should complete execution
        assert result.run_id is not None
        assert result.metrics.total_time > 0
        # Commands likely failed, so syntactic validity may be low
        assert 0.0 <= result.scoring.syntactic_validity <= 1.0


@pytest.mark.integration
@pytest.mark.slow
class TestConfigurationFailures:
    """Test configuration-related failure scenarios with REAL infrastructure."""

    def test_invalid_commands_handled(self):
        """Test that syntactically invalid commands are handled gracefully."""
        repository = TaskRepository(Path("benchmark-tasks"))
        tasks = repository.load_tasks_by_property("reachability", limit=1)
        assert len(tasks) > 0
        task = tasks[0]
        
        # Create submission with invalid commands
        submission = Submission(
            task_id=task.task_id,
            testee_id="test_invalid_cmds",
            testee_type="test",
            approach=Approach(
                description="Test with invalid commands",
                commands=[
                    CommandSequence(
                        node=task.topology.nodes[0].name,
                        commands=[
                            "this_command_does_not_exist_xyz",
                            "another_invalid_command_abc",
                            "echo 'but this one works'"
                        ]
                    )
                ]
            )
        )
        
        # Run benchmark
        controller = BenchmarkController()
        result = controller.run(task, submission)
        
        # Should complete execution
        assert result.run_id is not None
        assert result.metrics.total_time > 0
        # Some commands failed
        assert result.scoring.syntactic_validity < 1.0
        # Should have error logs
        assert len(result.execution_log) > 0

    def test_empty_configuration(self):
        """Test that empty configuration (no commands) is handled."""
        repository = TaskRepository(Path("benchmark-tasks"))
        tasks = repository.load_tasks_by_property("reachability", limit=1)
        assert len(tasks) > 0
        task = tasks[0]
        
        # Create submission with no commands
        submission = Submission(
            task_id=task.task_id,
            testee_id="test_empty_config",
            testee_type="baseline",
            approach=Approach(
                description="Empty configuration",
                commands=[]
            )
        )
        
        # Run benchmark
        controller = BenchmarkController()
        result = controller.run(task, submission)
        
        # Should complete execution
        assert result.run_id is not None
        assert result.metrics.total_time > 0
        # No commands executed
        assert result.scoring.syntactic_validity >= 0.0
        # Properties likely not satisfied
        assert result.scoring.completeness == 0.0

    def test_commands_with_special_characters(self):
        """Test commands with special characters are handled correctly."""
        repository = TaskRepository(Path("benchmark-tasks"))
        tasks = repository.load_tasks_by_property("reachability", limit=1)
        assert len(tasks) > 0
        task = tasks[0]
        
        # Create submission with special characters
        submission = Submission(
            task_id=task.task_id,
            testee_id="test_special_chars",
            testee_type="test",
            approach=Approach(
                description="Test with special characters",
                commands=[
                    CommandSequence(
                        node=task.topology.nodes[0].name,
                        commands=[
                            "echo 'Test with \"quotes\" and $variables'",
                            "echo \"Another 'test' with \\backslashes\\\"",
                            "echo Test with ; semicolons && and || operators"
                        ]
                    )
                ]
            )
        )
        
        # Run benchmark
        controller = BenchmarkController()
        result = controller.run(task, submission)
        
        # Should complete without crashes
        assert result.run_id is not None
        assert result.metrics.total_time > 0


@pytest.mark.integration
class TestEvaluationFailures:
    """Test evaluation-related failure scenarios."""

    def test_malformed_json_observation(self):
        """Test that malformed JSON in observations is handled."""
        repository = TaskRepository(Path("benchmark-tasks"))
        tasks = repository.load_tasks_by_property("bgp_configuration", limit=1)
        
        if len(tasks) == 0:
            pytest.skip("No BGP tasks available")
        
        task = tasks[0]
        
        # Create submission that outputs malformed JSON
        submission = Submission(
            task_id=task.task_id,
            testee_id="test_malformed_json",
            testee_type="test",
            approach=Approach(
                description="Test with malformed JSON output",
                commands=[
                    CommandSequence(
                        node=task.topology.nodes[0].name,
                        commands=[
                            "echo '{invalid json without closing brace'",
                        ]
                    )
                ]
            )
        )
        
        # Run benchmark - should handle parsing errors gracefully
        controller = BenchmarkController()
        result = controller.run(task, submission)
        
        # Should complete execution
        assert result.run_id is not None
        assert result.metrics.total_time > 0


@pytest.mark.integration
class TestTaskRepositoryFailures:
    """Test task repository failure scenarios."""

    def test_missing_task_directory(self):
        """Test that missing task directory is handled."""
        with pytest.raises(Exception):
            repository = TaskRepository(Path("/nonexistent/path/to/tasks"))
            repository.load_all_tasks()

    def test_empty_property_type(self):
        """Test loading tasks for property type with no tasks."""
        repository = TaskRepository(Path("benchmark-tasks"))
        
        # Try to load from a property type that might not exist
        # This should return empty list, not crash
        tasks = repository.load_tasks_by_property("nonexistent_property", limit=10)
        assert tasks == []

    def test_corrupted_task_file(self):
        """Test that corrupted task JSON is handled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tasks_dir = Path(tmpdir) / "corrupted-tasks"
            prop_dir = tasks_dir / "property_types" / "test_property" / "tasks"
            prop_dir.mkdir(parents=True)
            
            # Create corrupted JSON file
            corrupted_file = prop_dir / "corrupted.json"
            corrupted_file.write_text("{invalid json content}")
            
            # Create index
            index_file = tasks_dir / "index.json"
            index_file.write_text(json.dumps({
                "total_tasks": 1,
                "property_types": {
                    "test_property": {"count": 1, "description": "Test"}
                }
            }))
            
            repository = TaskRepository(tasks_dir)
            
            # Should handle corrupted files gracefully (skip or raise clear error)
            try:
                tasks = repository.load_tasks_by_property("test_property")
                # If it doesn't raise, it should return empty or valid tasks only
                assert isinstance(tasks, list)
            except Exception as e:
                # Should get a clear error about JSON parsing
                assert "json" in str(e).lower() or "parse" in str(e).lower()


@pytest.mark.integration
@pytest.mark.slow
class TestResourceFailures:
    """Test resource-related failure scenarios."""

    def test_rapid_provision_teardown(self):
        """Test rapid provision and teardown doesn't leave orphaned resources."""
        provider = ContainerlabProvider()
        topology = TopologySpecification(
            nodes=[
                Node(
                    name="rapid_test",
                    type=NodeType.LINUX,
                    image="alpine:latest",
                    platform=Platform.FRR
                )
            ],
            links=[]
        )
        
        # Rapidly provision and teardown 3 times
        for i in range(3):
            topology_id = f"rapid_test_{i}"
            
            # Provision
            provider.provision(topology, topology_id)
            assert provider.is_ready(topology_id)
            
            # Teardown immediately
            assert provider.teardown(topology_id)
            
            # Should be fully cleaned up
            assert not provider.is_ready(topology_id)

    def test_long_running_task_completes(self):
        """Test that tasks with longer execution complete successfully."""
        repository = TaskRepository(Path("benchmark-tasks"))
        tasks = repository.load_tasks_by_property("reachability", limit=1)
        assert len(tasks) > 0
        task = tasks[0]
        
        # Create submission with sleep commands (simulating slow configuration)
        submission = Submission(
            task_id=task.task_id,
            testee_id="test_long_running",
            testee_type="test",
            approach=Approach(
                description="Test with slow commands",
                commands=[
                    CommandSequence(
                        node=task.topology.nodes[0].name,
                        commands=[
                            "sleep 2",  # 2 second delay
                            "echo 'Slow command completed'"
                        ]
                    )
                ]
            )
        )
        
        # Run benchmark
        controller = BenchmarkController()
        result = controller.run(task, submission)
        
        # Should complete successfully
        assert result.run_id is not None
        assert result.metrics.total_time >= 2.0  # At least 2 seconds due to sleep
        assert result.metrics.config_execution_time >= 2.0


@pytest.mark.integration
@pytest.mark.slow
class TestEndToEndFailureRecovery:
    """Test end-to-end failure recovery scenarios."""

    def test_property_executor_continues_after_task_failure(self):
        """Test that PropertyExecutor continues processing even if one task fails."""
        repository = TaskRepository(Path("benchmark-tasks"))
        controller = BenchmarkController()
        executor = PropertyExecutor(controller, repository)
        
        # Create testee that generates mostly working config but one bad command
        class PartiallyBrokenTestee(BaselineTestee):
            def __init__(self):
                super().__init__(testee_id="partially_broken")
                self.call_count = 0
            
            def generate_submission(self, task):
                submission = super().generate_submission(task)
                self.call_count += 1
                
                # Add one invalid command to make things interesting
                if submission.approach.commands and self.call_count % 2 == 0:
                    submission.approach.commands[0].commands.append(
                        "invalid_command_that_will_fail"
                    )
                
                return submission
        
        testee = PartiallyBrokenTestee()
        
        # Run multiple tasks
        result = executor.run_property_tasks(
            property_type="reachability",
            submission_generator=lambda task: testee.generate_submission(task),
            limit=2
        )
        
        # Should complete all tasks
        assert result.total_tasks == 2
        assert len(result.results) == 2
        # Both tasks should have attempted execution
        assert all(r.metrics.total_time > 0 for r in result.results)

    def test_infrastructure_cleanup_after_error(self):
        """Test that infrastructure is cleaned up even after errors."""
        repository = TaskRepository(Path("benchmark-tasks"))
        tasks = repository.load_tasks_by_property("reachability", limit=1)
        assert len(tasks) > 0
        task = tasks[0]
        
        # Create submission with commands that will cause issues
        submission = Submission(
            task_id=task.task_id,
            testee_id="test_cleanup",
            testee_type="test",
            approach=Approach(
                description="Test cleanup after errors",
                commands=[
                    CommandSequence(
                        node=task.topology.nodes[0].name,
                        commands=[
                            "invalid_command_xyz",
                            "echo 'This should still run'"
                        ]
                    )
                ]
            )
        )
        
        # Run benchmark
        controller = BenchmarkController()
        result = controller.run(task, submission)
        
        # Should complete and clean up
        assert result.run_id is not None
        
        # Verify no orphaned containers
        # (ContainerlabProvider should have cleaned up)
        provider = ContainerlabProvider()
        topology_id = result.run_id.replace("run_", "topology_")
        # Container should not exist after controller.run() completes
        assert not provider.is_ready(topology_id)

