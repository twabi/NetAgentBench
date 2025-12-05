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
TASK_LIMIT=1
PROPERTY_TYPES=("reachability" "bgp_configuration" "ospf_configuration")
MODELS=(
    "ollama:qwen3:30b:http://10.23.52.8:11434"
    "ollama:deepseek-r1:70b:http://10.23.52.8:11434"
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
        
        # Parse model_spec: provider:model:base_url or provider:model
        # Handle URLs that contain colons by looking for http:// or https://
        if [[ "$model_spec" == *"http://"* ]] || [[ "$model_spec" == *"https://"* ]]; then
            # Extract provider (first field before first colon)
            provider="${model_spec%%:*}"
            # Extract base_url (everything from http:// or https:// to end, including the protocol)
            if [[ "$model_spec" == *"http://"* ]]; then
                base_url="${model_spec#*http://}"
                base_url="http://${base_url}"
            else
                base_url="${model_spec#*https://}"
                base_url="https://${base_url}"
            fi
            # Extract model (everything between provider: and :http:// or :https://)
            # Remove provider: prefix
            temp="${model_spec#${provider}:}"
            # Remove :base_url suffix (but base_url includes http://, so we need to remove :http://...)
            if [[ "$base_url" == "http://"* ]]; then
                model="${temp%:http://*}"
            else
                model="${temp%:https://*}"
            fi
        else
            # Simple case: provider:model (no base_url)
            IFS=':' read -r provider model <<< "$model_spec"
            base_url=""
        fi
        
        echo "[$task_counter/$total_tasks] Running $property with $provider:$model" | tee -a "$LOG_FILE"
        
        cmd_args=(poetry run benchmark run-llm "$property" \
            --provider "$provider" \
            --model "$model" \
            --limit "$TASK_LIMIT")
            
        if [ ! -z "$base_url" ]; then
            cmd_args+=(--base-url "$base_url")
        fi

        run_cmd "${cmd_args[@]}"
        
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

