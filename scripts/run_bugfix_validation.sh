#!/bin/bash
# run_bugfix_validation.sh
# Minimal version: sequential and concurrent patterns, GPT only

set -e

DAGENT_ENDPOINT="${DAGENT_ENDPOINT:-http://localhost:8000}"
TURN_LIMIT="${TURN_LIMIT:-100}"
TIME_LIMIT="${TIME_LIMIT:-900}"

# All multi-turn tasks
TASKS=(
    "tasks/multi_turn/small_campus_baseline.json"
)

# Test fixed patterns
AGENT_CONFIGS=(
    "multi:concurrent"
    "multi:debate"
    "multi:group_chat"
)

# Only GPT
MODELS=(
    "openai:gpt-5-mini-2025-08-07"
)

SESSION_NAME="multiturn_study_$(date +%Y%m%d_%H%M%S)"
OUTPUT_DIR="results/multiturn_runs/${SESSION_NAME}"
mkdir -p "${OUTPUT_DIR}/runs"

echo "============================================================"
echo "Multi-Turn Benchmark Study (Sequential + Concurrent)"
echo "============================================================"
echo "Session: ${SESSION_NAME}"
echo "Output:  ${OUTPUT_DIR}"
echo "Tasks:   ${#TASKS[@]}"
echo "Patterns: sequential, concurrent"
echo "Model:   GPT-5-mini"
echo "============================================================"

TOTAL=$((${#TASKS[@]} * ${#AGENT_CONFIGS[@]} * ${#MODELS[@]}))
CURRENT=0
SUCCESSFUL=0
FAILED=0

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

cd ~/python_projects/benchmark

for task_file in "${TASKS[@]}"; do
    for config in "${AGENT_CONFIGS[@]}"; do
        IFS=':' read -r agent_mode structure <<< "${config}"
        
        for model_spec in "${MODELS[@]}"; do
            IFS=':' read -r provider model <<< "${model_spec}"
            
            CURRENT=$((CURRENT + 1))
            task_name=$(basename "${task_file}" .json)
            
            echo ""
            echo "[${CURRENT}/${TOTAL}] ${task_name} - ${structure}"
            echo "------------------------------------------------------------"
            
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
                echo "  ✓ Completed"
            else
                FAILED=$((FAILED + 1))  
                echo "  ✗ Failed"
            fi
        done
    done
done

echo ""
echo "============================================================"
echo "Complete: ${SUCCESSFUL}/${TOTAL} successful"
echo "Results: ${OUTPUT_DIR}"
echo ""
echo "Analyze with:"
echo "  poetry run python scripts/analyze_multiturn_results.py ${OUTPUT_DIR}"
echo ""
