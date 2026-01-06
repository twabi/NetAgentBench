#!/bin/bash
# run_baseline_study.sh
# Runs baseline benchmark evaluation and groups all results into one dated session folder

set -e

# Configuration
LIMIT=30
DAGENT_ENDPOINT="http://localhost:8000"

# Create dated session folder
SESSION_NAME="baseline_study_$(date +%Y%m%d_%H%M%S)"
OUTPUT_DIR="results/sessions/${SESSION_NAME}"
mkdir -p "${OUTPUT_DIR}"

echo "============================================================"
echo "Baseline Benchmark Study"
echo "============================================================"
echo "Session: ${SESSION_NAME}"
echo "Output:  ${OUTPUT_DIR}"
echo "Limit:   ${LIMIT} tasks per property"
echo "Models:  GPT-5-mini-2025-08-07, Gemini-2.5-pro"
echo "============================================================"
echo ""

# Create session metadata
cat > "${OUTPUT_DIR}/session_info.json" << EOF
{
  "session_name": "${SESSION_NAME}",
  "started_at": "$(date -Iseconds)",
  "limit_per_property": ${LIMIT},
  "models": ["gpt-5-mini-2025-08-07", "gemini-2.5-pro"],
  "property_types": ["reachability", "ospf_configuration", "bgp_configuration"],
  "dagent_endpoint": "${DAGENT_ENDPOINT}"
}
EOF

cd ~/python_projects/benchmark

# Track progress
TOTAL=6
CURRENT=0

run_benchmark() {
    local property=$1
    local platform=$2
    local provider=$3
    local model=$4
    CURRENT=$((CURRENT + 1))
    
    echo ""
    echo "[${CURRENT}/${TOTAL}] Running ${property} (${platform}) with ${provider}/${model}..."
    echo "------------------------------------------------------------"
    
    poetry run benchmark run-dagent "${property}" \
        --endpoint "${DAGENT_ENDPOINT}" \
        --platform "${platform}" \
        --limit ${LIMIT} \
        --provider "${provider}" \
        --model "${model}" \
        --output-dir "${OUTPUT_DIR}"
}

# GPT-5 runs
run_benchmark reachability generic openai gpt-5-mini-2025-08-07
run_benchmark ospf_configuration frr openai gpt-5-mini-2025-08-07
run_benchmark bgp_configuration frr openai gpt-5-mini-2025-08-07

# Gemini runs
run_benchmark reachability generic gemini gemini-2.5-pro
run_benchmark ospf_configuration frr gemini gemini-2.5-pro
run_benchmark bgp_configuration frr gemini gemini-2.5-pro

# Update session metadata with completion time
cat > "${OUTPUT_DIR}/session_info.json" << EOF
{
  "session_name": "${SESSION_NAME}",
  "started_at": "$(date -Iseconds)",
  "completed_at": "$(date -Iseconds)",
  "limit_per_property": ${LIMIT},
  "models": ["gpt-5-mini-2025-08-07", "gemini-2.5-pro"],
  "property_types": ["reachability", "ospf_configuration", "bgp_configuration"],
  "dagent_endpoint": "${DAGENT_ENDPOINT}",
  "total_runs": ${TOTAL}
}
EOF

echo ""
echo "============================================================"
echo "Baseline Study Complete!"
echo "============================================================"
echo "All results saved to: ${OUTPUT_DIR}"
echo ""
echo "To analyze:"
echo "  poetry run benchmark analyze ${OUTPUT_DIR}"
echo ""
