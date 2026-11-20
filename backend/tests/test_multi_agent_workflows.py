"""
Multi-Agent Dynamic Workflow Tests.
Verifies that the Supervisor dynamically plans intents, agents, dependencies,
and confirmation flags without static hardcoded pipelines.

Scenarios tested:
1. "Research RAG and create a technical report." -> [research, analysis, document]
2. "Analyze this database and explain the top customers." -> [database, analysis, writer]
3. "Create a Python FastAPI endpoint that queries PostgreSQL." -> [coding, database, coding]
4. "Check tomorrow's meetings and draft an email summary." -> [calendar, analysis, email] (no send confirmation)
5. "Check tomorrow's meetings and email me the summary." -> [calendar, analysis, email] (requires confirmation)
6. "Find emails about my interview and schedule the interview date." -> [email, analysis, calendar] (requires confirmation)
"""

import pytest
from app.agents.supervisor import plan_dynamic_workflow


def test_workflow_plan_research_and_document():
    plan = plan_dynamic_workflow("Research RAG and create a technical report.")
    assert plan["intent"] == "research_and_document"
    assert plan["agents"] == ["research", "analysis", "document"]
    assert "analysis" in plan["dependencies"]
    assert "document" in plan["dependencies"]
    assert plan["requires_confirmation"] is False


def test_workflow_plan_database_analysis():
    plan = plan_dynamic_workflow("Analyze this database and explain the top customers.")
    assert plan["intent"] == "database_analysis"
    assert "database" in plan["agents"]
    assert "analysis" in plan["agents"]
    assert plan["requires_confirmation"] is False


def test_workflow_plan_code_and_database():
    plan = plan_dynamic_workflow("Create a Python FastAPI endpoint that queries PostgreSQL.")
    assert plan["intent"] == "code_and_database"
    assert plan["agents"] == ["coding", "database", "coding"]
    assert plan["requires_confirmation"] is False


def test_workflow_plan_calendar_to_email_draft():
    plan = plan_dynamic_workflow("Check tomorrow's meetings and draft an email summary.")
    assert plan["intent"] == "schedule_and_email"
    assert plan["agents"] == ["calendar", "analysis", "email"]
    assert plan["requires_confirmation"] is False


def test_workflow_plan_calendar_to_email_send_requires_confirmation():
    plan = plan_dynamic_workflow("Check tomorrow's meetings and email me the summary.")
    assert plan["intent"] == "schedule_and_email"
    assert plan["agents"] == ["calendar", "analysis", "email"]
    assert plan["requires_confirmation"] is True


def test_workflow_plan_email_to_calendar_schedule():
    plan = plan_dynamic_workflow("Find emails about my interview and schedule the interview date.")
    assert plan["intent"] == "email_to_calendar"
    assert plan["agents"] == ["email", "analysis", "calendar"]
    assert plan["requires_confirmation"] is True


def test_workflow_plan_conversational_greetings():
    """Verify fast conversational path for greetings and simple queries like hey and wassup."""
    for query in ["hey", "wassup", "hey , wassup", "hello there", "how are you", "what can you do"]:
        plan = plan_dynamic_workflow(query)
        assert plan["intent"] == "conversational"
        assert plan["agents"] == []
        assert "direct_response" in plan
        assert len(plan["direct_response"]) > 0
        assert plan["requires_confirmation"] is False

