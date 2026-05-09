"""
Abstract base class for model providers.
"""

from abc import ABC, abstractmethod

from autogen_core.models import ChatCompletionClient


class ModelProvider(ABC):
    """
    Abstract base for all LLM providers.
    
    Each provider wraps a specific LLM service (OpenAI, Anthropic, Ollama)
    and returns an autogen-compatible ChatCompletionClient.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name (e.g., 'openai', 'ollama', 'anthropic')."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model name being used."""
        ...

    @abstractmethod
    def create_client(self) -> ChatCompletionClient:
        """
        Create and return the autogen-compatible model client.
        
        Returns:
            ChatCompletionClient: An autogen-compatible chat completion client.
        """
        ...
