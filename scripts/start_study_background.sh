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

# Handing existing dagent processes
if pgrep -f "uvicorn dagent.main:app" > /dev/null; then
    echo "Warning: dagent server seems to be running already."
    echo "Please kill it first if you want to restart it from this script."
    # Optional: pkill -f "uvicorn dagent.main:app"
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

# Run study in background
nohup ${STUDY_SCRIPT} > "${LOG_FILE}" 2>&1 &
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
echo "To stop:"
echo "  kill \$(cat study.pid dagent.pid 2>/dev/null) # Or use pkill -f \"run_comparative_multiturn_study.sh\""
echo "============================================================"
