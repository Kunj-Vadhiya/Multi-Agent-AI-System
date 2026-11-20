"""
Independent tests for the MCP Server (Phase 6).
Verifies tool discovery, invocation, and error handling without LangGraph.
"""

import json
from unittest.mock import patch
import pytest

from mcp_server.server import mcp, mcp_calculator, mcp_web_search


@pytest.mark.anyio
async def test_mcp_server_tool_discovery():
    """Verify calculator and web_search are registered and discoverable on the MCP server."""
    tools = await mcp.list_tools()
    tool_names = [tool.name for tool in tools]

    assert "calculator" in tool_names
    assert "web_search" in tool_names

    calc_tool = next(t for t in tools if t.name == "calculator")
    calc_schema = getattr(calc_tool, "input_schema", None) or getattr(calc_tool, "inputSchema", {})
    assert "expression" in calc_schema.get("properties", {})

    search_tool = next(t for t in tools if t.name == "web_search")
    search_schema = getattr(search_tool, "input_schema", None) or getattr(search_tool, "inputSchema", {})
    assert "query" in search_schema.get("properties", {})


@pytest.mark.anyio
async def test_mcp_server_call_calculator():
    """Verify invoking calculator tool via MCP server produces expected output."""
    res = await mcp.call_tool("calculator", {"expression": "125 * 48"})
    assert not res.is_error
    assert len(res.content) > 0
    text_payload = res.content[0].text
    data = json.loads(text_payload)
    assert data["result"] == 6000


@pytest.mark.anyio
async def test_mcp_server_call_calculator_invalid():
    """Verify invalid mathematical syntax produces controlled error without crashing."""
    res = await mcp.call_tool("calculator", {"expression": "100 / 0"})
    text_payload = res.content[0].text
    data = json.loads(text_payload)
    assert "error" in data
    assert "Division by zero" in data["error"]


@pytest.mark.anyio
async def test_mcp_server_call_web_search():
    """Verify invoking web_search tool via MCP server returns structured results."""
    mock_results = [
        {"title": "RAG Overview", "url": "https://example.com/rag", "snippet": "RAG couples retrieval with generation."}
    ]
    with patch("mcp_server.server.search_web", return_value={"query": "RAG", "results": mock_results}):
        res = await mcp.call_tool("web_search", {"query": "RAG", "max_results": 2})
        assert not res.is_error
        text_payload = res.content[0].text
        data = json.loads(text_payload)
        assert data["query"] == "RAG"
        assert len(data["results"]) == 1
        assert data["results"][0]["title"] == "RAG Overview"


def test_mcp_direct_calculator_function():
    """Verify direct Python function execution of mcp_calculator."""
    assert mcp_calculator("15% of 50000") == {"result": 7500}
    assert mcp_calculator("(25 * 4) + 100") == {"result": 200}
    err = mcp_calculator("")
    assert "error" in err


def test_mcp_direct_web_search_function():
    """Verify direct Python function execution of mcp_web_search."""
    with patch("mcp_server.server.search_web", return_value={"query": "test", "results": []}):
        res = mcp_web_search("test")
        assert res["query"] == "test"
        assert res["results"] == []
