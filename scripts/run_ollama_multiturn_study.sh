#!/bin/bash
# run_ollama_multiturn_study.sh
# Runs multi-turn benchmark study using Ollama (deepseek-r1:32b) with extended limits

set -e

# Configuration
DAGENT_ENDPOINT="${DAGENT_ENDPOINT:-http://localhost:8000}"
OLLAMA_HOST="http://localhost:11434"
# "Unreachably big" limits
TURN_LIMIT=10000
TIME_LIMIT=1800  # 30 minutes

# Multi-turn tasks
TASKS=(
    "tasks/multi_turn/small_campus_baseline.json"
    "tasks/multi_turn/medium_mixed_platform.json"
    "tasks/multi_turn/large_sp_core.json"
)

# Agent configurations: mode:structure
AGENT_CONFIGS=(
    "single:sequential"
    "multi:sequential"
    "multi:debate"
    "multi:group_chat"
    "multi:concurrent"
)

# Models to test (provider:model)
MODELS=(
    "ollama:deepseek-r1:32b"
)

# Create dated session folder
SESSION_NAME="ollama_multiturn_study_$(date +%Y%m%d_%H%M%S)"
OUTPUT_DIR="results/ollama_multiturn_runs/${SESSION_NAME}"
mkdir -p "${OUTPUT_DIR}/runs"

echo "============================================================"
echo "Ollama Multi-Turn Benchmark Study"
echo "============================================================"
echo "Session: ${SESSION_NAME}"
echo "Output:  ${OUTPUT_DIR}"
echo "Tasks:   ${#TASKS[@]}"
echo "Configs: ${#AGENT_CONFIGS[@]} (single + 4 multi patterns)"
echo "Model:   Ollama deepseek-r1:32b"
echo "Limits:  Turns=${TURN_LIMIT}, Time=${TIME_LIMIT}s"
echo "============================================================"
echo ""

# Calculate total runs
TOTAL=$((${#TASKS[@]} * ${#AGENT_CONFIGS[@]} * ${#MODELS[@]}))
CURRENT=0
SUCCESSFUL=0
FAILED=0

# Create session metadata
cat > "${OUTPUT_DIR}/session_info.json" << EOF
{
  "session_name": "${SESSION_NAME}",
  "study_type": "multi_turn",
  "started_at": "$(date -Iseconds)",
  "tasks": $(printf '%s\n' "${TASKS[@]}" | jq -R . | jq -s .),
  "agent_configs": $(printf '%s\n' "${AGENT_CONFIGS[@]}" | jq -R . | jq -s .),
  "models": $(printf '%s\n' "${MODELS[@]}" | jq -R . | jq -s .),
  "turn_limit": ${TURN_LIMIT},
  "time_limit": ${TIME_LIMIT},
  "dagent_endpoint": "${DAGENT_ENDPOINT}",
  "ollama_host": "${OLLAMA_HOST}",
  "total_planned_runs": ${TOTAL}
}
EOF

cd /home/grimm/python_projects/benchmark

run_multiturn() {
    local task_file=$1
    local agent_mode=$2
    local structure=$3
    local provider=$4
    local model=$5
    
    CURRENT=$((CURRENT + 1))
    
    local task_name=$(basename "${task_file}" .json)
    
    echo ""
    echo "[${CURRENT}/${TOTAL}] ${task_name}"
    echo "  Mode: ${agent_mode}, Structure: ${structure}"
    echo "  Provider: ${provider}, Model: ${model}"
    echo "------------------------------------------------------------"
    
    # Run the multi-turn benchmark using run-task command
    if poetry run benchmark run-task "${task_file}" \
        --dagent-endpoint "${DAGENT_ENDPOINT}" \
        --provider "${provider}" \
        --model "${model}" \
        --provider-host "${OLLAMA_HOST}" \
        --agent-mode "${agent_mode}" \
        --structure "${structure}" \
        --turn-limit ${TURN_LIMIT} \
        --time-limit ${TIME_LIMIT} \
        --output-dir "${OUTPUT_DIR}"; then
        SUCCESSFUL=$((SUCCESSFUL + 1))
        echo "  ✓ Completed successfully"
    else
        FAILED=$((FAILED + 1))  
        echo "  ✗ Failed"
    fi
}

# Run all combinations
for task_file in "${TASKS[@]}"; do
    for config in "${AGENT_CONFIGS[@]}"; do
        IFS=':' read -r agent_mode structure <<< "${config}"
        
        for model_spec in "${MODELS[@]}"; do
            IFS=':' read -r provider model <<< "${model_spec}"
            
            run_multiturn "${task_file}" "${agent_mode}" "${structure}" "${provider}" "${model}"
        done
    done
done

# Update session metadata with completion
cat > "${OUTPUT_DIR}/session_info.json" << EOF
{
  "session_name": "${SESSION_NAME}",
  "study_type": "multi_turn",
  "started_at": "$(date -Iseconds)",
  "completed_at": "$(date -Iseconds)",
  "tasks": $(printf '%s\n' "${TASKS[@]}" | jq -R . | jq -s .),
  "agent_configs": $(printf '%s\n' "${AGENT_CONFIGS[@]}" | jq -R . | jq -s .),
  "models": $(printf '%s\n' "${MODELS[@]}" | jq -R . | jq -s .),
  "turn_limit": ${TURN_LIMIT},
  "time_limit": ${TIME_LIMIT},
  "dagent_endpoint": "${DAGENT_ENDPOINT}",
  "total_planned_runs": ${TOTAL},
  "successful_runs": ${SUCCESSFUL},
  "failed_runs": ${FAILED}
}
EOF

echo ""
echo "============================================================"
echo "Ollama Multi-Turn Study Complete!"
echo "============================================================"
echo "Total Runs: ${TOTAL}"
echo "Successful: ${SUCCESSFUL}"
echo "Failed:     ${FAILED}"
echo ""
echo "Results saved to: ${OUTPUT_DIR}"
echo ""
echo "To analyze:"
echo "  python scripts/analyze_multiturn_results.py ${OUTPUT_DIR}"
echo ""
