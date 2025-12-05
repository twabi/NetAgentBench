"""
Unit tests for OllamaProvider.
"""
import pytest
from unittest.mock import MagicMock, patch
from benchmark.llm.providers import OllamaProvider
from benchmark.models.llm_config import LLMConfig
import httpx

class TestOllamaProvider:
    """Test OllamaProvider implementation."""
    
    def test_ollama_provider_init(self):
        """Test initialization of Ollama provider."""
        config = LLMConfig(
            provider="ollama",
            model="llama2",
            base_url="http://custom-host:11434"
        )
        provider = OllamaProvider(config)
        
        assert provider.base_url == "http://custom-host:11434"
        assert provider.model == "llama2"
        assert provider.httpx is not None

    def test_ollama_generate_response(self):
        """Test generating response with Ollama."""
        config = LLMConfig(provider="ollama", model="llama2")
        provider = OllamaProvider(config)
        
        # Mock httpx on the provider instance
        mock_httpx = MagicMock()
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        # Mocking the response for /api/chat
        mock_response.json.return_value = {
            "message": {"content": "Ollama response"}
        }
        
        mock_client.post.return_value = mock_response
        mock_client.__enter__.return_value = mock_client
        mock_httpx.Client.return_value = mock_client
        
        # Replace the real httpx with our mock
        provider.httpx = mock_httpx
        
        response = provider.generate_response("test prompt", system_prompt="test system")
        
        assert response == "Ollama response"
        
        # Verify API call arguments for /api/chat
        call_args = mock_client.post.call_args
        url = call_args[0][0]
        json_body = call_args[1]["json"]
        
        assert url.endswith("/api/chat")
        assert json_body["model"] == "llama2"
        assert json_body["messages"][0]["role"] == "system"
        assert json_body["messages"][0]["content"] == "test system"
        assert json_body["messages"][1]["role"] == "user"
        assert json_body["messages"][1]["content"] == "test prompt"
        assert json_body["stream"] is False

    def test_ollama_generate_response_default_url(self):
        """Test generating response with default URL."""
        config = LLMConfig(provider="ollama", model="llama2")
        provider = OllamaProvider(config)
        
        # Mock httpx
        mock_httpx = MagicMock()
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"message": {"content": "Response"}}
        
        mock_client.post.return_value = mock_response
        mock_client.__enter__.return_value = mock_client
        mock_httpx.Client.return_value = mock_client
        
        provider.httpx = mock_httpx
        
        provider.generate_response("test")
        
        call_args = mock_client.post.call_args
        url = call_args[0][0]
        assert url.startswith("http://localhost:11434")

    def test_ollama_get_model_info(self):
        """Test getting model info."""
        config = LLMConfig(provider="ollama", model="llama2")
        provider = OllamaProvider(config)
        
        info = provider.get_model_info()
        
        assert info["provider"] == "ollama"
        assert info["model"] == "llama2"
        assert info["base_url"] == "http://localhost:11434"
