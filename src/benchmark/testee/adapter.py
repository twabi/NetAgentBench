"""
Testee Adapter interface for the benchmark system.

This module provides the TesteeAdapter alias for the BaseTestee class,
following the adapter pattern described in WS2.1 of the Phase 2 implementation.

The adapter pattern enables a unified interface for different types of testees:
- LLM testees (OpenAI, Gemini, Anthropic, Ollama)
- Human testees (interactive or JSON-based)
- Baseline testees (empty configurations)
- External adapters (REST API, dagent)

Example usage:
    from benchmark.testee import TesteeAdapter
    
    class MyCustomAdapter(TesteeAdapter):
        def generate_submission(self, task: TaskDefinition) -> Submission:
            # Custom implementation
            pass
        
        def get_testee_info(self) -> dict:
            return {"testee_id": "my_adapter", "testee_type": "custom"}
"""
from benchmark.testee.base import BaseTestee

# TesteeAdapter is an alias for BaseTestee, providing naming consistency
# with WS2.1 specification while maintaining backward compatibility.
TesteeAdapter = BaseTestee

__all__ = ["TesteeAdapter"]
