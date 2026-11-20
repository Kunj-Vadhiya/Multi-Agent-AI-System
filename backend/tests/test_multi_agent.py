"""
Comprehensive unit and integration tests for Version 4 Multi-Agent Architecture.
Verifies the complete pipeline:
User -> Supervisor -> Research Agent -> Tools -> Analysis Agent -> Writer Agent -> Final Response.
"""

from unittest.mock import patch
from fastapi.testclient import TestClient

from app.graph.state import GraphState
from app.graph.workflow import app_graph
from app.main import app

client = TestClient(app)


def test_multi_agent_workflow_mocked_pipeline():
    """
    Test the multi-agent graph state transitions with mocked LLM calls
    to verify deterministic routing and state updates.
    """
    mock_research_output = (
        "### Factual Research Findings\n"
        "1. Modular RAG separates retrieval, generation, and augmentation.\n"
        "2. GraphRAG leverages knowledge graphs for relational reasoning.\n"
        "3. Self-RAG introduces adaptive retrieval and self-reflection."
    )
    mock_analysis_output = (
        "### Comparative Analysis\n"
        "- Modular RAG offers high flexibility but increased pipeline latency.\n"
        "- GraphRAG excels at multi-hop queries, with higher graph construction costs.\n"
        "- Self-RAG minimizes hallucinations, with additional inference overhead."
    )
    mock_writer_output = (
        "# Structured Technical Report: Advanced RAG Architectures\n\n"
        "## 1. Executive Summary\nRetrieval-Augmented Generation has evolved beyond naive retrieval.\n\n"
        "## 2. Factual Findings\nModular RAG, GraphRAG, and Self-RAG represent the state-of-the-art.\n\n"
        "## 3. Comparative Analysis & Trade-offs\nLatency vs precision trade-offs must guide architecture selection.\n\n"
        "## 4. Recommendations\nChoose GraphRAG for complex enterprise domain knowledge."
    )

    with patch(
        "app.services.llm_service.run_agent_with_tools",
        side_effect=[mock_research_output, mock_analysis_output, mock_writer_output],
    ):
        initial_state: GraphState = {
            "user_query": (
                "Research the latest developments in RAG, compare different approaches, "
                "analyze their advantages and limitations, and prepare a structured technical report."
            ),
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

        # Verify state integrity
        assert final_state["plan"] is not None
        assert len(final_state["plan"]) >= 3
        assert final_state["research_data"] == mock_research_output
        assert final_state["analysis_data"] == mock_analysis_output
        assert final_state["final_report"] == mock_writer_output
        assert final_state["response"] == mock_writer_output
        assert final_state["next_agent"] == "FINISH"

        # Verify execution trace in agent_logs
        agents_executed = [log["agent"] for log in final_state.get("agent_logs", [])]
        assert "supervisor" in agents_executed
        assert "research_agent" in agents_executed
        assert "analysis_agent" in agents_executed
        assert "writer_agent" in agents_executed


def test_api_chat_endpoint_multi_agent():
    """
    Test POST /chat returns the multi-agent response and execution metadata.
    """
    mock_research = "Key facts about FastAPI async performance."
    mock_analysis = "FastAPI outperforms Flask due to Starlette and uvloop."
    mock_report = "FastAPI Technical Report: High performance async web framework."

    with patch(
        "app.services.llm_service.run_agent_with_tools",
        side_effect=[mock_research, mock_analysis, mock_report],
    ):
        payload = {"message": "Analyze FastAPI performance and provide a report."}
        response = client.post("/chat", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert data["response"] == mock_report
        assert data["plan"] is not None
        assert data["research_data"] == mock_research
        assert data["analysis_data"] == mock_analysis
        assert len(data["agent_logs"]) > 0


def test_supervisor_loop_prevention():
    """
    Verify supervisor safely terminates when iteration limit is reached.
    """
    from app.agents.supervisor import supervisor_node

    looping_state: GraphState = {
        "user_query": "Test infinite loop",
        "plan": ["Subtask 1"],
        "next_agent": "research_agent",
        "research_data": "Some data",
        "analysis_data": "Some analysis",
        "final_report": "Finished report",
        "iteration_count": 5,
        "agent_logs": [],
        "response": "",
    }

    result = supervisor_node(looping_state)
    assert result["next_agent"] == "FINISH"
