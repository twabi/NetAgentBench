#!/usr/bin/env python3
"""
Simple test agent that interacts with the benchmark MCP server.

This script simulates what a real agent would do:
1. Connect to the MCP server
2. Get session status and nodes
3. Execute commands to configure the network
4. Submit when done

Run this WHILE run-task is running with --wait-for-submit flag.
"""

import asyncio
import httpx
import json
import sys


async def call_mcp_tool(url: str, tool_name: str, arguments: dict = None):
    """Call an MCP tool via JSON-RPC."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments or {}
        }
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{url}/messages",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        return response.json()


async def run_agent():
    """Simulate agent interaction with MCP server."""
    mcp_url = "http://localhost:8001"
    
    print("=" * 60)
    print("Simple Test Agent")
    print("=" * 60)
    
    # Step 1: Get nodes
    print("\n[1] Getting nodes...")
    try:
        result = await call_mcp_tool(mcp_url, "get_nodes")
        print(f"    Nodes: {result}")
    except Exception as e:
        print(f"    Error connecting to MCP server: {e}")
        print("    Make sure run-task is running with --wait-for-submit flag")
        return
    
    # Step 2: Get session status
    print("\n[2] Getting session status...")
    result = await call_mcp_tool(mcp_url, "get_session_status")
    print(f"    Status: {result}")
    
    # Step 3: Configure R1 with IP
    print("\n[3] Configuring R1 with IP 10.0.0.1/24...")
    result = await call_mcp_tool(mcp_url, "exec_command", {
        "node": "R1",
        "command": "ip addr add 10.0.0.1/24 dev eth1",
        "command_type": "config"
    })
    print(f"    Result: {result}")
    
    # Step 4: Bring up R1 eth1
    print("\n[4] Bringing up R1 eth1...")
    result = await call_mcp_tool(mcp_url, "exec_command", {
        "node": "R1",
        "command": "ip link set eth1 up",
        "command_type": "config"
    })
    print(f"    Result: {result}")
    
    # Step 5: Configure R2 with IP
    print("\n[5] Configuring R2 with IP 10.0.0.2/24...")
    result = await call_mcp_tool(mcp_url, "exec_command", {
        "node": "R2",
        "command": "ip addr add 10.0.0.2/24 dev eth1",
        "command_type": "config"
    })
    print(f"    Result: {result}")
    
    # Step 6: Bring up R2 eth1
    print("\n[6] Bringing up R2 eth1...")
    result = await call_mcp_tool(mcp_url, "exec_command", {
        "node": "R2",
        "command": "ip link set eth1 up",
        "command_type": "config"
    })
    print(f"    Result: {result}")
    
    # Step 7: Verify R1 can ping R2
    print("\n[7] Verifying R1 can ping R2...")
    result = await call_mcp_tool(mcp_url, "exec_command", {
        "node": "R1",
        "command": "ping -c 2 -W 1 10.0.0.2",
        "command_type": "read"
    })
    print(f"    Result: {result}")
    
    # Step 8: Submit
    print("\n[8] Submitting solution...")
    result = await call_mcp_tool(mcp_url, "submit")
    print(f"    Result: {result}")
    
    print("\n" + "=" * 60)
    print("Agent completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_agent())
