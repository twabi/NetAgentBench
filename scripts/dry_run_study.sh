#!/bin/bash
# run_comparative_multiturn_study.sh
# Runs comparative multi-turn benchmark study:
# - Models: GPT-5-mini, Qwen3-Coder:30b, Deepseek-Coder:33b
# - Patterns: Single, Sequential, Debate, Group Chat, Concurrent
# - Repetitions: 5 runs per configuration

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}" || exit 1

# Configuration
DAGENT_ENDPOINT="${DAGENT_ENDPOINT:-http://localhost:8000}"
OLLAMA_HOST="http://localhost:11434"
# "Unreachably big" limits
TURN_LIMIT=5
TIME_LIMIT=60  # 30 minutes
# Repetitions per configuration
REPETITIONS=1

# Multi-turn tasks
TASKS=(
    "tasks/multi_turn/ccna_rip_routing_basic.json"
)

# Agent configurations: mode:structure
AGENT_CONFIGS=(
    "single:sequential"
)

# Models to test (provider:model)
MODELS=(
    "ollama:qwen2.5-Coder:7b"
)

# Create dated session folder
SESSION_NAME="comparative_study_$(date +%Y%m%d_%H%M%S)"
OUTPUT_DIR="results/comparative_study/${SESSION_NAME}"
mkdir -p "${OUTPUT_DIR}/runs"

echo "============================================================"
echo "Comparative Multi-Turn Benchmark Study"
echo "============================================================"
echo "Session: ${SESSION_NAME}"
echo "Output:  ${OUTPUT_DIR}"
echo "Tasks:   ${#TASKS[@]}"
echo "Configs: ${#AGENT_CONFIGS[@]}"
echo "Models:  ${#MODELS[@]}"
echo "Reps:    ${REPETITIONS}"
echo "Limits:  Turns=${TURN_LIMIT}, Time=${TIME_LIMIT}s"
echo "============================================================"
echo ""

# Calculate total runs
TOTAL=$((${#TASKS[@]} * ${#AGENT_CONFIGS[@]} * ${#MODELS[@]} * ${REPETITIONS}))
CURRENT=0
SUCCESSFUL=0
FAILED=0

# Create session metadata
cat > "${OUTPUT_DIR}/session_info.json" << EOF
{
  "session_name": "${SESSION_NAME}",
  "study_type": "comparative_multi_turn",
  "started_at": "$(date -Iseconds)",
  "tasks": $(printf '%s\n' "${TASKS[@]}" | jq -R . | jq -s .),
  "agent_configs": $(printf '%s\n' "${AGENT_CONFIGS[@]}" | jq -R . | jq -s .),
  "models": $(printf '%s\n' "${MODELS[@]}" | jq -R . | jq -s .),
  "repetitions": ${REPETITIONS},
  "turn_limit": ${TURN_LIMIT},
  "time_limit": ${TIME_LIMIT},
  "dagent_endpoint": "${DAGENT_ENDPOINT}",
  "ollama_host": "${OLLAMA_HOST}",
  "total_planned_runs": ${TOTAL}
}
EOF

run_multiturn() {
    local task_file=$1
    local agent_mode=$2
    local structure=$3
    local provider=$4
    local model=$5
    local rep=$6
    
    CURRENT=$((CURRENT + 1))
    
    local task_name=$(basename "${task_file}" .json)
    
    echo ""
    echo "[${CURRENT}/${TOTAL}] ${task_name} (Rep ${rep}/${REPETITIONS})"
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
            
            for ((rep=1; rep<=REPETITIONS; rep++)); do
                run_multiturn "${task_file}" "${agent_mode}" "${structure}" "${provider}" "${model}" "${rep}"
            done
        done
    done
done

# Update session metadata with completion
cat > "${OUTPUT_DIR}/session_info.json" << EOF
{
  "session_name": "${SESSION_NAME}",
  "study_type": "comparative_multi_turn",
  "started_at": "$(date -Iseconds)",
  "completed_at": "$(date -Iseconds)",
  "tasks": $(printf '%s\n' "${TASKS[@]}" | jq -R . | jq -s .),
  "agent_configs": $(printf '%s\n' "${AGENT_CONFIGS[@]}" | jq -R . | jq -s .),
  "models": $(printf '%s\n' "${MODELS[@]}" | jq -R . | jq -s .),
  "repetitions": ${REPETITIONS},
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
echo "Comparative Study Complete!"
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
