#!/usr/bin/env bash
# Single-agent sweep on the five corrected v2 tasks, through OpenRouter.
# Labs are sequential. Each session logs per-turn snapshots.
#
# Start the agent harness first (it provides the OpenRouter provider):
#   cd agent_harness && poetry run uvicorn dagent.harness_main:app --host 0.0.0.0 --port 8000
set -euo pipefail

DAGENT_ENDPOINT="${DAGENT_ENDPOINT:-http://localhost:8000}"
REPEATS="${REPEATS:-3}"
TURN_LIMIT="${TURN_LIMIT:-100}"
TIME_LIMIT="${TIME_LIMIT:-1800}"
OUTPUT_DIR="${OUTPUT_DIR:-results/v2_openrouter}"
MODELS=(
  "openrouter:qwen/qwen3.8-flash"
  "openrouter:google/gemini-3.1-flash-lite"
  "openrouter:openai/gpt-6-luna"
  "openrouter:z-ai/glm-5.3"
)
TASKS=(
  tasks/multi_turn_v2/ccna_rip_routing_basic.json
  tasks/multi_turn_v2/troubleshoot_ospf_adjacency_issue.json
  tasks/multi_turn_v2/ccnp_multiarea_ospf_intermediate.json
  tasks/multi_turn_v2/ccie_bgp_dual_homing_expert.json
  tasks/multi_turn_v2/troubleshoot_bgp_route_filtering.json
)

mkdir -p "${OUTPUT_DIR}"
for task in "${TASKS[@]}"; do
  for spec in "${MODELS[@]}"; do
    provider="${spec%%:*}"
    model="${spec#*:}"
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
