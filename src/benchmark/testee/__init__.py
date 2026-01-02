"""
Testee implementations for the benchmark system.

Provides various testee types:
- BaseTestee: Abstract interface
- TesteeAdapter: Alias for BaseTestee (WS2.1 naming)
- HumanJsonTestee: Load submissions from JSON files
- HumanInteractiveTestee: Interactive CLI prompts for submissions
- BaselineTestee: Generate baseline (empty) submissions
- DagentAdapter: Connect to dagent multi-agent systems (WS2.3)
- LLMTestee: Generate submissions using LLMs (implemented separately)
- MLModelTestee: Generate submissions using ML models (implemented separately)
"""
from benchmark.testee.base import BaseTestee
from benchmark.testee.adapter import TesteeAdapter
from benchmark.testee.human import HumanJsonTestee, HumanInteractiveTestee
from benchmark.testee.baseline import BaselineTestee
from benchmark.testee.dagent_adapter import DagentAdapter

__all__ = [
    "BaseTestee",
    "TesteeAdapter",
    "HumanJsonTestee",
    "HumanInteractiveTestee",
    "BaselineTestee",
    "DagentAdapter",
]
