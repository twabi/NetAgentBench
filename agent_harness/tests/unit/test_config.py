"""
Unit tests for BenchmarkAgentConfig and related enums.
"""

import pytest

from dagent.benchmark.config import AgentMode, AgentStructure, BenchmarkAgentConfig


class TestAgentMode:
    """Tests for AgentMode enum."""

    def test_single_mode_value(self):
        """Test SINGLE mode has correct value."""
        assert AgentMode.SINGLE.value == "single"

    def test_multi_mode_value(self):
        """Test MULTI mode has correct value."""
        assert AgentMode.MULTI.value == "multi"

    def test_mode_from_string(self):
        """Test creating mode from string value."""
        assert AgentMode("single") == AgentMode.SINGLE
        assert AgentMode("multi") == AgentMode.MULTI

    def test_invalid_mode_raises_error(self):
        """Test invalid mode string raises ValueError."""
        with pytest.raises(ValueError):
            AgentMode("invalid")


class TestAgentStructure:
    """Tests for AgentStructure enum."""

    def test_sequential_structure_value(self):
        """Test SEQUENTIAL structure has correct value."""
        assert AgentStructure.SEQUENTIAL.value == "sequential"

    def test_structure_from_string(self):
        """Test creating structure from string value."""
        assert AgentStructure("sequential") == AgentStructure.SEQUENTIAL
        assert AgentStructure("group_chat") == AgentStructure.GROUP_CHAT

    def test_invalid_structure_raises_error(self):
        """Test invalid structure string raises ValueError."""
        with pytest.raises(ValueError):
            AgentStructure("invalid")

    def test_adaptive_not_in_enum(self):
        """Adaptive is omitted from this harness snapshot."""
        with pytest.raises(ValueError):
            AgentStructure("adaptive")


class TestBenchmarkAgentConfig:
    """Tests for BenchmarkAgentConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = BenchmarkAgentConfig()

        assert config.mode == AgentMode.SINGLE
        assert config.provider == "openai"
        assert config.model == "gpt-4o"
        assert config.structure == AgentStructure.SEQUENTIAL
        assert config.api_key is None
        assert config.host is None

    def test_custom_values(self):
        """Test custom configuration values."""
        config = BenchmarkAgentConfig(
            mode=AgentMode.MULTI,
            provider="ollama",
            model="qwen2.5:7b",
            structure=AgentStructure.SEQUENTIAL,
            host="http://localhost:11434",
        )

        assert config.mode == AgentMode.MULTI
        assert config.provider == "ollama"
        assert config.model == "qwen2.5:7b"
        assert config.host == "http://localhost:11434"

    def test_from_dict_with_defaults(self):
        """Test creating config from empty dict uses defaults."""
        config = BenchmarkAgentConfig.from_dict({})

        assert config.mode == AgentMode.SINGLE
        assert config.provider == "openai"
        assert config.model == "gpt-4o"

    def test_from_dict_with_string_mode(self):
        """Test creating config from dict with string mode."""
        config = BenchmarkAgentConfig.from_dict(
            {
                "mode": "multi",
                "provider": "anthropic",
                "model": "claude-3-sonnet-20240229",
            }
        )

        assert config.mode == AgentMode.MULTI
        assert config.provider == "anthropic"

    def test_from_dict_with_string_structure(self):
        """Test creating config from dict with string structure."""
        config = BenchmarkAgentConfig.from_dict(
            {
                "structure": "sequential",
            }
        )

        assert config.structure == AgentStructure.SEQUENTIAL

    def test_from_dict_with_all_fields(self):
        """Test creating config from dict with all fields."""
        config = BenchmarkAgentConfig.from_dict(
            {
                "mode": "single",
                "provider": "ollama",
                "model": "llama3:8b",
                "structure": "sequential",
                "host": "http://remote:11434",
            }
        )

        assert config.mode == AgentMode.SINGLE
        assert config.provider == "ollama"
        assert config.model == "llama3:8b"
        assert config.host == "http://remote:11434"

    def test_to_dict(self):
        """Test converting config to dictionary."""
        config = BenchmarkAgentConfig(
            mode=AgentMode.MULTI,
            provider="anthropic",
            model="claude-3-opus-20240229",
            structure=AgentStructure.SEQUENTIAL,
            api_key="test-key",
        )

        result = config.to_dict()

        assert result["mode"] == "multi"
        assert result["provider"] == "anthropic"
        assert result["model"] == "claude-3-opus-20240229"
        assert result["structure"] == "sequential"
        assert result["api_key"] == "test-key"

    def test_to_dict_from_dict_roundtrip(self):
        """Test that to_dict and from_dict are inverses."""
        original = BenchmarkAgentConfig(
            mode=AgentMode.MULTI,
            provider="ollama",
            model="qwen2.5:32b",
            structure=AgentStructure.GROUP_CHAT,
            host="http://localhost:11434",
        )

        data = original.to_dict()
        restored = BenchmarkAgentConfig.from_dict(data)

        assert restored.mode == original.mode
        assert restored.provider == original.provider
        assert restored.model == original.model
        assert restored.structure == original.structure
        assert restored.host == original.host

