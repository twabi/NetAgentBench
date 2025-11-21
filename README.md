# Network Configuration Benchmark

A formal verification system for evaluating network configuration approaches using Finite State Machine (FSM) theory and Containerlab.

## Overview

This benchmark evaluates whether network configurations (from LLMs, humans, or automated systems) correctly achieve specified network intent. It provides **provably correct** evaluation based on rigorous FSM formalization.

### Key Features

- ✅ **Formal verification** - Based on FSM theory with proven correctness
- ✅ **JSON-based standardization** - Structured input/output for testees
- ✅ **Task-driven evaluation** - Task definitions specify topology, intent, and evaluation procedures
- ✅ **Platform-agnostic design** - Abstracts infrastructure and configuration platforms
- ✅ **Research-ready** - Collects comprehensive metrics for publication
- ✅ **Containerlab integration** - Dynamic topology provisioning

### Design Philosophy

1. **Task definitions are king** - JSON-based specs guide everything
2. **Simplest solutions first** - No overengineering
3. **Test-driven development** - Tests before code
4. **Platform-agnostic** - Abstract design, Containerlab implementation
5. **Research-ready** - Metrics suitable for publication

## Quick Start

### Installation

```bash
# Prerequisites: Docker, Containerlab, Poetry

# Install Poetry (if not already installed)
curl -sSL https://install.python-poetry.org | python3 -

# Install project dependencies
poetry install

# Activate Poetry shell
poetry shell
```

### Run a Benchmark

```bash
# Using Poetry
poetry run benchmark run <task_file> <submission_file>

# Or from within Poetry shell
poetry shell
benchmark run <task_file> <submission_file>
```

### Example Task Definition

```json
{
  "task_id": "bgp_basic_001",
  "platform": "frr",
  "topology": {
    "nodes": [
      {"name": "R1", "type": "router", "image": "frrouting/frr:latest"},
      {"name": "R2", "type": "router", "image": "frrouting/frr:latest"}
    ],
    "links": [{"endpoints": ["R1:eth1", "R2:eth1"]}]
  },
  "intent": {
    "properties": [
      {
        "id": "bgp_session",
        "type": "bgp_session",
        "evaluation": {
          "method": "exec_and_parse",
          "target_node": "R1",
          "command": "vtysh -c 'show bgp summary json'",
          "parser": "json",
          "success_condition": {
            "json_path": "$.peers['192.168.1.2'].state",
            "expected_value": "Established"
          }
        }
      }
    ]
  }
}
```

### Example Submission

```json
{
  "task_id": "bgp_basic_001",
  "testee_id": "gpt4",
  "testee_type": "llm",
  "approach": {
    "description": "Configure eBGP peering",
    "commands": [
      {
        "node": "R1",
        "commands": [
          "vtysh -c 'conf t' -c 'router bgp 65001'",
          "vtysh -c 'conf t' -c 'neighbor 192.168.1.2 remote-as 65002'"
        ]
      }
    ]
  }
}
```

## Documentation

Comprehensive documentation is available in the [`docs/`](docs/) directory:

- **[Getting Started](docs/GETTING_STARTED.md)** - Installation, setup, and first steps
- **[Architecture](docs/ARCHITECTURE.md)** - System design and components
- **[Task Format](docs/TASK_FORMAT.md)** - Task definition specification
- **[Submission Format](docs/SUBMISSION_FORMAT.md)** - Submission format guide
- **[CLI Usage](docs/CLI_USAGE.md)** - Command-line interface reference
- **[Human Benchmark Guide](docs/HUMAN_BENCHMARK_GUIDE.md)** - Guide for human participants
- **[LLM Integration](docs/LLM_INTEGRATION.md)** - LLM provider setup and usage
- **[Research Usage](docs/RESEARCH_USAGE.md)** - Running studies and analyzing results
- **[Testing Guide](docs/TESTING.md)** - Running and writing tests
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions
- **[Formalization Alignment](docs/FORMALIZATION_ALIGNMENT.md)** - Theory and implementation alignment

See [docs/README.md](docs/README.md) for the complete documentation index.

## Architecture

The system follows a three-layer FSM architecture:

1. **Infrastructure Layer**: Provisions network topology (Containerlab)
2. **System Under Test (SUT) Layer**: Applies and evaluates configurations
3. **Controller Layer**: Orchestrates the entire benchmark workflow

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed architecture documentation.

## Scoring Metrics

Based on the formal model, the system computes:

- **Completeness**: Fraction of properties satisfied (Score_C)
- **Robustness**: Idempotency - can safely re-apply (Score_R)
- **Syntactic Validity**: Fraction of valid commands (Score_X)
- **Efficiency**: Optimality vs. reference solution (Score_E)
- **Final Score**: Weighted combination

Default weights: `{C: 0.4, R: 0.3, X: 0.2, E: 0.1}`

## Project Status

**Current Phase**: Phase 12 - CLI & Documentation

See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for detailed progress tracking.

## Development

### Running Tests

```bash
# Unit tests (fast)
poetry run pytest tests/unit/

# Integration tests (slow, requires Containerlab)
poetry run pytest tests/integration/ -m integration

# All tests with coverage
poetry run pytest --cov=benchmark --cov-report=html
```

### Project Structure

```
benchmark/
├── src/benchmark/          # Main package
│   ├── models/            # Pydantic models
│   ├── infrastructure/    # Containerlab provider
│   ├── executor/          # Command execution
│   ├── evaluator/         # Property evaluation
│   ├── scoring/           # Metrics calculation
│   ├── controller.py      # Main orchestrator
│   └── storage.py         # Results persistence
├── tasks/                 # Task definitions
├── results/               # Benchmark results
└── tests/                 # Test suite
```

## Research Usage

This system is designed for academic research on network configuration automation, particularly LLM-based approaches.

### Running a Study

```bash
# Run multiple submissions
benchmark run tasks/bgp_basic.json submission1.json
benchmark run tasks/bgp_basic.json submission2.json

# Analyze results
benchmark analyze study_001 run_001 run_002 run_003

# Results saved to results/analysis/study_001.json
```

See [docs/RESEARCH_USAGE.md](docs/RESEARCH_USAGE.md) for detailed research workflows.

## Theoretical Foundation

This implementation is based on formal FSM theory. Key theoretical contributions:

- **Two-layer FSM architecture** separating infrastructure from configuration
- **Proven benchmark correctness** (Theorem: Benchmark Correctness)
- **Valid solution characterization** (Theorem: Valid Solution)
- **Robustness formalization** (Theorem: Robust Solution)

Alignment with theory is tracked in [docs/FORMALIZATION_ALIGNMENT.md](docs/FORMALIZATION_ALIGNMENT.md).

## Contributing

This is a research project. Contributions welcome following TDD principles:

1. Write tests first
2. Keep solutions simple
3. Follow the formal model
4. Document divergences from theory

# Usage

```bash
# Step 1: Run reachability tasks (20 runs total)
benchmark run-llm reachability --provider openai --model gpt-5-mini --limit 10
benchmark run-llm reachability --provider gemini --model gemini-2.5-pro --limit 10

# Step 2: Run BGP tasks (20 runs total)
benchmark run-llm bgp_configuration --provider openai --model gpt-5-mini --limit 10
benchmark run-llm bgp_configuration --provider gemini --model gemini-2.5-pro --limit 10

# Step 3: Run OSPF tasks (20 runs total)
benchmark run-llm ospf_configuration --provider openai --model gpt-5-mini --limit 10
benchmark run-llm ospf_configuration --provider gemini --model gemini-2.5-pro --limit 10

# Step 4: Verify storage
benchmark list-runs --limit 30

# Step 5: Check a specific result
benchmark show-result <run_id> --verbose

# Step 6: Analysis - Comparison
benchmark analyze gpt-5-mini,gemini-2.5-pro

# Step 7: Analysis - Property type
benchmark analyze reachability
benchmark analyze bgp_configuration
benchmark analyze ospf_configuration

# Step 8: Analysis - Individual testee
benchmark analyze gpt-5-mini
benchmark analyze gemini-2.5-pro
```

## License

[To be determined]

## Citation

[To be added upon publication]

## Contact

[Your contact information]

---

**Status**: 🚧 Under active development - Phase 12 in progress
