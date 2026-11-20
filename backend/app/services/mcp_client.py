"""
Reusable Model Context Protocol (MCP) Client abstraction for Version 5.

Connects to the MCP Server, discovers registered tools dynamically, and executes
tool calls across transports (SSE HTTP, subprocess stdio, or direct in-process).
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import anyio
import httpx

from app.config import settings

logger = logging.getLogger("mcp_client")


def _convert_mcp_tool_to_openai_schema(tool: Any) -> Dict[str, Any]:
    """
    Translate an MCP Tool object into OpenAI/Groq standard function calling schema.
    """
    name = getattr(tool, "name", "")
    description = getattr(tool, "description", "") or ""
    schema = (
        getattr(tool, "input_schema", None)
        or getattr(tool, "inputSchema", None)
        or getattr(tool, "parameters", None)
        or {"type": "object", "properties": {}}
    )

    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": schema,
        },
    }


def is_port_open(host: str, port: int, timeout: float = 0.08) -> bool:
    """Instantly test if target host/port is accepting connections."""
    import socket
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


class MCPClient:
    """
    Standard MCP Client wrapper providing connect, disconnect, list_tools, and call_tool.
    """

    def __init__(self, server_url: Optional[str] = None, transport: Optional[str] = None) -> None:
        self.server_url = server_url or settings.MCP_SERVER_URL
        self.transport_mode = (transport or settings.MCP_TRANSPORT).lower()
        self._connected = False
        self._cached_tools: List[Any] = []
        self._cached_schemas: List[Dict[str, Any]] = []

    def _should_use_sse(self) -> bool:
        if self.transport_mode == "sse":
            return True
        if self.transport_mode in ("auto",):
            # Parse host and port from server_url
            try:
                from urllib.parse import urlparse
                parsed = urlparse(self.server_url)
                host = parsed.hostname or "127.0.0.1"
                port = parsed.port or 8001
                return is_port_open(host, port)
            except Exception:
                return False
        return False

    def connect(self) -> bool:
        """
        Establish connection to the MCP server and discover registered tools.

        Returns:
            bool: True if connection and tool discovery succeeded.
        """
        logger.info("[MCP Client] Connecting to MCP server...")
        try:
            if self._should_use_sse():
                self._cached_tools = anyio.run(self._async_list_tools)
            else:
                from mcp_server.server import mcp as local_server
                self._cached_tools = list(local_server._tool_manager.list_tools())

            self._cached_schemas = [_convert_mcp_tool_to_openai_schema(t) for t in self._cached_tools]
            tool_names = ", ".join(getattr(t, "name", str(t)) for t in self._cached_tools)
            logger.info("[MCP Client] Discovered tools: %s", tool_names)
            self._connected = True
            return True
        except Exception as err:
            logger.error("[MCP Client] Connection to MCP server failed: %s", err)
            self._connected = False
            return False

    def disconnect(self) -> None:
        """Disconnect and clear cached sessions."""
        logger.info("[MCP Client] Disconnecting from MCP server.")
        self._connected = False
        self._cached_tools = []
        self._cached_schemas = []

    def is_connected(self) -> bool:
        """Check if the client is connected and has discovered tools."""
        return self._connected and len(self._cached_tools) > 0

    async def _async_list_tools(self) -> List[Any]:
        """Discover tools from the MCP server based on the configured transport."""
        # 1. If SSE transport is active
        if self._should_use_sse():
            try:
                from mcp.client.session import ClientSession
                from mcp.client.sse import sse_client

                logger.info("[MCP Client] Connecting via SSE transport at %s", self.server_url)
                async with sse_client(self.server_url) as (read_stream, write_stream):
                    async with ClientSession(read_stream, write_stream) as session:
                        await session.initialize()
                        result = await session.list_tools()
                        return list(result.tools)
            except Exception as sse_err:
                logger.warning("[MCP Client] SSE connection failed (%s), using local MCP server instance.", sse_err)

        # 2. In-process fallback
        from mcp_server.server import mcp as local_server
        logger.info("[MCP Client] Querying local MCP server instance.")
        tools = await local_server.list_tools()
        return list(tools)

    def list_tools(self) -> List[Dict[str, Any]]:
        """
        Return the list of OpenAI/Groq compatible tool definition schemas discovered from MCP.

        Returns:
            List[Dict[str, Any]]: Tool function schemas.
        """
        if not self._connected or not self._cached_schemas:
            self.connect()
        return list(self._cached_schemas)

    async def _async_call_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        """Execute a tool call via SSE transport or fallback to local server."""
        # 1. Try SSE transport if active
        if self._should_use_sse():
            try:
                from mcp.client.session import ClientSession
                from mcp.client.sse import sse_client

                logger.info("[MCP Client] Calling %s via SSE transport", name)
                async with sse_client(self.server_url) as (read_stream, write_stream):
                    async with ClientSession(read_stream, write_stream) as session:
                        await session.initialize()
                        res = await session.call_tool(name, arguments)
                        if res.content:
                            return res.content[0].text
                        return json.dumps({"result": None})
            except Exception as sse_err:
                logger.warning("[MCP Client] SSE execution failed (%s), dispatching via local MCP server.", sse_err)

        # 2. Local MCP Server execution
        from mcp_server.server import mcp as local_server

        logger.info("[MCP Client] Calling %s", name)
        res = await local_server.call_tool(name, arguments)
        if res.is_error:
            logger.warning("[MCP Server] Tool execution error for %s", name)
        if res.content:
            return res.content[0].text
        return json.dumps({"result": None})

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        """
        Synchronously invoke an MCP tool and return serialized response text.

        Args:
            name (str): The tool name (e.g. 'calculator' or 'web_search').
            arguments (Dict[str, Any]): The arguments dictionary.

        Returns:
            str: Output string or serialized JSON from the MCP server.
        """
        try:
            # 1. If SSE transport is active, dispatch over SSE
            if self._should_use_sse():
                return anyio.run(self._async_call_tool, name, arguments)

            # 2. In-process direct execution (lightning-fast, zero event-loop lockups on Windows)
            import inspect
            from mcp_server.server import mcp as local_server

            tool = local_server._tool_manager.get_tool(name)
            if not tool:
                logger.warning("[MCP Client] Tool '%s' not found on local MCP server.", name)
                return json.dumps({"error": f"Tool '{name}' not found on MCP server."})

            logger.info("[MCP Client] In-process invoking tool '%s' with args %s", name, arguments)
            fn = tool.fn
            if inspect.iscoroutinefunction(fn):
                res = asyncio.run(fn(**arguments))
            else:
                res = fn(**arguments)

            if isinstance(res, str):
                return res
            return json.dumps(res, default=str)
        except Exception as err:
            logger.error("[MCP Client] Error calling tool '%s': %s", name, err)
            return json.dumps({"error": f"MCP tool execution failed: {str(err)}"})


# Singleton global MCP client instance
mcp_client = MCPClient()


def mcp_tool_executor(tool_name: str, arguments: Dict[str, Any]) -> str:
    """
    Clean execution layer taking an LLM tool call and forwarding it to the MCP client.

    Flow:
        LLM Tool Call -> MCP Tool Executor -> MCP Client -> MCP Server -> Requested Tool -> Result -> LLM
    """
    return mcp_client.call_tool(tool_name, arguments)
