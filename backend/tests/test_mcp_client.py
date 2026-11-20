"""
Comprehensive tests for the MCP Client abstraction (Version 5).

Covers:
- MCP Client connection and disconnection
- Dynamic tool discovery (list_tools)
- Tool invocation (calculator and web_search)
- Graceful error handling for unknown tools, invalid arguments, and calculation errors
- Fallback resilience when external endpoints are unreachable
"""

import json
from unittest.mock import patch

import pytest

from app.services.mcp_client import MCPClient, mcp_client, mcp_tool_executor


def test_mcp_client_connect_and_discover():
    """Verify that MCP client can connect and discover registered tools."""
    client = MCPClient()
    connected = client.connect()
    assert connected is True
    assert client.is_connected() is True

    tools = client.list_tools()
    assert isinstance(tools, list)
    assert len(tools) >= 2

    tool_names = [t.get("function", {}).get("name") for t in tools]
    assert "calculator" in tool_names
    assert "web_search" in tool_names


def test_mcp_client_call_calculator():
    """Verify invoking calculator tool via MCP client."""
    client = MCPClient()
    response_str = client.call_tool("calculator", {"expression": "125 * 48"})
    assert isinstance(response_str, str)
    data = json.loads(response_str)
    assert data.get("result") == 6000


def test_mcp_client_call_calculator_invalid_syntax():
    """Verify that calculator syntax errors are caught and returned gracefully."""
    client = MCPClient()
    response_str = client.call_tool("calculator", {"expression": "100 / 0"})
    data = json.loads(response_str)
    assert "error" in data


def test_mcp_client_call_calculator_empty():
    """Verify that empty calculator input returns a controlled error."""
    client = MCPClient()
    response_str = client.call_tool("calculator", {"expression": ""})
    data = json.loads(response_str)
    assert "error" in data


def test_mcp_client_call_web_search():
    """Verify invoking web_search tool via MCP client."""
    client = MCPClient()
    with patch("mcp_server.server.search_web") as mock_search:
        mock_search.return_value = {
            "query": "retrieval augmented generation",
            "results": [
                {
                    "title": "RAG Guide",
                    "url": "https://example.com/rag",
                    "snippet": "Retrieval Augmented Generation combines LLMs with external knowledge.",
                }
            ],
        }
        response_str = client.call_tool("web_search", {"query": "retrieval augmented generation"})
        data = json.loads(response_str)
        assert data.get("query") == "retrieval augmented generation"
        assert len(data.get("results", [])) == 1
        assert data["results"][0]["title"] == "RAG Guide"


def test_mcp_client_call_unknown_tool():
    """Verify that requesting an unknown tool does not crash and returns controlled error."""
    client = MCPClient()
    response_str = client.call_tool("nonexistent_random_tool", {})
    assert isinstance(response_str, str)
    # FastMCP/MCPServer returns error content or exception caught as error
    assert "error" in response_str.lower() or "not found" in response_str.lower()


def test_mcp_client_disconnect():
    """Verify client disconnect resets state."""
    client = MCPClient()
    client.connect()
    assert client.is_connected() is True
    client.disconnect()
    assert client.is_connected() is False


def test_mcp_tool_executor():
    """Verify the MCP tool execution layer correctly formats and routes requests."""
    res_str = mcp_tool_executor("calculator", {"expression": "50 + 25"})
    data = json.loads(res_str)
    assert data.get("result") == 75


def test_mcp_client_connection_failure():
    """Verify that when an external MCP SSE endpoint fails, client falls back gracefully."""
    client = MCPClient(server_url="http://127.0.0.1:9999/sse", transport="auto")
    # Even if remote port 9999 is closed, auto transport safely queries local server instance
    connected = client.connect()
    assert connected is True
    tools = client.list_tools()
    assert len(tools) >= 2

