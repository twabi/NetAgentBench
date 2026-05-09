#!/bin/bash
# run_multiturn_study.sh
# Runs multi-turn benchmark study across single-agent and multi-agent configurations

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}" || exit 1

# Configuration
DAGENT_ENDPOINT="${DAGENT_ENDPOINT:-http://localhost:8000}"
TURN_LIMIT="${TURN_LIMIT:-100}"
TIME_LIMIT="${TIME_LIMIT:-900}"  # 15 minutes per task

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
    "openai:gpt-5-mini-2025-08-07"
    "gemini:gemini-2.5-pro"
)

# Create dated session folder
SESSION_NAME="multiturn_study_$(date +%Y%m%d_%H%M%S)"
OUTPUT_DIR="results/multiturn_runs/${SESSION_NAME}"
mkdir -p "${OUTPUT_DIR}/runs"

echo "============================================================"
echo "Multi-Turn Benchmark Study"
echo "============================================================"
echo "Session: ${SESSION_NAME}"
echo "Output:  ${OUTPUT_DIR}"
echo "Tasks:   ${#TASKS[@]}"
echo "Configs: ${#AGENT_CONFIGS[@]} (single + 4 multi patterns)"
echo "Models:  ${#MODELS[@]}"
echo "Turn Limit: ${TURN_LIMIT}"
echo "Time Limit: ${TIME_LIMIT}s"
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
  "total_planned_runs": ${TOTAL}
}
EOF

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
echo "Multi-Turn Study Complete!"
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
