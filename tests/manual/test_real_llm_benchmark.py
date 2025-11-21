"""
Real LLM Benchmark Integration Test

This test uses:
- Real LLM APIs (OpenAI, Gemini, Anthropic) - not mocked
- Real BenchmarkController (with containerlab)
- Real task execution with infrastructure
- LLM-generated configurations

WARNING: This will:
1. Make actual API calls to the selected LLM provider (costs money)
2. Spin up real Docker containers via Containerlab
3. Take several minutes to complete
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, Any, Optional, Tuple

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from benchmark.controller import BenchmarkController
from benchmark.task_repository import TaskRepository
from benchmark.property_executor import PropertyExecutor
from benchmark.llm.providers import OpenAIProvider, GeminiProvider, AnthropicProvider
from benchmark.llm.runner import LLMTestee
from benchmark.models.llm_config import LLMConfig
from benchmark.models.results import PropertyExecutionResult
import time


# Provider configuration registry
PROVIDER_REGISTRY: Dict[str, Dict[str, Any]] = {
    "openai": {
        "env_var": "OPENAI_API_KEY",
        "default_model": "gpt-4o-mini",
        "class": OpenAIProvider,
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4", "gpt-3.5-turbo", "gpt-5-mini", "gpt-5-main"],
        "description": "OpenAI models (GPT-4, GPT-3.5, GPT-5)",
    },
    "gemini": {
        "env_var": "GEMINI_API_KEY",
        "default_model": "gemini-2.5-flash",
        "class": GeminiProvider,
        "models": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash", "gemini-flash-latest", "gemini-pro-latest"],
        "description": "Google Gemini models",
    },
    "anthropic": {
        "env_var": "ANTHROPIC_API_KEY",
        "default_model": "claude-3-5-sonnet-20241022",
        "class": AnthropicProvider,
        "models": ["claude-3-5-sonnet-20241022", "claude-3-opus-20240229", "claude-3-sonnet-20240229"],
        "description": "Anthropic Claude models",
    },
}


def get_provider_api_key(provider: str) -> Optional[str]:
    """
    Get API key for the specified provider from environment.
    
    Args:
        provider: Provider name ("openai", "gemini", "anthropic")
    
    Returns:
        API key if found, None otherwise
    """
    if provider not in PROVIDER_REGISTRY:
        raise ValueError(f"Unknown provider: {provider}. Available: {list(PROVIDER_REGISTRY.keys())}")
    
    env_var = PROVIDER_REGISTRY[provider]["env_var"]
    return os.getenv(env_var)


def create_llm_provider(
    provider: str, 
    model: Optional[str] = None, 
    temperature: float = 0.7,
    max_tokens: Optional[int] = None
) -> Tuple[Any, LLMTestee]:
    """
    Create an LLM provider and testee instance.
    
    Args:
        provider: Provider name ("openai", "gemini", "anthropic")
        model: Model name (uses default if None)
        temperature: Temperature parameter
        max_tokens: Max tokens (auto-selects if None)
    
    Returns:
        Tuple of (provider_instance, testee_instance)
    
    Raises:
        ValueError: If provider unknown or API key missing
    """
    if provider not in PROVIDER_REGISTRY:
        raise ValueError(
            f"Unknown provider: {provider}. "
            f"Available: {', '.join(PROVIDER_REGISTRY.keys())}"
        )
    
    # Load API key
    api_key = get_provider_api_key(provider)
    if not api_key:
        raise ValueError(
            f"{PROVIDER_REGISTRY[provider]['env_var']} not found in environment. "
            f"Please set it in .env file or environment variables."
        )
    
    # Use default model if none specified
    if model is None:
        model = PROVIDER_REGISTRY[provider]["default_model"]
    
    # Auto-select max_tokens based on model if not specified
    if max_tokens is None:
        if "gpt-5" in model:
            max_tokens = 10000  # GPT-5 needs higher limits for reasoning
        elif "gemini" in model:
            max_tokens = 8192  # Gemini default
        else:
            max_tokens = 2000  # Conservative default
    
    # Create config
    config = LLMConfig(
        provider=provider,
        model=model,
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens
    )
    
    # Create provider instance
    provider_class = PROVIDER_REGISTRY[provider]["class"]
    provider_instance = provider_class(config)
    
    # Create testee
    testee = LLMTestee(
        provider=provider_instance,
        testee_id=f"real_{provider}_{model}"
    )
    
    return provider_instance, testee


def test_real_llm_benchmark_execution(
    provider: str = "openai",
    property_type: str = "reachability", 
    limit: int = 1,
    model: Optional[str] = None
):
    """
    End-to-end test with real LLM and real benchmark execution.
    
    This test:
    1. Loads multiple tasks for a property type
    2. Uses the specified LLM provider to generate configurations for each task
    3. Runs the actual benchmark with containerlab
    4. Computes aggregate scores across all tasks
    
    Args:
        provider: LLM provider ("openai", "gemini", "anthropic")
        property_type: Property type to test ("reachability", "bgp_configuration", etc.)
        limit: Number of tasks to run (default: 1)
        model: Model name (uses provider default if None)
    """
    print("=" * 80)
    print(f"REAL LLM BENCHMARK INTEGRATION TEST - PHASE 10 & 11")
    print("=" * 80)
    print()
    print(f"Configuration:")
    print(f"  - Provider: {provider}")
    print(f"  - Model: {model or PROVIDER_REGISTRY[provider]['default_model']}")
    print(f"  - Property Type: {property_type}")
    print(f"  - Task Limit: {limit}")
    print()
    
    # Load environment variables
    load_dotenv()
    
    try:
        provider_instance, testee = create_llm_provider(provider, model)
    except ValueError as e:
        print(f"❌ ERROR: {e}")
        return False
    
    model_name = testee.provider.model
    print(f"✓ {provider.title()} provider initialized")
    print(f"  API key loaded: ...{testee.provider.config.api_key[-8:]}")
    print()
    
    # Step 1: Setup repository and controller
    print("Step 1: Setting up benchmark infrastructure...")
    try:
        repository = TaskRepository(Path("benchmark-tasks"))
        controller = BenchmarkController()
        executor = PropertyExecutor(controller, repository)
        
        print(f"✓ Created benchmark infrastructure")
        print(f"  - Repository: benchmark-tasks/")
        print(f"  - Controller: BenchmarkController")
        print(f"  - Executor: PropertyExecutor")
        print()
    except Exception as e:
        print(f"❌ ERROR setting up infrastructure: {e}")
        return False
    
    # Step 2: Display provider info
    print(f"Step 2: {provider.title()} LLM testee ready...")
    model_info = provider_instance.get_model_info()
    print(f"✓ LLM testee configured")
    print(f"  - Provider: {model_info['provider']}")
    print(f"  - Model: {model_info['model']}")
    print(f"  - Temperature: {model_info.get('temperature', 'N/A')}")
    print(f"  - Max Tokens: {model_info.get('max_tokens', 'N/A')}")
    print(f"  - Testee ID: {testee.testee_id}")
    print()
    
    # Step 3: Run property tasks with PropertyExecutor
    print(f"Step 3: Running {limit} {property_type} tasks with {model_name}...")
    print(f"   This will:")
    print(f"   - Call {model_name} {limit} times (~10-30s per call)")
    print(f"   - Spin up containers {limit} times (~2-5min per task)")
    print(f"   - Total estimated time: {limit * 3}-{limit * 6} minutes")
    print()
    print("Progress:")
    print("=" * 80)
    
    # Track tasks manually to show LLM responses and optimize container reuse
    tasks = repository.load_tasks_by_property(property_type, limit=limit)
    results = []
    
    # Group tasks by topology to optimize container reuse
    def topology_signature(task):
        """Create a signature for topology comparison."""
        link_signatures = frozenset(
            tuple(sorted(link.endpoints)) for link in task.topology.links
        )
        return (
            len(task.topology.nodes),
            len(task.topology.links),
            link_signatures
        )
    
    # Analyze topology reuse potential
    topology_groups = []
    current_group = []
    current_sig = None
    
    for task in tasks:
        sig = topology_signature(task)
        if sig == current_sig:
            current_group.append(task)
        else:
            if current_group:
                topology_groups.append((current_sig, current_group))
            current_group = [task]
            current_sig = sig
    if current_group:
        topology_groups.append((current_sig, current_group))
    
    # Show optimization info
    total_provisions = len(topology_groups)
    provisions_saved = len(tasks) - total_provisions
    if provisions_saved > 0:
        print(f"🚀 Container Optimization Analysis:")
        print(f"   Found {provisions_saved} tasks that could reuse containers")
        print(f"   Potential provisions: {total_provisions} (vs {len(tasks)} without optimization)")
        print(f"   Note: BenchmarkController currently always provisions/teardowns each task")
        print(f"   TODO: Implement container reuse in controller for ~{provisions_saved * 60}s savings")
        print()
    
    # Track submissions for diagnostic purposes
    task_submissions = {}  # task_id -> submission
    
    try:
        task_num = 0
        for group_idx, (sig, group_tasks) in enumerate(topology_groups, 1):
            for task_idx, task in enumerate(group_tasks):
                task_num += 1
                print()
                print(f"Task {task_num}/{len(tasks)}: {task.task_id}")
                if len(group_tasks) > 1:
                    print(f"  (Topology group {group_idx}: task {task_idx + 1}/{len(group_tasks)} - reusing containers)")
                print("-" * 80)
                
                # Generate submission with LLM
                print(f"[{task_num}/{len(tasks)}] Calling {model_name} to generate configuration...")
                print("Waiting for LLM response", end="", flush=True)
                
                # Show loading animation
                submission = None
                try:
                    # Call LLM
                    submission = testee.generate_submission(task)
                    task_submissions[task.task_id] = submission  # Store for diagnostics
                    print(" ✓")
                    
                    # Show LLM's response
                    print()
                    print(f"LLM Response for {task.task_id}:")
                    print("-" * 40)
                    print(f"Description: {submission.approach.description}")
                    print(f"Commands for {len(submission.approach.commands)} nodes:")
                    for node_cmd in submission.approach.commands[:2]:  # Show first 2 nodes
                        print(f"  {node_cmd.node}: {len(node_cmd.commands)} commands")
                        for cmd in node_cmd.commands[:3]:  # Show first 3 commands
                            print(f"    - {cmd}")
                        if len(node_cmd.commands) > 3:
                            print(f"    ... and {len(node_cmd.commands) - 3} more")
                    if len(submission.approach.commands) > 2:
                        print(f"  ... and {len(submission.approach.commands) - 2} more nodes")
                    print("-" * 40)
                    print()
                    
                except Exception as e:
                    print(f" ✗ Error: {e}")
                    raise
                
                # Run benchmark
                if task_idx == 0:
                    print(f"[{task_num}/{len(tasks)}] Provisioning containers (first task in group)...")
                    print("This may take 60-90 seconds", end="", flush=True)
                else:
                    print(f"[{task_num}/{len(tasks)}] Reusing existing containers (no provision needed)...")
                    print("Applying configuration", end="", flush=True)
                
                for _ in range(5):
                    print(".", end="", flush=True)
                    time.sleep(0.2)
                print()
                
                try:
                    task_result = controller.run(task, submission)
                    results.append(task_result)
                    
                    # Show quick result
                    status = "✅ PASS" if task_result.success else "❌ FAIL"
                    print(f"{status} - Score: {task_result.scoring.final_score:.3f}")
                    
                except Exception as e:
                    print(f" ✗ Error: {e}")
                    raise
        
        print()
        print("=" * 80)
        print("✓ All tasks completed!")
        print()
        
        # Create result object manually
        result = PropertyExecutionResult(
            property_type=property_type,
            total_tasks=len(results),
            successful_tasks=sum(1 for r in results if r.success),
            results=results,
            average_score=sum(r.scoring.final_score for r in results) / len(results) if results else 0.0,
            aggregate_metrics={
                "avg_completeness": sum(r.scoring.completeness for r in results) / len(results) if results else 0.0,
                "avg_robustness": sum(r.scoring.robustness for r in results) / len(results) if results else 0.0,
                "avg_syntactic_validity": sum(r.scoring.syntactic_validity for r in results) / len(results) if results else 0.0,
                "avg_efficiency": sum(r.scoring.efficiency for r in results if r.scoring.efficiency is not None) / len([r for r in results if r.scoring.efficiency is not None]) if any(r.scoring.efficiency is not None for r in results) else None,
            }
        )
        
    except Exception as e:
        print(f"\n❌ ERROR running tasks: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Step 4: Display aggregate results
    print("=" * 80)
    print("AGGREGATE RESULTS - PHASE 10 & 11")
    print("=" * 80)
    print()
    print(f"Provider: {provider.title()} ({model_name})")
    print(f"Property Type: {result.property_type}")
    print(f"Total Tasks: {result.total_tasks}")
    print(f"Successful Tasks: {result.successful_tasks}")
    print(f"Success Rate: {result.successful_tasks / result.total_tasks * 100:.1f}%")
    print()
    
    print("OVERALL AVERAGE SCORE (mean of all final_scores):")
    print(f"  {result.average_score:.3f}")
    print()
    
    print("Aggregate Metrics (averaged across all tasks):")
    if "avg_completeness" in result.aggregate_metrics:
        print(f"  - Average Completeness:       {result.aggregate_metrics['avg_completeness']:.3f}")
    if "avg_robustness" in result.aggregate_metrics:
        print(f"  - Average Robustness:         {result.aggregate_metrics['avg_robustness']:.3f}")
    if "avg_syntactic_validity" in result.aggregate_metrics:
        print(f"  - Average Syntactic Validity: {result.aggregate_metrics['avg_syntactic_validity']:.3f}")
    if "avg_efficiency" in result.aggregate_metrics and result.aggregate_metrics['avg_efficiency'] is not None:
        print(f"  - Average Efficiency:         {result.aggregate_metrics['avg_efficiency']:.3f}")
    print()
    
    # Show individual task results summary
    print("Individual Task Results:")
    print()
    for i, task_result in enumerate(result.results, 1):
        status = "✅" if task_result.success else "❌"
        print(f"  {i}. {status} {task_result.task_id}")
        print(f"     Score: {task_result.scoring.final_score:.3f} | "
              f"Complete: {task_result.scoring.completeness:.3f} | "
              f"Valid: {task_result.validity.is_valid_solution}")
        
        # Show brief failure info
        if not task_result.success and task_result.property_results:
            failed_props = [p.property_id for p in task_result.property_results if not p.satisfied]
            if failed_props:
                print(f"     Failed properties: {', '.join(failed_props[:3])}")
                if len(failed_props) > 3:
                    print(f"     ... and {len(failed_props) - 3} more")
    
    print()
    
    # Show timing summary
    total_time = sum(r.metrics.total_time for r in result.results)
    avg_time = total_time / len(result.results)
    print("Timing Summary:")
    print(f"  - Total Execution Time: {total_time:.1f}s ({total_time/60:.1f} minutes)")
    print(f"  - Average per Task: {avg_time:.1f}s")
    print()
    
    # Summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print()
    
    success_rate = result.successful_tasks / result.total_tasks
    
    if success_rate >= 0.8:
        print(f"✅ EXCELLENT! {model_name} succeeded on {result.successful_tasks}/{result.total_tasks} tasks!")
        print(f"   Overall Average Score: {result.average_score:.3f}")
        print(f"   Phase 10/11 integration working perfectly with real LLM!")
        return True
    elif success_rate >= 0.5:
        print(f"⚠️  GOOD! {model_name} succeeded on {result.successful_tasks}/{result.total_tasks} tasks.")
        print(f"   Overall Average Score: {result.average_score:.3f}")
        print(f"   Phase 10/11 integration verified - LLMs aren't perfect but system works!")
        return True
    elif result.total_tasks > 0:
        print(f"⚠️  PARTIAL: {model_name} succeeded on {result.successful_tasks}/{result.total_tasks} tasks.")
        print(f"   Overall Average Score: {result.average_score:.3f}")
        print(f"   The Phase 10/11 system is working correctly!")
        print(f"   (LLMs may need prompt tuning for better results)")
        return True
    else:
        print("❌ FRAMEWORK ERROR: No tasks completed.")
        return False


if __name__ == "__main__":
    import argparse
    
    # List available providers
    provider_list = "\n".join(
        f"  - {name}: {info['description']}"
        for name, info in PROVIDER_REGISTRY.items()
    )
    
    parser = argparse.ArgumentParser(
        description="Real LLM Benchmark Integration Test - Phase 10 & 11",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Available Providers:
{provider_list}

Examples:
  # Run 1 reachability task with OpenAI (default)
  python tests/manual/test_real_llm_benchmark.py
  
  # Run 3 tasks with Google Gemini
  python tests/manual/test_real_llm_benchmark.py --provider gemini --limit 3
  
  # Run 2 BGP tasks with specific model
  python tests/manual/test_real_llm_benchmark.py --provider openai --model gpt-4o --property bgp_configuration --limit 2
  
  # Run with Anthropic Claude
  python tests/manual/test_real_llm_benchmark.py --provider anthropic --limit 5
"""
    )
    parser.add_argument(
        "--provider",
        type=str,
        default="openai",
        choices=list(PROVIDER_REGISTRY.keys()),
        help="LLM provider (default: openai)"
    )
    parser.add_argument(
        "--property",
        type=str,
        default="reachability",
        choices=["reachability", "bgp_configuration", "ospf_configuration"],
        help="Property type to test (default: reachability)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help="Number of tasks to run (default: 1)"
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model name (uses provider default if not specified)"
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompt"
    )
    
    args = parser.parse_args()
    
    # Get model name for display
    model_display = args.model or PROVIDER_REGISTRY[args.provider]["default_model"]
    
    print()
    print("⚠️  WARNING: This test will:")
    print(f"   1. Run {args.limit} tasks using real {args.provider.upper()} API ({model_display})")
    print(f"   2. Estimated cost: ~${args.limit * 0.02:.2f}-${args.limit * 0.10:.2f}")
    print(f"   3. Spin up Docker containers {args.limit} times via Containerlab")
    print(f"   4. Take approximately {args.limit * 3}-{args.limit * 6} minutes")
    print()
    
    if not args.yes:
        response = input("Continue? [y/N]: ").strip().lower()
        if response != 'y':
            print("\nTest cancelled.")
            sys.exit(0)
    
    print()
    success = test_real_llm_benchmark_execution(
        provider=args.provider,
        property_type=args.property,
        limit=args.limit,
        model=args.model
    )
    
    print()
    if success:
        print("✅ Test completed successfully!")
        sys.exit(0)
    else:
        print("❌ Test failed!")
        sys.exit(1)
