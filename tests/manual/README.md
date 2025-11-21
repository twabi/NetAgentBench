# Manual Integration Tests

This directory contains manual integration tests that require:
- Real API credentials
- Real infrastructure (Docker/Containerlab)
- Extended execution time

## Quick Start

```bash
# Run real LLM benchmark test
python tests/manual/test_real_llm_benchmark.py --provider gemini --limit 1
```

## Documentation

For complete testing documentation, see:
- [Testing Guide](../../docs/TESTING.md) - Complete testing guide
- [LLM Integration](../../docs/LLM_INTEGRATION.md) - LLM provider setup

## Key Points

- These tests are not run in CI/CD
- Require API keys (OpenAI, Gemini, Anthropic)
- Use real LLM APIs (costs money)
- See [Testing Guide](../../docs/TESTING.md) for full details
