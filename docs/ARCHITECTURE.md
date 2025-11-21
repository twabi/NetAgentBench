# System Architecture

This document describes the architecture of the Network Configuration Benchmark system.

## Overview

The benchmark system follows a three-layer Finite State Machine (FSM) architecture that separates infrastructure provisioning from configuration evaluation. This design enables formal verification of network configurations while remaining platform-agnostic.

## Three-Layer FSM Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Benchmark Controller                      │
│                  (FSM State Orchestrator)                    │
└────────┬──────────────────────────────────────┬─────────────┘
         │                                       │
         ▼                                       ▼
┌────────────────────┐              ┌────────────────────────┐
│ Infrastructure FSM │              │    SUT FSM             │
│   (Containerlab)   │──Initialize─▶│ (Config + Evaluate)   │
│                    │              │                        │
│ • Provision        │              │ • Execute commands     │
│ • Teardown         │              │ • Observe state        │
│ • Node management  │              │ • Evaluate properties  │
└────────────────────┘              └────────────────────────┘
         │                                       │
         └───────────────┬───────────────────────┘
                         ▼
                 ┌───────────────┐
                 │    Storage    │
                 │ (JSON Results)│
                 └───────────────┘
```

### Layer 1: Infrastructure FSM

The Infrastructure FSM provisions and manages the network topology:

- **Provision**: Creates network topology using Containerlab
- **Teardown**: Cleans up topology and containers
- **Node Management**: Manages individual network nodes

**Implementation**: `src/benchmark/infrastructure/containerlab.py`

### Layer 2: System Under Test (SUT) FSM

The SUT FSM applies configurations and evaluates properties:

- **Execute Commands**: Applies configuration commands to nodes
- **Observe State**: Executes observation commands to check network state
- **Evaluate Properties**: Checks if properties are satisfied

**Implementation**: 
- `src/benchmark/executor/` - Command execution
- `src/benchmark/evaluator/` - Property evaluation

### Layer 3: Controller FSM

The Controller FSM orchestrates the entire benchmark workflow:

- Coordinates infrastructure provisioning
- Manages configuration application
- Orchestrates property evaluation
- Computes scores and saves results

**Implementation**: `src/benchmark/controller.py`

## Repository Structure

```
network-config-benchmark/
├── src/benchmark/
│   ├── models/           # Pydantic models (task, submission, results)
│   ├── infrastructure/   # Containerlab provider
│   ├── executor/         # Command execution & observation
│   ├── evaluator/        # Property evaluation & parsing
│   ├── scoring/          # Scoring metrics calculation
│   ├── llm/              # LLM integration layer
│   ├── testee/           # Testee implementations (baseline, human, ML)
│   ├── controller.py     # Main orchestrator
│   ├── storage.py        # Results persistence
│   ├── task_repository.py # Task repository management
│   ├── property_executor.py # Property-based execution
│   └── presenter.py      # Task presentation system
├── benchmark-tasks/      # Task library
│   ├── property_types/   # Tasks organized by property type
│   │   ├── reachability/
│   │   ├── bgp_configuration/
│   │   └── ospf_configuration/
│   └── index.json        # Task index
├── tasks/                # Legacy task definitions
├── results/              # Benchmark results
│   ├── runs/            # Individual run results
│   ├── suites/          # Suite-level results
│   └── analysis/        # Aggregate statistics
├── tests/               # Unit and integration tests
│   ├── unit/           # Fast unit tests
│   └── integration/    # Integration tests (require Containerlab)
└── pyproject.toml       # Project configuration
```

## Core Components

### Models (`src/benchmark/models/`)

Pydantic models for data validation:

- **`task.py`**: Task definition models (Topology, Properties, Evaluation)
- **`submission.py`**: Submission models (Approach, Commands)
- **`results.py`**: Result models (RunResult, PropertyResult, Scoring)
- **`llm_config.py`**: LLM configuration models

### Infrastructure (`src/benchmark/infrastructure/`)

Infrastructure provisioning:

- **`containerlab.py`**: Containerlab provider implementation
- **`base.py`**: Abstract infrastructure provider interface

### Executor (`src/benchmark/executor/`)

Command execution and observation:

- **`command.py`**: Command execution on nodes
- **`observation.py`**: Observation command execution

### Evaluator (`src/benchmark/evaluator/`)

Property evaluation:

- **`property.py`**: Property evaluation logic
- **`parsers.py`**: Output parsers (JSON, regex, text)

### Scoring (`src/benchmark/scoring/`)

Metrics calculation:

- **`metrics.py`**: Score calculation (Completeness, Robustness, etc.)
- **`validity.py`**: Syntactic validity checking

### Controller (`src/benchmark/controller.py`)

Main orchestrator that coordinates all components:

- Loads task and submission
- Provisions infrastructure
- Applies configuration
- Evaluates properties
- Computes scores
- Saves results

### Storage (`src/benchmark/storage.py`)

Results persistence:

- Saves run results to JSON files
- Organizes results by task and run ID
- Supports analysis aggregation

### Task Repository (`src/benchmark/task_repository.py`)

Task library management:

- Loads tasks from task repository
- Filters by property type
- Provides task metadata

### Property Executor (`src/benchmark/property_executor.py`)

Property-based execution:

- Executes tasks by property type
- Aggregates results across multiple tasks
- Computes aggregate metrics

## Data Flow

```
1. Load Task Definition (JSON)
   ├─ Topology specification
   ├─ Intent specification (properties)
   └─ Evaluation procedures

2. Load Testee Submission (JSON)
   └─ Configuration approach (commands)

3. Provision Infrastructure
   └─ Generate .clab.yml → clab deploy

4. Apply Configuration
   └─ Execute commands via docker exec

5. Wait for Convergence
   └─ Manual timeout (smart detection later)

6. Evaluate Properties
   ├─ Execute observation commands
   ├─ Parse outputs (JSON/regex/text)
   └─ Check success conditions

7. Compute Scores
   ├─ Completeness (properties satisfied)
   ├─ Robustness (idempotency)
   ├─ Syntactic validity (command success)
   └─ Efficiency (vs optimal solution)

8. Save Results (JSON)
   └─ results/runs/{task_id}/{run_id}.json

9. Generate Statistics
   └─ Aggregate across multiple runs
```

## Key Design Decisions

### Task-Driven Evaluation

**The Task Definition specifies:**
- Topology structure (nodes, links, interfaces)
- Properties to verify (intent)
- **HOW to check each property** (evaluation procedures)
- Platform-specific metadata

This makes the benchmark engine **generic** - it just follows instructions!

### Platform-Agnostic Design

The system abstracts platform-specific details:

- Infrastructure provider is pluggable (Containerlab implementation)
- Command execution is abstracted
- Evaluation procedures are specified in tasks

### JSON-Based Standardization

All inputs and outputs use JSON:

- Task definitions: JSON
- Submissions: JSON
- Results: JSON

This enables:
- Easy integration with LLMs
- Human-readable format
- Simple parsing and validation

### Formal Verification

The system is based on FSM formalization:

- Proven correctness guarantees
- Valid solution characterization
- Robustness formalization

See [Formalization Alignment](FORMALIZATION_ALIGNMENT.md) for details.

## Component Interactions

### Running a Benchmark

1. **Controller** loads task and submission
2. **Infrastructure Provider** provisions topology
3. **Executor** applies configuration commands
4. **Evaluator** evaluates properties
5. **Scoring** computes metrics
6. **Storage** saves results

### Property Evaluation

1. **Evaluator** receives property definition
2. **Executor** executes observation command
3. **Parser** parses output (JSON/regex/text)
4. **Evaluator** checks success condition
5. Returns property result

### LLM Integration

1. **LLM Runner** loads task
2. **Presenter** formats task for LLM
3. **LLM Provider** generates configuration
4. **Parser** extracts commands from response
5. **Controller** runs benchmark with generated submission

## Extension Points

### Adding New Infrastructure Providers

Implement `InfrastructureProvider` interface:

```python
class MyProvider(InfrastructureProvider):
    def provision(self, topology: TopologySpecification) -> str:
        # Provision topology
        pass
    
    def teardown(self, topology_id: str) -> None:
        # Teardown topology
        pass
```

### Adding New Parsers

Add parser to `src/benchmark/evaluator/parsers.py`:

```python
def parse_my_format(output: str, condition: dict) -> bool:
    # Parse output and check condition
    pass
```

### Adding New Property Types

Add property type to task definition and implement evaluation in `PropertyEvaluator`.

## Performance Considerations

### Infrastructure Provisioning

- Containerlab provisioning: ~10-30 seconds per topology
- Teardown: ~5-10 seconds

### Command Execution

- Command execution: ~1-5 seconds per command
- Observation commands: ~1-3 seconds each

### Property Evaluation

- JSON parsing: < 1 second
- Regex parsing: < 1 second
- Text parsing: < 1 second

## Security Considerations

- Containerlab requires sudo access
- Docker containers run with network isolation
- No persistent data stored in containers
- All results stored locally in JSON files

## Future Enhancements

- Smart convergence detection (instead of fixed timeouts)
- Parallel execution of multiple benchmarks
- Additional infrastructure providers
- Web-based UI for task creation
- Real-time result visualization

## Related Documentation

- [Getting Started](GETTING_STARTED.md) - Installation and setup
- [Task Format](TASK_FORMAT.md) - Task definition specification
- [Formalization Alignment](FORMALIZATION_ALIGNMENT.md) - Theory and implementation
- [Testing Guide](TESTING.md) - Testing architecture

---

**Last Updated**: Phase 12 - Documentation Consolidation

