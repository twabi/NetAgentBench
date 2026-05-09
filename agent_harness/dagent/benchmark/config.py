"""
Configuration classes for benchmark agents.

Defines agent modes (single/multi) and structures (sequential, etc.).
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional


class AgentMode(Enum):
    """Agent execution mode."""
    SINGLE = "single"  # Single LLM agent with tools
    MULTI = "multi"    # Multiple specialized agents


class AgentStructure(Enum):
    """Multi-agent structure type (only used when mode=MULTI)."""
    SEQUENTIAL = "sequential"      # Planner → Executor → Verifier
    CONCURRENT = "concurrent"      # Splitter → Workers (parallel) → Aggregator
    DEBATE = "debate"              # Proponent vs Opponent → Judge → Executor
    GROUP_CHAT = "group_chat"      # Manager selects next speaker from pool


@dataclass
class BenchmarkAgentConfig:
    """
    Configuration for benchmark agent execution.
    
    Attributes:
        mode: Agent execution mode (single or multi)
        provider: LLM provider name (openai, ollama, anthropic)
        model: Model name for the provider
        structure: Multi-agent structure (only used when mode=MULTI)
        api_key: API key for OpenAI/Anthropic (optional, uses env var if not set)
        host: Server host URL for Ollama (optional, defaults to localhost)
    """
    mode: AgentMode = AgentMode.SINGLE
    provider: str = "openai"
    model: str = "gpt-4o"
    structure: AgentStructure = AgentStructure.SEQUENTIAL
    api_key: Optional[str] = None
    host: Optional[str] = None
    context_length: Optional[int] = None

    @classmethod
    def from_dict(cls, data: dict) -> "BenchmarkAgentConfig":
        """
        Create config from dictionary.
        
        Handles string-to-enum conversion for mode and structure.
        
        Args:
            data: Dictionary with config values
            
        Returns:
            BenchmarkAgentConfig instance
        """
        mode = data.get("mode", "single")
        if isinstance(mode, str):
            mode = AgentMode(mode)
        
        structure = data.get("structure", "sequential")
        if isinstance(structure, str):
            structure = AgentStructure(structure)
        
        return cls(
            mode=mode,
            provider=data.get("provider", "openai"),
            model=data.get("model", "gpt-4o"),
            structure=structure,
            api_key=data.get("api_key"),
            host=data.get("host"),
            context_length=data.get("context_length"),
        )

    def to_dict(self) -> dict:
        """Convert config to dictionary."""
        return {
            "mode": self.mode.value,
            "provider": self.provider,
            "model": self.model,
            "structure": self.structure.value,
            "api_key": self.api_key,
            "host": self.host,
            "context_length": self.context_length,
        }
