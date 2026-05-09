"""
Anthropic model provider implementation.
"""

import os
from typing import Optional

from autogen_ext.models.anthropic import AnthropicChatCompletionClient
from autogen_core.models import ChatCompletionClient

from dagent.core.providers.base import ModelProvider


class AnthropicProvider(ModelProvider):
    """
    Anthropic model provider.
    
    Supports Claude 3 models (Opus, Sonnet, Haiku).
    """

    def __init__(
        self,
        model: str = "claude-3-sonnet-20240229",
        api_key: Optional[str] = None,
    ):
        """
        Initialize Anthropic provider.
        
        Args:
            model: Anthropic model name (default: claude-3-sonnet-20240229)
            api_key: Anthropic API key. If not provided, uses ANTHROPIC_API_KEY env var.
        """
        self._model = model
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        
        if not self._api_key:
            raise ValueError(
                "Anthropic API key not provided. Set ANTHROPIC_API_KEY env var or pass api_key."
            )

    @property
    def provider_name(self) -> str:
        return "anthropic"

    @property
    def model_name(self) -> str:
        return self._model

    def create_client(self) -> ChatCompletionClient:
        """Create Anthropic chat completion client."""
        return AnthropicChatCompletionClient(
            model=self._model,
            api_key=self._api_key,
        )
