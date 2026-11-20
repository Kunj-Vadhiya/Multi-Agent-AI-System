"""
Tests for Persistent Memory, Checkpointing, and Thread Conversations (Version 6).

Verifies:
- Test 1: New Thread creates fresh isolated state.
- Test 2: Existing Thread loads previous state and conversation history.
- Test 3: Separate Threads maintain strict isolation.
- Test 4: Checkpoint persistence survives restart (reconnection to SQLite file).
"""

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.graph.state import GraphState
from app.graph.workflow import create_workflow
from app.main import app
from app.services.checkpoint_service import get_checkpointer, reset_checkpointer


@pytest.fixture
def client():
    return TestClient(app)


def _make_mock_specialist(agent_name: str, payload_key: str, payload_value: str):
    def _mock(state):
        history = list(state.get("agent_history") or [])
        history.append({"agent": agent_name, "status": "completed"})
        return {payload_key: payload_value, "agent_history": history}
    return _mock


def test_new_thread_initialization():
    """
    Test 1: Verify a new thread_id creates a distinct workflow state.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test_checkpoints.db")
        conn = sqlite3.connect(db_path, check_same_thread=False)
        from langgraph.checkpoint.sqlite import SqliteSaver
        saver = SqliteSaver(conn)
        saver.setup()

        mock_res = _make_mock_specialist("research", "research_data", "RAG facts")
        mock_ana = _make_mock_specialist("analysis", "analysis_data", "RAG analysis")

        with patch("app.graph.workflow.research_agent_node", side_effect=mock_res), \
             patch("app.graph.workflow.analysis_agent_node", side_effect=mock_ana), \
             patch("app.graph.workflow.writer_agent_node", return_value={"final_report": "RAG Report", "response": "RAG Report"}), \
             patch("app.graph.workflow.validator_agent_node", return_value={"validation_result": {"status": "PASS", "issues": [], "feedback": ""}}):

            graph = create_workflow(checkpointer=saver)

            thread_a = "thread_alpha_001"
            input_state: GraphState = {
                "thread_id": thread_a,
                "user_query": "Explain RAG architecture",
                "execution_plan": {"agents": ["research", "analysis", "writer"], "plan": ["1. Research", "2. Analysis", "3. Writer"]},
                "agent_history": [],
                "messages": [{"role": "user", "content": "Explain RAG architecture"}],
                "iteration_count": 0,
                "retry_count": 0,
                "agent_logs": [],
                "response": "",
            }

            final_state = graph.invoke(input_state, config={"configurable": {"thread_id": thread_a}})

            assert final_state["response"] == "RAG Report"
            assert final_state.get("validation_result", {}).get("status") == "PASS"

            # Verify checkpoint is recorded
            saved_state = graph.get_state({"configurable": {"thread_id": thread_a}})
            assert saved_state is not None
            assert saved_state.values.get("research_data") == "RAG facts"

        conn.close()


def test_existing_thread_continuation():
    """
    Test 2: Verify continuation on the same thread retains conversation state.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test_checkpoints.db")
        conn = sqlite3.connect(db_path, check_same_thread=False)
        from langgraph.checkpoint.sqlite import SqliteSaver
        saver = SqliteSaver(conn)
        saver.setup()

        thread_id = "thread_continuation_002"

        mock_res1 = _make_mock_specialist("research", "research_data", "Transformer concepts")
        mock_ana1 = _make_mock_specialist("analysis", "analysis_data", "Transformer analysis")

        # Turn 1
        with patch("app.graph.workflow.research_agent_node", side_effect=mock_res1), \
             patch("app.graph.workflow.analysis_agent_node", side_effect=mock_ana1), \
             patch("app.graph.workflow.writer_agent_node", return_value={"final_report": "Transformers Report", "response": "Transformers Report"}), \
             patch("app.graph.workflow.validator_agent_node", return_value={"validation_result": {"status": "PASS", "issues": [], "feedback": ""}}):

            graph = create_workflow(checkpointer=saver)

            turn1_state: GraphState = {
                "thread_id": thread_id,
                "user_query": "Explain Transformers",
                "execution_plan": {"agents": ["research", "analysis", "writer"], "plan": ["1. Research", "2. Analysis", "3. Writer"]},
                "agent_history": [],
                "messages": [{"role": "user", "content": "Explain Transformers"}],
                "response": "",
            }
            graph.invoke(turn1_state, config={"configurable": {"thread_id": thread_id}})

        # Verify state from Turn 1 is in checkpointer
        snapshot_after_t1 = graph.get_state({"configurable": {"thread_id": thread_id}})
        assert snapshot_after_t1 is not None
        assert snapshot_after_t1.values.get("research_data") == "Transformer concepts"

        # Turn 2
        mock_res2 = _make_mock_specialist("research", "research_data", "RNN comparison")
        mock_ana2 = _make_mock_specialist("analysis", "analysis_data", "Comparison analysis")

        with patch("app.graph.workflow.research_agent_node", side_effect=mock_res2), \
             patch("app.graph.workflow.analysis_agent_node", side_effect=mock_ana2), \
             patch("app.graph.workflow.writer_agent_node", return_value={"final_report": "Comparison Report", "response": "Comparison Report"}), \
             patch("app.graph.workflow.validator_agent_node", return_value={"validation_result": {"status": "PASS", "issues": [], "feedback": ""}}):

            graph2 = create_workflow(checkpointer=saver)
            prior_messages = snapshot_after_t1.values.get("messages", [])
            turn2_messages = list(prior_messages) + [{"role": "user", "content": "Now compare with RNNs"}]

            turn2_state: GraphState = {
                "thread_id": thread_id,
                "user_query": "Now compare with RNNs",
                "execution_plan": {"agents": ["research", "analysis", "writer"], "plan": ["1. Research", "2. Analysis", "3. Writer"]},
                "agent_history": [],
                "messages": turn2_messages,
                "plan": None,
                "research_data": None,
                "analysis_data": None,
                "final_report": None,
                "response": "",
            }
            final_turn2 = graph2.invoke(turn2_state, config={"configurable": {"thread_id": thread_id}})
            assert final_turn2["response"] == "Comparison Report"
            assert len(final_turn2["messages"]) >= 2

        conn.close()


def test_thread_isolation():
    """
    Test 3: Thread A and Thread B maintain separate state and do not cross-contaminate.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test_checkpoints.db")
        conn = sqlite3.connect(db_path, check_same_thread=False)
        from langgraph.checkpoint.sqlite import SqliteSaver
        saver = SqliteSaver(conn)
        saver.setup()

        thread_a = "thread_isolation_A"
        thread_b = "thread_isolation_B"

        mock_res_a = _make_mock_specialist("research", "research_data", "Data A")
        mock_ana_a = _make_mock_specialist("analysis", "analysis_data", "Analysis A")

        # Thread A: Research Transformers
        with patch("app.graph.workflow.research_agent_node", side_effect=mock_res_a), \
             patch("app.graph.workflow.analysis_agent_node", side_effect=mock_ana_a), \
             patch("app.graph.workflow.writer_agent_node", return_value={"final_report": "Report A", "response": "Report A"}), \
             patch("app.graph.workflow.validator_agent_node", return_value={"validation_result": {"status": "PASS", "issues": [], "feedback": ""}}):

            graph = create_workflow(checkpointer=saver)
            graph.invoke(
                {"thread_id": thread_a, "user_query": "Query A", "execution_plan": {"agents": ["research", "analysis", "writer"], "plan": ["1. Research", "2. Analysis", "3. Writer"]}, "agent_history": [], "response": ""},
                config={"configurable": {"thread_id": thread_a}},
            )

        mock_res_b = _make_mock_specialist("research", "research_data", "Data B")
        mock_ana_b = _make_mock_specialist("analysis", "analysis_data", "Analysis B")

        # Thread B: Research Quantum Computing
        with patch("app.graph.workflow.research_agent_node", side_effect=mock_res_b), \
             patch("app.graph.workflow.analysis_agent_node", side_effect=mock_ana_b), \
             patch("app.graph.workflow.writer_agent_node", return_value={"final_report": "Report B", "response": "Report B"}), \
             patch("app.graph.workflow.validator_agent_node", return_value={"validation_result": {"status": "PASS", "issues": [], "feedback": ""}}):

            graph = create_workflow(checkpointer=saver)
            graph.invoke(
                {"thread_id": thread_b, "user_query": "Query B", "execution_plan": {"agents": ["research", "analysis", "writer"], "plan": ["1. Research", "2. Analysis", "3. Writer"]}, "agent_history": [], "response": ""},
                config={"configurable": {"thread_id": thread_b}},
            )

        # Retrieve isolated snapshots
        snapshot_a = graph.get_state({"configurable": {"thread_id": thread_a}})
        snapshot_b = graph.get_state({"configurable": {"thread_id": thread_b}})

        assert snapshot_a.values.get("research_data") == "Data A"
        assert snapshot_b.values.get("research_data") == "Data B"
        assert snapshot_a.values.get("final_report") == "Report A"
        assert snapshot_b.values.get("final_report") == "Report B"

        conn.close()


def test_checkpoint_persistence_across_restarts():
    """
    Test 4: State must survive application shutdown and restart.
    Simulated by closing the connection and opening a new connection to the same SQLite file.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "persistent_restart.db")
        thread_id = "restart_thread_101"

        # Session 1: Run workflow and shut down
        conn1 = sqlite3.connect(db_path, check_same_thread=False)
        from langgraph.checkpoint.sqlite import SqliteSaver
        saver1 = SqliteSaver(conn1)
        saver1.setup()

        mock_res = _make_mock_specialist("research", "research_data", "Pre-restart facts")
        mock_ana = _make_mock_specialist("analysis", "analysis_data", "Pre-restart analysis")

        with patch("app.graph.workflow.research_agent_node", side_effect=mock_res), \
             patch("app.graph.workflow.analysis_agent_node", side_effect=mock_ana), \
             patch("app.graph.workflow.writer_agent_node", return_value={"final_report": "Pre-restart Report", "response": "Pre-restart Report"}), \
             patch("app.graph.workflow.validator_agent_node", return_value={"validation_result": {"status": "PASS", "issues": [], "feedback": ""}}):

            graph1 = create_workflow(checkpointer=saver1)
            graph1.invoke(
                {"thread_id": thread_id, "user_query": "Initial question", "execution_plan": {"agents": ["research", "analysis", "writer"], "plan": ["1. Research", "2. Analysis", "3. Writer"]}, "agent_history": [], "response": ""},
                config={"configurable": {"thread_id": thread_id}},
            )

        # Simulate shutdown
        conn1.close()

        # Session 2: Start new application instance pointing to same DB file
        conn2 = sqlite3.connect(db_path, check_same_thread=False)
        saver2 = SqliteSaver(conn2)
        saver2.setup()
        graph2 = create_workflow(checkpointer=saver2)

        recovered_snapshot = graph2.get_state({"configurable": {"thread_id": thread_id}})
        assert recovered_snapshot is not None
        assert recovered_snapshot.values.get("research_data") == "Pre-restart facts"

        conn2.close()
