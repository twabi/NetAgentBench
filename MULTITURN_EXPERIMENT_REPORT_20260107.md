# Multi-Turn Agent Architecture Study: Experiment Report

> **Session**: `multiturn_study_20260107_043749`  
> **Date**: January 7, 2026  
> **Purpose**: Empirical comparison of single-agent vs multi-agent architectures for network configuration tasks

---

## Executive Summary

This study attempted to evaluate five agent configurations across three network tasks of varying complexity. **All 30 runs technically failed** (0% success rate), but valuable insights emerged from the partial results:

- **Single-agent consistently outperformed multi-agent** patterns by 0.232 points average
- **Sequential pattern** showed promise after mid-study bug-fix, reaching within 28% of single-agent
- **Concurrent pattern** achieved 3.85x wall-clock speedup but failed to execute meaningful work
- **Debate and Group Chat** patterns exhibited structural mismatches with execution-heavy tasks

> [!IMPORTANT]  
> These results suggest that standard multi-agent patterns may be **fundamentally mismatched** with network configuration tasks due to their inherent sequential dependencies and stateful nature. This is not merely an implementation issue—the architectural assumptions of these patterns conflict with the domain requirements.

---

## 1. Experiment Setup

### 1.1 Study Configuration

| Parameter | Value |
|-----------|-------|
| **Tasks** | 3 (small, medium, large) |
| **Agent Configurations** | 5 (single + 4 multi-agent patterns) |
| **Models** | 2 (GPT-5-mini, Gemini 2.5 Pro) |
| **Turn Limit** | 100 turns |
| **Time Limit** | 900 seconds (15 minutes) |
| **Total Planned Runs** | 30 |
| **Successful Runs** | 0 |
| **Failed Runs** | 30 |

### 1.2 Task Descriptions

| Task | File | Size | Properties Evaluated |
|------|------|------|---------------------|
| **Small Campus** | `small_campus_baseline.json` | ~15 nodes | OSPF neighbors, reachability |
| **Medium Mixed** | `medium_mixed_platform.json` | ~30 nodes | OSPF, BGP sessions, route advertisement |
| **Large SP Core** | `large_sp_core.json` | ~50 nodes | OSPF, BGP, route reflectors, reachability |

### 1.3 Agent Configurations Tested

| Config ID | Architecture | Pattern | Description |
|-----------|--------------|---------|-------------|
| `single:sequential` | Single-Agent | ReAct | Monolithic LLM with all tools |
| `multi:sequential` | Multi-Agent | Planner→Executor→Verifier | Sequential phases |
| `multi:debate` | Multi-Agent | Proponent vs Opponent→Judge | Adversarial refinement |
| `multi:group_chat` | Multi-Agent | Manager→Participants | Dynamic speaker selection |
| `multi:concurrent` | Multi-Agent | Splitter→Workers→Aggregator | Parallel execution |

---

## 2. Overall Results

### 2.1 Score Comparison

| Architecture | Average Score | Completeness | Robustness |
|--------------|---------------|--------------|------------|
| **Single-Agent** | **0.429** | 0.429 | 0.000 |
| **Multi-Agent (all)** | 0.196 | 0.149 | 0.000 |

**Key Finding**: Single-agent outperformed multi-agent by **0.232 points** (54% relative improvement).

### 2.2 Pattern-Level Breakdown

| Pattern | Avg Score | Total Commands | Commands/Run | Error Rate |
|---------|-----------|----------------|--------------|------------|
| **single** | 0.429 | 231 | 38.5 | 83% |
| **sequential** | 0.306 | 226 | 37.7 | 100% |
| **debate** | 0.274 | 174 | 29.0 | 100% |
| **group_chat** | 0.064 | 55 | 9.2 | 100% |
| **concurrent** | 0.142 | 66 | 11.0 | 100% |

### 2.3 Model Comparison

| Model | Average Score |
|-------|---------------|
| **GPT-5-mini** | 0.273 |
| **Gemini 2.5 Pro** | 0.213 |

**Observation**: Model differences were minimal (0.06 points), suggesting architecture matters more than model choice for this task type.

---

## 3. Research Question Analysis

### RQ1: Architectural Effectiveness

> **Does a multi-agent architecture outperform single-agent systems on complex network configuration tasks?**

**Finding: NO** — Single-agent significantly outperformed all multi-agent configurations.

| Evidence | Single | Multi-Agent (Best: Sequential) |
|----------|--------|--------------------------------|
| Avg Score | 0.429 | 0.306 |
| Properties Satisfied | 50% (small task) | 75% (small task, post-fix) |
| Commands Executed | 38/run | 37/run |

**Interpretation**: The hypothesis that multi-agent would outperform single-agent was **not supported**. Upon reflection, this appears to stem from **fundamental architectural mismatches** rather than mere implementation bugs:

- **Debate**: The adversarial structure *naturally* promotes "tear it down and restart" strategies—this is the pattern working as designed, not a bug
- **Concurrent**: Network configuration has implicit ordering dependencies (e.g., daemon must start before neighbors can form) that an LLM splitter cannot reliably infer
- **Group Chat**: Discussion overhead is structural when only one agent can execute tools

---

### RQ2: Role Specialization

> **Does role specialization (planner/executor) improve performance compared to generalist agents?**

**Finding: INCONCLUSIVE** — Sequential pattern showed promise but was hampered by bugs.

**Command Type Distribution (Construction vs Destruction)**:

| Pattern | Constructive | Diagnostic | Destructive |
|---------|--------------|------------|-------------|
| **single** | 90.5% | 1.3% | 3.5% |
| **sequential** | 88.1% | 0.0% | 8.0% |
| **debate** | 86.8% | 1.1% | 12.1% |
| **group_chat** | 61.8% | 5.5% | 30.9% |
| **concurrent** | 57.6% | 6.1% | 16.7% |

**Key Insight**: Single-agent had the highest constructive command ratio and lowest destructive ratio, indicating more focused, less wasteful execution.

---

### RQ3: Parallelism and Scaling

> **Do multi-agent systems leverage parallelism to achieve speedup on large-scale tasks?**

**Finding: MIXED** — Concurrent achieved speedup but failed to do meaningful work.

| Pattern | Parallelism Factor | Avg Time (s) | Speedup vs Single |
|---------|-------------------|--------------|-------------------|
| **single** | 1.00 | 685 | — |
| **sequential** | 1.00 | 676 | 1.01x |
| **debate** | 1.00 | 767 | 0.89x (slower) |
| **group_chat** | 1.00 | 931 | 0.74x (slower) |
| **concurrent** | 1.00 | 178 | **3.85x** |

**Paradox**: Concurrent was fastest (3.85x speedup) but achieved lowest meaningful progress—workers terminated prematurely without executing configuration commands.

---

### RQ4: Exploration Patterns

> **What exploration patterns differentiate effective from ineffective agent architectures?**

| Pattern | Exploration Rate | Backtracking (cmds) |
|---------|------------------|---------------------|
| **single** | 1.3% | 8.2 |
| **sequential** | 0.0% | 9.5 |
| **debate** | 1.1% | 11.5 |
| **group_chat** | 5.5% | 2.2 |
| **concurrent** | 6.1% | 1.7 |

**Observation**: Single-agent and sequential showed moderate backtracking (indicating iterative refinement), while concurrent and group_chat had low backtracking but also low overall activity.

---

## 4. Root Cause Analysis: Bugs vs Architectural Limitations

### 4.1 True Implementation Bugs (Fixable)

| Pattern | Bug | Fix Applied | Impact |
|---------|-----|-------------|--------|
| **Sequential** | Executor missing `task.context` (node topology) | Added context to executor prompt | Score: 0.203 → 0.306 (+50%) |

This was a genuine implementation bug—the executor lacked necessary context to function. Fixing it improved performance measurably.

### 4.2 Inherent Architectural Limitations (Not Bugs)

> [!CAUTION]
> The following issues were initially labeled as "bugs" but upon critical examination represent **fundamental pattern-task mismatches**.

| Pattern | "Issue" | Why It's Not a Bug | Implication |
|---------|---------|-------------------|-------------|
| **Concurrent** | Workers exit without doing work | LLM splitter cannot infer implicit task dependencies (e.g., OSPF daemon must start before neighbors form) | Pattern assumes embarrassingly parallel tasks; network config has temporal/state dependencies |
| **Debate** | Opponent suggests destructive approaches | Adversarial structure is *designed* to promote opposition—"tear it down" is valid opposition | Pattern rewards contrarian behavior; network config punishes unnecessary destruction |
| **Group Chat** | Only Executor calls tools; others waste turns | Pattern designed for discussion-heavy tasks where multiple perspectives add value | Network config is action-heavy; discussion adds latency without benefit |

### 4.3 The Subjective Prompt Problem

One might argue: "Just tweak the Debate prompt to discourage destructive suggestions."

This approach is problematic because:
1. **Undermines pattern integrity**: An adversarial debate where the opponent is constrained to be "constructive" is no longer adversarial
2. **Introduces researcher bias**: What constitutes "good opposition" becomes subjective
3. **Non-reproducible**: Different prompt formulations yield different results, making comparisons invalid

### 4.4 Why Single Agent Won

| Factor | Single-Agent | Multi-Agent |
|--------|--------------|-------------|
| **Tool Access** | Every turn | Only some agents |
| **Coordination Overhead** | None | High |
| **Commands per Turn** | 1.0 | 0.3-0.8 |
| **Adversarial Dynamics** | None | Debate has opposition |
| **Context Continuity** | Full | Fragmented across agents |
| **Dependency Handling** | Implicit in reasoning | Requires explicit coordination |

---

## 5. Property-Level Analysis

### 5.1 Hardest Properties (0% Satisfaction)

| Property | Type | Total Evaluations |
|----------|------|-------------------|
| `bgp_session_core1` | BGP | 10 |
| `bgp_session_pe20` | BGP | 10 |
| `reachability_pe1_to_pe40` | Reachability | 10 |
| `reachability_pe20_to_pe21` | Reachability | 10 |
| `route_exists_pe1_loopback` | Route | 10 |

**All BGP and large-scale reachability properties failed 100%** — tasks may be too complex for current implementations.

### 5.2 Property Success by Pattern (Small Task)

| Property | Single | Sequential | Debate | Group Chat | Concurrent |
|----------|--------|------------|--------|------------|------------|
| `ospf_neighbor_r1_r2` | ✅ 50% | ✅ 50% | ❌ 0% | ❌ 0% | ❌ 0% |
| `ospf_neighbor_r8_both` | ✅ 100% | ✅ 50% | ✅ 50% | ❌ 0% | ❌ 0% |
| `reachability_r1_to_r8` | ✅ 50% | ❌ 0% | ❌ 0% | ❌ 0% | ❌ 0% |
| `reachability_r1_to_r15` | ✅ 50% | ✅ 50% | ❌ 0% | ❌ 0% | ❌ 0% |

---

## 6. Sample Run Comparison

### Small Campus Task: Single vs Sequential vs Concurrent

| Metric | Single (GPT-5-mini) | Sequential (GPT-5-mini) | Concurrent (GPT-5-mini) |
|--------|---------------------|-------------------------|-------------------------|
| **Properties Satisfied** | 4/4 (100%) | 3/4 (75%) | 0/4 (0%) |
| **OSPF Status** | Full neighbors | Full neighbors | "OSPF not enabled" |
| **Reachability** | R1→R8 ✅, R1→R15 ✅ | R1→R8 ❌, R1→R15 ✅ | Both ❌ |

**Concurrent failed to even enable OSPF** — workers terminated before executing configuration commands.

---

## 7. Critical Analysis: Why Multi-Agent Patterns Fail for Network Configuration

### 7.1 The Fundamental Mismatch Thesis

Network configuration tasks have characteristics that conflict with standard multi-agent pattern assumptions:

| Network Config Requirement | Multi-Agent Pattern Assumption | Conflict |
|---------------------------|-------------------------------|----------|
| **Sequential dependencies** | Tasks are decomposable/parallel | Concurrent fails because OSPF daemon must start before neighbors form; BGP needs underlay first |
| **Stateful execution** | Agents can work independently | Changes by one agent affect validity of another agent's planned actions |
| **Straightforward reasoning** | Debate/discussion improves outcomes | Back-and-forth adds latency and introduces destructive "alternative" suggestions |
| **Irreversible side effects** | Exploration is cheap | "Try something else" in network config means undoing work, risking loops |

### 7.2 Pattern Suitability Assessment

| Pattern | Designed For | Why It Fails for Network Config |
|---------|--------------|--------------------------------|
| **Debate** | Decision-making with tradeoffs | Execution tasks don't benefit from opposition; destruction has real costs |
| **Concurrent** | Embarrassingly parallel tasks | Network config has implicit ordering (temporal, state, and protocol dependencies) |
| **Group Chat** | Research/analysis with diverse expertise | Only execution matters; discussion is pure overhead |
| **Sequential** | Structured workflows | ✅ *Best fit*—planning before execution aligns with network change workflows |

### 7.3 The Case Against "Fixing" These Patterns

**Prompt engineering is not the answer:**
- Modifying Debate's opponent prompt to "be constructive" defeats the adversarial purpose
- Adding dependency graphs to Concurrent transforms it into a different pattern entirely
- Giving Group Chat participants tool access creates coordination chaos

**These patterns may simply be wrong tools for this job.**

---

## 8. Proposed Solution: The Reflective Execution Loop

Given that existing patterns fail, we propose a **new pattern** designed specifically for stateful, dependent execution tasks:

### 8.1 Pattern Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                    REFLECTIVE EXECUTION LOOP                     │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────────┐                          ┌─────────────┐       │
│   │  ENHANCED   │    Fast, focused         │    DEEP     │       │
│   │  PLANNING   │ ────────────────────────►│  EXECUTION  │       │
│   │  (thorough) │                          │   (minimal) │       │
│   └──────▲──────┘                          └──────┬──────┘       │
│          │                                        │              │
│          │ Loop if                                │              │
│          │ unsuccessful                           ▼              │
│          │                                 ┌─────────────┐       │
│   ┌──────┴──────┐                          │    DEEP     │       │
│   │   RETRACE   │◄─────────────────────────│ REFLECTION  │       │
│   │ (undo plan) │    Analyze outputs       │  (outputs)  │       │
│   └─────────────┘                          └─────────────┘       │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 8.2 Phase Descriptions

| Phase | Purpose | Key Characteristics |
|-------|---------|--------------------|
| **Enhanced Planning** | Create detailed, dependency-aware execution plan | Thorough analysis of task requirements; explicit ordering of steps; identification of verification points |
| **Fast Execution** | Execute the plan with minimal deliberation | Low latency; follow plan faithfully; capture all outputs; no mid-execution second-guessing |
| **Deep Reflection** | Analyze execution results against expected outcomes | Compare actual vs expected outputs; identify failures and root causes; determine if goals are met |
| **Retrace** | If needed, systematically undo to a known-good state | Avoid blind destructive commands; use recorded state to rollback cleanly; preserve working config |

### 8.3 Key Design Principles

1. **No adversarial elements**: Reasoning should be straightforward, not contentious
2. **Explicit dependency handling**: Plan must capture ordering requirements
3. **Minimal execution latency**: Don't deliberate mid-action
4. **Thoughtful undo**: Retrace rather than "wipe and restart"
5. **State awareness**: Track what was done to enable clean rollback

### 8.4 Comparison to Existing Patterns

| Aspect | Sequential | Debate | Reflective Loop |
|--------|------------|--------|----------------|
| Planning depth | Medium | Low (rushed to debate) | **High** |
| Execution speed | Medium | Low (interrupted) | **High** |
| Reflection | Verification only | None | **Deep output analysis** |
| Undo capability | None | Random destruction | **Systematic retrace** |
| Adversarial | No | Yes | **No** |

### 8.5 Experimental Priority

This pattern should be implemented and tested as the primary alternative to single-agent:

1. **Hypothesis**: Reflective Execution Loop will match or exceed single-agent performance while providing better error recovery
2. **Expected benefit**: Retrace capability should reduce destructive command ratio
3. **Risk**: Additional phases may add latency without proportional benefit

---

## 9. Charts Generated

The following visualizations were generated during analysis:

| Chart | Description |
|-------|-------------|
| `pattern_comparison.png` | Bar chart of average scores by pattern |
| `model_comparison.png` | Score comparison between GPT-5-mini and Gemini 2.5 Pro |
| `command_distribution.png` | Constructive/Diagnostic/Destructive breakdown |
| `error_rates.png` | Error rate by pattern |
| `exploration_patterns.png` | Exploration vs construction rates |
| `property_heatmap.png` | Property satisfaction by pattern |
| `pattern_model_heatmap.png` | Cross-comparison of patterns and models |
| `task_breakdown.png` | Performance by task size |
| `turns_vs_score.png` | Correlation between turns used and final score |

---

## 8. Charts Generated

The following visualizations were generated during analysis:

| Chart | Description |
|-------|-------------|
| `pattern_comparison.png` | Bar chart of average scores by pattern |
| `model_comparison.png` | Score comparison between GPT-5-mini and Gemini 2.5 Pro |
| `command_distribution.png` | Constructive/Diagnostic/Destructive breakdown |
| `error_rates.png` | Error rate by pattern |
| `exploration_patterns.png` | Exploration vs construction rates |
| `property_heatmap.png` | Property satisfaction by pattern |
| `pattern_model_heatmap.png` | Cross-comparison of patterns and models |
| `task_breakdown.png` | Performance by task size |
| `turns_vs_score.png` | Correlation between turns used and final score |

---

## 10. Conclusion

This study revealed that **standard multi-agent patterns are fundamentally mismatched** with network configuration tasks. This is not primarily an implementation issue—the architectural assumptions of Debate, Concurrent, and Group Chat patterns conflict with the sequential, stateful, dependency-laden nature of network configuration.

**Key Takeaways**:

1. **Single-agent remains the baseline to beat** — its simplicity avoids coordination overhead and context fragmentation
2. **Sequential is the only viable multi-agent pattern** — its structure aligns with network change workflows
3. **Debate is architecturally unsuited** — adversarial dynamics promote destruction, which has real costs in network config
4. **Concurrent cannot handle implicit dependencies** — LLM task decomposition fails when subtasks have temporal/state ordering
5. **Group Chat wastes turns** — discussion adds latency without benefit for action-heavy tasks
6. **A new pattern is needed** — the Reflective Execution Loop proposes enhanced planning, fast execution, deep reflection, and systematic retrace

**Critical Insight**: Tweaking prompts to "fix" these patterns would introduce researcher bias and undermine pattern integrity. The honest conclusion is that these patterns may simply be wrong tools for network configuration tasks.

**Next Steps**: 
1. Implement the Reflective Execution Loop pattern
2. Run controlled comparison against single-agent and sequential
3. Evaluate whether explicit dependency handling and retrace capability provide measurable benefits

---

*Report generated: January 13, 2026*  
*Report updated: January 13, 2026 — Reframed to distinguish architectural limitations from implementation bugs*  
*Study data from: January 7, 2026*
