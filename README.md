# Network Configuration Benchmark (NetAgentBench)

Formal evaluation of network configuration behaviors using Finite State Machine (FSM) structure and Containerlab emulation. Companion software to [*NetAgentBench: A State-Centric Benchmark for Evaluating Agentic Network Configuration*](https://arxiv.org/abs/2604.09678).

## Overview

This benchmark evaluates whether configurations (human, scripted, LLM-guided, or autonomous agents) satisfy stated network intent while recording execution traces suited to research analysis.

### Key features

- **Formal grounding** — FSM-oriented task definitions with deterministic evaluation pipelines
- **JSON task specs** — Topology, intent, and property checks standardized for tooling
- **Multi-turn agentic runs** — Primary research path (`benchmark run-task`), with bounded episodes and MCP-mediated lab control
- **Single-turn submissions** — Legacy/auxiliary workflows using static submissions (`benchmark run`, `benchmark run-llm`, …)
- **Containerlab integration** — Emulated routers and links for repeatable experiments

### Design philosophy

1. Task definitions remain the contracts for evaluation
2. Prefer the smallest change that solves the problem
3. Test-driven iteration for correctness-critical pieces
4. Keep infrastructure adapters swappable beyond Containerlab defaults

## Evaluation modes

| Mode | CLI | Typical tasks | Role |
|------|-----|---------------|------|
| **Multi-turn agentic** | `benchmark run-task` | [`tasks/multi_turn_v2/`](tasks/multi_turn_v2/) (changes from the earlier set: [`CHANGES.md`](tasks/multi_turn_v2/CHANGES.md)) | **Primary.** Paper-aligned interactive evaluation; requires a separately run **agent HTTP service** reachable via `--dagent-endpoint`. Use the bundled **[`agent_harness/`](agent_harness/)** (recommended) or any compatible agent. |
| **Single-turn submission** | `benchmark run`, `benchmark run-llm`, … | [`tasks/archive/`](tasks/archive/) (with the earlier multi-turn set in `tasks/archive/multi_turn/`) | **Legacy/auxiliary.** One-shot submissions and property-batch sweeps. |

Orchestration examples live under [`scripts/`](scripts/); conceptual diagram and MCP boundaries are in **[Agentic evaluation](docs/AGENTIC_EVALUATION.md)**.

## Quick Start

### Install

```bash
# Prerequisites: Docker, Containerlab, Poetry
curl -sSL https://install.python-poetry.org | python3 -
git clone https://github.com/twabi/NetAgentBench.git
cd NetAgentBench
poetry install
poetry shell
```

Configure provider secrets in `.env` (ignored by git) when using cloud LLM APIs — see **[LLM integration](docs/LLM_INTEGRATION.md)**.

### Multi-turn (recommended)

Install and start the **in-tree harness** (trimmed MCP-facing HTTP agent):

```bash
cd agent_harness && poetry install
# On headless Linux without a desktop keyring, use:
# PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring poetry install
poetry run uvicorn dagent.harness_main:app --host 0.0.0.0 --port 8000
```

This snapshot supports agent structures `sequential`, `concurrent`, `debate`, and `group_chat` in multi mode (**not** `adaptive`). Details: [`agent_harness/README.md`](agent_harness/README.md).

Then from the benchmark repo:

```bash
poetry run benchmark run-task tasks/multi_turn_v2/ccna_rip_routing_basic.json \
  --dagent-endpoint http://localhost:8000 \
  --provider openai \
  --model gpt-4o-mini \
  --turn-limit 50 \
  --time-limit 600
```

For large studies, wrapper scripts call `benchmark run-task` repeatedly (see **[Benchmark scripts](docs/BENCHMARK_SCRIPTS.md)**).

### Legacy single-turn

```bash
poetry run benchmark run tasks/archive/bgp_basic.json examples/human_submissions/bgp_2as_example.json
benchmark list-tasks
```

### Example task excerpt (BGP property)

```json
{
  "task_id": "bgp_basic_001",
  "platform": "frr",
  "topology": {
    "nodes": [
      {"name": "R1", "type": "router", "image": "frrouting/frr:latest"},
      {"name": "R2", "type": "router", "image": "frrouting/frr:latest"}
    ],
    "links": [{"endpoints": ["R1:eth1", "R2:eth1"]}]
  },
  "intent": { "properties": [] }
}
```

## Documentation index

| Guide | Purpose |
|-------|---------|
| [Getting Started](docs/GETTING_STARTED.md) | Prerequisites and first notebooks |
| [Agentic Evaluation](docs/AGENTIC_EVALUATION.md) | Multi-turn setup, MCP/agent split, diagram |
| [CLI Usage](docs/CLI_USAGE.md) | `run-task`, `run`, `run-llm`, utilities |
| [Research Usage](docs/RESEARCH_USAGE.md) | Session folders, comparative studies, analyzers |
| [Benchmark Scripts](docs/BENCHMARK_SCRIPTS.md) | `scripts/*.sh` catalog |
| [LLM Integration](docs/LLM_INTEGRATION.md) | Provider keys & configuration |
| [Task Format](docs/TASK_FORMAT.md) | JSON schema reference |
| [Submission Format](docs/SUBMISSION_FORMAT.md) | Single-turn submission JSON |
| [Architecture](docs/ARCHITECTURE.md), [Formalization](docs/FORMALIZATION_ALIGNMENT.md) | Design references |
| [Public Release](docs/PUBLIC_RELEASE.md) | Mirrors, rewritten history guidance |
| [Security](SECURITY.md) | Disclosure policy |
| [Agent harness](agent_harness/README.md) | In-tree HTTP agent (`dagent.harness_main`) for `run-task` (no `adaptive` in this snapshot) |

Full index: [docs/README.md](docs/README.md)

## Architecture (FSM view)

1. **Infrastructure** — Provision Containerlab topology
2. **SUT layer** — Apply candidate configuration and probe state
3. **Controller** — Schedule evaluation, MCP bridges, telemetry

Interactive multi-turn runs add an **external agent tier** coordinating through MCP — see **[Agentic evaluation](docs/AGENTIC_EVALUATION.md)**.

## Scores

Weighted combination of completeness, robustness, syntactic validity, and efficiency metrics (defaults documented in codebase and theory notes).

## Development

```bash
poetry run pytest tests/unit/
poetry run pytest tests/integration/ -m integration   # slow; needs Containerlab
(cd agent_harness && poetry run pytest tests/unit/ -q) # harness-only (separate Poetry project)
```

## Contributing

Prefer focused pull requests with tests for behavior changes. Larger design shifts should cite discussion in issues first.

### Legacy batch LLM sweep (optional)

```bash
benchmark run-llm reachability --provider openai --model gpt-5-mini --limit 10
benchmark list-runs --limit 30
benchmark analyze gpt-5-mini,gemini-2.5-pro
```

## License

Licensed under **Apache License 2.0** — see [LICENSE](LICENSE).

## Security

See [SECURITY.md](SECURITY.md) for coordinated disclosure. Assume any historically committed secret is burned; rotate keys regardless of cleanup.

## Citation

Twabi, A., Ding, Y., Kondo, T., *NetAgentBench: A State-Centric Benchmark for Evaluating Agentic Network Configuration*, arXiv:2604.09678, 2026.  
Metadata for GitHub: [CITATION.cff](CITATION.cff).

## Contact

Open an issue at [github.com/twabi/network-benchmark](https://github.com/twabi/network-benchmark) for bugs and feature discussions.
