"""Unit tests for BenchmarkMCPClient generic tool passthrough."""

import json

import pytest

from dagent.benchmark.mcp_client import BenchmarkMCPClient


class _FakeContent:
    def __init__(self, text):
        self.text = text


class _FakeResult:
    def __init__(self, payload):
        self.content = [_FakeContent(json.dumps(payload))]


class _FakeSession:
    def __init__(self):
        self.calls = []

    async def call_tool(self, name, args):
        self.calls.append((name, args))
        return _FakeResult({"success": True, "tool": name, "args": args})


@pytest.mark.asyncio
async def test_unknown_tool_is_proxied_to_mcp():
    client = BenchmarkMCPClient("http://localhost:0/mcp")
    client._session = _FakeSession()

    # check_properties has no explicit method; it must be proxied to call_tool.
    result = await client.check_properties()

    assert result["success"] is True
    assert result["tool"] == "check_properties"
    assert client._session.calls == [("check_properties", {})]


@pytest.mark.asyncio
async def test_proxy_forwards_kwargs():
    client = BenchmarkMCPClient("http://localhost:0/mcp")
    client._session = _FakeSession()

    await client.check_syntactic_validity()
    assert client._session.calls[-1] == ("check_syntactic_validity", {})


def test_private_attributes_still_raise():
    client = BenchmarkMCPClient("http://localhost:0/mcp")
    with pytest.raises(AttributeError):
        _ = client._not_a_real_private_attr
