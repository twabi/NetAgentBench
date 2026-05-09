"""
Custom Ollama Chat Completion Client using native ollama library.

This is a wrapper around the native ollama Python library that implements
autogen's ChatCompletionClient interface. It properly supports Ollama's
structured output feature with JSON schemas.
"""

import asyncio
from typing import Any, AsyncGenerator, Dict, List, Mapping, Optional, Sequence, Union
from ollama import Client as OllamaClient

from autogen_core.models import (
    ChatCompletionClient,
    CreateResult,
    FinishReasons,
    LLMMessage,
    ModelInfo,
    ModelFamily,
    ModelCapabilities,
    RequestUsage,
)
from autogen_core.tools import Tool, ToolSchema
from autogen_core import CancellationToken
from pydantic import BaseModel


# Default JSON schema for agent responses
DEFAULT_AGENT_SCHEMA = {
    "type": "object",
    "properties": {
        "thought": {
            "type": "string",
            "description": "Brief reasoning about what to do next"
        },
        "action": {
            "type": "string",
            "description": "The tool/action to execute"
        },
        "action_input": {
            "type": "object",
            "description": "Parameters for the action"
        }
    },
    "required": ["thought", "action", "action_input"]
}


class CustomOllamaChatCompletionClient(ChatCompletionClient):
    """
    Custom Ollama client that uses the native ollama library.
    
    This client properly supports Ollama's structured output feature,
    which is more reliable than the simple format='json' mode.
    """
    
    def __init__(
        self,
        model: str,
        host: str = "http://localhost:11434",
        json_schema: Optional[Dict[str, Any]] = None,
        model_info: Optional[ModelInfo] = None,
        context_length: Optional[int] = None,
        **kwargs
    ):
        """
        Initialize the Ollama client.
        
        Args:
            model: Ollama model name
            host: Ollama server URL
            json_schema: JSON schema for structured output (uses default agent schema if None)
            model_info: Model information for autogen compatibility
            context_length: Context window size (e.g., 120000)
            **kwargs: Additional options to pass to Ollama
        """
        super().__init__()
        self._model = model
        self._host = host
        self._json_schema = json_schema or DEFAULT_AGENT_SCHEMA
        self._context_length = context_length or 120000
        self._client = OllamaClient(host=host)
        self._extra_options = kwargs
        
        # Model info for autogen compatibility
        self._model_info = model_info or ModelInfo(
            vision=False,
            function_calling=True,
            json_output=True,
            family=ModelFamily.UNKNOWN,
        )
        
        # Usage tracking
        self._total_prompt_tokens = 0
        self._total_completion_tokens = 0
        self._total_tokens = 0
        self._actual_prompt_tokens = 0
        self._actual_completion_tokens = 0
        self._actual_tokens = 0
    
    def _convert_messages(self, messages: Sequence[LLMMessage]) -> List[Dict[str, str]]:
        """Convert autogen messages to Ollama format."""
        ollama_messages = []
        for msg in messages:
            # Extract role and content
            if hasattr(msg, 'role'):
                role = msg.role
            elif hasattr(msg, 'source'):
                role = msg.source if msg.source != 'system' else 'system'
            else:
                role = 'user'
            
            content = msg.content if hasattr(msg, 'content') else str(msg)
            
            ollama_messages.append({
                "role": role,
                "content": content
            })
        
        return ollama_messages
    
    async def create(
        self,
        messages: Sequence[LLMMessage],
        *,
        tools: Sequence[Tool | ToolSchema] = [],
        json_output: Optional[bool | type[BaseModel]] = None,
        extra_create_args: Mapping[str, Any] = {},
        cancellation_token: Optional[CancellationToken] = None,
    ) -> CreateResult:
        """Create a completion using Ollama."""
        # Convert messages to Ollama format
        ollama_messages = self._convert_messages(messages)
        
        # Prepare options
        options = {
            "temperature": 0,
            "num_ctx": self._context_length,
            **self._extra_options,
            **extra_create_args
        }
        
        # Determine format parameter
        format_param = None
        if json_output is not None:
            if isinstance(json_output, type) and issubclass(json_output, BaseModel):
                # Pydantic model - use its schema
                format_param = json_output.model_json_schema()
            elif json_output is True:
                # Use our default JSON schema for agent responses
                format_param = self._json_schema
        else:
            # Default: always use JSON schema for consistent output
            format_param = self._json_schema
        
        # Call Ollama (run in thread pool to avoid blocking event loop)
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"Calling Ollama with options: {options}")
        
        response = await asyncio.to_thread(
            self._client.chat,
            model=self._model,
            messages=ollama_messages,
            format=format_param,
            options=options
        )
        
        # Extract response data
        message = response.get('message', {})
        content = message.get('content', '')
        
        # Track usage if available
        prompt_tokens = response.get('prompt_eval_count', 0)
        completion_tokens = response.get('eval_count', 0)
        total_tokens = prompt_tokens + completion_tokens
        
        self._actual_prompt_tokens = prompt_tokens
        self._actual_completion_tokens = completion_tokens
        self._actual_tokens = total_tokens
        
        self._total_prompt_tokens += prompt_tokens
        self._total_completion_tokens += completion_tokens
        self._total_tokens += total_tokens
        
        # Create usage object
        usage = RequestUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens
        )
        
        # Determine finish reason
        finish_reason = "stop"  # Use string value instead of enum
        if response.get('done', False):
            finish_reason = "stop"
        
        # Create result
        return CreateResult(
            finish_reason=finish_reason,
            content=content,  # Just string content
            usage=usage,
            cached=False
        )
    
    async def create_stream(
        self,
        messages: Sequence[LLMMessage],
        *,
        tools: Sequence[Tool | ToolSchema] = [],
        json_output: Optional[bool | type[BaseModel]] = None,
        extra_create_args: Mapping[str, Any] = {},
        cancellation_token: Optional[CancellationToken] = None,
    ) -> AsyncGenerator[Union[str, CreateResult], None]:
        """Create a streaming completion (not implemented yet)."""
        # For now, just use non-streaming and yield the result
        result = await self.create(
            messages,
            tools=tools,
            json_output=json_output,
            extra_create_args=extra_create_args,
            cancellation_token=cancellation_token
        )
        yield result.content
        yield result
    
    async def close(self) -> None:
        """Close the client."""
        # Native ollama client doesn't need explicit closing
        pass
    
    def actual_usage(self) -> RequestUsage:
        """Get current request usage."""
        return RequestUsage(
            prompt_tokens=self._actual_prompt_tokens,
            completion_tokens=self._actual_completion_tokens
        )
    
    def total_usage(self) -> RequestUsage:
        """Get total usage across all requests."""
        return RequestUsage(
            prompt_tokens=self._total_prompt_tokens,
            completion_tokens=self._total_completion_tokens
        )
    
    def count_tokens(self, messages: Sequence[LLMMessage], *, tools: Sequence[Tool | ToolSchema] = []) -> int:
        """Count tokens (approximate)."""
        # Simple approximation: ~4 chars per token
        total_chars = sum(len(str(msg.content)) for msg in messages if hasattr(msg, 'content'))
        return total_chars // 4
    
    def remaining_tokens(self, messages: Sequence[LLMMessage], *, tools: Sequence[Tool | ToolSchema] = []) -> int:
        """Get remaining tokens (approximate)."""
        used = self.count_tokens(messages, tools=tools)
        return self._context_length - used
    
    @property
    def capabilities(self) -> ModelCapabilities:
        """Get model capabilities (deprecated)."""
        return self._model_info
    
    @property
    def model_info(self) -> ModelInfo:
        """Get model information."""
        return self._model_info
