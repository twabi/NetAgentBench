# Multi-Turn Task Design Guide

## Core Principle: Same Tasks, Different Interaction Mode

### The Elegant Simplicity

**Multi-turn is NOT about changing task definitions.**  
**Multi-turn is about giving agents the ability to explore before committing.**

**Single-Turn Mode**:
```
Task → Agent generates config → Submit → Evaluate
```

**Multi-Turn Mode**:
```
Task → Lab provisioned → Agent explores + configures iteratively → Submit → Evaluate
```

**Same task JSON. Same property definitions. Same success criteria.**

The difference: Agent has `exec_command` tool to check network state before/during/after configuration.

---

## What Makes a Good Multi-Turn Task?

### 1. Complexity That Rewards Exploration

**Bad for Multi-Turn** (too simple):
```json
{
  "task_id": "simple_reachability_2_nodes",
  "topology": {"nodes": 2, "platform": "frr"},
  "intent": {
    "properties": [
      {"type": "reachability", "source": "R1", "dest": "R2"}
    ]
  }
}
```
→ Agent can solve in one shot. No benefit from multi-turn.

**Good for Multi-Turn** (exploration helps):
```json
{
  "task_id": "bgp_ospf_campus_50_nodes",
  "topology": {
    "nodes": 50,
    "platforms": ["frr", "nokia_srlinux", "arista_ceos"],
    "topology_type": "spine_leaf"
  },
  "intent": {
    "properties": [
      {"type": "reachability", "all_nodes": true},
      {"type": "ospf_neighbors", "area": "0.0.0.0", "adjacencies": "spine_to_leaf"},
      {"type": "bgp_sessions", "spine_to_leaf": true, "route_reflectors": ["R1", "R2"]}
    ]
  }
}
```
→ Agent benefits from:
- Checking current OSPF state before adding BGP
- Verifying reachability before declaring BGP sessions
- Testing one node before applying to all 50

### 2. Interdependent Properties

**Design goals where order matters**:

```json
"properties": [
  {"type": "reachability"},              // Foundation
  {"type": "ospf_neighbors"},            // Underlay
  {"type": "bgp_sessions"}               // Overlay (depends on underlay)
]
```

A smart agent might:
1. Check if any OSPF is already configured
2. Configure OSPF on subset, verify adjacencies
3. Roll out to all nodes
4. Only then configure BGP (which needs OSPF reachability)

**Single-turn agents**: Must guess correct order, can't verify intermediate steps.  
**Multi-turn agents**: Can verify each step before proceeding.

### 3. Platform Heterogeneity

**Mixed platforms force exploration**:

```json
"topology": {
  "nodes": 35,
  "platforms": ["frr", "nokia_srlinux", "arista_ceos"]
}
```

Agent must:
- Determine which nodes are which platform (exec commands to check)
- Use platform-specific syntax (FRR vtysh vs Nokia SR Linux CLI)
- Verify configs work per-platform before rolling out

**Benefit of multi-turn**: Agent can test on one Nokia node, verify syntax, then apply to all Nokia nodes.

---

## Task Complexity Framework

### Small Task (15 nodes, 15-20 min timeout)

**Characteristics**:
- 10-15 nodes
- Single or two platforms
- 2-3 interdependent properties
- Simple topology (linear, ring, or small spine-leaf)

**Example**:
```json
{
  "task_id": "ospf_basic_15_nodes_frr",
  "topology": {"nodes": 15, "platform": "frr", "topology_type": "ring"},
  "intent": {
    "properties": [
      {"type": "reachability", "all_nodes": true},
      {"type": "ospf_neighbors", "area": "0.0.0.0"}
    ]
  }
}
```

**Why multi-turn helps**:
- Agent can configure 3 nodes, verify adjacencies work
- Check OSPF database before proceeding
- Incrementally expand to all nodes

**Expected behavior**: Agent completes in 10-20 turns, 5-15 minutes.

---

### Medium Task (35 nodes, 30-40 min timeout)

**Characteristics**:
- 30-40 nodes
- Two platforms (e.g., FRR + Nokia)
- 3-4 interdependent properties
- Spine-leaf topology

**Example**:
```json
{
  "task_id": "campus_network_35_nodes_mixed",
  "topology": {
    "nodes": 35,
    "platforms": ["frr", "nokia_srlinux"],
    "topology_type": "spine_leaf",
    "spine_count": 5,
    "leaf_count": 30
  },
  "intent": {
    "properties": [
      {"type": "reachability", "all_nodes": true},
      {"type": "ospf_neighbors", "area": "0.0.0.0"},
      {"type": "bgp_sessions", "spine_to_leaf": true},
      {"type": "route_advertisement", "prefix": "10.0.0.0/8"}
    ]
  }
}
```

**Why multi-turn helps**:
- Must discover which nodes are spines vs leafs
- Verify OSPF underlay before BGP overlay
- Test BGP on one spine-leaf pair before full rollout
- Check route propagation incrementally

**Expected behavior**: Agent completes in 30-50 turns, 15-30 minutes.

---

### Large Task (50+ nodes, 60 min timeout)

**Characteristics**:
- 50+ nodes
- Three platforms (FRR + Nokia + Arista)
- 5+ interdependent properties
- Complex spine-leaf with route reflectors

**Example**:
```json
{
  "task_id": "service_provider_core_50_nodes",
  "topology": {
    "nodes": 50,
    "platforms": ["frr", "nokia_srlinux", "arista_ceos"],
    "topology_type": "spine_leaf",
    "spine_count": 10,
    "leaf_count": 40
  },
  "intent": {
    "properties": [
      {"type": "reachability", "all_nodes": true},
      {"type": "ospf_neighbors", "area": "0.0.0.0"},
      {"type": "bfd_sessions", "all_ospf_neighbors": true},
      {"type": "bgp_sessions", "spine_to_leaf": true},
      {"type": "bgp_route_reflectors", "rr_nodes": ["R1", "R2", "R3"]},
      {"type": "route_advertisement", "prefix": "10.0.0.0/8"},
      {"type": "traffic_engineering", "ecmp": true}
    ]
  }
}
```

**Why multi-turn helps**:
- Massive configuration surface (50 nodes × 3 platforms)
- Must build incrementally (OSPF → BFD → BGP → RR → TE)
- Verify each layer before adding next
- Debug misconfigurations without restarting

**Expected behavior**: Agent completes in 60-100 turns, 30-60 minutes.

---

## What Agents Naturally Do in Multi-Turn

### Exploration Strategies

**Strategy 1: Incremental Rollout**
```
1. exec_command(node="R1", command="vtysh -c 'show ip ospf neighbor'")
   → Check current state
2. exec_command(node="R1", command="vtysh -c 'conf t' -c 'router ospf'...")
   → Configure first node
3. exec_command(node="R1", command="vtysh -c 'show ip ospf neighbor'")
   → Verify it worked
4. exec_command(node="R2", command="vtysh -c 'conf t' -c 'router ospf'...")
   → Roll out to second node
... repeat ...
N. submit()
```

**Strategy 2: Batch Then Verify**
```
1. exec_command(node="R1", command="vtysh -c 'conf t' ...")
2. exec_command(node="R2", command="vtysh -c 'conf t' ...")
... configure all nodes ...
25. exec_command(node="R1", command="vtysh -c 'show ip ospf neighbor'")
26. exec_command(node="R2", command="vtysh -c 'show ip ospf neighbor'")
... verify all nodes ...
50. submit()
```

**Strategy 3: Pilot-then-Scale**
```
1. exec_command(node="R1", command="vtysh -c 'show version'")
   → Discover platform
2. exec_command(node="R1", command="vtysh -c 'conf t' ...")
   → Test config on pilot node
3. exec_command(node="R1", command="vtysh -c 'show ip ospf neighbor'")
   → Verify pilot
4-20. exec_command(node="R2" through "R15", ...)
   → Apply to all FRR nodes with same syntax
21. submit()
```

**No strategy is prescribed - agent chooses based on its reasoning.**

---

## Single-Agent vs Multi-Agent Differentiation

### What Creates Natural Differentiation

**Parallel Subtasks** (implicitly present in goal):
```json
"properties": [
  {"type": "ospf_neighbors", "nodes": ["R1" .. "R25"]},  // Independent
  {"type": "bgp_sessions", "nodes": ["R26" .. "R50"]}   // Independent
]
```

**Single-Agent**:
- Configures OSPF on R1-R25 sequentially
- Then configures BGP on R26-R50 sequentially
- Time: T_ospf + T_bgp

**Multi-Agent**:
- OSPF Agent: Configures R1-R25 in parallel with...
- BGP Agent: Configures R26-R50
- Time: max(T_ospf, T_bgp)
- Speedup: ~2x if independent

**The task doesn't need to specify parallelism - it emerges from the goal structure.**

### Diagnosing vs Executing

**Implicit in complex tasks**:
```json
{
  "properties": [
    {"type": "bgp_sessions", "full_mesh": true},
    {"type": "route_advertisement", "prefix": "10.0.0.0/8"}
  ]
}
```

**Single-Agent** (serial pipeline):
1. Diagnose: Check current BGP state
2. Plan: Formulate config changes
3. Execute: Apply configs
4. Verify: Check routes learned
5. Repeat until success or timeout

**Multi-Agent** (parallel pipeline):
- Diagnostic Agent: Continuously checks `show bgp summary`
- Planning Agent: Generates configs based on diagnostic feedback
- Execution Agent: Applies configs from planning agent
- Verification Agent: Validates route propagation

**Speedup from pipelining**: Diagnosis happens concurrently with execution.

**Again, no task modification needed - emerges from multi-agent orchestration.**

---

## Metrics That Reveal Strategy Differences

### Exploration Efficiency

```python
exploration_efficiency = config_commands / total_commands
```

**High efficiency** (0.8+): Agent makes few diagnostic checks, mostly config commands  
**Low efficiency** (0.3-): Agent extensively explores before each config change

**Neither is inherently better** - depends on task complexity:
- Simple tasks: High efficiency is good (don't over-verify)
- Complex tasks: Low efficiency may be necessary (diagnose before acting)

### Turn Distribution

```python
turns_per_node = total_turns / num_nodes
```

**Low turns/node** (1-2): Agent configures in batches, minimal per-node verification  
**High turns/node** (5+): Agent incrementally tests each node

### Time Efficiency

```python
time_per_property = total_time / properties_passed
```

Compares how long different agents take to achieve same correctness score.

---

## Task Design Checklist

Before releasing a multi-turn task:

- [ ] **Complexity Justified**: Too complex for reliable one-shot? (30+ nodes or 4+ interdependent properties)
- [ ] **Exploration Benefit**: Does checking intermediate state help? (interdependent properties)
- [ ] **Platform Diversity**: Mixed platforms force syntax discovery? (2+ platforms ideal)
- [ ] **Incremental Testable**: Can agent verify partial progress? (properties can be checked individually)
- [ ] **Time Budget**: 60 min timeout sufficient for 50-100 turns? (adjust based on complexity)
- [ ] **Repeatable**: Same difficulty across runs? (no randomness in evaluation)
- [ ] **Clear Goals**: Properties are unambiguous? (agent knows what success looks like)

---

## Example Task Suite

### Task 1: "Campus Baseline" (Easy)
- **Nodes**: 15 FRR
- **Properties**: Reachability + OSPF
- **Time**: 20 min
- **Purpose**: Baseline multi-turn capability

### Task 2: "Mixed Platform Deployment" (Medium)
- **Nodes**: 35 (FRR + Nokia)
- **Properties**: Reachability + OSPF + BGP sessions
- **Time**: 35 min
- **Purpose**: Platform heterogeneity, incremental verification

### Task 3: "Service Provider Core" (Hard)
- **Nodes**: 50 (FRR + Nokia + Arista)
- **Properties**: Reachability + OSPF + BFD + BGP + Route Reflectors + ECMP
- **Time**: 60 min
- **Purpose**: Complex interdependencies, sustained reasoning

**Run each 3-5 times** → 9-15 total runs per model → ~6-20 hours evaluation time

---

## How This Differs from Single-Turn Evaluation

| Aspect | Single-Turn | Multi-Turn |
|--------|-------------|------------|
| **Task Count** | 100+ tasks | 3-5 tasks |
| **Task Complexity** | Simple (2-10 nodes) | Complex (15-50 nodes) |
| **Evaluation Time** | ~1 hour | ~6-20 hours |
| **Agent Capability** | Breadth (many scenarios) | Depth (sustained reasoning) |
| **Failure Mode** | Wrong config → fail task | Can iterate and recover |
| **What's Tested** | Coverage of scenarios | Exploration + recovery strategies |

---

## Research Questions Enabled

1. **Exploration Strategies**: How do different agents balance exploration vs execution?
2. **Incremental Correctness**: Can agents build complex systems step-by-step?
3. **Error Recovery**: When agents make mistakes, can they diagnose and fix?
4. **Scaling Behavior**: Do agents maintain coherence as network size grows?
5. **Single vs Multi-Agent**: Does parallelism provide measurable speedup?

---

## Next Steps

1. **Generate Tasks**: Create 3-5 reference multi-turn tasks (small, medium, large)
2. **Baseline Runs**: Test with single-agent testee to calibrate difficulty
3. **Multi-Agent Runs**: Test with dagent to verify differentiation
4. **Metrics Collection**: Ensure all multi-turn metrics are captured
5. **Analysis**: Compare strategies, identify patterns


