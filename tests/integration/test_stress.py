"""
Stress and reliability tests with REAL infrastructure (no mocks).

Tests:
- Sequential execution
- Mixed property types
- Rapid provision/teardown
- Resource leak detection
- System reliability under load

All tests use REAL Containerlab - NO MOCKS.
"""
import pytest
import subprocess
import time
from pathlib import Path
from benchmark.controller import BenchmarkController
from benchmark.task_repository import TaskRepository
from benchmark.property_executor import PropertyExecutor
from benchmark.testee.baseline import BaselineTestee
from benchmark.infrastructure.containerlab import ContainerlabProvider
from benchmark.models.task import Node, NodeType, Platform, TopologySpecification


@pytest.mark.integration
@pytest.mark.stress
@pytest.mark.slow
class TestSequentialExecution:
    """Test sequential execution stress scenarios with REAL infrastructure."""

    def test_run_10_tasks_sequentially(self):
        """Run 10 tasks sequentially (same property type)."""
        repository = TaskRepository(Path("benchmark-tasks"))
        controller = BenchmarkController()  # REAL controller
        executor = PropertyExecutor(controller, repository)
        
        testee = BaselineTestee(testee_id="stress_sequential_10")
        
        # Run 10 tasks
        start_time = time.time()
        result = executor.run_property_tasks(
            property_type="reachability",
            submission_generator=lambda task: testee.generate_submission(task),
            limit=10
        )
        elapsed_time = time.time() - start_time
        
        # Verify all completed successfully
        assert result.total_tasks == 10
        assert len(result.results) == 10
        
        # All should have executed
        assert all(r.metrics.total_time > 0 for r in result.results)
        
        print(f"\n{'='*60}")
        print(f"SEQUENTIAL EXECUTION STRESS TEST")
        print(f"{'='*60}")
        print(f"  Total tasks: {result.total_tasks}")
        print(f"  Total time: {elapsed_time:.1f}s ({elapsed_time/60:.1f} minutes)")
        print(f"  Avg per task: {elapsed_time/result.total_tasks:.1f}s")
        print(f"  Successful: {result.successful_tasks}")
        print(f"{'='*60}")

    def test_verify_no_resource_leaks(self):
        """Verify no resource leaks during sequential execution."""
        repository = TaskRepository(Path("benchmark-tasks"))
        controller = BenchmarkController()  # REAL controller
        executor = PropertyExecutor(controller, repository)
        
        testee = BaselineTestee(testee_id="stress_leak_test")
        
        # Get baseline container count
        try:
            initial_result = subprocess.run(
                ["docker", "ps", "-q"],
                capture_output=True,
                text=True,
                check=True
            )
            initial_containers = [c for c in initial_result.stdout.strip().split('\n') if c]
            initial_count = len(initial_containers)
        except Exception:
            pytest.skip("Docker not available for container counting")
        
        # Run multiple tasks
        result = executor.run_property_tasks(
            property_type="reachability",
            submission_generator=lambda task: testee.generate_submission(task),
            limit=5
        )
        
        # Verify execution completed
        assert result.total_tasks == 5
        
        # Check final container count
        final_result = subprocess.run(
            ["docker", "ps", "-q"],
            capture_output=True,
            text=True,
            check=True
        )
        final_containers = [c for c in final_result.stdout.strip().split('\n') if c]
        final_count = len(final_containers)
        
        print(f"\n{'='*60}")
        print(f"RESOURCE LEAK TEST")
        print(f"{'='*60}")
        print(f"  Tasks executed: {result.total_tasks}")
        print(f"  Initial containers: {initial_count}")
        print(f"  Final containers: {final_count}")
        print(f"  Leaked containers: {max(0, final_count - initial_count)}")
        print(f"{'='*60}")
        
        # Should not have significant leaks (allow 1-2 for race conditions)
        assert final_count <= initial_count + 2, \
            f"Resource leak detected: {final_count - initial_count} extra containers"


@pytest.mark.integration
@pytest.mark.stress
@pytest.mark.slow
class TestMixedPropertyTypes:
    """Test stress with mixed property types."""

    def test_run_mixed_property_types_sequentially(self):
        """Run 3 reachability + 2 BGP + 2 OSPF tasks sequentially."""
        repository = TaskRepository(Path("benchmark-tasks"))
        controller = BenchmarkController()  # REAL controller
        executor = PropertyExecutor(controller, repository)
        
        testee = BaselineTestee(testee_id="stress_mixed")
        
        results = {}
        total_time = 0.0
        
        # Run reachability tasks
        start = time.time()
        reach_result = executor.run_property_tasks(
            property_type="reachability",
            submission_generator=lambda task: testee.generate_submission(task),
            limit=3
        )
        total_time += time.time() - start
        results["reachability"] = reach_result
        
        # Run BGP tasks
        start = time.time()
        bgp_result = executor.run_property_tasks(
            property_type="bgp_configuration",
            submission_generator=lambda task: testee.generate_submission(task),
            limit=2
        )
        total_time += time.time() - start
        results["bgp_configuration"] = bgp_result
        
        # Run OSPF tasks
        start = time.time()
        ospf_result = executor.run_property_tasks(
            property_type="ospf_configuration",
            submission_generator=lambda task: testee.generate_submission(task),
            limit=2
        )
        total_time += time.time() - start
        results["ospf_configuration"] = ospf_result
        
        # Verify all completed
        total_tasks = sum(r.total_tasks for r in results.values())
        assert total_tasks == 7  # 3 + 2 + 2
        
        print(f"\n{'='*60}")
        print(f"MIXED PROPERTY TYPES STRESS TEST")
        print(f"{'='*60}")
        print(f"  Total tasks: {total_tasks}")
        print(f"  Total time: {total_time:.1f}s ({total_time/60:.1f} minutes)")
        print(f"  Avg per task: {total_time/total_tasks:.1f}s")
        for prop_type, result in results.items():
            print(f"  {prop_type}: {result.successful_tasks}/{result.total_tasks} successful")
        print(f"{'='*60}")


@pytest.mark.integration
@pytest.mark.stress
class TestRapidProvisionTeardown:
    """Test rapid provision and teardown stress scenarios."""

    def test_rapid_provision_teardown_5_times(self):
        """Provision and teardown same topology 5 times rapidly."""
        provider = ContainerlabProvider()
        topology = TopologySpecification(
            nodes=[
                Node(
                    name="rapid_node",
                    type=NodeType.LINUX,
                    image="alpine:latest",
                    platform=Platform.FRR
                )
            ],
            links=[]
        )
        
        success_count = 0
        
        for i in range(5):
            topology_id = f"rapid_stress_{i}"
            
            try:
                # Provision
                provider.provision(topology, topology_id)
                assert provider.is_ready(topology_id)
                
                # Small delay
                time.sleep(0.5)
                
                # Teardown
                assert provider.teardown(topology_id)
                
                # Verify cleaned up
                assert not provider.is_ready(topology_id)
                
                success_count += 1
            except Exception as e:
                print(f"\nIteration {i} failed: {e}")
                # Try to clean up
                try:
                    provider.teardown(topology_id)
                except:
                    pass
        
        print(f"\n{'='*60}")
        print(f"RAPID PROVISION/TEARDOWN STRESS TEST")
        print(f"{'='*60}")
        print(f"  Iterations: 5")
        print(f"  Successful: {success_count}")
        print(f"  Success rate: {success_count/5*100:.0f}%")
        print(f"{'='*60}")
        
        # At least 4 out of 5 should succeed
        assert success_count >= 4, \
            f"Too many failures in rapid provision/teardown: {5 - success_count}/5 failed"

    def test_no_container_name_conflicts(self):
        """Test that rapid provision doesn't cause container name conflicts."""
        provider = ContainerlabProvider()
        topology = TopologySpecification(
            nodes=[
                Node(
                    name="conflict_test",
                    type=NodeType.LINUX,
                    image="alpine:latest",
                    platform=Platform.FRR
                )
            ],
            links=[]
        )
        
        # Use same topology_id pattern but ensure cleanup between
        for i in range(3):
            topology_id = f"conflict_test_{i % 2}"  # Alternate between 2 IDs
            
            # Ensure clean state
            try:
                provider.teardown(topology_id)
            except:
                pass
            
            # Provision
            provider.provision(topology, topology_id)
            assert provider.is_ready(topology_id)
            
            # Teardown
            assert provider.teardown(topology_id)
            assert not provider.is_ready(topology_id)
        
        print(f"\n✅ No container name conflicts detected")


@pytest.mark.integration
@pytest.mark.stress
@pytest.mark.slow
class TestSystemReliability:
    """Test system reliability under various conditions."""

    def test_mixed_success_and_failure_tasks(self):
        """Test system handles mix of successful and failing tasks."""
        repository = TaskRepository(Path("benchmark-tasks"))
        controller = BenchmarkController()  # REAL controller
        executor = PropertyExecutor(controller, repository)
        
        # Create testee that alternates between working and broken
        class AlternatingTestee(BaselineTestee):
            def __init__(self):
                super().__init__(testee_id="alternating")
                self.call_count = 0
            
            def generate_submission(self, task):
                submission = super().generate_submission(task)
                self.call_count += 1
                
                # Even calls: add invalid command
                # Odd calls: leave as is (baseline)
                if self.call_count % 2 == 0 and submission.approach.commands:
                    submission.approach.commands[0].commands.insert(0, 
                        "invalid_command_will_fail"
                    )
                
                return submission
        
        testee = AlternatingTestee()
        
        # Run multiple tasks
        result = executor.run_property_tasks(
            property_type="reachability",
            submission_generator=lambda task: testee.generate_submission(task),
            limit=6
        )
        
        # All should complete (some may have errors)
        assert result.total_tasks == 6
        assert len(result.results) == 6
        assert all(r.metrics.total_time > 0 for r in result.results)
        
        print(f"\n{'='*60}")
        print(f"MIXED SUCCESS/FAILURE RELIABILITY TEST")
        print(f"{'='*60}")
        print(f"  Total tasks: {result.total_tasks}")
        print(f"  Successful: {result.successful_tasks}")
        print(f"  Failed: {result.total_tasks - result.successful_tasks}")
        print(f"  System remained stable: ✅")
        print(f"{'='*60}")

    def test_long_running_suite_stability(self):
        """Test that system remains stable during long-running suite."""
        repository = TaskRepository(Path("benchmark-tasks"))
        controller = BenchmarkController()  # REAL controller
        executor = PropertyExecutor(controller, repository)
        
        testee = BaselineTestee(testee_id="long_running")
        
        start_time = time.time()
        
        # Run a moderate number of tasks
        result = executor.run_property_tasks(
            property_type="reachability",
            submission_generator=lambda task: testee.generate_submission(task),
            limit=5
        )
        
        elapsed_time = time.time() - start_time
        
        # Verify stability
        assert result.total_tasks == 5
        assert len(result.results) == 5
        
        # All should have valid metrics
        assert all(r.metrics.total_time > 0 for r in result.results)
        assert all(r.metrics.infrastructure_provision_time > 0 for r in result.results)
        
        # No crashes or hung processes
        assert elapsed_time < 3600, "Suite took > 1 hour, something may be wrong"
        
        print(f"\n{'='*60}")
        print(f"LONG-RUNNING SUITE STABILITY TEST")
        print(f"{'='*60}")
        print(f"  Tasks: {result.total_tasks}")
        print(f"  Duration: {elapsed_time/60:.1f} minutes")
        print(f"  System remained stable: ✅")
        print(f"  No hangs or crashes: ✅")
        print(f"{'='*60}")


@pytest.mark.integration
@pytest.mark.stress
class TestResourceMonitoring:
    """Test resource usage monitoring."""

    def test_measure_peak_resource_usage(self):
        """Measure peak resource usage during task execution."""
        repository = TaskRepository(Path("benchmark-tasks"))
        controller = BenchmarkController()  # REAL controller
        
        testee = BaselineTestee()
        tasks = repository.load_tasks_by_property("reachability", limit=3)
        assert len(tasks) >= 3
        
        # Track metrics
        peak_containers = 0
        
        for task in tasks:
            submission = testee.generate_submission(task)
            
            # Count containers before
            try:
                result = subprocess.run(
                    ["docker", "ps", "-q"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                container_count = len([c for c in result.stdout.strip().split('\n') if c])
                peak_containers = max(peak_containers, container_count)
            except:
                pass
            
            # Run task
            controller.run(task, submission)
        
        print(f"\n{'='*60}")
        print(f"RESOURCE USAGE MONITORING")
        print(f"{'='*60}")
        print(f"  Tasks executed: 3")
        print(f"  Peak containers: {peak_containers}")
        print(f"{'='*60}")
        
        # Should use reasonable resources (not thousands of containers)
        assert peak_containers < 100, f"Too many containers: {peak_containers}"

