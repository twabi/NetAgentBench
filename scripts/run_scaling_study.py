#!/usr/bin/env python3
"""
Scaling Study Test Harness

Runs benchmark tasks across various node counts and collects performance,
resource usage, and reliability metrics.

Usage:
    python scripts/run_scaling_study.py --node-counts 2,3,4,5 --property reachability --platform frr
"""
import argparse
import json
import logging
import subprocess
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import psutil

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ResourceMonitor:
    """Monitor system resources during benchmark execution."""
    
    def __init__(self):
        self.start_time = None
        self.measurements = []
        self.process = psutil.Process()  # Track this Python process
    
    def start(self):
        """Start monitoring."""
        self.start_time = time.time()
        self.measurements = []
        logger.info("Resource monitoring started")
    
    def sample(self):
        """Take a resource measurement sample."""
        # Get memory info for the benchmark process
        mem_info = self.process.memory_info()
        
        # Also get overall system memory
        sys_mem = psutil.virtual_memory()
        
        # CPU percent for this process
        cpu = self.process.cpu_percent(interval=1)
        
        sample = {
            "timestamp": time.time() - self.start_time,
            "benchmark_memory_mb": mem_info.rss / (1024 * 1024),  # Process RSS
            "system_memory_percent": sys_mem.percent,
            "cpu_percent": cpu,
        }
        self.measurements.append(sample)
        return sample
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics."""
        if not self.measurements:
            return {}
        
        memory_values = [m["benchmark_memory_mb"] for m in self.measurements]
        cpu_values = [m["cpu_percent"] for m in self.measurements]
        
        return {
            "duration_sec": time.time() - self.start_time if self.start_time else 0,
            "benchmark_memory_avg_mb": sum(memory_values) / len(memory_values),
            "benchmark_memory_peak_mb": max(memory_values),
            "benchmark_memory_min_mb": min(memory_values),
            "cpu_avg_percent": sum(cpu_values) / len(cpu_values),
            "cpu_peak_percent": max(cpu_values),
            "sample_count": len(self.measurements),
        }


class ScalingTestRunner:
    """Run scaling tests and collect metrics."""
    
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results = []
    
    def run_test(
        self,
        property_type: str,
        platform: str,
        limit: int,
        ollama_endpoint: Optional[str] = None,
        ollama_model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run a single scaling test.
        
        Args:
            property_type: Property type to test
            platform: Platform to test on
            limit: Number of tasks to run
            ollama_endpoint: Ollama endpoint URL
            ollama_model: Ollama model name
        
        Returns:
            Dictionary with test results and metrics
        """
        logger.info(f"Running test: {property_type} on {platform} (limit={limit})")
        
        test_result = {
            "property_type": property_type,
            "platform": platform,
            "limit": limit,
            "timestamp": datetime.now().isoformat(),
            "success": False,
            "metrics": {},
            "errors": [],
        }
        
        # Build command based on testee type
        if ollama_endpoint and ollama_model:
            # Use run-llm with Ollama
            cmd = [
                "poetry", "run", "python", "-m", "benchmark.cli",
                "run-llm", property_type,
                "--platform", platform,
                "--limit", str(limit),
                "--provider", "ollama",
                "--model", ollama_model,
                "--base-url", ollama_endpoint,
                "--output-dir", str(self.output_dir / f"run_{property_type}_{platform}_{limit}"),
            ]
        else:
            # Use run-baseline (no LLM)
            cmd = [
                "poetry", "run", "python", "-m", "benchmark.cli",
                "run-baseline", property_type,
                "--platform", platform,
                "--limit", str(limit),
                "--output-dir", str(self.output_dir / f"run_{property_type}_{platform}_{limit}"),
            ]
        
        # Start resource monitoring
        monitor = ResourceMonitor()
        monitor.start()
        
        # Run benchmark
        start_time = time.time()
        try:
            # Sample resources before
            monitor.sample()
            
            result = subprocess.run(
                cmd,
                cwd="/home/grimm/python_projects/benchmark",
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout
            )
            
            # Sample resources after
            monitor.sample()
            
            execution_time = time.time() - start_time
            
            test_result["success"] = result.returncode == 0
            test_result["execution_time_sec"] = execution_time
            test_result["stdout"] = result.stdout[-1000:]  # Last 1000 chars
            test_result["stderr"] = result.stderr[-1000:] if result.stderr else ""
            
            if not test_result["success"]:
                test_result["errors"].append(f"Command failed with code {result.returncode}")
            
        except subprocess.TimeoutExpired:
            test_result["errors"].append("Command timed out after 600s")
            logger.error(f"Test timed out: {property_type}/{platform}/{limit}")
        except Exception as e:
            test_result["errors"].append(f"Exception: {str(e)}")
            logger.error(f"Test failed: {e}")
        
        # Add resource metrics
        test_result["metrics"] = monitor.get_summary()
        
        self.results.append(test_result)
        return test_result
    
    def save_results(self):
        """Save all results to JSON file."""
        results_file = self.output_dir / "scaling_study_results.json"
        
        summary = {
            "timestamp": datetime.now().isoformat(),
            "total_tests": len(self.results),
            "successful_tests": sum(1 for r in self.results if r["success"]),
            "failed_tests": sum(1 for r in self.results if not r["success"]),
            "results": self.results,
        }
        
        with open(results_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"Results saved to {results_file}")
        return results_file


def main():
    parser = argparse.ArgumentParser(description="Run scaling study tests")
    parser.add_argument("--node-counts", default="2,3,4,5",
                       help="Comma-separated node counts to test (or 'auto' to detect from tasks)")
    parser.add_argument("--property", default="reachability",
                       help="Property type to test")
    parser.add_argument("--platform", default="frr",
                       help="Platform to test on")
    parser.add_argument("--limit", type=int, default=5,
                       help="Number of tasks per test")
    parser.add_argument("--ollama-endpoint", 
                       help="Ollama endpoint (e.g., http://192.168.3.2:11434)")
    parser.add_argument("--ollama-model",
                       help="Ollama model name (e.g., gpt-oss:120b-cloud)")
    parser.add_argument("--output-dir", type=Path, default=Path("scaling_study_output"),
                       help="Output directory for results")
    
    args = parser.parse_args()
    
    logger.info("Starting scaling study")
    logger.info(f"Property: {args.property}")
    logger.info(f"Platform: {args.platform}")
    logger.info(f"Limit: {args.limit} tasks per test")
    
    if args.ollama_endpoint and args.ollama_model:
        logger.info(f"Using Ollama: {args.ollama_model} at {args.ollama_endpoint}")
    else:
        logger.info("Using baseline testee (no LLM)")
    
    # Create test runner
    runner = ScalingTestRunner(args.output_dir)
    
    # Run test
    result = runner.run_test(
        property_type=args.property,
        platform=args.platform,
        limit=args.limit,
        ollama_endpoint=args.ollama_endpoint,
        ollama_model=args.ollama_model,
    )
    
    # Save results
    results_file = runner.save_results()
    
    # Print summary
    print("\n" + "="*80)
    print("SCALING STUDY SUMMARY")
    print("="*80)
    print(f"Test: {args.property} on {args.platform}")
    print(f"Status: {'✅ SUCCESS' if result['success'] else '❌ FAILED'}")
    print(f"Execution time: {result.get('execution_time_sec', 0):.2f}s")
    
    if result['metrics']:
        print(f"\nResource Usage:")
        print(f"  Benchmark Memory (avg): {result['metrics'].get('benchmark_memory_avg_mb', 0):.0f} MB")
        print(f"  Benchmark Memory (peak): {result['metrics'].get('benchmark_memory_peak_mb', 0):.0f} MB")
        print(f"  CPU (avg): {result['metrics'].get('cpu_avg_percent', 0):.1f}%")
    
    if result['errors']:
        print(f"\nErrors:")
        for error in result['errors']:
            print(f"  - {error}")
    
    print(f"\nResults saved to: {results_file}")
    print("="*80)
    
    return 0 if result['success'] else 1


if __name__ == "__main__":
    exit(main())
