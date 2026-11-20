"""
Integration tests for FastAPI REST endpoints (/, /health, /chat).
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_endpoint():
    """Test GET / returns 200 OK and expected root status payload."""
    response = client.get("/")
    assert response.status_code == 200
    json_data = response.json()
    assert "message" in json_data
    assert "running" in json_data["message"]


def test_health_endpoint():
    """Test GET /health returns 200 OK and healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data == {"status": "healthy"}


def test_chat_endpoint_via_langgraph():
    """Test POST /chat triggers LangGraph workflow and returns generated answer."""
    payload = {"message": "Explain what FastAPI is in one simple sentence."}
    response = client.post("/chat", json=payload)
    assert response.status_code == 200
    json_data = response.json()
    assert "response" in json_data
    assert len(json_data["response"]) > 0


def test_chat_endpoint_conversational_fast_path():
    """Test POST /chat returns near-instant responses for simple queries like hey and wassup."""
    for greeting in ["hey", "wassup", "hey , wassup"]:
        response = client.post("/chat", json={"message": greeting})
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert len(data["response"]) > 0
        assert data["status"] == "completed"
        assert data["current_agent"] == "supervisor"
        assert data["thread_title"] == "General Chat"

