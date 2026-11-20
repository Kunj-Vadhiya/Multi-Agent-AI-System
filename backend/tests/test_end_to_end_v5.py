"""
End-to-End Verification Tests for Version 5 (MCP Integration).

Verifies:
- Phase 14: End-to-End Research Workflow ("Research RAG and explain its advantages and limitations.")
- Phase 15: End-to-End Calculator Workflow ("Calculate 125 * 48.")
"""

import pytest

from app.graph.state import GraphState
from app.graph.workflow import app_graph


def test_end_to_end_calculator_workflow():
    """
    Phase 15 Verification:
    User asks to calculate 125 * 48.
    The system should execute:
    Supervisor -> Agent -> LLM requests calculator -> MCP Client -> MCP Server -> calculator -> 6000 -> Final Response
    """
    initial_state: GraphState = {
        "user_query": "Calculate 125 * 48.",
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

    response = final_state.get("response", "")
    assert isinstance(response, str)
    assert len(response.strip()) > 0
    # Verify that the calculation result (6000) is present in the output or research data
    combined_text = (response + " " + str(final_state.get("research_data", ""))).replace(",", "").replace(" ", "").replace("\u202f", "")
    assert "6000" in combined_text
    assert final_state.get("next_agent") == "FINISH"


def test_end_to_end_research_workflow():
    """
    Phase 14 Verification:
    User asks: "Research RAG and explain its advantages and limitations."
    The system should execute:
    Supervisor -> Research Agent -> MCP web_search -> Analysis Agent -> Writer Agent -> Final Report
    """
    initial_state: GraphState = {
        "user_query": "Research RAG and explain its advantages and limitations.",
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

    response = final_state.get("response", "")
    assert isinstance(response, str)
    assert len(response.strip()) > 0

    # Verify RAG concepts are covered
    response_lower = response.lower()
    assert "rag" in response_lower or "retrieval" in response_lower
    assert any(term in response_lower for term in ["advantage", "strength", "benefit"])

    # Verify that research and analysis data was produced
    assert final_state.get("research_data") is not None
    assert final_state.get("analysis_data") is not None
    assert final_state.get("final_report") is not None
    assert final_state.get("next_agent") == "FINISH"
