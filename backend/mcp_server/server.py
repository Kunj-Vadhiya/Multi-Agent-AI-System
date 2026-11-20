"""
MCP Server implementation for Multi-Agent AI Task Automation System.

Exposes standard MCP tools across specialized agent domains:
- Core: calculator, web_search
- Database: list_tables, describe_table, execute_read_query, get_sample_rows
- Email: search_emails, get_email, draft_email, send_email
- Calendar: list_events, get_event, find_free_time, create_event
- Code: validate_python_code, execute_sandboxed_python

Supports multiple transports:
- stdio: for CLI subprocess execution
- sse: for standalone HTTP/SSE server execution
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcp.server.mcpserver import MCPServer

from app.tools.calculator import calculate
from app.tools.calendar_tools import create_event, find_free_time, get_event, list_events
from app.tools.code_tools import execute_sandboxed_python, validate_python_code
from app.tools.db_tools import describe_table, execute_read_query, get_sample_rows, list_tables
from app.tools.email_tools import draft_email, get_email, search_emails, send_email
from app.tools.image_tools import search_images
from app.tools.web_search import search_web


# Configure structured logging for MCP Server
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [MCP Server] %(levelname)s - %(message)s",
)
logger = logging.getLogger("mcp_server")

# Instantiate MCPServer instance
mcp = MCPServer("multi-agent-mcp-server")


@mcp.tool(
    name="calculator",
    description="Safely evaluate mathematical expressions (e.g. '125 * 48', '15% of 50000').",
)
def mcp_calculator(expression: str) -> Dict[str, Any]:
    if not expression or not expression.strip():
        return {"error": "Expression cannot be empty."}
    calc_res = calculate(expression)
    if calc_res.startswith("Error:"):
        return {"error": calc_res}
    try:
        val = float(calc_res)
        return {"result": int(val) if val.is_integer() else val}
    except ValueError:
        return {"result": calc_res}


@mcp.tool(
    name="web_search",
    description="Search the web for up-to-date information, news, or technical documentation.",
)
def mcp_web_search(query: str, max_results: int = 4) -> Dict[str, Any]:
    if not query or not query.strip():
        return {"query": query, "results": [], "error": "Search query cannot be empty."}
    return search_web(query=query, max_results=max_results)


@mcp.tool(
    name="search_images",
    description="Search for authentic diagrams, illustrations, charts, and images from Wikimedia Commons, Wikipedia, and media repositories.",
)
def mcp_search_images(query: str, max_results: int = 4) -> Dict[str, Any]:
    if not query or not query.strip():
        return {"query": query, "images": [], "error": "Search query cannot be empty."}
    return search_images(query=query, max_results=max_results)



@mcp.tool(
    name="list_tables",
    description="List all accessible tables in the database.",
)
def mcp_list_tables() -> Dict[str, Any]:
    tables = list_tables()
    return {"tables": tables}


@mcp.tool(
    name="describe_table",
    description="Get schema, column names, and data types for a table.",
)
def mcp_describe_table(table_name: str) -> Dict[str, Any]:
    return describe_table(table_name)


@mcp.tool(
    name="execute_read_query",
    description="Execute a safe, read-only SQL query (SELECT only). Write queries are rejected.",
)
def mcp_execute_read_query(query: str, max_rows: int = 100) -> Dict[str, Any]:
    return execute_read_query(query=query, max_rows=max_rows)


@mcp.tool(
    name="get_sample_rows",
    description="Get sample rows from a database table.",
)
def mcp_get_sample_rows(table_name: str, limit: int = 5) -> Dict[str, Any]:
    return get_sample_rows(table_name=table_name, limit=limit)


@mcp.tool(
    name="search_emails",
    description="Search emails by keyword, sender, or subject.",
)
def mcp_search_emails(query: str, folder: Optional[str] = None) -> Dict[str, Any]:
    return search_emails(query=query, folder=folder)


@mcp.tool(
    name="get_email",
    description="Get full content of an email by its ID.",
)
def mcp_get_email(email_id: str) -> Dict[str, Any]:
    return get_email(email_id=email_id)


@mcp.tool(
    name="draft_email",
    description="Create an email draft in the drafts folder without sending.",
)
def mcp_draft_email(recipient: str, subject: str, body: str) -> Dict[str, Any]:
    return draft_email(recipient=recipient, subject=subject, body=body)


@mcp.tool(
    name="send_email",
    description="Send an email. Requires explicit user confirmation.",
)
def mcp_send_email(recipient: str, subject: str, body: str, confirmed: bool = False) -> Dict[str, Any]:
    return send_email(recipient=recipient, subject=subject, body=body, confirmed=confirmed)


@mcp.tool(
    name="list_events",
    description="List scheduled calendar events within an optional date range.",
)
def mcp_list_events(start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
    return list_events(start_date=start_date, end_date=end_date)


@mcp.tool(
    name="get_event",
    description="Get calendar event details by ID.",
)

def mcp_get_event(event_id: str) -> Dict[str, Any]:
    return get_event(event_id=event_id)

@mcp.tool(
    name="find_free_time",
    description="Find open time slots on a given date.",
)
def mcp_find_free_time(date: str, duration_minutes: int = 30) -> Dict[str, Any]:
    return find_free_time(date=date, duration_minutes=duration_minutes)


@mcp.tool(
    name="create_event",
    description="Schedule a calendar event. Requires explicit user confirmation.",
)
def mcp_create_event(
    title: str,
    start_time: str,
    end_time: str,
    attendees: Optional[List[str]] = None,
    description: str = "",
    confirmed: bool = False,
) -> Dict[str, Any]:
    return create_event(
        title=title,
        start_time=start_time,
        end_time=end_time,
        attendees=attendees,
        description=description,
        confirmed=confirmed,
    )


@mcp.tool(
    name="validate_python_code",
    description="Inspect and validate Python code syntax and safety via AST parsing.",
)
def mcp_validate_python_code(code: str) -> Dict[str, Any]:
    return validate_python_code(code=code)


@mcp.tool(
    name="execute_sandboxed_python",
    description="Execute Python code in a secure restricted sandbox with timeout capping.",
)
def mcp_execute_sandboxed_python(code: str, timeout: int = 5) -> Dict[str, Any]:
    return execute_sandboxed_python(code=code, timeout=timeout)


# Starlette app for SSE transport
app = mcp.sse_app()


def main() -> None:
    """Entry point for standalone execution of MCP server."""
    parser = argparse.ArgumentParser(description="Multi-Agent MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport protocol to use (default: stdio)",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host for SSE server")
    parser.add_argument("--port", type=int, default=8001, help="Port for SSE server")
    args = parser.parse_args()

    if args.transport == "sse":
        import uvicorn

        logger.info("Starting MCP Server with SSE transport on http://%s:%d...", args.host, args.port)
        uvicorn.run(app, host=args.host, port=args.port)
    else:
        logger.info("Starting MCP Server with stdio transport...")
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
