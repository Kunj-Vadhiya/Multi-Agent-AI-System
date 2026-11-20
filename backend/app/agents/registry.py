"""
Agent Registry module.

Centralized catalog of all available specialized agents.
Allows the Supervisor to inspect agent descriptions, roles, and allowed tools
to formulate dynamic multi-agent execution plans.
"""

from typing import Dict, Type

from app.agents.analyst import AnalysisAgent, analysis_agent_node
from app.agents.base import BaseAgent
from app.agents.calendar_agent import CalendarAgent, calendar_agent_node
from app.agents.coder import CodingAgent, coding_agent_node
from app.agents.database_agent import DatabaseAgent, database_agent_node
from app.agents.document_agent import DocumentAgent, document_agent_node
from app.agents.email_agent import EmailAgent, email_agent_node
from app.agents.researcher import ResearchAgent, research_agent_node
from app.agents.validator import validator_agent_node
from app.agents.writer import writer_agent_node

# Agent class registry
AVAILABLE_AGENTS: Dict[str, Type[BaseAgent]] = {
    "research": ResearchAgent,
    "analysis": AnalysisAgent,
    "coding": CodingAgent,
    "database": DatabaseAgent,
    "document": DocumentAgent,
    "email": EmailAgent,
    "calendar": CalendarAgent,
}

# Node mapping for LangGraph registration
AGENT_NODES = {
    "research": research_agent_node,
    "analysis": analysis_agent_node,
    "coding": coding_agent_node,
    "database": database_agent_node,
    "document": document_agent_node,
    "email": email_agent_node,
    "calendar": calendar_agent_node,
    "writer": writer_agent_node,
    "validator": validator_agent_node,
}


def get_agent_descriptions() -> str:
    """Format catalog of agents and their specializations for Supervisor planning prompt."""
    lines = []
    for key, agent_cls in AVAILABLE_AGENTS.items():
        lines.append(f"- '{key}': {agent_cls.description} (Role: {agent_cls.role})")
    return "\n".join(lines)
