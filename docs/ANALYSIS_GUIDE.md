# Analysis Guide

Complete guide to analyzing benchmark results using the `benchmark analyze` command.

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Analysis Types](#analysis-types)
- [Statistical Interpretation](#statistical-interpretation)
- [Output Formats](#output-formats)
- [Example Workflows](#example-workflows)
- [CSV Format Reference](#csv-format-reference)

---

## Overview

The analysis system provides three types of analysis:

1. **Testee Analysis** - Analyze performance of a single testee across all tasks
2. **Comparison Analysis** - Compare multiple testees statistically
3. **Property Analysis** - Analyze all runs for a property type across testees

The system automatically detects which analysis to run based on your identifier.

---

## Quick Start

Basic usage:

```bash
# Analyze a single testee
benchmark analyze gpt-4

# Compare multiple testees
benchmark analyze gpt-4,baseline

# Analyze a property type
benchmark analyze reachability
```

Analysis results are exported to `results/analysis/` by default.

---

## Analysis Types

### 1. Testee Analysis

Analyzes all runs for a specific testee, providing:
- Overall aggregate scores (completeness, robustness, syntactic validity, final score)
- Performance breakdown by property type
- Execution time metrics
- Success rates

**Usage**:
```bash
benchmark analyze gpt-4
benchmark analyze baseline
benchmark analyze human-expert-1
```

**Output**:
- `testee_gpt-4_TIMESTAMP.json` - Complete analysis data
- `testee_gpt-4_TIMESTAMP_summary.csv` - Summary table

**Example Output**:
```
Analyzing: gpt-4
================================================================================

Analysis type: testee
Testee: gpt-4

Total runs: 25
Overall score: 0.825
Completeness: 0.850
Properties analyzed: 3

Exporting results...
JSON: results/analysis/testee_gpt-4_20251120_123456.json
CSV: results/analysis/testee_gpt-4_20251120_123456_summary.csv

Analysis complete: testee_gpt-4_20251120_123456
```

### 2. Comparison Analysis

Compares 2+ testees statistically on matched tasks (same tasks completed by all testees):
- Side-by-side score comparison
- Statistical significance testing (t-test for 2 testees, ANOVA for 3+)
- Effect size calculation (Cohen's d)
- Confidence intervals
- Per-property breakdown

**Usage**:
```bash
# Compare two testees (t-test)
benchmark analyze gpt-4,baseline

# Compare three or more testees (ANOVA)
benchmark analyze gpt-4,claude,gemini,baseline
```

**Output**:
- `comparison_gpt-4_baseline_TIMESTAMP.json` - Complete comparison data
- `comparison_gpt-4_baseline_TIMESTAMP_summary.csv` - Comparison table with statistics

**Example Output**:
```
Analyzing: gpt-4,baseline
================================================================================

Analysis type: comparison
Comparing testees: gpt-4, baseline

Testee scores:
  gpt-4: 0.825
  baseline: 0.455

Statistical test: t-test
  p-value: 0.0012
  effect size: 1.85

Exporting results...
JSON: results/analysis/comparison_gpt-4_baseline_20251120_123456.json
CSV: results/analysis/comparison_gpt-4_baseline_20251120_123456_summary.csv

Analysis complete: comparison_gpt-4_baseline_20251120_123456
```

### 3. Property Analysis

Analyzes all runs for a property type across all testees:
- Per-testee performance on the property
- Task difficulty ranking (which tasks are hardest/easiest)
- Cross-testee comparison

**Usage**:
```bash
benchmark analyze reachability
benchmark analyze bgp_configuration
benchmark analyze ospf_configuration
```

**Output**:
- `property_reachability_TIMESTAMP.json` - Complete property analysis
- `property_reachability_TIMESTAMP_summary.csv` - Property summary table

**Example Output**:
```
Analyzing: reachability
================================================================================

Analysis type: property
Property type: reachability

Total runs: 122
Testees analyzed: 3
Tasks: 61

Testee performance:
  gpt-4: 0.825 (50/61 successful)
  claude: 0.775 (45/61 successful)
  baseline: 0.455 (20/61 successful)

Exporting results...
JSON: results/analysis/property_reachability_20251120_123456.json
CSV: results/analysis/property_reachability_20251120_123456_summary.csv

Analysis complete: property_reachability_20251120_123456
```

---

## Statistical Interpretation

### P-values

The p-value indicates the probability that the observed difference occurred by chance:

- **p < 0.01**: Highly significant (strong evidence of difference)
- **p < 0.05**: Significant (good evidence of difference)
- **p < 0.10**: Marginally significant (weak evidence)
- **p >= 0.10**: Not significant (insufficient evidence)

**Example**: `p = 0.0012` means there's only a 0.12% chance the score difference is due to random variation.

### Effect Size (Cohen's d)

Effect size quantifies the magnitude of the difference between groups:

- **d < 0.2**: Small effect
- **d = 0.5**: Medium effect
- **d >= 0.8**: Large effect
- **d >= 1.2**: Very large effect

**Example**: `d = 1.85` indicates a very large, practically significant difference.

### Confidence Intervals

95% confidence intervals indicate the range where the true mean difference likely falls:

**Example**: `CI = [0.25, 0.45]` means we're 95% confident the true score difference is between 0.25 and 0.45.

### Statistical Tests

**T-test** (2 testees):
- Compares means of two independent groups
- Assumes approximately normal distributions
- Reports: t-statistic, p-value, effect size, confidence interval

**ANOVA** (3+ testees):
- Compares means across multiple groups
- Tests if at least one group differs significantly
- Reports: F-statistic, p-value, post-hoc pairwise comparisons

---

## Output Formats

### JSON Format

Complete analysis data in JSON format, suitable for:
- Programmatic access (Python, R, etc.)
- Archiving and reproducibility
- Further statistical analysis

**Structure**:
```json
{
  "analysis_id": "testee_gpt-4_20251120_123456",
  "analysis_type": "testee",
  "timestamp": "2025-11-20T12:34:56",
  "testee_analysis": {
    "testee_id": "gpt-4",
    "total_runs": 25,
    "aggregate_scores": {
      "completeness": 0.850,
      "robustness": 0.800,
      "syntactic_validity": 0.950,
      "final_score": 0.825
    },
    "property_breakdown": { ... },
    "execution_metrics": { ... }
  },
  "export_paths": { ... }
}
```

### CSV Format

Tabular summary suitable for:
- Excel analysis
- R/Python data frames
- Quick visualization
- Sharing with non-technical stakeholders

**Testee Analysis CSV**:
| property_type | total_tasks | successful_tasks | completeness | robustness | final_score |
|---------------|-------------|------------------|--------------|------------|-------------|
| reachability  | 10          | 8                | 0.80         | 0.75       | 0.82        |
| bgp_configuration | 8      | 7                | 0.88         | 0.85       | 0.89        |
| OVERALL       | 25          | -                | 0.85         | 0.80       | 0.825       |

**Comparison Analysis CSV**:
| testee_id | total_runs | completeness | robustness | final_score |
|-----------|------------|--------------|------------|-------------|
| gpt-4     | 20         | 0.85         | 0.80       | 0.825       |
| baseline  | 20         | 0.45         | 0.40       | 0.455       |

Plus statistical test results section below.

---

## Example Workflows

### Workflow 1: Compare LLM Models

Compare multiple LLM models to find the best performer:

```bash
# Run benchmarks (already completed in Phase 11-12)
benchmark run-llm reachability --provider openai --model gpt-4o-mini --limit 10
benchmark run-llm reachability --provider gemini --model gemini-2.5-flash --limit 10
benchmark run-llm reachability --provider anthropic --model claude-3-5-sonnet-20241022 --limit 10

# Analyze comparison
benchmark analyze gpt-4o-mini,gemini-2.5-flash,claude-3-5-sonnet-20241022

# Results will show which model performs best with statistical significance
```

### Workflow 2: Evaluate LLM vs Human vs Baseline

Compare automated approaches against human performance:

```bash
# Analyze comparison
benchmark analyze gpt-4,human-expert-1,baseline

# Check if LLM reaches human-level performance
# Look for:
# - Statistical significance (p-value < 0.05)
# - Effect size (practical significance)
# - Score differences
```

### Workflow 3: Identify Hard Tasks

Find which tasks are most challenging:

```bash
# Analyze property type
benchmark analyze reachability

# Look at task difficulty section in CSV
# Tasks with low average scores are harder
# Use this to:
# - Focus training data on hard tasks
# - Understand LLM limitations
# - Design targeted benchmarks
```

### Workflow 4: Track Progress Over Time

Monitor improvement of a testee across versions:

```bash
# Analyze each version
benchmark analyze gpt-4-v1
benchmark analyze gpt-4-v2
benchmark analyze gpt-4-v3

# Compare versions
benchmark analyze gpt-4-v1,gpt-4-v2,gpt-4-v3

# Check if improvements are statistically significant
```

### Workflow 5: Property-Specific Performance

Understand which properties are hardest for LLMs:

```bash
# Analyze each property
benchmark analyze reachability
benchmark analyze bgp_configuration
benchmark analyze ospf_configuration

# Compare property difficulty across testees
# Identify property types where LLMs struggle
```

---

## CSV Format Reference

### Testee Analysis CSV

**Columns**:
- `property_type`: Property type name (or "OVERALL" for aggregate)
- `total_tasks`: Number of tasks executed
- `successful_tasks`: Tasks with valid solutions
- `completeness`: Average completeness score (0.0-1.0)
- `robustness`: Average robustness score (0.0-1.0)
- `syntactic_validity`: Average syntactic validity (0.0-1.0)
- `efficiency`: Average efficiency (0.0-1.0, or empty if N/A)
- `final_score`: Average final score (0.0-1.0)

### Comparison Analysis CSV

**Section 1: Testee Scores**
- `testee_id`: Testee identifier
- `total_runs`: Number of matched runs
- `completeness`: Average completeness
- `robustness`: Average robustness
- `syntactic_validity`: Average syntactic validity
- `efficiency`: Average efficiency (if available)
- `final_score`: Average final score

**Section 2: Statistical Tests** (after blank row)
- Test type (t-test or ANOVA)
- Statistical test parameters
- Significance indicators

### Property Analysis CSV

**Section 1: Testee Performance**
- `testee_id`: Testee identifier
- `total_tasks`: Tasks completed
- `successful_tasks`: Successful tasks
- Score columns (same as testee analysis)

**Section 2: Task Difficulty** (after blank row)
- `task_id`: Task identifier
- `average_score`: Average score across all testees (sorted by difficulty)

---

## Advanced Options

### Custom Output Directory

```bash
benchmark analyze gpt-4 --output-dir /path/to/custom/dir
```

### Export Format Selection

```bash
# JSON only
benchmark analyze gpt-4 --format json

# CSV only
benchmark analyze gpt-4 --format csv

# Both (default)
benchmark analyze gpt-4 --format all
```

### Case-Insensitive Property Types

Property types are case-insensitive:

```bash
benchmark analyze REACHABILITY
benchmark analyze Bgp_Configuration
benchmark analyze ospf_configuration
```

All resolve to the correct property type.

---

## Troubleshooting

### Error: "No results found for testee: X"

**Cause**: No benchmark runs exist for the specified testee.

**Solution**: Run benchmarks first:
```bash
benchmark run-llm reachability --provider openai --model gpt-4
```

### Error: "No matched runs found for testees"

**Cause**: Testees have not completed the same tasks (required for comparison).

**Solution**: 
- Ensure all testees complete the same set of tasks
- Use property-based execution for fair comparison:
```bash
benchmark run-llm reachability --provider openai --limit 10
benchmark run-baseline reachability --limit 10
```

### Error: "No results found for property type: X"

**Cause**: No runs exist for the specified property type.

**Solution**: Check property type spelling (must be one of: reachability, bgp_configuration, ospf_configuration)

### Very High P-values (p > 0.5)

**Meaning**: No statistically significant difference between testees.

**Possible causes**:
- Testees perform similarly
- Insufficient sample size
- High variance in scores

**Solution**: Collect more runs or check if testees are actually different.

---

## Best Practices

1. **Run Sufficient Samples**: Aim for 10+ matched runs for meaningful comparisons
2. **Use Consistent Task Sets**: Compare testees on identical tasks
3. **Check Assumptions**: Ensure approximately normal distributions for statistical tests
4. **Report Effect Sizes**: Don't rely on p-values alone - effect sizes show practical significance
5. **Document Analysis**: Keep analysis IDs and timestamps for reproducibility
6. **Export Both Formats**: JSON for archiving, CSV for quick analysis
7. **Review Property Breakdown**: Overall scores can hide property-specific strengths/weaknesses

---

## See Also

- [CLI Usage Guide](CLI_USAGE.md) - Complete CLI reference
- [Research Usage Guide](RESEARCH_USAGE.md) - Research workflows
- [LLM Integration Guide](LLM_INTEGRATION.md) - LLM testee configuration

