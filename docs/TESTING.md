# Testing Guide

This document describes how to run and write tests for the Network Configuration Benchmark system.

## Overview

The benchmark system uses pytest for testing. Tests are organized into:
- **Unit tests** - Fast tests that don't require external dependencies
- **Integration tests** - Tests that use real infrastructure (Containerlab, Docker)

## Running Tests

### All Tests

```bash
# Run all tests
poetry run pytest

# With verbose output
poetry run pytest -v

# With coverage
poetry run pytest --cov=benchmark --cov-report=html
```

### Unit Tests

Unit tests are fast and don't require external dependencies:

```bash
# Run all unit tests
poetry run pytest tests/unit/ -v

# Run specific test file
poetry run pytest tests/unit/test_models.py -v

# Run specific test
poetry run pytest tests/unit/test_models.py::test_node_creation -v
```

### Integration Tests

Integration tests use **real infrastructure** (no mocks):

```bash
# Run all integration tests
poetry run pytest tests/integration/ -v

# Run with integration marker
poetry run pytest -m integration -v
```

**⚠️ Warning**: Integration tests take 15-20 minutes and spin up many containers.

### Test Categories

Tests are organized by markers:

```bash
# Fast tests (< 1 minute)
poetry run pytest -m "integration and not slow" -v

# Slow tests (> 1 minute)
poetry run pytest -m slow -v

# Performance benchmarks
poetry run pytest -m performance -v

# Stress tests
poetry run pytest -m stress -v

# Manual tests (require API keys)
poetry run pytest -m manual -v

# LLM tests (require LLM API access)
poetry run pytest -m llm -v
```

## Test Markers

The test suite uses pytest markers to categorize tests:

| Marker | Description | Usage |
|--------|-------------|-------|
| `integration` | All integration tests | Auto-applied to all tests in `tests/integration/` |
| `slow` | Tests taking > 1 minute | Heavy infrastructure usage |
| `performance` | Performance benchmarks | Timing validation |
| `stress` | Stress/reliability tests | High resource usage |
| `manual` | Requires manual setup | API keys, human interaction |
| `llm` | LLM provider tests | Requires LLM API access |

### Example Usage

```bash
# Run only fast integration tests
poetry run pytest -m "integration and not slow"

# Run only performance tests
poetry run pytest -m performance

# Run stress tests only
poetry run pytest -m stress

# Skip manual/LLM tests
poetry run pytest -m "not manual and not llm"

# Run specific combination
poetry run pytest -m "integration and not (slow or manual)"
```

## Test Structure

### Unit Tests

Located in `tests/unit/`:

- `test_models.py` - Model validation tests
- `test_executor.py` - Command execution tests
- `test_evaluator.py` - Property evaluation tests
- `test_scoring.py` - Scoring calculation tests
- `test_storage.py` - Storage tests
- `test_cli.py` - CLI tests
- `test_documentation.py` - Documentation structure tests

### Integration Tests

Located in `tests/integration/`:

- `test_end_to_end_tasks.py` - Complete workflow tests
- `test_controller_integration.py` - Controller integration tests
- `test_containerlab_integration.py` - Containerlab integration tests
- `test_evaluator_integration.py` - Evaluator integration tests
- `test_executor_integration.py` - Executor integration tests
- `test_storage_integration.py` - Storage integration tests
- `test_benchmark_suite.py` - Benchmark suite tests
- `test_phase10_integration.py` - Property-based execution tests
- `test_llm_integration.py` - LLM integration tests
- `test_performance.py` - Performance tests
- `test_stress.py` - Stress tests
- `test_failure_scenarios.py` - Failure scenario tests

### Manual Tests

Located in `tests/manual/`:

- `test_real_llm_benchmark.py` - Real LLM benchmark test

**Note**: Manual tests require API keys and are not run in CI/CD.

## Writing Tests

### Unit Test Example

```python
import pytest
from benchmark.models.task import Node, NodeType, Platform

def test_node_creation():
    """Test creating a valid node"""
    node = Node(name="R1", type=NodeType.ROUTER, platform=Platform.FRR)
    assert node.name == "R1"
    assert node.type == NodeType.ROUTER
    assert node.platform == Platform.FRR

def test_node_requires_name():
    """Test that node requires a name"""
    with pytest.raises(ValueError):
        Node(type=NodeType.ROUTER)
```

### Integration Test Example

```python
import pytest
from benchmark.controller import BenchmarkController
from benchmark.models.task import TaskDefinition
from benchmark.models.submission import Submission

@pytest.mark.integration
def test_bgp_basic_end_to_end(task_repository, tmp_path):
    """Test complete BGP benchmark workflow"""
    # Load task
    task = task_repository.get_task("bgp_basic")
    
    # Create submission
    submission = Submission(
        task_id="bgp_basic",
        testee_id="test_baseline",
        testee_type="baseline",
        approach={
            "description": "Test BGP configuration",
            "commands": [
                {
                    "node": "R1",
                    "commands": [
                        "vtysh -c 'configure terminal'",
                        "vtysh -c 'router bgp 65001'",
                        "vtysh -c 'neighbor 192.168.1.2 remote-as 65002'",
                        "vtysh -c 'end'"
                    ]
                }
            ]
        }
    )
    
    # Run benchmark
    controller = BenchmarkController()
    result = controller.run(task, submission)
    
    # Assertions
    assert result.valid_solution is True
    assert result.scoring.final_score > 0.8
```

### Test Fixtures

Common fixtures are available in `tests/integration/conftest.py`:

- `task_repository` - Task repository fixture
- `tmp_path` - Temporary directory fixture
- `ensure_cleanup` - Cleanup fixture for containers

## Test Execution Times

Approximate execution times (on standard hardware):

| Test Category | Time | Container Count |
|---------------|------|-----------------|
| Fast tests | ~5 minutes | 5-10 containers |
| All integration | ~15-20 minutes | 30-50 containers |
| Performance tests | ~10-15 minutes | 20-30 containers |
| Stress tests | ~15-20 minutes | 30-40 containers |
| LLM tests | ~5-10 minutes + API latency | Variable |

## Prerequisites

### Required

- Docker (installed and running)
- Containerlab (`sudo clab version` works)
- Sudo access (for containerlab commands)
- Python 3.10+ with all dependencies installed

### Optional (for LLM tests)

- OpenAI API key (set `OPENAI_API_KEY` in `.env`)
- Gemini API key (set `GEMINI_API_KEY` in `.env`)
- Anthropic API key (set `ANTHROPIC_API_KEY` in `.env`)

## Cleanup

### Automatic Cleanup

Tests automatically clean up containers after execution. The `conftest.py` provides:
- `ensure_cleanup` fixture for test-level cleanup
- Session-level cleanup check after all tests

### Manual Cleanup

If containers are orphaned (test crashes, etc.):

```bash
# Use the cleanup script
python scripts/cleanup_benchmark_networks.py

# Or manually
sudo containerlab destroy --all
docker ps -a | grep clab | awk '{print $1}' | xargs docker rm -f
```

### Verify Cleanup

```bash
# Check for running containers
docker ps

# Check for containerlab topologies
sudo containerlab inspect --all

# Should see no test-related containers/topologies
```

## Troubleshooting

### Tests Fail with "Permission Denied"

```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Log out and back in, or:
newgrp docker
```

### Tests Hang or Timeout

- Check Docker is running: `docker ps`
- Check Containerlab: `sudo clab version`
- Increase timeouts if network is slow
- Clean up orphaned containers

### "Address already in use" Errors

```bash
# Clean up all containers
python scripts/cleanup_benchmark_networks.py

# Check no containers running
docker ps
```

### LLM Tests Fail

- Verify API key is set: `echo $OPENAI_API_KEY` (or check `.env`)
- Check API key is valid (not expired)
- Ensure sufficient API credits
- Check network connectivity

### Too Many Containers Running

```bash
# Get container count
docker ps -q | wc -l

# If too many, clean up
python scripts/cleanup_benchmark_networks.py
```

## Best Practices

### For Development

1. Run fast tests first: `poetry run pytest -m "integration and not slow"`
2. Fix any failures before running full suite
3. Clean up regularly: `python scripts/cleanup_benchmark_networks.py`
4. Monitor disk space (containers can use significant space)

### For CI/CD

1. Use markers to control which tests run
2. Set appropriate timeouts (tests can take 20+ minutes)
3. Ensure cleanup runs even on failure
4. Consider splitting into stages:
   - Stage 1: Fast tests
   - Stage 2: Slow tests
   - Stage 3: Performance tests
   - Stage 4: Stress tests
   - Manual: LLM tests (optional)

### For Performance Testing

1. Run on consistent hardware
2. Close other applications
3. Use performance markers: `poetry run pytest -m performance`
4. Save timing reports for comparison
5. Look for regressions in bottleneck analysis

### Writing Tests

1. **NO MOCKS** - Use real infrastructure only (for integration tests)
2. **Add appropriate markers** - `@pytest.mark.slow`, `@pytest.mark.performance`, etc.
3. **Clean up resources** - Use fixtures or try/finally
4. **Test real failures** - Use actual failing scenarios, not mocked exceptions
5. **Document** - Add docstrings explaining what's being tested
6. **Time limits** - Consider test execution time (mark as slow if > 1 min)

## Coverage

### Running Coverage

```bash
# Generate coverage report
poetry run pytest --cov=benchmark --cov-report=html

# View coverage report
open htmlcov/index.html  # On macOS
xdg-open htmlcov/index.html  # On Linux
```

### Coverage Goals

- Unit tests: > 90% coverage
- Integration tests: Cover all major workflows
- Overall: > 80% coverage

## Related Documentation

- [Getting Started](GETTING_STARTED.md) - Installation and setup
- [Architecture](ARCHITECTURE.md) - System architecture
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues and solutions

---

**Last Updated**: Phase 12 - Documentation Consolidation

