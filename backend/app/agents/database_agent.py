"""
Database Agent module.

Specialized agent responsible for:
- Inspecting database schemas, discovering tables, and examining column types.
- Generating and executing safe, read-only SQL queries (SELECT only).
- Analyzing relational datasets and explaining query results.
- Enforcing database security policies (blocking destructive write/drop operations).
- Populating database_results in workflow state.
"""

import json
import logging
from typing import Any, Dict

from app.agents.base import BaseAgent
from app.graph.state import GraphState
from app.services import llm_service

logger = logging.getLogger(__name__)

DATABASE_SYSTEM_PROMPT = """You are the Database Agent in a multi-agent task automation system.
Your responsibility is schema discovery, SQL query generation, safe query execution, and relational data analysis.

Database Tools Available:
- list_tables: Call to discover all available tables in the database.
- describe_table: Call with a table_name to view column names and types.
- execute_read_query: Call with a SELECT query to safely query data.
- get_sample_rows: Call with a table_name to view sample rows.

Security Constraints:
- You have READ-ONLY database access.
- NEVER attempt to execute INSERT, UPDATE, DELETE, DROP, ALTER, or TRUNCATE operations.
- Construct efficient queries using LIMIT and filtering.
- Interpret the returned rows and explain what the data reveals to address the user's objective."""


class DatabaseAgent(BaseAgent):
    name = "database"
    description = "Inspects schemas, executes safe read-only SQL queries, and analyzes relational database tables."
    role = "Database Operations & SQL Analytics"
    allowed_tools = ["list_tables", "describe_table", "execute_read_query", "get_sample_rows"]

    def run(self, state: GraphState) -> Dict[str, Any]:
        user_query = state.get("user_query", "")
        plan = state.get("plan") or []
        agent_logs = list(state.get("agent_logs") or [])
        agent_history = list(state.get("agent_history") or [])

        logger.info("[Database Agent] Executing database task for query: '%s'", user_query)

        scoped_tools = self.get_scoped_tools()

        user_prompt = (
            f"User Query:\n{user_query}\n\n"
            "Instructions: Inspect the database schema, identify the relevant tables, "
            "run the required safe SQL SELECT queries, and summarize the findings with exact data."
        )

        db_analysis = llm_service.run_agent_with_tools(
            system_prompt=DATABASE_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            tools=scoped_tools,
            temperature=0.2,
            max_tool_rounds=3,
            max_tokens=1400,
        )

        database_results_payload = {
            "summary": db_analysis,
            "status": "completed",
        }

        agent_logs.append(
            {
                "agent": self.name,
                "action": "Queried database and analyzed schema/records",
                "preview": db_analysis[:150] + "...",
            }
        )

        agent_history.append({"agent": self.name, "status": "completed"})

        return {
            "current_agent": self.name,
            "database_results": database_results_payload,
            "draft": db_analysis,
            "agent_logs": agent_logs,
            "agent_history": agent_history,
        }


# Singleton callable node for LangGraph
database_agent_node = DatabaseAgent()
