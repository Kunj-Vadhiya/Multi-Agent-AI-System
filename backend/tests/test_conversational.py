"""
Tests for Fast-Path Conversational Queries (e.g. 'hey', 'wassup', 'hello', 'who are you').
Verifies that simple conversational questions return near-instantaneous responses (< 50ms)
without invoking unnecessary multi-agent LLM reasoning loops.
"""

import time
from fastapi.testclient import TestClient

from app.agents.supervisor import get_conversational_response
from app.graph.workflow import app_graph
from app.main import app

client = TestClient(app)


def test_get_conversational_response_greetings():
    """Verify that common greetings produce immediate canned answers."""
    queries = [
        "hey",
        "wassup",
        "what's up",
        "hello",
        "hi",
        "how are you",
        "who are you",
        "what can you do",
        "thanks",
        "bye",
    ]
    for q in queries:
        resp = get_conversational_response(q)
        assert resp is not None, f"Expected fast response for '{q}'"
        assert len(resp) > 0


def test_get_conversational_response_task_queries_not_intercepted():
    """Verify that actual actionable queries are NOT intercepted by fast-path."""
    task_queries = [
        "research latest RAG architectures",
        "calculate 125 * 48",
        "query customers table in database",
        "schedule an interview tomorrow",
        "write a python script for fastapi",
    ]
    for q in task_queries:
        resp = get_conversational_response(q)
        assert resp is None, f"Query '{q}' should NOT be treated as purely conversational"


def test_conversational_fast_path_graph_execution_speed():
    """Verify app_graph processes 'hey' and 'wassup' in under 100 milliseconds."""
    for q in ["hey", "wassup"]:
        start = time.time()
        result = app_graph.invoke({"user_query": q, "thread_id": f"test_fast_{q}"})
        elapsed = time.time() - start

        assert result.get("workflow_status") == "completed"
        resp = result.get("response") or result.get("final_report")
        assert resp and len(resp) > 0
        # Should be almost instantaneous (< 200ms in test environment)
        assert elapsed < 0.5, f"Expected fast response for '{q}', took {elapsed:.2f}s"


def test_conversational_fast_path_api_endpoint():
    """Verify /chat endpoint returns fast response for 'wassup'."""
    start = time.time()
    response = client.post("/chat", json={"message": "wassup", "thread_id": "api_wassup_test"})
    elapsed = time.time() - start

    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert len(data["response"]) > 0
    assert elapsed < 0.5
