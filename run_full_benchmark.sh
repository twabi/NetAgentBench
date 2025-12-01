#!/bin/bash
#
# Full Benchmark Comparison: GPT-5-mini vs Gemini 2.5 Pro
#
# This script runs 100 tasks per property type for both models (600 total tasks)
# and performs comprehensive statistical analysis.
#
# Estimated runtime: 20-30 hours
# Results will be saved in: results/analysis/<batch_name>/
#

set -e  # Exit on error

# Configuration
BATCH_NAME="${1:-benchmark_run_$(date +%Y%m%d_%H%M%S)}"
TASK_LIMIT=50
PROPERTY_TYPES=("reachability" "bgp_configuration" "ospf_configuration")
MODELS=(
    "openai:gpt-5-mini"
    "gemini:gemini-2.5-pro"
)

echo "================================================================================"
echo "FULL BENCHMARK COMPARISON"
echo "================================================================================"
echo "Batch Name: $BATCH_NAME"
echo "Task Limit: $TASK_LIMIT per property type"
echo "Property Types: ${PROPERTY_TYPES[@]}"
echo "Models: ${MODELS[@]}"
echo ""
echo "Total Tasks: $((${#PROPERTY_TYPES[@]} * ${#MODELS[@]} * TASK_LIMIT))"
echo "Estimated Time: 20-30 hours"
echo "================================================================================"
echo ""

read -p "Continue with benchmark run? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Benchmark cancelled."
    exit 0
fi

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
        echo "Failed command: $@" | tee -a "$LOG_FILE"
        # Continue despite errors to collect as much data as possible
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
        echo "--------------------------------------------------------------------------------" | tee -a "$LOG_FILE"
        
        run_cmd poetry run benchmark run-llm "$property" \
            --provider "$provider" \
            --model "$model" \
            --limit "$TASK_LIMIT"
        
        echo "Completed: $property with $provider:$model" | tee -a "$LOG_FILE"
        echo "" | tee -a "$LOG_FILE"
        
        # Optional: Add a brief pause to avoid API rate limits
        sleep 5
    done
done

echo "================================================================================" | tee -a "$LOG_FILE"
echo "PHASE 2: RUNNING STATISTICAL ANALYSIS" | tee -a "$LOG_FILE"
echo "================================================================================" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Phase 2: Run analyses
echo "Comparison Analysis: GPT-5-mini vs Gemini 2.5 Pro" | tee -a "$LOG_FILE"
run_cmd poetry run benchmark analyze \
    "llm_openai_gpt-5-mini,llm_gemini_gemini-2.5-pro" \
    --batch-name "$BATCH_NAME"

echo "" | tee -a "$LOG_FILE"

for property in "${PROPERTY_TYPES[@]}"; do
    echo "Property Analysis: $property" | tee -a "$LOG_FILE"
    run_cmd poetry run benchmark analyze \
        "$property" \
        --batch-name "$BATCH_NAME"
    echo "" | tee -a "$LOG_FILE"
done

echo "Testee Analysis: GPT-5-mini" | tee -a "$LOG_FILE"
run_cmd poetry run benchmark analyze \
    "llm_openai_gpt-5-mini" \
    --batch-name "$BATCH_NAME"

echo "" | tee -a "$LOG_FILE"

echo "Testee Analysis: Gemini 2.5 Pro" | tee -a "$LOG_FILE"
run_cmd poetry run benchmark analyze \
    "llm_gemini_gemini-2.5-pro" \
    --batch-name "$BATCH_NAME"

# End time
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
HOURS=$((DURATION / 3600))
MINUTES=$(((DURATION % 3600) / 60))
SECONDS=$((DURATION % 60))

echo "" | tee -a "$LOG_FILE"
echo "================================================================================" | tee -a "$LOG_FILE"
echo "BENCHMARK COMPLETE" | tee -a "$LOG_FILE"
echo "================================================================================" | tee -a "$LOG_FILE"
echo "End Time: $(date)" | tee -a "$LOG_FILE"
echo "Duration: ${HOURS}h ${MINUTES}m ${SECONDS}s" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"
echo "Results saved to: results/analysis/$BATCH_NAME/" | tee -a "$LOG_FILE"
echo "Log saved to: $LOG_FILE" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Display analysis results location
echo "Analysis files:" | tee -a "$LOG_FILE"
if [ -d "results/analysis/$BATCH_NAME" ]; then
    ls -lh "results/analysis/$BATCH_NAME/" | tee -a "$LOG_FILE"
else
    echo "Warning: Analysis directory not found" | tee -a "$LOG_FILE"
fi

echo "" | tee -a "$LOG_FILE"
echo "✅ Full benchmark comparison complete!" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

