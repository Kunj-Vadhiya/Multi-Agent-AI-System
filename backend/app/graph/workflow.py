"""
LangGraph Multi-Agent Workflow definition for Pre-V8 Specialized Agent Expansion.
Constructs a dynamic supervisor-coordinated multi-agent graph with:
- Persistent SQLite-backed Checkpointing
- 7 Specialized Agents (Research, Analysis, Coding, Database, Document, Email, Calendar)
- Writer Agent for technical synthesis and revision
- Validator Agent with structured multi-domain quality auditing and retry loop
- Least-privilege Tool Permissions
- Human-in-the-loop confirmation pausing and resumption
- Retry limit protection against infinite cycles
"""

import logging
import uuid
from typing import Any, Dict, Optional

from langgraph.graph import END, START, StateGraph

from app.agents.analyst import analysis_agent_node
from app.agents.calendar_agent import calendar_agent_node
from app.agents.coder import coding_agent_node
from app.agents.database_agent import database_agent_node
from app.agents.document_agent import document_agent_node
from app.agents.email_agent import email_agent_node
from app.agents.researcher import research_agent_node
from app.agents.supervisor import supervisor_node
from app.agents.validator import validator_agent_node
from app.agents.writer import writer_agent_node
from app.config import settings
from app.graph.state import GraphState
from app.services.checkpoint_service import get_checkpointer

logger = logging.getLogger(__name__)

AGENT_NODE_MAP = {
    "research": "research_agent",
    "research_agent": "research_agent",
    "analysis": "analysis_agent",
    "analysis_agent": "analysis_agent",
    "coding": "coding_agent",
    "coding_agent": "coding_agent",
    "database": "database_agent",
    "database_agent": "database_agent",
    "document": "document_agent",
    "document_agent": "document_agent",
    "email": "email_agent",
    "email_agent": "email_agent",
    "calendar": "calendar_agent",
    "calendar_agent": "calendar_agent",
    "writer": "writer_agent",
    "writer_agent": "writer_agent",
}


def route_supervisor(state: GraphState) -> str:
    """
    Evaluates the supervisor's dynamic routing decision in state.

    Args:
        state (GraphState): Current workflow state.

    Returns:
        str: Next node key or END signal.
    """
    next_step = state.get("next_agent", "FINISH")
    logger.info("Supervisor conditional routing dispatched to: '%s'", next_step)
    if next_step in AGENT_NODE_MAP:
        return AGENT_NODE_MAP[next_step]
    return "FINISH"


def route_validator(state: GraphState) -> str:
    """
    Evaluates the Validator Agent's structured verdict and enforces retry protection.

    Args:
        state (GraphState): Current workflow state.

    Returns:
        str: Next node ('writer_agent' if FAIL and within retry limit; 'FINISH' if PASS or retries exhausted).
    """
    validation_result = state.get("validation_result") or {}
    status = str(validation_result.get("status", "PASS")).upper().strip()
    retry_count = state.get("retry_count", 0)
    max_retries = settings.MAX_RETRIES

    if status == "PASS":
        logger.info("[Validator Routing] Report passed validation. Routing to FINISH (END).")
        return "FINISH"

    # Validation failed: Check if maximum retries have been reached
    if retry_count > max_retries:
        logger.warning(
            "[Validator Routing] Validation failed but maximum retry limit (%d) reached. "
            "Routing to FINISH (END) with best available draft to prevent infinite loops.",
            max_retries,
        )
        return "FINISH"

    logger.info(
        "[Validator Routing] Validation failed (retry cycle %d of %d). Routing back to writer_agent for revision.",
        retry_count,
        max_retries,
    )
    return "writer_agent"


class CheckpointedGraphWrapper:
    """
    Transparent wrapper around CompiledStateGraph ensuring every invoke has a valid thread_id
    so that checkpointer requirements are always satisfied seamlessly across calls.
    """

    def __init__(self, graph: Any) -> None:
        self._graph = graph

    def invoke(self, input: Any, config: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Any:
        cfg = dict(config or {})
        configurable = dict(cfg.get("configurable") or {})
        if "thread_id" not in configurable:
            tid = None
            if isinstance(input, dict):
                tid = input.get("thread_id")
            if not tid:
                tid = f"thread_{uuid.uuid4().hex[:12]}"
            configurable["thread_id"] = str(tid)
            cfg["configurable"] = configurable
        return self._graph.invoke(input, config=cfg, **kwargs)

    def get_state(self, config: Dict[str, Any]) -> Any:
        return self._graph.get_state(config)

    def update_state(self, config: Dict[str, Any], values: Dict[str, Any], as_node: Optional[str] = None) -> Any:
        return self._graph.update_state(config, values, as_node=as_node)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._graph, name)


def create_workflow(checkpointer: Optional[Any] = None) -> Any:
    """
    Constructs and compiles the Multi-Agent LangGraph workflow with persistent checkpointing
    and all 7 specialized agents.

    Args:
        checkpointer (Optional[Any]): Custom checkpointer instance, or default SqliteSaver.

    Returns:
        CheckpointedGraphWrapper: The compiled executable multi-agent workflow graph.
    """
    logger.info("Constructing Multi-Agent StateGraph with 7 Specialized Agents and Validator...")
    workflow = StateGraph(GraphState)

    # Register all agent nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("research_agent", research_agent_node)
    workflow.add_node("analysis_agent", analysis_agent_node)
    workflow.add_node("coding_agent", coding_agent_node)
    workflow.add_node("database_agent", database_agent_node)
    workflow.add_node("document_agent", document_agent_node)
    workflow.add_node("email_agent", email_agent_node)
    workflow.add_node("calendar_agent", calendar_agent_node)
    workflow.add_node("writer_agent", writer_agent_node)
    workflow.add_node("validator_agent", validator_agent_node)

    # Initial entry: START -> supervisor
    workflow.add_edge(START, "supervisor")

    # Supervisor conditionally dispatches to specialized agents or terminates
    workflow.add_conditional_edges(
        "supervisor",
        route_supervisor,
        {
            "research_agent": "research_agent",
            "analysis_agent": "analysis_agent",
            "coding_agent": "coding_agent",
            "database_agent": "database_agent",
            "document_agent": "document_agent",
            "email_agent": "email_agent",
            "calendar_agent": "calendar_agent",
            "writer_agent": "writer_agent",
            "FINISH": END,
        },
    )

    # All specialized agents return control back to supervisor for dynamic coordination
    workflow.add_edge("research_agent", "supervisor")
    workflow.add_edge("analysis_agent", "supervisor")
    workflow.add_edge("coding_agent", "supervisor")
    workflow.add_edge("database_agent", "supervisor")
    workflow.add_edge("document_agent", "supervisor")
    workflow.add_edge("email_agent", "supervisor")
    workflow.add_edge("calendar_agent", "supervisor")

    # Writer Agent hands off draft to Validator Agent
    workflow.add_edge("writer_agent", "validator_agent")

    # Validator Agent evaluates draft: PASS -> END; FAIL -> writer_agent (revision) or END (max retries)
    workflow.add_conditional_edges(
        "validator_agent",
        route_validator,
        {
            "writer_agent": "writer_agent",
            "FINISH": END,
        },
    )

    active_checkpointer = checkpointer if checkpointer is not None else get_checkpointer()
    logger.info("Compiling Multi-Agent LangGraph workflow with SQLite checkpointer...")
    compiled = workflow.compile(checkpointer=active_checkpointer)
    return CheckpointedGraphWrapper(compiled)


# Singleton compiled graph instance for application execution
app_graph = create_workflow()
