#!/bin/bash
# rerun_failed_study_runs.sh
# Reruns only the configurations that were identified as failed due to the AttributeError

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}" || exit 1

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

# Load the rerun plan (override with env RERUN_PLAN_FILE)
PLAN_FILE="${RERUN_PLAN_FILE:-${REPO_ROOT}/scripts/rerun_plan.json}"
# Example shape: [{"task":"tasks/multi_turn/foo.json","provider":"openai","model":"gpt-4o-mini","agent_mode":"multi","structure":"sequential"}]
if [ ! -f "$PLAN_FILE" ]; then
    echo "Error: Rerun plan $PLAN_FILE not found! Set RERUN_PLAN_FILE or create ${REPO_ROOT}/scripts/rerun_plan.json"
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
