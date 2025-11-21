# Documentation Index

Welcome to the Network Configuration Benchmark documentation. This guide will help you understand, use, and contribute to the benchmark system.

## Quick Navigation

### Getting Started
- **[Getting Started Guide](GETTING_STARTED.md)** - Installation, setup, and first steps
- **[Architecture Overview](ARCHITECTURE.md)** - System design and components

### User Guides
- **[Task Format Specification](TASK_FORMAT.md)** - How to define benchmark tasks
- **[Submission Format Guide](SUBMISSION_FORMAT.md)** - How to create submissions
- **[CLI Usage](CLI_USAGE.md)** - Command-line interface reference
- **[Human Benchmark Guide](HUMAN_BENCHMARK_GUIDE.md)** - Guide for human participants
- **[LLM Integration](LLM_INTEGRATION.md)** - LLM provider setup and usage

### Research & Development
- **[Research Usage](RESEARCH_USAGE.md)** - Running studies and analyzing results
- **[Testing Guide](TESTING.md)** - Running and writing tests
- **[Troubleshooting](TROUBLESHOOTING.md)** - Common issues and solutions
- **[Formalization Alignment](FORMALIZATION_ALIGNMENT.md)** - Theory and implementation alignment

## Documentation Structure

```
docs/
├── README.md                    # This file - documentation index
├── GETTING_STARTED.md           # Quick start guide
├── ARCHITECTURE.md              # System architecture
├── TASK_FORMAT.md              # Task definition specification
├── SUBMISSION_FORMAT.md         # Submission format guide
├── CLI_USAGE.md                # CLI command reference
├── RESEARCH_USAGE.md           # Research workflows
├── HUMAN_BENCHMARK_GUIDE.md    # Human participant guide
├── LLM_INTEGRATION.md          # LLM integration guide
├── TESTING.md                  # Testing guide
├── TROUBLESHOOTING.md          # Troubleshooting guide
└── FORMALIZATION_ALIGNMENT.md  # Theory alignment
```

## For Different Audiences

### Network Engineers / Human Participants
Start with:
1. [Getting Started Guide](GETTING_STARTED.md)
2. [Human Benchmark Guide](HUMAN_BENCHMARK_GUIDE.md)
3. [Submission Format Guide](SUBMISSION_FORMAT.md)

### LLM Developers / Researchers
Start with:
1. [Getting Started Guide](GETTING_STARTED.md)
2. [LLM Integration](LLM_INTEGRATION.md)
3. [Research Usage](RESEARCH_USAGE.md)
4. [Task Format Specification](TASK_FORMAT.md)

### System Developers / Contributors
Start with:
1. [Getting Started Guide](GETTING_STARTED.md)
2. [Architecture Overview](ARCHITECTURE.md)
3. [Testing Guide](TESTING.md)
4. [Formalization Alignment](FORMALIZATION_ALIGNMENT.md)

## Project Overview

The Network Configuration Benchmark is a formal verification system for evaluating network configuration approaches using Finite State Machine (FSM) theory and Containerlab. It provides **provably correct** evaluation based on rigorous FSM formalization.

### Key Features

- ✅ **Formal verification** - Based on FSM theory with proven correctness
- ✅ **JSON-based standardization** - Structured input/output for testees
- ✅ **Task-driven evaluation** - Task definitions specify topology, intent, and evaluation procedures
- ✅ **Platform-agnostic design** - Abstracts infrastructure and configuration platforms
- ✅ **Research-ready** - Collects comprehensive metrics for publication
- ✅ **Containerlab integration** - Dynamic topology provisioning

## Contributing to Documentation

When updating documentation:

1. Keep it simple and clear
2. Include practical examples
3. Update the index if adding new sections
4. Test JSON examples are valid
5. Verify all links work

## External Resources

- [Containerlab Documentation](https://containerlab.dev/)
- [FRR Routing Suite](https://frrouting.org/)
- [Pydantic Documentation](https://docs.pydantic.dev/)

---

**Last Updated**: Phase 12 - Documentation Consolidation

