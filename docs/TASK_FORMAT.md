# Task Format Specification

This document describes the format for defining benchmark tasks in the Network Configuration Benchmark system.

**Where tasks ship:** Interactive research uses JSON under [`tasks/multi_turn/`](../tasks/multi_turn/) via **`benchmark run-task`** (see [Research usage](RESEARCH_USAGE.md), [CLI usage](CLI_USAGE.md)). That path matches the NetAgentBench study in [arXiv:2604.09678](https://arxiv.org/abs/2604.09678). Older single-turn catalogs live at the repository root [`tasks/`](../tasks/) and in [`tasks/sample/`](../tasks/sample/).

## Overview

A task definition (`TaskDefinition`) specifies:
- **Topology**: Network nodes, links, and interfaces
- **Intent**: Properties to verify and how to evaluate them
- **Platform**: Target network platform (FRR, Cisco IOS, etc.)
- **Convergence**: Timeout settings for protocol convergence
- **Optimal Solution**: Reference for efficiency scoring

## Complete Task Definition Structure

```json
{
  "task_id": "unique_task_identifier",
  "description": "Human-readable task description",
  "platform": "frr",
  "topology": {
    "nodes": [...],
    "links": [...],
    "interfaces": [...]
  },
  "intent": {
    "properties": [...]
  },
  "convergence": {
    "timeout_seconds": 30,
    "check_interval_seconds": 2
  },
  "optimal_solution": {
    "command_count": 4,
    "description": "Description of optimal approach"
  }
}
```

## Required Fields

### task_id (string)

Unique identifier for the task. Used to reference the task in submissions and results.

```json
"task_id": "bgp_basic_001"
```

### description (string)

Human-readable description of what the task requires.

```json
"description": "Configure eBGP peering between two routers"
```

### platform (string)

Target network platform. Supported values:
- `"frr"` - FRR (FRRouting)
- `"cisco_ios"` - Cisco IOS
- `"juniper_junos"` - Juniper JunOS
- `"vyos"` - VyOS

```json
"platform": "frr"
```

### topology (object)

Network topology specification containing nodes, links, and optional interfaces.

#### nodes (array)

List of network nodes (routers, switches, hosts).

```json
"nodes": [
  {
    "name": "R1",
    "type": "router",
    "image": "frrouting/frr:latest",
    "platform": "frr"
  },
  {
    "name": "R2",
    "type": "router",
    "image": "frrouting/frr:latest",
    "platform": "frr"
  }
]
```

**Node Fields**:
- `name` (string, required): Unique node identifier
- `type` (string, required): Node type: `"router"`, `"switch"`, `"host"`, `"linux"`
- `image` (string, optional): Docker image to use (default: `"frrouting/frr:latest"`)
- `platform` (string, optional): Platform type (defaults to task platform)

#### links (array)

Network links connecting nodes.

```json
"links": [
  {
    "endpoints": ["R1:eth1", "R2:eth1"]
  }
]
```

**Link Fields**:
- `endpoints` (array, required): List of two endpoint strings in format `"NodeName:InterfaceName"`

#### interfaces (array, optional)

Additional interface specifications (if needed).

```json
"interfaces": []
```

### intent (object)

Network intent specification containing properties to verify.

#### properties (array)

List of properties that must be satisfied.

```json
"properties": [
  {
    "id": "bgp_session",
    "type": "bgp_configuration",
    "description": "BGP session is established",
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
```

**Property Fields**:
- `id` (string, required): Unique property identifier
- `type` (string, required): Property type (see Property Types below)
- `description` (string, required): Human-readable description
- `evaluation` (object, required): Evaluation procedure (see Evaluation below)

### convergence (object)

Convergence timeout settings.

```json
"convergence": {
  "timeout_seconds": 30,
  "check_interval_seconds": 2
}
```

**Convergence Fields**:
- `timeout_seconds` (integer, required): Maximum time to wait for convergence
- `check_interval_seconds` (integer, required): Interval between convergence checks

### optimal_solution (object)

Reference solution for efficiency scoring.

```json
"optimal_solution": {
  "command_count": 4,
  "description": "Minimal configuration: IP addresses and BGP session"
}
```

**Optimal Solution Fields**:
- `command_count` (integer, required): Number of commands in optimal solution
- `description` (string, required): Description of optimal approach

## Property Types

Supported property types:

- `"reachability"` - Network reachability between nodes
- `"bgp_configuration"` - BGP session configuration
- `"bgp_session"` - BGP session state (deprecated, use `bgp_configuration`)
- `"route_exists"` - Route existence in routing table
- `"ospf_configuration"` - OSPF configuration
- `"ospf_adjacency"` - OSPF adjacency state
- `"interface_up"` - Interface state

## Evaluation Procedures

Each property must specify how it is evaluated using an `evaluation` object.

### Evaluation Method

Currently supported:
- `"exec_and_parse"` - Execute command and parse output

### Evaluation Object Structure

```json
"evaluation": {
  "method": "exec_and_parse",
  "target_node": "R1",
  "command": "vtysh -c 'show bgp summary json'",
  "parser": "json",
  "success_condition": {
    // Parser-specific conditions
  }
}
```

**Evaluation Fields**:
- `method` (string, required): Evaluation method (`"exec_and_parse"`)
- `target_node` (string, required): Node on which to execute command
- `command` (string, required): Command to execute
- `parser` (string, required): Parser type (`"json"`, `"regex"`, `"text"`)
- `success_condition` (object, required): Parser-specific success condition

## Parsers

### JSON Parser

For structured command output (e.g., `show` commands with JSON output).

```json
{
  "parser": "json",
  "success_condition": {
    "json_path": "$.peers['192.168.1.2'].state",
    "expected_value": "Established"
  }
}
```

**Success Condition Fields**:
- `json_path` (string, required): JSONPath expression to extract value
- `expected_value` (any, required): Expected value (string, number, boolean)

**Example Command Output**:
```json
{
  "peers": {
    "192.168.1.2": {
      "state": "Established"
    }
  }
}
```

### Regex Parser

For pattern matching in text output.

```json
{
  "parser": "regex",
  "success_condition": {
    "pattern": "2\\.2\\.2\\.2/32.*via.*192\\.168\\.1\\.2",
    "must_match": true
  }
}
```

**Success Condition Fields**:
- `pattern` (string, required): Regular expression pattern (escape special chars)
- `must_match` (boolean, required): Whether pattern must match (`true`) or not match (`false`)

**Example Command Output**:
```
2.2.2.2/32 via 192.168.1.2, eth1
```

### Text Parser

For simple string presence checks.

```json
{
  "parser": "text",
  "success_condition": {
    "contains_text": "3 packets transmitted, 3 packets received"
  }
}
```

**Success Condition Fields**:
- `contains_text` (string, required): Text that must be present in output

**Example Command Output**:
```
PING 192.168.1.2 (192.168.1.2) 56(84) bytes of data.
64 bytes from 192.168.1.2: icmp_seq=1 ttl=64 time=0.123 ms
64 bytes from 192.168.1.2: icmp_seq=2 ttl=64 time=0.098 ms
64 bytes from 192.168.1.2: icmp_seq=3 ttl=64 time=0.105 ms

--- 192.168.1.2 ping statistics ---
3 packets transmitted, 3 packets received, 0% packet loss
```

## Complete Example

```json
{
  "task_id": "bgp_basic",
  "description": "Basic BGP configuration with two routers",
  "platform": "frr",
  "topology": {
    "nodes": [
      {
        "name": "R1",
        "type": "router",
        "image": "frrouting/frr:latest",
        "platform": "frr"
      },
      {
        "name": "R2",
        "type": "router",
        "image": "frrouting/frr:latest",
        "platform": "frr"
      }
    ],
    "links": [
      {
        "endpoints": ["R1:eth1", "R2:eth1"]
      }
    ],
    "interfaces": []
  },
  "intent": {
    "properties": [
      {
        "id": "bgp_session_established",
        "type": "bgp_configuration",
        "description": "BGP session between R1 and R2 is established",
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
  },
  "convergence": {
    "timeout_seconds": 45,
    "check_interval_seconds": 3
  },
  "optimal_solution": {
    "command_count": 12,
    "description": "Configure IP addresses, loopbacks, and BGP session"
  }
}
```

## Best Practices

### Task Design

1. **Use descriptive property IDs**: Make property IDs clear and meaningful
   ```json
   "id": "bgp_session_r1_to_r2"  // Good
   "id": "p1"  // Bad
   ```

2. **Choose appropriate parser types**:
   - Use JSON parser for structured output (show commands with JSON)
   - Use regex parser for pattern matching in text
   - Use text parser for simple presence checks

3. **Set realistic convergence timeouts**:
   - BGP: 30-60 seconds
   - OSPF: 20-40 seconds
   - Basic reachability: 10-20 seconds

4. **Include optimal solution**: Provides reference for efficiency scoring

5. **Validate node names**: Ensure all node names in links exist in nodes array

### Property Evaluation

- **JSON Parser**: Best for structured command output (show commands)
- **Regex Parser**: Best for pattern matching in text output
- **Text Parser**: Best for simple string presence checks

### Command Design

- Use platform-specific commands (e.g., `vtysh` for FRR)
- Ensure commands are idempotent when possible
- Test commands manually before adding to task

## Validation

All task definitions are validated against Pydantic models:

- Required fields must be present
- Enum values must be valid
- Data types must match specifications
- Cross-references must be valid (e.g., node names in links)

### Validation Errors

Common validation errors:

1. **Missing required field**: Add the missing field
2. **Invalid enum value**: Use one of the supported values
3. **Invalid node reference**: Ensure node name exists in nodes array
4. **Invalid JSONPath**: Test JSONPath expression separately

## Related Documentation

- [Submission Format](SUBMISSION_FORMAT.md) - How to create submissions
- [Architecture](ARCHITECTURE.md) - System architecture
- [Getting Started](GETTING_STARTED.md) - Installation and setup

---

**Last Updated**: Phase 12 - Documentation Consolidation

