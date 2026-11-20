"""
Unit and integration tests for LLM tool calling (Version 3).
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from app.services.llm_service import execute_tool, run_agent_with_tools
from app.tools import CALCULATOR_TOOL_DEFINITION


def test_execute_tool_calculator():
    res = execute_tool("calculator", {"expression": "125 * 48"})
    parsed = json.loads(res)
    assert parsed.get("result") == 6000


def test_execute_tool_unknown():
    res = execute_tool("unknown_tool", {})
    parsed = json.loads(res)
    assert "error" in parsed


def test_execute_tool_web_search():
    mock_provider = MagicMock()
    mock_provider.search.return_value = [{"title": "T", "url": "U", "snippet": "S"}]

    with patch("app.tools.web_search.get_search_provider", return_value=mock_provider):
        res = execute_tool("web_search", {"query": "python fastapi"})
        parsed = json.loads(res)
        assert parsed["query"] == "python fastapi"
        assert len(parsed["results"]) == 1


def test_run_agent_with_tools_mocked():
    """Verify tool calling flow: LLM issues tool_call -> tool executed -> final response."""
    mock_tool_call = MagicMock()
    mock_tool_call.id = "call_test_123"
    mock_tool_call.function.name = "calculator"
    mock_tool_call.function.arguments = json.dumps({"expression": "15% of 50000"})

    mock_msg_with_call = MagicMock()
    mock_msg_with_call.tool_calls = [mock_tool_call]
    mock_msg_with_call.content = None

    mock_msg_final = MagicMock()
    mock_msg_final.tool_calls = None
    mock_msg_final.content = "15% of 50,000 is 7,500."

    mock_choice1 = MagicMock()
    mock_choice1.message = mock_msg_with_call

    mock_choice2 = MagicMock()
    mock_choice2.message = mock_msg_final

    with patch(
        "app.services.llm_service.create_completion_with_rotation",
        side_effect=[
            MagicMock(choices=[mock_choice1]),
            MagicMock(choices=[mock_choice2]),
        ],
    ) as mock_create:
        output = run_agent_with_tools(
            system_prompt="Test agent",
            user_prompt="Calculate 15% of 50000",
            tools=[CALCULATOR_TOOL_DEFINITION],
        )
        assert "7,500" in output
        assert mock_create.call_count == 2
