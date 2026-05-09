"""
Configuration for the Multi-Agent System.

Defines design patterns, conversation modes, and MAS configuration.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List


class DesignPattern(Enum):
    """Multi-agent design patterns supported by the MAS."""
    SINGLE = "single"              # One agent, ReAct loop
    SEQUENTIAL = "sequential"      # Planner → Executor → Verifier
    CONCURRENT = "concurrent"      # Fan-out, then aggregate
    DEBATE = "debate"              # Two+ agents argue back and forth
    GROUP_CHAT = "group_chat"      # Manager selects next speaker


class ConversationMode(Enum):
    """Conversation context handling for benchmark runs."""
    MULTI_TURN = "multi_turn"      # Same conversation ID, persistent history
    SINGLE_TURN = "single_turn"    # Fresh conversation per task, no history


@dataclass
class MASConfig:
    """
    Configuration for Multi-Agent System.
    
    Attributes:
        pattern: Design pattern to use for agent orchestration
        conversation_mode: How to handle conversation context between tasks
        provider: LLM provider name (openai, anthropic, ollama, gemini)
        model: Model identifier
        max_turns: Maximum turns for ReAct loop
        max_debate_rounds: For DEBATE pattern, max back-and-forth rounds
        participant_roles: Role definitions for multi-agent patterns
    """
    pattern: DesignPattern = DesignPattern.SINGLE
    conversation_mode: ConversationMode = ConversationMode.SINGLE_TURN
    
    # Provider config
    provider: str = "openai"
    model: str = "gpt-4o"
    api_key: Optional[str] = None
    host: Optional[str] = None  # For Ollama
    
    # Pattern-specific options
    max_turns: int = 50
    max_debate_rounds: int = 5  # For DEBATE pattern
    context_length: Optional[int] = None
    
    # Participant definitions for multi-agent patterns
    participant_roles: List[str] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: dict) -> "MASConfig":
        """Create config from dictionary, handling enum conversions."""
        if "pattern" in data and isinstance(data["pattern"], str):
            data["pattern"] = DesignPattern(data["pattern"])
        if "conversation_mode" in data and isinstance(data["conversation_mode"], str):
            data["conversation_mode"] = ConversationMode(data["conversation_mode"])
        return cls(**data)
