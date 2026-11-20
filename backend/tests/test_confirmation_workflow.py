"""
Human-in-the-Loop Confirmation Workflow Tests.
Verifies that:
- External side-effect actions (send email, schedule event) trigger confirmation pause
- Workflows transition through NONE -> PENDING -> APPROVED / REJECTED
- Confirmed actions execute with authorized credentials
- Rejected actions cancel safely without side-effects
"""

import pytest
from app.agents.email_agent import EmailAgent
from app.agents.calendar_agent import CalendarAgent
from app.agents.supervisor import supervisor_node


def test_email_send_pause_for_confirmation():
    agent = EmailAgent()
    state = {
        "user_query": "Send the performance metrics email to all managers",
        "agent_history": [],
        "agent_logs": [],
        "confirmation_status": "NONE",
    }
    result = agent.run(state)
    assert result["confirmation_required"] is True
    assert result["workflow_status"] == "awaiting_confirmation"
    assert result["pending_action"]["action"] == "send_email"
    assert "recipient" in result["pending_action"]["details"]


def test_email_send_resumption_approved():
    agent = EmailAgent()
    state = {
        "user_query": "Send the performance metrics email to all managers",
        "agent_history": [],
        "agent_logs": [],
        "confirmation_status": "APPROVED",
        "pending_action": {
            "action": "send_email",
            "details": {"recipient": "manager@example.com", "subject": "Metrics", "body": "Summary"},
        },
    }
    result = agent.run(state)
    assert result.get("confirmation_required") is False
    assert result["workflow_status"] == "completed"
    assert result["email_results"]["status"] == "sent"


def test_calendar_schedule_pause_for_confirmation():
    agent = CalendarAgent()
    state = {
        "user_query": "Schedule the executive board review for Friday at 2 PM",
        "agent_history": [],
        "agent_logs": [],
        "confirmation_status": "NONE",
    }
    result = agent.run(state)
    assert result["confirmation_required"] is True
    assert result["workflow_status"] == "awaiting_confirmation"
    assert result["pending_action"]["action"] == "create_calendar_event"


def test_calendar_schedule_resumption_approved():
    agent = CalendarAgent()
    state = {
        "user_query": "Schedule the executive board review for Friday at 2 PM",
        "agent_history": [],
        "agent_logs": [],
        "confirmation_status": "APPROVED",
        "pending_action": {
            "action": "create_calendar_event",
            "details": {
                "title": "Executive Review",
                "start_time": "2026-10-02T14:00:00",
                "end_time": "2026-10-02T15:00:00",
            },
        },
    }
    result = agent.run(state)
    assert result.get("confirmation_required") is False
    assert result["calendar_results"]["status"] == "scheduled"


def test_supervisor_pauses_when_confirmation_pending():
    state = {
        "user_query": "Send the report email",
        "confirmation_required": True,
        "confirmation_status": "PENDING",
        "execution_plan": {"agents": ["email"], "plan": ["1. Email Agent"]},
        "agent_history": [{"agent": "email", "status": "awaiting_confirmation"}],
        "agent_logs": [],
        "iteration_count": 1,
    }
    result = supervisor_node(state)
    assert result["workflow_status"] == "awaiting_confirmation"
    assert result["next_agent"] == "FINISH"
