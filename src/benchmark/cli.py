"""
Command-line interface for the Network Configuration Benchmark.

Provides commands for running benchmarks with different testee types:
- LLM testees (OpenAI, Gemini, Anthropic)
- Human testees (interactive or pre-written JSON)
- Baseline testees (empty configurations)

Supports both single-task and property-based batch execution.
"""
import click
import logging
import json
import os
import sys
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

from benchmark.controller import BenchmarkController
from benchmark.storage import ResultsStorage
from benchmark.task_repository import TaskRepository
from benchmark.property_executor import PropertyExecutor
from benchmark.presenter import TaskPresenter
from benchmark.testee.base import BaseTestee
from benchmark.testee.human import HumanJsonTestee, HumanInteractiveTestee
from benchmark.testee.baseline import BaselineTestee
from benchmark.models.task import TaskDefinition
from benchmark.models.submission import Submission
from benchmark.models.results import BenchmarkResult

logger = logging.getLogger(__name__)

# Provider registry for LLM testees
PROVIDER_REGISTRY = {
    "openai": {
        "env_var": "OPENAI_API_KEY",
        "default_model": "gpt-4o-mini",
        "description": "OpenAI models (GPT-4, GPT-3.5, GPT-5)",
    },
    "gemini": {
        "env_var": "GEMINI_API_KEY",
        "default_model": "gemini-2.5-flash",
        "description": "Google Gemini models",
    },
    "anthropic": {
        "env_var": "ANTHROPIC_API_KEY",
        "default_model": "claude-3-5-sonnet-20241022",
        "description": "Anthropic Claude models",
    },
    "ollama": {
        "env_var": None,  # No API key needed usually
        "default_model": "llama3",
        "description": "Ollama local models",
    },
}


@click.group()
@click.option("-v", "--verbose", is_flag=True, help="Enable detailed logging")
@click.option("-q", "--quiet", is_flag=True, help="Suppress non-error output")
def main(verbose, quiet):
    """Network Configuration Benchmark CLI."""
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    elif quiet:
        logging.basicConfig(level=logging.ERROR)
    else:
        logging.basicConfig(level=logging.INFO)


# ============================================================================
# Task Management Commands
# ============================================================================


@main.command()
@click.option(
    "--property-type",
    type=click.Choice(TaskRepository.VALID_PROPERTY_TYPES, case_sensitive=False),
    help="Filter tasks by property type.",
)
@click.option("--verbose", is_flag=True, help="Show detailed task information.")
def list_tasks(property_type, verbose):
    """List available tasks in the task repository."""
    try:
        repo = TaskRepository()
        tasks = repo.list_tasks(property_type=property_type)
        if not tasks:
            click.echo("No tasks found.")
            return

        click.echo(f"Found {len(tasks)} tasks:")
        for task in tasks:
            if verbose:
                click.echo(f"  ID: {task.task_id}")
                click.echo(f"    Description: {task.description}")
                click.echo(f"    Platform: {task.platform.value}")
                click.echo(
                    f"    Property Type: {task.intent.properties[0].type if task.intent.properties else 'N/A'}"
                )
            else:
                click.echo(
                    f"- {task.task_id} ({task.intent.properties[0].type if task.intent.properties else 'N/A'}): {task.description}"
                )
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        click.echo(
            f"Error: An unexpected error occurred. Check logs for details.", err=True
        )
        sys.exit(1)


@main.command()
@click.argument("task_id")
def show_task(task_id):
    """Display detailed information about a specific task."""
    try:
        repo = TaskRepository()
        task = repo.load_task(task_id)

        presenter = TaskPresenter()
        task_text = presenter.present_task_text(task)

        click.echo(task_text)

    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        click.echo(
            f"Error: An unexpected error occurred. Check logs for details.", err=True
        )
        sys.exit(1)


@main.command()
@click.option("--task-id", help="Filter by task ID.")
@click.option("--limit", type=int, default=10, help="Number of recent runs to show.")
def list_runs(task_id, limit):
    """List recent benchmark runs."""
    try:
        storage = ResultsStorage()
        runs = storage.list_recent_runs(limit=limit, task_id=task_id)

        if not runs:
            click.echo("No runs found.")
            return

        click.echo(f"Recent runs (limit={limit}):")
        for run_info in runs:
            click.echo(
                f"- {run_info['run_id']}: {run_info['task_id']} "
                f"(score: {run_info['score']:.3f}, "
                f"time: {run_info['timestamp']})"
            )

    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        click.echo(
            f"Error: An unexpected error occurred. Check logs for details.", err=True
        )
        sys.exit(1)


@main.command()
@click.argument("run_id")
@click.option("--verbose", is_flag=True, help="Show detailed result information.")
def show_result(run_id, verbose):
    """Display detailed results for a specific run."""
    try:
        storage = ResultsStorage()
        result = storage.load_result(run_id)

        click.echo(f"\nRun ID: {result.run_id}")
        click.echo(f"Task ID: {result.task_id}")
        click.echo(f"Testee: {result.testee_id} ({result.testee_type})")
        click.echo(f"Timestamp: {result.timestamp}")
        click.echo(f"\nSuccess: {result.success}")
        click.echo(f"Final Score: {result.scoring.final_score:.3f}")
        click.echo(f"Completeness: {result.scoring.completeness:.3f}")
        click.echo(f"Robustness: {result.scoring.robustness:.3f}")
        click.echo(f"Syntactic Validity: {result.scoring.syntactic_validity:.3f}")

        if result.scoring.efficiency is not None:
            click.echo(f"Efficiency: {result.scoring.efficiency:.3f}")

        if verbose and result.property_results:
            click.echo(f"\nProperty Results ({len(result.property_results)}):")
            for prop in result.property_results:
                status = "✓" if prop.satisfied else "✗"
                click.echo(f"  {status} {prop.property_id}")
                if prop.error_message:
                    click.echo(f"    Error: {prop.error_message}")

    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        click.echo(
            f"Error: An unexpected error occurred. Check logs for details.", err=True
        )
        sys.exit(1)


# ============================================================================
# Single Task Execution (for specific task + submission files)
# ============================================================================


@main.command()
@click.argument("task_file", type=click.Path(exists=True))
@click.argument("submission_file", type=click.Path(exists=True))
@click.option("--verbose", is_flag=True, help="Enable detailed logging.")
@click.option("--no-teardown", is_flag=True, help="Keep containers running (debugging).")
@click.option("--output-dir", type=click.Path(), help="Custom output directory for results.")
def run(task_file, submission_file, verbose, no_teardown, output_dir):
    """
    Run a single benchmark task with a pre-written submission file.
    
    This is useful for testing individual submissions or debugging.
    For batch execution, use run-property, run-llm, or run-baseline.
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        # Load task
        with open(task_file, "r") as f:
            task_data = json.load(f)
        task = TaskDefinition(**task_data)

        # Load submission
        testee = HumanJsonTestee(submission_file)
        submission = testee.generate_submission(task)

        # Run benchmark
        controller = BenchmarkController()
        result = controller.run(task, submission)

        # Save result
        storage = ResultsStorage(base_dir=output_dir) if output_dir else ResultsStorage()
        storage.save_result(result)

        # Display summary
        click.echo(f"\n{'='*80}")
        click.echo("Benchmark Result")
        click.echo(f"{'='*80}")
        click.echo(f"Task: {result.task_id}")
        click.echo(f"Success: {result.success}")
        click.echo(f"Final Score: {result.scoring.final_score:.3f}")
        click.echo(f"Run ID: {result.run_id}")
        click.echo(f"\nResults saved to: {storage.base_dir / 'runs' / result.run_id}.json")

        if not result.success:
            sys.exit(1)

    except Exception as e:
        logger.error(f"Benchmark execution failed: {e}")
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# ============================================================================
# Property-Based Execution Commands
# ============================================================================


@main.command()
@click.argument("property_type", type=click.Choice(TaskRepository.VALID_PROPERTY_TYPES, case_sensitive=False))
@click.option("--provider", type=click.Choice(list(PROVIDER_REGISTRY.keys())), help="LLM provider (openai, gemini, anthropic, ollama)")
@click.option("--model", help="LLM model name (uses provider default if not specified)")
@click.option("--base-url", help="Base URL for local providers (e.g. Ollama)")
@click.option("--limit", type=int, help="Limit number of tasks to run")
@click.option("--output-dir", type=click.Path(), help="Custom output directory for results")
def run_llm(property_type, provider, model, base_url, limit, output_dir):
    """
    Run all tasks for a property type using an LLM testee.
    
    Requires LLM provider credentials in environment variables or .env file.
    
    Examples:
    
        \b
        # Run reachability tasks with OpenAI (default model)
        benchmark run-llm reachability --provider openai
        
        \b
        # Run 3 BGP tasks with specific Gemini model
        benchmark run-llm bgp_configuration --provider gemini --model gemini-2.5-pro --limit 3
        
        \b
        # Run with Ollama on custom host
        benchmark run-llm reachability --provider ollama --base-url http://myserver:11434
    """
    # Load environment variables
    load_dotenv()

    if not provider:
        click.echo("Error: --provider is required for run-llm command.", err=True)
        click.echo("Available providers: openai, gemini, anthropic, ollama")
        sys.exit(1)

    try:
        # Import LLM components
        from benchmark.llm.providers import OpenAIProvider, GeminiProvider, AnthropicProvider, OllamaProvider
        from benchmark.llm.runner import LLMTestee
        from benchmark.models.llm_config import LLMConfig

        # Get API key
        env_var = PROVIDER_REGISTRY[provider]["env_var"]
        api_key = None
        if env_var:
            api_key = os.getenv(env_var)
            if not api_key:
                click.echo(f"Error: {env_var} not found in environment.", err=True)
                click.echo("Please set it in .env file or environment variables.")
                sys.exit(1)

        # Get base_url if not provided
        if not base_url and provider == "ollama":
             base_url = os.getenv("OLLAMA_BASE_URL")

        # Use default model if not specified
        if model is None:
            model = PROVIDER_REGISTRY[provider]["default_model"]

        # Auto-select max_tokens based on model
        if "gpt-5" in model:
            max_tokens = 10000  # GPT-5 needs higher limits for reasoning tokens
        elif "gemini" in model:
            max_tokens = 8192  # Gemini default
        elif "ollama" in provider:
            max_tokens = 4096   # Decent default for Llama3/Mistral
        else:
            max_tokens = 2000  # Conservative default

        # Create LLM provider
        config = LLMConfig(
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=0.7,
            max_tokens=max_tokens,
        )

        provider_classes = {
            "openai": OpenAIProvider,
            "gemini": GeminiProvider,
            "anthropic": AnthropicProvider,
            "ollama": OllamaProvider,
        }
        provider_instance = provider_classes[provider](config)
        testee = LLMTestee(provider=provider_instance, testee_id=f"llm_{provider}_{model}")

        click.echo(f"Using LLM: {provider} ({model})")

        # Run property tasks
        _run_property_execution(
            property_type=property_type,
            testee=testee,
            limit=limit,
            output_dir=output_dir,
        )

    except ImportError as e:
        click.echo(f"Error: LLM components not available: {e}", err=True)
        click.echo("Make sure LLM dependencies are installed.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"LLM benchmark execution failed: {e}")
        click.echo(f"Error: {e}", err=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


@main.command()
@click.argument("property_type", type=click.Choice(TaskRepository.VALID_PROPERTY_TYPES, case_sensitive=False))
@click.option("--limit", type=int, help="Limit number of tasks to run")
@click.option("--output-dir", type=click.Path(), help="Custom output directory for results")
def run_baseline(property_type, limit, output_dir):
    """
    Run all tasks for a property type using baseline (empty) configurations.
    
    Useful for establishing a performance baseline.
    
    Examples:
    
        \b
        # Run all reachability tasks with baseline
        benchmark run-baseline reachability
        
        \b
        # Run 5 BGP tasks with baseline
        benchmark run-baseline bgp_configuration --limit 5
    """
    try:
        testee = BaselineTestee()
        click.echo("Using baseline testee (empty configurations)")

        _run_property_execution(
            property_type=property_type,
            testee=testee,
            limit=limit,
            output_dir=output_dir,
        )

    except Exception as e:
        logger.error(f"Baseline benchmark execution failed: {e}")
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.argument("property_type", type=click.Choice(TaskRepository.VALID_PROPERTY_TYPES, case_sensitive=False))
@click.option("--limit", type=int, help="Limit number of tasks to run")
@click.option("--output-dir", type=click.Path(), help="Custom output directory for results")
def run_human(property_type, limit, output_dir):
    """
    Run tasks interactively with human testee.
    
    For each task, displays task details and prompts for submission file path.
    
    Examples:
    
        \b
        # Run reachability tasks interactively
        benchmark run-human reachability
        
        \b
        # Run 3 BGP tasks interactively
        benchmark run-human bgp_configuration --limit 3
    """
    try:
        testee = HumanInteractiveTestee()
        click.echo("Interactive human testee mode")
        click.echo("You will be prompted for submission files for each task.\n")

        _run_property_execution(
            property_type=property_type,
            testee=testee,
            limit=limit,
            output_dir=output_dir,
        )

    except KeyboardInterrupt:
        click.echo("\n\nBenchmark interrupted by user.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Human benchmark execution failed: {e}")
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option("--provider", type=click.Choice(list(PROVIDER_REGISTRY.keys())), help="LLM provider for LLM mode")
@click.option("--model", help="LLM model name")
@click.option("--base-url", help="Base URL for local providers (e.g. Ollama)")
@click.option("--testee-type", type=click.Choice(["llm", "baseline", "human"]), default="baseline", help="Testee type to use")
@click.option("--limit", type=int, help="Limit number of tasks per property type")
@click.option("--output-dir", type=click.Path(), help="Custom output directory for results")
def run_all(provider, model, base_url, testee_type, limit, output_dir):
    """
    Run tasks across ALL property types with a testee.
    
    Examples:
    
        \b
        # Run all tasks with baseline
        benchmark run-all --testee-type baseline
        
        \b
        # Run 3 tasks per property with OpenAI
        benchmark run-all --testee-type llm --provider openai --limit 3
    """
    load_dotenv()

    try:
        # Create testee based on type
        if testee_type == "llm":
            if not provider:
                click.echo("Error: --provider is required for LLM testee type.", err=True)
                sys.exit(1)

            from benchmark.llm.providers import OpenAIProvider, GeminiProvider, AnthropicProvider, OllamaProvider
            from benchmark.llm.runner import LLMTestee
            from benchmark.models.llm_config import LLMConfig

            env_var = PROVIDER_REGISTRY[provider]["env_var"]
            api_key = None
            if env_var:
                api_key = os.getenv(env_var)
                if not api_key:
                    click.echo(f"Error: {env_var} not found in environment.", err=True)
                    sys.exit(1)
            
            # Get base_url if not provided
            if not base_url and provider == "ollama":
                 base_url = os.getenv("OLLAMA_BASE_URL")

            if model is None:
                model = PROVIDER_REGISTRY[provider]["default_model"]

            # Auto-select max_tokens based on model
            if "gpt-5" in model:
                max_tokens = 10000  # GPT-5 needs higher limits for reasoning tokens
            elif "gemini" in model:
                max_tokens = 8192  # Gemini default
            elif "ollama" in provider:
                max_tokens = 4096
            else:
                max_tokens = 2000  # Conservative default

            config = LLMConfig(
                provider=provider,
                model=model,
                api_key=api_key,
                base_url=base_url,
                temperature=0.7,
                max_tokens=max_tokens,
            )

            provider_classes = {
                "openai": OpenAIProvider,
                "gemini": GeminiProvider,
                "anthropic": AnthropicProvider,
                "ollama": OllamaProvider,
            }
            provider_instance = provider_classes[provider](config)
            testee = LLMTestee(provider=provider_instance, testee_id=f"llm_{provider}_{model}")
            click.echo(f"Using LLM testee: {provider} ({model})")

        elif testee_type == "baseline":
            testee = BaselineTestee()
            click.echo("Using baseline testee")

        elif testee_type == "human":
            testee = HumanInteractiveTestee()
            click.echo("Using interactive human testee")

        # Run all property types
        repo = TaskRepository()
        controller = BenchmarkController()
        storage = ResultsStorage(base_dir=output_dir) if output_dir else ResultsStorage()
        executor = PropertyExecutor(controller, repo, storage=storage)

        click.echo(f"\nRunning benchmark across all property types (limit per type: {limit or 'all'})")
        click.echo(f"{'='*80}\n")

        result = executor.run_all_tasks(
            submission_generator=testee.generate_submission,
            limit=limit,
        )

        # Save result
        storage.save_benchmark_run(result)

        # Display summary
        click.echo(f"\n{'='*80}")
        click.echo("Benchmark Run Complete")
        click.echo(f"{'='*80}")
        click.echo(f"Run ID: {result.run_id}")
        click.echo(f"Testee: {result.testee_id} ({result.testee_type})")
        click.echo(f"Total Tasks: {result.total_tasks}")
        click.echo(f"Overall Average Score: {result.overall_average_score:.3f}")
        click.echo(f"Execution Time: {result.execution_time_seconds:.1f}s")
        click.echo(f"\nProperty Type Results:")
        for prop_type, prop_result in result.property_results.items():
            click.echo(
                f"  {prop_type}: {prop_result.successful_tasks}/{prop_result.total_tasks} "
                f"(avg: {prop_result.average_score:.3f})"
            )

    except KeyboardInterrupt:
        click.echo("\n\nBenchmark interrupted by user.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Benchmark run failed: {e}")
        click.echo(f"Error: {e}", err=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


# ============================================================================
# Helper Functions
# ============================================================================


def _run_property_execution(
    property_type: str,
    testee: BaseTestee,
    limit: Optional[int],
    output_dir: Optional[str],
):
    """
    Internal helper to run property-based execution.
    
    Args:
        property_type: Property type to run
        testee: Testee instance to use
        limit: Optional task limit
        output_dir: Optional custom output directory
    """
    # Setup components
    repo = TaskRepository()
    controller = BenchmarkController()
    storage = ResultsStorage(base_dir=output_dir) if output_dir else ResultsStorage()
    executor = PropertyExecutor(controller, repo, storage=storage)

    click.echo(f"\nRunning {property_type} tasks (limit: {limit or 'all'})")
    click.echo(f"{'='*80}\n")

    # Run tasks
    result = executor.run_property_tasks(
        property_type=property_type,
        submission_generator=testee.generate_submission,
        limit=limit,
    )

    # Save result
    storage.save_property_result(result)

    # Display summary
    click.echo(f"\n{'='*80}")
    click.echo(f"Property Execution Complete: {property_type}")
    click.echo(f"{'='*80}")
    click.echo(f"Total Tasks: {result.total_tasks}")
    click.echo(f"Successful Tasks: {result.successful_tasks}")
    click.echo(f"Average Score: {result.average_score:.3f}")
    click.echo(f"\nAggregate Metrics:")
    for metric, value in result.aggregate_metrics.items():
        if value is not None:
            click.echo(f"  {metric}: {value:.3f}")

    if result.successful_tasks < result.total_tasks:
        click.echo(f"\nWarning: {result.total_tasks - result.successful_tasks} tasks failed.")


# ============================================================================
# Analysis Commands
# ============================================================================


@main.command()
@click.argument("identifier")
@click.option("--output-dir", type=click.Path(), default="results/analysis", help="Output directory for analysis results")
@click.option("--format", type=click.Choice(["json", "csv", "all"]), default="all", help="Export format")
@click.option("--batch-name", type=str, default=None, help="Batch name for organizing results in a subfolder")
def analyze(identifier, output_dir, format, batch_name):
    """
    Analyze benchmark results with automatic identifier detection.
    
    IDENTIFIER can be:
      - Testee ID (e.g., "gpt-4", "baseline") - analyze single testee
      - Property type (e.g., "reachability") - analyze property across testees
      - Comparison (e.g., "gpt-4,claude,baseline") - compare multiple testees
    
    Examples:
    
        benchmark analyze gpt-4
        benchmark analyze reachability
        benchmark analyze gpt-4,claude,baseline
    """
    try:
        from benchmark.analysis.identifier import IdentifierDetector
        from benchmark.analysis.analyzer import BenchmarkAnalyzer
        from benchmark.analysis.exporter import AnalysisExporter
        from benchmark.models.analysis import AnalysisResult
        from datetime import datetime
        from pathlib import Path
        
        # Setup
        storage = ResultsStorage()
        detector = IdentifierDetector(storage)
        analyzer = BenchmarkAnalyzer(storage)
        exporter = AnalysisExporter()
        
        click.echo(f"Analyzing: {identifier}")
        click.echo(f"{'='*80}\n")
        
        # Detect identifier type
        spec = detector.detect(identifier)
        click.echo(f"Analysis type: {spec.analysis_type}")
        
        # Generate analysis ID
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Perform analysis based on type
        if spec.analysis_type == "testee":
            click.echo(f"Testee: {spec.testee_id}\n")
            
            testee_analysis = analyzer.analyze_testee(spec.testee_id)
            
            analysis_id = f"testee_{spec.testee_id}_{timestamp}"
            result = AnalysisResult(
                analysis_id=analysis_id,
                analysis_type="testee",
                timestamp=datetime.now(),
                testee_analysis=testee_analysis,
                comparison_analysis=None,
                property_analysis=None,
                export_paths={},
            )
            
            # Display summary
            click.echo(f"Total runs: {testee_analysis.total_runs}")
            click.echo(f"Overall score: {testee_analysis.aggregate_scores.final_score:.3f}")
            click.echo(f"Completeness: {testee_analysis.aggregate_scores.completeness:.3f}")
            click.echo(f"Properties analyzed: {len(testee_analysis.property_breakdown)}")
            
        elif spec.analysis_type == "comparison":
            click.echo(f"Comparing testees: {', '.join(spec.testees)}\n")
            
            comparison_analysis = analyzer.analyze_comparison(spec.testees)
            
            analysis_id = f"comparison_{'_'.join(spec.testees)}_{timestamp}"
            result = AnalysisResult(
                analysis_id=analysis_id,
                analysis_type="comparison",
                timestamp=datetime.now(),
                testee_analysis=None,
                comparison_analysis=comparison_analysis,
                property_analysis=None,
                export_paths={},
            )
            
            # Display summary
            click.echo("Testee scores:")
            for testee_id, scores in comparison_analysis.score_comparison.testee_scores.items():
                click.echo(f"  {testee_id}: {scores.final_score:.3f}")
            
            click.echo(f"\nStatistical test: {comparison_analysis.statistical_tests.test_type}")
            if comparison_analysis.statistical_tests.test_type == "t-test":
                ttest = comparison_analysis.statistical_tests.ttest_result
                click.echo(f"  p-value: {ttest.p_value:.4f}")
                click.echo(f"  effect size: {ttest.effect_size:.3f}")
            elif comparison_analysis.statistical_tests.test_type == "anova":
                anova = comparison_analysis.statistical_tests.anova_result
                click.echo(f"  p-value: {anova.p_value:.4f}")
                click.echo(f"  F-statistic: {anova.f_statistic:.3f}")
            
        elif spec.analysis_type == "property":
            click.echo(f"Property type: {spec.property_type}\n")
            
            property_analysis = analyzer.analyze_property_type(spec.property_type)
            
            analysis_id = f"property_{spec.property_type}_{timestamp}"
            result = AnalysisResult(
                analysis_id=analysis_id,
                analysis_type="property",
                timestamp=datetime.now(),
                testee_analysis=None,
                comparison_analysis=None,
                property_analysis=property_analysis,
                export_paths={},
            )
            
            # Display summary
            click.echo(f"Total runs: {property_analysis.total_runs}")
            click.echo(f"Testees analyzed: {len(property_analysis.testee_breakdown)}")
            click.echo(f"Tasks: {len(property_analysis.task_difficulty)}")
            
            # Show testee scores
            click.echo("\nTestee performance:")
            for testee_id, stats in property_analysis.testee_breakdown.items():
                click.echo(f"  {testee_id}: {stats.aggregate_scores.final_score:.3f} ({stats.successful_tasks}/{stats.total_tasks} successful)")
        
        else:
            click.echo(f"Error: Unknown analysis type: {spec.analysis_type}", err=True)
            sys.exit(1)
        
        # Export results
        output_path = Path(output_dir)
        
        # Create batch subfolder if batch_name is provided
        if batch_name:
            output_path = output_path / batch_name
            output_path.mkdir(parents=True, exist_ok=True)
        
        click.echo(f"\n{'='*80}")
        click.echo("Exporting results...")
        
        export_paths = {}
        
        if format in ["json", "all"]:
            json_path = exporter.export_json(result, output_path)
            export_paths["json"] = json_path
            click.echo(f"JSON: {json_path}")
        
        if format in ["csv", "all"]:
            csv_path = exporter.export_csv_summary(result, output_path)
            export_paths["csv"] = csv_path
            click.echo(f"CSV: {csv_path}")
        
        # Update result with export paths
        result.export_paths = export_paths
        
        click.echo(f"\nAnalysis complete: {analysis_id}")
        
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        click.echo(f"Error: {e}", err=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
