#!/bin/bash
#
# Quick Benchmark Test: GPT-5-mini vs Gemini 2.5 Pro
#
# This script runs a smaller benchmark for quick testing (10 tasks per property type)
# Estimated runtime: 1-2 hours
#

set -e  # Exit on error

# Configuration
BATCH_NAME="${1:-quick_test_$(date +%Y%m%d_%H%M%S)}"
TASK_LIMIT=2
PROPERTY_TYPES=("reachability" "bgp_configuration" "ospf_configuration")
MODELS=(
    "openai:gpt-5-mini"
    "gemini:gemini-2.5-pro"
)

echo "================================================================================"
echo "QUICK BENCHMARK TEST"
echo "================================================================================"
echo "Batch Name: $BATCH_NAME"
echo "Task Limit: $TASK_LIMIT per property type (quick test)"
echo "Property Types: ${PROPERTY_TYPES[@]}"
echo "Models: ${MODELS[@]}"
echo ""
echo "Total Tasks: $((${#PROPERTY_TYPES[@]} * ${#MODELS[@]} * TASK_LIMIT))"
echo "Estimated Time: 1-2 hours"
echo "================================================================================"
echo ""

# Log file
LOG_FILE="logs/benchmark_${BATCH_NAME}.log"
mkdir -p logs
echo "Logging to: $LOG_FILE"
echo ""

# Function to log and execute
run_cmd() {
    echo ">>> $@" | tee -a "$LOG_FILE"
    "$@" 2>&1 | tee -a "$LOG_FILE"
    local exit_code=${PIPESTATUS[0]}
    if [ $exit_code -ne 0 ]; then
        echo "ERROR: Command failed with exit code $exit_code" | tee -a "$LOG_FILE"
        echo "Continuing with next task..." | tee -a "$LOG_FILE"
    fi
    echo "" | tee -a "$LOG_FILE"
    return $exit_code
}

# Start time
START_TIME=$(date +%s)
echo "Start Time: $(date)" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Phase 1: Run benchmarks
echo "================================================================================" | tee -a "$LOG_FILE"
echo "PHASE 1: RUNNING BENCHMARKS" | tee -a "$LOG_FILE"
echo "================================================================================" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

task_counter=0
total_tasks=$((${#PROPERTY_TYPES[@]} * ${#MODELS[@]}))

for property in "${PROPERTY_TYPES[@]}"; do
    for model_spec in "${MODELS[@]}"; do
        task_counter=$((task_counter + 1))
        
        IFS=':' read -r provider model <<< "$model_spec"
        
        echo "[$task_counter/$total_tasks] Running $property with $provider:$model" | tee -a "$LOG_FILE"
        
        run_cmd poetry run benchmark run-llm "$property" \
            --provider "$provider" \
            --model "$model" \
            --limit "$TASK_LIMIT"
        
        sleep 2
    done
done

# Phase 2: Run analyses
echo "================================================================================" | tee -a "$LOG_FILE"
echo "PHASE 2: RUNNING STATISTICAL ANALYSIS" | tee -a "$LOG_FILE"
echo "================================================================================" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

run_cmd poetry run benchmark analyze \
    "llm_openai_gpt-5-mini,llm_gemini_gemini-2.5-pro" \
    --batch-name "$BATCH_NAME"

for property in "${PROPERTY_TYPES[@]}"; do
    run_cmd poetry run benchmark analyze "$property" --batch-name "$BATCH_NAME"
done

run_cmd poetry run benchmark analyze "llm_openai_gpt-5-mini" --batch-name "$BATCH_NAME"
run_cmd poetry run benchmark analyze "llm_gemini_gemini-2.5-pro" --batch-name "$BATCH_NAME"

# End time
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
HOURS=$((DURATION / 3600))
MINUTES=$(((DURATION % 3600) / 60))

echo "" | tee -a "$LOG_FILE"
echo "================================================================================" | tee -a "$LOG_FILE"
echo "QUICK TEST COMPLETE" | tee -a "$LOG_FILE"
echo "================================================================================" | tee -a "$LOG_FILE"
echo "Duration: ${HOURS}h ${MINUTES}m" | tee -a "$LOG_FILE"
echo "Results: results/analysis/$BATCH_NAME/" | tee -a "$LOG_FILE"
echo "Log: $LOG_FILE" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

