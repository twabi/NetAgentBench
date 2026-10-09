"""
Factory for creating model providers.
"""

from typing import Optional

from dagent.core.providers.base import ModelProvider
from dagent.core.providers.openai_provider import OpenAIProvider
from dagent.core.providers.ollama_provider import OllamaProvider
from dagent.core.providers.anthropic_provider import AnthropicProvider
from dagent.core.providers.gemini_provider import GeminiProvider
from dagent.core.providers.openrouter_provider import OpenRouterProvider


class ModelProviderFactory:
    """
    Factory for creating model providers based on provider name.
    """

    SUPPORTED_PROVIDERS = ["openai", "ollama", "anthropic", "gemini", "openrouter"]

    @staticmethod
    def create(
        provider: str,
        model: str,
        api_key: Optional[str] = None,
        host: Optional[str] = None,
        context_length: Optional[int] = None,
    ) -> ModelProvider:
        """
        Create a model provider instance.
        
        Args:
            provider: Provider name ('openai', 'ollama', 'anthropic', 'gemini')
            model: Model name for the provider
            api_key: API key (for OpenAI, Anthropic, Gemini)
            host: Server host URL (for Ollama)
            
        Returns:
            ModelProvider: The appropriate provider instance
            
        Raises:
            ValueError: If provider is not supported
        """
        if provider == "openai":
            return OpenAIProvider(model=model, api_key=api_key)
        elif provider == "ollama":
            return OllamaProvider(model=model, host=host, context_length=context_length)
        elif provider == "anthropic":
            return AnthropicProvider(model=model, api_key=api_key)
        elif provider == "gemini":
            return GeminiProvider(model=model, api_key=api_key)
        elif provider == "openrouter":
            return OpenRouterProvider(model=model, api_key=api_key)
        else:
            raise ValueError(
                f"Unknown provider: {provider}. "
                f"Supported providers: {ModelProviderFactory.SUPPORTED_PROVIDERS}"
            )

