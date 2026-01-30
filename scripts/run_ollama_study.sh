#!/bin/bash
# run_ollama_study.sh
# Runs benchmark evaluation using Ollama (qwen3:8b) with extended limits

set -e

# Configuration
LIMIT=30
DAGENT_ENDPOINT="http://localhost:8000"
OLLAMA_HOST="http://localhost:11434"
# "Unreachably big" limits
TURN_LIMIT=100000
TIME_LIMIT=86400  # 24 hours

# Create dated session folder
SESSION_NAME="ollama_study_$(date +%Y%m%d_%H%M%S)"
OUTPUT_DIR="results/sessions/${SESSION_NAME}"
mkdir -p "${OUTPUT_DIR}"

echo "============================================================"
echo "Ollama Benchmark Study"
echo "============================================================"
echo "Session: ${SESSION_NAME}"
echo "Output:  ${OUTPUT_DIR}"
echo "Limit:   ${LIMIT} tasks per property"
echo "Model:   Ollama qwen3:8b"
echo "Limits:  Turns=${TURN_LIMIT}, Time=${TIME_LIMIT}s"
echo "============================================================"
echo ""

# Create session metadata
cat > "${OUTPUT_DIR}/session_info.json" << EOF
{
  "session_name": "${SESSION_NAME}",
  "started_at": "$(date -Iseconds)",
  "limit_per_property": ${LIMIT},
  "models": ["qwen3:8b"],
  "property_types": ["reachability", "ospf_configuration", "bgp_configuration"],
  "dagent_endpoint": "${DAGENT_ENDPOINT}",
  "ollama_host": "${OLLAMA_HOST}"
}
EOF

cd /home/grimm/python_projects/benchmark

# Track progress
TOTAL=3
CURRENT=0

run_benchmark() {
    local property=$1
    local platform=$2
    local provider="ollama"
    local model="qwen3:8b"
    CURRENT=$((CURRENT + 1))
    
    echo ""
    echo "[${CURRENT}/${TOTAL}] Running ${property} (${platform}) with ${provider}/${model}..."
    echo "------------------------------------------------------------"
    
    poetry run benchmark run-dagent "${property}" \
        --endpoint "${DAGENT_ENDPOINT}" \
        --platform "${platform}" \
        --limit ${LIMIT} \
        --provider "${provider}" \
        --model "${model}" \
        --provider-host "${OLLAMA_HOST}" \
        --turn-limit ${TURN_LIMIT} \
        --time-limit ${TIME_LIMIT} \
        --mode multi \
        --output-dir "${OUTPUT_DIR}"
}

# Ollama qwen3:8b runs
run_benchmark reachability generic
run_benchmark ospf_configuration frr
run_benchmark bgp_configuration frr

# Update session metadata with completion time
cat > "${OUTPUT_DIR}/session_info.json" << EOF
{
  "session_name": "${SESSION_NAME}",
  "started_at": "$(date -Iseconds)",
  "completed_at": "$(date -Iseconds)",
  "limit_per_property": ${LIMIT},
  "models": ["qwen3:8b"],
  "property_types": ["reachability", "ospf_configuration", "bgp_configuration"],
  "dagent_endpoint": "${DAGENT_ENDPOINT}",
  "total_runs": ${TOTAL}
}
EOF

echo ""
echo "============================================================"
echo "Ollama Study Complete!"
echo "============================================================"
echo "All results saved to: ${OUTPUT_DIR}"
echo ""
echo "To analyze:"
echo "  poetry run benchmark analyze ${OUTPUT_DIR}"
echo ""
