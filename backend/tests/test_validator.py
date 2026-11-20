"""
Tests for Validator Agent, Structured Output, and Retry Protection (Version 6).

Verifies:
- Test 5: Validator PASS routes directly to END.
- Test 6: Validator FAIL triggers Writer revision loop with feedback.
- Test 7: Maximum Retries prevents infinite loops and terminates gracefully.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.agents.validator import validator_agent_node
from app.config import settings
from app.graph.state import GraphState
from app.graph.workflow import create_workflow, route_validator


def test_validator_node_pass_verdict():
    """
    Test 5a: Validator node returns PASS and structured verdict on high quality draft.
    """
    state: GraphState = {
        "user_query": "What is linear regression?",
        "research_data": "Linear regression models the relationship between scalar response and explanatory variables.",
        "analysis_data": "Advantages include interpretability; limitations include sensitivity to outliers.",
        "final_report": "Executive Summary: Linear regression is a supervised learning algorithm...",
        "retry_count": 0,
        "agent_logs": [],
    }

    mock_llm_json = {
        "status": "PASS",
        "issues": [],
        "feedback": "",
    }

    with patch("app.services.llm_service.run_structured_json", return_value=mock_llm_json):
        result = validator_agent_node(state)

        assert result["validation_result"]["status"] == "PASS"
        assert result["validation_result"]["issues"] == []
        assert result["current_agent"] in ("validator", "validator_agent")


def test_validator_node_fail_verdict():
    """
    Test 6a: Validator node returns FAIL, identifies issues, and provides actionable feedback.
    """
    state: GraphState = {
        "user_query": "Compare PyTorch and TensorFlow for production deployment.",
        "research_data": "PyTorch has TorchScript; TensorFlow has TF Serving.",
        "analysis_data": "Both support serving, but TF Serving has mature C++ backend.",
        "final_report": "PyTorch is great for research.",  # Incomplete, omitted TensorFlow and comparison
        "retry_count": 0,
        "agent_logs": [],
    }

    mock_llm_json = {
        "status": "FAIL",
        "issues": ["TensorFlow production comparison is missing", "No mention of TF Serving"],
        "feedback": "Include a comparative breakdown of TensorFlow Serving and TorchScript.",
    }

    with patch("app.services.llm_service.run_structured_json", return_value=mock_llm_json):
        result = validator_agent_node(state)

        assert result["validation_result"]["status"] == "FAIL"
        assert len(result["validation_result"]["issues"]) == 2
        assert "TensorFlow" in result["validation_feedback"]
        assert result["retry_count"] == 1
        assert result["workflow_status"] == "in_progress"


def test_route_validator_pass_routes_to_finish():
    """
    Test 5b: route_validator routes to FINISH when verdict is PASS.
    """
    state: GraphState = {
        "validation_result": {"status": "PASS", "issues": [], "feedback": ""},
        "retry_count": 0,
    }
    decision = route_validator(state)
    assert decision == "FINISH"


def test_route_validator_fail_routes_to_writer():
    """
    Test 6b: route_validator routes to writer_agent when verdict is FAIL and retries remain.
    """
    state: GraphState = {
        "validation_result": {"status": "FAIL", "issues": ["Missing details"], "feedback": "Add details"},
        "retry_count": 1,
    }
    decision = route_validator(state)
    assert decision == "writer_agent"


def test_route_validator_max_retries_protection():
    """
    Test 7: When retry_count exceeds MAX_RETRIES, route_validator terminates to FINISH to avoid infinite loop.
    """
    max_retries = settings.MAX_RETRIES  # default 2

    # Exceeding retry count
    state: GraphState = {
        "validation_result": {"status": "FAIL", "issues": ["Still imperfect"], "feedback": "Fix"},
        "retry_count": max_retries + 1,
    }
    decision = route_validator(state)
    assert decision == "FINISH"


def test_workflow_validation_retry_and_recovery_loop():
    """
    Integration test: Graph executes Writer -> Validator (FAIL) -> Writer (revises with feedback) -> Validator (PASS) -> END.
    """
    import sqlite3
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    from langgraph.checkpoint.sqlite import SqliteSaver
    saver = SqliteSaver(conn)
    saver.setup()

    writer_call_count = 0
    validator_call_count = 0

    def mock_writer(state):
        nonlocal writer_call_count
        writer_call_count += 1
        feedback = state.get("validation_feedback") or ""
        return {
            "draft": f"Report draft revision {writer_call_count} (Feedback addressed: {bool(feedback)})",
            "final_report": f"Report draft revision {writer_call_count}",
            "response": f"Report draft revision {writer_call_count}",
            "agent_logs": [],
        }

    def mock_validator(state):
        nonlocal validator_call_count
        validator_call_count += 1
        retry_count = state.get("retry_count", 0)

        # First call fails; second call passes
        if validator_call_count == 1:
            return {
                "validation_result": {"status": "FAIL", "issues": ["Draft lacks detail"], "feedback": "Add more technical detail."},
                "validation_feedback": "Add more technical detail.",
                "retry_count": retry_count + 1,
                "workflow_status": "in_progress",
                "agent_logs": [],
            }
        else:
            return {
                "validation_result": {"status": "PASS", "issues": [], "feedback": ""},
                "validation_feedback": "",
                "retry_count": retry_count,
                "workflow_status": "completed",
                "agent_logs": [],
            }

    with patch("app.graph.workflow.research_agent_node", return_value={"research_data": "Facts"}), \
         patch("app.graph.workflow.analysis_agent_node", return_value={"analysis_data": "Analysis"}), \
         patch("app.graph.workflow.writer_agent_node", side_effect=mock_writer), \
         patch("app.graph.workflow.validator_agent_node", side_effect=mock_validator):

        graph = create_workflow(checkpointer=saver)

        initial_state: GraphState = {
            "thread_id": "test_retry_thread",
            "user_query": "Test query for validation recovery",
            "execution_plan": {"agents": ["writer"], "plan": ["1. Writer"]},
            "agent_history": [],
            "response": "",
        }

        final_state = graph.invoke(initial_state, config={"configurable": {"thread_id": "test_retry_thread"}})

        # Verify writer ran twice (initial + revision)
        assert writer_call_count == 2
        # Verify validator ran twice (fail + pass)
        assert validator_call_count == 2
        assert final_state["workflow_status"] == "completed"
        assert "revision 2" in final_state["response"]
