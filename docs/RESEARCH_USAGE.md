# Research Usage Guide

This document describes how to use the Network Configuration Benchmark system for academic research, including running studies, analyzing results, and exporting data for publication.

## Overview

The benchmark system is designed for academic research on network configuration automation, particularly evaluating LLM-based approaches. It provides:

- **Reproducible results** - Deterministic execution with full traceability
- **Comprehensive metrics** - Multiple scoring dimensions for analysis
- **Statistical analysis** - Built-in tools for comparing testee groups
- **Export formats** - JSON, CSV, and LaTeX table formats for papers

## Running Studies

### Single Benchmark Run

```bash
# Run a single benchmark
benchmark run tasks/bgp_basic.json submission.json

# Results saved to results/runs/bgp_basic/run_<timestamp>.json
```

### Multiple Runs

```bash
# Run multiple submissions for same task
benchmark run tasks/bgp_basic.json submission1.json
benchmark run tasks/bgp_basic.json submission2.json
benchmark run tasks/bgp_basic.json submission3.json

# Or run multiple tasks
benchmark run tasks/task1.json submission.json
benchmark run tasks/task2.json submission.json
benchmark run tasks/task3.json submission.json
```

### Property-Based Execution

Run all tasks of a specific property type:

```python
from benchmark.property_executor import PropertyExecutor
from benchmark.task_repository import TaskRepository

# Load task repository
repo = TaskRepository("benchmark-tasks/")

# Create executor
executor = PropertyExecutor(repo)

# Run all reachability tasks
results = executor.run_property_tasks(
    property_type="reachability",
    testee=testee,
    limit=10
)
```

## Analyzing Results

### Aggregate Statistics

```bash
# Analyze multiple runs
benchmark analyze study_001 run_001 run_002 run_003

# Results saved to results/analysis/study_001.json
```

### Python API

```python
from benchmark.storage import ResultsStorage
from benchmark.scoring.metrics import compute_aggregate_metrics

# Load results
storage = ResultsStorage()
runs = [
    storage.load_run("run_001"),
    storage.load_run("run_002"),
    storage.load_run("run_003")
]

# Compute aggregate metrics
aggregate = compute_aggregate_metrics(runs)

print(f"Average Completeness: {aggregate.avg_completeness}")
print(f"Average Final Score: {aggregate.avg_final_score}")
print(f"Success Rate: {aggregate.success_rate}")
```

## Scoring Metrics

### Individual Metrics

The system computes four primary metrics:

1. **Completeness (Score_C)**: Fraction of properties satisfied
   - Range: 0.0 to 1.0
   - Formula: `satisfied_properties / total_properties`

2. **Robustness (Score_R)**: Idempotency score
   - Range: 0.0 to 1.0
   - Checks if configuration can be safely re-applied

3. **Syntactic Validity (Score_X)**: Fraction of valid commands
   - Range: 0.0 to 1.0
   - Formula: `valid_commands / total_commands`

4. **Efficiency (Score_E)**: Optimality vs. reference solution
   - Range: 0.0 to 1.0
   - Formula: `optimal_count / actual_count`

### Final Score

Weighted combination of all metrics:

```
Final = w_C × Score_C + w_R × Score_R + w_X × Score_X + w_E × Score_E
```

Default weights: `{C: 0.4, R: 0.3, X: 0.2, E: 0.1}`

### Validity

A solution is **valid** if and only if:
- **(a) Syntactic Correctness**: All commands valid for platform
- **(b) Semantic Completeness**: All properties satisfied

## Statistical Analysis

### Comparing Testee Groups

```python
from benchmark.analysis import compare_groups

# Group results by testee type
llm_results = [r for r in runs if r.testee_type == "llm"]
human_results = [r for r in runs if r.testee_type == "human"]

# Compare groups
comparison = compare_groups(
    group1=llm_results,
    group2=human_results,
    metric="final_score"
)

print(f"LLM Average: {comparison.group1_mean}")
print(f"Human Average: {comparison.group2_mean}")
print(f"T-test p-value: {comparison.p_value}")
print(f"Effect size: {comparison.effect_size}")
```

### T-Test

```python
from benchmark.analysis import t_test

result = t_test(
    group1_scores=[0.85, 0.90, 0.88, ...],
    group2_scores=[0.92, 0.95, 0.93, ...]
)

print(f"T-statistic: {result.t_statistic}")
print(f"P-value: {result.p_value}")
print(f"Significant: {result.significant}")
```

### ANOVA

For comparing multiple groups:

```python
from benchmark.analysis import anova

result = anova(
    groups={
        "gpt4": [0.85, 0.90, 0.88, ...],
        "claude": [0.88, 0.92, 0.90, ...],
        "human": [0.92, 0.95, 0.93, ...]
    }
)

print(f"F-statistic: {result.f_statistic}")
print(f"P-value: {result.p_value}")
```

## Export Formats

### JSON Export

```python
# Export results to JSON
import json

with open("study_results.json", "w") as f:
    json.dump({
        "runs": [r.model_dump() for r in runs],
        "aggregate": aggregate.model_dump()
    }, f, indent=2)
```

### CSV Export

```python
from benchmark.analysis import export_to_csv

# Export to CSV
export_to_csv(
    runs=runs,
    output_file="study_results.csv"
)
```

### LaTeX Tables

```python
from benchmark.analysis import export_latex_table

# Export to LaTeX
export_latex_table(
    runs=runs,
    output_file="table.tex"
)
```

## Example Study Workflow

### 1. Define Research Question

Example: "Do LLMs perform better than humans on BGP configuration tasks?"

### 2. Select Tasks

```bash
# List available BGP tasks
benchmark list-tasks --property-type bgp_configuration

# Select representative sample
# - Basic tasks
# - Intermediate tasks
# - Advanced tasks
```

### 3. Collect Data

```bash
# Run LLM submissions
for submission in llm_submissions/*.json; do
    benchmark run tasks/bgp_basic.json "$submission"
done

# Run human submissions
for submission in human_submissions/*.json; do
    benchmark run tasks/bgp_basic.json "$submission"
done
```

### 4. Analyze Results

```python
# Load all runs
runs = load_all_runs("results/runs/bgp_basic/")

# Group by testee type
llm_runs = [r for r in runs if r.testee_type == "llm"]
human_runs = [r for r in runs if r.testee_type == "human"]

# Compute statistics
llm_stats = compute_statistics(llm_runs)
human_stats = compute_statistics(human_runs)

# Compare groups
comparison = compare_groups(llm_runs, human_runs)
```

### 5. Export for Publication

```python
# Export to CSV for analysis
export_to_csv(runs, "study_results.csv")

# Export LaTeX table
export_latex_table(runs, "table.tex")
```

## Best Practices

### Study Design

1. **Sample Size**: Aim for at least 30 runs per group for statistical power
2. **Task Selection**: Use diverse tasks covering different difficulty levels
3. **Randomization**: Randomize task order to avoid order effects
4. **Controls**: Include baseline/reference solutions for comparison

### Data Collection

1. **Consistent Testee IDs**: Use consistent identifiers across runs
2. **Metadata**: Record testee metadata (model version, human experience, etc.)
3. **Reproducibility**: Save all task and submission files
4. **Backup**: Regularly backup results directory

### Analysis

1. **Multiple Metrics**: Report all four metrics, not just final score
2. **Statistical Tests**: Use appropriate tests (t-test, ANOVA, etc.)
3. **Effect Sizes**: Report effect sizes, not just p-values
4. **Confidence Intervals**: Include confidence intervals in reports

### Reporting

1. **Transparency**: Report all experimental details
2. **Reproducibility**: Include task definitions and submission examples
3. **Visualization**: Use appropriate visualizations (box plots, bar charts)
4. **Limitations**: Discuss limitations and threats to validity

## Related Documentation

- [Task Format](TASK_FORMAT.md) - Task definition specification
- [Submission Format](SUBMISSION_FORMAT.md) - Submission format guide
- [CLI Usage](CLI_USAGE.md) - Command-line interface reference
- [Architecture](ARCHITECTURE.md) - System architecture

---

**Last Updated**: Phase 12 - Documentation Consolidation

