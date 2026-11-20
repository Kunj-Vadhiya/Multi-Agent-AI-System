"""
Agents package for Multi-Agent AI Task Automation System.
Exports nodes and classes for:
- Supervisor
- Research Agent
- Analysis Agent
- Coding Agent
- Database Agent
- Document Agent
- Email Agent
- Calendar Agent
- Writer Agent
- Validator Agent
"""

from app.agents.analyst import AnalysisAgent, analysis_agent_node
from app.agents.base import BaseAgent
from app.agents.calendar_agent import CalendarAgent, calendar_agent_node
from app.agents.coder import CodingAgent, coding_agent_node
from app.agents.database_agent import DatabaseAgent, database_agent_node
from app.agents.document_agent import DocumentAgent, document_agent_node
from app.agents.email_agent import EmailAgent, email_agent_node
from app.agents.registry import AVAILABLE_AGENTS, AGENT_NODES
from app.agents.researcher import ResearchAgent, research_agent_node
from app.agents.supervisor import supervisor_node
from app.agents.validator import ValidatorAgent, validator_agent_node
from app.agents.writer import WriterAgent, writer_agent_node

__all__ = [
    "BaseAgent",
    "AVAILABLE_AGENTS",
    "AGENT_NODES",
    "supervisor_node",
    "research_agent_node",
    "analysis_agent_node",
    "coding_agent_node",
    "database_agent_node",
    "document_agent_node",
    "email_agent_node",
    "calendar_agent_node",
    "writer_agent_node",
    "validator_agent_node",
    "ResearchAgent",
    "AnalysisAgent",
    "CodingAgent",
    "DatabaseAgent",
    "DocumentAgent",
    "EmailAgent",
    "CalendarAgent",
    "WriterAgent",
    "ValidatorAgent",
]
