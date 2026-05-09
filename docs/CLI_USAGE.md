# CLI Usage Guide

Complete reference for the Network Configuration Benchmark CLI.

## Table of Contents

1. [Installation](#installation)
2. [Quick Start](#quick-start)
3. [Single-turn vs multi-turn tasks](#single-turn-vs-multi-turn-tasks)
4. [Multi-turn benchmark (`run-task`)](#multi-turn-benchmark-run-task)
5. [Task Management](#task-management)
6. [Running Benchmarks](#running-benchmarks)
   - [Single Task Execution](#single-task-execution)
   - [Property-Based Execution](#property-based-execution)
   - [LLM Testees](#llm-testees)
   - [Human Testees](#human-testees)
   - [Baseline Testees](#baseline-testees)
7. [Results Management](#results-management)
8. [Advanced Usage](#advanced-usage)

---

## Installation

The CLI is automatically installed when you install the benchmark package:

```bash
# Install with Poetry (recommended)
poetry install

# Activate the virtual environment
poetry shell

# Verify installation
benchmark --help
```

---

## Quick Start

```bash
# List catalogued single-turn tasks (multi-turn JSONs live in tasks/multi_turn/)
benchmark list-tasks

# Primary: multi-turn evaluation (start dagent/similar first)
benchmark run-task tasks/multi_turn/ccna_rip_routing_basic.json \
  --dagent-endpoint http://localhost:8000 \
  --provider openai --model gpt-4o-mini

# Legacy property batches
benchmark run-baseline reachability
benchmark run-llm bgp_configuration --provider openai
benchmark run-human reachability --limit 3
```

---

## Single-turn vs multi-turn tasks

| | Multi-turn | Single-turn |
|--|------------|-------------|
| **`benchmark` entrypoint** | **`run-task`** | **`run`**, **`run-llm`**, **`run-baseline`**, **`run-human`** |
| Task location | [`tasks/multi_turn/`](../tasks/multi_turn/) | Repo `tasks/`, `tasks/sample/`, registered catalog |
| Paper track | [NetAgentBench (arXiv:2604.09678)](https://arxiv.org/abs/2604.09678) | auxiliary / regression |

More context: [Research usage](RESEARCH_USAGE.md), [Agentic evaluation](AGENTIC_EVALUATION.md).

---

## Multi-turn benchmark (`run-task`)

Runs a **single** multi-turn task JSON; provisions the lab, spins up the interactive controller/MCP path, and binds to an external `--dagent-endpoint`.

```bash
benchmark run-task <task_file> [OPTIONS]
```

| Option | Purpose |
|--------|---------|
| `--dagent-endpoint URL` | Agent HTTP base (typically required). |
| `--provider` / `--model` | LLM routing (OpenAI, Gemini, Ollama, …). |
| `--agent-mode` | `single` or `multi`. |
| `--structure` | `sequential`, `concurrent`, `debate`, `group_chat`, `adaptive`. |
| `--turn-limit` / `--time-limit` | Step and wall-clock guards. |
| `--context-length`, `--provider-host`, `--mcp-host` | Extended provider / networking hints. |
| `--output-dir` | Session root under `results/` (script-dependent layout). |
| `--wait-for-submit` | Pause for hand-injected agents. |
| `-v` | Verbose logging. |

Examples:

```bash
benchmark run-task tasks/multi_turn/ccie_bgp_dual_homing_expert.json \
  --dagent-endpoint http://localhost:8000 \
  --provider openai --model gpt-4o \
  --agent-mode multi --structure debate \
  --turn-limit 100 --time-limit 1800
```

---

## Task Management

### List Tasks

```bash
benchmark list-tasks [OPTIONS]
```

**Options**:
- `--property-type TYPE` - Filter by property type (reachability, bgp_configuration, ospf_configuration)
- `--verbose` - Show detailed task information

**Examples**:

```bash
# List all tasks
benchmark list-tasks

# List only reachability tasks
benchmark list-tasks --property-type reachability

# List with detailed info
benchmark list-tasks --verbose
```

### Show Task Details

```bash
benchmark show-task <task_id>
```

Displays comprehensive information about a specific task including topology, properties, and evaluation procedures.

**Examples**:

```bash
# Show details for a specific task
benchmark show-task bgp_basic_001

# View task before creating submission
benchmark show-task reachability_triangle_001
```

---

## Running Benchmarks

The subcommands below cover **single-turn** workloads. For **multi-turn** research, prefer [`run-task`](#multi-turn-benchmark-run-task).

### Single Task Execution

**Single-turn (legacy):** supply a complete submission JSON for one evaluation pass.

```bash
benchmark run <task_file> <submission_file> [OPTIONS]
```

**Arguments**:
- `task_file` - Path to task definition JSON file
- `submission_file` - Path to submission JSON file

**Options**:
- `--verbose` - Enable detailed logging
- `--no-teardown` - Keep containers running after benchmark (for debugging)
- `--output-dir DIR` - Custom directory for results (default: `results/runs/`)

**Examples**:

```bash
# Basic usage
benchmark run tasks/bgp_basic.json submission.json

# With verbose output
benchmark run tasks/bgp_basic.json submission.json --verbose

# Keep containers for debugging
benchmark run tasks/bgp_basic.json submission.json --no-teardown

# Custom output directory
benchmark run tasks/bgp_basic.json submission.json --output-dir my_results/
```

### Property-Based Execution

Property-based commands run **all tasks** for a specific property type (e.g., all reachability tasks) with a testee. This is the primary way to benchmark different testee types.

---

### LLM Testees

Run tasks using Large Language Models to generate configurations:

```bash
benchmark run-llm <property_type> [OPTIONS]
```

**Arguments**:
- `property_type` - Property type to test (reachability, bgp_configuration, ospf_configuration)

**Options**:
- `--provider PROVIDER` - **Required**. LLM provider: `openai`, `gemini`, or `anthropic`
- `--model MODEL` - Model name (uses provider default if not specified)
- `--limit N` - Limit number of tasks to run
- `--output-dir DIR` - Custom output directory

**Environment Variables**:

LLM providers require API keys set in `.env` file or environment:

```bash
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=...
ANTHROPIC_API_KEY=sk-ant-...
```

**Examples**:

```bash
# Run reachability tasks with OpenAI (default model: gpt-4o-mini)
benchmark run-llm reachability --provider openai

# Run 3 BGP tasks with specific Gemini model
benchmark run-llm bgp_configuration --provider gemini --model gemini-2.5-pro --limit 3

# Run OSPF tasks with Anthropic Claude
benchmark run-llm ospf_configuration --provider anthropic

# Run with custom output directory
benchmark run-llm reachability --provider openai --output-dir results/openai_test/
```

**Supported Providers and Models**:

| Provider | Default Model | Other Models |
|----------|---------------|--------------|
| OpenAI | gpt-4o-mini | gpt-4o, gpt-4, gpt-3.5-turbo |
| Gemini | gemini-2.5-flash | gemini-2.5-pro, gemini-2.0-flash |
| Anthropic | claude-3-5-sonnet-20241022 | claude-3-opus-20240229, claude-3-sonnet-20240229 |

---

### Human Testees

#### Interactive Mode

Run tasks interactively where you're prompted for submission files:

```bash
benchmark run-human <property_type> [OPTIONS]
```

For each task:
1. Task details are displayed
2. You provide the path to a submission JSON file
3. The submission is validated and the benchmark runs
4. Type `skip` to skip a task

**Examples**:

```bash
# Run reachability tasks interactively
benchmark run-human reachability

# Run 3 BGP tasks interactively
benchmark run-human bgp_configuration --limit 3
```

**Interactive Session Example**:

```
$ benchmark run-human reachability --limit 2

================================================================================
Task: reachability_triangle_001
================================================================================
Description: Configure basic reachability in a triangle topology
Topology: 3 nodes (router1, router2, router3), 3 links
Properties: Host router1 can reach host router3
...
================================================================================

Enter path to submission JSON for reachability_triangle_001 (or 'skip' to skip): 
> submissions/reachability_001.json

[Running benchmark...]

Task reachability_triangle_001 completed: score=0.950

[Next task displays...]
```

---

### Baseline Testees

Run tasks with baseline (empty/minimal) configurations to establish performance baselines:

```bash
benchmark run-baseline <property_type> [OPTIONS]
```

**Examples**:

```bash
# Run all reachability tasks with baseline
benchmark run-baseline reachability

# Run 5 BGP tasks with baseline
benchmark run-baseline bgp_configuration --limit 5
```

Baseline testees are useful for:
- Establishing minimum scores
- Testing infrastructure setup
- Comparing against LLM/human performance

---

### Run All Property Types

Run tasks across **all property types** with a single testee:

```bash
benchmark run-all [OPTIONS]
```

**Options**:
- `--testee-type TYPE` - Testee type: `llm`, `baseline`, or `human` (default: baseline)
- `--provider PROVIDER` - LLM provider (required if testee-type is llm)
- `--model MODEL` - LLM model name
- `--limit N` - Limit number of tasks **per property type**
- `--output-dir DIR` - Custom output directory

**Examples**:

```bash
# Run all tasks with baseline
benchmark run-all --testee-type baseline

# Run 3 tasks per property with OpenAI
benchmark run-all --testee-type llm --provider openai --limit 3

# Run with specific model
benchmark run-all --testee-type llm --provider gemini --model gemini-2.5-pro --limit 5

# Interactive human mode across all properties
benchmark run-all --testee-type human --limit 2
```

**Output Example**:

```
Benchmark Run Complete
================================================================================
Run ID: run_1700000000_abc123
Testee: llm_openai_gpt-4o-mini (llm)
Total Tasks: 45
Overall Average Score: 0.782
Execution Time: 1234.5s

Property Type Results:
  reachability: 12/15 (avg: 0.850)
  bgp_configuration: 8/15 (avg: 0.720)
  ospf_configuration: 10/15 (avg: 0.776)
```

---

## Results Management

### List Recent Runs

```bash
benchmark list-runs [OPTIONS]
```

**Options**:
- `--task-id TASK_ID` - Filter by task ID
- `--limit N` - Number of recent runs to show (default: 10)

**Examples**:

```bash
# List 10 most recent runs
benchmark list-runs

# List recent runs for specific task
benchmark list-runs --task-id bgp_basic_001

# List 50 most recent runs
benchmark list-runs --limit 50
```

### Show Result Details

```bash
benchmark show-result <run_id> [OPTIONS]
```

**Options**:
- `--verbose` - Show detailed property results

**Examples**:

```bash
# Show result summary
benchmark show-result run_1234567890_abc123

# Show detailed property results
benchmark show-result run_1234567890_abc123 --verbose
```

**Output Example**:

```
Run ID: run_1234567890_abc123
Task ID: bgp_basic_001
Testee: llm_openai_gpt-4o-mini (llm)
Timestamp: 2024-11-20T10:30:00

Success: True
Final Score: 0.850
Completeness: 0.900
Robustness: 0.800
Syntactic Validity: 1.000
Efficiency: 0.750

Property Results (5):
  ✓ bgp_neighbor_established: BGP neighbor is established
  ✓ routes_advertised: Routes are advertised correctly
  ✗ convergence_time: Convergence within 30 seconds
  ✓ no_routing_loops: No routing loops detected
  ✓ traffic_forwarding: Traffic is forwarded correctly
```

---

## Advanced Usage

### Global Options

All commands support these global options:

```bash
benchmark [OPTIONS] COMMAND
```

**Options**:
- `-v, --verbose` - Enable detailed logging (DEBUG level)
- `-q, --quiet` - Suppress non-error output (ERROR level only)

**Examples**:

```bash
# Run with debug logging
benchmark -v run-llm reachability --provider openai

# Run quietly (only errors)
benchmark -q run-baseline bgp_configuration
```

### Environment Variables

Create a `.env` file in the project root:

```bash
# LLM API Keys
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=...
ANTHROPIC_API_KEY=sk-ant-...

# Optional: Custom paths
BENCHMARK_TASKS_DIR=benchmark-tasks/
BENCHMARK_RESULTS_DIR=results/
```

### Custom Task Repository

By default, tasks are loaded from `benchmark-tasks/`. To use a custom repository:

```python
# In Python
from benchmark.task_repository import TaskRepository

repo = TaskRepository(Path("/path/to/custom/tasks"))
```

### Debugging Failed Runs

```bash
# 1. Run with verbose logging and keep containers
benchmark -v run task.json submission.json --no-teardown

# 2. Inspect container logs
docker ps
docker logs <container_id>

# 3. SSH into containers for debugging
docker exec -it <container_id> bash

# 4. Clean up when done
docker stop <container_id>
```

### Batch Testing Multiple Models

```bash
#!/bin/bash
# test_all_llms.sh

PROPERTY="reachability"
LIMIT=5

# Test OpenAI models
benchmark run-llm $PROPERTY --provider openai --model gpt-4o-mini --limit $LIMIT
benchmark run-llm $PROPERTY --provider openai --model gpt-4o --limit $LIMIT

# Test Gemini models
benchmark run-llm $PROPERTY --provider gemini --model gemini-2.5-flash --limit $LIMIT
benchmark run-llm $PROPERTY --provider gemini --model gemini-2.5-pro --limit $LIMIT

# Test Anthropic models
benchmark run-llm $PROPERTY --provider anthropic --model claude-3-5-sonnet-20241022 --limit $LIMIT

echo "All benchmarks complete! Check results/ directory."
```

### Output Directory Structure

```
results/
├── runs/                          # Single task results
│   └── {task_id}/
│       └── {run_id}.json
├── property_results/              # Property-based execution results
│   └── {property_type}_{timestamp}.json
├── benchmark_runs/                # Multi-property run results
│   └── {run_id}.json
└── analysis/                      # Aggregate statistics
    └── {study_id}.json
```

---

## Troubleshooting

### Common Issues

**1. API Key Not Found**

```
Error: OPENAI_API_KEY not found in environment.
```

**Solution**: Create `.env` file with your API key:

```bash
echo "OPENAI_API_KEY=sk-..." > .env
```

**2. Docker Permission Denied**

```
Error: Permission denied while trying to connect to Docker daemon
```

**Solution**: Add your user to docker group:

```bash
sudo usermod -aG docker $USER
# Log out and back in
```

**3. Task Repository Not Found**

```
Error: Task repository not found: benchmark-tasks/
```

**Solution**: Ensure you're in the project root directory or specify custom path:

```bash
cd /path/to/benchmark
benchmark list-tasks
```

**4. Container Provisioning Timeout**

```
Error: Timeout waiting for containers to start
```

**Solution**: 
- Check Docker is running: `docker ps`
- Increase timeout in configuration
- Check system resources (memory, CPU)

### Getting Help

```bash
# General help
benchmark --help

# Command-specific help
benchmark run-llm --help
benchmark run-human --help
benchmark list-tasks --help
```

For more assistance:
- Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- Review [GitHub Issues](https://github.com/your-repo/issues)
- Join our Discord community

---

## Examples

### Example 1: Research Workflow

```bash
# 1. Explore available tasks
benchmark list-tasks --property-type reachability --verbose

# 2. Inspect a specific task
benchmark show-task reachability_triangle_001

# 3. Establish baseline performance
benchmark run-baseline reachability --limit 10

# 4. Test LLM performance
benchmark run-llm reachability --provider openai --limit 10

# 5. Compare results
benchmark list-runs --limit 20
```

### Example 2: Multi-Model Comparison

```bash
# Run same tasks across multiple LLMs
PROPERTY="bgp_configuration"
LIMIT=5

benchmark run-llm $PROPERTY --provider openai --model gpt-4o-mini --limit $LIMIT
benchmark run-llm $PROPERTY --provider gemini --model gemini-2.5-flash --limit $LIMIT
benchmark run-llm $PROPERTY --provider anthropic --limit $LIMIT

# Analyze results
benchmark list-runs --limit 15
```

### Example 3: Human Benchmark Participation

```bash
# Prepare submissions directory
mkdir -p my_submissions/

# Run interactively
benchmark run-human reachability --limit 5

# (For each task, provide path to your submission JSON)
```

---

---

## Analysis Commands

### Analyze Benchmark Results

```bash
benchmark analyze <identifier> [OPTIONS]
```

Analyze benchmark results with automatic identifier detection.

**Options**:
- `--output-dir PATH` - Output directory for analysis results (default: `results/analysis`)
- `--format {json|csv|all}` - Export format (default: `all`)

**Identifier Types**:

1. **Testee ID** - Analyze single testee performance:
   ```bash
   benchmark analyze gpt-4
   benchmark analyze baseline
   ```

2. **Property Type** - Analyze property across all testees:
   ```bash
   benchmark analyze reachability
   benchmark analyze bgp_configuration
   benchmark analyze ospf_configuration
   ```

3. **Comparison** (comma-separated) - Compare multiple testees:
   ```bash
   # Compare two testees (t-test)
   benchmark analyze gpt-4,baseline
   
   # Compare three or more testees (ANOVA)
   benchmark analyze gpt-4,claude,gemini,baseline
   ```

**Examples**:

```bash
# Analyze GPT-4 performance
benchmark analyze gpt-4

# Compare models statistically
benchmark analyze gpt-4,claude,baseline

# Analyze reachability property difficulty
benchmark analyze reachability

# Export JSON only
benchmark analyze gpt-4 --format json

# Custom output location
benchmark analyze gpt-4,baseline --output-dir /path/to/analysis
```

**Output**:

Analysis results are exported in the specified format(s):
- **JSON**: Complete analysis data with all details
- **CSV**: Summary table for Excel/R/Python analysis

Each analysis creates files with timestamps:
- `testee_gpt-4_TIMESTAMP.json`
- `testee_gpt-4_TIMESTAMP_summary.csv`
- `comparison_gpt-4_baseline_TIMESTAMP.json`
- `comparison_gpt-4_baseline_TIMESTAMP_summary.csv`
- `property_reachability_TIMESTAMP.json`
- `property_reachability_TIMESTAMP_summary.csv`

**Analysis Types**:

1. **Testee Analysis**:
   - Overall aggregate scores
   - Performance by property type
   - Execution time metrics
   - Success rates

2. **Comparison Analysis**:
   - Side-by-side score comparison
   - Statistical significance (t-test or ANOVA)
   - Effect size (Cohen's d)
   - Confidence intervals
   - Per-property breakdown

3. **Property Analysis**:
   - Per-testee performance on property
   - Task difficulty ranking
   - Cross-testee comparison

For detailed information on analysis and statistical interpretation, see the [Analysis Guide](ANALYSIS_GUIDE.md).

---

## See Also

- [Analysis Guide](ANALYSIS_GUIDE.md) - Complete analysis documentation
- [Getting Started Guide](GETTING_STARTED.md) - Installation and first steps
- [Task Format Specification](TASK_FORMAT.md) - Creating custom tasks
- [Submission Format Guide](SUBMISSION_FORMAT.md) - Writing submissions
- [LLM Integration Guide](LLM_INTEGRATION.md) - LLM provider setup
- [Research Usage Guide](RESEARCH_USAGE.md) - Research workflows and analysis
