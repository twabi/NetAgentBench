"""Unit tests for the OpenRouter provider."""

import os
from unittest.mock import patch

import pytest

from dagent.core.providers.factory import ModelProviderFactory
from dagent.core.providers.openrouter_provider import OPENROUTER_BASE_URL, OpenRouterProvider


def test_factory_returns_openrouter_provider():
    provider = ModelProviderFactory.create(
        "openrouter", model="openai/gpt-6-luna", api_key="test-key"
    )
    assert isinstance(provider, OpenRouterProvider)
    assert provider.provider_name == "openrouter"
    assert provider.model_name == "openai/gpt-6-luna"


def test_missing_key_raises():
    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("OPEN_ROUTER_API_KEY", None)
        with pytest.raises(ValueError, match="OPEN_ROUTER_API_KEY"):
            OpenRouterProvider(model="qwen/qwen3.8-flash")


def test_create_client_keeps_slug_and_openrouter_base_url():
    provider = OpenRouterProvider(model="z-ai/glm-5.3", api_key="test-key")
    with patch(
        "dagent.core.providers.openrouter_provider.OpenAIChatCompletionClient"
    ) as client_cls:
        provider.create_client()
    kwargs = client_cls.call_args.kwargs
    assert kwargs["model"] == "z-ai/glm-5.3"
    assert kwargs["base_url"] == OPENROUTER_BASE_URL
    assert kwargs["api_key"] == "test-key"
