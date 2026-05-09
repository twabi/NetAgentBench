# GPU Server Deployment with Containerlab

**Manual Deployment Guide for Network Benchmark + Dagent on GPU Server**

This guide provides all the technical details for manually deploying the network benchmark and dagent on a GPU server using containerlab. Containerlab runs on the host, while the benchmark executes from your existing Ubuntu container.

**Path placeholders used below** (adapt to your layout):

- `$BENCHMARK_REPO` — checkout of this benchmark repository  
- `$DAGENT_REPO` — checkout of the **dagent** agent service  
- `$DAGENT_DATA_DIR` — persistent host or container path for dagent state (knowledge store, workspace, DB)  
- `$WORKSPACE_ROOT` — optional parent directory mounting several repos

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Part 1: GPU Server Host Setup](#part-1-gpu-server-host-setup)
4. [Part 2: Dagent Deployment](#part-2-dagent-deployment)
5. [Part 3: Ubuntu Container Setup](#part-3-ubuntu-container-setup)
6. [Part 4: Running Benchmarks](#part-4-running-benchmarks)
7. [Network Communication Details](#network-communication-details)
8. [Troubleshooting](#troubleshooting)
9. [Cleanup](#cleanup)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│ GPU Server Host                                                 │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Your Ubuntu Container                                    │  │
│  │                                                          │  │
│  │  • Benchmark Python app                                 │  │
│  │  • Poetry environment                                   │  │
│  │  • Access to host Docker socket (/var/run/docker.sock) │  │
│  │                                                          │  │
│  │  Sends HTTP requests to dagent on host ───────────┐    │  │
│  │  Uses containerlab via Docker socket ─────────┐   │    │  │
│  └──────────────────────────────────────────────┼───┼────┘  │
│                                                  │   │       │
│  Containerlab (installed on host) ◄─────────────┘   │       │
│  ├─ Creates network topologies                      │       │
│  └─ Manages all containers                          │       │
│                                                      │       │
│  ┌───────────────────────────────────────────┐      │       │
│  │ Dagent Container (via containerlab)       │      │       │
│  │  • FastAPI service on :8000               │◄─────┘       │
│  │  • Generates network configs              │              │
│  │  • Poetry environment                     │              │
│  └───────────────────────────────────────────┘              │
│                                                              │
│  ┌───────────────────────────────────────────┐              │
│  │ Network Topology Containers               │              │
│  │  • Router R1 (FRR)                        │              │
│  │  • Router R2 (FRR)                        │              │
│  │  • Router R3 (FRR)                        │              │
│  │  Created dynamically per benchmark        │              │
│  └───────────────────────────────────────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

**Key Components:**

- **Containerlab**: Installed on GPU server host, manages all containers
- **Dagent**: Runs as a containerlab node, accessible via HTTP on port 8000
- **Benchmark**: Runs from your Ubuntu container, orchestrates everything
- **Network Topologies**: Created dynamically by containerlab for each test

**Why This Works:**

✅ No nested containers - benchmark uses host's Docker socket  
✅ Dagent accessible via standard Docker networking  
✅ GPU can be assigned to dagent container if needed  
✅ All containers share Docker network space

---

## Prerequisites

### On GPU Server Host

- **Operating System**: Linux (Ubuntu 20.04+ recommended)
- **Docker**: Version 20.10+
- **Root/sudo access**: Required for containerlab installation
- **Network**: Ability to pull Docker images from registries

### On Your Ubuntu Container

- **Python**: 3.10 or higher
- **Access to host Docker socket**: `/var/run/docker.sock` mounted
- **Network**: Ability to reach host services (typically via `172.17.0.1` or host IP)

### API Keys

- **OpenAI API key** (or other LLM provider keys)
- Export these in your environment or store in `.env` files

---

## Part 1: GPU Server Host Setup

### Step 1.1: Install Docker (if not already installed)

```bash
# Check if Docker is installed
docker --version

# If not installed, run Docker installation script
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add your user to docker group (to run without sudo)
sudo usermod -aG docker $USER

# Log out and back in, or run:
newgrp docker

# Verify
docker run hello-world
```

### Step 1.2: Install Containerlab

```bash
# Install containerlab
sudo bash -c "$(curl -sL https://get.containerlab.dev)"

# Verify installation
containerlab version

# Expected output: containerlab version x.x.x
```

**Alternative: Manual Installation**

```bash
# Download latest release
CLAB_VERSION="0.50.0"  # Check https://containerlab.dev for latest
curl -sLO "https://github.com/srl-labs/containerlab/releases/download/v${CLAB_VERSION}/containerlab_${CLAB_VERSION}_linux_amd64.deb"

# Install
sudo dpkg -i containerlab_${CLAB_VERSION}_linux_amd64.deb

# Verify
containerlab version
```

### Step 1.3: Verify Prerequisites

```bash
# Check Docker is running
sudo systemctl status docker

# Check containerlab is accessible
which containerlab

# Check user permissions
groups | grep docker
```

---

## Part 2: Dagent Deployment

### Step 2.1: Build Dagent Docker Image

Navigate to your dagent repository:

```bash
cd $DAGENT_REPO
```

**Create Dockerfile (if not using existing):**

```bash
cat > Dockerfile.deployment << 'EOF'
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --no-cache-dir poetry

# Copy project files
COPY pyproject.toml poetry.lock* ./
COPY dagent ./dagent
COPY static ./static
COPY README.md ./
RUN touch __init__.py

# Install dependencies (without dev dependencies for production)
RUN poetry config virtualenvs.create false && \
    poetry install --no-dev --no-interaction --no-ansi

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Run dagent
CMD ["uvicorn", "dagent.main:app", "--host", "0.0.0.0", "--port", "8000"]
EOF
```

**Build the image:**

```bash
docker build -f Dockerfile.deployment -t dagent:latest .

# Verify image was built
docker images | grep dagent
```

### Step 2.2: Create Containerlab Topology for Dagent

Create the topology file:

```bash
mkdir -p $BENCHMARK_REPO/containerlab
cd $BENCHMARK_REPO/containerlab

cat > dagent-service.clab.yml << 'EOF'
name: dagent-service

topology:
  nodes:
    dagent:
      kind: linux
      image: dagent:latest
      ports:
        - "8000:8000"
      env:
        # LLM API Keys - REPLACE WITH YOUR ACTUAL KEYS
        OPENAI_API_KEY: ${OPENAI_API_KEY:-""}
        ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:-""}
        GOOGLE_API_KEY: ${GOOGLE_API_KEY:-""}
        
        # Dagent configuration
        KNOWLEDGE_ROOT_PATH: /app/knowledge_store
        CODE_EXECUTION_PATH: /app/execution_workspace
        DB_DRIVER: sqlite
        DB_URL: sqlite:///db.sqlite3
        
        # Optional: Ollama endpoint if using local models
        # OLLAMA_BASE_URL: http://host.docker.internal:11434
      
      # Optional: GPU access for dagent
      # Uncomment if dagent needs GPU access
      # runtime: nvidia
      # env:
      #   NVIDIA_VISIBLE_DEVICES: all
      
      # Optional: Mount persistent storage
      # binds:
      #   - $DAGENT_DATA_DIR:/app/data
EOF
```

**Important Configuration Notes:**

- **API Keys**: Set via environment variables before deployment
- **GPU Access**: Uncomment `runtime: nvidia` if dagent needs GPU
- **Persistent Storage**: Uncomment `binds` to persist data across restarts
- **Network Mode**: Default bridge network allows communication with other containers

### Step 2.3: Deploy Dagent with Containerlab

**Set your API keys:**

```bash
# Set API keys in environment
export OPENAI_API_KEY="sk-your-key-here"
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
# Add other keys as needed
```

**Deploy dagent:**

```bash
cd $BENCHMARK_REPO/containerlab

# Deploy with containerlab
sudo -E containerlab deploy -t dagent-service.clab.yml

# The -E flag preserves environment variables for sudo
```

**Expected output:**

```
INFO[0000] Containerlab v0.x.x starting                 
INFO[0000] Parsing & checking topology file: dagent-service.clab.yml 
INFO[0001] Creating lab directory: /root/clab-dagent-service 
INFO[0001] Creating container: "dagent"                 
INFO[0005] Created link: dagent:eth0 <--> mgmt-net     
INFO[0005] Adding containerlab host entries to /etc/hosts file 
+---+-----------------+--------------+-------------+-------+---------+
| # |      Name       | Container ID |    Image    | Kind  |  State  |
+---+-----------------+--------------+-------------+-------+---------+
| 1 | dagent-service  | 3x2x1x0x9x8x | dagent:     | linux | running |
|   | -dagent         |              | latest      |       |         |
+---+-----------------+--------------+-------------+-------+---------+
```

### Step 2.4: Verify Dagent is Running

```bash
# Check container status
docker ps | grep dagent

# Test HTTP endpoint from host
curl http://localhost:8000

# Expected: {"message":"Hello Dagent"}

# Check logs
docker logs clab-dagent-service-dagent

# Inspect containerlab topology
sudo containerlab inspect -t dagent-service.clab.yml
```

**Get Dagent Container IP (for reference):**

```bash
docker inspect clab-dagent-service-dagent | grep IPAddress

# You'll see something like "IPAddress": "172.20.20.2"
```

---

## Part 3: Ubuntu Container Setup

### Step 3.1: Ensure Docker Socket Access

Your Ubuntu container needs access to the host's Docker socket to use containerlab.

**If starting a new container:**

```bash
docker run -it \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v $WORKSPACE_ROOT:/workspace \
  --name my-ubuntu-container \
  ubuntu:22.04 /bin/bash
```

**If container is already running, verify socket access:**

```bash
# Inside your Ubuntu container
ls -la /var/run/docker.sock

# Try running docker command
docker ps

# If permission denied, you may need to add user to docker group
# or run docker commands with appropriate permissions
```

### Step 3.2: Install Python and Dependencies

```bash
# Inside your Ubuntu container
apt-get update
apt-get install -y python3 python3-pip curl git

# Verify Python version (need 3.10+)
python3 --version
```

### Step 3.3: Install Poetry

```bash
# Install Poetry
curl -sSL https://install.python-poetry.org | python3 -

# Add to PATH (add to ~/.bashrc for persistence)
export PATH="$HOME/.local/bin:$PATH"

# Verify
poetry --version
```

### Step 3.4: Setup Benchmark Repository

```bash
cd $BENCHMARK_REPO

# Install benchmark dependencies
poetry install

# Verify installation
poetry run benchmark --help
```

### Step 3.5: Configure Dagent Endpoint

Create or update `.env` file:

```bash
cd $BENCHMARK_REPO

cat > .env << 'EOF'
# Dagent endpoint
# Use 172.17.0.1 (Docker bridge gateway) to reach host services
# Or use actual host IP if on different network
DAGENT_ENDPOINT=http://172.17.0.1:8000

# Alternative: Use host.docker.internal (if supported)
# DAGENT_ENDPOINT=http://host.docker.internal:8000

# LLM API Keys (if calling directly, not through dagent)
OPENAI_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
EOF
```

**Network Options for Reaching Host:**

| Method | Endpoint | Notes |
|--------|----------|-------|
| Docker bridge | `172.17.0.1:8000` | Default Docker bridge gateway |
| Host IP | `<host-ip>:8000` | Use actual host IP address |
| host.docker.internal | `host.docker.internal:8000` | Works on Docker Desktop, may need `--add-host` on Linux |

### Step 3.6: Test Connection to Dagent

```bash
# From inside Ubuntu container
curl http://172.17.0.1:8000

# Expected: {"message":"Hello Dagent"}

# If this fails, try host IP:
# Get host IP first, then:
# curl http://<HOST_IP>:8000
```

---

## Part 4: Running Benchmarks

### Step 4.1: Understanding the Workflow

**Benchmark Execution Flow:**

1. **Benchmark** (in container) → HTTP request → **Dagent** (on host)
2. **Dagent** generates configuration commands
3. **Dagent** returns commands to **Benchmark**
4. **Benchmark** → Uses Docker socket → **Containerlab** (on host)
5. **Containerlab** creates network topology (routers)
6. **Benchmark** executes commands on routers
7. **Benchmark** evaluates network state
8. **Benchmark** tears down topology

### Step 4.2: Run Single Task with Dagent

```bash
cd $BENCHMARK_REPO

# Run a single task using dagent
poetry run benchmark run-task \
  tasks/<task-file>.json \
  --dagent-endpoint http://172.17.0.1:8000 \
  --provider openai \
  --model gpt-4 \
  --verbose

# Example with specific task:
poetry run benchmark run-task \
  tasks/reachability/simple_reachability_001.json \
  --dagent-endpoint http://172.17.0.1:8000 \
  --provider openai \
  --model gpt-4
```

### Step 4.3: Run Batch Study with Dagent

```bash
# Run all tasks of a specific type
poetry run benchmark run-dagent reachability \
  --endpoint http://172.17.0.1:8000 \
  --provider openai \
  --model gpt-4 \
  --limit 10

# With multi-agent mode
poetry run benchmark run-dagent bgp_configuration \
  --endpoint http://172.17.0.1:8000 \
  --provider openai \
  --model gpt-4 \
  --agent-mode multi \
  --structure sequential \
  --limit 5

# Available property types:
# - reachability
# - bgp_configuration
# - ospf_configuration
# - vlan_configuration
```

**Command Options:**

- `--endpoint`: Dagent HTTP endpoint
- `--provider`: LLM provider (openai, anthropic, ollama, etc.)
- `--model`: Model name (gpt-4, claude-3-opus, etc.)
- `--agent-mode`: `single` or `multi` agent
- `--structure`: Multi-agent structure (sequential, concurrent, debate, group_chat)
- `--limit`: Number of tasks to run
- `--platform`: Network platform (frr, nokia_srlinux)

### Step 4.4: Monitor Execution

```bash
# In another terminal, watch containerlab topologies
watch -n 2 "sudo containerlab inspect -a"

# Watch Docker containers
watch -n 2 "docker ps"

# Monitor dagent logs
docker logs -f clab-dagent-service-dagent

# Monitor benchmark progress
# (Benchmark will output progress in its terminal)
```

### Step 4.5: Review Results

```bash
cd $BENCHMARK_REPO

# List recent runs
poetry run benchmark list-runs --limit 20

# View specific result
poetry run benchmark show-result <run_id> --verbose

# Results are stored in:
ls -la results/
```

**Result Directory Structure:**

```
results/
├── dagent_runs/
│   └── dagent_study_YYYYMMDD_HHMMSS/
│       ├── runs/
│       │   ├── reachability/
│       │   │   └── dagent_<timestamp>_<hash>.json
│       │   └── bgp_configuration/
│       └── analysis/
└── logs/
```

---

## Network Communication Details

### Container-to-Host Communication

**From Ubuntu Container to Dagent on Host:**

```
Ubuntu Container → Docker Bridge (172.17.0.1) → Host Network Stack → Dagent Container (port 8000)
```

**Key Points:**

- Docker bridge network: `172.17.0.0/16` (default)
- Bridge gateway: `172.17.0.1` (host as seen from containers)
- Dagent exposed on host: `0.0.0.0:8000` → accessible via bridge gateway

### Docker Socket Communication

**Benchmark in Container Uses Host's Docker:**

```
Benchmark → /var/run/docker.sock (mounted) → Docker Daemon on Host → Creates Containers
```

**What This Enables:**

- Benchmark can run `containerlab` commands via Docker API
- Network topologies created on host, not nested
- All containers are siblings, not nested

### Containerlab Network Topology

**When Benchmark Creates Topology:**

```bash
# Containerlab creates:
# - Custom Docker network: clab-<topology-name>
# - Router containers connected to this network
# - Management network for access
```

**Example:**

```
clab-bench-20260123-abc123/
├── Router R1: clab-bench-20260123-abc123-r1
├── Router R2: clab-bench-20260123-abc123-r2
└── Router R3: clab-bench-20260123-abc123-r3
```

All these containers can communicate with each other and with the benchmark container.

---

## Troubleshooting

### Issue: Cannot Connect to Dagent from Ubuntu Container

**Symptoms:**
```bash
curl http://172.17.0.1:8000
# curl: (7) Failed to connect to 172.17.0.1 port 8000: Connection refused
```

**Solutions:**

1. **Check dagent is running:**
   ```bash
   # On host
   docker ps | grep dagent
   sudo containerlab inspect -t dagent-service.clab.yml
   ```

2. **Check port binding:**
   ```bash
   # On host
   docker port clab-dagent-service-dagent
   # Should show: 8000/tcp -> 0.0.0.0:8000
   ```

3. **Try different endpoints:**
   ```bash
   # Get host IP
   ip addr show | grep "inet "
   
   # Try host IP instead
   curl http://<HOST_IP>:8000
   ```

4. **Check firewall:**
   ```bash
   # On host
   sudo ufw status
   sudo iptables -L -n | grep 8000
   ```

### Issue: Permission Denied Accessing Docker Socket

**Symptoms:**
```bash
docker ps
# permission denied while trying to connect to the Docker daemon socket
```

**Solutions:**

1. **Verify socket is mounted:**
   ```bash
   ls -la /var/run/docker.sock
   ```

2. **Add user to docker group (in container):**
   ```bash
   # Not ideal, but works:
   chmod 666 /var/run/docker.sock
   ```

3. **Run with appropriate user:**
   ```bash
   # Start container with same UID as host docker group
   docker run --user $(id -u):$(getent group docker | cut -d: -f3) ...
   ```

### Issue: Containerlab Command Not Found

**Symptoms:**
```bash
containerlab version
# containerlab: command not found
```

**Note:** You do NOT need containerlab installed in the Ubuntu container! The benchmark uses the host's containerlab via Docker socket.

**Verify:**
```bash
# From Ubuntu container, check docker works:
docker ps

# The benchmark will use Docker API to call containerlab on host
```

### Issue: API Key Errors in Dagent

**Symptoms:**
```
ERROR: OpenAI API key not found
```

**Solutions:**

1. **Check dagent environment:**
   ```bash
   docker exec clab-dagent-service-dagent env | grep API_KEY
   ```

2. **Redeploy with correct keys:**
   ```bash
   sudo containerlab destroy -t dagent-service.clab.yml
   export OPENAI_API_KEY="your-key"
   sudo -E containerlab deploy -t dagent-service.clab.yml
   ```

3. **Pass keys in topology file (not recommended for security):**
   Edit `dagent-service.clab.yml` and hardcode keys (use only for testing)

### Issue: Network Topology Creation Fails

**Symptoms:**
```
ERROR: Failed to create topology: containerlab deploy failed
```

**Solutions:**

1. **Check Docker resources:**
   ```bash
   docker system df
   docker system prune  # Clean up if needed
   ```

2. **Check for stale networks:**
   ```bash
   docker network ls | grep clab
   
   # Clean up old networks
   python scripts/cleanup_benchmark_networks.py
   ```

3. **Verify FRR image is available:**
   ```bash
   docker pull frrouting/frr:latest
   docker images | grep frr
   ```

### Issue: Benchmark Hangs or Times Out

**Symptoms:**
```
Waiting for dagent response...
(hangs for several minutes)
```

**Solutions:**

1. **Check dagent logs:**
   ```bash
   docker logs clab-dagent-service-dagent --tail 100 -f
   ```

2. **Increase timeout:**
   ```bash
   poetry run benchmark run-dagent reachability \
     --endpoint http://172.17.0.1:8000 \
     --time-limit 600  # 10 minutes
   ```

3. **Test dagent directly:**
   ```bash
   curl -X POST http://172.17.0.1:8000/benchmark/generate \
     -H "Content-Type: application/json" \
     -d '{"task_id": "test", "description": "test BGP config", ...}'
   ```

---

## Cleanup

### Clean Up After Benchmark Run

**Benchmark typically cleans up automatically**, but if needed:

```bash
# From Ubuntu container
cd $BENCHMARK_REPO

# Clean all benchmark networks
poetry run python scripts/cleanup_benchmark_networks.py
```

### Manually Clean Containerlab Topologies

```bash
# On host, list all topologies
sudo containerlab inspect -a

# Destroy specific topology
sudo containerlab destroy -t <topology-file>.clab.yml

# Or by name
sudo containerlab destroy --name <topology-name>

# Clean all
sudo containerlab destroy --all
```

### Remove Dagent Deployment

```bash
# On host
cd $BENCHMARK_REPO/containerlab
sudo containerlab destroy -t dagent-service.clab.yml

# Verify
docker ps | grep dagent
```

### Clean Docker Resources

```bash
# On host
# Remove stopped containers
docker container prune

# Remove unused networks
docker network prune

# Remove unused images
docker image prune

# Full cleanup (careful!)
docker system prune -a --volumes
```

### Stop and Remove Everything

```bash
# NUCLEAR OPTION - removes ALL docker containers, networks, images
# Use only if you want to start completely fresh

# Stop all containers
docker stop $(docker ps -aq)

# Remove all containers
docker rm $(docker ps -aq)

# Remove all networks
docker network prune -f

# Remove all images
docker rmi $(docker images -q)
```

---

## Advanced Configuration

### GPU Access for Dagent

If dagent needs GPU access (e.g., for local LLM inference):

**1. Install NVIDIA Container Toolkit on host:**

```bash
# Add repository
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-docker.list

# Install
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# Restart Docker
sudo systemctl restart docker

# Test
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi
```

**2. Update dagent topology:**

Edit `dagent-service.clab.yml`:

```yaml
topology:
  nodes:
    dagent:
      kind: linux
      image: dagent:latest
      runtime: nvidia  # Add this
      env:
        NVIDIA_VISIBLE_DEVICES: all  # Add this
      # ... rest of config
```

### Persistent Storage for Dagent

To persist dagent data across restarts:

```bash
# Create storage directory on host
mkdir -p $DAGENT_DATA_DIR/{knowledge_store,execution_workspace,db}

# Update topology file
```

Edit `dagent-service.clab.yml`:

```yaml
topology:
  nodes:
    dagent:
      binds:
        - $DAGENT_DATA_DIR/knowledge_store:/app/knowledge_store
        - $DAGENT_DATA_DIR/execution_workspace:/app/execution_workspace
        - $DAGENT_DATA_DIR/db:/app/db
      env:
        DB_URL: sqlite:////app/db/dagent.sqlite3
```

### Using Ollama with Dagent

If running Ollama on the host for local models:

**1. Install Ollama on host:**

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama serve &
ollama pull qwen3:8b
```

**2. Update dagent topology to access host Ollama:**

```yaml
topology:
  nodes:
    dagent:
      env:
        OLLAMA_BASE_URL: http://172.17.0.1:11434
        # Or use host IP
```

---

## Quick Reference Commands

### Essential Commands

```bash
# Deploy dagent
sudo -E containerlab deploy -t dagent-service.clab.yml

# Destroy dagent
sudo containerlab destroy -t dagent-service.clab.yml

# Run benchmark
poetry run benchmark run-dagent reachability \
  --endpoint http://172.17.0.1:8000 \
  --provider openai --model gpt-4

# View results
poetry run benchmark list-runs

# Cleanup
poetry run python scripts/cleanup_benchmark_networks.py
```

### Monitoring Commands

```bash
# Watch containers
watch -n 2 "docker ps"

# Watch dagent logs
docker logs -f clab-dagent-service-dagent

# Inspect topology
sudo containerlab inspect -t dagent-service.clab.yml

# Network information
docker network ls
docker network inspect <network-name>
```

---

## Summary Checklist

### Initial Setup (One-time)

- [ ] Install Docker on GPU server host
- [ ] Install Containerlab on GPU server host
- [ ] Build dagent Docker image
- [ ] Create dagent topology file
- [ ] Deploy dagent with containerlab
- [ ] Verify dagent is accessible from host
- [ ] Setup Ubuntu container with Docker socket access
- [ ] Install Poetry in Ubuntu container
- [ ] Install benchmark dependencies
- [ ] Configure dagent endpoint in benchmark
- [ ] Test connection from container to dagent

### Per Benchmark Run

- [ ] Ensure dagent is running (`docker ps | grep dagent`)
- [ ] Run benchmark command from Ubuntu container
- [ ] Monitor execution
- [ ] Review results
- [ ] Clean up if needed

### After Work

- [ ] Stop dagent if not needed (`containerlab destroy`)
- [ ] Clean up Docker resources
- [ ] Backup results if important

---

## Contact and Support

For issues specific to:

- **Containerlab**: https://containerlab.dev/
- **Docker**: https://docs.docker.com/
- **Benchmark**: Check benchmark repo docs
- **Dagent**: Check dagent repo docs

---

**Document Version**: 1.0  
**Last Updated**: 2026-01-23  
**Tested On**: Ubuntu 22.04, Docker 24.0+, Containerlab 0.50+
