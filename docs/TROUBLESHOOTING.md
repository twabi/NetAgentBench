# Troubleshooting Guide

This document provides solutions to common issues encountered when using the Network Configuration Benchmark system.

## Installation Issues

### Poetry Command Not Found

**Problem**: `poetry: command not found`

**Solution**:
```bash
# Add Poetry to PATH (add to ~/.bashrc or ~/.zshrc)
export PATH="$HOME/.local/bin:$PATH"

# Or reinstall Poetry
curl -sSL https://install.python-poetry.org | python3 -
```

### Module Not Found Errors

**Problem**: `ModuleNotFoundError: No module named 'benchmark'`

**Solution**:
```bash
# Make sure dependencies are installed
poetry install

# Make sure you're in Poetry environment
poetry shell
# OR use poetry run
poetry run python your_script.py
```

### Import Errors

**Problem**: Import errors when running scripts

**Solution**:
```bash
# Check that the package is installed
poetry show network-config-benchmark

# Reinstall if needed
poetry install
```

## Docker Issues

### Docker Permission Denied

**Problem**: `permission denied while trying to connect to the Docker daemon socket`

**Solution**:
```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Log out and back in, or:
newgrp docker

# Verify
docker ps
```

### Docker Not Running

**Problem**: `Cannot connect to the Docker daemon`

**Solution**:
```bash
# Check Docker status
sudo systemctl status docker

# Start Docker
sudo systemctl start docker

# Enable Docker on boot
sudo systemctl enable docker
```

### Too Many Containers Running

**Problem**: Many containers from previous runs

**Solution**:
```bash
# Use cleanup script
python scripts/cleanup_benchmark_networks.py

# Or manually
sudo containerlab destroy --all
docker ps -a | grep clab | awk '{print $1}' | xargs docker rm -f
```

## Containerlab Issues

### Containerlab Not Found

**Problem**: `clab: command not found`

**Solution**:
```bash
# Install Containerlab
bash -c "$(curl -sL https://get.containerlab.dev)"

# Verify installation
sudo clab version
```

### Containerlab Permission Denied

**Problem**: Containerlab requires sudo access

**Solution**:
```bash
# Containerlab requires sudo for network operations
# This is expected behavior

# Run commands with sudo
sudo clab version
```

### Subnet Already in Use

**Problem**: `Error: subnet already in use` when creating topology

**Solution**:
```bash
# Clean up orphaned networks
python scripts/cleanup_benchmark_networks.py

# Or manually remove networks
docker network ls | grep bench_ | awk '{print $1}' | xargs docker network rm

# Verify cleanup
docker network ls | grep bench_
```

### Containerlab Cleanup Issues

**Problem**: Docker networks not cleaned up after teardown

**Solution**:
The system automatically cleans up Docker networks, but if you encounter issues:

```bash
# Manual cleanup
python scripts/cleanup_benchmark_networks.py

# Check for orphaned networks
docker network ls | grep bench_

# Remove specific network
docker network rm <network_name>
```

**Note**: The `--cleanup` flag in `clab destroy` only removes lab directories, not Docker networks. The system handles network cleanup automatically.

## Benchmark Execution Issues

### Task Not Found

**Problem**: `Task not found: <task_id>`

**Solution**:
```bash
# List available tasks
benchmark list-tasks

# Verify task file exists
ls tasks/
ls benchmark-tasks/property_types/*/tasks/

# Check task repository path
echo $BENCHMARK_TASK_REPO
```

### Submission Validation Failed

**Problem**: Submission validation errors

**Solution**:
```bash
# Check submission format
cat submission.json

# Verify against task
benchmark show-task <task_id>

# Check required fields:
# - task_id (must match existing task)
# - testee_id (unique identifier)
# - testee_type (llm, human, baseline, ml)
# - approach.commands (array of node commands)
```

### Invalid Node Name

**Problem**: `Node 'R1' not found in topology`

**Solution**:
```bash
# Check task topology
benchmark show-task <task_id>

# Ensure node names in submission match task exactly
# Case-sensitive!
```

### Command Execution Failed

**Problem**: Commands fail during execution

**Solution**:
```bash
# Check command syntax for platform
# FRR uses vtysh commands
vtysh -c 'show version'

# Test commands manually
docker exec -it <container_name> <command>

# Verify platform matches task
benchmark show-task <task_id>
```

## Property Evaluation Issues

### JSON Parser Failed

**Problem**: JSON parsing errors

**Solution**:
```bash
# Check command output format
# Ensure command produces valid JSON

# Test JSONPath expression
# Use online JSONPath tester

# Verify expected_value type matches
# String vs number vs boolean
```

### Regex Parser Failed

**Problem**: Regex pattern not matching

**Solution**:
```bash
# Escape special characters in pattern
# Use \\. for literal dot
# Use .* for any characters

# Test regex pattern separately
python -c "import re; print(re.search('pattern', 'text'))"
```

### Text Parser Failed

**Problem**: Text not found in output

**Solution**:
```bash
# Check exact text match
# Case-sensitive!
# Include whitespace if needed

# Test command output manually
docker exec -it <container_name> <command>
```

## LLM Integration Issues

### API Key Not Found

**Problem**: `OPENAI_API_KEY not found` or similar

**Solution**:
```bash
# Check .env file exists
cat .env

# Verify API key is set
echo $OPENAI_API_KEY

# Add to .env file
echo "OPENAI_API_KEY=sk-..." >> .env
```

### API Key Invalid

**Problem**: API authentication errors

**Solution**:
```bash
# Verify API key is valid
# Check API key hasn't expired
# Ensure sufficient API credits

# Test API key manually
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

### LLM Response Parsing Failed

**Problem**: Cannot parse LLM response

**Solution**:
```bash
# Check LLM response format
# Ensure response contains valid commands
# Check parser configuration

# Enable verbose logging
benchmark run ... --verbose
```

## Test Issues

### Tests Hang or Timeout

**Problem**: Tests hang indefinitely

**Solution**:
```bash
# Check Docker is running
docker ps

# Check Containerlab
sudo clab version

# Clean up orphaned containers
python scripts/cleanup_benchmark_networks.py

# Increase timeout if network is slow
# Edit test file timeout values
```

### Address Already in Use

**Problem**: `Address already in use` errors

**Solution**:
```bash
# Clean up all containers
python scripts/cleanup_benchmark_networks.py

# Check no containers running
docker ps

# Check for orphaned networks
docker network ls
```

### Test Failures with Permission Denied

**Problem**: Permission errors during tests

**Solution**:
```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Log out and back in
# Or use newgrp
newgrp docker
```

## Performance Issues

### Slow Benchmark Execution

**Problem**: Benchmarks take too long

**Solution**:
```bash
# Check system resources
docker stats

# Close other applications
# Increase convergence timeout if needed
# Check network connectivity
```

### High Memory Usage

**Problem**: System running out of memory

**Solution**:
```bash
# Clean up containers
python scripts/cleanup_benchmark_networks.py

# Check container memory usage
docker stats

# Limit concurrent benchmarks
# Run benchmarks sequentially
```

### Disk Space Issues

**Problem**: Running out of disk space

**Solution**:
```bash
# Clean up Docker resources
docker system prune -a

# Remove old results
rm -rf results/runs/old_runs/

# Check disk usage
df -h
```

## Results and Storage Issues

### Results Not Saved

**Problem**: Results not appearing in results directory

**Solution**:
```bash
# Check results directory exists
ls results/runs/

# Check write permissions
ls -la results/

# Verify output directory
echo $BENCHMARK_RESULTS_DIR

# Check for errors in logs
benchmark run ... --verbose
```

### Cannot Load Results

**Problem**: Cannot load or view results

**Solution**:
```bash
# Verify result file exists
ls results/runs/<task_id>/<run_id>.json

# Check file format
cat results/runs/<task_id>/<run_id>.json | jq .

# Verify JSON is valid
python -m json.tool results/runs/<task_id>/<run_id>.json
```

## Getting Help

### Enable Verbose Logging

```bash
# Enable detailed logging
benchmark run ... --verbose

# Set log level
export BENCHMARK_LOG_LEVEL=DEBUG
```

### Check System Status

```bash
# Check Docker
docker ps
docker network ls

# Check Containerlab
sudo clab version
sudo clab inspect --all

# Check Python environment
poetry show
poetry run python --version
```

### Common Commands

```bash
# Clean up everything
python scripts/cleanup_benchmark_networks.py

# List tasks
benchmark list-tasks

# Show task details
benchmark show-task <task_id>

# List runs
benchmark list-runs

# Show result
benchmark show-result <run_id>
```

## Related Documentation

- [Getting Started](GETTING_STARTED.md) - Installation and setup
- [Testing Guide](TESTING.md) - Running and writing tests
- [CLI Usage](CLI_USAGE.md) - Command-line interface reference

---

**Last Updated**: Phase 12 - Documentation Consolidation

