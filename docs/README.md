Welcome to the NetAgentBench / network configuration benchmark docs. **Multi-turn** workflows are the paper path; single-turn submission docs remain for legacy tooling.

## Quick Navigation

### Getting Started
- **[Getting Started Guide](GETTING_STARTED.md)** — Install stack, then pick multi-turn vs legacy flow
- **[Agentic Evaluation](AGENTIC_EVALUATION.md)** — Agent / MCP / Containerlab diagram & narrative
- **[Agent harness](../agent_harness/README.md)** — In-tree `uvicorn dagent.harness_main` for `run-task`
- **[Architecture Overview](ARCHITECTURE.md)** — System design

### User Guides
- **[Task Format Specification](TASK_FORMAT.md)** — Multi-turn + single-turn JSON tasks
- **[Submission Format Guide](SUBMISSION_FORMAT.md)** — Legacy `benchmark run` payloads
- **[CLI Usage](CLI_USAGE.md)** — `run-task`, `run`, `run-llm`, …
- **[Human Benchmark Guide](HUMAN_BENCHMARK_GUIDE.md)** — Human participants
- **[LLM Integration](LLM_INTEGRATION.md)** — Provider wiring

### Research & Tooling
- **[Research Usage](RESEARCH_USAGE.md)** — Session layouts, analyzers, rerun helper
- **[Benchmark Scripts](BENCHMARK_SCRIPTS.md)** — Shell automation matrix
- **[GPU + Containerlab Ops](GPU_SERVER_CONTAINERLAB_DEPLOYMENT.md)** — Host reference
- **[Public Release Checklist](PUBLIC_RELEASE.md)** — History rewrite + mirroring
- **[Testing Guide](TESTING.md)**, **[Troubleshooting](TROUBLESHOOTING.md)**, **[Formalization Alignment](FORMALIZATION_ALIGNMENT.md)**

### Repository Policies
- **[Security policy](../SECURITY.md)** (repo root)

## Documentation structure (selected)

```
docs/
├── AGENTIC_EVALUATION.md / PUBLIC_RELEASE.md / BENCHMARK_SCRIPTS.md
├── README.md (this index)
├── CLI_USAGE.md / RESEARCH_USAGE.md / GETTING_STARTED.md
├── GPU_SERVER_CONTAINERLAB_DEPLOYMENT.md
├── assets/                       # Diagrams consumed by docs
└── …
```

## Audience paths

### LLM / agent researchers
1. [Research Usage](RESEARCH_USAGE.md) → [Agentic Evaluation](AGENTIC_EVALUATION.md)  
2. [CLI Usage](CLI_USAGE.md) (`run-task`) → [Benchmark Scripts](BENCHMARK_SCRIPTS.md)  
3. [LLM Integration](LLM_INTEGRATION.md) → [Task Format](TASK_FORMAT.md)

### Network engineers / human benchmarks
1. [Getting Started](GETTING_STARTED.md)  
2. [Human Benchmark Guide](HUMAN_BENCHMARK_GUIDE.md)  
3. [Submission Format](SUBMISSION_FORMAT.md)

### Maintainers
1. [Architecture](ARCHITECTURE.md) + [Testing](TESTING.md)  
2. [Public Release](PUBLIC_RELEASE.md) + [Security](../SECURITY.md)

## Overview

This project couples FSM-style task definitions with Containerlab for repeatable network emulation. **Interactive studies** require both this repository and the **`agent_harness/`** HTTP runtime (or another compatible `/benchmark/solve` implementation); see **[Agentic Evaluation](AGENTIC_EVALUATION.md)** and **[`agent_harness/README.md`](../agent_harness/README.md)**.

### Highlights

- Formal property checking on emulated devices  
- JSON tasks for both modern multi-turn and legacy single-turn paths  
- Research-oriented logging + analysis tooling under `scripts/`

## Contributing to Documentation

Keep examples copy-pasteable, prefer linking to canonical CLI docs, and bump the timestamp below whenever you materially change flows.

## External resources

- [NetAgentBench preprint](https://arxiv.org/abs/2604.09678)  
- [Containerlab](https://containerlab.dev/) · [FRR](https://frrouting.org/) · [Pydantic](https://docs.pydantic.dev/)

---

**Last reviewed:** Documentation pass for multi-turn prominence + publication hygiene.

