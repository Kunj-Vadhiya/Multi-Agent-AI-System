"""
Analysis Agent module.

Specialized agent responsible for:
- Deeply evaluating findings, data, and patterns produced by other agents.
- Comparing approaches, methodologies, and technical trade-offs.
- Analyzing metrics, advantages, limitations, and risks.
- Performing exact numeric calculations via the calculator tool.
"""

import logging
from typing import Any, Dict

from app.agents.base import BaseAgent
from app.graph.state import GraphState
from app.services import llm_service

logger = logging.getLogger(__name__)

ANALYST_SYSTEM_PROMPT = """You are the Analysis Agent in a multi-agent system.
Your role is to deeply analyze, compare, and reason over data provided by other specialized agents.

Guidelines:
- Work strictly from the provided research, database, code, or schedule data in the prompt.
- If numeric calculations or percentages are needed, call the 'calculator' tool.
- Do NOT perform web searches or hallucinate external facts.
- Provide a rigorous, structured analytical assessment including:
  1. Core findings and pattern evaluation
  2. Comparative analysis of approaches or alternatives
  3. Key advantages and strengths
  4. Limitations, risks, and bottlenecks
  5. Architectural and strategic trade-offs (e.g. latency vs accuracy, complexity vs maintainability)"""


class AnalysisAgent(BaseAgent):
    name = "analysis"
    description = "Evaluates data, compares approaches, and identifies architectural patterns and trade-offs."
    role = "Reasoning, Comparative Analysis & Evaluation"
    allowed_tools = ["calculator"]

    def run(self, state: GraphState) -> Dict[str, Any]:
        user_query = state.get("user_query", "")
        research_data = (state.get("research_data") or "")[:3000]
        database_results = state.get("database_results")
        code_results = state.get("code_results")
        calendar_results = state.get("calendar_results")
        rag_context = state.get("rag_context")
        agent_logs = list(state.get("agent_logs") or [])
        agent_history = list(state.get("agent_history") or [])

        logger.info("[Analysis Agent] Executing analysis for query: '%s'", user_query)

        scoped_tools = self.get_scoped_tools()

        # Build context from whatever prior agents produced
        context_parts = []
        if research_data:
            context_parts.append(f"--- RESEARCH FINDINGS ---\n{research_data}")
        if rag_context:
            context_parts.append(f"--- RAG DOCUMENT CONTEXT ---\n{rag_context[:1500]}")
        if database_results:
            context_parts.append(f"--- DATABASE QUERY RESULTS ---\n{database_results}")
        if code_results:
            context_parts.append(f"--- CODE RESULTS ---\n{code_results}")
        if calendar_results:
            context_parts.append(f"--- CALENDAR DATA ---\n{calendar_results}")

        combined_input = "\n\n".join(context_parts) if context_parts else "No intermediate agent data provided."

        user_prompt = (
            f"Original User Request:\n{user_query}\n\n"
            f"{combined_input}\n\n"
            "Please provide a rigorous comparative analysis, identifying key patterns, trade-offs, "
            "and evaluating advantages and limitations."
        )

        analysis_result = llm_service.run_agent_with_tools(
            system_prompt=ANALYST_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            tools=scoped_tools,
            temperature=0.3,
            max_tool_rounds=2,
            max_tokens=2500,
        )

        agent_logs.append(
            {
                "agent": self.name,
                "action": "Produced comparative analysis and trade-off evaluation",
                "preview": analysis_result[:150] + "...",
            }
        )

        agent_history.append({"agent": self.name, "status": "completed"})

        return {
            "current_agent": self.name,
            "analysis_data": analysis_result,
            "analysis": analysis_result,
            "agent_logs": agent_logs,
            "agent_history": agent_history,
        }


# Singleton callable node for LangGraph
analysis_agent_node = AnalysisAgent()
