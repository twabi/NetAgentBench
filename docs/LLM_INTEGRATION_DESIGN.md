# LLM and Human Integration Design

## Overview

This document outlines the comprehensive design for integrating both Large Language Models (LLMs) and Human Network Engineers into the Network Configuration Benchmark system. The integration enables automated evaluation of LLMs' ability to generate network configurations and provides a user-friendly interface for human engineers to participate in the same benchmark framework.

## Architecture

### Core Components

#### LLM Integration
1. **LLM Provider Abstraction Layer** - Unified interface for different LLM providers
2. **LLM Task Presentation System** - Formats tasks for optimal LLM understanding
3. **LLM Response Parser** - Converts LLM responses to benchmark submissions
4. **LLM Runner** - Main orchestrator for LLM benchmark execution

#### Human Integration
5. **Human Task Presentation System** - User-friendly interface for human engineers
6. **Human Input Collection** - Interactive and file-based input collection
7. **Human Benchmark Runner** - Orchestrator for human benchmark execution

#### Shared Components
8. **Suite Management** - Handles multi-task benchmark suites for both LLMs and humans
9. **Logging & Analytics** - Comprehensive logging and performance analysis
10. **Unified Scoring** - Same evaluation framework for both LLMs and humans

## Implementation

### 1. LLM Provider Abstraction Layer

**File**: `src/benchmark/llm/providers.py`

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pydantic import BaseModel

class LLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize the LLM provider with configuration"""
        pass
    
    @abstractmethod
    def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate response from LLM"""
        pass
    
    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """Get model information (name, version, etc.)"""
        pass

class OpenAIProvider(LLMProvider):
    """OpenAI API integration"""
    
    def initialize(self, config: Dict[str, Any]) -> None:
        self.api_key = config["api_key"]
        self.model = config.get("model", "gpt-4")
        self.max_tokens = config.get("max_tokens", 2000)
        # Initialize OpenAI client
        
    def generate_response(self, prompt: str, **kwargs) -> str:
        # Call OpenAI API
        pass

class AnthropicProvider(LLMProvider):
    """Anthropic Claude API integration"""
    
    def initialize(self, config: Dict[str, Any]) -> None:
        self.api_key = config["api_key"]
        self.model = config.get("model", "claude-3-sonnet")
        # Initialize Anthropic client
        
    def generate_response(self, prompt: str, **kwargs) -> str:
        # Call Anthropic API
        pass

class OllamaProvider(LLMProvider):
    """Local Ollama integration"""
    
    def initialize(self, config: Dict[str, Any]) -> None:
        self.model = config["model"]
        self.base_url = config.get("base_url", "http://localhost:11434")
        # Initialize Ollama client
        
    def generate_response(self, prompt: str, **kwargs) -> str:
        # Call local Ollama API
        pass
```

### 2. LLM Configuration Models

**File**: `src/benchmark/models/llm_config.py`

```python
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, Literal

class LLMConfig(BaseModel):
    """Configuration for LLM provider"""
    
    provider: Literal["openai", "anthropic", "ollama", "mock"] = Field(..., description="LLM provider")
    model: str = Field(..., description="Model name/identifier")
    api_key: Optional[str] = Field(None, description="API key (if required)")
    base_url: Optional[str] = Field(None, description="Base URL for local providers")
    max_tokens: int = Field(default=2000, description="Maximum tokens per response")
    temperature: float = Field(default=0.1, description="Temperature for generation")
    timeout_seconds: int = Field(default=300, description="Request timeout")
    retry_attempts: int = Field(default=3, description="Number of retry attempts")
    rate_limit_delay: float = Field(default=1.0, description="Delay between requests")
    
    # Provider-specific settings
    provider_config: Dict[str, Any] = Field(default_factory=dict, description="Provider-specific configuration")

class LLMBenchmarkConfig(BaseModel):
    """Configuration for LLM benchmark run"""
    
    llm_config: LLMConfig = Field(..., description="LLM provider configuration")
    suite_id: str = Field(..., description="Benchmark suite identifier")
    testee_id: str = Field(..., description="Unique identifier for this LLM run")
    max_tasks: Optional[int] = Field(None, description="Maximum number of tasks to run")
    task_timeout_minutes: int = Field(default=10, description="Timeout per task in minutes")
    enable_context_preservation: bool = Field(default=True, description="Preserve context between tasks")
    log_level: str = Field(default="INFO", description="Logging level")
```

### 3. Task Presentation System

**File**: `src/benchmark/llm/presenter.py`

```python
from typing import Dict, Any, List
from benchmark.models.task import TaskDefinition

class TaskPresenter:
    """Formats tasks for LLM presentation"""
    
    def format_task_for_llm(self, task: TaskDefinition, task_index: int, total_tasks: int) -> str:
        """Format a task for LLM presentation with full context"""
        
        prompt = f"""
# Network Configuration Task {task_index}/{total_tasks}

## Task ID: {task.task_id}
## Description: {task.description}
## Platform: {task.platform.value}

## Network Topology
{self._generate_topology_diagram(task)}

## Success Criteria
You need to configure the network to satisfy these properties:
{self._format_properties(task.intent.properties)}

## Configuration Requirements
- Platform: {task.platform.value}
- Time limit: {task.convergence.timeout_seconds} seconds
- You must provide configuration commands for each node

## Expected Response Format
Provide your solution as a JSON object with this structure:
```json
{{
  "approach": {{
    "description": "Brief description of your approach",
    "commands": [
      {{
        "node": "R1",
        "commands": ["command1", "command2", ...]
      }},
      {{
        "node": "R2", 
        "commands": ["command1", "command2", ...]
      }}
    ]
  }}
}}
```

Please analyze the topology and provide the configuration commands needed to satisfy all success criteria.
"""
        return prompt.strip()
    
    def _generate_topology_diagram(self, task: TaskDefinition) -> str:
        """Generate ASCII topology diagram"""
        # Implementation to create ASCII art of the network topology
        pass
    
    def _format_properties(self, properties: List[Property]) -> str:
        """Format properties as readable success criteria"""
        formatted = []
        for prop in properties:
            formatted.append(f"- {prop.description}")
        return "\n".join(formatted)
```

### 4. LLM Response Parser

**File**: `src/benchmark/llm/parser.py`

```python
import json
import re
from typing import Dict, Any, Optional
from benchmark.models.submission import Submission, Approach, CommandSequence

class LLMResponseParser:
    """Parses and validates LLM responses"""
    
    def parse_response(self, response: str, task_id: str) -> Submission:
        """Parse LLM response into Submission format"""
        
        # Try to extract JSON from response
        json_content = self._extract_json(response)
        
        if not json_content:
            raise ValueError("No valid JSON found in LLM response")
        
        # Validate and convert to Submission
        try:
            approach_data = json_content["approach"]
            commands = []
            
            for cmd_seq in approach_data["commands"]:
                commands.append(CommandSequence(
                    node=cmd_seq["node"],
                    commands=cmd_seq["commands"]
                ))
            
            approach = Approach(
                description=approach_data["description"],
                commands=commands
            )
            
            return Submission(
                task_id=task_id,
                testee_id="llm_generated",  # Will be overridden
                testee_type="llm",
                approach=approach
            )
            
        except (KeyError, TypeError) as e:
            raise ValueError(f"Invalid response format: {e}")
    
    def _extract_json(self, response: str) -> Optional[Dict[str, Any]]:
        """Extract JSON content from LLM response"""
        # Look for JSON code blocks
        json_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
        matches = re.findall(json_pattern, response, re.DOTALL)
        
        if matches:
            try:
                return json.loads(matches[0])
            except json.JSONDecodeError:
                pass
        
        # Look for JSON without code blocks
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        
        return None
```

### 5. Main LLM Runner

**File**: `src/benchmark/llm_runner.py`

```python
import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

from benchmark.controller import BenchmarkController
from benchmark.models.task import TaskDefinition
from benchmark.models.submission import Submission
from benchmark.models.results import BenchmarkResult
from benchmark.llm.providers import LLMProvider, OpenAIProvider, AnthropicProvider, OllamaProvider
from benchmark.llm.presenter import TaskPresenter
from benchmark.llm.parser import LLMResponseParser
from benchmark.storage import ResultsStorage

logger = logging.getLogger(__name__)

class LLMBenchmarkRunner:
    """Main LLM benchmark runner"""
    
    def __init__(self, config: LLMBenchmarkConfig):
        self.config = config
        self.llm_provider = self._initialize_provider()
        self.presenter = TaskPresenter()
        self.parser = LLMResponseParser()
        self.controller = BenchmarkController()
        self.storage = ResultsStorage()
        
        # Setup logging
        self._setup_logging()
        
    def _initialize_provider(self) -> LLMProvider:
        """Initialize the appropriate LLM provider"""
        provider_map = {
            "openai": OpenAIProvider,
            "anthropic": AnthropicProvider,
            "ollama": OllamaProvider,
        }
        
        provider_class = provider_map.get(self.config.llm_config.provider)
        if not provider_class:
            raise ValueError(f"Unknown provider: {self.config.llm_config.provider}")
        
        provider = provider_class()
        provider.initialize(self.config.llm_config.model_dump())
        return provider
    
    def run_benchmark_suite(self, tasks: List[TaskDefinition]) -> Dict[str, Any]:
        """Run complete benchmark suite with LLM"""
        
        logger.info(f"Starting LLM benchmark suite: {self.config.suite_id}")
        logger.info(f"LLM: {self.config.llm_config.provider}/{self.config.llm_config.model}")
        logger.info(f"Tasks: {len(tasks)}")
        
        results = []
        suite_start_time = time.time()
        
        # Limit tasks if specified
        if self.config.max_tasks:
            tasks = tasks[:self.config.max_tasks]
        
        for i, task in enumerate(tasks, 1):
            logger.info(f"Running task {i}/{len(tasks)}: {task.task_id}")
            
            try:
                result = self._run_single_task(task, i, len(tasks))
                results.append(result)
                
                # Log progress
                logger.info(f"Task {i} completed - Score: {result.scoring.final_score:.3f}")
                
            except Exception as e:
                logger.error(f"Task {i} failed: {e}")
                # Create error result
                error_result = self._create_error_result(task, str(e))
                results.append(error_result)
        
        # Calculate suite-level metrics
        suite_metrics = self._calculate_suite_metrics(results)
        suite_duration = time.time() - suite_start_time
        
        suite_result = {
            "suite_id": self.config.suite_id,
            "testee_id": self.config.testee_id,
            "llm_config": self.config.llm_config.model_dump(),
            "total_tasks": len(tasks),
            "completed_tasks": len([r for r in results if r.success]),
            "duration_seconds": suite_duration,
            "results": results,
            "suite_metrics": suite_metrics,
            "timestamp": datetime.now().isoformat()
        }
        
        # Save suite results
        self._save_suite_results(suite_result)
        
        logger.info(f"Suite completed - Average score: {suite_metrics['average_score']:.3f}")
        return suite_result
    
    def _run_single_task(self, task: TaskDefinition, task_index: int, total_tasks: int) -> BenchmarkResult:
        """Run a single task with LLM"""
        
        # Format task for LLM
        prompt = self.presenter.format_task_for_llm(task, task_index, total_tasks)
        
        # Get LLM response
        start_time = time.time()
        try:
            response = self.llm_provider.generate_response(
                prompt,
                max_tokens=self.config.llm_config.max_tokens,
                temperature=self.config.llm_config.temperature
            )
            llm_time = time.time() - start_time
            
        except Exception as e:
            raise Exception(f"LLM request failed: {e}")
        
        # Parse response
        try:
            submission = self.parser.parse_response(response, task.task_id)
            submission.testee_id = self.config.testee_id
            
        except Exception as e:
            raise Exception(f"Failed to parse LLM response: {e}")
        
        # Run benchmark
        result = self.controller.run(task, submission)
        
        # Add LLM-specific metadata
        result.execution_log.append(f"LLM response time: {llm_time:.2f}s")
        result.execution_log.append(f"LLM model: {self.config.llm_config.provider}/{self.config.llm_config.model}")
        
        return result
    
    def _calculate_suite_metrics(self, results: List[BenchmarkResult]) -> Dict[str, Any]:
        """Calculate suite-level metrics"""
        
        successful_results = [r for r in results if r.success]
        
        if not successful_results:
            return {
                "average_score": 0.0,
                "average_completeness": 0.0,
                "average_robustness": 0.0,
                "average_syntactic_validity": 0.0,
                "average_efficiency": 0.0,
                "valid_solution_rate": 0.0,
                "total_properties_satisfied": 0,
                "total_properties": 0
            }
        
        # Calculate averages
        avg_score = sum(r.scoring.final_score for r in successful_results) / len(successful_results)
        avg_completeness = sum(r.scoring.completeness for r in successful_results) / len(successful_results)
        avg_robustness = sum(r.scoring.robustness for r in successful_results) / len(successful_results)
        avg_syntactic = sum(r.scoring.syntactic_validity for r in successful_results) / len(successful_results)
        
        # Calculate efficiency average (only for results that have it)
        efficiency_results = [r.scoring.efficiency for r in successful_results if r.scoring.efficiency is not None]
        avg_efficiency = sum(efficiency_results) / len(efficiency_results) if efficiency_results else None
        
        # Calculate validity rate
        valid_solutions = sum(1 for r in successful_results if r.validity.is_valid_solution)
        valid_rate = valid_solutions / len(successful_results)
        
        # Calculate property satisfaction
        total_satisfied = sum(sum(1 for p in r.property_results if p.satisfied) for r in successful_results)
        total_properties = sum(len(r.property_results) for r in successful_results)
        
        return {
            "average_score": avg_score,
            "average_completeness": avg_completeness,
            "average_robustness": avg_robustness,
            "average_syntactic_validity": avg_syntactic,
            "average_efficiency": avg_efficiency,
            "valid_solution_rate": valid_rate,
            "total_properties_satisfied": total_satisfied,
            "total_properties": total_properties,
            "property_satisfaction_rate": total_satisfied / total_properties if total_properties > 0 else 0.0
        }
    
    def _save_suite_results(self, suite_result: Dict[str, Any]) -> None:
        """Save suite results to storage"""
        
        # Create suite results directory
        suite_dir = Path("results/suites") / self.config.suite_id
        suite_dir.mkdir(parents=True, exist_ok=True)
        
        # Save suite-level results
        suite_file = suite_dir / f"{self.config.testee_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(suite_file, 'w') as f:
            json.dump(suite_result, f, indent=2, default=str)
        
        logger.info(f"Suite results saved to: {suite_file}")
        
        # Save individual task results
        for result in suite_result["results"]:
            self.storage.save_run(result)
    
    def _setup_logging(self) -> None:
        """Setup logging for LLM benchmark"""
        
        log_dir = Path("results/logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        
        log_file = log_dir / f"llm_benchmark_{self.config.testee_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        logging.basicConfig(
            level=getattr(logging, self.config.log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
```

### 6. CLI Integration

**File**: `src/benchmark/cli.py` (addition)

```python
@click.command()
@click.argument('suite_id')
@click.option('--llm-config', required=True, help='Path to LLM configuration file')
@click.option('--testee-id', help='Unique identifier for this run')
@click.option('--max-tasks', type=int, help='Maximum number of tasks to run')
@click.option('--log-level', default='INFO', help='Logging level')
def run_suite_llm(suite_id: str, llm_config: str, testee_id: Optional[str], max_tasks: Optional[int], log_level: str):
    """Run benchmark suite with LLM integration"""
    
    # Load LLM configuration
    with open(llm_config, 'r') as f:
        llm_config_data = json.load(f)
    
    # Generate testee ID if not provided
    if not testee_id:
        testee_id = f"{llm_config_data['provider']}_{llm_config_data['model']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Create benchmark configuration
    config = LLMBenchmarkConfig(
        llm_config=LLMConfig(**llm_config_data),
        suite_id=suite_id,
        testee_id=testee_id,
        max_tasks=max_tasks,
        log_level=log_level
    )
    
    # Load tasks from suite
    suite_manager = SuiteManager()
    suite = suite_manager.load_suite(suite_id)
    tasks = [suite_manager.load_task(task_id) for task_id in suite.tasks]
    
    # Run benchmark
    runner = LLMBenchmarkRunner(config)
    results = runner.run_benchmark_suite(tasks)
    
    # Print summary
    print(f"\nBenchmark Suite Complete!")
    print(f"Suite: {suite_id}")
    print(f"LLM: {config.llm_config.provider}/{config.llm_config.model}")
    print(f"Tasks: {results['completed_tasks']}/{results['total_tasks']}")
    print(f"Average Score: {results['suite_metrics']['average_score']:.3f}")
    print(f"Valid Solution Rate: {results['suite_metrics']['valid_solution_rate']:.1%}")
    print(f"Duration: {results['duration_seconds']:.1f}s")
```

## Configuration Files

### Example LLM Configuration Files

**File**: `configs/openai_gpt4.json`

```json
{
  "provider": "openai",
  "model": "gpt-4",
  "api_key": "your-api-key-here",
  "max_tokens": 2000,
  "temperature": 0.1,
  "timeout_seconds": 300,
  "retry_attempts": 3,
  "rate_limit_delay": 1.0
}
```

**File**: `configs/anthropic_claude.json`

```json
{
  "provider": "anthropic", 
  "model": "claude-3-sonnet-20240229",
  "api_key": "your-api-key-here",
  "max_tokens": 2000,
  "temperature": 0.1,
  "timeout_seconds": 300,
  "retry_attempts": 3,
  "rate_limit_delay": 1.0
}
```

**File**: `configs/ollama_local.json`

```json
{
  "provider": "ollama",
  "model": "llama2:7b",
  "base_url": "http://localhost:11434",
  "max_tokens": 2000,
  "temperature": 0.1,
  "timeout_seconds": 300,
  "retry_attempts": 3,
  "rate_limit_delay": 0.5
}
```

## Usage Examples

### Basic Usage

```bash
# Run a benchmark suite with GPT-4
benchmark run-suite-llm research_basic_v1.0 --llm-config configs/openai_gpt4.json --testee-id gpt4_test_001

# Run with local Ollama model
benchmark run-suite-llm research_basic_v1.0 --llm-config configs/ollama_local.json --max-tasks 10

# Run with custom testee ID and logging
benchmark run-suite-llm research_basic_v1.0 --llm-config configs/anthropic_claude.json --testee-id claude_experiment_001 --log-level DEBUG
```

### Advanced Usage

```bash
# Run with specific task selection strategy
benchmark run-suite-llm research_basic_v1.0 --llm-config configs/openai_gpt4.json --strategy stratified_random --size 25 --seed 42

# Run difficulty-targeted suite
benchmark run-suite-llm -- --llm-config configs/anthropic_claude.json --strategy difficulty_targeted --difficulty intermediate --size 20

# Run protocol-focused suite
benchmark run-suite-llm -- --llm-config configs/openai_gpt4.json --strategy protocol_focused --protocols bgp,ospf --size 15
```

## Workflow

### Complete LLM Benchmarking Process

1. **Suite Selection and Setup**
   ```bash
   # List available benchmark suites
   benchmark list-suites
   
   # Run suite with live LLM integration
   benchmark run-suite-llm research_basic_networking_v1.0 --llm-config openai_gpt4.json
   ```

2. **Task Presentation to LLM**
   ```python
   # Each task is presented with full context:
   task_prompt = {
       "task_id": "bgp_basic_001",
       "description": "Configure BGP session between two routers",
       "topology": {
           "nodes": [{"name": "R1", "type": "router"}, {"name": "R2", "type": "router"}],
           "links": [{"endpoints": ["R1:eth1", "R2:eth1"]}],
           "visualization": "ASCII topology diagram"
       },
       "success_criteria": [
           "BGP session established between R1 and R2",
           "Routes exchanged successfully"
       ],
       "time_limit_seconds": 300,
       "platform": "frr"
   }
   ```

3. **LLM Response Processing**
   ```python
   # LLM generates configuration approach
   llm_response = llm_client.generate(task_prompt)
   
   # System parses and validates response
   submission = LLMBenchmarkRunner.parse_response(llm_response, task_id)
   
   # Executes benchmark with LLM's solution
   result = controller.run(task, submission)
   ```

4. **Suite-Level Analysis**
   ```python
   # Aggregate results across all tasks in suite
   suite_results = SuiteExecutor.run_suite(suite, "gpt4_20250113")
   
   # Generate comprehensive analysis
   analysis = LLMAnalyzer.analyze_suite_performance(suite_results)
   ```

## Key Features

### Multi-Provider Support
- **OpenAI**: GPT-3.5, GPT-4, GPT-4 Turbo
- **Anthropic**: Claude-3 Haiku, Sonnet, Opus
- **Ollama**: Local models (Llama2, Mistral, CodeLlama, etc.)
- **Extensible**: Easy to add new providers

### Comprehensive Logging
- **Task-level logs**: Individual task execution details
- **Suite-level logs**: Aggregated performance metrics
- **LLM-specific logs**: Response times, token usage, API calls
- **Error logs**: Detailed error tracking and debugging

### Suite-Level Aggregation
- **Average scores**: Mean performance across all tasks
- **Validity rates**: Percentage of valid solutions
- **Property satisfaction**: Overall success rate
- **Performance metrics**: Response times, execution duration

### Error Handling
- **LLM failures**: Graceful handling of API errors
- **Parsing errors**: Robust response validation
- **Infrastructure errors**: Network topology failures
- **Partial completion**: Continue suite even if some tasks fail

### Rate Limiting & Retry Logic
- **Built-in rate limiting**: Prevent API quota exhaustion
- **Exponential backoff**: Smart retry with increasing delays
- **Timeout handling**: Prevent hanging requests
- **Circuit breaker**: Stop retrying after max attempts

### Result Storage
- **Individual results**: Per-task benchmark results
- **Suite results**: Aggregated suite-level metrics
- **Log files**: Comprehensive execution logs
- **JSON format**: Easy integration with analysis tools

## Integration Points

1. **Task Repository** → **LLM Presentation**: Tasks formatted for optimal LLM understanding
2. **LLM Response** → **Submission Format**: Automatic parsing and validation
3. **Individual Results** → **Suite Analysis**: Aggregated performance metrics
4. **Multi-Provider Support**: Unified interface for different LLM APIs

## Research Applications

### Academic Studies
- **Comparative Analysis**: Compare different LLM providers
- **Performance Evaluation**: Assess LLM capabilities on network tasks
- **Capability Assessment**: Understand strengths and weaknesses
- **Benchmark Validation**: Validate task difficulty and coverage

### Industry Applications
- **LLM Selection**: Choose optimal LLM for network automation
- **Cost Analysis**: Evaluate performance vs. cost trade-offs
- **Capability Mapping**: Understand which tasks each LLM handles well
- **Training Data**: Generate training examples for specialized models

## Future Enhancements

### Planned Features
- **Context Preservation**: Maintain conversation context across tasks
- **Adaptive Prompting**: Adjust prompts based on LLM performance
- **Multi-Modal Support**: Support for image-based topology descriptions
- **Real-time Monitoring**: Live dashboard for benchmark progress
- **Batch Processing**: Parallel execution of multiple LLM runs
- **Custom Evaluators**: Specialized evaluation for different task types

### Research Extensions
- **Transfer Learning**: Evaluate fine-tuned models
- **Few-Shot Learning**: Test with example-based prompting
- **Chain-of-Thought**: Evaluate reasoning capabilities
- **Tool Integration**: Test LLMs with network simulation tools
- **Human Comparison**: Compare LLM performance to human experts

## Human Integration Implementation

### 1. Human Task Presentation System

**File**: `src/benchmark/human_interface.py`

```python
from typing import List, Dict, Any, Optional
from benchmark.models.task import TaskDefinition
from benchmark.models.submission import Submission, Approach, CommandSequence
import json
from datetime import datetime

class HumanTaskPresenter:
    """Presents tasks to human network engineers in a user-friendly format"""
    
    def present_task_interactive(self, task: TaskDefinition, task_index: int, total_tasks: int) -> Dict[str, Any]:
        """Present task with interactive elements for human engineers"""
        
        presentation = {
            "task_header": self._format_task_header(task, task_index, total_tasks),
            "topology": self._format_topology_for_human(task),
            "success_criteria": self._format_success_criteria(task),
            "platform_info": self._format_platform_info(task),
            "time_limits": self._format_time_limits(task),
            "interactive_elements": self._create_interactive_elements(task)
        }
        
        return presentation
    
    def _format_task_header(self, task: TaskDefinition, task_index: int, total_tasks: int) -> str:
        """Format task header with progress"""
        return f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                          NETWORK CONFIGURATION TASK                         ║
║                                {task_index}/{total_tasks}                                ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ Task ID: {task.task_id:<70} ║
║ Description: {task.description:<65} ║
║ Platform: {task.platform.value:<70} ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
    
    def _format_topology_for_human(self, task: TaskDefinition) -> str:
        """Format topology with ASCII diagram and detailed info"""
        topology_text = f"""
🌐 NETWORK TOPOLOGY

{self._generate_ascii_topology(task)}

📋 NODE DETAILS:
"""
        for node in task.topology.nodes:
            topology_text += f"   • {node.name} ({node.type.value}) - Image: {node.image}\n"
        
        topology_text += f"\n🔗 CONNECTIONS:\n"
        for link in task.topology.links:
            topology_text += f"   • {link.endpoints[0]} ↔ {link.endpoints[1]}\n"
        
        return topology_text
    
    def _generate_ascii_topology(self, task: TaskDefinition) -> str:
        """Generate ASCII art topology diagram"""
        nodes = task.topology.nodes
        links = task.topology.links
        
        # Simple ASCII representation
        diagram = ""
        if len(nodes) == 2:
            diagram = f"    {nodes[0].name} ───── {nodes[1].name}"
        elif len(nodes) == 3:
            diagram = f"    {nodes[0].name} ──── {nodes[1].name} ──── {nodes[2].name}"
        else:
            # More complex topologies
            diagram = "    [Complex topology - see connections below]"
        
        return diagram
    
    def _format_success_criteria(self, task: TaskDefinition) -> str:
        """Format success criteria in human-readable format"""
        criteria_text = """
✅ SUCCESS CRITERIA

You need to configure the network so that ALL of these properties are satisfied:
"""
        for i, prop in enumerate(task.intent.properties, 1):
            criteria_text += f"   {i}. {prop.description}\n"
        
        criteria_text += f"\n📊 EVALUATION METHOD:\n"
        criteria_text += f"   Each property will be tested using: {task.intent.properties[0].evaluation.method}\n"
        
        return criteria_text
    
    def _format_platform_info(self, task: TaskDefinition) -> str:
        """Format platform-specific information"""
        platform_info = f"""
🔧 PLATFORM INFORMATION

Target Platform: {task.platform.value.upper()}
"""
        
        if task.platform.value == "frr":
            platform_info += """
Common Commands:
   • vtysh - Enter configuration mode
   • show ip route - Display routing table
   • show bgp summary - Show BGP status
   • configure terminal - Enter global config
   • interface <name> - Configure interface
"""
        elif task.platform.value == "cisco_ios":
            platform_info += """
Common Commands:
   • enable - Enter privileged mode
   • configure terminal - Enter global config
   • show ip route - Display routing table
   • show bgp summary - Show BGP status
   • interface <name> - Configure interface
"""
        
        return platform_info
    
    def _format_time_limits(self, task: TaskDefinition) -> str:
        """Format time limit information"""
        return f"""
⏱️  TIME LIMITS

Configuration Time: {task.convergence.timeout_seconds} seconds
Check Interval: {task.convergence.check_interval_seconds} seconds

💡 TIP: You have {task.convergence.timeout_seconds} seconds to complete your configuration.
The system will wait {task.convergence.check_interval_seconds} seconds between checks.
"""
    
    def _create_interactive_elements(self, task: TaskDefinition) -> Dict[str, Any]:
        """Create interactive elements for human input"""
        return {
            "command_templates": self._generate_command_templates(task),
            "validation_hints": self._generate_validation_hints(task),
            "common_mistakes": self._generate_common_mistakes(task)
        }
    
    def _generate_command_templates(self, task: TaskDefinition) -> List[str]:
        """Generate command templates for the platform"""
        templates = []
        
        if task.platform.value == "frr":
            templates = [
                "vtysh",
                "configure terminal",
                "router bgp <as_number>",
                "neighbor <ip_address> remote-as <as_number>",
                "network <network/mask>",
                "interface <interface_name>",
                "ip address <ip/mask>",
                "no shutdown"
            ]
        elif task.platform.value == "cisco_ios":
            templates = [
                "enable",
                "configure terminal",
                "router bgp <as_number>",
                "neighbor <ip_address> remote-as <as_number>",
                "network <network/mask>",
                "interface <interface_name>",
                "ip address <ip/mask>",
                "no shutdown"
            ]
        
        return templates
    
    def _generate_validation_hints(self, task: TaskDefinition) -> List[str]:
        """Generate validation hints for the task"""
        hints = [
            "Make sure all interfaces are configured with correct IP addresses",
            "Verify routing protocols are properly configured",
            "Check that all required adjacencies/sessions are established",
            "Ensure reachability tests will pass",
            "Double-check command syntax for the target platform"
        ]
        return hints
    
    def _generate_common_mistakes(self, task: TaskDefinition) -> List[str]:
        """Generate common mistakes to avoid"""
        mistakes = [
            "Forgetting to configure interface IP addresses",
            "Missing 'no shutdown' on interfaces",
            "Incorrect AS numbers in BGP configuration",
            "Wrong network statements",
            "Missing neighbor statements",
            "Incorrect interface names"
        ]
        return mistakes
```

### 2. Human Input Collection System

**File**: `src/benchmark/human_input.py`

```python
from typing import List, Dict, Any, Optional
from benchmark.models.submission import Submission, Approach, CommandSequence
import json

class HumanInputCollector:
    """Collects configuration input from human network engineers"""
    
    def collect_human_submission(self, task_id: str, testee_id: str) -> Submission:
        """Interactive collection of human submission"""
        
        print("\n" + "="*80)
        print("🤖 HUMAN NETWORK ENGINEER BENCHMARK")
        print("="*80)
        
        # Collect approach description
        print("\n📝 APPROACH DESCRIPTION")
        print("Please describe your configuration approach:")
        description = input("Description (optional): ").strip()
        
        # Collect commands per node
        commands = []
        nodes = self._get_nodes_from_task(task_id)  # This would need task context
        
        print(f"\n🔧 CONFIGURATION COMMANDS")
        print("Enter commands for each node. Type 'DONE' when finished for a node.")
        print("Commands will be executed in the order you enter them.")
        
        for node in nodes:
            print(f"\n📡 Node: {node}")
            node_commands = []
            
            while True:
                cmd = input(f"  Command for {node} (or 'DONE'): ").strip()
                if cmd.upper() == 'DONE':
                    break
                if cmd:
                    node_commands.append(cmd)
            
            if node_commands:
                commands.append(CommandSequence(node=node, commands=node_commands))
        
        # Create submission
        approach = Approach(
            description=description if description else None,
            commands=commands
        )
        
        submission = Submission(
            task_id=task_id,
            testee_id=testee_id,
            testee_type="human",
            approach=approach
        )
        
        return submission
    
    def collect_submission_from_file(self, file_path: str) -> Submission:
        """Load human submission from JSON file"""
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        # Convert to Submission model
        commands = []
        for cmd_seq in data["approach"]["commands"]:
            commands.append(CommandSequence(
                node=cmd_seq["node"],
                commands=cmd_seq["commands"]
            ))
        
        approach = Approach(
            description=data["approach"].get("description"),
            commands=commands
        )
        
        return Submission(
            task_id=data["task_id"],
            testee_id=data["testee_id"],
            testee_type=data["testee_type"],
            approach=approach
        )
    
    def save_submission_template(self, task_id: str, file_path: str) -> None:
        """Save a template file for human to fill out"""
        template = {
            "task_id": task_id,
            "testee_id": "human_engineer_001",
            "testee_type": "human",
            "approach": {
                "description": "Describe your configuration approach here",
                "commands": [
                    {
                        "node": "R1",
                        "commands": [
                            "command1",
                            "command2"
                        ]
                    },
                    {
                        "node": "R2", 
                        "commands": [
                            "command1",
                            "command2"
                        ]
                    }
                ]
            }
        }
        
        with open(file_path, 'w') as f:
            json.dump(template, f, indent=2)
        
        print(f"Template saved to: {file_path}")
        print("Edit this file with your configuration and use it for submission.")
```

### 3. Human Benchmark Runner

**File**: `src/benchmark/human_runner.py`

```python
from typing import List, Dict, Any, Optional
from benchmark.controller import BenchmarkController
from benchmark.models.task import TaskDefinition
from benchmark.models.submission import Submission
from benchmark.models.results import BenchmarkResult
from benchmark.human_interface import HumanTaskPresenter
from benchmark.human_input import HumanInputCollector
from benchmark.storage import ResultsStorage
import time
from datetime import datetime

class HumanBenchmarkRunner:
    """Runs benchmarks with human network engineers"""
    
    def __init__(self):
        self.presenter = HumanTaskPresenter()
        self.input_collector = HumanInputCollector()
        self.controller = BenchmarkController()
        self.storage = ResultsStorage()
    
    def run_interactive_benchmark(self, task: TaskDefinition, testee_id: str) -> BenchmarkResult:
        """Run interactive benchmark with human engineer"""
        
        print("\n" + "="*80)
        print("🚀 STARTING HUMAN BENCHMARK")
        print("="*80)
        
        # Present task to human
        presentation = self.presenter.present_task_interactive(task, 1, 1)
        
        print(presentation["task_header"])
        print(presentation["topology"])
        print(presentation["success_criteria"])
        print(presentation["platform_info"])
        print(presentation["time_limits"])
        
        # Show interactive elements
        print("\n💡 COMMAND TEMPLATES:")
        for template in presentation["interactive_elements"]["command_templates"]:
            print(f"   • {template}")
        
        print("\n⚠️  COMMON MISTAKES TO AVOID:")
        for mistake in presentation["interactive_elements"]["common_mistakes"]:
            print(f"   • {mistake}")
        
        print("\n✅ VALIDATION HINTS:")
        for hint in presentation["interactive_elements"]["validation_hints"]:
            print(f"   • {hint}")
        
        # Collect human input
        print("\n" + "="*80)
        print("📝 ENTER YOUR CONFIGURATION")
        print("="*80)
        
        submission = self.input_collector.collect_human_submission(task.task_id, testee_id)
        
        # Confirm submission
        print("\n" + "="*80)
        print("📋 CONFIGURATION SUMMARY")
        print("="*80)
        print(f"Task: {task.task_id}")
        print(f"Engineer: {testee_id}")
        print(f"Description: {submission.approach.description or 'None'}")
        print(f"Commands:")
        for cmd_seq in submission.approach.commands:
            print(f"  {cmd_seq.node}:")
            for cmd in cmd_seq.commands:
                print(f"    • {cmd}")
        
        confirm = input("\nProceed with this configuration? (y/N): ").strip().lower()
        if confirm != 'y':
            print("Benchmark cancelled.")
            return None
        
        # Run benchmark
        print("\n" + "="*80)
        print("🏃 RUNNING BENCHMARK")
        print("="*80)
        print("Executing your configuration and evaluating results...")
        
        start_time = time.time()
        result = self.controller.run(task, submission)
        duration = time.time() - start_time
        
        # Display results
        self._display_results(result, duration)
        
        # Save results
        self.storage.save_run(result)
        print(f"\nResults saved with run_id: {result.run_id}")
        
        return result
    
    def run_suite_interactive(self, tasks: List[TaskDefinition], testee_id: str) -> Dict[str, Any]:
        """Run interactive benchmark suite with human engineer"""
        
        print("\n" + "="*80)
        print("🎯 HUMAN BENCHMARK SUITE")
        print("="*80)
        print(f"Engineer: {testee_id}")
        print(f"Tasks: {len(tasks)}")
        
        results = []
        suite_start_time = time.time()
        
        for i, task in enumerate(tasks, 1):
            print(f"\n{'='*20} TASK {i}/{len(tasks)} {'='*20}")
            
            # Present task
            presentation = self.presenter.present_task_interactive(task, i, len(tasks))
            print(presentation["task_header"])
            print(presentation["topology"])
            print(presentation["success_criteria"])
            
            # Collect input
            submission = self.input_collector.collect_human_submission(task.task_id, testee_id)
            
            # Run benchmark
            print(f"\nRunning task {i}...")
            result = self.controller.run(task, submission)
            results.append(result)
            
            # Show immediate feedback
            print(f"Task {i} Score: {result.scoring.final_score:.3f}")
            print(f"Valid Solution: {'✅' if result.validity.is_valid_solution else '❌'}")
        
        # Calculate suite metrics
        suite_metrics = self._calculate_suite_metrics(results)
        suite_duration = time.time() - suite_start_time
        
        # Display suite results
        self._display_suite_results(suite_metrics, suite_duration)
        
        return {
            "suite_results": results,
            "suite_metrics": suite_metrics,
            "duration": suite_duration
        }
    
    def _display_results(self, result: BenchmarkResult, duration: float) -> None:
        """Display benchmark results to human"""
        
        print("\n" + "="*80)
        print("📊 BENCHMARK RESULTS")
        print("="*80)
        
        print(f"Overall Success: {'✅ SUCCESS' if result.success else '❌ FAILED'}")
        print(f"Valid Solution: {'✅ YES' if result.validity.is_valid_solution else '❌ NO'}")
        print(f"Execution Time: {duration:.2f} seconds")
        
        print(f"\n📈 SCORES:")
        print(f"   Final Score: {result.scoring.final_score:.3f}")
        print(f"   Completeness: {result.scoring.completeness:.3f}")
        print(f"   Robustness: {result.scoring.robustness:.3f}")
        print(f"   Syntactic Validity: {result.scoring.syntactic_validity:.3f}")
        if result.scoring.efficiency:
            print(f"   Efficiency: {result.scoring.efficiency:.3f}")
        
        print(f"\n🔍 PROPERTY RESULTS:")
        for prop_result in result.property_results:
            status = "✅ SATISFIED" if prop_result.satisfied else "❌ NOT SATISFIED"
            print(f"   {prop_result.property_id}: {status}")
            if prop_result.error_message:
                print(f"      Error: {prop_result.error_message}")
        
        print(f"\n⏱️  TIMING:")
        print(f"   Infrastructure: {result.metrics.infrastructure_provision_time:.2f}s")
        print(f"   Configuration: {result.metrics.config_execution_time:.2f}s")
        print(f"   Convergence: {result.metrics.convergence_time:.2f}s")
        print(f"   Evaluation: {result.metrics.evaluation_time:.2f}s")
    
    def _display_suite_results(self, metrics: Dict[str, Any], duration: float) -> None:
        """Display suite-level results"""
        
        print("\n" + "="*80)
        print("🏆 SUITE RESULTS SUMMARY")
        print("="*80)
        
        print(f"Average Score: {metrics['average_score']:.3f}")
        print(f"Valid Solution Rate: {metrics['valid_solution_rate']:.1%}")
        print(f"Property Satisfaction: {metrics['property_satisfaction_rate']:.1%}")
        print(f"Total Duration: {duration:.1f} seconds")
        
        print(f"\n📊 DETAILED METRICS:")
        print(f"   Average Completeness: {metrics['average_completeness']:.3f}")
        print(f"   Average Robustness: {metrics['average_robustness']:.3f}")
        print(f"   Average Syntactic Validity: {metrics['average_syntactic_validity']:.3f}")
        if metrics['average_efficiency']:
            print(f"   Average Efficiency: {metrics['average_efficiency']:.3f}")
    
    def _calculate_suite_metrics(self, results: List[BenchmarkResult]) -> Dict[str, Any]:
        """Calculate suite-level metrics (same as LLM runner)"""
        # Implementation similar to LLM runner
        pass
```

### 4. CLI Integration for Humans

**File**: `src/benchmark/cli.py` (addition)

```python
@click.command()
@click.argument('task_id')
@click.option('--testee-id', required=True, help='Your identifier (e.g., john_engineer_001)')
@click.option('--interactive/--no-interactive', default=True, help='Interactive mode')
def run_human_benchmark(task_id: str, testee_id: str, interactive: bool):
    """Run benchmark with human network engineer"""
    
    # Load task
    task_repo = TaskRepository()
    task = task_repo.load_task(task_id)
    
    # Run benchmark
    runner = HumanBenchmarkRunner()
    
    if interactive:
        result = runner.run_interactive_benchmark(task, testee_id)
    else:
        # Non-interactive mode - load from file
        submission_file = f"submissions/{testee_id}_{task_id}.json"
        if not os.path.exists(submission_file):
            print(f"Submission file not found: {submission_file}")
            print("Use --interactive mode or create submission file first.")
            return
        
        submission = runner.input_collector.collect_submission_from_file(submission_file)
        result = runner.controller.run(task, submission)
        runner._display_results(result, 0)

@click.command()
@click.argument('suite_id')
@click.option('--testee-id', required=True, help='Your identifier')
def run_human_suite(suite_id: str, testee_id: str):
    """Run benchmark suite with human network engineer"""
    
    # Load suite and tasks
    suite_manager = SuiteManager()
    suite = suite_manager.load_suite(suite_id)
    tasks = [suite_manager.load_task(task_id) for task_id in suite.tasks]
    
    # Run suite
    runner = HumanBenchmarkRunner()
    results = runner.run_suite_interactive(tasks, testee_id)

@click.command()
@click.argument('task_id')
@click.option('--output', default='submission_template.json', help='Output file')
def create_submission_template(task_id: str, output: str):
    """Create submission template for human to fill out"""
    
    collector = HumanInputCollector()
    collector.save_submission_template(task_id, output)
```

### 5. Human Usage Examples

#### **Interactive Mode**
```bash
# Run single task interactively
benchmark run-human-benchmark bgp_basic_001 --testee-id john_engineer_001

# Run suite interactively  
benchmark run-human-suite research_basic_v1.0 --testee-id jane_expert_001
```

#### **File-Based Mode**
```bash
# Create template
benchmark create-submission-template bgp_basic_001 --output my_solution.json

# Edit my_solution.json with your configuration

# Run with file
benchmark run-human-benchmark bgp_basic_001 --testee-id john_engineer_001 --no-interactive
```

#### **Example Submission File**
```json
{
  "task_id": "bgp_basic_001",
  "testee_id": "john_engineer_001", 
  "testee_type": "human",
  "approach": {
    "description": "Configure BGP peering between R1 and R2 with AS 65001 and 65002",
    "commands": [
      {
        "node": "R1",
        "commands": [
          "vtysh",
          "configure terminal",
          "router bgp 65001",
          "neighbor 192.168.1.2 remote-as 65002",
          "network 10.1.1.0/24",
          "exit",
          "interface eth1",
          "ip address 192.168.1.1/24",
          "no shutdown"
        ]
      },
      {
        "node": "R2",
        "commands": [
          "vtysh", 
          "configure terminal",
          "router bgp 65002",
          "neighbor 192.168.1.1 remote-as 65001",
          "network 10.2.2.0/24",
          "exit",
          "interface eth1",
          "ip address 192.168.1.2/24",
          "no shutdown"
        ]
      }
    ]
  }
}
```

### 6. Key Features for Humans

1. **User-Friendly Interface**: Clear ASCII diagrams, progress indicators, helpful hints
2. **Interactive Input**: Step-by-step command collection with validation
3. **Template Generation**: Create JSON templates for offline work
4. **Real-time Feedback**: Immediate results and scoring
5. **Educational Elements**: Command templates, common mistakes, validation hints
6. **Flexible Workflow**: Both interactive and file-based modes
7. **Same Scoring**: Humans compete on the same metrics as LLMs
8. **Comprehensive Logging**: Full audit trail of human decisions

This design allows human network engineers to participate in the benchmark using the same evaluation framework as LLMs, while providing a user-friendly interface tailored for human interaction patterns.

## Unified Benchmark System

### Shared Architecture

Both LLM and human integration share the same core components:

1. **Task Definition**: Same JSON-based task specifications
2. **Submission Format**: Unified `Submission` model with `testee_type` field
3. **Evaluation Framework**: Identical property evaluation and scoring
4. **Result Storage**: Same result format and storage system
5. **Suite Management**: Shared suite execution and aggregation

### Comparison Capabilities

The unified system enables comprehensive comparison studies:

#### **Performance Comparison**
- **Speed**: LLM response time vs human thinking time
- **Accuracy**: Property satisfaction rates
- **Efficiency**: Command count optimization
- **Consistency**: Performance across multiple tasks

#### **Capability Analysis**
- **Protocol Expertise**: BGP, OSPF, ISIS configuration skills
- **Complexity Handling**: Performance on basic vs advanced tasks
- **Error Patterns**: Common mistakes and failure modes
- **Learning Curve**: Improvement over time

#### **Research Applications**
- **Baseline Establishment**: Human performance as reference
- **AI Validation**: Verify LLM capabilities against human expertise
- **Training Data**: Generate examples from human solutions
- **Capability Mapping**: Identify AI strengths and weaknesses

### Research Use Cases

#### **Academic Studies**
```bash
# Compare GPT-4 vs Human Expert
benchmark run-suite-llm research_basic_v1.0 --llm-config openai_gpt4.json --testee-id gpt4_study_001
benchmark run-human-suite research_basic_v1.0 --testee-id human_expert_001

# Analyze results
benchmark analyze-study llm_vs_human_study --runs gpt4_study_001 human_expert_001
```

#### **Industry Evaluation**
```bash
# Evaluate multiple LLMs against human baseline
benchmark run-suite-llm research_basic_v1.0 --llm-config openai_gpt4.json --testee-id gpt4_eval
benchmark run-suite-llm research_basic_v1.0 --llm-config anthropic_claude.json --testee-id claude_eval
benchmark run-human-suite research_basic_v1.0 --testee-id senior_engineer_001

# Generate comparison report
benchmark generate-comparison-report industry_evaluation_2025
```

## Conclusion

This comprehensive integration design provides a unified framework for evaluating both Large Language Models and Human Network Engineers on network configuration tasks. The modular architecture supports multiple providers, robust error handling, and detailed analytics, making it suitable for both academic research and industry applications.

### Key Benefits

The system enables researchers and practitioners to:
- **Compare AI and Human Performance**: Direct comparison on identical tasks
- **Validate AI Capabilities**: Benchmark LLMs against human expertise
- **Generate Training Data**: Create datasets from human solutions
- **Conduct Reproducible Studies**: Standardized evaluation framework
- **Support Multiple Testee Types**: LLMs, humans, and baseline systems
- **Enable Comprehensive Analysis**: Suite-level aggregation and comparison

### System Architecture Alignment

The design aligns with the overall benchmark system architecture while providing specialized functionality for both LLM and human evaluation, ensuring:
- **Consistency**: Same evaluation criteria and scoring
- **Maintainability**: Shared components and unified interfaces
- **Extensibility**: Easy addition of new testee types
- **Research Readiness**: Comprehensive logging and analytics

This unified approach creates a powerful platform for understanding the capabilities and limitations of both artificial and human intelligence in network configuration tasks.
