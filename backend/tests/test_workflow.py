"""
Independent unit test for the LangGraph workflow.
Verifies that graph.invoke() accepts an initial state and returns an updated state with a response.
"""

from app.graph.state import GraphState
from app.graph.workflow import app_graph


def test_langgraph_workflow_execution():
    """
    Test that the compiled LangGraph workflow processes user_query state
    and returns a state dictionary populated with a non-empty response.
    """
    initial_state: GraphState = {
        "user_query": "What is machine learning?",
        "response": "",
    }

    final_state = app_graph.invoke(initial_state)

    assert "user_query" in final_state
    assert final_state["user_query"] == "What is machine learning?"
    assert "response" in final_state
    assert isinstance(final_state["response"], str)
    assert len(final_state["response"].strip()) > 0


def test_langgraph_workflow_mcp_failure_handling():
    """
    Test that LangGraph workflow does not crash if an MCP tool call encounters an error,
    and returns a graceful degradation response.
    """
    from unittest.mock import patch
    from app.services.mcp_client import mcp_client

    with patch.object(mcp_client, "call_tool", return_value='{"error": "MCP tool temporarily unavailable"}'):
        initial_state: GraphState = {
            "user_query": "What is 99 * 99?",
            "plan": None,
            "next_agent": None,
            "research_data": None,
            "analysis_data": None,
            "final_report": None,
            "iteration_count": 0,
            "agent_logs": [],
            "response": "",
        }
        final_state = app_graph.invoke(initial_state)

        assert "response" in final_state
        assert isinstance(final_state["response"], str)
        assert len(final_state["response"].strip()) > 0
        assert final_state.get("next_agent") in ("FINISH", "writer", None) or final_state.get("workflow_status") == "completed"

