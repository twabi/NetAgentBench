"""
Testee implementations for the benchmark system.

Provides various testee types:
- BaseTestee: Abstract interface
- HumanJsonTestee: Load submissions from JSON files
- HumanInteractiveTestee: Interactive CLI prompts for submissions
- BaselineTestee: Generate baseline (empty) submissions
- LLMTestee: Generate submissions using LLMs (implemented separately)
- MLModelTestee: Generate submissions using ML models (implemented separately)
"""
from benchmark.testee.base import BaseTestee
from benchmark.testee.human import HumanJsonTestee, HumanInteractiveTestee
from benchmark.testee.baseline import BaselineTestee

__all__ = ["BaseTestee", "HumanJsonTestee", "HumanInteractiveTestee", "BaselineTestee"]

