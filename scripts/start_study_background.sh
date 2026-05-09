#!/bin/bash
# start_study_background.sh
# Uses nohup to run both the agent harness (`agent_harness/`) and the study in background.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}" || exit 1

# Configuration
LOG_FILE="${STUDY_LOG_FILE:-${REPO_ROOT}/study.log}"
DAGENT_LOG="${DAGENT_LOG_FILE:-${REPO_ROOT}/dagent_server.log}"
STUDY_SCRIPT="${STUDY_SCRIPT:-${REPO_ROOT}/scripts/run_comparative_multiturn_study.sh}"
DAGENT_DIR="${DAGENT_DIR:-${REPO_ROOT}/agent_harness}"

echo "============================================================"
echo "Starting Background Study Session"
echo "============================================================"

# Use port 8000 as source of truth (study expects dagent on 8000)
DAGENT_PORT=8000
if ss -tlnp 2>/dev/null | grep -q ":${DAGENT_PORT}[^0-9]" || netstat -tlnp 2>/dev/null | grep -q ":${DAGENT_PORT}[^0-9]"; then
    echo "Agent harness already listening on port ${DAGENT_PORT}; skipping server start."
else
    echo "Starting agent harness in background..."
    echo "  > Log: ${DAGENT_LOG}"

    if [ ! -d "$DAGENT_DIR" ]; then
        echo "Error: agent harness not found at ${DAGENT_DIR}. Install from repo agent_harness/ or set DAGENT_DIR to your checkout."
        exit 1
    fi

    cd "$DAGENT_DIR" || exit 1
    nohup env PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring \
      poetry run uvicorn dagent.harness_main:app --host 0.0.0.0 --port 8000 > "${DAGENT_LOG}" 2>&1 &
    DAGENT_PID=$!
    cd "${REPO_ROOT}" || exit 1

    echo "  > DAGENT_PID: ${DAGENT_PID}"
    echo "${DAGENT_PID}" > "${REPO_ROOT}/dagent.pid"

    echo "Waiting 10s for agent harness to initialize..."
    sleep 10
fi

echo ""
echo "Starting benchmark study in background..."
echo "  > Log: ${LOG_FILE}"

if command -v setsid >/dev/null 2>&1; then
    setsid nohup "${STUDY_SCRIPT}" > "${LOG_FILE}" 2>&1 &
else
    nohup "${STUDY_SCRIPT}" > "${LOG_FILE}" 2>&1 &
fi
STUDY_PID=$!
echo "${STUDY_PID}" > "${REPO_ROOT}/study.pid"

echo "  > STUDY_PID:  ${STUDY_PID}"
echo ""
echo "============================================================"
echo "Processes running in background."
echo "To monitor:"
echo "  tail -f ${LOG_FILE}"
echo "  tail -f ${DAGENT_LOG}"
echo ""
echo "To stop (kills study + all benchmark children, e.g. MCP on 8001):"
echo "  kill -TERM -\$(cat ${REPO_ROOT}/study.pid 2>/dev/null) 2>/dev/null; kill \$(cat ${REPO_ROOT}/dagent.pid 2>/dev/null) 2>/dev/null"
echo "  # If no setsid: pkill -f run_comparative_multiturn_study.sh; pkill -f 'benchmark run-task'; kill \$(cat ${REPO_ROOT}/dagent.pid 2>/dev/null)"
echo "============================================================"
