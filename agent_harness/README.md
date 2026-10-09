# NetAgentBench agent harness

This subdirectory is a **standalone Poetry project** that runs a minimal FastAPI service the NetAgentBench CLI talks to (`benchmark run-task --dagent-endpoint …`). It is **not** the full upstream dagent framework—only MCP-facing benchmark logic is vendored here.

Supported multi-agent **`structure`** values when `agent_mode` is `multi`: `sequential`, `concurrent`, `debate`, `group_chat`. The **`adaptive`** structure is intentionally omitted from this snapshot.

## Install

Requires Python ≥ 3.12.

```bash
cd agent_harness
poetry install
```

If `poetry install` fails with **SecretServiceNotAvailableException** / **DBusErrorResponse** on headless Linux, rerun with:

`PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring poetry install`

## Run

```bash
cd agent_harness
poetry run uvicorn dagent.harness_main:app --host 0.0.0.0 --port 8000
```

Health check: `GET http://localhost:8000/benchmark/health`

## Environment variables (typical)

- **OpenRouter** (used for the manuscript runs): `OPEN_ROUTER_API_KEY`
- **OpenAI**: `OPENAI_API_KEY`
- **Anthropic**: `ANTHROPIC_API_KEY`
- **Gemini** (via OpenAI-compatible endpoint): `GEMINI_API_KEY` or `GOOGLE_API_KEY`
- **Ollama**: pass `host` in the solve request body (e.g. `http://localhost:11434`) or rely on defaults in the provider

Variables can also be put in a `.env` file in this folder; it is read at startup if `python-dotenv` is installed. Secrets must not be committed; use env vars or inject `api_key` per request **without** logging them.

## Pairing with NetAgentBench

1. Start the benchmark MCP URL your task expects (same as documented in the main repo).
2. Start this harness as above.
3. From the main repo: `poetry run benchmark run-task … --dagent-endpoint http://127.0.0.1:8000` (plus your MCP/lab flags as usual).

The harness receives the task definition and `mcp_url` from the controller and connects to NetAgentBench over MCP streamable HTTP. Before the task reaches the model, `dagent/benchmark/arms.py` removes the injected fault (`preconfiguration`), the reference solution, `research_context`, `fault_verification`, and each property's evaluation check; the agent sees the goal and the topology.

## Reproducing the manuscript runs

The 400 runs in `experiments_reports/` were produced by the agent server at the state reproduced here (single-agent mode, provider `openrouter`), with:

```bash
poetry run benchmark run-task tasks/multi_turn_v2/<task>.json \
  --dagent-endpoint http://127.0.0.1:8000 \
  --provider openrouter --model <model> --agent-mode single \
  --turn-limit 100 --time-limit 1800 --reveal-snapshots
```

Models: `openai/gpt-5-mini`, `meta-llama/llama-3.3-70b-instruct`, `qwen/qwen3-coder-30b-a3b-instruct`, `qwen/qwen3-coder-next`, `qwen/qwen3.8-flash`, `google/gemini-3.1-flash-lite`, `openai/gpt-6-luna`, `z-ai/glm-5.3`.

## License

Apache-2.0 (same as the parent NetAgentBench repository). See [NOTICE](NOTICE) for upstream attribution.
