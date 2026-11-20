"""
LangGraph state definition for Multi-Agent Task Automation System.
Defines the shared data schema passed between the Supervisor, specialized agents,
and the Validator, persisted across conversation threads via LangGraph Checkpointing.
"""

from typing import Any, Dict, List, Optional, TypedDict


class GraphState(TypedDict, total=False):
    """
    Represents the shared state of the Multi-Agent LangGraph workflow.

    Attributes:
        thread_id (Optional[str]): Unique thread/conversation identifier for persistent memory.
        user_query (str): The current user query or instruction for this turn.
        messages (Optional[List[Dict[str, Any]]]): Full conversation message history across turns.
        tasks (Optional[List[str]]): Decomposed subtasks for workflow execution.
        plan (Optional[List[str]]): Alias for tasks.
        current_task (Optional[str]): Current task description being worked on.
        current_agent (Optional[str]): Currently executing agent node identifier.
        next_agent (Optional[str]): Routing target.
        agent_history (Optional[List[Dict[str, Any]]]): Sequence of executed agents with statuses.
        execution_plan (Optional[Dict[str, Any]]): Structured plan containing intent, required agents, dependencies.

        # Specialized Agent Results
        research_results (Optional[Any]): Structured research findings from Research Agent.
        research_data (Optional[str]): Factual research text.
        analysis (Optional[str]): Comparative analysis and trade-offs produced by Analysis Agent.
        analysis_data (Optional[str]): Analysis text alias.
        code_results (Optional[Dict[str, Any]]): Output from Coding Agent (code, explanation, lint/execution).
        database_results (Optional[Dict[str, Any]]): Output from Database Agent (schema, query, rows).
        document_results (Optional[Dict[str, Any]]): Output from Document Agent (generated docs, summaries).
        email_results (Optional[Dict[str, Any]]): Output from Email Agent (search, drafts, send status).
        calendar_results (Optional[Dict[str, Any]]): Output from Calendar Agent (events, availability, bookings).

        # RAG and Tools
        rag_context (Optional[str]): Retrieved RAG document context.
        retrieved_documents (Optional[List[Dict[str, Any]]]): Retrieved knowledge base chunk metadata.
        tool_results (Optional[List[Dict[str, Any]]]): Intermediate outputs from tool calls.

        # Generation and Validation
        draft (Optional[str]): Initial draft awaiting validation.
        validation_result (Optional[Dict[str, Any]]): Structured validation result from Validator Agent.
        validation_feedback (Optional[str]): Targeted feedback from Validator if revision is needed.
        final_report (Optional[str]): Final report synthesized by Writer Agent.
        final_response (Optional[str]): Final response alias.
        response (str): Final user-facing response.

        # Status and Retries
        workflow_status (str): Workflow status ('in_progress', 'completed', 'max_retries_exceeded', 'awaiting_confirmation').
        retry_count (int): Counter tracking validation/regeneration attempts.
        iteration_count (int): Loop counter to prevent infinite supervisor cycles.
        agent_logs (Optional[List[Dict[str, Any]]]): Audit log tracing all agent actions.

        # Human-in-the-Loop Confirmation
        pending_action (Optional[Dict[str, Any]]): Details of external side effect awaiting user approval.
        confirmation_required (bool): Whether an action requires explicit user confirmation.
        confirmation_status (str): Confirmation status ('NONE', 'PENDING', 'APPROVED', 'REJECTED').
    """

    thread_id: Optional[str]
    user_query: str
    messages: Optional[List[Dict[str, Any]]]
    tasks: Optional[List[str]]
    plan: Optional[List[str]]
    current_task: Optional[str]
    current_agent: Optional[str]
    next_agent: Optional[str]
    agent_history: Optional[List[Dict[str, Any]]]
    execution_plan: Optional[Dict[str, Any]]

    # Specialized Agent Results
    research_results: Optional[Any]
    research_data: Optional[str]
    analysis: Optional[str]
    analysis_data: Optional[str]
    code_results: Optional[Dict[str, Any]]
    database_results: Optional[Dict[str, Any]]
    document_results: Optional[Dict[str, Any]]
    email_results: Optional[Dict[str, Any]]
    calendar_results: Optional[Dict[str, Any]]

    # RAG & Tools
    rag_context: Optional[str]
    retrieved_documents: Optional[List[Dict[str, Any]]]
    tool_results: Optional[List[Dict[str, Any]]]

    # Generation & Validation
    draft: Optional[str]
    validation_result: Optional[Dict[str, Any]]
    validation_feedback: Optional[str]
    final_report: Optional[str]
    final_response: Optional[str]
    response: str

    # Status & Retries
    workflow_status: str
    retry_count: int
    iteration_count: int
    agent_logs: Optional[List[Dict[str, Any]]]

    # Human-in-the-Loop / Confirmation
    pending_action: Optional[Dict[str, Any]]
    confirmation_required: bool
    confirmation_status: str
