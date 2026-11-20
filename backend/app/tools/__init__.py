"""
Tools package for Multi-Agent AI Task Automation System.
Exports tools and function schemas for calculator, web search, database,
email, calendar, and safe sandboxed code execution.
"""

from typing import Any, Dict

from app.tools.calculator import calculate
from app.tools.calendar_tools import (
    create_event,
    delete_event,
    find_free_time,
    get_event,
    list_events,
    update_event,
)
from app.tools.code_tools import execute_sandboxed_python, validate_python_code
from app.tools.db_tools import describe_table, execute_read_query, get_sample_rows, list_tables
from app.tools.email_tools import draft_email, get_email, search_emails, send_email
from app.tools.image_tools import search_images
from app.tools.web_search import search_web

# Tool function schemas for LLM tool calling (OpenAI / Groq format)

SEARCH_IMAGES_TOOL_DEFINITION: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "search_images",
        "description": "Search for authentic diagrams, illustrations, charts, and images from Wikimedia Commons, Wikipedia, and media repositories.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Subject, concept, technology, or topic to find images or diagrams for"},
                "max_results": {"type": "integer", "description": "Max images to return (default: 4)", "default": 4},
            },
            "required": ["query"],
        },
    },
}


CALCULATOR_TOOL_DEFINITION: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "calculator",
        "description": "Safely evaluate mathematical expressions (e.g. '125 * 48', '15% of 50000').",
        "parameters": {
            "type": "object",
            "properties": {"expression": {"type": "string", "description": "Mathematical expression to evaluate"}},
            "required": ["expression"],
        },
    },
}

WEB_SEARCH_TOOL_DEFINITION: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Search the live web for recent developments, news, documentation, or facts.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query string"},
                "max_results": {"type": "integer", "description": "Max results to return (default: 4)", "default": 4},
            },
            "required": ["query"],
        },
    },
}

LIST_TABLES_TOOL_DEFINITION: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "list_tables",
        "description": "List all accessible tables in the relational database.",
        "parameters": {"type": "object", "properties": {}},
    },
}

DESCRIBE_TABLE_TOOL_DEFINITION: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "describe_table",
        "description": "Get schema, columns, and data types for a specific database table.",
        "parameters": {
            "type": "object",
            "properties": {"table_name": {"type": "string", "description": "Name of the table"}},
            "required": ["table_name"],
        },
    },
}

EXECUTE_READ_QUERY_TOOL_DEFINITION: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "execute_read_query",
        "description": "Execute a safe, read-only SQL query (SELECT only). Write operations are rejected.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "SQL SELECT query string"},
                "max_rows": {"type": "integer", "description": "Max rows to return (default: 100)", "default": 100},
            },
            "required": ["query"],
        },
    },
}

SEARCH_EMAILS_TOOL_DEFINITION: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "search_emails",
        "description": "Search the user's emails by keyword, sender, or subject.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search term"},
                "folder": {"type": "string", "description": "Folder filter ('inbox', 'sent', 'drafts')"},
            },
            "required": ["query"],
        },
    },
}

DRAFT_EMAIL_TOOL_DEFINITION: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "draft_email",
        "description": "Create a draft email in the user's drafts folder without sending it.",
        "parameters": {
            "type": "object",
            "properties": {
                "recipient": {"type": "string", "description": "Recipient email address"},
                "subject": {"type": "string", "description": "Subject line"},
                "body": {"type": "string", "description": "Email body content"},
            },
            "required": ["recipient", "subject", "body"],
        },
    },
}

SEND_EMAIL_TOOL_DEFINITION: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "send_email",
        "description": "Send an email. Requires explicit user confirmation.",
        "parameters": {
            "type": "object",
            "properties": {
                "recipient": {"type": "string", "description": "Recipient email address"},
                "subject": {"type": "string", "description": "Subject line"},
                "body": {"type": "string", "description": "Email body content"},
                "confirmed": {"type": "boolean", "description": "True if user explicitly approved sending", "default": False},
            },
            "required": ["recipient", "subject", "body"],
        },
    },
}

LIST_EVENTS_TOOL_DEFINITION: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "list_events",
        "description": "List scheduled calendar events within an optional date range.",
        "parameters": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "description": "Optional ISO start date (YYYY-MM-DD)"},
                "end_date": {"type": "string", "description": "Optional ISO end date (YYYY-MM-DD)"},
            },
        },
    },
}

CREATE_EVENT_TOOL_DEFINITION: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "create_event",
        "description": "Schedule a new calendar event. Requires explicit user confirmation before creation.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Event title"},
                "start_time": {"type": "string", "description": "Start ISO datetime (YYYY-MM-DDTHH:MM:SS)"},
                "end_time": {"type": "string", "description": "End ISO datetime (YYYY-MM-DDTHH:MM:SS)"},
                "attendees": {"type": "array", "items": {"type": "string"}, "description": "List of attendee emails"},
                "description": {"type": "string", "description": "Event description"},
                "confirmed": {"type": "boolean", "description": "True if user approved creation", "default": False},
            },
            "required": ["title", "start_time", "end_time"],
        },
    },
}

VALIDATE_PYTHON_CODE_TOOL_DEFINITION: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "validate_python_code",
        "description": "Inspect and validate Python code syntax and safety via AST parsing.",
        "parameters": {
            "type": "object",
            "properties": {"code": {"type": "string", "description": "Python source code"}},
            "required": ["code"],
        },
    },
}

EXECUTE_SANDBOXED_PYTHON_TOOL_DEFINITION: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "execute_sandboxed_python",
        "description": "Execute Python code in a secure restricted sandbox with timeout capping.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python code to execute"},
                "timeout": {"type": "integer", "description": "Timeout in seconds (default: 5)", "default": 5},
            },
            "required": ["code"],
        },
    },
}

# Available tool mapping for runtime dispatch
AVAILABLE_TOOLS = {
    "calculator": calculate,
    "web_search": search_web,
    "search_images": search_images,
    "list_tables": list_tables,
    "describe_table": describe_table,
    "execute_read_query": execute_read_query,
    "get_sample_rows": get_sample_rows,
    "search_emails": search_emails,
    "get_email": get_email,
    "draft_email": draft_email,
    "send_email": send_email,
    "list_events": list_events,
    "get_event": get_event,
    "find_free_time": find_free_time,
    "create_event": create_event,
    "update_event": update_event,
    "delete_event": delete_event,
    "validate_python_code": validate_python_code,
    "execute_sandboxed_python": execute_sandboxed_python,
}

__all__ = [
    "calculate",
    "search_web",
    "search_images",
    "list_tables",
    "describe_table",
    "execute_read_query",
    "get_sample_rows",
    "search_emails",
    "get_email",
    "draft_email",
    "send_email",
    "list_events",
    "get_event",
    "find_free_time",
    "create_event",
    "update_event",
    "delete_event",
    "validate_python_code",
    "execute_sandboxed_python",
    "CALCULATOR_TOOL_DEFINITION",
    "WEB_SEARCH_TOOL_DEFINITION",
    "SEARCH_IMAGES_TOOL_DEFINITION",
    "LIST_TABLES_TOOL_DEFINITION",
    "DESCRIBE_TABLE_TOOL_DEFINITION",
    "EXECUTE_READ_QUERY_TOOL_DEFINITION",
    "SEARCH_EMAILS_TOOL_DEFINITION",
    "DRAFT_EMAIL_TOOL_DEFINITION",
    "SEND_EMAIL_TOOL_DEFINITION",
    "LIST_EVENTS_TOOL_DEFINITION",
    "CREATE_EVENT_TOOL_DEFINITION",
    "VALIDATE_PYTHON_CODE_TOOL_DEFINITION",
    "EXECUTE_SANDBOXED_PYTHON_TOOL_DEFINITION",
    "AVAILABLE_TOOLS",
]

