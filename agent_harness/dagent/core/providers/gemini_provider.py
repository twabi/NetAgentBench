"""
Google Gemini model provider implementation.

Uses the google-generativeai SDK via autogen's OpenAI-compatible interface.
"""

import os
from typing import Optional

from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_core.models import ChatCompletionClient, ModelInfo

from dagent.core.providers.base import ModelProvider


class GeminiProvider(ModelProvider):
    """
    Google Gemini model provider.
    
    Supports Gemini 2.x and 3.x models via Google's Generative AI API
    with OpenAI-compatible endpoint.
    """

    # OpenAI-compatible base URL for Gemini
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

    def __init__(
        self,
        model: str = "gemini-2.0-flash",
        api_key: Optional[str] = None,
    ):
        """
        Initialize Gemini provider.
        
        Args:
            model: Gemini model name (default: gemini-2.0-flash)
            api_key: Google AI API key. If not provided, uses GEMINI_API_KEY 
                     or GOOGLE_API_KEY env var.
        """
        self._model = model
        self._api_key = (
            api_key 
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
        )
        
        if not self._api_key:
            raise ValueError(
                "Google API key not provided. Set GEMINI_API_KEY or GOOGLE_API_KEY "
                "env var or pass api_key."
            )

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model

    def create_client(self) -> ChatCompletionClient:
        """
        Create Gemini chat completion client via OpenAI-compatible API.
        
        Uses Google's OpenAI-compatible endpoint for seamless integration
        with autogen's existing OpenAI client infrastructure.
        """
        # Model info required for non-OpenAI models in autogen-ext
        # All Gemini models support vision and function calling
        model_info = ModelInfo(
            vision=True,
            function_calling=True,
            json_output=True,
            family="gemini",
        )
        
        return OpenAIChatCompletionClient(
            model=self._model,
            api_key=self._api_key,
            base_url=self.BASE_URL,
            model_info=model_info,
        )

