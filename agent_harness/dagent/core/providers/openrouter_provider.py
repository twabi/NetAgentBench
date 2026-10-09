"""
OpenRouter model provider.

OpenRouter exposes an OpenAI-compatible chat API. Model ids are passed through
unchanged (for example ``openai/gpt-6-luna``).
"""

import os
from typing import Optional

from autogen_core.models import ChatCompletionClient, ModelInfo
from autogen_ext.models.openai import OpenAIChatCompletionClient

from dagent.core.providers.base import ModelProvider

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterProvider(ModelProvider):
    """Chat completions against OpenRouter's OpenAI-compatible endpoint."""

    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
    ):
        self._model = model
        self._api_key = api_key or os.getenv("OPEN_ROUTER_API_KEY")
        if not self._api_key:
            raise ValueError(
                "OpenRouter API key not provided. Set OPEN_ROUTER_API_KEY env var or pass api_key."
            )

    @property
    def provider_name(self) -> str:
        return "openrouter"

    @property
    def model_name(self) -> str:
        return self._model

    def create_client(self) -> ChatCompletionClient:
        model_info = ModelInfo(
            vision=False,
            function_calling=True,
            json_output=True,
            structured_output=True,
            family="unknown",
        )
        return OpenAIChatCompletionClient(
            model=self._model,
            api_key=self._api_key,
            base_url=OPENROUTER_BASE_URL,
            model_info=model_info,
        )
