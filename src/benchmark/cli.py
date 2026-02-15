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
@click.option(
    "--platform",
    type=click.Choice(TaskRepository.VALID_PLATFORMS, case_sensitive=False),
    help="Filter tasks by platform (frr, cisco_ios_xe, nokia_srl, mixed).",
)
@click.option("--verbose", is_flag=True, help="Show detailed task information.")
def list_tasks(property_type, platform, verbose):
    """List available tasks in the task repository."""
    try:
        repo = TaskRepository()
        if property_type:
            tasks = repo.load_tasks_by_property(property_type, platform=platform)
        else:
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


@main.command()
@click.argument("task_file", type=click.Path(exists=True))
@click.option("--dagent-endpoint", default=None, help="Dagent HTTP endpoint to trigger (e.g., http://localhost:8000)")
@click.option("--provider", default="openai", help="LLM provider: openai, anthropic, gemini, ollama (default: openai)")
@click.option("--model", default=None, help="Model name (e.g., gpt-4o, gemini-2.0-flash, claude-3-5-sonnet)")
@click.option("--agent-mode", type=click.Choice(["single", "multi"]), default="single", help="Agent mode: single (one agent) or multi (multi-agent)")
@click.option("--structure", type=click.Choice(["sequential", "concurrent", "debate", "group_chat"]), default="sequential", help="Multi-agent structure (only for --agent-mode multi)")
@click.option("--turn-limit", type=int, default=50, help="Max config commands (default: 50)")
@click.option("--time-limit", type=float, default=600.0, help="Max session time in seconds (default: 600)")
@click.option("--output-dir", type=click.Path(), help="Custom output directory for results")
@click.option("--wait-for-submit", is_flag=True, help="Wait for agent to call submit (manual mode)")
@click.option("--provider-host", help="Host URL for provider (e.g., http://oai:11434)")
@click.option("--mcp-host", default="localhost", help="Host address for the local MCP server (e.g., your local IP if dagent is remote)")
@click.option("--context-length", type=int, default=120000, help="Context window for Ollama models (default: 120000)")
@click.option("--verbose", "-v", is_flag=True, help="Print each agent action as it executes")
def run_task(task_file, dagent_endpoint, provider, model, provider_host, mcp_host, context_length, agent_mode, structure, turn_limit, time_limit, output_dir, wait_for_submit, verbose):
    """
    Run a single task file in multi-turn interactive mode.
    
    This command provisions the lab, starts an MCP server, and runs
    the interactive benchmark controller for a specific task.
    
    Examples:
    
        \\b
        # Run with dagent using single-agent (default)
        benchmark run-task tasks/task.json --dagent-endpoint http://localhost:8000
        
        \\b
        # Run with multi-agent sequential pattern
        benchmark run-task tasks/task.json --dagent-endpoint http://localhost:8000 --agent-mode multi --structure sequential
        
        \\b
        # Run with Gemini and multi-agent debate pattern
        benchmark run-task tasks/task.json --dagent-endpoint http://localhost:8000 --provider gemini --model gemini-2.5-pro --agent-mode multi --structure debate
        
        \\b
        # Run with custom limits
        benchmark run-task tasks/task.json --dagent-endpoint http://localhost:8000 --turn-limit 20 --time-limit 120
        
        \\b
        # Wait for external agent (manual mode)
        benchmark run-task tasks/task.json --wait-for-submit
    """
    try:
        from benchmark.interactive_controller import InteractiveBenchmarkController
        from benchmark.storage import ResultsStorage
        import asyncio

        # Load task
        with open(task_file, "r") as f:
            task_data = json.load(f)
        task = TaskDefinition(**task_data)

        # Build testee_id based on provider/model/mode/structure
        if dagent_endpoint:
            mode_suffix = "multi" if agent_mode == "multi" else "single"
            # Include structure in testee_id for multi-agent runs
            if agent_mode == "multi":
                mode_suffix = f"multi_{structure}"
            if model:
                # Use model name for clearer identification  
                testee_id = f"{provider}_{model.replace('-', '').replace('.', '')}_{mode_suffix}"
            else:
                testee_id = f"{provider}_default_{mode_suffix}"
        else:
            testee_id = "manual_agent"

        click.echo(f"\n{'='*80}")
        click.echo(f"Multi-Turn Task: {task.task_id}")
        click.echo(f"{'='*80}")
        click.echo(f"Description: {task.description}")
        click.echo(f"Nodes: {len(task.topology.nodes)}")
        click.echo(f"Properties: {len(task.intent.properties)}")
        click.echo(f"Turn Limit: {turn_limit}")
        click.echo(f"Time Limit: {time_limit}s")
        if dagent_endpoint:
            click.echo(f"Dagent Endpoint: {dagent_endpoint}")
            click.echo(f"Provider: {provider}")
            click.echo(f"Model: {model or '(default)'}")
            click.echo(f"Agent Mode: {agent_mode}")
            if agent_mode == "multi":
                click.echo(f"Structure: {structure}")
        else:
            click.echo(f"Wait for Submit: {wait_for_submit}")
        click.echo(f"{'='*80}\n")

        controller = InteractiveBenchmarkController()
        storage = ResultsStorage(base_dir=output_dir) if output_dir else ResultsStorage()

        # Run async controller
        async def run():
            return controller.run_interactive(
                task=task,
                testee_id=testee_id,
                testee_type="dagent" if dagent_endpoint else "manual",
                model_name=model,
                turn_limit=turn_limit,
                time_limit=time_limit,
                wait_for_submit=wait_for_submit,
                dagent_endpoint=dagent_endpoint,
                dagent_provider=provider,
                dagent_model=model,
                dagent_host=provider_host,
                dagent_mode=agent_mode,
                dagent_structure=structure,
                context_length=context_length,
                mcp_host=mcp_host,
                verbose=verbose,
            )
        
        result = asyncio.run(run())

        storage.save_result(result)

        # Auto-update leaderboards if they exist
        try:
            manager = storage.get_leaderboard_manager()
            if manager.list_leaderboard_ids():
                updated = manager.add_single_result(result)
                manager.save_leaderboards()
                if updated:
                    click.echo(f"\nUpdated {len(updated)} leaderboards")
        except Exception as lb_err:
            logger.debug(f"Leaderboard update skipped: {lb_err}")

        # Display summary
        click.echo(f"\n{'='*80}")
        click.echo("Multi-Turn Result")
        click.echo(f"{'='*80}")
        click.echo(f"Task: {result.task_id}")
        click.echo(f"Success: {result.success}")
        click.echo(f"Final Score: {result.scoring.final_score:.3f}")
        click.echo(f"Run ID: {result.run_id}")
        click.echo(f"Provision Time: {result.metrics.infrastructure_provision_time:.2f}s")
        click.echo(f"Total Time: {result.metrics.total_time:.2f}s")
        click.echo(f"\nResults saved to: {storage.base_dir / 'runs' / result.run_id}.json")

        if not result.success:
            sys.exit(1)

    except Exception as e:
        logger.error(f"Multi-turn benchmark failed: {e}")
        click.echo(f"Error: {e}", err=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


# ============================================================================
# Property-Based Execution Commands
# ============================================================================


@main.command()
@click.argument("property_type", type=click.Choice(TaskRepository.VALID_PROPERTY_TYPES, case_sensitive=False))
@click.option("--provider", type=click.Choice(list(PROVIDER_REGISTRY.keys())), help="LLM provider (openai, gemini, anthropic, ollama)")
@click.option("--model", help="LLM model name (uses provider default if not specified)")
@click.option("--base-url", help="Base URL for local providers (e.g. Ollama)")
@click.option("--platform", type=click.Choice(TaskRepository.VALID_PLATFORMS, case_sensitive=False), help="Filter by platform")
@click.option("--limit", type=int, help="Limit number of tasks to run")
@click.option("--output-dir", type=click.Path(), help="Custom output directory for results")
@click.option("--mode", type=click.Choice(["single", "multi"]), default="single", help="Benchmark mode: single (default) or multi-turn")
@click.option("--turn-limit", type=int, default=50, help="Max config commands for multi-turn mode (default: 50)")
@click.option("--time-limit", type=float, default=600.0, help="Max session time in seconds for multi-turn mode (default: 600)")
def run_llm(property_type, provider, model, base_url, platform, limit, output_dir, mode, turn_limit, time_limit):
    """
    Run all tasks for a property type using an LLM testee.
    
    Requires LLM provider credentials in environment variables or .env file.
    
    Examples:
    
        \\b
        # Run reachability tasks with OpenAI (default model, single-turn)
        benchmark run-llm reachability --provider openai
        
        \\b
        # Run 3 BGP tasks with specific Gemini model
        benchmark run-llm bgp_configuration --provider gemini --model gemini-2.5-pro --limit 3
        
        \\b
        # Run with multi-turn mode (interactive session)
        benchmark run-llm reachability --provider openai --mode multi --turn-limit 30
        
        \\b
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
        provider_config = {}
        if "gpt-5" in model:
            max_tokens = 10000  # GPT-5 needs higher limits for reasoning tokens
        elif "gemini" in model:
            max_tokens = 8192  # Gemini default
        elif "ollama" in provider:
            # Reasoning models (qwen3, deepseek-r1) need much higher limits
            # because they output thinking before content
            if any(reasoning_model in model for reasoning_model in ["qwen3", "deepseek-r1", "gpt-oss"]):
                max_tokens = 32768  # Very high limit for reasoning models
                provider_config["num_ctx"] = 32768  # Also increase context window
            else:
                max_tokens = 8192   # Decent default for other Ollama models
                provider_config["num_ctx"] = 16384  # Higher context for better responses
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
            provider_config=provider_config,
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
        click.echo(f"Mode: {mode}-turn" + (f" (turn_limit={turn_limit}, time_limit={time_limit}s)" if mode == "multi" else ""))

        if mode == "multi":
            # Multi-turn interactive mode
            click.echo("Multi-turn mode not yet implemented for LLM testees.")
            click.echo("Use run-dagent for multi-turn interactive sessions.")
            sys.exit(1)
        else:
            # Single-turn mode (existing behavior)
            _run_property_execution(
                property_type=property_type,
                testee=testee,
                limit=limit,
                platform=platform,
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
@click.option("--endpoint", default="http://localhost:8000", help="Dagent HTTP endpoint")
@click.option("--platform", type=click.Choice(TaskRepository.VALID_PLATFORMS, case_sensitive=False), help="Filter by platform")
@click.option("--limit", type=int, help="Limit number of tasks to run")
@click.option("--output-dir", type=click.Path(), help="Custom output directory for results")
@click.option("--mode", type=click.Choice(["single", "multi"]), default="single", help="Benchmark mode: single (default) or multi-turn")
@click.option("--turn-limit", type=int, default=50, help="Max config commands for multi-turn mode (default: 50)")
@click.option("--time-limit", type=float, default=600.0, help="Max session time in seconds for multi-turn mode (default: 600)")
@click.option("--provider", default="openai", help="LLM provider (default: openai)")
@click.option("--model", default=None, help="LLM model name")
@click.option("--agent-mode", type=click.Choice(["single", "multi"]), default="single", help="Agent mode: single (one agent) or multi (multi-agent)")
@click.option("--structure", type=click.Choice(["sequential", "concurrent", "debate", "group_chat"]), default="sequential", help="Multi-agent structure (only for --agent-mode multi)")
@click.option("--provider-host", help="Host URL for provider (e.g., http://oai:11434)")
def run_dagent(property_type, endpoint, platform, limit, output_dir, mode, turn_limit, time_limit, provider, model, provider_host, agent_mode, structure):
    """
    Run all tasks for a property type using dagent multi-agent system.
    
    Connects to a running dagent instance to generate configurations
    using multi-agent orchestration (DAG, FSM, or automated handoff).
    
    Start dagent first: uvicorn dagent.main:app --reload
    
    Examples:
    
        \b
        # Run reachability tasks with dagent (default localhost, single-turn, single-agent)
        benchmark run-dagent reachability
        
        \b
        # Run with multi-agent sequential pattern
        benchmark run-dagent bgp_configuration --agent-mode multi --structure sequential
        
        \b
        # Run with multi-turn interactive mode
        benchmark run-dagent reachability --mode multi --turn-limit 30 --time-limit 300
        
        \b
        # Run on specific platform with specific model
        benchmark run-dagent ospf_configuration --platform frr --provider gemini --model gemini-2.5-pro
    """
    try:
        click.echo(f"Using dagent at: {endpoint}")
        click.echo(f"Mode: {mode}-turn" + (f" (turn_limit={turn_limit}, time_limit={time_limit}s)" if mode == "multi" else ""))
        click.echo(f"Agent Mode: {agent_mode}" + (f" ({structure})" if agent_mode == "multi" else ""))

        if mode == "multi":
            # Multi-turn interactive mode using InteractiveBenchmarkController
            from benchmark.interactive_controller import InteractiveBenchmarkController
            from benchmark.task_repository import TaskRepository
            from benchmark.storage import ResultsStorage
            
            repo = TaskRepository()
            tasks = repo.load_tasks_by_property(property_type, platform=platform)
            if limit:
                tasks = tasks[:limit]
            
            if not tasks:
                click.echo("No tasks found for the specified criteria.")
                return
            
            controller = InteractiveBenchmarkController()
            storage = ResultsStorage(base_dir=output_dir) if output_dir else ResultsStorage()
            
            click.echo(f"\nRunning {len(tasks)} tasks in multi-turn mode")
            click.echo(f"{'='*80}\n")
            
            results = []
            for task in tasks:
                click.echo(f"Task: {task.task_id}")
                result = controller.run_interactive(
                    task=task,
                    testee_id=f"dagent_{endpoint.replace('http://', '').replace(':', '_')}_{agent_mode}",
                    testee_type="dagent",
                    turn_limit=turn_limit,
                    time_limit=time_limit,
                    wait_for_submit=False,  # Don't wait for interactive submission
                    dagent_endpoint=endpoint,
                    dagent_provider=provider,
                    dagent_model=model,
                    dagent_host=provider_host,
                    dagent_mode=agent_mode,
                    dagent_structure=structure,
                )
                storage.save_result(result)
                results.append(result)
                click.echo(f"  Score: {result.scoring.final_score:.3f} | Success: {result.success}")
            
            # Summary
            avg_score = sum(r.scoring.final_score for r in results) / len(results) if results else 0
            successes = sum(1 for r in results if r.success)
            click.echo(f"\n{'='*80}")
            click.echo(f"Multi-turn Execution Complete: {property_type}")
            click.echo(f"{'='*80}")
            click.echo(f"Total Tasks: {len(results)}")
            click.echo(f"Successful: {successes}/{len(results)}")
            click.echo(f"Average Score: {avg_score:.3f}")
        else:
            # Single-turn mode (existing behavior)
            from benchmark.testee.dagent_adapter import DagentAdapter

            testee = DagentAdapter(
                endpoint=endpoint,
                testee_id=f"dagent_{endpoint.replace('http://', '').replace(':', '_')}",
                provider=provider,
                model=model,
                agent_mode=agent_mode,
                structure=structure,
                host=provider_host,
            )

            _run_property_execution(
                property_type=property_type,
                testee=testee,
                limit=limit,
                platform=platform,
                output_dir=output_dir,
            )

    except ImportError as e:
        click.echo(f"Error: Required components not available: {e}", err=True)
        sys.exit(1)
    except ConnectionError as e:
        click.echo(f"Error: Could not connect to dagent: {e}", err=True)
        click.echo("Make sure dagent is running: uvicorn dagent.main:app --reload")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Dagent benchmark execution failed: {e}")
        click.echo(f"Error: {e}", err=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


@main.command()
@click.argument("property_type", type=click.Choice(TaskRepository.VALID_PROPERTY_TYPES, case_sensitive=False))
@click.option("--platform", type=click.Choice(TaskRepository.VALID_PLATFORMS, case_sensitive=False), help="Filter by platform")
@click.option("--limit", type=int, help="Limit number of tasks to run")
@click.option("--output-dir", type=click.Path(), help="Custom output directory for results")
def run_baseline(property_type, platform, limit, output_dir):
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
            platform=platform,
            output_dir=output_dir,
        )

    except Exception as e:
        logger.error(f"Baseline benchmark execution failed: {e}")
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.argument("property_type", type=click.Choice(TaskRepository.VALID_PROPERTY_TYPES, case_sensitive=False))
@click.option("--platform", type=click.Choice(TaskRepository.VALID_PLATFORMS, case_sensitive=False), help="Filter by platform")
@click.option("--limit", type=int, help="Limit number of tasks to run")
@click.option("--output-dir", type=click.Path(), help="Custom output directory for results")
def run_human(property_type, platform, limit, output_dir):
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
            platform=platform,
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
# Leaderboard Commands
# ============================================================================


@main.group()
def leaderboard():
    """Manage benchmark leaderboards."""
    pass


@leaderboard.command()
@click.option("--output-dir", type=click.Path(), default=None, help="Custom output directory for results")
def init(output_dir):
    """Initialize standard leaderboards.
    
    Creates 14 standard leaderboards for tracking testee performance:
    - Overall (single-turn, multi-turn)
    - Per-metric (completeness, robustness, syntactic_validity × modes)
    - Per-property (reachability, BGP, OSPF × modes)
    """
    try:
        from benchmark.analysis.leaderboard import LeaderboardManager
        
        storage = ResultsStorage(base_dir=output_dir) if output_dir else ResultsStorage()
        manager = storage.get_leaderboard_manager()
        
        if manager.list_leaderboard_ids():
            click.echo("Leaderboards already exist. Use other commands to manage them.")
            click.echo(f"Loaded {len(manager.list_leaderboard_ids())} existing leaderboards.")
            return
        
        manager.initialize_leaderboards()
        manager.save_leaderboards()
        
        click.echo(f"Initialized {len(manager.list_leaderboard_ids())} standard leaderboards.")
        click.echo(f"Saved to: {storage.leaderboards_path}")
        
    except Exception as e:
        logger.error(f"Failed to initialize leaderboards: {e}")
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@leaderboard.command("list")
@click.option("--output-dir", type=click.Path(), default=None, help="Custom output directory for results")
def list_leaderboards(output_dir):
    """List all available leaderboards."""
    try:
        storage = ResultsStorage(base_dir=output_dir) if output_dir else ResultsStorage()
        manager = storage.get_leaderboard_manager()
        
        ids = manager.list_leaderboard_ids()
        
        if not ids:
            click.echo("No leaderboards found. Run 'benchmark leaderboard init' first.")
            return
        
        click.echo(f"Available leaderboards ({len(ids)}):")
        for lb_id in sorted(ids):
            lb = manager.get_leaderboard(lb_id)
            entry_count = len(lb.entries) if lb else 0
            click.echo(f"  {lb_id}: {entry_count} entries")
            
    except Exception as e:
        logger.error(f"Failed to list leaderboards: {e}")
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@leaderboard.command()
@click.argument("leaderboard_id")
@click.option("--limit", type=int, default=10, help="Number of entries to show (default: 10)")
@click.option("--output-dir", type=click.Path(), default=None, help="Custom output directory for results")
def show(leaderboard_id, limit, output_dir):
    """Display a leaderboard's top entries.
    
    LEADERBOARD_ID: The leaderboard to display (e.g., 'overall_single_turn')
    """
    try:
        storage = ResultsStorage(base_dir=output_dir) if output_dir else ResultsStorage()
        manager = storage.get_leaderboard_manager()
        
        lb = manager.get_leaderboard(leaderboard_id)
        
        if not lb:
            click.echo(f"Leaderboard not found: {leaderboard_id}", err=True)
            click.echo("Run 'benchmark leaderboard list' to see available leaderboards.")
            sys.exit(1)
        
        click.echo(f"\n{'='*70}")
        click.echo(f"{lb.name}")
        click.echo(f"{'='*70}")
        click.echo(f"Mode: {lb.evaluation_mode} | Metric: {lb.metric_name}")
        if lb.property_type:
            click.echo(f"Property: {lb.property_type}")
        click.echo(f"Last Updated: {lb.last_updated.strftime('%Y-%m-%d %H:%M:%S')}")
        click.echo(f"{'='*70}\n")
        
        entries = lb.get_top_n(limit)
        
        if not entries:
            click.echo("No entries yet.")
            return
        
        # Header
        click.echo(f"{'Rank':<5}{'Testee':<16}{'Model':<14}{'Score':<7}{'Timestamp':<18}{'Run ID':<16}")
        click.echo("-" * 76)
        
        # Entries
        for rank, entry in enumerate(entries, 1):
            testee = entry.testee_id
            if len(testee) > 15:
                testee = testee[:12] + "..."
            
            model = entry.model_version or "-"
            if len(model) > 13:
                model = model[:10] + "..."
            
            run_id = entry.run_id
            if len(run_id) > 15:
                run_id = run_id[:12] + "..."
            
            timestamp_str = entry.timestamp.strftime("%m-%d %H:%M")
            
            click.echo(f"{rank:<5}{testee:<16}{model:<14}{entry.score:<7.3f}{timestamp_str:<18}{run_id:<16}")
            
    except Exception as e:
        logger.error(f"Failed to show leaderboard: {e}")
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@leaderboard.command()
@click.option("--run-id", required=True, help="Benchmark run ID to add")
@click.option("--output-dir", type=click.Path(), default=None, help="Custom output directory for results")
def update(run_id, output_dir):
    """Add a benchmark run to appropriate leaderboards.
    
    Updates leaderboards based on the run's evaluation mode and property types.
    """
    try:
        storage = ResultsStorage(base_dir=output_dir) if output_dir else ResultsStorage()
        manager = storage.get_leaderboard_manager()
        
        if not manager.list_leaderboard_ids():
            click.echo("No leaderboards found. Run 'benchmark leaderboard init' first.", err=True)
            sys.exit(1)
        
        # Load the benchmark run
        run_result = storage.load_benchmark_run(run_id)
        
        if not run_result:
            click.echo(f"Benchmark run not found: {run_id}", err=True)
            click.echo("Make sure the run was saved using 'save_benchmark_run()'.")
            sys.exit(1)
        
        updated = manager.add_benchmark_run(run_result)
        manager.save_leaderboards()
        
        click.echo(f"Updated {len(updated)} leaderboards for run: {run_id}")
        for lb_id in updated:
            click.echo(f"  - {lb_id}")
            
    except Exception as e:
        logger.error(f"Failed to update leaderboards: {e}")
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@leaderboard.command("update-testee")
@click.option("--testee-id", required=True, help="Testee ID to add runs for")
@click.option("--output-dir", type=click.Path(), default=None, help="Custom output directory for results")
def update_testee(testee_id, output_dir):
    """Add all runs for a testee to leaderboards.
    
    Finds all benchmark runs for the specified testee and adds them to
    the appropriate leaderboards (keeps most recent per leaderboard).
    """
    try:
        storage = ResultsStorage(base_dir=output_dir) if output_dir else ResultsStorage()
        manager = storage.get_leaderboard_manager()
        
        if not manager.list_leaderboard_ids():
            click.echo("No leaderboards found. Run 'benchmark leaderboard init' first.", err=True)
            sys.exit(1)
        
        # Find all benchmark runs for this testee
        run_ids = storage.list_benchmark_runs()
        testee_runs = []
        
        for run_id in run_ids:
            run_result = storage.load_benchmark_run(run_id)
            if run_result and run_result.testee_id == testee_id:
                testee_runs.append(run_result)
        
        if not testee_runs:
            click.echo(f"No benchmark runs found for testee: {testee_id}", err=True)
            sys.exit(1)
        
        click.echo(f"Found {len(testee_runs)} runs for testee: {testee_id}")
        
        all_updated = set()
        for run_result in testee_runs:
            updated = manager.add_benchmark_run(run_result)
            all_updated.update(updated)
        
        manager.save_leaderboards()
        
        click.echo(f"Updated {len(all_updated)} leaderboards.")
            
    except Exception as e:
        logger.error(f"Failed to update testee leaderboards: {e}")
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@leaderboard.command()
@click.option("--output", "-o", type=click.Path(), required=True, help="Output path for JSON export")
@click.option("--output-dir", type=click.Path(), default=None, help="Custom input directory for results")
def export(output, output_dir):
    """Export all leaderboards to a JSON file.
    
    Exports the complete LeaderboardCollection to the specified path.
    """
    try:
        storage = ResultsStorage(base_dir=output_dir) if output_dir else ResultsStorage()
        manager = storage.get_leaderboard_manager()
        
        if not manager.list_leaderboard_ids():
            click.echo("No leaderboards found. Run 'benchmark leaderboard init' first.", err=True)
            sys.exit(1)
        
        # Export to specified path
        manager.save_leaderboards(output)
        
        click.echo(f"Exported {len(manager.list_leaderboard_ids())} leaderboards to: {output}")
            
    except Exception as e:
        logger.error(f"Failed to export leaderboards: {e}")
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# ============================================================================
# Helper Functions
# ============================================================================


def _run_property_execution(
    property_type: str,
    testee: BaseTestee,
    limit: Optional[int],
    output_dir: Optional[str],
    platform: Optional[str] = None,
):
    """
    Internal helper to run property-based execution.
    
    Args:
        property_type: Property type to run
        testee: Testee instance to use
        limit: Optional task limit
        output_dir: Optional custom output directory
        platform: Optional platform filter
    """
    # Setup components
    repo = TaskRepository()
    controller = BenchmarkController()
    storage = ResultsStorage(base_dir=output_dir) if output_dir else ResultsStorage()
    executor = PropertyExecutor(controller, repo, storage=storage)

    platform_str = f" for {platform}" if platform else ""
    click.echo(f"\nRunning {property_type} tasks{platform_str} (limit: {limit or 'all'})")
    click.echo(f"{'='*80}\n")

    # Run tasks
    result = executor.run_property_tasks(
        property_type=property_type,
        submission_generator=testee.generate_submission,
        limit=limit,
        platform=platform,
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


@main.command()
@click.argument("session_path", type=click.Path(exists=True))
@click.option("--no-charts", is_flag=True, help="Skip chart generation")
def analyze_session(session_path, no_charts):
    """
    Analyze a benchmark study session.
    
    SESSION_PATH is the path to a session folder (e.g., results/sessions/baseline_study_xxx).
    
    Generates:
      - analysis_report.md: Comprehensive markdown report with model comparison
      - charts/: Visualization charts (unless --no-charts)
    
    Examples:
    
        benchmark analyze-session results/sessions/baseline_study_20260106_031052
    """
    try:
        from benchmark.analysis.session_analyzer import (
            generate_session_report,
            generate_session_charts,
            SessionAnalyzer,
        )
        
        click.echo(f"Analyzing session: {session_path}")
        click.echo("=" * 80)
        
        # Load session info
        analyzer = SessionAnalyzer(session_path)
        session_info = analyzer.session_info
        
        click.echo(f"Session: {session_info.get('session_name', 'unknown')}")
        click.echo(f"Models: {', '.join(session_info.get('models', []))}")
        click.echo(f"Property Types: {', '.join(session_info.get('property_types', []))}")
        click.echo("")
        
        # Generate report
        click.echo("Generating analysis report...")
        report_path = generate_session_report(session_path)
        click.echo(f"  Report: {report_path}")
        
        # Generate charts
        if not no_charts:
            click.echo("Generating comparison charts...")
            chart_paths = generate_session_charts(session_path)
            for chart_path in chart_paths:
                click.echo(f"  Chart: {chart_path}")
        
        click.echo("")
        click.echo("=" * 80)
        click.echo("Session analysis complete!")
        click.echo(f"View report: {report_path}")
        
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        logger.error(f"Session analysis failed: {e}")
        click.echo(f"Error: {e}", err=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

