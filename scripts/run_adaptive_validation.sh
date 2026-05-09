#!/bin/bash
# run_adaptive_validation.sh
# Validation ladder for the improved adaptive pattern.
# Runs only Pi_adaptive on the four key tasks from the fix plan.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}" || exit 1

DAGENT_ENDPOINT="${DAGENT_ENDPOINT:-http://localhost:8000}"
OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
TURN_LIMIT=100
TIME_LIMIT=1800
CONTEXT_LENGTH=120000

TASKS=(
    "tasks/multi_turn/ccna_rip_routing_basic.json"
    "tasks/multi_turn/ccie_bgp_dual_homing_expert.json"
    "tasks/multi_turn/troubleshoot_ospf_adjacency_issue.json"
    "tasks/multi_turn/troubleshoot_bgp_route_filtering.json"
)

MODELS=(
    "openai:gpt-5-nano-2025-08-07"
)

SESSION_NAME="adaptive_validation_$(date +%Y%m%d_%H%M%S)"
OUTPUT_DIR="results/adaptive_validation/${SESSION_NAME}"
mkdir -p "${OUTPUT_DIR}"

TOTAL=$((${#TASKS[@]} * ${#MODELS[@]}))
CURRENT=0

echo "======================================================"
echo "Adaptive Pattern Validation"
echo "======================================================"
echo "Session: ${SESSION_NAME}"
echo "Output:  ${OUTPUT_DIR}"
echo "Tasks:   ${#TASKS[@]}"
echo "Models:  ${#MODELS[@]}"
echo "Limits:  Turns=${TURN_LIMIT}, Time=${TIME_LIMIT}s"
echo "======================================================"

for task_file in "${TASKS[@]}"; do
    for model_spec in "${MODELS[@]}"; do
        IFS=':' read -r provider model <<< "${model_spec}"
        CURRENT=$((CURRENT + 1))
        task_name=$(basename "${task_file}" .json)

        echo ""
        echo "[${CURRENT}/${TOTAL}] ${task_name}"
        echo "  Provider: ${provider}, Model: ${model}"
        echo "------------------------------------------------------"

        if poetry run benchmark run-task "${task_file}" \
            --dagent-endpoint "${DAGENT_ENDPOINT}" \
            --provider "${provider}" \
            --model "${model}" \
            --provider-host "${OLLAMA_HOST}" \
            --agent-mode "multi" \
            --structure "adaptive" \
            --turn-limit ${TURN_LIMIT} \
            --time-limit ${TIME_LIMIT} \
            --context-length "${CONTEXT_LENGTH}" \
            --output-dir "${OUTPUT_DIR}"; then
            echo "  OK"
        else
            echo "  FAILED (benchmark runner error)"
        fi
    done
done

echo ""
echo "======================================================"
echo "Adaptive validation complete. Results: ${OUTPUT_DIR}"
echo "======================================================"
