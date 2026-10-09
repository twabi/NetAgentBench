#!/usr/bin/env bash
# New agent runs for the two corrected OSPF tasks (their topology changed, so old logs
# cannot be replayed). Apply harness_fixes.patch first so the final evaluation waits the
# task's full convergence budget (60 s) instead of the old 30 s cap.
#
# Usage:
#   REPEATS=3 MODELS="openai:gpt-5-mini-2025-08-07" ./experiments/replay_v2/run_v2_ospf.sh
# Then replay each new run with replay_v2.py after adding the two OSPF task ids to REPLAYABLE
# (their v2 topology now matches the logs).
set -euo pipefail

DAGENT_ENDPOINT="${DAGENT_ENDPOINT:-http://localhost:8000}"
REPEATS="${REPEATS:-3}"
MODELS="${MODELS:-openai:gpt-5-mini-2025-08-07}"
TURN_LIMIT="${TURN_LIMIT:-100}"
TIME_LIMIT="${TIME_LIMIT:-1800}"
OUTPUT_DIR="${OUTPUT_DIR:-results/v2_ospf_runs}"
TASKS=(
  tasks/multi_turn_v2/troubleshoot_ospf_adjacency_issue.json
  tasks/multi_turn_v2/ccnp_multiarea_ospf_intermediate.json
)

mkdir -p "${OUTPUT_DIR}"
for task in "${TASKS[@]}"; do
  for spec in ${MODELS}; do
    IFS=':' read -r provider model <<< "${spec}"
    for rep in $(seq 1 "${REPEATS}"); do
      echo "== ${task} | ${provider}:${model} | rep ${rep}/${REPEATS}"
      poetry run benchmark run-task "${task}" \
        --dagent-endpoint "${DAGENT_ENDPOINT}" \
        --provider "${provider}" --model "${model}" \
        --agent-mode single \
        --turn-limit "${TURN_LIMIT}" --time-limit "${TIME_LIMIT}" \
        --reveal-snapshots \
        --output-dir "${OUTPUT_DIR}" || echo "   run failed (recorded by harness)"
    done
  done
done
