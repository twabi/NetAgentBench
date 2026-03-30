#!/bin/bash
# start_study_background.sh
# Uses nohup to run both dagent and the study in background for persistent sessions.

# Configuration
LOG_FILE="study.log"
DAGENT_LOG="dagent_server.log"
STUDY_SCRIPT="./scripts/run_comparative_multiturn_study.sh"

echo "============================================================"
echo "Starting Background Study Session"
echo "============================================================"

# Use port 8000 as source of truth (study expects dagent on 8000)
DAGENT_PORT=8000
if ss -tlnp 2>/dev/null | grep -q ":${DAGENT_PORT}[^0-9]" || netstat -tlnp 2>/dev/null | grep -q ":${DAGENT_PORT}[^0-9]"; then
    echo "dagent already listening on port ${DAGENT_PORT}; skipping server start."
else
    echo "Starting dagent server in background..."
    echo "  > Log: ${DAGENT_LOG}"
    
    # Start dagent server in background
    # Assuming dagent is in ../dagent relative to network-benchmark root or absolute path
    if [ -d "../dagent" ]; then
        cd ../dagent
        nohup poetry run uvicorn dagent.main:app --host 0.0.0.0 --port 8000 > "../network-benchmark/${DAGENT_LOG}" 2>&1 &
        DAGENT_PID=$!
        cd ../network-benchmark
    elif [ -d "/root/dagent" ]; then
        cd /root/dagent
        nohup poetry run uvicorn dagent.main:app --host 0.0.0.0 --port 8000 > "/root/network-benchmark/${DAGENT_LOG}" 2>&1 &
        DAGENT_PID=$!
        cd /root/network-benchmark
    else
        echo "Error: Could not find dagent directory."
        exit 1
    fi
    
    echo "  > DAGENT_PID: ${DAGENT_PID}"
    echo "${DAGENT_PID}" > dagent.pid
    
    # Wait for server to initialize
    echo "Waiting 10s for dagent to initialize..."
    sleep 10
fi

echo ""
echo "Starting benchmark study in background..."
echo "  > Log: ${LOG_FILE}"

# Run study in its own process group so stopping kills shell + all children (benchmark, MCP on 8001)
if command -v setsid >/dev/null 2>&1; then
    setsid nohup ${STUDY_SCRIPT} > "${LOG_FILE}" 2>&1 &
else
    nohup ${STUDY_SCRIPT} > "${LOG_FILE}" 2>&1 &
fi
STUDY_PID=$!
echo "${STUDY_PID}" > study.pid

echo "  > STUDY_PID:  ${STUDY_PID}"
echo ""
echo "============================================================"
echo "Processes running in background."
echo "To monitor:"
echo "  tail -f ${LOG_FILE}"
echo "  tail -f ${DAGENT_LOG}"
echo ""
echo "To stop (kills study + all benchmark children, e.g. MCP on 8001):"
echo "  kill -TERM -\$(cat study.pid 2>/dev/null) 2>/dev/null; kill \$(cat dagent.pid 2>/dev/null) 2>/dev/null"
echo "  # If no setsid: pkill -f run_comparative_multiturn_study.sh; pkill -f 'benchmark run-task'; kill \$(cat dagent.pid 2>/dev/null)"
echo "============================================================"
