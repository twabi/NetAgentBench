"""
HTTP tests against the trimmed harness FastAPI app.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from dagent.harness_main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_run_benchmark_agent():
    with patch(
        "dagent.web.router.benchmark.run_benchmark_agent",
        new_callable=AsyncMock,
    ) as mock:
        yield mock


def test_health_check(client):
    response = client.get("/benchmark/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "netagentbench-agent-harness"


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "health" in r.json()


def test_solve_task_single(client, mock_run_benchmark_agent):
    mock_run_benchmark_agent.return_value = {
        "success": True,
        "turns_used": 5,
        "actions_executed": [{"action": "test"}],
        "reasoning_trace": [],
        "error": None,
        "token_usage": {},
        "tool_usage": {},
        "agent_conversations": [],
    }

    response = client.post(
        "/benchmark/solve",
        json={
            "task_id": "t1",
            "description": "test task",
            "nodes": ["n1"],
            "properties": [],
            "mcp_url": "http://mcp",
            "agent_mode": "single",
            "provider": "openai",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["turns_used"] == 5
    assert data["commands_executed"] == 1
    assert data["model_version"] == "openai:default"

    kwargs = mock_run_benchmark_agent.await_args.kwargs
    assert kwargs["agent_config"] == {
        "mode": "single",
        "provider": "openai",
        "structure": "sequential",
        "api_key": None,
        "host": None,
        "context_length": None,
    }


def test_solve_task_multi(client, mock_run_benchmark_agent):
    mock_run_benchmark_agent.return_value = {
        "success": True,
        "turns_used": 10,
        "actions_executed": [],
        "reasoning_trace": [],
        "error": None,
        "token_usage": {},
        "tool_usage": {},
        "agent_conversations": [],
    }

    response = client.post(
        "/benchmark/solve",
        json={
            "task_id": "t2",
            "description": "test",
            "nodes": ["n1"],
            "properties": [],
            "mcp_url": "http://mcp",
            "agent_mode": "multi",
            "structure": "sequential",
            "provider": "ollama",
            "model": "llama3",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["model_version"] == "ollama:llama3"

    kwargs = mock_run_benchmark_agent.await_args.kwargs
    assert kwargs["agent_config"]["mode"] == "multi"
    assert kwargs["agent_config"]["provider"] == "ollama"
    assert kwargs["agent_config"]["model"] == "llama3"
