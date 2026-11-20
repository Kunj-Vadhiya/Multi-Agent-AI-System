"""
Main FastAPI application entry point for Multi-Agent AI Task Automation System (Version 6 + Version 7).

Features:
- REST endpoints for system status and health check.
- Thread-based persistent Multi-Agent LangGraph workflow execution with checkpointing.
- Self-validation loop with Validator Agent and retry protection.
- Document ingestion and retrieval-augmented generation (RAG) knowledge base API.
"""

import logging
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root directory is in sys.path for robust module resolution
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import json
from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.graph.state import GraphState
from app.graph.workflow import app_graph
from app.rag.pipeline import get_rag_pipeline
from app.rag.vector_store import get_vector_store
from app.schemas import (
    ChatRequest,
    ChatResponse,
    DocumentUploadResponse,
    HealthResponse,
    RootResponse,
)
from app.services.checkpoint_service import (
    delete_thread_data,
    get_thread_state,
    get_thread_title,
    list_all_threads,
    set_thread_title,
)
from app.services.topic_service import generate_topic_title


class ThreadCreateRequest(BaseModel):
    title: Optional[str] = None


class ThreadUpdateRequest(BaseModel):
    title: str = Field(..., min_length=1)


# Configure logging for step-by-step execution tracking
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="7.0.0",
    description=(
        "Version 6 + Version 7: Multi-Agent AI Task Automation System coordinated by a Supervisor Agent "
        "with specialized Research, Analysis, Writer, and Validator Agents. Features persistent SQLite "
        "workflow checkpointing, conversational thread memory, automated validation with retry loops, "
        "and a local RAG Knowledge Base combining document retrieval with dynamic MCP tools."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(
    "/",
    response_model=RootResponse,
    status_code=status.HTTP_200_OK,
    summary="Root Status",
    tags=["System"],
)
def read_root() -> RootResponse:
    """
    Root endpoint indicating the API service is alive and accessible.
    """
    return RootResponse(message="Multi-Agent AI Task Automation API is running")


@app.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health Check",
    tags=["System"],
)
def health_check() -> HealthResponse:
    """
    Health check endpoint for monitoring system availability.
    """
    return HealthResponse(status="healthy")


@app.post(
    "/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute Thread-Based Multi-Agent Workflow via LangGraph",
    tags=["Chat"],
)
def chat(request: ChatRequest) -> ChatResponse:
    """
    Accept a user message, process it through the Multi-Agent LangGraph workflow:
    User -> Supervisor -> Research Agent (RAG + MCP) -> Analysis Agent -> Writer Agent -> Validator Agent -> Response.

    Maintains thread-isolated state and conversation history across turns using SQLite checkpoints.
    """
    thread_id = (request.thread_id or "").strip() or f"thread_{uuid.uuid4().hex[:8]}"
    logger.info("[API] Request received on thread '%s': '%s'", thread_id, request.message)

    config = {"configurable": {"thread_id": thread_id}}

    # Check for existing conversation history from persistent checkpoints
    prior_state: Dict[str, Any] = {}
    existing_messages: List[Dict[str, Any]] = []
    try:
        current_snapshot = app_graph.get_state(config)
        if current_snapshot and current_snapshot.values:
            prior_state = current_snapshot.values
            existing_messages = list(prior_state.get("messages") or [])
            logger.info(
                "[Thread Memory] Resuming conversation for thread '%s' with %d previous messages.",
                thread_id,
                len(existing_messages),
            )
    except Exception as err:
        logger.warning("[Thread Memory] Could not load prior snapshot for thread '%s': %s", thread_id, err)

    # Human-in-the-loop confirmation logic
    pending_action = prior_state.get("pending_action")
    prev_confirmation_required = prior_state.get("confirmation_required", False)
    confirmation_status = prior_state.get("confirmation_status", "NONE")

    msg_lower = request.message.lower().strip()
    is_confirm_true = request.confirm_action is True or msg_lower in (
        "yes", "confirm", "approve", "approved", "proceed", "send", "send it", "yes, approve action", "send email", "send this email", "yes send", "yes send it", "go ahead"
    )
    is_confirm_false = request.confirm_action is False or msg_lower in ("no", "reject", "cancel", "deny", "rejected")

    if prev_confirmation_required and pending_action:
        if is_confirm_true:
            confirmation_status = "APPROVED"
            logger.info("[API] User APPROVED pending action '%s' on thread '%s'", pending_action.get("action"), thread_id)
        elif is_confirm_false:
            confirmation_status = "REJECTED"
            logger.info("[API] User REJECTED pending action '%s' on thread '%s'", pending_action.get("action"), thread_id)

    is_resuming_confirmation = confirmation_status in ("APPROVED", "REJECTED") and bool(pending_action)

    # Append current user turn to conversation history
    if request.messages is not None:
        updated_messages = list(request.messages)
        if not updated_messages or updated_messages[-1].get("role") != "user" or updated_messages[-1].get("content") != request.message:
            updated_messages.append({"role": "user", "content": request.message})
    else:
        updated_messages = list(existing_messages)
        updated_messages.append({"role": "user", "content": request.message})


    # Prepare turn input state
    turn_state: GraphState = {
        "thread_id": thread_id,
        "user_query": request.message,
        "messages": updated_messages,
        "plan": prior_state.get("plan") if is_resuming_confirmation else None,
        "tasks": prior_state.get("tasks") if is_resuming_confirmation else None,
        "current_task": "Supervisor dynamic coordination" if is_resuming_confirmation else "Supervisor planning",
        "current_agent": "supervisor",
        "next_agent": None,
        "execution_plan": prior_state.get("execution_plan") if is_resuming_confirmation else None,
        "agent_history": list(prior_state.get("agent_history", [])) if is_resuming_confirmation else [],
        "research_data": prior_state.get("research_data") if is_resuming_confirmation else None,
        "research_results": prior_state.get("research_results") if is_resuming_confirmation else None,
        "analysis_data": prior_state.get("analysis_data") if is_resuming_confirmation else None,
        "analysis": prior_state.get("analysis") if is_resuming_confirmation else None,
        "code_results": prior_state.get("code_results") if is_resuming_confirmation else None,
        "database_results": prior_state.get("database_results") if is_resuming_confirmation else None,
        "document_results": prior_state.get("document_results") if is_resuming_confirmation else None,
        "email_results": prior_state.get("email_results") if is_resuming_confirmation else None,
        "calendar_results": prior_state.get("calendar_results") if is_resuming_confirmation else None,
        "pending_action": pending_action if is_resuming_confirmation and confirmation_status != "REJECTED" else None,
        "confirmation_required": False,
        "confirmation_status": confirmation_status if is_resuming_confirmation else "NONE",
        "draft": prior_state.get("draft") if is_resuming_confirmation else None,
        "rag_context": prior_state.get("rag_context") if is_resuming_confirmation else None,
        "retrieved_documents": prior_state.get("retrieved_documents") if is_resuming_confirmation else None,
        "tool_results": prior_state.get("tool_results") if is_resuming_confirmation else None,
        "validation_result": None,
        "validation_feedback": None,
        "final_report": None,
        "response": "",
        "final_response": "",
        "workflow_status": "in_progress",
        "retry_count": 0,
        "iteration_count": 0,
        "agent_logs": list(prior_state.get("agent_logs", [])) if is_resuming_confirmation else [],
    }

    try:
        logger.info("[LangGraph] Starting workflow execution for thread '%s'", thread_id)
        final_state = app_graph.invoke(turn_state, config=config)
    except Exception as err:
        logger.error("[LangGraph] Workflow execution error on thread '%s': %s", thread_id, err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The multi-agent workflow encountered an unexpected execution error.",
        ) from err

    final_resp_text = final_state.get("response") or final_state.get("final_report") or ""
    workflow_stat = final_state.get("workflow_status", "completed")

    # Update conversation history with assistant response
    if final_resp_text:
        updated_messages.append({"role": "assistant", "content": final_resp_text})
        try:
            app_graph.update_state(config, {"messages": updated_messages})
        except Exception:
            pass

    # Ensure thread has an informative topic-based title summarizing the conversation
    current_title = get_thread_title(thread_id)
    if not current_title or current_title in ("New Conversation", "New Chat") or current_title.startswith("Chat thread_") or current_title.endswith("..."):
        topic_title = generate_topic_title(request.message, final_resp_text)
        if topic_title:
            set_thread_title(thread_id, topic_title)
            current_title = topic_title

    logger.info(
        "[LangGraph] Workflow completed for thread '%s' (topic: '%s') with status '%s'.",
        thread_id,
        current_title,
        workflow_stat,
    )

    return ChatResponse(
        thread_id=thread_id,
        thread_title=current_title,
        response=final_resp_text,
        status=workflow_stat,
        plan=final_state.get("plan"),
        current_agent=final_state.get("current_agent"),
        agent_history=final_state.get("agent_history"),
        code_results=final_state.get("code_results"),
        database_results=final_state.get("database_results"),
        document_results=final_state.get("document_results"),
        email_results=final_state.get("email_results"),
        calendar_results=final_state.get("calendar_results"),
        pending_action=final_state.get("pending_action"),
        confirmation_required=final_state.get("confirmation_required", False),
        research_data=final_state.get("research_data"),
        analysis_data=final_state.get("analysis_data"),
        rag_context=final_state.get("rag_context"),
        retrieved_documents=final_state.get("retrieved_documents"),
        validation_result=final_state.get("validation_result"),
        agent_logs=final_state.get("agent_logs"),
    )


@app.post(
    "/documents/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload and Ingest Document into RAG Knowledge Base",
    tags=["Knowledge Base"],
)
async def upload_document(file: UploadFile = File(...)) -> DocumentUploadResponse:
    """
    Ingest a document into the RAG Knowledge Base:
    Upload document -> Extract text -> Chunk text -> Generate embeddings -> Store in Vector DB.

    Supports: .pdf, .txt, .md
    """
    original_filename = file.filename or "uploaded_document"
    ext = Path(original_filename).suffix.lower()

    supported_extensions = {".pdf", ".txt", ".text", ".md", ".markdown"}
    if ext not in supported_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. Supported formats: {', '.join(sorted(supported_extensions))}",
        )

    # Save uploaded file to data/documents/
    save_dir = settings.DOCUMENTS_DIR
    save_dir.mkdir(parents=True, exist_ok=True)
    destination_path = save_dir / f"{uuid.uuid4().hex[:8]}_{original_filename}"

    try:
        content = await file.read()
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty.",
            )
        destination_path.write_bytes(content)
        logger.info("Saved uploaded file '%s' to '%s'", original_filename, destination_path)
    except HTTPException:
        raise
    except Exception as err:
        logger.error("Failed to save uploaded file '%s': %s", original_filename, err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save uploaded file.",
        ) from err

    # Ingest document via RAG pipeline
    try:
        rag_pipeline = get_rag_pipeline()
        ingest_result = rag_pipeline.ingest_file(
            file_path=destination_path,
            filename=original_filename,
        )
    except Exception as err:
        logger.error("Error during ingestion of '%s': %s", original_filename, err)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to process document: {str(err)}",
        ) from err

    return DocumentUploadResponse(
        document_id=ingest_result["document_id"],
        filename=ingest_result["filename"],
        chunks_created=ingest_result["chunks_created"],
        status=ingest_result["status"],
    )


@app.get(
    "/documents",
    status_code=status.HTTP_200_OK,
    summary="List Ingested Documents in Knowledge Base",
    tags=["Knowledge Base"],
)
def list_documents() -> Dict[str, Any]:
    """
    List all documents currently indexed in the RAG vector store.
    """
    vector_store = get_vector_store()
    docs = vector_store.list_documents()
    total_chunks = vector_store.count()
    return {
        "total_documents": len(docs),
        "total_chunks": total_chunks,
        "documents": docs,
    }


@app.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete Ingested Document from Knowledge Base",
    tags=["Knowledge Base"],
)
def delete_document(document_id: str) -> Dict[str, Any]:
    """
    Delete a document and its chunks from the RAG vector store.
    """
    vector_store = get_vector_store()
    deleted_chunks = vector_store.delete_document(document_id)
    return {
        "status": "deleted",
        "document_id": document_id,
        "deleted_chunks": deleted_chunks,
    }


@app.get(
    "/threads",
    status_code=status.HTTP_200_OK,
    summary="List All Conversation Threads",
    tags=["Threads"],
)
def get_threads() -> Dict[str, Any]:
    """
    Retrieve all persistent conversation threads with metadata and message counts.
    """
    threads = list_all_threads()
    return {"threads": threads}


@app.post(
    "/threads",
    status_code=status.HTTP_201_CREATED,
    summary="Create New Conversation Thread",
    tags=["Threads"],
)
def create_thread(body: Optional[ThreadCreateRequest] = None) -> Dict[str, Any]:
    """
    Create a new thread ID with optional custom title.
    """
    thread_id = f"thread_{uuid.uuid4().hex[:8]}"
    title = (body.title if body and body.title else "").strip() or "New Conversation"
    set_thread_title(thread_id, title)
    return {"thread_id": thread_id, "title": title}


@app.get(
    "/threads/{thread_id}",
    status_code=status.HTTP_200_OK,
    summary="Get Conversation Thread Details and Messages",
    tags=["Threads"],
)
def get_thread(thread_id: str) -> Dict[str, Any]:
    """
    Fetch all messages and execution state snapshot for a specific thread.
    """
    state = get_thread_state(thread_id)
    if not state:
        return {
            "thread_id": thread_id,
            "title": "New Conversation",
            "messages": [],
            "status": "not_found",
        }

    return {
        "thread_id": thread_id,
        "messages": state.get("messages", []),
        "plan": state.get("plan"),
        "current_agent": state.get("current_agent"),
        "agent_history": state.get("agent_history", []),
        "retrieved_documents": state.get("retrieved_documents", []),
        "code_results": state.get("code_results"),
        "database_results": state.get("database_results"),
        "document_results": state.get("document_results"),
        "email_results": state.get("email_results"),
        "calendar_results": state.get("calendar_results"),
        "pending_action": state.get("pending_action"),
        "confirmation_required": state.get("confirmation_required", False),
        "validation_result": state.get("validation_result"),
        "workflow_status": state.get("workflow_status", "completed"),
        "agent_logs": state.get("agent_logs", []),
    }


@app.patch(
    "/threads/{thread_id}",
    status_code=status.HTTP_200_OK,
    summary="Update Conversation Thread Title",
    tags=["Threads"],
)
def update_thread(thread_id: str, body: ThreadUpdateRequest) -> Dict[str, Any]:
    """
    Rename a conversation thread.
    """
    clean_title = body.title.strip()
    set_thread_title(thread_id, clean_title)
    return {"status": "updated", "thread_id": thread_id, "title": clean_title}


@app.delete(
    "/threads/{thread_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete Conversation Thread",
    tags=["Threads"],
)
def delete_thread(thread_id: str) -> Dict[str, Any]:
    """
    Delete a conversation thread and its checkpoints.
    """
    delete_thread_data(thread_id)
    return {"status": "deleted", "thread_id": thread_id}


@app.post(
    "/chat/stream",
    summary="Stream Multi-Agent Workflow Execution via Server-Sent Events",
    tags=["Chat"],
)
async def chat_stream(request: ChatRequest):
    """
    Stream real-time agent lifecycle and execution events using Server-Sent Events (SSE).
    Yields live agent status updates (running, completed), plan, citations, and final response.
    """
    thread_id = (request.thread_id or "").strip() or f"thread_{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}

    def event_stream():
        # Check prior state
        prior_state: Dict[str, Any] = {}
        existing_messages: List[Dict[str, Any]] = []
        try:
            snapshot = app_graph.get_state(config)
            if snapshot and snapshot.values:
                prior_state = snapshot.values
                existing_messages = list(prior_state.get("messages") or [])
        except Exception as err:
            logger.warning("[Stream] Prior snapshot error: %s", err)

        pending_action = prior_state.get("pending_action")
        prev_confirmation_required = prior_state.get("confirmation_required", False)
        confirmation_status = prior_state.get("confirmation_status", "NONE")

        msg_lower = request.message.lower().strip()
        is_confirm_true = request.confirm_action is True or msg_lower in (
            "yes", "confirm", "approve", "approved", "proceed", "send", "send it", "yes, approve action", "send email", "send this email", "yes send", "yes send it", "go ahead"
        )
        is_confirm_false = request.confirm_action is False or msg_lower in ("no", "reject", "cancel", "deny", "rejected")

        if prev_confirmation_required and pending_action:
            if is_confirm_true:
                confirmation_status = "APPROVED"
            elif is_confirm_false:
                confirmation_status = "REJECTED"

        is_resuming_confirmation = confirmation_status in ("APPROVED", "REJECTED") and bool(pending_action)

        if request.messages is not None:
            updated_messages = list(request.messages)
            if not updated_messages or updated_messages[-1].get("role") != "user" or updated_messages[-1].get("content") != request.message:
                updated_messages.append({"role": "user", "content": request.message})
        else:
            updated_messages = list(existing_messages)
            updated_messages.append({"role": "user", "content": request.message})


        turn_state: GraphState = {
            "thread_id": thread_id,
            "user_query": request.message,
            "messages": updated_messages,
            "plan": prior_state.get("plan") if is_resuming_confirmation else None,
            "tasks": prior_state.get("tasks") if is_resuming_confirmation else None,
            "current_task": "Supervisor dynamic coordination" if is_resuming_confirmation else "Supervisor planning",
            "current_agent": "supervisor",
            "next_agent": None,
            "execution_plan": prior_state.get("execution_plan") if is_resuming_confirmation else None,
            "agent_history": list(prior_state.get("agent_history", [])) if is_resuming_confirmation else [],
            "research_data": prior_state.get("research_data") if is_resuming_confirmation else None,
            "research_results": prior_state.get("research_results") if is_resuming_confirmation else None,
            "analysis_data": prior_state.get("analysis_data") if is_resuming_confirmation else None,
            "analysis": prior_state.get("analysis") if is_resuming_confirmation else None,
            "code_results": prior_state.get("code_results") if is_resuming_confirmation else None,
            "database_results": prior_state.get("database_results") if is_resuming_confirmation else None,
            "document_results": prior_state.get("document_results") if is_resuming_confirmation else None,
            "email_results": prior_state.get("email_results") if is_resuming_confirmation else None,
            "calendar_results": prior_state.get("calendar_results") if is_resuming_confirmation else None,
            "pending_action": pending_action if is_resuming_confirmation and confirmation_status != "REJECTED" else None,
            "confirmation_required": False,
            "confirmation_status": confirmation_status if is_resuming_confirmation else "NONE",
            "draft": prior_state.get("draft") if is_resuming_confirmation else None,
            "rag_context": prior_state.get("rag_context") if is_resuming_confirmation else None,
            "retrieved_documents": prior_state.get("retrieved_documents") if is_resuming_confirmation else None,
            "tool_results": prior_state.get("tool_results") if is_resuming_confirmation else None,
            "validation_result": None,
            "validation_feedback": None,
            "final_report": None,
            "response": "",
            "final_response": "",
            "workflow_status": "in_progress",
            "retry_count": 0,
            "iteration_count": 0,
            "agent_logs": list(prior_state.get("agent_logs", [])) if is_resuming_confirmation else [],
        }

        # Yield initial connected event
        yield f"data: {json.dumps({'event': 'started', 'thread_id': thread_id})}\n\n"

        try:
            final_state = dict(turn_state)
            for chunk in app_graph.stream(turn_state, config=config):
                for node_name, node_update in chunk.items():
                    if isinstance(node_update, dict):
                        final_state.update(node_update)
                    progress_payload = {
                        "event": "agent_start",
                        "agent": node_name,
                        "current_agent": node_name,
                        "plan": final_state.get("plan"),
                        "agent_history": final_state.get("agent_history", []),
                    }
                    yield f"data: {json.dumps(progress_payload)}\n\n"

            final_resp_text = final_state.get("response") or final_state.get("final_report") or ""
            workflow_stat = final_state.get("workflow_status", "completed")


            if final_resp_text:
                updated_messages.append({"role": "assistant", "content": final_resp_text})
                try:
                    app_graph.update_state(config, {"messages": updated_messages})
                except Exception:
                    pass

            # Ensure thread has an informative topic-based title summarizing the conversation
            current_title = get_thread_title(thread_id)
            if not current_title or current_title in ("New Conversation", "New Chat") or current_title.startswith("Chat thread_") or current_title.endswith("..."):
                topic_title = generate_topic_title(request.message, final_resp_text)
                if topic_title:
                    set_thread_title(thread_id, topic_title)
                    current_title = topic_title

            # Yield full completion payload
            done_payload = {
                "event": "done",
                "thread_id": thread_id,
                "thread_title": current_title,
                "response": final_resp_text,
                "status": workflow_stat,
                "plan": final_state.get("plan"),
                "current_agent": final_state.get("current_agent"),
                "agent_history": final_state.get("agent_history"),
                "code_results": final_state.get("code_results"),
                "database_results": final_state.get("database_results"),
                "document_results": final_state.get("document_results"),
                "email_results": final_state.get("email_results"),
                "calendar_results": final_state.get("calendar_results"),
                "pending_action": final_state.get("pending_action"),
                "confirmation_required": final_state.get("confirmation_required", False),
                "research_data": final_state.get("research_data"),
                "analysis_data": final_state.get("analysis_data"),
                "retrieved_documents": final_state.get("retrieved_documents"),
                "validation_result": final_state.get("validation_result"),
                "agent_logs": final_state.get("agent_logs"),
            }
            yield f"data: {json.dumps(done_payload)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as err:
            logger.error("[Stream] Workflow error: %s", err)
            err_payload = {"event": "error", "detail": "An execution error occurred in the multi-agent workflow."}
            yield f"data: {json.dumps(err_payload)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
        },
    )

