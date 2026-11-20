"""
Standard Base Agent interface and Tool Permission Model for specialized agents.

Each agent inherits from BaseAgent:
- name: Unique identifier (e.g. 'research', 'analysis', 'coding', 'database', 'document', 'email', 'calendar')
- description: Domain responsibility for Supervisor planning
- allowed_tools: Principle of Least Privilege - only tools assigned to this agent are exposed
- run(state): Executes the agent cycle and returns partial state update
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from app.graph.state import GraphState
from app.services.mcp_client import mcp_client

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Standard Base Agent interface enforcing least-privilege tool access
    and consistent execution contracts across the multi-agent system.
    """

    name: str = "base_agent"
    description: str = "Base agent specification"
    role: str = "Specialist"
    allowed_tools: List[str] = []

    def get_scoped_tools(self) -> List[Dict[str, Any]]:
        """
        Tool Permission Model:
        Filter available MCP tools to strictly match allowed_tools for this agent.
        Prevents unauthorized capabilities (e.g. Email agent cannot access database).
        """
        all_tools = mcp_client.list_tools()
        if not self.allowed_tools:
            return []

        scoped = [
            tool for tool in all_tools
            if tool.get("function", {}).get("name") in self.allowed_tools
        ]
        logger.info(
            "[%s] Scoped %d/%d MCP tools permitted: %s",
            self.name,
            len(scoped),
            len(all_tools),
            [t.get("function", {}).get("name") for t in scoped],
        )
        return scoped

    @abstractmethod
    def run(self, state: GraphState) -> Dict[str, Any]:
        """
        Execute agent reasoning cycle, interact with scoped tools if necessary,
        and return dictionary of state updates.
        """
        pass

    def __call__(self, state: GraphState) -> Dict[str, Any]:
        """Allow agent instance to be called directly as a LangGraph node callable."""
        return self.run(state)
