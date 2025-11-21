"""
Pytest configuration for integration tests.

Integration tests require:
- Containerlab installed
- Docker running
- sudo access
"""
import pytest
import time
import subprocess
from pathlib import Path
from benchmark.controller import BenchmarkController
from benchmark.task_repository import TaskRepository
from benchmark.property_executor import PropertyExecutor


def pytest_configure(config):
    """Register custom markers"""
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test (requires real infrastructure)",
    )
    config.addinivalue_line(
        "markers",
        "slow: mark test as slow (takes > 1 minute, uses real infrastructure heavily)",
    )
    config.addinivalue_line(
        "markers",
        "performance: mark test as performance benchmark",
    )
    config.addinivalue_line(
        "markers",
        "stress: mark test as stress test (high resource usage)",
    )
    config.addinivalue_line(
        "markers",
        "manual: mark test as manual (requires API keys or human interaction)",
    )
    config.addinivalue_line(
        "markers",
        "llm: mark test as LLM integration test (requires LLM API access)",
    )


@pytest.fixture
def ensure_cleanup():
    """Ensure cleanup happens even if test fails."""
    cleanup_commands = []
    
    def register_cleanup(cmd):
        """Register a cleanup command to run after test."""
        cleanup_commands.append(cmd)
    
    yield register_cleanup
    
    # Run all cleanup commands
    for cmd in cleanup_commands:
        try:
            subprocess.run(cmd, shell=True, capture_output=True, timeout=30)
        except Exception as e:
            print(f"Cleanup warning: {e}")


@pytest.fixture
def benchmark_controller():
    """Provide a real BenchmarkController instance."""
    return BenchmarkController()


@pytest.fixture
def task_repository():
    """Provide a TaskRepository instance."""
    return TaskRepository(Path("benchmark-tasks"))


@pytest.fixture
def property_executor(benchmark_controller, task_repository):
    """Provide a PropertyExecutor with real controller and repository."""
    return PropertyExecutor(benchmark_controller, task_repository)


@pytest.fixture
def timing_tracker():
    """Track and report test execution times."""
    times = {}
    
    class TimingTracker:
        def start(self, name):
            times[name] = {"start": time.time()}
        
        def end(self, name):
            if name in times:
                times[name]["end"] = time.time()
                times[name]["duration"] = times[name]["end"] - times[name]["start"]
        
        def report(self):
            print("\n" + "="*60)
            print("TIMING REPORT")
            print("="*60)
            for name, data in times.items():
                if "duration" in data:
                    print(f"  {name}: {data['duration']:.2f}s")
            print("="*60)
    
    tracker = TimingTracker()
    yield tracker
    tracker.report()


def pytest_collection_modifyitems(config, items):
    """Modify test collection to handle slow/manual markers."""
    # Add integration marker to all tests in integration directory
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)


def pytest_sessionfinish(session, exitstatus):
    """Clean up any orphaned containers after test session."""
    try:
        # List all containerlab topologies
        result = subprocess.run(
            ["sudo", "containerlab", "inspect", "--all"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0 and result.stdout:
            # Check for test-related topologies
            if "test_" in result.stdout.lower() or "rapid_" in result.stdout.lower():
                print("\n⚠️  Warning: Found test-related containers still running")
                print("    Run cleanup script: python scripts/cleanup_benchmark_networks.py")
    except Exception:
        pass  # Silently ignore if containerlab not available

