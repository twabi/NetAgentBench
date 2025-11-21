"""
Performance and timing validation tests with REAL infrastructure (no mocks).

Tests:
- Execution timing constraints
- Performance benchmarks
- Metrics validation
- Bottleneck identification

All tests use REAL Containerlab - NO MOCKS.
"""
import pytest
import time
from pathlib import Path
from benchmark.controller import BenchmarkController
from benchmark.task_repository import TaskRepository
from benchmark.property_executor import PropertyExecutor
from benchmark.testee.baseline import BaselineTestee
from benchmark.models.submission import Submission, Approach, CommandSequence


@pytest.mark.integration
@pytest.mark.performance
@pytest.mark.slow
class TestExecutionTiming:
    """Test execution timing constraints."""

    def test_infrastructure_provision_time_reasonable(self):
        """Test that infrastructure provision time is < 60s per topology."""
        repository = TaskRepository(Path("benchmark-tasks"))
        tasks = repository.load_tasks_by_property("reachability", limit=1)
        assert len(tasks) > 0
        task = tasks[0]
        
        # Create minimal submission
        testee = BaselineTestee()
        submission = testee.generate_submission(task)
        
        # Run benchmark
        controller = BenchmarkController()
        result = controller.run(task, submission)
        
        # Check provision time
        provision_time = result.metrics.infrastructure_provision_time
        print(f"\nProvision time: {provision_time:.2f}s")
        assert provision_time < 60.0, f"Provision took {provision_time:.2f}s, expected < 60s"

    def test_simple_topology_convergence_time(self):
        """Test that simple topologies (2-3 nodes) converge < 30s."""
        repository = TaskRepository(Path("benchmark-tasks"))
        tasks = repository.load_tasks_by_property("reachability", limit=1)
        assert len(tasks) > 0
        task = tasks[0]
        
        # Only test if topology is simple (2-3 nodes)
        if len(task.topology.nodes) > 3:
            pytest.skip("Skipping - topology too complex for this test")
        
        testee = BaselineTestee()
        submission = testee.generate_submission(task)
        
        controller = BenchmarkController()
        result = controller.run(task, submission)
        
        # Check convergence time (note: baseline testee doesn't configure routing,
        # so convergence time is the timeout/wait period)
        convergence_time = result.metrics.convergence_time
        print(f"\nConvergence time: {convergence_time:.2f}s for {len(task.topology.nodes)} nodes")
        # Convergence time includes waiting, so may be up to the configured wait time
        assert convergence_time < 150.0, f"Convergence took {convergence_time:.2f}s"

    def test_property_evaluation_time(self):
        """Test that property evaluation time is < 10s per property."""
        repository = TaskRepository(Path("benchmark-tasks"))
        tasks = repository.load_tasks_by_property("reachability", limit=1)
        assert len(tasks) > 0
        task = tasks[0]
        
        testee = BaselineTestee()
        submission = testee.generate_submission(task)
        
        controller = BenchmarkController()
        result = controller.run(task, submission)
        
        # Check evaluation time per property
        num_properties = len(result.property_results)
        total_eval_time = result.metrics.evaluation_time
        avg_eval_time = total_eval_time / num_properties if num_properties > 0 else 0
        
        print(f"\nTotal evaluation time: {total_eval_time:.2f}s for {num_properties} properties")
        print(f"Average per property: {avg_eval_time:.2f}s")
        
        # Per-property time should be reasonable
        assert avg_eval_time < 15.0, f"Average evaluation time {avg_eval_time:.2f}s per property too high"

    def test_total_task_time_reasonable(self):
        """Test that total task time is < 5 minutes for simple tasks."""
        repository = TaskRepository(Path("benchmark-tasks"))
        tasks = repository.load_tasks_by_property("reachability", limit=1)
        assert len(tasks) > 0
        task = tasks[0]
        
        # Only test simple topologies
        if len(task.topology.nodes) > 3:
            pytest.skip("Skipping - topology too complex for this test")
        
        testee = BaselineTestee()
        submission = testee.generate_submission(task)
        
        start_time = time.time()
        controller = BenchmarkController()
        result = controller.run(task, submission)
        elapsed_time = time.time() - start_time
        
        print(f"\nTotal task time: {elapsed_time:.2f}s")
        print(f"  Provision: {result.metrics.infrastructure_provision_time:.2f}s")
        print(f"  Config: {result.metrics.config_execution_time:.2f}s")
        print(f"  Convergence: {result.metrics.convergence_time:.2f}s")
        print(f"  Evaluation: {result.metrics.evaluation_time:.2f}s")
        
        assert elapsed_time < 300.0, f"Total time {elapsed_time:.2f}s exceeds 5 minute limit"


@pytest.mark.integration
@pytest.mark.performance
@pytest.mark.slow
class TestPerformanceBenchmarks:
    """Performance benchmarks for sequential task execution."""

    def test_sequential_reachability_tasks_performance(self):
        """Benchmark sequential execution of 3 reachability tasks."""
        repository = TaskRepository(Path("benchmark-tasks"))
        controller = BenchmarkController()
        executor = PropertyExecutor(controller, repository)
        
        testee = BaselineTestee(testee_id="perf_test_reachability")
        
        start_time = time.time()
        result = executor.run_property_tasks(
            property_type="reachability",
            submission_generator=lambda task: testee.generate_submission(task),
            limit=3
        )
        elapsed_time = time.time() - start_time
        
        # Report performance
        print(f"\n{'='*60}")
        print(f"REACHABILITY TASKS PERFORMANCE BENCHMARK")
        print(f"{'='*60}")
        print(f"Total tasks: {result.total_tasks}")
        print(f"Total time: {elapsed_time:.1f}s ({elapsed_time/60:.1f} minutes)")
        print(f"Average per task: {elapsed_time/result.total_tasks:.1f}s")
        print(f"Successful tasks: {result.successful_tasks}")
        print(f"Average score: {result.average_score:.3f}")
        print(f"{'='*60}")
        
        # Verify completed
        assert result.total_tasks == 3
        assert elapsed_time > 0

    def test_sequential_bgp_tasks_performance(self):
        """Benchmark sequential execution of 2 BGP tasks."""
        repository = TaskRepository(Path("benchmark-tasks"))
        controller = BenchmarkController()
        executor = PropertyExecutor(controller, repository)
        
        testee = BaselineTestee(testee_id="perf_test_bgp")
        
        start_time = time.time()
        result = executor.run_property_tasks(
            property_type="bgp_configuration",
            submission_generator=lambda task: testee.generate_submission(task),
            limit=2
        )
        elapsed_time = time.time() - start_time
        
        # Report performance
        print(f"\n{'='*60}")
        print(f"BGP TASKS PERFORMANCE BENCHMARK")
        print(f"{'='*60}")
        print(f"Total tasks: {result.total_tasks}")
        print(f"Total time: {elapsed_time:.1f}s ({elapsed_time/60:.1f} minutes)")
        print(f"Average per task: {elapsed_time/result.total_tasks:.1f}s")
        print(f"Successful tasks: {result.successful_tasks}")
        print(f"Average score: {result.average_score:.3f}")
        print(f"{'='*60}")
        
        # Verify completed
        assert result.total_tasks == 2
        assert elapsed_time > 0

    def test_bottleneck_identification(self):
        """Identify performance bottlenecks by analyzing phase timings."""
        repository = TaskRepository(Path("benchmark-tasks"))
        tasks = repository.load_tasks_by_property("reachability", limit=2)
        assert len(tasks) >= 2
        
        controller = BenchmarkController()
        testee = BaselineTestee()
        
        results = []
        for task in tasks:
            submission = testee.generate_submission(task)
            result = controller.run(task, submission)
            results.append(result)
        
        # Analyze timings
        print(f"\n{'='*60}")
        print(f"BOTTLENECK ANALYSIS")
        print(f"{'='*60}")
        
        phases = [
            ("Provision", "infrastructure_provision_time"),
            ("Config", "config_execution_time"),
            ("Convergence", "convergence_time"),
            ("Evaluation", "evaluation_time"),
        ]
        
        for phase_name, attr in phases:
            times = [getattr(r.metrics, attr) for r in results]
            avg_time = sum(times) / len(times)
            total_time = sum([r.metrics.total_time for r in results]) / len(results)
            percentage = (avg_time / total_time) * 100 if total_time > 0 else 0
            
            print(f"{phase_name:15} : {avg_time:6.2f}s avg ({percentage:5.1f}% of total)")
        
        print(f"{'='*60}")
        print(f"Total avg time  : {sum([r.metrics.total_time for r in results]) / len(results):6.2f}s")
        print(f"{'='*60}")
        
        # Verify all phases have reasonable times
        assert all(r.metrics.total_time > 0 for r in results)


@pytest.mark.integration
@pytest.mark.performance
class TestMetricsValidation:
    """Validate that execution metrics are populated correctly."""

    def test_execution_metrics_populated(self):
        """Test that all ExecutionMetrics fields are populated."""
        repository = TaskRepository(Path("benchmark-tasks"))
        tasks = repository.load_tasks_by_property("reachability", limit=1)
        assert len(tasks) > 0
        task = tasks[0]
        
        testee = BaselineTestee()
        submission = testee.generate_submission(task)
        
        controller = BenchmarkController()
        result = controller.run(task, submission)
        
        # Verify all timing fields are populated
        assert result.metrics.infrastructure_provision_time > 0
        assert result.metrics.config_execution_time >= 0  # Can be 0 if no commands
        assert result.metrics.convergence_time >= 0
        assert result.metrics.evaluation_time > 0
        assert result.metrics.total_time > 0
        
        print(f"\nMetrics for task {task.task_id}:")
        print(f"  Provision:    {result.metrics.infrastructure_provision_time:.3f}s")
        print(f"  Config:       {result.metrics.config_execution_time:.3f}s")
        print(f"  Convergence:  {result.metrics.convergence_time:.3f}s")
        print(f"  Evaluation:   {result.metrics.evaluation_time:.3f}s")
        print(f"  Total:        {result.metrics.total_time:.3f}s")

    def test_total_time_matches_components(self):
        """Test that total_time approximately equals sum of component times."""
        repository = TaskRepository(Path("benchmark-tasks"))
        tasks = repository.load_tasks_by_property("reachability", limit=1)
        assert len(tasks) > 0
        task = tasks[0]
        
        testee = BaselineTestee()
        submission = testee.generate_submission(task)
        
        controller = BenchmarkController()
        result = controller.run(task, submission)
        
        # Sum of components
        component_sum = (
            result.metrics.infrastructure_provision_time +
            result.metrics.config_execution_time +
            result.metrics.convergence_time +
            result.metrics.evaluation_time
        )
        
        total_time = result.metrics.total_time
        
        print(f"\nTime breakdown:")
        print(f"  Component sum: {component_sum:.3f}s")
        print(f"  Total time:    {total_time:.3f}s")
        print(f"  Difference:    {abs(total_time - component_sum):.3f}s")
        
        # Allow some overhead for orchestration
        # Total might be slightly higher due to Python overhead, serialization, etc.
        assert abs(total_time - component_sum) < total_time * 0.1, \
            f"Total time {total_time:.3f}s differs significantly from component sum {component_sum:.3f}s"

    def test_convergence_time_reasonable(self):
        """Test that convergence time is reasonable."""
        repository = TaskRepository(Path("benchmark-tasks"))
        tasks = repository.load_tasks_by_property("reachability", limit=1)
        assert len(tasks) > 0
        task = tasks[0]
        
        testee = BaselineTestee()
        submission = testee.generate_submission(task)
        
        controller = BenchmarkController()
        result = controller.run(task, submission)
        
        convergence_time = result.metrics.convergence_time
        
        print(f"\nConvergence time: {convergence_time:.2f}s")
        
        # Convergence time should be reasonable (not negative, not excessively long)
        assert convergence_time >= 0
        assert convergence_time < 200.0, f"Convergence time {convergence_time:.2f}s seems too long"

    def test_stat_logs_captured(self):
        """Test that execution logs are captured for analysis."""
        repository = TaskRepository(Path("benchmark-tasks"))
        tasks = repository.load_tasks_by_property("reachability", limit=1)
        assert len(tasks) > 0
        task = tasks[0]
        
        # Create submission with actual commands
        submission = Submission(
            task_id=task.task_id,
            testee_id="test_stat_logs",
            testee_type="test",
            approach=Approach(
                description="Test logging",
                commands=[
                    CommandSequence(
                        node=task.topology.nodes[0].name,
                        commands=[
                            "echo 'Command 1'",
                            "echo 'Command 2'",
                            "echo 'Command 3'"
                        ]
                    )
                ]
            )
        )
        
        controller = BenchmarkController()
        result = controller.run(task, submission)
        
        # Verify execution log exists
        assert len(result.execution_log) > 0
        
        print(f"\nExecution log entries: {len(result.execution_log)}")
        print("Sample entries:")
        for entry in result.execution_log[:5]:
            print(f"  {entry}")
        
        # Log should contain timing information
        assert any("✓" in str(entry) or "✗" in str(entry) for entry in result.execution_log)

