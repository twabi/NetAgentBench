# Multi-Turn Interactive Benchmark Implementation Plan

## Overview

Enhance the benchmark to support multi-turn interactions where agents can:
1. Execute commands on the live network (agent decides shell/command)
2. Check network state via exec (agent decides what to check)
3. Iterate on their configuration until satisfied
4. Explicitly **submit** when ready for evaluation

This transforms the benchmark from a one-shot submission system into an **interactive environment**.

---

## Architecture Summary

### Current Flow (One-Shot)
```
Task → Agent generates config → Submit → Provision Lab → Apply config → Evaluate → Teardown
```

### New Flow (Multi-Turn)
```
Task → Provision Lab → Agent interacts via tools → Agent calls submit() → Evaluate → Teardown
           ↑                                              |
           └──────── (loop until submit/timeout) ────────┘
```

**Key Insight**: The lab is provisioned **first** and stays alive while the agent interacts. Containerlab already supports keeping labs up.

---

## Stopping Criteria

The benchmark session ends when any of these conditions are met:

| Condition | Description | Configurable |
|-----------|-------------|--------------|
| **Submit** | Agent explicitly calls `submit()` tool | No |
| **Turn Limit** | Maximum number of tool calls (e.g., 50) | Yes |
| **Time Limit** | Wall-clock timeout (e.g., 10 minutes) | Yes |
| **Failure** | Unrecoverable error (lab crash, connection loss) | No |

**No session resumption** - when session ends, that's it. Agent had their shot.

---

## Metrics to Track

| Metric | Description |
|--------|-------------|
| **Turns to Complete** | Number of tool calls before submit |
| **Time Taken** | Wall-clock time from session start to submit |
| **Existing Scores** | Completeness, Robustness, Syntactic Validity, Efficiency |
| **Tool Usage** | Count of exec_command, submit calls |
| **Termination Reason** | submit / turn_limit / time_limit / error |

---

## Dagent Tool Integration - MCP Server Architecture

**Key Issue**: Dagent and benchmark are **separate processes** on different ports.

**Solution**: Benchmark exposes tools via **MCP (Model Context Protocol) SSE server**, dagent connects using `SSETool`.

### Architecture Flow
```
Dagent (port 8000)                    Benchmark (port 8001)
     │                                       │
     │  SSETool connects to MCP server      │
     │────────────────────────────────────>│
     │                                       │
     │  Tool call: exec_command(...)         │
     │────────────────────────────────────>│
     │                                       │
     │                            InteractiveSession.exec_command()
     │                                       │
     │  Tool result: {stdout, stderr, ...}   │
     │<────────────────────────────────────│
```

### Dagent Side (Consumer)
Dagent uses `SSETool` to connect to benchmark's MCP server:

```python
from dagent.core.component.tool.decorator import sse_tool
from dagent.core.component.tool.llm import SSETool

@sse_tool(
    url="http://localhost:8001/mcp/sse",  # Benchmark MCP server
    name="benchmark_tools"
)
class BenchmarkTools(SSETool):
    pass

# Used in agent configuration
tools = [BenchmarkTools()]
```

---

## Proposed Changes

### Component 1: Interactive Session Manager

#### [NEW] [session.py](file:///home/grimm/python_projects/benchmark/src/benchmark/session/session.py)

```python
class InteractiveSession:
    """Manages an interactive benchmark session."""
    
    def __init__(
        self,
        task: TaskDefinition,
        infrastructure: InfrastructureProvider,
        executor: CommandExecutor,
        turn_limit: int = 50,
        time_limit_seconds: float = 600.0,
    ): ...
    
    def start(self) -> SessionContext:
        """Provision lab and return session context with node info."""
        
    def exec_command(self, node: str, command: str) -> ExecResult:
        """
        Execute a command on a node via docker exec.
        Agent decides the shell (sh, vtysh, etc.) and command.
        Increments turn counter.
        """
        
    def submit(self) -> SubmitResult:
        """End session and trigger evaluation."""
        
    def get_session_status(self) -> SessionStatus:
        """Return current turn count, elapsed time, remaining limits."""
        
    @property
    def is_active(self) -> bool:
        """Check if session is still active."""
```

#### [NEW] [models.py](file:///home/grimm/python_projects/benchmark/src/benchmark/session/models.py)

```python
@dataclass
class SessionContext:
    session_id: str
    task: TaskDefinition
    topology_id: str
    nodes: List[str]           # Available nodes agent can exec on
    platform: str              # e.g., "frr", "nokia_srlinux"
    start_time: datetime
    turn_limit: int
    time_limit_seconds: float

@dataclass  
class ExecResult:
    node: str
    command: str
    stdout: str
    stderr: str
    exit_code: int
    turn_number: int
    elapsed_seconds: float

@dataclass
class SessionStatus:
    session_id: str
    turns_used: int
    turns_remaining: int
    elapsed_seconds: float
    time_remaining_seconds: float
    is_active: bool
    termination_reason: Optional[str]  # None if active

@dataclass
class SubmitResult:
    success: bool
    benchmark_result: Optional[BenchmarkResult]
    termination_reason: str
    total_turns: int
    total_time_seconds: float
```

---

### Component 2: MCP Server for Benchmark Tools

Benchmark exposes an **MCP SSE server** that provides tools to dagent.

#### [NEW] [mcp_server.py](file:///home/grimm/python_projects/benchmark/src/benchmark/session/mcp_server.py)

```python
from mcp.server import Server
from mcp.types import Tool, TextContent
from typing import Any
import uvicorn
from fastapi import FastAPI
from sse_starlette.sse import EventSourceResponse

class BenchmarkMCPServer:
    """MCP server exposing benchmark session tools."""
    
    def __init__(self, session: InteractiveSession):
        self.session = session
        self.server = Server("benchmark-tools")
        self._register_tools()
    
    def _register_tools(self):
        """Register benchmark tools with MCP server."""
        
        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            return [
                Tool(
                    name="exec_command",
                    description="Execute a command on a network node. "
                               "You decide the shell (sh, vtysh, etc.) and command. "
                               "Example: node='R1', command='vtysh -c \"show ip route\"'",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "node": {"type": "string"},
                            "command": {"type": "string"}
                        },
                        "required": ["node", "command"]
                    }
                ),
                Tool(
                    name="submit",
                    description="Submit your configuration for evaluation. "
                               "Call this when configured correctly.",
                    inputSchema={"type": "object", "properties": {}}
                ),
                Tool(
                    name="get_session_status",
                    description="Check remaining turns and time for this session.",
                    inputSchema={"type": "object", "properties": {}}
                )
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Any) -> list[TextContent]:
            if name == "exec_command":
                result = self.session.exec_command(
                    node=arguments["node"],
                    command=arguments["command"]
                )
                content = (
                    f"Exit code: {result.exit_code}\n"
                    f"Stdout:\n{result.stdout}\n"
                    f"Stderr:\n{result.stderr}"
                )
                return [TextContent(type="text", text=content)]
            
            elif name == "submit":
                result = self.session.submit()
                if result.success and result.benchmark_result:
                    score = result.benchmark_result.scores.final_score
                    text = f"Submitted. Final score: {score:.2f}"
                else:
                    text = f"Session ended: {result.termination_reason}"
                return [TextContent(type="text", text=text)]
            
            elif name == "get_session_status":
                status = self.session.get_session_status()
                text = (
                    f"Turns: {status.turns_used}/{status.turns_used + status.turns_remaining}\n"
                    f"Time: {status.elapsed_seconds:.1f}s / "
                    f"{status.elapsed_seconds + status.time_remaining_seconds:.1f}s\n"
                    f"Active: {status.is_active}"
                )
                return [TextContent(type="text", text=text)]
    
    def create_fastapi_app(self) -> FastAPI:
        """Create FastAPI app with SSE endpoint for MCP."""
        app = FastAPI()
        
        @app.get("/mcp/sse")
        async def mcp_sse_endpoint():
            return EventSourceResponse(self.server.sse_handler())
        
        return app
```

---

### Component 3: Interactive Controller

#### [NEW] [interactive_controller.py](file:///home/grimm/python_projects/benchmark/src/benchmark/interactive_controller.py)

```python
class InteractiveBenchmarkController:
    """Controller for multi-turn interactive benchmarks."""
    
    def __init__(
        self,
        infrastructure: InfrastructureProvider = None,
        executor: CommandExecutor = None,
        evaluator: PropertyEvaluator = None,
        scoring: ScoringCalculator = None,
    ): ...
    
    def run_interactive(
        self,
        task: TaskDefinition,
        dagent_endpoint: str = "http://localhost:8000",
        turn_limit: int = 50,
        time_limit_seconds: float = 600.0,
    ) -> BenchmarkResult:
        """
        Run an interactive benchmark session.
        
        1. Provision lab (stays up)
        2. Create session with tools
        3. Send task to dagent with tools
        4. Dagent agent uses tools until submit/limit
        5. Evaluate properties
        6. Calculate scores
        7. Teardown lab
        """
        ...
```

---

### Component 4: Unified CLI with Mode Switching

#### [MODIFY] [cli.py](file:///home/grimm/python_projects/benchmark/src/benchmark/cli.py)

Support both single-turn and multi-turn modes via `--mode` flag:

```bash
# Single-turn mode (current behavior - default)
benchmark run <task_file> --mode single --testee dagent --dagent-endpoint http://localhost:8000

# Multi-turn mode (new interactive mode)
benchmark run <task_file> --mode multi --testee dagent --dagent-endpoint http://localhost:8000 \
    --turn-limit 50 --time-limit 600

# Batch runs with mode
benchmark run-batch <task_dir> --mode single --testee dagent --output results/
benchmark run-batch <task_dir> --mode multi --testee dagent --output results/ \
    --turn-limit 50 --time-limit 600
```

**Default behavior**: `--mode single` (backward compatible)

**Mode-specific options**:
- `--mode single`: No additional options required
- `--mode multi`: Requires `--turn-limit` (default: 50) and `--time-limit` (default: 600)

---

## New Directory Structure

```
src/benchmark/
├── session/                    # NEW
│   ├── __init__.py
│   ├── session.py             # InteractiveSession
│   ├── models.py              # SessionContext, ExecResult, etc.
│   └── mcp_server.py          # BenchmarkMCPServer (exposes tools via MCP SSE)
├── interactive_controller.py   # NEW
└── cli.py                      # MODIFIED (add --mode single/multi)
```

**Dependencies to add**:
```toml
# pyproject.toml
[tool.poetry.dependencies]
mcp = "^1.0.0"                 # Model Context Protocol
sse-starlette = "^1.0.0"       # Server-Sent Events for FastAPI
fastapi = "^0.100.0"
uvicorn = "^0.23.0"
```

---

## Verification Plan

### Unit Tests

#### [NEW] `tests/unit/test_interactive_session.py`
- Test session lifecycle (start, active, stopped states)
- Test turn counting and turn limit enforcement
- Test time limit enforcement
- Test submit terminates session

#### [NEW] `tests/unit/test_benchmark_tools.py`
- Test ExecCommandTool returns correct ToolResult
- Test SubmitTool triggers evaluation
- Test GetSessionStatusTool returns correct status

Run with:
```bash
poetry run pytest tests/unit/test_interactive_session.py tests/unit/test_benchmark_tools.py -v
```

### Integration Tests

#### [NEW] `tests/integration/test_interactive_benchmark.py`
- Test full interactive session with mock agent
- Test session with real Containerlab (if available)

Run with:
```bash
poetry run pytest tests/integration/test_interactive_benchmark.py -v -m integration
```

### Manual Verification

1. **Start dagent server**: `uvicorn dagent.main:app --reload`

2. **Run interactive session**:
   ```bash
   poetry run benchmark run-interactive tasks/reachability/reach_2_frr_01.json \
     --dagent-endpoint http://localhost:8000 --turn-limit 10 --time-limit 300
   ```

3. **Verify metrics**: Check that turns_to_complete, time_taken are in results

---

## Implementation Order

| Phase | Component | Effort |
|-------|-----------|--------|
| 1 | Session models and `InteractiveSession` class | 1 day |
| 2 | `BenchmarkMCPServer` (MCP SSE server exposing tools) | 1 day |
| 3 | `InteractiveBenchmarkController` with MCP server startup | 1 day |
| 4 | CLI integration with `--mode single/multi` | 0.5 day |
| 5 | Dagent `SSETool` configuration for benchmark tools | 0.5 day |
| 6 | Unit tests | 1 day |
| 7 | Integration testing with dagent via MCP | 1 day |

**Total estimate**: ~6 days

**Note**: MCP server runs on separate port (e.g., 8001) from dagent (8000).

---

## Future Enhancements (Not in Scope)

- Dashboard (FastAPI + React) for leaderboard
- PyPI package release
- Result aggregation across models
- Automatic re-runs when new models are released
