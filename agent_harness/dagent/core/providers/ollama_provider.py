"""
Ollama model provider implementation.
"""

from typing import Optional

from autogen_core.models import ChatCompletionClient, ModelInfo, ModelFamily

from dagent.core.providers.base import ModelProvider
from dagent.core.providers.custom_ollama_client import CustomOllamaChatCompletionClient


class OllamaProvider(ModelProvider):
    """
    Ollama model provider.
    
    Supports local Ollama models like Qwen, Llama, Mistral, DeepSeek, etc.
    Uses native ollama library with JSON schema for structured output.
    """

    def __init__(
        self,
        model: str = "qwen2.5:7b",
        host: Optional[str] = None,
        context_length: Optional[int] = None,
    ):
        """
        Initialize Ollama provider.
        
        Args:
            model: Ollama model name (default: qwen2.5:7b)
            host: Ollama server URL (default: http://localhost:11434)
            context_length: Context window size (e.g., 120000)
        """
        self._model = model
        self._host = host or "http://localhost:11434"
        self._context_length = context_length

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def model_name(self) -> str:
        return self._model

    def create_client(self) -> ChatCompletionClient:
        """Create Ollama chat completion client with JSON schema support."""
        return CustomOllamaChatCompletionClient(
            model=self._model,
            host=self._host,
            context_length=self._context_length,
            model_info=ModelInfo(
                vision=False,
                function_calling=True,
                json_output=True,
                family=ModelFamily.UNKNOWN,
            ),
        )
