# Integration Test Suite

Comprehensive integration tests for the Network Configuration Benchmark system using **REAL infrastructure** (no mocks).

## Quick Start

```bash
# Run all integration tests
pytest tests/integration/ -v

# Run fast tests only
pytest tests/integration/ -m "integration and not slow" -v
```

## Documentation

For complete testing documentation, see:
- [Testing Guide](../../docs/TESTING.md) - Complete testing guide with all details

## Key Points

- All tests use **real Containerlab** and **real Docker containers**
- Tests are organized by markers: `slow`, `performance`, `stress`, `manual`, `llm`
- Execution time: ~15-20 minutes for full suite
- Requires Docker and Containerlab installed

See [Testing Guide](../../docs/TESTING.md) for full details.
