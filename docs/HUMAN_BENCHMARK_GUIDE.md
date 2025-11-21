# Human Benchmark Guide

This guide explains how humans (network engineers) can participate in the Network Configuration Benchmark.

## Overview

The benchmark supports two modes for human participation:

1. **JSON File Submission** - Submit pre-written configurations in JSON format
2. **Interactive CLI** - Use the interactive command-line tool to submit configurations

## Quick Start

### Option 1: JSON File Submission

Create a JSON file with your configuration:

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

Run the benchmark:

```bash
python -m benchmark.cli.run_human --submission my_submission.json
```

### Option 2: Interactive CLI

Launch the interactive tool:

```bash
python -m benchmark.cli.human_cli
```

The tool will:

1. Display the task description and network topology
2. Show each node and prompt for commands
3. Generate a JSON submission file
4. Optionally run the benchmark immediately

## JSON Submission Format

### Required Fields

- `task_id` (string): The ID of the benchmark task
- `testee_id` (string): Your unique identifier (e.g., "john_doe", "team_acme")
- `testee_type` (string): Must be "human"
- `approach` (object): Your configuration approach

### Approach Object

- `description` (string): Brief description of your approach
- `commands` (array): Array of node command objects

### Node Commands Object

- `node` (string): Node name (e.g., "R1", "R2")
- `commands` (array of strings): CLI commands to execute

## Available Tasks

Tasks are organized by property type:

### Reachability Tasks

Test basic network connectivity between nodes.

Example tasks:
- `reachability_linear_2n_R1_to_R2` - Two nodes in a line
- `reachability_linear_3n_R1_to_R3` - Three nodes in a line
- `reachability_mesh_4n_all_to_all` - Four nodes, full mesh

### BGP Configuration Tasks

Configure BGP routing between autonomous systems.

Example tasks:
- `bgp_ebgp_2as` - Two AS with eBGP
- `bgp_ibgp_3routers` - Three routers with iBGP
- `bgp_mixed_tree_d2_b4` - Complex BGP topology

### OSPF Configuration Tasks

Configure OSPF routing within an area.

Example tasks:
- `ospf_area0_linear_3n` - Three nodes in OSPF area 0
- `ospf_area0_mesh_4n` - Four nodes in full mesh
- `ospf_area0_ring_8n` - Eight nodes in a ring

## Viewing Tasks

To view available tasks:

```bash
python -m benchmark.cli.list_tasks
```

To view a specific task:

```bash
python -m benchmark.cli.view_task reachability_linear_2n_R1_to_R2
```

## Running the Benchmark

### Single Task

```bash
python -m benchmark.cli.run_human --submission my_submission.json
```

### Multiple Tasks

Submit a directory of JSON files:

```bash
python -m benchmark.cli.run_human --submission-dir ./my_submissions/
```

### Run All Tasks for a Property Type

```bash
python -m benchmark.cli.run_human \
  --property-type reachability \
  --submission-generator interactive
```

## Understanding Results

After running the benchmark, you'll receive:

### Scoring Metrics

1. **Completeness (Score_C)**: Fraction of required properties satisfied (0.0-1.0)
2. **Robustness (Score_R)**: Idempotency score - configuration remains stable (0.0-1.0)
3. **Syntactic Validity (Score_X)**: Fraction of valid CLI commands (0.0-1.0)
4. **Efficiency (Score_E)**: Efficiency vs. optimal solution (0.0-1.0)
5. **Final Score**: Weighted combination of all metrics

### Example Results

```json
{
  "task_id": "reachability_linear_2n_R1_to_R2",
  "testee_id": "alice_engineer",
  "success": true,
  "scoring": {
    "completeness": 1.0,
    "robustness": 1.0,
    "syntactic_validity": 1.0,
    "efficiency": 0.95,
    "final_score": 0.99
  }
}
```

## Best Practices

### 1. Read the Task Carefully

- Understand the network topology
- Note all required properties
- Check any constraints or requirements

### 2. Test Your Configuration

- Ensure commands are syntactically valid
- Consider idempotency (running twice should be safe)
- Think about efficiency (minimize unnecessary commands)

### 3. Document Your Approach

- Provide a clear description
- Explain any non-obvious choices
- Note any assumptions

### 4. Start Simple

- Begin with basic reachability tasks
- Progress to BGP and OSPF as you gain confidence
- Use smaller topologies before tackling larger ones

## Example Submissions

See `examples/human_submissions/` for complete examples:

- `reachability_2node_example.json` - Basic reachability
- `bgp_2as_example.json` - Simple BGP configuration
- `ospf_3node_example.json` - Basic OSPF configuration

## Scoring Details

### Completeness (Score_C)

The fraction of properties that are satisfied:

```
Score_C = (number of satisfied properties) / (total properties)
```

For reachability: All required node pairs must be reachable.
For BGP: All required BGP sessions must be established.
For OSPF: All required OSPF adjacencies must be formed.

### Robustness (Score_R)

Tests idempotency by applying the configuration twice:

```
Score_R = 1 - (changes after second application) / (total properties)
```

Ideally, your configuration should produce the same result when applied multiple times.

### Syntactic Validity (Score_X)

Fraction of commands that are syntactically valid:

```
Score_X = (valid commands) / (total commands)
```

Invalid commands may fail to execute or cause errors.

### Efficiency (Score_E)

Compares your solution to the optimal:

```
Score_E = 1 - ((your_commands - optimal_commands) / optimal_commands)
```

Only available for tasks with known optimal solutions.

### Final Score

Weighted combination:

```
Final = 0.4 * C + 0.3 * R + 0.2 * X + 0.1 * E
```

Default weights can be customized.

## Tips for High Scores

1. **Completeness**: Ensure all requirements are met
2. **Robustness**: Use idempotent commands (e.g., set values, not toggle)
3. **Validity**: Test commands in a real environment if possible
4. **Efficiency**: Remove unnecessary commands, use concise syntax

## Comparing with Other Testees

View leaderboards:

```bash
python -m benchmark.cli.leaderboard --property-type reachability
```

Compare specific submissions:

```bash
python -m benchmark.cli.compare \
  --submission-1 human_alice.json \
  --submission-2 llm_gpt4.json
```

## Troubleshooting

### Common Issues

**Q: My submission file is rejected**

A: Check that:
- JSON is valid (no syntax errors)
- All required fields are present
- task_id matches an existing task
- Node names match the topology

**Q: I got a low completeness score**

A: Verify that:
- All required properties are configured
- Commands actually execute successfully
- Network converges before evaluation

**Q: I got a low robustness score**

A: Check for:
- Commands that toggle state
- Missing "no shutdown" commands
- Race conditions in configuration order

**Q: I got a low efficiency score**

A: Consider:
- Removing redundant commands
- Using more concise syntax
- Avoiding unnecessary configuration

## Getting Help

- File issues: https://github.com/your-repo/benchmark/issues
- Documentation: https://your-docs-site.com
- Community: https://discord.gg/your-server

## Contributing

We welcome contributions:

- Report bugs or unclear documentation
- Suggest new tasks
- Share your best practices
- Improve the human CLI tool

See `CONTRIBUTING.md` for details.

