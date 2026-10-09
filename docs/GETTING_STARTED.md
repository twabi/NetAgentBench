# Getting Started with Network Configuration Benchmark

This guide will help you install, set up, and run your first benchmark.

## Prerequisites

Before you begin, ensure you have:

- **Python 3.10+** - The benchmark requires Python 3.10 or higher
- **Docker** - For running containerized network topologies
- **Containerlab** - For network topology provisioning
- **Poetry** - For Python dependency management (recommended) or pip

## Prerequisites Setup

Before installing the benchmark, you must ensure all required dependencies are properly installed and configured on your system.

### 1. Verify Docker Installation

**Docker** is critical for running containerized network topologies. Ensure Docker is installed and running:

```bash
# Check if Docker is running
sudo systemctl status docker

# If Docker is not installed, install it (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install docker.io docker-compose

# Start Docker service
sudo systemctl start docker
sudo systemctl enable docker
```

**Important**: Ensure your user is in the `docker` group so you don't need `sudo`:

```bash
# Add your user to docker group
sudo usermod -aG docker $USER

# Apply changes immediately without logging out
newgrp docker

# Verify you can run Docker without sudo
docker ps
```

### 2. Install Containerlab

**Containerlab** is critical for provisioning the network topologies. This must be installed:

```bash
# Install Containerlab
bash -c "$(curl -sL https://get.containerlab.dev)"

# Verify installation
sudo clab version
```

### 3. Install Python 3.10+ and Poetry

Ensure you have Python 3.10 or higher, then install Poetry:

```bash
# Check Python version
python3 --version  # Should be 3.10 or higher

# Install Poetry (recommended method)
curl -sSL https://install.python-poetry.org | python3 -

# Add to PATH (add to ~/.bashrc or ~/.zshrc)
export PATH="$HOME/.local/bin:$PATH"

# Verify installation
poetry --version
```

### Installing Prerequisites

#### Docker

```bash
# On Ubuntu/Debian
sudo apt-get update
sudo apt-get install docker.io docker-compose

# Start Docker service
sudo systemctl start docker
sudo systemctl enable docker
sudo systemctl status docker  # Verify it's running

# Add your user to docker group (to run without sudo)
sudo usermod -aG docker $USER
# Apply changes immediately without logging out
newgrp docker
```

#### Containerlab

```bash
# Install Containerlab
bash -c "$(curl -sL https://get.containerlab.dev)"

# Verify installation
sudo clab version
```

#### Poetry

```bash
# Install Poetry (recommended method)
curl -sSL https://install.python-poetry.org | python3 -

# Add to PATH (add to ~/.bashrc or ~/.zshrc)
export PATH="$HOME/.local/bin:$PATH"

# Verify installation
poetry --version
```

## Installation

### Step 1: Clone the Repository

Clone the benchmark repository to your machine:

```bash
# Clone the repository
git clone <repository-url> benchmark
cd benchmark

# Or if you already have the repository, navigate to it
cd /path/to/benchmark
```

### Step 2: Install Dependencies

#### Using Poetry (Recommended)

```bash
# Install all dependencies (creates virtual environment automatically)
poetry install

# This will:
# - Create .venv/ directory with virtual environment
# - Install all core dependencies (pydantic, docker, etc.)
# - Install all dev dependencies (pytest, mypy, etc.)
# - Create poetry.lock file
```

#### Using pip (Alternative)

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .
```

### Step 3: Verify Installation

```bash
# Using Poetry
poetry shell
python -c "import benchmark; print('Installation successful!')"

# Or using pip
source venv/bin/activate
python -c "import benchmark; print('Installation successful!')"
```

## Quick start (choose a lane)

- **Multi-turn (NetAgentBench-style):** start **[`agent_harness/`](../agent_harness/)** (`uvicorn dagent.harness_main:app`), then run `benchmark run-task tasks/multi_turn_v2/<task>.json …` (details: [Research usage](RESEARCH_USAGE.md), [Agentic evaluation](AGENTIC_EVALUATION.md)).
- **Single-turn (legacy classroom / regression):** craft a submission JSON and invoke `benchmark run <task> <submission>`.

### Multi-turn smoke test

```bash
poetry shell
benchmark run-task tasks/multi_turn_v2/ccna_rip_routing_basic.json \
  --dagent-endpoint http://localhost:8000 \
  --provider openai \
  --model gpt-4o-mini \
  --turn-limit 25 \
  --time-limit 600
```

### Legacy: first single-shot benchmark

1. **Inspect catalogued tasks**

```bash
benchmark list-tasks
```

2. **Author a submission**

```json
{
  "task_id": "reachability_linear_2n_R1_to_R2",
  "testee_id": "my_first_test",
  "testee_type": "human",
  "approach": {
    "description": "Configure basic IP addresses",
    "commands": [
      {
        "node": "R1",
        "commands": [
          "configure terminal",
          "interface eth0",
          "ip address 10.0.0.1/24",
          "no shutdown",
          "exit"
        ]
      }
    ]
  }
}
```

3. **Run the benchmark**:

```bash
benchmark run <task_file> <submission_file>
```

See [Submission Format](SUBMISSION_FORMAT.md).

## Development Workflow

### TDD Cycle

1. ✍️ **Write test** for functionality you want
2. ❌ **Run test** - it should fail
3. 💻 **Write minimal code** to make test pass
4. ✅ **Run test** - it should pass now
5. 🔄 **Refactor** if needed
6. ♻️ **Repeat**

### Running Tests

```bash
# Unit tests (fast)
poetry run pytest tests/unit/ -v

# Integration tests (slow, requires Containerlab)
poetry run pytest tests/integration/ -m integration -v

# All tests with coverage
poetry run pytest --cov=benchmark --cov-report=html

# View coverage report
open htmlcov/index.html  # On macOS
xdg-open htmlcov/index.html  # On Linux
```

### Code Quality

```bash
# Type checking
poetry run mypy src/benchmark/

# Linting
poetry run ruff check src/

# Formatting
poetry run black src/

# Format check (CI)
poetry run black --check src/
```

## Working with Poetry

### Activating the Environment

```bash
# Activate Poetry shell (recommended for interactive work)
poetry shell

# Now you can run commands directly
pytest tests/unit/
python -m benchmark.cli

# Or run commands without activating shell
poetry run pytest tests/unit/
poetry run python -m benchmark.cli
```

### Managing Dependencies

```bash
# Add a new core dependency
poetry add requests

# Add a new dev dependency
poetry add --group dev ipython

# Remove a dependency
poetry remove requests

# Update all dependencies
poetry update

# Show installed packages
poetry show

# Show dependency tree
poetry show --tree
```

## Common Commands

```bash
# Activate Poetry shell
poetry shell

# Run tests
poetry run pytest tests/unit/ -v

# Run CLI command
poetry run benchmark list-tasks

# Check code style
poetry run ruff check src/
poetry run black --check src/

# Format code
poetry run black src/

# Type checking
poetry run mypy src/benchmark/
```

## Troubleshooting

### Import Errors

If you get `ModuleNotFoundError: No module named 'benchmark'`:

```bash
# Make sure dependencies are installed
poetry install

# Make sure you're in Poetry environment
poetry shell
# OR use poetry run
poetry run python your_script.py
```

### Docker Issues

```bash
# Check Docker is running
docker ps

# Check Containerlab is installed
sudo clab version

# Test basic containerlab
sudo clab deploy -t example.clab.yml
```

### Permission Denied on Docker

```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Log out and back in, or:
newgrp docker
```

### Poetry Command Not Found

```bash
# Add Poetry to PATH (add to ~/.bashrc or ~/.zshrc)
export PATH="$HOME/.local/bin:$PATH"

# Or reinstall Poetry
curl -sSL https://install.python-poetry.org | python3 -
```

### Virtual Environment Location

```bash
# Poetry creates .venv in project directory
ls -la .venv/

# To use a different location, configure Poetry
poetry config virtualenvs.in-project true  # Use .venv in project (default)
poetry config virtualenvs.in-project false # Use global cache

# Show current configuration
poetry config --list
```

## Next Steps

Now that you're set up:

1. ✅ Installation complete
2. → Read [Task Format Guide](TASK_FORMAT.md) to understand task definitions
3. → Read [Submission Format Guide](SUBMISSION_FORMAT.md) to create submissions
4. → Try running a benchmark with an example task
5. → Explore [Architecture](ARCHITECTURE.md) to understand the system

## Additional Resources

- [Architecture Overview](ARCHITECTURE.md) - System design and components
- [Task Format Specification](TASK_FORMAT.md) - How to define tasks
- [Submission Format Guide](SUBMISSION_FORMAT.md) - How to create submissions
- [CLI Usage](CLI_USAGE.md) - Command-line interface reference
- [Testing Guide](TESTING.md) - Running and writing tests
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues and solutions

---

**Questions?** Check the [documentation index](README.md) or file an issue on GitHub.

