#!/usr/bin/env python3
"""
Analyze scaling study results and generate summary report.

Usage:
    python scripts/analyze_scaling_results.py /tmp/scaling_test_baseline/scaling_study_results.json
"""
import argparse
import json
from pathlib import Path
from typing import Dict, List, Any


def analyze_results(results_file: Path) -> Dict[str, Any]:
    """Analyze scaling test results."""
    
    with open(results_file) as f:
        data = json.load(f)
    
    results = data.get("results", [])
    
    if not results:
        return {"error": "No results found"}
    
    # Aggregate statistics
    successful = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success")]
    
    analysis = {
        "summary": {
            "total_tests": len(results),
            "successful": len(successful),
            "failed": len(failed),
            "success_rate": len(successful) / len(results) if results else 0,
        },
        "performance": {},
        "resources": {},
        "errors": [],
    }
    
    if successful:
        exec_times = [r["execution_time_sec"] for r in successful if "execution_time_sec" in r]
        if exec_times:
            analysis["performance"] = {
                "avg_execution_time_sec": sum(exec_times) / len(exec_times),
                "min_execution_time_sec": min(exec_times),
                "max_execution_time_sec": max(exec_times),
            }
        
        # Resource statistics
        memory_avgs = [r["metrics"]["benchmark_memory_avg_mb"] for r in successful if "metrics" in r and "benchmark_memory_avg_mb" in r["metrics"]]
        memory_peaks = [r["metrics"]["benchmark_memory_peak_mb"] for r in successful if "metrics" in r and "benchmark_memory_peak_mb" in r["metrics"]]
        cpu_avgs = [r["metrics"]["cpu_avg_percent"] for r in successful if "metrics" in r and "cpu_avg_percent" in r["metrics"]]
        
        if memory_avgs:
            analysis["resources"]["memory_avg_mb"] = sum(memory_avgs) / len(memory_avgs)
        if memory_peaks:
            analysis["resources"]["memory_peak_mb"] = max(memory_peaks)
        if cpu_avgs:
            analysis["resources"]["cpu_avg_percent"] = sum(cpu_avgs) / len(cpu_avgs)
    
    # Collect errors
    for r in failed:
        if r.get("errors"):
            analysis["errors"].extend(r["errors"])
    
    return analysis


def print_report(analysis: Dict[str, Any]):
    """Print formatted analysis report."""
    
    print("\n" + "="*80)
    print("SCALING STUDY ANALYSIS REPORT")
    print("="*80)
    
    # Summary
    summary = analysis.get("summary", {})
    print(f"\n📊 Test Summary:")
    print(f"  Total tests: {summary.get('total_tests', 0)}")
    print(f"  Successful: {summary.get('successful', 0)}")
    print(f"  Failed: {summary.get('failed', 0)}")
    print(f"  Success rate: {summary.get('success_rate', 0):.1%}")
    
    # Performance
    perf = analysis.get("performance", {})
    if perf:
        print(f"\n⏱️  Performance:")
        print(f"  Avg execution time: {perf.get('avg_execution_time_sec', 0):.2f}s")
        print(f"  Min execution time: {perf.get('min_execution_time_sec', 0):.2f}s")
        print(f"  Max execution time: {perf.get('max_execution_time_sec', 0):.2f}s")
    
    # Resources
    resources = analysis.get("resources", {})
    if resources:
        print(f"\n💾 Resource Usage:")
        print(f"  Avg memory: {resources.get('memory_avg_mb', 0):.0f} MB")
        print(f"  Peak memory: {resources.get('memory_peak_mb', 0):.0f} MB")
        print(f"  Avg CPU: {resources.get('cpu_avg_percent', 0):.1f}%")
    
    # Errors
    errors = analysis.get("errors", [])
    if errors:
        print(f"\n❌ Errors ({len(errors)}):")
        for error in errors[:5]:  # Show first 5
            print(f"  - {error}")
        if len(errors) > 5:
            print(f"  ... and {len(errors) - 5} more")
    
    print("="*80 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Analyze scaling study results")
    parser.add_argument("results_file", type=Path, help="Path to scaling_study_results.json")
    
    args = parser.parse_args()
    
    if not args.results_file.exists():
        print(f"Error: Results file not found: {args.results_file}")
        return 1
    
    analysis = analyze_results(args.results_file)
    print_report(analysis)
    
    return 0


if __name__ == "__main__":
    exit(main())
