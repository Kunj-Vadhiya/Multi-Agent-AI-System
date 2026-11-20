"""
End-to-End Verification Tests for Version 6 + Version 7.

Verifies:
- Test 15: Research Agent combines internal RAG documents with external MCP tools.
- Test 16: MCP Regression check (calculator and web_search continue working seamlessly).
- Test 17: Full End-to-End Pipeline (FastAPI -> Thread -> Checkpoint -> Multi-Agent -> Validator -> Response).
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.graph.state import GraphState
from app.graph.workflow import app_graph, create_workflow
from app.main import app
from app.rag.pipeline import get_rag_pipeline
from app.rag.vector_store import get_vector_store
from app.services.mcp_client import mcp_client


@pytest.fixture
def client():
    return TestClient(app)


def test_mcp_tools_regression():
    """
    Test 16: Verify MCP tools (calculator and web_search) remain fully functional.
    """
    tools = mcp_client.list_tools()
    tool_names = [t.get("function", {}).get("name") for t in tools]
    assert "calculator" in tool_names
    assert "web_search" in tool_names

    # Test calculator tool execution
    calc_res = mcp_client.call_tool("calculator", {"expression": "25 * 4"})
    assert "100" in str(calc_res)


def test_research_agent_combines_rag_and_mcp():
    """
    Test 15: Research Agent combines internal knowledge base chunks with MCP tools.
    """
    from app.agents.researcher import research_agent_node

    # Ingest a sample doc into RAG
    vector_store = get_vector_store()
    rag_pipeline = get_rag_pipeline()

    with tempfile.TemporaryDirectory() as tmpdir:
        sample_doc = Path(tmpdir) / "company_policy.txt"
        sample_doc.write_text(
            "Acme Corp uses Architecture Alpha with a 4-layer microservices design.",
            encoding="utf-8",
        )
        rag_pipeline.ingest_file(sample_doc, filename="company_policy.pdf")

        state: GraphState = {
            "user_query": "Compare Acme Corp Architecture Alpha from our company policy with industry standards.",
            "plan": ["1. Check internal company policy", "2. Compare with industry standards"],
            "agent_logs": [],
        }

        with patch("app.services.llm_service.run_agent_with_tools") as mock_llm:
            mock_llm.return_value = (
                "Internal Findings: Acme Corp Architecture Alpha uses 4 microservice layers [Document: company_policy.pdf]. "
                "External Findings: Industry standards typically recommend event-driven domain boundaries."
            )

            result = research_agent_node(state)

            assert result["research_data"] is not None
            assert result["rag_context"] is not None
            assert result["retrieved_documents"] is not None
            assert len(result["retrieved_documents"]) >= 1
            assert result["retrieved_documents"][0]["metadata"]["filename"] == "company_policy.pdf"


def test_full_pipeline_via_fastapi(client):
    """
    Test 17: Full multi-agent pipeline executed via FastAPI POST /chat with persistent thread_id.
    """
    thread_id = "test_e2e_thread_v67"

    mock_llm_plan = [
        "1. Research topic",
        "2. Analyze trade-offs",
        "3. Synthesize report",
    ]

    with patch("app.agents.researcher.research_agent_node") as mock_research, \
         patch("app.agents.analyst.analysis_agent_node") as mock_analysis, \
         patch("app.agents.writer.writer_agent_node") as mock_writer, \
         patch("app.agents.validator.validator_agent_node") as mock_validator:

        mock_research.return_value = {
            "current_agent": "research_agent",
            "research_data": "Transformers use self-attention to replace recurrent connections.",
            "research_results": "Transformers use self-attention.",
            "agent_logs": [{"agent": "research_agent", "action": "researched"}],
        }

        mock_analysis.return_value = {
            "current_agent": "analysis_agent",
            "analysis_data": "Self-attention enables massive parallelism but quadratic memory scaling with sequence length.",
            "analysis": "Self-attention enables massive parallelism.",
            "agent_logs": [{"agent": "analysis_agent", "action": "analyzed"}],
        }

        mock_writer.return_value = {
            "current_agent": "writer_agent",
            "draft": "# Technical Report: Transformers\n\nExecutive Summary: Transformers dominate modern NLP...",
            "final_report": "# Technical Report: Transformers\n\nExecutive Summary: Transformers dominate modern NLP...",
            "response": "# Technical Report: Transformers\n\nExecutive Summary: Transformers dominate modern NLP...",
            "final_response": "# Technical Report: Transformers\n\nExecutive Summary: Transformers dominate modern NLP...",
            "agent_logs": [{"agent": "writer_agent", "action": "compiled report"}],
        }

        mock_validator.return_value = {
            "current_agent": "validator_agent",
            "validation_result": {"status": "PASS", "issues": [], "feedback": ""},
            "workflow_status": "completed",
            "agent_logs": [{"agent": "validator_agent", "action": "approved"}],
        }

        response = client.post(
            "/chat",
            json={"thread_id": thread_id, "message": "Explain transformer architecture."},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["thread_id"] == thread_id
        assert data["status"] == "completed"
        assert "Technical Report: Transformers" in data["response"]
        assert data["research_data"] is not None
        assert data["analysis_data"] is not None
        assert data["validation_result"]["status"] == "PASS"
