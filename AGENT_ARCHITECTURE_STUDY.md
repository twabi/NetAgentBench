# Agent Architecture Study: Single-Agent vs Multi-Agent Systems

## Research Positioning

### Publication Trajectory

**Paper 1 (Submitted)**: NetAgentBench - FSM-Based Benchmark Framework
- **Core Contribution**: Formal evaluation framework for network configuration agents
- **Research Question**: Can LLMs generate correct network configurations?
- **Evaluation Mode**: Single-turn (one-shot generation)
- **Key Finding**: LLMs achieve high completeness (78-85%) but catastrophic robustness gaps (<4% on OSPF)

**Paper 2 (This Work)**: Single-Agent vs Multi-Agent Architectures
- **Core Contribution**: Empirical comparison of agent architectures for network management
- **Research Question**: Which agent architectures are effective for complex network configuration tasks?
- **Evaluation Mode**: Multi-turn (interactive exploration)
- **Focus**: Architectural design patterns, role specialization, parallelism

**Paper 3 (Future)**: Memory and Context Management
- **Core Contribution**: Memory architectures for long-context network operations
- **Research Question**: How do agents maintain coherence across extended interactions?
- **Focus**: Memory management, context windows, knowledge retention

---

## Paper 2: Core Research Questions

### RQ1: Architectural Effectiveness
**Does a multi-agent architecture outperform single-agent systems on complex network configuration tasks?**

**Hypothesis**: Multi-agent systems (e.g., dagent with planner/executor roles) will outperform single-agent systems (e.g., monolithic LLM) on tasks requiring:
- Parallel exploration across multiple network segments
- Specialized expertise (routing protocols vs connectivity)
- Coordinated multi-step configuration workflows

**Null Hypothesis**: No significant difference in final score between single-agent and multi-agent systems.

**Metrics**:
- **Primary**: Final score, completeness, robustness
- **Efficiency**: Turns to completion, wall-clock time
- **Exploration**: Diagnostic vs configuration command ratio

---

### RQ2: Role Specialization Benefits
**Does role specialization (planner/executor) improve performance compared to generalist agents?**

**Hypothesis**: Agents with specialized roles (one for planning, one for execution) will:
- Make fewer failed configuration attempts
- Achieve higher robustness (better idempotency)
- Complete tasks in fewer turns through better planning

**Comparison**:
- **Generalist**: Single LLM handles all aspects (diagnosis, planning, execution)
- **Specialist**: Separate agents for planning vs execution (e.g., dagent architecture)

**Metrics**:
- **Planning Quality**: Ratio of successful commands to total commands
- **Execution Precision**: Commands with exit code 0
- **Coordination Overhead**: Communication turns between agents

---

### RQ3: Parallelism and Scaling
**Do multi-agent systems leverage parallelism to achieve speedup on large-scale tasks?**

**Hypothesis**: On tasks with >30 nodes, multi-agent systems will show:
- Faster time to completion (wall-clock)
- Reduced turns through parallel exploration
- Better handling of heterogeneous platforms (FRR + Nokia SR Linux)

**Task Categories**:
- **Small** (≤15 nodes): No expected parallelism benefit
- **Medium** (15-35 nodes): Moderate benefit from parallel exploration
- **Large** (>35 nodes): Significant speedup from parallel configuration

**Metrics**:
- **Speedup**: $\frac{T_{single}}{T_{multi}}$ (wall-clock time ratio)
- **Parallelism Factor**: $\frac{\text{commands issued}}{turns}$ (commands per turn)
- **Scaling Efficiency**: How speedup changes with network size

---

### RQ4: Exploration Strategy Emergence
**What exploration patterns differentiate effective from ineffective agent architectures?**

**Hypothesis**: Effective agents exhibit:
- **Systematic exploration**: Check reachability → verify underlay → configure overlay
- **Early validation**: Diagnostic commands precede bulk configuration
- **Error recovery**: Re-check failed segments before retry

**Analysis Methods**:
- **Pattern Mining**: Cluster agent behaviors based on tool usage sequences
- **Transition Analysis**: Model agent actions as Markov chains
- **Success Correlation**: Which patterns correlate with high scores?

**Metrics**:
- **Exploration Rate**: $\frac{n_{diagnostic}}{n_{total}}$
- **Sequence Patterns**: Common command subsequences (e.g., `show → configure → verify`)
- **Backtracking**: Commands issued after failed attempts

---

## Experimental Design

### Testee Configurations

| Testee | Architecture | Implementation | Description |
|--------|-------------|----------------|-------------|
| **GPT-4o** | Single-agent | OpenAI API | Monolithic LLM with all tools |
| **Gemini 2.0 Pro** | Single-agent | Google API | Monolithic LLM with all tools |
| **dagent (single)** | Single-agent | dagent framework | One agent with all tools |
| **dagent (multi)** | Multi-agent | dagent framework | Planner + Executor agents |

### Task Suite

**Design Goal**: Tasks where architectural differences matter.

| Size | Nodes | Platforms | Properties | Expected Differentiator |
|------|-------|-----------|------------|-------------------------|
| **Small** | 15 | FRR | Reachability + OSPF | Baseline (minimal difference) |
| **Medium** | 35 | FRR + Nokia | OSPF + BGP | Role specialization benefit |
| **Large** | 50+ | FRR + Nokia + Arista | OSPF + BGP + BFD | Parallelism benefit |

**Coverage**:
- 3 small tasks (control - should show parity)
- 3 medium tasks (test role specialization)
- 3 large tasks (test parallelism and scaling)

**Total**: 9 tasks × 4 testees = 36 benchmark runs

### Controlled Variables

**Fixed Across All Runs**:
- Convergence timeout (60s per command)
- Turn limit (50 turns)
- Time limit (30 minutes)
- Platform versions (FRR 8.5.4, Nokia SR Linux latest)

**Independent Variables**:
- Agent architecture (single vs multi)
- Task complexity (small, medium, large)
- Property types (reachability, OSPF, BGP)

**Dependent Variables**:
- Final score (completeness, robustness, syntactic validity)
- Turn efficiency (turns to completion)
- Wall-clock time
- Command success rate
- Exploration patterns

---

## Statistical Analysis Plan

### Primary Analysis: Architecture Comparison

**Paired t-test** (same tasks, different architectures):
```python
from scipy import stats

single_scores = [score for each task with single-agent]
multi_scores = [score for same task with multi-agent]

t_stat, p_value = stats.ttest_rel(single_scores, multi_scores)
# Significant if p < 0.05
```

**Effect Size** (Cohen's d):
```python
mean_diff = np.mean(multi_scores) - np.mean(single_scores)
pooled_std = np.sqrt((np.std(single_scores)**2 + np.std(multi_scores)**2) / 2)
cohens_d = mean_diff / pooled_std
# d > 0.5: medium, d > 0.8: large effect
```

### Secondary Analysis: Scaling Benefit

**Regression Analysis** (speedup vs task size):
```python
from sklearn.linear_model import LinearRegression

# Model: speedup = β0 + β1 × (num_nodes)
model.fit(num_nodes, speedup_ratios)
# Positive β1 indicates scaling benefit
```

### Qualitative Analysis: Exploration Patterns

**Sequence Mining**:
```python
from mlxtend.frequent_patterns import apriori

# Extract frequent command sequences
# Compare patterns: successful vs failed runs
# Identify architectural signatures (e.g., multi-agent shows more parallel exec)
```

---

## Threat to Validity

### Internal Validity

**Confounds**:
- **Model Variability**: LLM temperature > 0 introduces randomness
  - *Mitigation*: Run each task 3 times, report mean ± std
- **Network Convergence**: Timing variations in protocol convergence
  - *Mitigation*: Fixed convergence timeouts, same for all testees

### External Validity

**Generalizability**:
- **Platform Limitation**: Evaluation on FRR, Nokia, Arista (container-based)
  - *Limitation*: May not generalize to physical hardware or other vendors
- **Task Representativeness**: 9 tasks cover common scenarios but not exhaustive
  - *Justification*: Selected based on production network analysis (Paper 1)

### Construct Validity

**Measurement**:
- **Turn count as proxy for effort**: Valid for tool-calling LLMs
  - *Justification*: Industry standard (function-calling APIs charge per call)
- **Final score as correctness**: Validated in Paper 1
  - *Justification*: Correlates with idempotency and production readiness

---

## Expected Contributions

### Academic Contributions

1. **First comparative study** of single vs multi-agent architectures for network configuration
2. **Empirical evidence** for role specialization benefits in network automation
3. **Scaling analysis** showing when multi-agent parallelism provides advantage
4. **Exploration pattern taxonomy** for effective network configuration agents

### Industrial Contributions

1. **Architectural guidelines** for building network automation agents
2. **Task complexity thresholds** where multi-agent is cost-effective
3. **Proof of concept** for production-ready agent architectures
4. **Benchmark extension** enabling future architecture comparisons

---

## Publication Target

### Conference Options

**Tier 1**:
- **ACM SIGCOMM**: Networking focus, systems emphasis
- **USENIX NSDI**: Networked systems design
- **IEEE INFOCOM**: Networking research

**Tier 2**:
- **ACM CoNEXT**: Next-generation networks
- **IFIP Networking**: European networking conference

### Paper Structure (8 pages)

1. **Introduction** (1 page)
   - Motivation: Why agent architecture matters
   - Gap: No empirical comparison exists
   - Contribution summary

2. **Background** (0.5 pages)
   - Paper 1 recap (benchmark framework)
   - Agent architectures (single vs multi)

3. **Experimental Design** (1.5 pages)
   - Task suite (small/medium/large)
   - Testee configurations
   - Metrics and analysis methods

4. **Results** (2.5 pages)
   - RQ1: Architecture comparison
   - RQ2: Role specialization
   - RQ3: Parallelism and scaling
   - RQ4: Exploration patterns

5. **Discussion** (1.5 pages)
   - Architectural recommendations
   - When to use multi-agent
   - Exploration strategy insights

6. **Related Work** (0.5 pages)
   - Multi-agent systems
   - Network automation
   - LLM agent architectures

7. **Conclusion** (0.5 pages)
   - Summary of findings
   - Future work (Paper 3: memory)

---

## Timeline

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| **Phase 1**: Task Generation | 1 week | 9 reference tasks (small/medium/large) |
| **Phase 2**: Infrastructure | 2 weeks | Multi-turn implementation complete |
| **Phase 3**: Baseline Runs | 1 week | Single-agent benchmarks (GPT-4o, Gemini) |
| **Phase 4**: Multi-Agent Runs | 1 week | dagent (single + multi) benchmarks |
| **Phase 5**: Analysis | 2 weeks | Statistical analysis, pattern mining |
| **Phase 6**: Writing | 3 weeks | Draft → internal review → submission |

**Total**: ~10 weeks to submission

**Submission Deadline**: Target SIGCOMM or NSDI (Spring deadlines)

---

## Relationship to Multi-Turn Implementation

**Multi-turn is the evaluation platform, not the contribution.**

The multi-turn implementation documents (`MULTI_TURN_IMPLEMENTATION.md`, `MULTI_TURN_TASK_DESIGN_GUIDE.md`) are:
- **Infrastructure** enabling this study
- **Tool** for differentiation, not novel method itself
- **Validated** by ability to expose architectural differences

**Key Message**: Multi-turn complexity naturally reveals which architectures handle:
- Iterative refinement (exploration + execution)
- Parallel workflows (multi-agent advantage)
- Error recovery (robustness testing)

Single-turn benchmarks (Paper 1) measure **capability**.  
Multi-turn benchmarks (Paper 2) measure **architecture**.
