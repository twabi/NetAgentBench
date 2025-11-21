# LLM Integration Guide

This document describes how to integrate and use Large Language Models (LLMs) with the Network Configuration Benchmark system.

## Overview

The benchmark system supports multiple LLM providers for automated network configuration generation:

- **OpenAI** - GPT-4, GPT-3.5, and other OpenAI models
- **Anthropic** - Claude models
- **Google Gemini** - Gemini 2.5 Flash, Pro, and other models
- **Ollama** - Local models (experimental)

All providers use a unified interface, making it easy to compare different LLMs.

## Architecture

### Core Components

1. **LLM Provider Abstraction Layer** - Unified interface for different LLM providers
2. **LLM Task Presentation System** - Formats tasks for optimal LLM understanding
3. **LLM Response Parser** - Converts LLM responses to benchmark submissions
4. **LLM Runner** - Main orchestrator for LLM benchmark execution

### Provider Interface

All providers implement the `LLMProvider` interface:

```python
from abc import ABC, abstractmethod

class LLMProvider(ABC):
    @abstractmethod
    def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate response from LLM"""
        pass
```

## Setup

### OpenAI

1. **Get API Key**:
   - Go to [OpenAI Platform](https://platform.openai.com/api-keys)
   - Create an API key

2. **Add to Environment**:
   ```bash
   # .env
   OPENAI_API_KEY=sk-...
   ```

3. **Usage**:
   ```python
   from benchmark.llm.providers import OpenAIProvider
   from benchmark.models.llm_config import LLMConfig
   
   config = LLMConfig(
       provider="openai",
       model="gpt-4",
       api_key=os.getenv("OPENAI_API_KEY"),
       temperature=0.7
   )
   ```

### Anthropic

1. **Get API Key**:
   - Go to [Anthropic Console](https://console.anthropic.com/)
   - Create an API key

2. **Add to Environment**:
   ```bash
   # .env
   ANTHROPIC_API_KEY=sk-ant-...
   ```

3. **Usage**:
   ```python
   from benchmark.llm.providers import AnthropicProvider
   from benchmark.models.llm_config import LLMConfig
   
   config = LLMConfig(
       provider="anthropic",
       model="claude-3-sonnet-20240229",
       api_key=os.getenv("ANTHROPIC_API_KEY"),
       temperature=0.7
   )
   ```

### Google Gemini

1. **Get API Key**:
   - Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
   - Sign in with your Google account
   - Click "Get API Key" or "Create API Key"
   - Copy your API key

2. **Add to Environment**:
   ```bash
   # .env
   GEMINI_API_KEY=your-api-key-here
   ```

3. **Available Models**:
   - `gemini-2.5-flash` - Fast, efficient (DEFAULT)
   - `gemini-2.5-pro` - Most capable
   - `gemini-2.0-flash` - Previous generation
   - `gemini-flash-latest` - Always latest flash
   - `gemini-pro-latest` - Always latest pro
   - Plus 30+ other models

4. **Usage**:
   ```python
   from benchmark.llm.providers import GeminiProvider
   from benchmark.models.llm_config import LLMConfig
   
   config = LLMConfig(
       provider="gemini",
       model="gemini-2.5-flash",  # or "gemini-2.5-pro"
       api_key=os.getenv("GEMINI_API_KEY"),
       temperature=0.7,
       max_tokens=8192
   )
   ```

**Note**: Model names are automatically prefixed with `models/` by the provider.

## Configuration

### LLMConfig Model

```python
from benchmark.models.llm_config import LLMConfig

config = LLMConfig(
    provider="openai",  # or "anthropic", "gemini", "ollama"
    model="gpt-4",      # Model name
    api_key="sk-...",   # API key (optional if in .env)
    temperature=0.7,    # Generation temperature (0.0-2.0)
    max_tokens=2000,    # Maximum response length
    timeout_seconds=300, # Request timeout
    retry_attempts=3,   # Number of retry attempts
    rate_limit_delay=1.0 # Delay between requests
)
```

### Configuration Options

- **provider** (required): LLM provider name
- **model** (required): Model identifier
- **api_key** (optional): API key (can be in .env)
- **temperature** (default: 0.7): Generation temperature
- **max_tokens** (default: 2000): Maximum response length
- **timeout_seconds** (default: 300): Request timeout
- **retry_attempts** (default: 3): Retry attempts on failure
- **rate_limit_delay** (default: 1.0): Delay between requests

## Usage

### Basic Usage

```python
from benchmark.llm.providers import OpenAIProvider
from benchmark.llm.runner import LLMTestee
from benchmark.models.llm_config import LLMConfig
from benchmark.task_repository import TaskRepository

# Create config
config = LLMConfig(
    provider="openai",
    model="gpt-4",
    api_key=os.getenv("OPENAI_API_KEY")
)

# Create provider and testee
provider = OpenAIProvider(config)
testee = LLMTestee(provider=provider, testee_id="gpt4_test")

# Load task
repo = TaskRepository("benchmark-tasks/")
task = repo.get_task("reachability_linear_2n_R1_to_R2")

# Generate submission
submission = testee.generate_submission(task)

# Run benchmark
from benchmark.controller import BenchmarkController
controller = BenchmarkController()
result = controller.run(task, submission)
```

### Using CLI

```bash
# Run with OpenAI
python tests/manual/test_real_llm_benchmark.py --provider openai --limit 5

# Run with Gemini
python tests/manual/test_real_llm_benchmark.py --provider gemini --limit 5

# Run with Anthropic
python tests/manual/test_real_llm_benchmark.py --provider anthropic --limit 5

# Use specific model
python tests/manual/test_real_llm_benchmark.py --provider gemini --model gemini-2.5-pro --limit 3

# Different property types
python tests/manual/test_real_llm_benchmark.py --provider gemini --property bgp_configuration --limit 2
```

### Property-Based Execution

```python
from benchmark.property_executor import PropertyExecutor
from benchmark.task_repository import TaskRepository
from benchmark.llm.runner import LLMTestee
from benchmark.llm.providers import GeminiProvider
from benchmark.models.llm_config import LLMConfig

# Setup
repo = TaskRepository("benchmark-tasks/")
config = LLMConfig(provider="gemini", model="gemini-2.5-flash", api_key=os.getenv("GEMINI_API_KEY"))
provider = GeminiProvider(config)
testee = LLMTestee(provider=provider, testee_id="gemini_test")

# Create executor
executor = PropertyExecutor(repo)

# Run all reachability tasks
results = executor.run_property_tasks(
    property_type="reachability",
    testee=testee,
    limit=10
)

# View aggregate results
print(f"Average Score: {results.aggregate_metrics.avg_final_score}")
```

## Task Presentation

The system automatically formats tasks for LLMs using the `TaskPresenter`:

```python
from benchmark.presenter import TaskPresenter

presenter = TaskPresenter()
prompt = presenter.format_for_llm(task, format="text")
```

The presenter includes:
- Topology description
- Property requirements
- Platform information
- Expected response format

## Response Parsing

LLM responses are automatically parsed to extract configuration commands:

```python
from benchmark.llm.parser import LLMResponseParser

parser = LLMResponseParser()
submission = parser.parse_response(response, task)
```

The parser:
- Extracts JSON from markdown code blocks
- Validates submission format
- Handles various response formats

## Model Comparison

### OpenAI Models

| Model | Speed | Cost | Best For |
|-------|-------|------|----------|
| `gpt-4` | ⚡⚡ Medium | 💰💰💰 High | Best quality, complex tasks |
| `gpt-3.5-turbo` | ⚡⚡⚡ Fast | 💰 Low | Quick tasks, batch processing |

### Anthropic Models

| Model | Speed | Cost | Best For |
|-------|-------|------|----------|
| `claude-3-opus` | ⚡⚡ Medium | 💰💰💰 High | Complex reasoning |
| `claude-3-sonnet` | ⚡⚡ Medium | 💰💰 Medium | Balanced quality/speed |
| `claude-3-haiku` | ⚡⚡⚡ Fast | 💰 Low | Fast, simple tasks |

### Gemini Models

| Model | Speed | Cost | Best For |
|-------|-------|------|----------|
| `gemini-2.5-pro` | ⚡⚡ Medium | 💰💰 Medium | Complex reasoning, best quality |
| `gemini-2.5-flash` | ⚡⚡⚡ Fast | 💰 Low | Quick tasks, batch processing |
| `gemini-2.0-flash` | ⚡⚡⚡ Fast | 💰 Low | Previous gen, still good |

## Best Practices

### Model Selection

1. **For bulk testing**: Use fast models (`gemini-2.5-flash`, `gpt-3.5-turbo`)
2. **For quality**: Use best models (`gpt-4`, `gemini-2.5-pro`, `claude-3-opus`)
3. **For cost**: Use cheaper models (`gemini-2.5-flash`, `claude-3-haiku`)

### Temperature Settings

- **Low (0.3-0.5)**: More deterministic, consistent results
- **Medium (0.7)**: Balanced creativity and consistency (default)
- **High (0.9-1.0)**: More creative, varied results

### Token Limits

- **Simple tasks**: 2000-4000 tokens
- **Complex tasks**: 4000-8000 tokens
- **Very complex**: 8000+ tokens

### Error Handling

```python
try:
    submission = testee.generate_submission(task)
except Exception as e:
    # Handle API errors, timeouts, etc.
    print(f"Error: {e}")
```

## Troubleshooting

### API Key Issues

**Problem**: `API key not found` or `Invalid API key`

**Solution**:
```bash
# Check .env file
cat .env

# Verify API key
echo $OPENAI_API_KEY  # or GEMINI_API_KEY, ANTHROPIC_API_KEY

# Test API key manually
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

### Model Not Found

**Problem**: `Model not found` error

**Solution**:
- Check model name is correct
- For Gemini, try using "latest" aliases
- Verify model is available in your region

### Response Truncated

**Problem**: LLM response is cut off

**Solution**:
```python
# Increase max_tokens
config = LLMConfig(
    provider="openai",
    model="gpt-4",
    max_tokens=8000  # Increase from default
)
```

### Rate Limiting

**Problem**: Rate limit errors

**Solution**:
```python
# Add delay between requests
config = LLMConfig(
    provider="openai",
    model="gpt-4",
    rate_limit_delay=2.0  # 2 seconds between requests
)
```

## Cost Estimates

Approximate costs (as of 2025):

| Provider | Model | Cost per 1M tokens | Cost per task (est) |
|----------|-------|-------------------|---------------------|
| OpenAI | gpt-4 | $30.00 | $0.05 - $0.20 |
| OpenAI | gpt-3.5-turbo | $0.50 | $0.001 - $0.01 |
| Anthropic | claude-3-opus | $15.00 | $0.03 - $0.15 |
| Anthropic | claude-3-sonnet | $3.00 | $0.01 - $0.05 |
| Gemini | gemini-2.5-pro | $1.25 | $0.01 - $0.05 |
| Gemini | gemini-2.5-flash | $0.10 | $0.001 - $0.01 |

**Note**: Actual costs vary by task complexity and response length.

## Examples

### Quick Test

```bash
# Test with Gemini (fast and cheap)
python tests/manual/test_real_llm_benchmark.py --provider gemini --limit 1 --yes
```

### Small Study

```bash
# Run 5 tasks with Gemini
python tests/manual/test_real_llm_benchmark.py \
  --provider gemini \
  --model gemini-2.5-flash \
  --property reachability \
  --limit 5
```

### Compare Providers

```bash
# Run with different providers
python tests/manual/test_real_llm_benchmark.py --provider openai --limit 3
python tests/manual/test_real_llm_benchmark.py --provider gemini --limit 3
python tests/manual/test_real_llm_benchmark.py --provider anthropic --limit 3

# Compare results!
```

## Related Documentation

- [Getting Started](GETTING_STARTED.md) - Installation and setup
- [Research Usage](RESEARCH_USAGE.md) - Running studies and analyzing results
- [CLI Usage](CLI_USAGE.md) - Command-line interface reference
- [Human Benchmark Guide](HUMAN_BENCHMARK_GUIDE.md) - Guide for human participants

---

**Last Updated**: Phase 12 - Documentation Consolidation

