"""
Coding Agent module.

Specialized agent responsible for:
- Writing, debugging, explaining, and refactoring source code (Python, SQL, FastAPI, etc.).
- Verifying code safety and syntax with validate_python_code tool.
- Executing code safely in an isolated restricted sandbox via execute_sandboxed_python tool.
- Populating code_results in workflow state.
"""

import json
import logging
from typing import Any, Dict

from app.agents.base import BaseAgent
from app.graph.state import GraphState
from app.services import llm_service

logger = logging.getLogger(__name__)

CODER_SYSTEM_PROMPT = """You are the Coding Agent in a multi-agent task automation system.
Your responsibility is software engineering, code generation, debugging, refactoring, and code review.

Tools Available:
- validate_python_code: Call this to parse code through an AST to check syntax errors and security policy violations.
- execute_sandboxed_python: Call this to run code safely in a restricted sandbox with timeout protection to verify output.

Guidelines:
- Write clean, modular, production-ready code with type annotations and docstrings.
- Always present the complete, runnable code block in your response.
- Tools (validation/execution) are optional: for standard coding requests, write and present the complete, working code solution directly with clean explanations and usage examples.
- Adhere to security best practices: do not attempt to import restricted host modules or use dangerous functions.
- If implementing an API, follow FastAPI idioms with Pydantic schemas.
- If asked to debug or review code, identify root causes and provide the corrected version."""


class CodingAgent(BaseAgent):
    name = "coding"
    description = "Generates, reviews, debugs, and validates software code with safe sandboxed execution."
    role = "Software Development & Code Engineering"
    allowed_tools = ["validate_python_code", "execute_sandboxed_python"]

    def run(self, state: GraphState) -> Dict[str, Any]:
        user_query = state.get("user_query", "")
        database_results = state.get("database_results")
        research_data = state.get("research_data")
        agent_logs = list(state.get("agent_logs") or [])
        agent_history = list(state.get("agent_history") or [])

        logger.info("[Coding Agent] Processing code request: '%s'", user_query)

        scoped_tools = self.get_scoped_tools()

        context_info = []
        if database_results:
            context_info.append(f"Database Schema Context:\n{database_results}")
        if research_data:
            context_info.append(f"Research Documentation:\n{research_data[:1500]}")

        additional_context = "\n\n".join(context_info)

        user_prompt = (
            f"User Request:\n{user_query}\n\n"
            f"{additional_context}\n\n"
            "Please deliver the complete requested code implementation directly in Markdown code blocks, "
            "with clear comments, explanations, and usage examples."
        )

        code_response = llm_service.run_agent_with_tools(
            system_prompt=CODER_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            tools=scoped_tools,
            temperature=0.2,
            max_tool_rounds=2,
            max_tokens=1500,
        )

        code_results_payload = {
            "response": code_response,
            "status": "completed",
        }

        agent_logs.append(
            {
                "agent": self.name,
                "action": "Generated and validated code solution",
                "preview": code_response[:150] + "...",
            }
        )

        agent_history.append({"agent": self.name, "status": "completed"})

        return {
            "current_agent": self.name,
            "code_results": code_results_payload,
            "draft": code_response,
            "agent_logs": agent_logs,
            "agent_history": agent_history,
        }


# Singleton callable node for LangGraph
coding_agent_node = CodingAgent()
