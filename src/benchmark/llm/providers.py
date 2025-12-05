"""
LLM provider abstraction layer.

Provides a unified interface for different LLM providers (OpenAI, Anthropic, Ollama, etc.).
"""
import logging
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from benchmark.models.llm_config import LLMConfig

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    
    All LLM providers (OpenAI, Anthropic, Ollama) must implement this interface.
    """

    def __init__(self, config: LLMConfig):
        """
        Initialize the LLM provider.
        
        Args:
            config: LLMConfig with provider settings
        """
        self.config = config
        self.model = config.model
        self.max_tokens = config.max_tokens
        self.temperature = config.temperature
        self.timeout = config.timeout_seconds
        self.retry_attempts = config.retry_attempts

    @abstractmethod
    def generate_response(
        self, prompt: str, **kwargs
    ) -> str:
        """
        Generate a response from the LLM.
        
        Args:
            prompt: Input prompt for the LLM
            **kwargs: Additional provider-specific parameters
        
        Returns:
            Generated text response
        
        Raises:
            Exception: If generation fails after retries
        """
        pass

    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the model.
        
        Returns:
            Dictionary with model information (name, version, etc.)
        """
        pass

    def _retry_with_backoff(self, func, *args, **kwargs):
        """
        Retry a function with exponential backoff.
        
        Args:
            func: Function to retry
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func
        
        Returns:
            Result of func
        
        Raises:
            Exception: If all retry attempts fail
        """
        last_exception = None
        
        for attempt in range(self.retry_attempts):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < self.retry_attempts - 1:
                    wait_time = (2 ** attempt) * self.config.rate_limit_delay
                    logger.warning(
                        f"Attempt {attempt + 1}/{self.retry_attempts} failed: {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(
                        f"All {self.retry_attempts} attempts failed: {last_exception}"
                    )
        
        raise last_exception


class MockLLMProvider(LLMProvider):
    """
    Mock LLM provider for testing.
    
    Returns pre-configured responses without making actual API calls.
    """

    def __init__(self, config: LLMConfig, mock_response: Optional[str] = None):
        """
        Initialize mock provider.
        
        Args:
            config: LLMConfig (mostly ignored for mock)
            mock_response: Pre-configured response to return
        """
        super().__init__(config)
        self.mock_response = mock_response or self._default_mock_response()
        self.call_count = 0
        self.last_prompt = None

    def generate_response(self, prompt: str, **kwargs) -> str:
        """
        Return the mock response.
        
        Args:
            prompt: Input prompt (stored but not used)
            **kwargs: Ignored
        
        Returns:
            Mock response string
        """
        self.call_count += 1
        self.last_prompt = prompt
        
        logger.debug(f"MockLLMProvider called (count={self.call_count})")
        
        # Simulate some processing time
        time.sleep(0.01)
        
        return self.mock_response

    def get_model_info(self) -> Dict[str, Any]:
        """
        Return mock model information.
        
        Returns:
            Dictionary with mock model info
        """
        return {
            "provider": "mock",
            "model": self.model,
            "version": "1.0-mock",
            "description": "Mock LLM provider for testing",
            "call_count": self.call_count,
        }

    def _default_mock_response(self) -> str:
        """
        Generate a default mock response with valid JSON structure.
        
        Returns:
            JSON string with mock configuration
        """
        return '''```json
{
  "approach": {
    "description": "Mock configuration from LLM",
    "commands": [
      {
        "node": "R1",
        "commands": ["echo 'mock command'"]
      }
    ]
  }
}
```'''

    def set_mock_response(self, response: str):
        """
        Update the mock response.
        
        Args:
            response: New response to return
        """
        self.mock_response = response

    def reset(self):
        """Reset call count and last prompt."""
        self.call_count = 0
        self.last_prompt = None


class OpenAIProvider(LLMProvider):
    """
    OpenAI API provider (GPT-4, GPT-3.5, etc.).
    
    Supports all OpenAI chat models via the official API.
    """

    def __init__(self, config: LLMConfig):
        """
        Initialize OpenAI provider.
        
        Args:
            config: LLMConfig with OpenAI settings
        
        Raises:
            ValueError: If API key is not provided
        """
        super().__init__(config)
        
        if not config.api_key:
            raise ValueError("OpenAI API key is required")
        
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "openai package is required for OpenAIProvider. "
                "Install it with: pip install openai"
            )
        
        # Initialize OpenAI client
        self.client = OpenAI(
            api_key=config.api_key,
            timeout=config.timeout_seconds,
            **config.provider_config
        )

    def generate_response(self, prompt: str, **kwargs) -> str:
        """
        Generate a response using OpenAI API.
        
        Args:
            prompt: Input prompt
            **kwargs: Additional parameters (system_prompt, etc.)
        
        Returns:
            Generated text response
        
        Raises:
            Exception: If API call fails after retries
        """
        system_prompt = kwargs.get(
            "system_prompt",
            "You are a network configuration expert. Generate valid network configurations."
        )
        
        def _call_api():
            # Build params based on model capabilities
            params = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
            }
            
            # GPT-5 models only support temperature=1 (default)
            # o1 models don't support temperature at all
            if "gpt-5" not in self.model and "o1" not in self.model:
                params["temperature"] = self.temperature
            
            # Use max_completion_tokens for newer models, max_tokens for older ones
            if "gpt-4o" in self.model or "gpt-5" in self.model or "o1" in self.model:
                params["max_completion_tokens"] = self.max_tokens
            else:
                params["max_tokens"] = self.max_tokens
            
            response = self.client.chat.completions.create(**params)
            content = response.choices[0].message.content
            
            # Log if content is None or empty
            if not content:
                logger.warning(f"OpenAI returned empty content. Full response: {response}")
                logger.warning(f"Model: {self.model}, Params: {params.keys()}")
            
            return content
        
        return self._retry_with_backoff(_call_api)

    def get_model_info(self) -> Dict[str, Any]:
        """
        Get OpenAI model information.
        
        Returns:
            Dictionary with model info
        """
        return {
            "provider": "openai",
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }


class AnthropicProvider(LLMProvider):
    """
    Anthropic API provider (Claude models).
    
    Supports Claude 3 and other Anthropic models.
    """

    def __init__(self, config: LLMConfig):
        """
        Initialize Anthropic provider.
        
        Args:
            config: LLMConfig with Anthropic settings
        
        Raises:
            ValueError: If API key is not provided
        """
        super().__init__(config)
        
        if not config.api_key:
            raise ValueError("Anthropic API key is required")
        
        try:
            from anthropic import Anthropic
        except ImportError:
            raise ImportError(
                "anthropic package is required for AnthropicProvider. "
                "Install it with: pip install anthropic"
            )
        
        # Initialize Anthropic client
        self.client = Anthropic(
            api_key=config.api_key,
            timeout=config.timeout_seconds,
            **config.provider_config
        )

    def generate_response(self, prompt: str, **kwargs) -> str:
        """
        Generate a response using Anthropic API.
        
        Args:
            prompt: Input prompt
            **kwargs: Additional parameters (system_prompt, etc.)
        
        Returns:
            Generated text response
        
        Raises:
            Exception: If API call fails after retries
        """
        system_prompt = kwargs.get(
            "system_prompt",
            "You are a network configuration expert. Generate valid network configurations."
        )
        
        def _call_api():
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": prompt}
                ],
            )
            return response.content[0].text
        
        return self._retry_with_backoff(_call_api)

    def get_model_info(self) -> Dict[str, Any]:
        """
        Get Anthropic model information.
        
        Returns:
            Dictionary with model info
        """
        return {
            "provider": "anthropic",
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }


class GeminiProvider(LLMProvider):
    """
    Google Gemini API provider (Gemini Pro, Gemini 1.5 Pro, etc.).
    
    Supports all Gemini models via the Google Generative AI API.
    """

    def __init__(self, config: LLMConfig):
        """
        Initialize Gemini provider.
        
        Args:
            config: LLMConfig with Gemini settings
        
        Raises:
            ValueError: If API key is not provided
        """
        super().__init__(config)
        
        if not config.api_key:
            raise ValueError("Gemini API key is required")
        
        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError(
                "google-generativeai package is required for GeminiProvider. "
                "Install it with: pip install google-generativeai"
            )
        
        # Configure Gemini with API key
        genai.configure(api_key=config.api_key)
        
        # Initialize Gemini model
        # Increase max_output_tokens for complex network configurations
        # Gemini models need higher limits for JSON responses
        # Network configs can be large, so use generous limits
        if "pro" in self.model.lower():
            max_tokens = max(self.max_tokens, 32768)  # Pro models: up to 32K tokens
        elif "flash" in self.model.lower():
            max_tokens = max(self.max_tokens, 16384)  # Flash models: up to 16K tokens
        else:
            max_tokens = max(self.max_tokens, 8192)  # Default: 8K tokens
        
        logger.info(f"Gemini {self.model} configured with max_output_tokens={max_tokens}")
        
        generation_config = {
            "temperature": self.temperature,
            "max_output_tokens": max_tokens,
        }
        
        # Add provider-specific config if provided
        if config.provider_config:
            generation_config.update(config.provider_config)
        
        # Add models/ prefix if not already present
        model_name = self.model
        if not model_name.startswith("models/"):
            model_name = f"models/{model_name}"
        
        self.model_instance = genai.GenerativeModel(
            model_name=model_name,
            generation_config=generation_config
        )
        self.genai = genai

    def generate_response(self, prompt: str, **kwargs) -> str:
        """
        Generate a response using Gemini API.
        
        Args:
            prompt: Input prompt
            **kwargs: Additional parameters (system_prompt, etc.)
        
        Returns:
            Generated text response
        
        Raises:
            Exception: If API call fails after retries
        """
        system_prompt = kwargs.get(
            "system_prompt",
            "You are a network configuration expert. Generate valid network configurations."
        )
        
        # Combine system prompt with user prompt
        full_prompt = f"{system_prompt}\n\n{prompt}"
        
        def _call_api():
            # Set timeout using request_options (available in google-generativeai >= 0.5.0)
            # For older versions, timeout is handled by the httpx client internally
            try:
                # Try with request_options first (newer API)
                request_options = {"timeout": self.timeout}
                response = self.model_instance.generate_content(
                    full_prompt,
                    request_options=request_options
                )
            except (TypeError, ValueError) as e:
                # Fallback for older versions that don't support request_options
                # Error message typically contains "request_options" or "Unknown field"
                error_str = str(e)
                if "request_options" in error_str or "Unknown field" in error_str:
                    logger.warning(
                        f"request_options not supported in this google-generativeai version. "
                        f"Using default timeout. Consider upgrading to >= 0.5.0. Error: {error_str}"
                    )
                    response = self.model_instance.generate_content(full_prompt)
                else:
                    raise
            
            # Check if response was blocked
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                raise ValueError(
                    f"Gemini blocked the prompt: {response.prompt_feedback}"
                )
            
            # Extract text from response - prioritize parts over response.text
            # response.text can be truncated, but parts contain the full content
            text = None
            finish_reason = None
            
            # First, check candidates for the full response
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                
                # Check finish reason
                if hasattr(candidate, 'finish_reason'):
                    finish_reason = candidate.finish_reason
                    if finish_reason == 'MAX_TOKENS':
                        logger.warning(
                            "Gemini response was truncated due to MAX_TOKENS. "
                            f"Current max_output_tokens: {self.max_tokens}. "
                            "Consider increasing max_output_tokens."
                        )
                
                # Extract from content.parts (most reliable method)
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                    text_parts = []
                    for part in candidate.content.parts:
                        if hasattr(part, 'text') and part.text:
                            text_parts.append(part.text)
                    if text_parts:
                        text = ''.join(text_parts)
                        logger.debug(f"Extracted {len(text)} chars from candidate.content.parts")
            
            # Fallback to response.text if parts didn't work
            if not text:
                try:
                    if hasattr(response, 'text') and response.text:
                        text = response.text
                        logger.debug(f"Extracted {len(text)} chars from response.text")
                except Exception as e:
                    logger.debug(f"Could not use response.text: {e}")
            
            # Last resort: try response.parts directly
            if not text and hasattr(response, 'parts'):
                text_parts = []
                for part in response.parts:
                    if hasattr(part, 'text') and part.text:
                        text_parts.append(part.text)
                if text_parts:
                    text = ''.join(text_parts)
                    logger.debug(f"Extracted {len(text)} chars from response.parts")
            
            if not text:
                # Log full response structure for debugging
                logger.error(f"Gemini response structure: {dir(response)}")
                if hasattr(response, 'candidates') and response.candidates:
                    logger.error(f"Candidate structure: {dir(response.candidates[0])}")
                raise ValueError("Gemini returned empty response")
            
            # Log if response appears truncated
            if finish_reason == 'MAX_TOKENS':
                logger.warning(
                    f"Response may be truncated. Length: {len(text)} chars. "
                    f"Finish reason: {finish_reason}"
                )
            
            return text
        
        return self._retry_with_backoff(_call_api)

    def get_model_info(self) -> Dict[str, Any]:
        """
        Get Gemini model information.
        
        Returns:
            Dictionary with model info
        """
        return {
            "provider": "gemini",
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }


class OllamaProvider(LLMProvider):
    """
    Ollama provider for local LLM models.
    
    Supports running open-source models locally via Ollama.
    """

    def __init__(self, config: LLMConfig):
        """
        Initialize Ollama provider.
        
        Args:
            config: LLMConfig with Ollama settings
        """
        super().__init__(config)
        
        try:
            import httpx
        except ImportError:
            raise ImportError(
                "httpx package is required for OllamaProvider. "
                "Install it with: pip install httpx"
            )
        
        self.base_url = config.base_url or "http://localhost:11434"
        self.httpx = httpx

    def generate_response(self, prompt: str, **kwargs) -> str:
        """
        Generate a response using Ollama API.
        
        Args:
            prompt: Input prompt
            **kwargs: Additional parameters (system_prompt, etc.)
        
        Returns:
            Generated text response
        
        Raises:
            Exception: If API call fails after retries
        """
        system_prompt = kwargs.get(
            "system_prompt",
            "You are a network configuration expert. Generate valid network configurations."
        )
        
        def _call_api():
            with self.httpx.Client(timeout=self.timeout) as client:
                # Use /api/chat instead of /api/generate for better instruction following
                response = client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt}
                        ],
                        "stream": False,
                        "options": {
                            "temperature": self.temperature,
                            "num_predict": self.max_tokens,
                            "num_ctx": self.config.provider_config.get("num_ctx", 8192),
                        }
                    }
                )
                response.raise_for_status()
                json_response = response.json()
                content = json_response["message"]["content"]
                
                if not content:
                    logger.warning(f"Ollama returned empty content. Full response: {json_response}")
                
                return content
        
        return self._retry_with_backoff(_call_api)

    def get_model_info(self) -> Dict[str, Any]:
        """
        Get Ollama model information.
        
        Returns:
            Dictionary with model info
        """
        return {
            "provider": "ollama",
            "model": self.model,
            "base_url": self.base_url,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }

