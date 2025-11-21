"""
LLM configuration models.

Defines configuration models for LLM providers and benchmark runs.
"""
from typing import Dict, Any, Optional, Literal
from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    """
    Configuration for an LLM provider.
    
    Contains all necessary configuration to initialize and use an LLM provider.
    """

    provider: Literal["openai", "anthropic", "gemini", "ollama", "mock"] = Field(
        ..., description="LLM provider type"
    )
    model: str = Field(..., description="Model name/identifier")
    api_key: Optional[str] = Field(None, description="API key (if required)")
    base_url: Optional[str] = Field(None, description="Base URL for local providers")
    max_tokens: int = Field(default=2000, description="Maximum tokens per response")
    temperature: float = Field(
        default=0.1, ge=0.0, le=2.0, description="Temperature for generation"
    )
    timeout_seconds: int = Field(default=300, ge=1, description="Request timeout")
    retry_attempts: int = Field(
        default=3, ge=0, description="Number of retry attempts"
    )
    rate_limit_delay: float = Field(
        default=1.0, ge=0.0, description="Delay between requests (seconds)"
    )

    # Provider-specific settings
    provider_config: Dict[str, Any] = Field(
        default_factory=dict, description="Provider-specific configuration"
    )

    model_config = {"extra": "allow"}  # Allow additional fields


class LLMBenchmarkConfig(BaseModel):
    """
    Configuration for an LLM benchmark run.
    
    Contains settings specific to running benchmarks with LLMs.
    """

    llm_config: LLMConfig = Field(..., description="LLM provider configuration")
    testee_id: str = Field(..., description="Unique identifier for this LLM testee")
    max_tasks: Optional[int] = Field(
        None, description="Maximum number of tasks to run"
    )
    task_timeout_minutes: int = Field(
        default=10, ge=1, description="Timeout per task in minutes"
    )
    enable_context_preservation: bool = Field(
        default=False, description="Preserve context between tasks"
    )
    log_level: str = Field(default="INFO", description="Logging level")

