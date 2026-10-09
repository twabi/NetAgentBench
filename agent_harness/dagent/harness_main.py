"""
NetAgentBench agent harness entrypoint.

Run: poetry run uvicorn dagent.harness_main:app --host 0.0.0.0 --port 8000
"""

from fastapi import FastAPI

try:  # read OPEN_ROUTER_API_KEY etc. from a local .env if python-dotenv is installed
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from dagent.web.router.benchmark import benchmark_router

app = FastAPI(
    title="NetAgentBench agent harness",
    version="0.1.0",
    description="HTTP surface for benchmark run-task: /benchmark/solve, /generate, /health",
)

app.include_router(benchmark_router)


@app.get("/")
async def root() -> dict:
    return {
        "service": "netagentbench-agent-harness",
        "health": "/benchmark/health",
    }
