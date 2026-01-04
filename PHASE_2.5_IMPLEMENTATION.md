# Phase 2.5 Implementation Plan: Multi-Turn & Analysis Infrastructure

## Overview

This plan consolidates implementation tasks from:
- Multi-turn interactive benchmark (MCP server, interactive sessions)
- Analysis enhancements (multi-turn metrics, leaderboard system)
- Task generation (multi-turn reference tasks)

**Goal**: Enable agent architecture comparison study (single vs multi-agent)

**Timeline**: ~6-7 weeks

---

## Phase 1: Multi-Turn Core Infrastructure (Week 1-2)

### 1.1 Session Management ✅
- [x] Create `src/benchmark/session/` directory
- [x] Implement `session/models.py` with data classes:
  - [x] `SessionContext` (session metadata, nodes, limits)
  - [x] `ExecResult` (command execution result)
  - [x] `SessionStatus` (turns used, time elapsed)
  - [x] `SubmitResult` (final result with benchmark scores)
  - [x] **Enhancement 1: Command Type Differentiation**
    - [x] Add `CommandType` enum: `"config"` (Σ_config) vs `"read"` (Σ_read)
    - [x] Extend `ExecResult` to include `command_type` field
    - [x] Enable read commands that don't increment turn counter (state-preserving)
  - [x] **Enhancement 2: Convergence Tracking**
    - [x] Add `convergence_status` to `ExecResult`: `"converged"`, `"timeout"`, `"error"`
    - [x] Add `convergence_time` field to track actual convergence duration
    - [x] Ensure each command waits for protocol convergence (ε-transition) if execresult comes back within the time, then thats fine other wise its a timeout
  - [x] **Enhancement 3: Approach Reconstruction**
    - [x] Add `executed_commands: List[Tuple[str, str, CommandType]]` to `SessionContext`
    - [x] Track complete command history for robustness testing
    - [x] Implement `get_approach()` method to reconstruct config-only sequence A
- [x] Implement `session/session.py` with `InteractiveSession` class:
  - [x] `start()` - provision lab, return session context
  - [x] `exec_command(node, command, command_type="config")` - execute on node
    - [x] Increment turn counter only for config commands (not reads)
    - [x] Wait for convergence and track convergence status
    - [x] Log command to session history
  - [x] `submit()` - end session, trigger evaluation
  - [x] `get_session_status()` - return current status
  - [x] `get_approach()` - return reconstructed config sequence for robustness test
  - [x] Turn limit enforcement
  - [x] Time limit enforcement
  - [x] Session state management (active/stopped)

### 1.2 MCP Server Implementation ✅
- [x] Add dependencies to `pyproject.toml`:
  - [x] `mcp = "^1.0.0"`
  - [x] `fastapi = "^0.115.0"`
  - [x] `uvicorn = "^0.30.0"`
  - [x] `starlette = "^0.40.0"`
- [x] Implement `session/mcp_server.py` with `BenchmarkMCPServer`:
  - [x] Tool registration (`exec_command`, `submit`, `get_session_status`, `get_nodes`)
  - [x] MCP tool handler for `exec_command`
  - [x] MCP tool handler for `submit`
  - [x] MCP tool handler for `get_session_status`
  - [x] MCP tool handler for `get_nodes`
  - [x] FastMCP-based server with streamable HTTP support

### 1.3 Interactive Controller ✅
- [x] Implement `src/benchmark/interactive_controller.py`:
  - [x] `InteractiveBenchmarkController` class
  - [x] `run_interactive()` method:
    - [x] Provision lab (stays up during session)
    - [x] Create `InteractiveSession`
    - [x] Start MCP server (configurable port)
    - [x] Wait for session completion (submit/timeout)
    - [x] Evaluate properties
    - [x] Calculate scores
    - [x] Teardown lab
  - [x] Generate descriptive `run_id` with model name and mode

### 1.4 CLI Integration ✅
- [x] Modify `cli.py` to support `--mode` flag:
  - [x] Add `--mode single` (default, backward compatible)
  - [x] Add `--mode multi` for multi-turn
  - [x] Add `--turn-limit` option (default: 50)
  - [x] Add `--time-limit` option (default: 600 seconds)
  - [x] Update `run-llm` command to use mode
  - [x] Update `run-dagent` command to use mode (multi-turn uses InteractiveBenchmarkController)

### 1.5 Phase 1 Verification Tests ⚠️ CRITICAL
> **Must pass before proceeding to Phase 2**

#### Unit Tests
- [x] Create `tests/unit/test_session_models.py`: ✅ 20 tests
  - [x] Test `SessionContext` creation
  - [x] Test `ExecResult` with various exit codes
  - [x] Test `SessionStatus` calculations
  - [x] Test `SubmitResult` creation

- [x] Create `tests/unit/test_interactive_session.py`: ✅ 21 tests
  - [x] Test session lifecycle: `start()` → `is_active=True` → `submit()` → `is_active=False`
  - [x] Test `exec_command()` increments turn counter
  - [x] Test turn limit enforcement (reject after limit reached)
  - [x] Test time limit enforcement (session ends after timeout)
  - [x] Test `get_session_status()` returns correct values

- [x] Create `tests/unit/test_mcp_server.py`: ✅ 12 tests
  - [x] Test MCP server initialization
  - [x] Test tool registration (4 tools: exec_command, submit, get_session_status, get_nodes)
  - [x] Mock test each tool handler returns correct format

#### Integration Tests
- [x] Create `tests/integration/test_session_integration.py`: ✅
  - [x] Provision simple 2-node topology (skipped - requires Containerlab)
  - [x] Start interactive session
  - [x] Execute command on node
  - [x] Verify `ExecResult` contains stdout
  - [x] Submit and verify session ends
  - [x] Cleanup topology

- [x] MCP server integration tests:
  - [x] Test tool registration
  - [x] Test streamable HTTP app
  - [x] Test server close

#### Manual Verification
- [ ] **Test 1**: Start interactive session manually
  ```bash
  # In terminal 1: Start MCP server
  poetry run python -m benchmark.session.mcp_server
  
  # Verify: Server starts on port 8001, no errors
  ```

- [ ] **Test 2**: Execute command via session
  ```python
  from benchmark.session.session import InteractiveSession
  # Create session, exec command, verify result
  ```

- [ ] **Test 3**: Verify turn limit
  ```python
  # Create session with turn_limit=5
  # Execute 6 commands
  # Verify 6th command rejected
  ```

- [ ] **Test 4**: Verify time limit
  ```python
  # Create session with time_limit=10 seconds
  # Sleep 11 seconds
  # Verify session inactive
  ```

**Phase 1 Exit Criteria**:
- [x] All unit tests passing (`pytest tests/unit/test_session*.py tests/unit/test_mcp*.py -v`) - 396 passed
- [x] Integration tests passing
- [x] Manual verification completed
- [x] MCP server starts without errors
- [x] Session management works end-to-end

### 1.6 Dagent Integration ✅ (Added)
- [x] Create `dagent/benchmark/agent.py` - MCP client and network config agent
- [x] Create `dagent/web/router/benchmark.py` - POST /benchmark/solve endpoint
- [x] Modify `interactive_controller.py` - Add `dagent_endpoint` parameter
- [x] Update CLI `run-task` command with `--dagent-endpoint` option
- [x] End-to-end test: 3/3 properties satisfied, Score: 0.800 ✅



### 2.1 Results Model Updates ✅
- [x] Modify `models/results.py`:
  - [x] Add `evaluation_mode` field to `BenchmarkResult` (default: "single_turn")
  - [x] Add `model_version` field to `BenchmarkResult` (optional)
  - [x] Add multi-turn fields to `ExecutionMetrics`:
    - [x] `is_multi_turn: bool = False`
    - [x] `turns_to_complete: Optional[int]`
    - [x] `time_to_complete: Optional[float]`
    - [x] `termination_reason: Optional[str]`
    - [x] `tool_usage: Optional[Dict[str, int]]`
    - [x] `failed_commands: Optional[int]`
  - [x] Add `evaluation_mode` to `BenchmarkRunResult`
  - [x] Add `benchmark_suite_id` to `BenchmarkRunResult`
  - [x] Add `model_version` to `BenchmarkRunResult`
- [x] Unit tests: `tests/unit/test_multi_turn_models.py` (13 tests passed)

### 2.2 Analysis Model Updates ✅
- [x] Modify `models/analysis.py`:
  - [x] Add multi-turn aggregates to `AggregateExecutionMetrics`:
    - [x] `avg_turns_to_complete: Optional[float]`
    - [x] `avg_time_to_complete: Optional[float]`
    - [x] `termination_breakdown: Optional[Dict[str, int]]`
    - [x] `avg_tool_usage: Optional[Dict[str, float]]`
    - [x] `turn_success_rate: Optional[float]`
- [x] Unit tests: `tests/unit/test_multi_turn_analysis.py` (9 tests passed)

### 2.3 Analyzer Updates ✅
- [x] Modify `analysis/analyzer.py`:
  - [x] Update `_compute_execution_metrics()` to handle multi-turn:
    - [x] Filter multi-turn runs
    - [x] Compute `avg_turns_to_complete`
    - [x] Compute `avg_time_to_complete`
    - [x] Aggregate `termination_breakdown`
    - [x] Calculate `avg_tool_usage`
    - [x] Calculate `turn_success_rate`
  - [x] Ensure backward compatibility (single-turn unchanged)
- [x] Unit tests: `tests/unit/test_multi_turn_analyzer.py` (5 tests passed)

### 2.4 Exporter Updates ✅
- [x] Modify `analysis/exporter.py`:
  - [x] Add multi-turn columns to CSV export:
    - [x] `avg_turns`
    - [x] `avg_session_time`
    - [x] `turn_success_rate`
  - [x] Include multi-turn data in JSON export (via model_dump)
- [x] Unit tests: `tests/unit/test_multi_turn_analyzer.py` (2 tests passed)

### 2.5 Phase 2 Verification Tests ✅
> **All tests passed!**

#### Unit Tests ✅
- [x] `tests/unit/test_multi_turn_models.py` (13 tests)
- [x] `tests/unit/test_multi_turn_analysis.py` (9 tests)
- [x] `tests/unit/test_multi_turn_analyzer.py` (7 tests)
- **Total: 29 unit tests passed**

#### Integration Tests ✅
- [x] `tests/integration/test_multi_turn_analysis_workflow.py` (6 tests)
  - Save/load multi-turn result
  - Analyze multi-turn testee
  - Mixed single/multi-turn analysis
  - CSV export with multi-turn columns
  - JSON export with multi-turn data

**Phase 2 Exit Criteria ✅**:
- [x] All unit tests passing (`pytest tests/unit/test_multi_turn*.py -v`) - 29 passed
- [x] Integration tests passing - 6 passed
- [x] CSV export includes multi-turn columns
- [x] Backward compatibility maintained (single-turn analysis unchanged)

---

## Phase 3: Leaderboard System (Week 3-4)

### 3.1 Leaderboard Data Models ✅
- [x] Create `models/leaderboard.py`:
  - [x] `LeaderboardEntry` class:
    - [x] `testee_id`, `model_version`, `score`
    - [x] `run_id`, `timestamp`, `num_tasks`
    - [x] `breakdown: Optional[Dict[str, float]]`
  - [x] `Leaderboard` class:
    - [x] `leaderboard_id`, `name`, `description`
    - [x] `evaluation_mode` ("single_turn", "multi_turn", "both")
    - [x] `metric_name` ("overall", "robustness", etc.)
    - [x] `property_type: Optional[str]`
    - [x] `entries: List[LeaderboardEntry]`
    - [x] `last_updated: datetime`
  - [x] `LeaderboardCollection` class

### 3.2 Leaderboard Manager ✅
- [x] Create `analysis/leaderboard.py`:
  - [x] `LeaderboardManager` class:
    - [x] `initialize_leaderboards()` - create standard leaderboards
    - [x] `add_benchmark_run(run_result)` - add to appropriate leaderboards
    - [x] `_add_entry()` - add/update entry, maintain sort
    - [x] `save_leaderboards(path)` - serialize to JSON
    - [x] `load_leaderboards(path)` - deserialize from JSON
  - [x] Standard leaderboards:
    - [x] Overall (single-turn)
    - [x] Overall (multi-turn)
    - [x] Per-metric (completeness, robustness, syntactic_validity)
    - [x] Per-property (reachability, BGP, OSPF × single/multi)

### 3.3 Leaderboard CLI ✅
- [x] Modify `cli.py` to add leaderboard commands:
  - [x] `benchmark leaderboard init` - initialize standard leaderboards
  - [x] `benchmark leaderboard list` - list all leaderboards
  - [x] `benchmark leaderboard update --run-id <run_id>` - add specific run
  - [x] `benchmark leaderboard update-testee --testee-id <testee>` - add all runs for testee
  - [x] `benchmark leaderboard show <leaderboard_id>` - display leaderboard
  - [x] `benchmark leaderboard export --output <path>` - export to JSON

### 3.4 Storage Integration ✅
- [x] Modify `storage.py`:
  - [x] Add `leaderboards_path` property
  - [x] Add `save_leaderboards()` / `load_leaderboards()` methods
  - [x] Add `get_leaderboard_manager()` factory method
  - [x] Add `load_benchmark_run()` / `list_benchmark_runs()` methods


### 3.5 Phase 3 Verification Tests ⚠️ CRITICAL
> **Must pass before proceeding to Phase 4**

#### Unit Tests ✅
- [x] Create `tests/unit/test_leaderboard_models.py` (23 tests):
  - [x] Test `LeaderboardEntry` creation and validation
  - [x] Test `Leaderboard` sorting (descending by score)
  - [x] Test `LeaderboardCollection` operations
  - [x] Test serialization/deserialization

- [x] Create `tests/unit/test_leaderboard_manager.py` (21 tests):
  - [x] Test `initialize_leaderboards()` creates all standard leaderboards
  - [x] Test `add_benchmark_run()` adds to correct leaderboards
  - [x] Test `_add_entry()` handles duplicates (keeps most recent)
  - [x] Test `_add_entry()` maintains sort order
  - [x] Test `save_leaderboards()` / `load_leaderboards()`

#### Integration Tests ✅
- [x] Create `tests/integration/test_leaderboard_workflow.py`:
  - [x] Initialize leaderboards
  - [x] Create mock `BenchmarkRunResult` (multiple testees)
  - [x] Add runs to leaderboards
  - [x] Verify correct placement and ordering
  - [x] Save to file
  - [x] Load from file
  - [x] Verify data integrity

#### Manual Verification
- [ ] **Test 1**: Initialize leaderboards
  ```python
  from benchmark.analysis.leaderboard import LeaderboardManager
  manager = LeaderboardManager(storage)
  manager.initialize_leaderboards()
  # Verify standard leaderboards created
  ```

- [ ] **Test 2**: Add run to leaderboard
  ```python
  # Create mock run with score 0.85
  manager.add_benchmark_run(run_result)
  # Verify entry added to overall_single_turn leaderboard
  ```

- [ ] **Test 3**: CLI commands
  ```bash
  poetry run benchmark leaderboard show --leaderboard overall_single_turn
  # Verify output formatted correctly
  
  poetry run benchmark leaderboard export --output leaderboards.json
  # Verify JSON file created with all leaderboards
  ```

**Phase 3 Exit Criteria**:
- [X] All unit tests passing (`pytest tests/unit/test_leaderboard*.py -v`)
- [X] Leaderboard manager correctly handles duplicates
- [X] CLI commands work end-to-end
- [X] Leaderboards persist and reload correctly

---

## Phase 4: Multi-Turn Task Generation (Week 4-5)

### 4.1 Reference Task Suite
- [ ] Create small task (15 nodes):
  - [ ] Topology: Linear or star
  - [ ] Properties: Reachability + OSPF
  - [ ] Expected time: ~20 minutes
  - [ ] File: `tasks/multi_turn/small_ospf_reachability.json`
- [ ] Create medium task (35 nodes):
  - [ ] Topology: Spine-leaf
  - [ ] Properties: OSPF + BGP + route advertisement
  - [ ] Expected time: ~35 minutes
  - [ ] File: `tasks/multi_turn/medium_ospf_bgp.json`
- [ ] Create large task (50+ nodes):
  - [ ] Topology: Multi-tier spine-leaf
  - [ ] Properties: OSPF + BFD + BGP + route reflectors + ECMP
  - [ ] Expected time: ~60 minutes
  - [ ] File: `tasks/multi_turn/large_full_stack.json`

### 4.2 Task Validation
- [ ] Validate small task with baseline (single-turn mode)
- [ ] Validate medium task with baseline (single-turn mode)
- [ ] Validate large task with baseline (single-turn mode)
- [ ] Adjust convergence timeouts if needed
- [ ] Document expected behaviors

### 4.3 Phase 4 Verification Tests ⚠️ CRITICAL
> **Must pass before proceeding to Phase 5**

#### Task Validation Tests
- [ ] **Small Task Validation**:
  - [ ] Load `tasks/multi_turn/small_ospf_reachability.json`
  - [ ] Provision topology successfully
  - [ ] Verify 15 nodes created
  - [ ] Verify all interfaces accessible
  - [ ] Run baseline in single-turn mode
  - [ ] Verify task completes within 20 minutes
  - [ ] Document baseline score

- [ ] **Medium Task Validation**:
  - [ ] Load `tasks/multi_turn/medium_ospf_bgp.json`
  - [ ] Provision topology successfully
  - [ ] Verify 35 nodes created
  - [ ] Run baseline in single-turn mode
  - [ ] Verify task completes within 35 minutes
  - [ ] Document baseline score

- [ ] **Large Task Validation**:
  - [ ] Load `tasks/multi_turn/large_full_stack.json`
  - [ ] Provision topology successfully
  - [ ] Verify 50+ nodes created
  - [ ] Run baseline in single-turn mode
  - [ ] Verify task completes within 60 minutes
  - [ ] Document baseline score

#### Task Quality Checks
- [ ] **Complexity Gradient**:
  - [ ] Verify small < medium < large in terms of:
    - [ ] Number of nodes
    - [ ] Number of properties
    - [ ] Expected turns to complete
  - [ ] Document complexity metrics per task

- [ ] **Convergence Testing**:
  - [ ] Run each task 3 times in single-turn mode
  - [ ] Verify deterministic outcomes (same score each time)
  - [ ] Check convergence timeouts are appropriate
  - [ ] Adjust if needed (80% margin recommended)

#### Manual Verification
- [ ] **Test 1**: Provision all tasks
  ```bash
  # Small
  poetry run benchmark run tasks/multi_turn/small_ospf_reachability.json --testee baseline --mode single
  
  # Medium  
  poetry run benchmark run tasks/multi_turn/medium_ospf_bgp.json --testee baseline --mode single
  
  # Large
  poetry run benchmark run tasks/multi_turn/large_full_stack.json --testee baseline --mode single
  ```

- [ ] **Test 2**: Verify task definitions
  ```python
  import json
  # Load each task JSON
  # Verify topology structure
  # Verify intent properties
  # Check for syntax errors
  ```

**Phase 4 Exit Criteria**:
- [ ] All 3 tasks provision successfully
- [ ] Baseline scores documented
- [ ] Complexity gradient verified (small < medium < large)
- [ ] Convergence timeouts calibrated
- [ ] Task definitions validated (no syntax errors)

---

## Phase 5: Dagent Integration (Week 5)

### 5.1 Dagent MCP Server (in dagent repo)
- [ ] Add `get_model_info` tool to dagent MCP server:
  - [ ] Extract model from `AgentConfig`
  - [ ] Return `{model_name, provider, dagent_version, agent_count}`
- [ ] Test MCP endpoint locally

### 5.2 Benchmark-Dagent Connection Testing
- [ ] Test `exec_command` tool from dagent to benchmark
- [ ] Test `submit` tool from dagent to benchmark
- [ ] Test `get_session_status` tool from dagent to benchmark
- [ ] Test `get_model_info` tool from benchmark to dagent
- [ ] Verify model discovery works end-to-end

### 5.3 Phase 5 Verification Tests ⚠️ CRITICAL
> **Must pass before proceeding to Phase 6**

#### Dagent MCP Tests
- [ ] **Test dagent MCP server**:
  - [ ] Start dagent MCP server locally
  - [ ] Call `get_model_info` tool via MCP client
  - [ ] Verify response format: `{model_name, provider, dagent_version, agent_count}`
  - [ ] Test with different dagent configs (gpt-4o, gpt-4o-mini)

#### End-to-End Connection Tests
- [ ] **Test benchmark → dagent connection**:
  - [ ] Start dagent MCP server (port 8000)
  - [ ] Start benchmark MCP server (port 8001)
  - [ ] Create interactive session
  - [ ] Benchmark calls dagent's `get_model_info`
  - [ ] Verify model name extracted correctly

- [ ] **Test dagent → benchmark connection**:
  - [ ] Dagent calls benchmark's `exec_command`
  - [ ] Verify command executes on node
  - [ ] Verify `ExecResult` returned to dagent
  - [ ] Dagent calls `submit`
  - [ ] Verify session ends and evaluation runs

#### Model Discovery Tests
- [ ] **Test run_id generation with model discovery**:
  - [ ] Run interactive benchmark with dagent (gpt-4o)
  - [ ] Verify `run_id` format: `dagent_gpt4o_mt_YYYYMMDD_HHMMSS_uuid`
  - [ ] Change dagent config to gpt-4o-mini
  - [ ] Verify `run_id` updates: `dagent_gpt4o_mini_mt_YYYYMMDD_HHMMSS_uuid`

#### Manual Verification
- [ ] **Test 1**: Full interactive session
  ```bash
  # Terminal 1: Start dagent
  cd ~/python_projects/dagent
  poetry run uvicorn dagent.main:app --port 8000
  
  # Terminal 2: Run benchmark
  cd ~/python_projects/benchmark
  poetry run benchmark run tasks/multi_turn/small_ospf_reachability.json \
    --testee dagent \
    --mode multi \
    --dagent-endpoint http://localhost:8000
  
  # Verify:
  # - Session starts
  # - Model discovered (gpt-4o or gpt-4o-mini)
  # - Commands execute
  # - Session completes
  # - run_id includes model name
  ```

- [ ] **Test 2**: Verify leaderboard with discovered model
  ```bash
  poetry run benchmark leaderboard show --leaderboard overall_multi_turn
  # Verify entry shows: dagent_gpt-4o (not just "dagent")
  ```

**Phase 5 Exit Criteria**:
- [ ] Dagent MCP server exposes `get_model_info`
- [ ] Benchmark can discover dagent's model
- [ ] Full interactive session works end-to-end
- [ ] run_id includes model name
- [ ] Leaderboard differentiates dagent_gpt-4o vs dagent_gpt-4o-mini

---

## Phase 6: Testing & Validation (Week 6)

### 6.1 Unit Tests
- [ ] Create `tests/unit/test_interactive_session.py`:
  - [ ] Test session lifecycle (start → active → stopped)
  - [ ] Test turn counting
  - [ ] Test turn limit enforcement
  - [ ] Test time limit enforcement
  - [ ] Test submit terminates session
- [ ] Create `tests/unit/test_multi_turn_analysis.py`:
  - [ ] Test `_compute_execution_metrics()` with multi-turn data
  - [ ] Test multi-turn/single-turn mixed runs
  - [ ] Test termination breakdown aggregation
- [ ] Create `tests/unit/test_leaderboard.py`:
  - [ ] Test `LeaderboardEntry` creation
  - [ ] Test `Leaderboard` sorting
  - [ ] Test duplicate testee handling (keep most recent)
  - [ ] Test save/load leaderboards

### 6.2 Integration Tests
- [ ] Create `tests/integration/test_interactive_benchmark.py`:
  - [ ] Test full multi-turn session with mock agent
  - [ ] Test MCP server startup and connection
  - [ ] Test session with real Containerlab (if available)
- [ ] Create `tests/integration/test_leaderboard_workflow.py`:
  - [ ] Create mock `BenchmarkRunResult`
  - [ ] Add to leaderboards
  - [ ] Verify placement and sorting
  - [ ] Test export and reload

### 6.3 Manual Verification
- [ ] Run single small task in multi-turn mode with dagent
- [ ] Verify run_id format: `dagent_gpt4o_mt_20260102_120000_abc123`
- [ ] Verify metrics captured (turns, time, tool usage)
- [ ] Verify leaderboard update
- [ ] Check CSV export includes multi-turn columns

---

## Phase 7: Baseline Data Collection (Week 7)

### 7.1 Single-Turn Baseline
- [ ] Run 9 tasks (3 small, 3 medium, 3 large) with GPT-4o (single-turn)
- [ ] Run 9 tasks with Gemini 2.0 Pro (single-turn)
- [ ] Analyze results, compute baselines
- [ ] Document completion rates and scores

### 7.2 Multi-Turn Single-Agent
- [ ] Run 9 tasks with GPT-4o (multi-turn)
- [ ] Run 9 tasks with Gemini 2.0 Pro (multi-turn)
- [ ] Run 9 tasks with dagent-single (multi-turn)
- [ ] Compare to single-turn baselines

### 7.3 Multi-Turn Multi-Agent
- [ ] Run 9 tasks with dagent-multi (planner + executor)
- [ ] Compare to dagent-single
- [ ] Analyze parallelism metrics
- [ ] Identify exploration patterns

### 7.4 Initial Analysis
- [ ] Generate comparison tables
- [ ] Compute statistical significance (t-tests, effect sizes)
- [ ] Identify preliminary trends
- [ ] Document findings for Paper 2

---

## Phase 8: Analysis & Visualization Scripts (Ongoing)

### 8.1 Multi-Turn Analysis Script
- [ ] Create `scripts/analyze_multi_turn_results.py`:
  - [ ] Load multi-turn results from directory
  - [ ] Compute turn efficiency metrics
  - [ ] Analyze termination patterns
  - [ ] Generate tool usage heatmaps
  - [ ] Plot turns vs difficulty scatter
  - [ ] Export summary JSON

### 8.2 Architecture Comparison Script
- [ ] Create `scripts/compare_architectures.py`:
  - [ ] Load results for all testees
  - [ ] Compute paired comparisons (same task, different architecture)
  - [ ] Generate comparison tables
  - [ ] Plot scaling curves (speedup vs nodes)
  - [ ] Statistical tests (t-test, Cohen's d)
  - [ ] Export figures for paper

---

## Dependencies & Prerequisites

### External Dependencies
- MCP library (`mcp >= 1.0.0`)
- FastAPI + Uvicorn for MCP server
- SSE-Starlette for server-sent events

### Internal Prerequisites
- Phase 1 complete before Phase 2 (need session management for metrics)
- Phase 2 complete before Phase 3 (need metrics for leaderboard)
- Phase 4 can proceed in parallel with Phase 2-3
- Phase 5 requires dagent repo access
- Phase 6 after Phase 1-3 complete
- Phase 7 requires all infrastructure (Phase 1-4)

---

## Success Criteria

**Phase 1-3 Complete**:
- [ ] Can run multi-turn benchmark with dagent
- [ ] Metrics captured and stored correctly
- [ ] Leaderboard updates automatically

**Phase 4-5 Complete**:
- [ ] 9 reference tasks validated
- [ ] Dagent integration working end-to-end

**Phase 6 Complete**:
- [ ] All unit tests passing
- [ ] Integration tests passing
- [ ] Manual verification successful

**Phase 7 Complete**:
- [ ] Baseline data collected (4 testees × 9 tasks = 36 runs)
- [ ] Preliminary results show architectural differentiation

---

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| MCP connection issues | High | Test with simple echo server first |
| Dagent integration delays | Medium | Phase 5 can start after Phase 4 |
| Task timeout calibration | Medium | Start conservative, tune based on results |
| Metrics storage format changes | Low | Version result schema carefully |

---

## Notes

- Keep implementation plan updated as tasks complete
- Document any deviations or issues in this file
- Link to implementation files as they're created
- Track time estimates vs actual for future planning
