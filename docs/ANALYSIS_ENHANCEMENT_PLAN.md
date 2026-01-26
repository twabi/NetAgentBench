# Analysis Infrastructure Enhancement Plan

## Overview

This plan enhances the analysis infrastructure to support:
1. **Multi-turn evaluation metrics** (turns to complete, tool usage, session time)
2. **Leaderboard system** (track model performance across single/multi-turn evaluations)

Current system tracks scores and timing but lacks:
- Multi-turn specific metrics
- Evaluation mode differentiation (single vs multi-turn)
- Leaderboard tracking and ranking

---

## Part 1: Multi-Turn Metrics

### Required New Metrics

### 1. New Metrics to Track

#### Session-Level Metrics
- `turns_to_complete`: Number of tool calls before submit
- `time_to_complete`: Wall-clock time from session start to submit
- `termination_reason`: `"submit"` | `"turn_limit"` | `"time_limit"` | `"error"`
- `tool_usage_breakdown`: Count of each tool call type (`exec_command`, `submit`, `get_session_status`)

#### Turn-Level Metrics  
- `turns_per_property`: Avg turns needed per property type (reachability, BGP, OSPF)
- `failed_turns`: Commands that resulted in non-zero exit codes
- `convergence_detection_turns`: Number of turns before network converges (if agent checks)

#### Efficiency Metrics
- `turns_vs_baseline`: Comparison to single-turn baseline
- `time_efficiency`: Time per valid configuration applied
- `exploration_efficiency`: Ratio of successful commands to total commands

---

### 2. Data Model Updates

#### [MODIFY] [models/results.py](file:///home/grimm/python_projects/benchmark/src/benchmark/models/results.py)

Add multi-turn metrics to `ExecutionMetrics`:

```python
class ExecutionMetrics(BaseModel):
    # Existing fields...
    infrastructure_provision_time: float
    config_execution_time: float
    convergence_time: float
    evaluation_time: float
    total_time: float
    
    # NEW: Multi-turn specific metrics
    is_multi_turn: bool = Field(False, description="Whether this was a multi-turn session")
    turns_to_complete: Optional[int] = Field(None, description="Number of tool calls before submit")
    time_to_complete: Optional[float] = Field(None, description="Wall-clock session time (seconds)")
    termination_reason: Optional[str] = Field(None, description="How session ended")
    tool_usage: Optional[Dict[str, int]] = Field(None, description="Count per tool type")
    failed_commands: Optional[int] = Field(None, description="Commands with non-zero exit code")
```

#### [MODIFY] [models/analysis.py](file:///home/grimm/python_projects/benchmark/src/benchmark/models/analysis.py)

Add aggregations for multi-turn metrics:

```python
class AggregateExecutionMetrics(BaseModel):
    # Existing fields...
    avg_infrastructure_provision_time: float
    avg_config_execution_time: float
    avg_convergence_time: float
    avg_evaluation_time: float
    avg_total_time: float
    
    # NEW: Multi-turn aggregates
    avg_turns_to_complete: Optional[float] = Field(None, description="Avg turns before submit")
    avg_time_to_complete: Optional[float] = Field(None, description="Avg session time")
    termination_breakdown: Optional[Dict[str, int]] = Field(
        None, description="Count of each termination reason"
    )
    avg_tool_usage: Optional[Dict[str, float]] = Field(None, description="Avg calls per tool type")
    turn_success_rate: Optional[float] = Field(None, description="Ratio of successful commands")
```

---

### 3. Analyzer Updates

#### [MODIFY] [analysis/analyzer.py](file:///home/grimm/python_projects/benchmark/src/benchmark/analysis/analyzer.py) 

Update `_compute_execution_metrics()` to handle multi-turn:

```python
def _compute_execution_metrics(self, runs: List[BenchmarkResult]) -> AggregateExecutionMetrics:
    """Compute aggregate execution metrics from runs."""
    if not runs:
        raise ValueError("Cannot compute execution metrics for empty runs")
        
    n = len(runs)
    
    # Existing metrics
    metrics = AggregateExecutionMetrics(
        avg_infrastructure_provision_time=sum(r.metrics.infrastructure_provision_time for r in runs) / n,
        avg_config_execution_time=sum(r.metrics.config_execution_time for r in runs) / n,
        avg_convergence_time=sum(r.metrics.convergence_time for r in runs) / n,
        avg_evaluation_time=sum(r.metrics.evaluation_time for r in runs) / n,
        avg_total_time=sum(r.metrics.total_time for r in runs) / n,
    )
    
    # NEW: Multi-turn metrics (only if runs have multi-turn data)
    multi_turn_runs = [r for r in runs if r.metrics.is_multi_turn]
    
    if multi_turn_runs:
        metrics.avg_turns_to_complete = sum(
            r.metrics.turns_to_complete for r in multi_turn_runs if r.metrics.turns_to_complete
        ) / len(multi_turn_runs)
        
        metrics.avg_time_to_complete = sum(
            r.metrics.time_to_complete for r in multi_turn_runs if r.metrics.time_to_complete
        ) / len(multi_turn_runs)
        
        # Termination breakdown
        termination_counts = {}
        for r in multi_turn_runs:
            reason = r.metrics.termination_reason or "unknown"
            termination_counts[reason] = termination_counts.get(reason, 0) + 1
        metrics.termination_breakdown = termination_counts
        
        # Tool usage aggregation
        if any(r.metrics.tool_usage for r in multi_turn_runs):
            tool_totals = {}
            for r in multi_turn_runs:
                if r.metrics.tool_usage:
                    for tool, count in r.metrics.tool_usage.items():
                        tool_totals[tool] = tool_totals.get(tool, []) + [count]
            
            metrics.avg_tool_usage = {
                tool: sum(counts) / len(counts)
                for tool, counts in tool_totals.items()
            }
        
        # Turn success rate
        total_commands = sum(r.metrics.tool_usage.get("exec_command", 0) for r in multi_turn_runs if r.metrics.tool_usage)
        failed_commands = sum(r.metrics.failed_commands or 0 for r in multi_turn_runs)
        if total_commands > 0:
            metrics.turn_success_rate = 1.0 - (failed_commands / total_commands)
    
    return metrics
```

---

### 4. Comparison Analysis Enhancements

Add multi-turn specific comparisons:

```python
def compare_multi_turn_efficiency(self, testee_ids: List[str]) -> Dict[str, Any]:
    """
    Compare multi-turn efficiency between testees.
    
    Returns:
        Dict with:
        - turns_comparison: Avg turns per testee
        - time_comparison: Avg session time per testee  
        - termination_patterns: How each testee terminates
        - exploration_efficiency: Command success rates
    """
    ...
```

---

### 5. Exporter Updates

#### [MODIFY] [analysis/exporter.py](file:///home/grimm/python_projects/benchmark/src/benchmark/analysis/exporter.py)

Add multi-turn columns to CSV exports:

```python
def _export_testee_csv(self, analysis: AnalysisResult, file_path: Path):
    """Export testee analysis to CSV"""
    # ...existing code...
    
    # Add multi-turn columns to header
    writer.writerow([
        "property_type",
        "total_tasks",
        "successful_tasks",
        "completeness",
        "robustness",
        "syntactic_validity",
        "efficiency",
        "final_score",
        # NEW
        "avg_turns",  
        "avg_session_time",
        "turn_success_rate",
    ])
    
    # Include multi-turn data in rows
    # ...
```

---

### 6. Large-Scale Analysis Script

#### [NEW] [scripts/analyze_multi_turn_results.py](file:///home/grimm/python_projects/benchmark/scripts/analyze_multi_turn_results.py)

```python
#!/usr/bin/env python3
"""
Analyze large-scale multi-turn evaluation results.

Provides insights specific to multi-turn benchmarking:
- Turn efficiency per model
- Termination pattern analysis
- Tool usage heatmaps
- Scaling behavior (turns vs task difficulty)
"""

def analyze_multi_turn_batch(results_dir: Path) -> Dict[str, Any]:
    """
    Analyze multiple multi-turn benchmark runs.
    
    Returns:
        {
            "turn_efficiency": {...},
            "termination_patterns": {...},
            "tool_usage_analysis": {...},
            "scaling_analysis": {...},
        }
    """
    ...

def plot_turns_vs_difficulty(results: List[BenchmarkResult]):
    """Plot scatter: turns_to_complete vs final_score"""
    ...

def plot_tool_usage_heatmap(testee_ids: List[str], results: Dict):
    """Heatmap showing tool usage patterns per testee"""
    ...
```

---

## Implementation Order

| Phase | Component | Effort |
|-------|-----------|--------|
| 1 | Update `ExecutionMetrics` in `models/results.py` | 0.5 day |
| 2 | Update `AggregateExecutionMetrics` in `models/analysis.py` | 0.5 day |
| 3 | Update `_compute_execution_metrics()` in `analyzer.py` | 0.5 day |
| 4 | Update CSV exporters to include multi-turn columns | 0.5 day |
| 5 | Create `analyze_multi_turn_results.py` script | 1 day |
| 6 | Add visualization functions (matplotlib/plotly) | 1 day |
| 7 | Integration testing with sample multi-turn results | 0.5 day |

**Total estimate**: ~4.5 days

---

## Verification Plan

### Unit Tests

#### [NEW] `tests/unit/test_multi_turn_analysis.py`
- Test `_compute_execution_metrics()` with multi-turn data
- Test multi-turn/single-turn mixed runs
- Test termination breakdown aggregation

Run with:
```bash
poetry run pytest tests/unit/test_multi_turn_analysis.py -v
```

### Integration Tests

#### [MODIFY] `tests/integration/test_analyzer.py`
- Add test case with multi-turn benchmark results
- Verify CSV export includes multi-turn columns

Run with:
```bash
poetry run pytest tests/integration/test_analyzer.py -v
```

### Manual Verification

1. **Generate sample multi-turn results**:
   ```bash
   # Run a few multi-turn benchmarks
   benchmark run task.json --mode multi --testee dagent --turn-limit 10
   ```

2. **Analyze results**:
   ```bash
   # Testee analysis
   benchmark analyze-testee dagent
   
   # Verify output includes:
   # - avg_turns_to_complete
   # - avg_time_to_complete
   # - termination_breakdown
   ```

3. **Check CSV export**:
   ```bash
   # Export to CSV
   benchmark export-analysis <analysis_id> --format csv
   
   # Verify columns: avg_turns, avg_session_time, turn_success_rate
   ```

4. **Run multi-turn analysis script**:
   ```bash
   python scripts/analyze_multi_turn_results.py results/ --output report.json
   ```

---

## Future Enhancements (Not in Immediate Scope)

- **Dashboard integration**: Real-time multi-turn metrics visualization
- **Learned patterns**: Identify common exploration strategies per model
- **Turn-by-turn replay**: Ability to replay agent's session step-by-step
- **Failure analysis**: Categorize why sessions hit timeout/turn-limit

---

---

## Part 2: Leaderboard System

### Current State Analysis

**Run ID Generation** (from `controller.py:98`):
```python
run_id = f"run_{int(time.time())}_{uuid.uuid4().hex[:8]}"
```

**Issues**:
- No model name in run_id
- No evaluation mode indicator  
- Not easily parseable

**Missing Metadata**:
- `BenchmarkResult`: No `evaluation_mode` or `model_version`
- `BenchmarkRunResult`: No mode tracking
- No leaderboard persistence

### Leaderboard Requirements

**Workflow**:
1. New model → Run benchmark (70 tasks single-turn)
2. Get overall score: 0.7
3. Get per-property scores (robustness: 0.5, completeness: 0.8)
4. **Add to leaderboards**: Overall, per-property, per-metric

**Categories**:
- Overall (Single-Turn / Multi-Turn)
- Per-Property (reachability, BGP, OSPF × single/multi)
- Per-Metric (completeness, robustness, syntactic_validity)

---

### 1. Enhanced Metadata

#### [MODIFY] [models/results.py](file:///home/grimm/python_projects/benchmark/src/benchmark/models/results.py)

```python
class BenchmarkResult(BaseModel):
    # Existing fields...
    run_id: str
    timestamp: datetime
    task_id: str
    testee_id: str
    testee_type: str
    
    # NEW: Evaluation mode metadata
    evaluation_mode: str = Field(
        "single_turn",
        description="Evaluation mode: 'single_turn' or 'multi_turn'"
    )
    model_version: Optional[str] = Field(
        None,
        description="Model version (e.g., 'gpt-4-turbo-2024-04-09')"
    )
```

**Also update `BenchmarkRunResult`**:
```python
class BenchmarkRunResult(BaseModel):
    # Existing...
    run_id: str
    testee_id: str
    timestamp: datetime
    
    # NEW
    evaluation_mode: str = Field("single_turn")
    benchmark_suite_id: str = Field(..., description="Suite ID (e.g., 'single_turn_v1')")
    model_version: Optional[str] = None
```

---

### 2. Improved Run ID Generation

#### [MODIFY] [controller.py](file:///home/grimm/python_projects/benchmark/src/benchmark/controller.py)

```python
def _generate_run_id(
    testee_id: str,
    evaluation_mode: str = "single_turn",
    timestamp: Optional[datetime] = None
) -> str:
    """
    Format: {testee_id}_{mode}_{timestamp}_{uuid}
    Example: gpt4_st_20260102_120000_a3f7b2c1
    """
    if timestamp is None:
        timestamp = datetime.now()
    
    ts_str = timestamp.strftime("%Y%m%d_%H%M%S")
    short_uuid = uuid.uuid4().hex[:8]
    
    clean_testee_id = testee_id.replace(" ", "_").replace("-", "_")
    mode_short = "st" if evaluation_mode == "single_turn" else "mt"
    
    return f"{clean_testee_id}_{mode_short}_{ts_str}_{short_uuid}"
```

---

### 3. Leaderboard Data Models

#### [NEW] [models/leaderboard.py](file:///home/grimm/python_projects/benchmark/src/benchmark/models/leaderboard.py)

```python
from datetime import datetime
from typing import List, Dict, Optional
from pydantic import BaseModel, Field


class LeaderboardEntry(BaseModel):
    """Single entry in a leaderboard."""
    
    testee_id: str
    model_version: Optional[str] = None
    score: float = Field(..., ge=0.0, le=1.0)
    
    # Metadata
    run_id: str
    timestamp: datetime
    num_tasks: int = Field(..., ge=0)
    breakdown: Optional[Dict[str, float]] = None


class Leaderboard(BaseModel):
    """A leaderboard for a specific category."""
    
    leaderboard_id: str
    name: str
    description: str
    
    evaluation_mode: str  # 'single_turn', 'multi_turn', or 'both'
    metric_name: str      # 'overall', 'robustness', 'completeness', etc.
    property_type: Optional[str] = None  # 'reachability', 'bgp', or None for all
    
    entries: List[LeaderboardEntry] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=datetime.now)


class LeaderboardCollection(BaseModel):
    """Collection of all leaderboards."""
    leaderboards: Dict[str, Leaderboard] = Field(default_factory=dict)
```

---

### 4. Leaderboard Manager

#### [NEW] [analysis/leaderboard.py](file:///home/grimm/python_projects/benchmark/src/benchmark/analysis/leaderboard.py)

```python
class LeaderboardManager:
    """Manages leaderboard creation and updates."""
    
    def __init__(self, storage: ResultsStorage):
        self.storage = storage
        self.collection = LeaderboardCollection()
    
    def initialize_leaderboards(self):
        """Initialize standard leaderboards."""
        # Overall
        self.collection.leaderboards["overall_single_turn"] = Leaderboard(...)
        self.collection.leaderboards["overall_multi_turn"] = Leaderboard(...)
        
        # Per-metric
        for metric in ["completeness", "robustness", "syntactic_validity"]:
            self.collection.leaderboards[f"{metric}_all"] = Leaderboard(...)
        
        # Per-property
        for prop in ["reachability", "bgp", "ospf"]:
            for mode in ["single_turn", "multi_turn"]:
                self.collection.leaderboards[f"{prop}_{mode}"] = Leaderboard(...)
    
    def add_benchmark_run(self, run_result: BenchmarkRunResult):
        """Add new run to appropriate leaderboards."""
        mode = run_result.evaluation_mode
        
        # Add to overall leaderboard
        entry = LeaderboardEntry(
            testee_id=run_result.testee_id,
            model_version=run_result.model_version,
            score=run_result.overall_average_score,
            run_id=run_result.run_id,
            timestamp=run_result.timestamp,
            num_tasks=run_result.total_tasks,
        )
        self._add_entry(f"overall_{mode}", entry)
        
        # Add to property-specific leaderboards
        for prop_type, prop_result in run_result.property_results.items():
            entry = LeaderboardEntry(
                testee_id=run_result.testee_id,
                score=prop_result.average_score,
                run_id=run_result.run_id,
                timestamp=run_result.timestamp,
                num_tasks=prop_result.total_tasks,
            )
            self._add_entry(f"{prop_type}_{mode}", entry)
        
        # Add to metric leaderboards (completeness, robustness, etc.)
        # ... (aggregate across all results)
    
    def _add_entry(self, leaderboard_id: str, entry: LeaderboardEntry):
        """Add entry and maintain sort order. Replace if testee exists and new is more recent."""
        leaderboard = self.collection.leaderboards[leaderboard_id]
        
        # Check for existing entry
        existing_idx = None
        for idx, existing in enumerate(leaderboard.entries):
            if existing.testee_id == entry.testee_id:
                existing_idx = idx
                break
        
        if existing_idx is not None:
            # Replace if newer
            if entry.timestamp > leaderboard.entries[existing_idx].timestamp:
                leaderboard.entries[existing_idx] = entry
        else:
            leaderboard.entries.append(entry)
        
        # Sort by score (descending)
        leaderboard.entries.sort(key=lambda e: e.score, reverse=True)
        leaderboard.last_updated = datetime.now()
    
    def save_leaderboards(self, output_path: str):
        """Save to JSON."""
        # ... (serialize with datetime conversion)
    
    def load_leaderboards(self, input_path: str):
        """Load from JSON."""
        # ... (deserialize with datetime conversion)
```

---

### 5. CLI Integration

#### [MODIFY] [cli.py](file:///home/grimm/python_projects/benchmark/src/benchmark/cli.py)

```bash
# Update leaderboards
benchmark leaderboard update --run-id <run_id>
benchmark leaderboard update-testee --testee-id gpt5

# View leaderboard
benchmark leaderboard show --leaderboard overall_single_turn

# Export
benchmark leaderboard export --output leaderboards.json
```

---

### 6. Updated Workflow

```bash
# 1. Run benchmark
benchmark run-batch tasks/single_turn/ \
  --testee gpt5 \
  --mode single \
  --model-version "gpt-5-turbo-2026-01-01"

# 2. Analyze (creates BenchmarkRunResult)
benchmark analyze-run <run_id>

# 3. Update leaderboards
benchmark leaderboard update --run-id <run_id>

# 4. View
benchmark leaderboard show --leaderboard overall_single_turn
```

**Example Output**:
```
=== Overall (Single-Turn) Leaderboard ===
Last Updated: 2026-01-02 19:00:00

Rank | Model         | Version    | Score | Tasks | Date
-----|---------------|------------|-------|-------|------------
1    | gpt5          | 2026-01-01 | 0.85  | 70    | 2026-01-02
2    | claude-opus-4 | 2025-12-15 | 0.82  | 70    | 2025-12-20
3    | gpt4-turbo    | 2024-04-09 | 0.75  | 70    | 2025-11-15
```

---

### 7. Dagent Model Discovery

#### Problem

When using dagent for multi-turn benchmarking, the benchmark doesn't know which LLM model dagent is configured with. The `testee_id` is "dagent", but we need to know the underlying model (e.g., "gpt-4o", "gpt-4o-mini") for meaningful leaderboard tracking.

#### Solution: Dedicated MCP Endpoint

Add a new MCP tool that benchmark can call to query dagent's model:

```python
# In dagent MCP server (to be implemented)
@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "get_model_info":
        return [TextContent(
            type="text",
            text=json.dumps({
                "model_name": "gpt-4o",
                "model_version": "2024-05-13",
                "provider": "openai"
            })
        )]
```

Benchmark calls this at session start:

```python
# In benchmark InteractiveBenchmarkController
async def run_multi_turn(...):
    # After connecting to dagent MCP
    model_info = await dagent_client.call_tool("get_model_info", {})
    model_name = model_info["model_name"]
    
    # Use in run_id generation and metadata
    run_id = _generate_run_id(
        testee_id=f"dagent_{model_name}",  # e.g., "dagent_gpt-4o"
        evaluation_mode="multi_turn"
    )
```

**Benefits**:
- Clean API separation
- Dynamic (works if dagent changes models mid-session)
- Multi-agent support (can report different models for different agents)
- No file dependencies

#### Implementation in Dagent

##### [NEW] Expose model info via MCP

```python
# In dagent, add get_model_info to available tools

class DagentMCPServer:
    def __init__(self, runtime: AgentRuntimeInterpreter):
        self.runtime = runtime
        self.config = runtime.config  # Has model info
    
    async def handle_get_model_info(self) -> Dict[str, str]:
        """Return model information for benchmark tracking."""
        # Get primary agent's model
        primary_agent = self.config.agents[0]
        
        return {
            "model_name": primary_agent.model or "unknown",
            "provider": "openai",  # Could be inferred from model name
            "dagent_version": "0.1.0",
            "agent_count": len(self.config.agents)
        }
```

##### [MODIFY] Benchmark to query model info

```python
# In benchmark InteractiveBenchmarkController

async def _discover_testee_model(self, dagent_session) -> str:
    """Discover which model dagent is using."""
    try:
        response = await dagent_session.call_tool("get_model_info", {})
        model_info = json.loads(response)
        return model_info.get("model_name", "unknown")
    except Exception as e:
        logger.warning(f"Could not discover dagent model: {e}")
        return "unknown"

async def run_multi_turn(self, task, submission):
    # Connect to dagent MCP
    dagent_session = await connect_to_dagent_mcp(...)
    
    # Discover model
    model_name = await self._discover_testee_model(dagent_session)
    
    # Generate run_id with actual model
    run_id = _generate_run_id(
        testee_id=f"dagent_{model_name}",
        evaluation_mode="multi_turn",
        timestamp=datetime.now()
    )
    # run_id: "dagent_gpt4o_mt_20260102_120000_abc123"
    
    # Store in result metadata
    result = BenchmarkResult(
        run_id=run_id,
        testee_id=f"dagent_{model_name}",
        model_version=model_name,
        evaluation_mode="multi_turn",
        ...
    )
```

#### Leaderboard Impact

With model discovery, leaderboards become more meaningful:

```
=== Overall (Multi-Turn) Leaderboard ===

Rank | Model              | Score | Tasks | Date
-----|-------------------|-------|-------|------------
1    | dagent_gpt-4o     | 0.88  | 3     | 2026-01-02
2    | dagent_gpt-4o-mini| 0.75  | 3     | 2026-01-02
3    | baseline          | 0.45  | 3     | 2025-12-01
```

Now we can track:
- **Same dagent, different models**: gpt-4o vs gpt-4o-mini
- **Multi-agent vs single-agent**: If dagent uses multiple agents, track that separately
- **Model versions**: Track performance across GPT-4o releases

---

## Combined Implementation Order

| Phase | Component | Effort |
|-------|-----------|--------|
| **Multi-Turn Metrics** | | |
| 1 | Add multi-turn fields to `ExecutionMetrics` | 0.5 day |
| 2 | Add multi-turn aggregates to `AggregateExecutionMetrics` | 0.5 day |
| 3 | Update `analyzer.py` to compute multi-turn metrics | 0.5 day |
| 4 | Update CSV exporters | 0.5 day |
| 5 | Create `analyze_multi_turn_results.py` | 1 day |
| **Leaderboard System** | | |
| 6 | Add `evaluation_mode`, `model_version` to models | 0.5 day |
| 7 | Update `_generate_run_id()` in controller | 0.5 day |
| 8 | Create `models/leaderboard.py` | 0.5 day |
| 9 | Create `analysis/leaderboard.py` | 1 day |
| 10 | Add leaderboard CLI commands | 0.5 day |
| 11 | Integration testing | 0.5 day |

**Total estimate**: ~7 days

---

## Verification Plan

### Multi-Turn Testing

```bash
# Run multi-turn benchmark
benchmark run task.json --mode multi --testee dagent --turn-limit 10

# Analyze
benchmark analyze-testee dagent

# Verify multi-turn metrics in output
```

### Leaderboard Testing

```bash
# Run with metadata
benchmark run-batch tasks/ --testee gpt5 --mode single --model-version "2026-01-01"

# Update leaderboard
benchmark leaderboard update --run-id <run_id>

# View
benchmark leaderboard show --leaderboard overall_single_turn

# Verify sorting and entry placement
```

### Unit Tests

- `tests/unit/test_multi_turn_analysis.py`: Multi-turn metric computation
- `tests/unit/test_leaderboard.py`: Leaderboard entry management, sorting, duplicate handling

### Integration Tests

- `tests/integration/test_analyzer.py`: End-to-end analysis with multi-turn results
- `tests/integration/test_leaderboard_workflow.py`: Full workflow from run to leaderboard
