#!/bin/bash
# rerun_failed_study_runs.sh
# Reruns only the configurations that were identified as failed due to the AttributeError

set -e

# Configuration
DAGENT_ENDPOINT="${DAGENT_ENDPOINT:-http://localhost:8000}"
OLLAMA_HOST="http://localhost:11434"
TURN_LIMIT=100
TIME_LIMIT=1800
CONTEXT_LENGTH=120000

# Target the original study folder to overwrite failed logs
DEFAULT_SESSION="comparative_study_20260213_061130"
SESSION_NAME="${1:-$DEFAULT_SESSION}"
OUTPUT_DIR="results/comparative_study/${SESSION_NAME}"

# Ensure output directory exists (though it should for the original study)
mkdir -p "${OUTPUT_DIR}/runs"

echo "============================================================"
echo "Rerunning Failed Multi-Turn Benchmark Study Runs"
echo "============================================================"
echo "Session: ${SESSION_NAME}"
echo "Output:  ${OUTPUT_DIR}"
echo "============================================================"

# Ensure we're in the project root
if [ -d "/home/grimm/python_projects/benchmark" ]; then
    cd /home/grimm/python_projects/benchmark
elif [ -d "/root/network-benchmark" ]; then
    cd /root/network-benchmark
fi

# Load the rerun plan
PLAN_FILE="/root/rerun_plan.json"
if [ ! -f "$PLAN_FILE" ]; then
    echo "Error: Rerun plan $PLAN_FILE not found!"
    exit 1
fi

TOTAL_RERUNS=$(jq '. | length' "$PLAN_FILE")
CURRENT=0

for ((i=0; i<$TOTAL_RERUNS; i++)); do
    CURRENT=$((CURRENT + 1))
    
    # Extract config details
    TASK_FILE=$(jq -r ".[$i].task" "$PLAN_FILE")
    PROVIDER=$(jq -r ".[$i].provider" "$PLAN_FILE")
    MODEL=$(jq -r ".[$i].model" "$PLAN_FILE")
    AGENT_MODE=$(jq -r ".[$i].agent_mode" "$PLAN_FILE")
    STRUCTURE=$(jq -r ".[$i].structure" "$PLAN_FILE")
    
    TASK_NAME=$(basename "${TASK_FILE}" .json)
    
    echo ""
    echo "[${CURRENT}/${TOTAL_RERUNS}] ${TASK_NAME}"
    echo "  Mode: ${AGENT_MODE}, Structure: ${STRUCTURE}"
    echo "  Provider: ${PROVIDER}, Model: ${MODEL}"
    echo "------------------------------------------------------------"
    
    poetry run benchmark run-task "${TASK_FILE}" \
        --dagent-endpoint "${DAGENT_ENDPOINT}" \
        --provider "${PROVIDER}" \
        --model "${MODEL}" \
        --provider-host "${OLLAMA_HOST}" \
        --agent-mode "${AGENT_MODE}" \
        --structure "${STRUCTURE}" \
        --turn-limit ${TURN_LIMIT} \
        --time-limit ${TIME_LIMIT} \
        --context-length "${CONTEXT_LENGTH}" \
        --output-dir "${OUTPUT_DIR}" || echo "  ✗ Failed again"
done

echo ""
echo "============================================================"
echo "Rerun Complete!"
echo "============================================================"
echo "Results saved to: ${OUTPUT_DIR}"
echo ""
