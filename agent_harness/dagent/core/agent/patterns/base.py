"""
Base class for Multi-Agent System design patterns.

All patterns inherit from BasePattern and implement the
register_agents() and execute() methods.
"""

import json
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import logging

from autogen_core import SingleThreadedAgentRuntime
from autogen_core.models import (
    ChatCompletionClient,
    LLMMessage,
    AssistantMessage,
)

from dagent.core.agent.conversation.manager import Conversation

logger = logging.getLogger(__name__)


class BasePattern(ABC):
    """
    Abstract base class for all multi-agent design patterns.
    
    Patterns define how agents are orchestrated to solve tasks.
    Each pattern registers its required agents and provides an
    execute() method that runs the pattern logic.
    
    Subclasses must implement:
        - register_agents(): Set up agents in the runtime
        - execute(): Run the pattern on a task
        - entry_topic: The topic to publish initial messages to
    """
    
    def __init__(
        self,
        runtime: SingleThreadedAgentRuntime,
        config: Any,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the pattern.
        
        Args:
            runtime: AutoGen Core runtime for agent messaging
            config: Pattern-specific configuration
            logger: Optional logger instance
        """
        self._runtime = runtime
        self._config = config
        self._logger = logger or logging.getLogger(__name__)
        self._registered = False

        # Shared token tracking
        self._total_prompt_tokens: int = 0
        self._total_completion_tokens: int = 0
        self._total_tokens: int = 0

    def _parse_json_response(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Parse JSON from LLM response text robustly.
        Handles <think> blocks, markdown code blocks, and brace balancing.
        """
        # Remove <think>...</think> blocks (DeepSeek R1 style)
        clean_text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()

        # Try direct JSON parse on cleaned text
        try:
            return json.loads(clean_text)
        except json.JSONDecodeError:
            pass

        # Try to find ```json code blocks and extract the first one
        match = re.search(r"```json\s*(.*?)\s*```", clean_text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Try to extract the first complete JSON object using brace balancing
        start = clean_text.find("{")
        if start >= 0:
            depth = 0
            in_string = False
            escape_next = False
            for i, char in enumerate(clean_text[start:], start):
                if escape_next:
                    escape_next = False
                    continue
                if char == '\\' and in_string:
                    escape_next = True
                    continue
                if char == '"' and not escape_next:
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if char == '{':
                    depth += 1
                elif char == '}':
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(clean_text[start:i+1])
                        except json.JSONDecodeError:
                            break
        return None

    async def _get_llm_response(
        self,
        model_client: ChatCompletionClient,
        messages: List[LLMMessage],
        max_retries: int = 3,
        json_output: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        Get and parse LLM response with retries.
        """
        for attempt in range(max_retries):
            try:
                if json_output:
                    result = await model_client.create(messages, json_output=True)
                else:
                    result = await model_client.create(messages)

                # Track token usage
                if hasattr(result, 'usage') and result.usage:
                    prompt = getattr(result.usage, 'prompt_tokens', 0)
                    completion = getattr(result.usage, 'completion_tokens', 0)
                    self._total_prompt_tokens += prompt
                    self._total_completion_tokens += completion
                    self._total_tokens += prompt + completion

                content = result.content

                if isinstance(content, str):
                    text = content
                elif isinstance(content, list) and len(content) > 0:
                    text = content[0].text if hasattr(content[0], 'text') else str(content[0])
                else:
                    text = str(content)

                parsed = self._parse_json_response(text)
                if parsed:
                    return parsed
                else:
                    # Only warn on final attempt to reduce log noise
                    if attempt == max_retries - 1:
                        self._logger.warning(f"Failed to parse JSON after {max_retries} attempts")
                        preview = text[:300] if len(text) > 300 else text
                        self._logger.debug(f"Response preview: {preview}")
                    else:
                        self._logger.debug(f"Attempt {attempt + 1}: Failed to parse JSON, retrying...")

            except Exception as e:
                self._logger.warning(f"LLM response attempt {attempt + 1} failed: {e}")

        return None
    
    async def setup(self) -> None:
        """
        Set up the pattern by registering agents.
        
        Call this before execute() to ensure agents are registered.
        """
        if not self._registered:
            await self.register_agents()
            self._registered = True
    
    @abstractmethod
    async def register_agents(self) -> None:
        """
        Register all agents required by this pattern.
        
        This is called once during setup to add agents to the runtime.
        """
        ...
    
    @abstractmethod
    async def execute(
        self,
        task: Dict[str, Any],
        conversation: Optional[Conversation] = None,
    ) -> Dict[str, Any]:
        """
        Execute the pattern on a given task.
        
        Args:
            task: Task definition dictionary
            conversation: Optional conversation context for history
            
        Returns:
            Result dictionary with success status and details
        """
        ...
    
    @property
    @abstractmethod
    def entry_topic(self) -> str:
        """
        The topic to publish the initial task message to.
        
        Returns:
            Topic type string for the pattern's entry point
        """
        ...
    
    @property
    def is_registered(self) -> bool:
        """Whether agents have been registered."""
        return self._registered
