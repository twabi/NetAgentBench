# Submission Format Guide

This document describes the format for creating benchmark submissions in the Network Configuration Benchmark system.

**Scope:** Submissions are consumed by **`benchmark run`** and related single-shot tooling. **Multi-turn** **`run-task`** runs never take a `Submission` JSON as their driver—agent transcripts are emitted directly into `results/` instead.

## Overview

A submission (`Submission`) specifies:
- **Task Reference**: Which task is being solved
- **Testee Information**: Who/what is submitting
- **Approach**: Configuration commands organized by node

## Complete Submission Structure

```json
{
  "task_id": "task_identifier_being_solved",
  "testee_id": "unique_testee_identifier",
  "testee_type": "llm|human|baseline|ml",
  "approach": {
    "description": "Human-readable approach description",
    "commands": [
      {
        "node": "R1",
        "commands": ["command1", "command2", ...]
      }
    ]
  }
}
```

## Required Fields

### task_id (string)

The identifier of the task being solved. Must match an existing task.

```json
"task_id": "bgp_basic_001"
```

**Finding Task IDs**:
```bash
benchmark list-tasks
```

### testee_id (string)

Unique identifier for the testee (person, LLM, or system) submitting the solution.

```json
"testee_id": "alice_engineer"
```

**Best Practices**:
- Use consistent identifiers across submissions
- Include meaningful information (e.g., `"john_engineer"`, `"gpt4_v1"`, `"team_acme"`)

### testee_type (string)

Type of testee submitting the solution. Supported values:
- `"llm"` - Large Language Model
- `"human"` - Human network engineer
- `"baseline"` - Baseline/reference solution
- `"ml"` - Machine learning model

```json
"testee_type": "human"
```

### approach (object)

Configuration approach containing description and commands.

#### description (string)

Brief description of the configuration approach.

```json
"description": "Configure basic IP addresses and enable interfaces"
```

#### commands (array)

Array of command objects, each specifying commands for a particular node.

```json
"commands": [
  {
    "node": "R1",
    "commands": [
      "configure terminal",
      "interface eth0",
      "ip address 10.0.0.1/24",
      "no shutdown",
      "exit"
    ]
  },
  {
    "node": "R2",
    "commands": [
      "configure terminal",
      "interface eth0",
      "ip address 10.0.0.2/24",
      "no shutdown",
      "exit"
    ]
  }
]
```

**Command Object Fields**:
- `node` (string, required): Target node name (must match node name in task)
- `commands` (array of strings, required): List of commands to execute on that node

## Complete Examples

### Basic Reachability Task

```json
{
  "task_id": "reachability_linear_2n_R1_to_R2",
  "testee_id": "alice_engineer",
  "testee_type": "human",
  "approach": {
    "description": "Configure basic IP addresses and enable interfaces",
    "commands": [
      {
        "node": "R1",
        "commands": [
          "configure terminal",
          "interface eth0",
          "ip address 10.0.0.1/24",
          "no shutdown",
          "exit"
        ]
      },
      {
        "node": "R2",
        "commands": [
          "configure terminal",
          "interface eth0",
          "ip address 10.0.0.2/24",
          "no shutdown",
          "exit"
        ]
      }
    ]
  }
}
```

### BGP Configuration Task

```json
{
  "task_id": "bgp_2as_example",
  "testee_id": "gpt4_v1",
  "testee_type": "llm",
  "approach": {
    "description": "Configure eBGP peering between two autonomous systems",
    "commands": [
      {
        "node": "R1",
        "commands": [
          "vtysh -c 'configure terminal'",
          "vtysh -c 'router bgp 65001'",
          "vtysh -c 'neighbor 192.168.1.2 remote-as 65002'",
          "vtysh -c 'network 10.0.0.0/24'",
          "vtysh -c 'end'"
        ]
      },
      {
        "node": "R2",
        "commands": [
          "vtysh -c 'configure terminal'",
          "vtysh -c 'router bgp 65002'",
          "vtysh -c 'neighbor 192.168.1.2 remote-as 65001'",
          "vtysh -c 'network 20.0.0.0/24'",
          "vtysh -c 'end'"
        ]
      }
    ]
  }
}
```

### OSPF Configuration Task

```json
{
  "task_id": "ospf_3node_example",
  "testee_id": "baseline_reference",
  "testee_type": "baseline",
  "approach": {
    "description": "Configure OSPF on all interfaces in area 0",
    "commands": [
      {
        "node": "R1",
        "commands": [
          "vtysh -c 'configure terminal'",
          "vtysh -c 'router ospf'",
          "vtysh -c 'network 10.0.0.0/24 area 0'",
          "vtysh -c 'end'"
        ]
      },
      {
        "node": "R2",
        "commands": [
          "vtysh -c 'configure terminal'",
          "vtysh -c 'router ospf'",
          "vtysh -c 'network 10.0.0.0/24 area 0'",
          "vtysh -c 'network 20.0.0.0/24 area 0'",
          "vtysh -c 'end'"
        ]
      },
      {
        "node": "R3",
        "commands": [
          "vtysh -c 'configure terminal'",
          "vtysh -c 'router ospf'",
          "vtysh -c 'network 20.0.0.0/24 area 0'",
          "vtysh -c 'end'"
        ]
      }
    ]
  }
}
```

## Command Formatting

### Platform-Specific Commands

Commands must match the platform specified in the task:

#### FRR (FRRouting)

```bash
# Using vtysh (recommended)
vtysh -c 'configure terminal'
vtysh -c 'router bgp 65001'
vtysh -c 'neighbor 192.168.1.2 remote-as 65002'
vtysh -c 'end'

# Or using individual commands
vtysh -c 'conf t' -c 'router bgp 65001' -c 'neighbor 192.168.1.2 remote-as 65002' -c 'end'
```

#### Cisco IOS

```bash
configure terminal
router bgp 65001
neighbor 192.168.1.2 remote-as 65002
exit
exit
```

### Command Organization

Commands are organized by target node:

```json
{
  "node": "R1",
  "commands": [
    "command1",
    "command2",
    "command3"
  ]
}
```

**Best Practices**:
- Group related commands together
- Execute commands in logical order
- Include error handling where appropriate
- Use idempotent commands when possible

## Common Patterns

### Basic Interface Configuration

```json
{
  "node": "R1",
  "commands": [
    "configure terminal",
    "interface eth0",
    "ip address 10.0.0.1/24",
    "no shutdown",
    "exit",
    "exit"
  ]
}
```

### BGP Configuration

```json
{
  "node": "R1",
  "commands": [
    "vtysh -c 'configure terminal'",
    "vtysh -c 'router bgp 65001'",
    "vtysh -c 'neighbor 192.168.1.2 remote-as 65002'",
    "vtysh -c 'network 10.0.0.0/24'",
    "vtysh -c 'end'"
  ]
}
```

### OSPF Configuration

```json
{
  "node": "R1",
  "commands": [
    "vtysh -c 'configure terminal'",
    "vtysh -c 'router ospf'",
    "vtysh -c 'network 10.0.0.0/24 area 0'",
    "vtysh -c 'end'"
  ]
}
```

## Best Practices

### Submission Design

1. **Use consistent testee IDs**: Use the same identifier across all your submissions
   ```json
   "testee_id": "john_engineer"  // Use consistently
   ```

2. **Clear descriptions**: Provide clear, concise approach descriptions
   ```json
   "description": "Configure eBGP with route filtering"  // Good
   "description": "BGP"  // Too vague
   ```

3. **Organize commands by node**: Group commands logically by target node
   ```json
   "commands": [
     {"node": "R1", "commands": [...]},
     {"node": "R2", "commands": [...]}
   ]
   ```

4. **Use valid commands**: Ensure commands are valid for the platform
   - Test commands manually if unsure
   - Use platform-specific syntax

5. **Node names must match**: Node names must exactly match task definition
   ```json
   // Task has node "R1"
   {"node": "R1", "commands": [...]}  // Correct
   {"node": "router1", "commands": [...]}  // Wrong
   ```

### Command Design

- **Idempotency**: Use idempotent commands when possible (can be safely re-applied)
- **Error handling**: Include error handling where appropriate
- **Command order**: Execute commands in logical order (e.g., configure interface before enabling)
- **Platform syntax**: Use correct syntax for the target platform

## Validation

All submissions are validated against Pydantic models:

- Required fields must be present
- `task_id` must reference an existing task
- `testee_type` must be a valid enum value
- Node names in commands must exist in the task topology

### Validation Errors

Common validation errors:

1. **Missing required field**: Add the missing field
2. **Invalid task_id**: Ensure task exists (use `benchmark list-tasks`)
3. **Invalid testee_type**: Use one of: `"llm"`, `"human"`, `"baseline"`, `"ml"`
4. **Invalid node name**: Ensure node name matches task definition

## Running Submissions

### Using CLI

```bash
# Run a single submission
benchmark run <task_file> <submission_file>

# Example
benchmark run tasks/bgp_basic.json my_submission.json
```

### Using Python API

```python
from benchmark.controller import BenchmarkController
from benchmark.models.task import TaskDefinition
from benchmark.models.submission import Submission
import json

# Load task
with open('tasks/bgp_basic.json', 'r') as f:
    task_data = json.load(f)
task = TaskDefinition.model_validate(task_data)

# Load submission
with open('my_submission.json', 'r') as f:
    submission_data = json.load(f)
submission = Submission.model_validate(submission_data)

# Run benchmark
controller = BenchmarkController()
result = controller.run(task, submission)

# Results are automatically saved
print(f"Final score: {result.scoring.final_score}")
```

## Example Files

Example submission files are available in:
- `examples/human_submissions/` - Human submission examples
- `templates/` - Submission templates

## Related Documentation

- [Task Format](TASK_FORMAT.md) - Task definition specification
- [Human Benchmark Guide](HUMAN_BENCHMARK_GUIDE.md) - Guide for human participants
- [CLI Usage](CLI_USAGE.md) - Command-line interface reference
- [Getting Started](GETTING_STARTED.md) - Installation and setup

---

**Last Updated**: Phase 12 - Documentation Consolidation

