"""
MCP client for benchmark server interaction.
"""

import json
import logging
from typing import Optional, Dict, Any, List

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

logger = logging.getLogger(__name__)


class BenchmarkMCPClient:
    """
    Client for connecting to the benchmark MCP server.
    
    Wraps the MCP client session and provides convenient methods
    for calling benchmark tools.
    """
    
    def __init__(self, mcp_url: str):
        self.mcp_url = mcp_url
        self._session: Optional[ClientSession] = None
        self._client = None
        
    async def connect(self) -> None:
        """Connect to the MCP server."""
        logger.info(f"Connecting to MCP server at {self.mcp_url}")
        self._client = streamablehttp_client(self.mcp_url)
        read, write, _ = await self._client.__aenter__()
        self._session = ClientSession(read, write)
        await self._session.__aenter__()
        await self._session.initialize()
        logger.info("MCP connection established")
        
    async def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        if self._session:
            await self._session.__aexit__(None, None, None)
        if self._client:
            await self._client.__aexit__(None, None, None)
        logger.info("MCP connection closed")
        
    async def get_nodes(self) -> List[str]:
        """Get list of available nodes."""
        result = await self._session.call_tool("get_nodes", {})
        if result.content and len(result.content) > 0:
            text = result.content[0].text
            data = json.loads(text)
            return data.get("nodes", [])
        return []
    
    async def exec_command(
        self, 
        node: str, 
        command: str, 
        command_type: str = "config"
    ) -> Dict[str, Any]:
        """Execute a command on a node."""
        result = await self._session.call_tool("exec_command", {
            "node": node,
            "command": command,
            "command_type": command_type,
        })
        if result.content and len(result.content) > 0:
            text = result.content[0].text
            return json.loads(text)
        return {"success": False, "error": "No response"}
    
    async def submit(self) -> Dict[str, Any]:
        """Submit the solution."""
        result = await self._session.call_tool("submit", {})
        if result.content and len(result.content) > 0:
            text = result.content[0].text
            return json.loads(text)
        return {"success": False}
    
    async def get_session_status(self) -> Dict[str, Any]:
        """Get current session status (turns, time remaining)."""
        result = await self._session.call_tool("get_session_status", {})
        if result.content and len(result.content) > 0:
            text = result.content[0].text
            return json.loads(text)
        return {"success": False, "error": "No response"}

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools."""
        result = await self._session.list_tools()
        # Convert ListToolsResult to list of dicts if needed, or return raw tools
        # result.tools is a list of Tool objects.
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema
            }
            for tool in result.tools
        ]
