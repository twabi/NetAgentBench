"""
OpenAI model provider implementation.
"""

import os
from typing import Optional

from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_core.models import ChatCompletionClient, ModelInfo

from dagent.core.providers.base import ModelProvider


# Models that autogen-ext recognizes natively (no model_info needed)
KNOWN_OPENAI_MODELS = {
    "gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4", "gpt-4-1106-preview",
    "gpt-3.5-turbo", "gpt-3.5-turbo-16k", "gpt-4-32k",
    "o1-preview", "o1-mini", "o3-mini",
}


class OpenAIProvider(ModelProvider):
    """
    OpenAI model provider.
    
    Supports GPT-4o, GPT-4o-mini, GPT-5, and other OpenAI chat models.
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: Optional[str] = None,
    ):
        """
        Initialize OpenAI provider.
        
        Args:
            model: OpenAI model name (default: gpt-4o)
            api_key: OpenAI API key. If not provided, uses OPENAI_API_KEY env var.
        """
        self._model = model
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        
        if not self._api_key:
            raise ValueError(
                "OpenAI API key not provided. Set OPENAI_API_KEY env var or pass api_key."
            )

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self._model

    def create_client(self) -> ChatCompletionClient:
        """Create OpenAI chat completion client."""
        # For newer models not in autogen-ext's known list, provide model_info
        if self._model not in KNOWN_OPENAI_MODELS:
            model_info = ModelInfo(
                vision=True,
                function_calling=True,
                json_output=True,
                structured_output=True,
                family="gpt",
            )
            return OpenAIChatCompletionClient(
                model=self._model,
                api_key=self._api_key,
                model_info=model_info,
            )
        
        return OpenAIChatCompletionClient(
            model=self._model,
            api_key=self._api_key,
        )

