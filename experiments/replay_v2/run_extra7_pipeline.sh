#!/usr/bin/env bash
# Extra-repeats cohort: unit-test gate, 280 OpenRouter sessions (8 models x
# 5 tasks x 7 repeats), full-sequence replay, then both analyses. Writes only
# under the extra7 directories below; earlier cohorts are left untouched, and
# no PDF is copied into the manuscript directory.
#
# Restarting this script skips sessions and replays that already finished.
# A cell is retried up to three times, then the script moves on. If the sweep
# is still short of 280 scored logs, it stops before replay so the next run
# fills the holes.
#
# The agent server (agent_harness/: poetry run uvicorn dagent.harness_main:app --port 8000)
# must already be listening on port 8000. This script does not start it.
set -u

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "${ROOT}"

DAGENT_ENDPOINT="${DAGENT_ENDPOINT:-http://127.0.0.1:8000}"
REPEATS="${REPEATS:-7}"
TURN_LIMIT="${TURN_LIMIT:-100}"
TIME_LIMIT="${TIME_LIMIT:-1800}"
ATTEMPTS="${ATTEMPTS:-3}"
BACKOFF_S="${BACKOFF_S:-20}"

OUTPUT_DIR="results/v2_openrouter_extra7"
REPLAY_DIR="experiments/replay_v2/out/v2_openrouter_extra7_replay"
SWEEP_ANALYSIS="experiments/replay_v2/out/v2_openrouter_extra7_analysis"
PROCESS_ANALYSIS="experiments/replay_v2/out/v2_openrouter_extra7_process"
LOG="${OUTPUT_DIR}/pipeline.log"

OLD_RUNS="results/v2_openrouter"
OLD_ANALYSIS="experiments/replay_v2/out/v2_openrouter_analysis"
OLD_PROCESS="experiments/replay_v2/out/process_analysis"
OLD_REPLAY="experiments/replay_v2/out/v2_openrouter_replay"

MODELS=(
  "openrouter:qwen/qwen3.8-flash"
  "openrouter:google/gemini-3.1-flash-lite"
  "openrouter:openai/gpt-6-luna"
  "openrouter:z-ai/glm-5.3"
  "openrouter:openai/gpt-5-mini"
  "openrouter:meta-llama/llama-3.3-70b-instruct"
  "openrouter:qwen/qwen3-coder-30b-a3b-instruct"
  "openrouter:qwen/qwen3-coder-next"
)
TASKS=(
  tasks/multi_turn_v2/ccna_rip_routing_basic.json
  tasks/multi_turn_v2/troubleshoot_ospf_adjacency_issue.json
  tasks/multi_turn_v2/ccnp_multiarea_ospf_intermediate.json
  tasks/multi_turn_v2/ccie_bgp_dual_homing_expert.json
  tasks/multi_turn_v2/troubleshoot_bgp_route_filtering.json
)
TASK_IDS="ccna_rip_routing_basic,troubleshoot_ospf_adjacency_issue,ccnp_multiarea_ospf_intermediate,ccie_bgp_dual_homing_expert,troubleshoot_bgp_route_filtering"

for forbidden in "${OLD_RUNS}" "${OLD_ANALYSIS}" "${OLD_PROCESS}" "${OLD_REPLAY}"; do
  if [[ "${OUTPUT_DIR}" == "${forbidden}" || "${REPLAY_DIR}" == "${forbidden}" || "${SWEEP_ANALYSIS}" == "${forbidden}" || "${PROCESS_ANALYSIS}" == "${forbidden}" ]]; then
    echo "refusing to write into an existing cohort directory: ${forbidden}" >&2
    exit 1
  fi
done

mkdir -p "${OUTPUT_DIR}"
exec > >(tee -a "${LOG}") 2>&1
echo "== pipeline start $(date -Is)"

echo "== pytest gate"
poetry run pytest \
  tests/unit/test_interactive_session.py \
  experiments/replay_v2/tests/test_replay_agreement.py \
  experiments/replay_determinism/tests/test_parse_log.py \
  experiments/replay_v2/tests/test_process_classify.py \
  experiments/replay_v2/tests/test_snapshots.py \
  -q --tb=line
echo "== pytest passed"

if docker ps --filter name=clab-bench_ --format '{{.Names}}' | grep -q .; then
  echo "a clab-bench_ lab is already running; refusing to start a second one" >&2
  exit 1
fi

# dagent is required only when a cell still needs a live session. Replay does not call it.

count_scored() {
  # Write the integer to a file, then print that file. A here-doc or a
  # command-substitution echo under the log redirect came back as 0.
  local tally="${OUTPUT_DIR}/.scored_tally"
  python3 -c '
import json
import sys
from pathlib import Path

task_id, testee, output_dir = sys.argv[1:]
root = Path(output_dir) / "runs" / task_id
n = 0
if root.is_dir():
    for path in root.glob(testee + "_*.json"):
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data.get("scoring"), dict):
            n += 1
print(n)
' "$1" "$2" "${OUTPUT_DIR}" > "${tally}"
  cat "${tally}"
}

total_scored() {
  local total=0
  local task spec provider model safe testee n
  for task in "${TASKS[@]}"; do
    local task_id
    task_id="$(basename "${task}" .json)"
    for spec in "${MODELS[@]}"; do
      provider="${spec%%:*}"
      model="${spec#*:}"
      safe="$(printf '%s' "${model}" | tr -d '.:/-')"
      testee="${provider}_${safe}_single"
      count_scored "${task_id}" "${testee}" >/dev/null
      n="$(tr -cd '0-9' < "${OUTPUT_DIR}/.scored_tally")"
      total=$((total + n))
    done
  done
  echo "${total}" > "${OUTPUT_DIR}/.scored_total"
  echo "${total}"
}

scored_from_file() {
  tr -cd '0-9' < "$1"
}

echo "== sweep into ${OUTPUT_DIR} (existing scored logs are kept)"
for task in "${TASKS[@]}"; do
  task_id="$(basename "${task}" .json)"
  for spec in "${MODELS[@]}"; do
    provider="${spec%%:*}"
    model="${spec#*:}"
    safe="$(printf '%s' "${model}" | tr -d '.:/-')"
    testee="${provider}_${safe}_single"
    count_scored "${task_id}" "${testee}" >/dev/null
    have="$(tr -cd '0-9' < "${OUTPUT_DIR}/.scored_tally")"
    while [[ "${have}" -lt "${REPEATS}" ]]; do
      ok=0
      for attempt in $(seq 1 "${ATTEMPTS}"); do
        echo "== ${task_id} | ${model} | have ${have}/${REPEATS} | attempt ${attempt}/${ATTEMPTS}"
        if ! curl -sf --max-time 5 "${DAGENT_ENDPOINT}/openapi.json" >/dev/null; then
          echo "dagent is not answering at ${DAGENT_ENDPOINT}; start it and rerun" >&2
          exit 1
        fi
        if poetry run benchmark run-task "${task}" \
          --dagent-endpoint "${DAGENT_ENDPOINT}" \
          --provider "${provider}" --model "${model}" \
          --agent-mode single \
          --turn-limit "${TURN_LIMIT}" --time-limit "${TIME_LIMIT}" \
          --reveal-snapshots \
          --output-dir "${OUTPUT_DIR}"; then
          :
        else
          echo "   benchmark exited nonzero"
        fi
        count_scored "${task_id}" "${testee}" >/dev/null
        now="$(tr -cd '0-9' < "${OUTPUT_DIR}/.scored_tally")"
        if [[ "${now}" -gt "${have}" ]]; then
          have="${now}"
          ok=1
          break
        fi
        echo "   no new scored log; sleeping ${BACKOFF_S}s"
        sleep "${BACKOFF_S}"
      done
      if [[ "${ok}" -ne 1 ]]; then
        echo "   giving up on this cell for now (${task_id} ${model})"
        break
      fi
    done
  done
done

total_scored >/dev/null
scored="$(scored_from_file "${OUTPUT_DIR}/.scored_total")"
EXPECTED=$(( ${#MODELS[@]} * ${#TASKS[@]} * REPEATS ))
echo "== scored sessions: ${scored}/${EXPECTED}"
if [[ "${scored}" -ne "${EXPECTED}" ]]; then
  echo "sweep is short of ${EXPECTED} scored logs; replay and analysis wait for the next run" >&2
  exit 1
fi

echo "== replay into ${REPLAY_DIR}"
mkdir -p "${REPLAY_DIR}"
replay_ok=0
for attempt in $(seq 1 "${ATTEMPTS}"); do
  echo "== replay attempt ${attempt}/${ATTEMPTS}"
  if poetry run python experiments/replay_v2/replay_v2.py \
    --runs-dir "${OUTPUT_DIR}/runs" \
    --tasks "${TASK_IDS}" \
    --infra containerlab --repeats 3 --resume \
    --out-dir "${REPLAY_DIR}"; then
    replay_ok=1
    break
  fi
  echo "   replay exited nonzero; sleeping ${BACKOFF_S}s"
  sleep "${BACKOFF_S}"
done
if [[ "${replay_ok}" -ne 1 ]]; then
  echo "replay did not finish; rerun this script to resume" >&2
  exit 1
fi

echo "== analyses (no manuscript copy)"
mkdir -p "${SWEEP_ANALYSIS}" "${PROCESS_ANALYSIS}"
poetry run python experiments/replay_v2/analyze_v2_sweep.py \
  --runs-dir "${OUTPUT_DIR}/runs" \
  --out-dir "${SWEEP_ANALYSIS}" \
  --paper-dir /dev/null
poetry run python experiments/replay_v2/analyze_process.py \
  --runs-dir "${OUTPUT_DIR}/runs" \
  --out-dir "${PROCESS_ANALYSIS}"
echo "== pipeline done $(date -Is)"
