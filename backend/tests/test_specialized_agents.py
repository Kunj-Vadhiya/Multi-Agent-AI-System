"""
Unit tests for the Pre-V8 Specialized Agents:
- Coding Agent (AST validation, sandboxed Python execution)
- Database Agent (Schema inspection, safe queries, read-only enforcement)
- Document Agent (Document creation, structured markdown artifacts)
- Email Agent (Search, draft, and confirmation safety)
- Calendar Agent (Event lookup, free time, and confirmation safety)
"""

import pytest
from app.agents.coder import CodingAgent
from app.agents.database_agent import DatabaseAgent
from app.agents.document_agent import DocumentAgent
from app.agents.email_agent import EmailAgent
from app.agents.calendar_agent import CalendarAgent
from app.tools.code_tools import validate_python_code, execute_sandboxed_python
from app.tools.db_tools import list_tables, describe_table, execute_read_query
from app.tools.email_tools import search_emails, draft_email, send_email
from app.tools.calendar_tools import list_events, find_free_time, create_event


# ---------------------------------------------------------
# 1. CODING AGENT & CODE TOOLS
# ---------------------------------------------------------

def test_code_validation_valid():
    code = "def add(a, b):\n    return a + b\n"
    res = validate_python_code(code)
    assert res["valid"] is True
    assert res["syntax_error"] is None
    assert len(res["security_violations"]) == 0


def test_code_validation_syntax_error():
    bad_code = "def broken(\n    return 42"
    res = validate_python_code(bad_code)
    assert res["valid"] is False
    assert res["syntax_error"] is not None


def test_code_validation_unsafe_imports():
    unsafe_code = "import os\nos.system('dir')"
    res = validate_python_code(unsafe_code)
    assert res["valid"] is False
    assert any("os" in v for v in res["security_violations"])


def test_sandboxed_python_execution():
    code = "numbers = [1, 2, 3, 4, 5]\nprint('Sum:', sum(numbers))"
    res = execute_sandboxed_python(code)
    assert res["status"] == "success"
    assert "Sum: 15" in res["stdout"]


def test_sandboxed_python_banned_builtin():
    code = "eval('1 + 1')"
    res = execute_sandboxed_python(code)
    assert res["status"] == "rejected"
    assert "Security policy violation" in res["error"] or "prohibited function" in res["error"]


def test_coding_agent_run():
    agent = CodingAgent()
    state = {
        "user_query": "Write a python function to compute factorial and test it",
        "agent_history": [],
        "agent_logs": [],
    }
    result = agent.run(state)
    assert result["current_agent"] == "coding"
    assert "code_results" in result
    assert result["code_results"]["status"] == "completed"
    assert "def " in result["draft"] or "factorial" in result["draft"]


# ---------------------------------------------------------
# 2. DATABASE AGENT & DB TOOLS
# ---------------------------------------------------------

def test_db_list_tables():
    tables = list_tables()
    assert isinstance(tables, list)
    assert "customers" in tables
    assert "orders" in tables


def test_db_describe_table():
    res = describe_table("customers")
    assert "columns" in res
    cols = [c["name"] for c in res["columns"]]
    assert "customer_id" in cols
    assert "name" in cols


def test_db_execute_read_query():
    query = "SELECT name, email FROM customers WHERE status = 'active' LIMIT 3"
    res = execute_read_query(query)
    assert "error" not in res
    assert res["row_count"] > 0
    assert len(res["rows"]) > 0


def test_db_read_only_enforcement():
    dangerous_query = "DROP TABLE customers"
    res = execute_read_query(dangerous_query)
    assert "error" in res
    assert "read-only" in res["error"].lower()


def test_database_agent_run():
    agent = DatabaseAgent()
    state = {
        "user_query": "Find the top active customers in the database",
        "agent_history": [],
        "agent_logs": [],
    }
    result = agent.run(state)
    assert result["current_agent"] == "database"
    assert "database_results" in result
    assert result["database_results"]["status"] == "completed"
    assert len(result["draft"]) > 0


# ---------------------------------------------------------
# 3. DOCUMENT AGENT
# ---------------------------------------------------------

def test_document_agent_run():
    agent = DocumentAgent()
    state = {
        "user_query": "Generate a technical report on RAG architectures",
        "research_results": {"findings": ["RAG combines vector search with LLMs.", "Chunking improves precision."]},
        "analysis": "RAG reduces hallucinations by 80% compared to zero-shot generation.",
        "agent_history": [],
        "agent_logs": [],
    }
    result = agent.run(state)
    assert result["current_agent"] == "document"
    assert "document_results" in result
    assert result["document_results"]["format"] == "markdown"
    assert "RAG" in result["draft"]


# ---------------------------------------------------------
# 4. EMAIL AGENT & EMAIL TOOLS
# ---------------------------------------------------------

def test_email_search():
    res = search_emails("interview")
    assert "emails" in res
    assert res["count"] > 0
    assert "interview" in str(res["emails"]).lower()


def test_email_draft():
    res = draft_email("test@example.com", "Project Status", "Here is the summary.")
    assert res["status"] == "draft_created"
    assert res["draft"]["recipient"] == "test@example.com"


def test_email_send_without_confirmation():
    res = send_email("test@example.com", "Project Status", "Body", confirmed=False)
    assert res["status"] == "requires_confirmation"
    assert res["confirmation_required"] is True


def test_email_send_with_confirmation():
    res = send_email("test@example.com", "Project Status", "Body", confirmed=True)
    assert res["status"] == "sent"


def test_email_agent_draft_mode():
    agent = EmailAgent()
    state = {
        "user_query": "Draft an email to client about project milestone",
        "agent_history": [],
        "agent_logs": [],
    }
    result = agent.run(state)
    assert result["current_agent"] == "email"
    assert result.get("confirmation_required") is False
    assert "email_results" in result


def test_email_agent_send_requires_confirmation():
    agent = EmailAgent()
    state = {
        "user_query": "Send this email summary to the team immediately",
        "agent_history": [],
        "agent_logs": [],
        "confirmation_status": "NONE",
    }
    result = agent.run(state)
    assert result["confirmation_required"] is True
    assert result["workflow_status"] == "awaiting_confirmation"
    assert result["pending_action"]["action"] == "send_email"


# ---------------------------------------------------------
# 5. CALENDAR AGENT & CALENDAR TOOLS
# ---------------------------------------------------------

def test_calendar_list_events():
    res = list_events()
    assert "events" in res
    assert res["count"] > 0
    assert any("Architecture" in e["title"] or "Demo" in e["title"] or "Standup" in e["title"] for e in res["events"])


def test_calendar_find_free_time():
    res = find_free_time("2026-10-01", duration_minutes=30)
    assert "available_slots" in res
    assert len(res["available_slots"]) > 0


def test_calendar_create_without_confirmation():
    res = create_event(
        title="1:1 Sync",
        start_time="2026-10-01T15:00:00",
        end_time="2026-10-01T15:30:00",
        confirmed=False,
    )
    assert res["status"] == "requires_confirmation"
    assert res["confirmation_required"] is True


def test_calendar_create_with_confirmation():
    res = create_event(
        title="1:1 Sync",
        start_time="2026-10-01T15:00:00",
        end_time="2026-10-01T15:30:00",
        confirmed=True,
    )
    assert res["status"] == "event_created"


def test_calendar_agent_schedule_requires_confirmation():
    agent = CalendarAgent()
    state = {
        "user_query": "Schedule a meeting with recruiter for tomorrow at 4 PM",
        "agent_history": [],
        "agent_logs": [],
        "confirmation_status": "NONE",
    }
    result = agent.run(state)
    assert result["confirmation_required"] is True
    assert result["workflow_status"] == "awaiting_confirmation"
    assert result["pending_action"]["action"] == "create_calendar_event"
