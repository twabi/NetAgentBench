"""
Unit tests for LLM providers.

Tests LLMProvider abstraction, MockLLMProvider, and configuration.
"""
import pytest
import time
from benchmark.llm.providers import LLMProvider, MockLLMProvider
from benchmark.models.llm_config import LLMConfig, LLMBenchmarkConfig


class TestLLMConfig:
    """Test LLMConfig model."""

    def test_create_llm_config(self):
        """Test creating a basic LLM config."""
        config = LLMConfig(
            provider="openai",
            model="gpt-4",
            api_key="sk-test",
        )

        assert config.provider == "openai"
        assert config.model == "gpt-4"
        assert config.api_key == "sk-test"
        assert config.max_tokens == 2000  # default
        assert config.temperature == 0.1  # default

    def test_llm_config_with_custom_settings(self):
        """Test LLM config with custom settings."""
        config = LLMConfig(
            provider="anthropic",
            model="claude-3-opus",
            api_key="sk-ant-test",
            max_tokens=4000,
            temperature=0.5,
            timeout_seconds=600,
            retry_attempts=5,
        )

        assert config.max_tokens == 4000
        assert config.temperature == 0.5
        assert config.timeout_seconds == 600
        assert config.retry_attempts == 5

    def test_llm_config_ollama(self):
        """Test LLM config for Ollama (local provider)."""
        config = LLMConfig(
            provider="ollama",
            model="llama2",
            base_url="http://localhost:11434",
        )

        assert config.provider == "ollama"
        assert config.base_url == "http://localhost:11434"
        assert config.api_key is None  # No API key for local

    def test_llm_config_provider_config(self):
        """Test provider-specific configuration."""
        config = LLMConfig(
            provider="openai",
            model="gpt-4-turbo",
            api_key="test",
            provider_config={"organization": "org-123", "project": "proj-456"},
        )

        assert "organization" in config.provider_config
        assert config.provider_config["organization"] == "org-123"


class TestLLMBenchmarkConfig:
    """Test LLMBenchmarkConfig model."""

    def test_create_benchmark_config(self):
        """Test creating a benchmark config."""
        llm_config = LLMConfig(provider="openai", model="gpt-4", api_key="test")

        bench_config = LLMBenchmarkConfig(
            llm_config=llm_config, testee_id="gpt4_run_001"
        )

        assert bench_config.testee_id == "gpt4_run_001"
        assert bench_config.llm_config.model == "gpt-4"
        assert bench_config.task_timeout_minutes == 10  # default

    def test_benchmark_config_with_custom_settings(self):
        """Test benchmark config with custom settings."""
        llm_config = LLMConfig(provider="mock", model="mock-model")

        bench_config = LLMBenchmarkConfig(
            llm_config=llm_config,
            testee_id="test_run",
            max_tasks=50,
            task_timeout_minutes=15,
            enable_context_preservation=True,
            log_level="DEBUG",
        )

        assert bench_config.max_tasks == 50
        assert bench_config.task_timeout_minutes == 15
        assert bench_config.enable_context_preservation is True
        assert bench_config.log_level == "DEBUG"


class TestLLMProviderAbstraction:
    """Test LLMProvider abstract base class."""

    def test_llm_provider_is_abstract(self):
        """Test that LLMProvider cannot be instantiated directly."""
        config = LLMConfig(provider="mock", model="test")

        with pytest.raises(TypeError):
            LLMProvider(config)

    def test_llm_provider_requires_generate_response(self):
        """Test that subclasses must implement generate_response."""

        class IncompleteProvider(LLMProvider):
            def get_model_info(self):
                return {}

        config = LLMConfig(provider="mock", model="test")

        with pytest.raises(TypeError):
            IncompleteProvider(config)

    def test_llm_provider_requires_get_model_info(self):
        """Test that subclasses must implement get_model_info."""

        class IncompleteProvider(LLMProvider):
            def generate_response(self, prompt, **kwargs):
                return "response"

        config = LLMConfig(provider="mock", model="test")

        with pytest.raises(TypeError):
            IncompleteProvider(config)


class TestMockLLMProvider:
    """Test MockLLMProvider implementation."""

    def test_create_mock_provider(self):
        """Test creating a MockLLMProvider."""
        config = LLMConfig(provider="mock", model="mock-model")
        provider = MockLLMProvider(config)

        assert provider is not None
        assert provider.model == "mock-model"
        assert provider.call_count == 0

    def test_mock_provider_generate_response(self):
        """Test generating a response from mock provider."""
        config = LLMConfig(provider="mock", model="mock-model")
        provider = MockLLMProvider(config)

        response = provider.generate_response("test prompt")

        assert isinstance(response, str)
        assert len(response) > 0
        assert provider.call_count == 1
        assert provider.last_prompt == "test prompt"

    def test_mock_provider_with_custom_response(self):
        """Test mock provider with custom response."""
        config = LLMConfig(provider="mock", model="mock-model")
        custom_response = "This is a custom response"
        provider = MockLLMProvider(config, mock_response=custom_response)

        response = provider.generate_response("anything")

        assert response == custom_response
        assert provider.call_count == 1

    def test_mock_provider_multiple_calls(self):
        """Test that mock provider tracks multiple calls."""
        config = LLMConfig(provider="mock", model="mock-model")
        provider = MockLLMProvider(config)

        for i in range(5):
            provider.generate_response(f"prompt {i}")

        assert provider.call_count == 5
        assert provider.last_prompt == "prompt 4"

    def test_mock_provider_get_model_info(self):
        """Test getting model info from mock provider."""
        config = LLMConfig(provider="mock", model="mock-gpt")
        provider = MockLLMProvider(config)

        # Make some calls
        provider.generate_response("test")
        provider.generate_response("test2")

        info = provider.get_model_info()

        assert isinstance(info, dict)
        assert info["provider"] == "mock"
        assert info["model"] == "mock-gpt"
        assert info["call_count"] == 2

    def test_mock_provider_set_mock_response(self):
        """Test updating the mock response."""
        config = LLMConfig(provider="mock", model="mock-model")
        provider = MockLLMProvider(config)

        initial_response = provider.generate_response("test")

        provider.set_mock_response("New custom response")
        new_response = provider.generate_response("test")

        assert initial_response != new_response
        assert new_response == "New custom response"

    def test_mock_provider_reset(self):
        """Test resetting the mock provider."""
        config = LLMConfig(provider="mock", model="mock-model")
        provider = MockLLMProvider(config)

        provider.generate_response("test1")
        provider.generate_response("test2")
        assert provider.call_count == 2

        provider.reset()

        assert provider.call_count == 0
        assert provider.last_prompt is None

    def test_mock_provider_default_response_format(self):
        """Test that default mock response has valid JSON structure."""
        config = LLMConfig(provider="mock", model="mock-model")
        provider = MockLLMProvider(config)

        response = provider.generate_response("test")

        # Should contain JSON-like structure
        assert "{" in response
        assert "}" in response
        assert "approach" in response
        assert "commands" in response

    def test_mock_provider_inherits_config(self):
        """Test that mock provider inherits config properties."""
        config = LLMConfig(
            provider="mock",
            model="mock-model",
            max_tokens=4000,
            temperature=0.7,
            timeout_seconds=120,
        )
        provider = MockLLMProvider(config)

        assert provider.max_tokens == 4000
        assert provider.temperature == 0.7
        assert provider.timeout == 120

    def test_mock_provider_simulates_delay(self):
        """Test that mock provider simulates processing time."""
        config = LLMConfig(provider="mock", model="mock-model")
        provider = MockLLMProvider(config)

        start = time.time()
        provider.generate_response("test")
        elapsed = time.time() - start

        # Should have some small delay (0.01s minimum)
        assert elapsed >= 0.01

