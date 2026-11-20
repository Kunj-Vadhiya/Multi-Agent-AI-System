"""
Document Agent module.

Specialized agent responsible for:
- Creating, structuring, formatting, and transforming comprehensive documents and technical reports.
- Exporting generated documents (Markdown, TXT, PDF).
- Reading, summarizing, and synthesizing structured information from the RAG Knowledge Base.
- Populating document_results and draft in workflow state.
"""

import logging
import uuid
from pathlib import Path
from typing import Any, Dict

from app.agents.base import BaseAgent
from app.config import settings
from app.graph.state import GraphState
from app.rag.pipeline import get_rag_pipeline
from app.services import llm_service

logger = logging.getLogger(__name__)

DOCUMENT_SYSTEM_PROMPT = """You are the Document Agent in a multi-agent task automation system.
Your responsibility is to author, structure, format, and synthesize comprehensive, high-quality documentation, articles, and guides.

Formatting & Design Standards:
- Generate clear, publication-ready Markdown with hierarchical headings (#, ##, ###), tables, bullet lists, and callouts.
- NO METADATA HEADERS: Do NOT include bureaucratic headers like "Document ID", "Version: 1.0", "Author: Document Agent", "Date", "Audience", "Scope", or "Status" unless explicitly asked for a metadata template. Start directly with an engaging, informative title followed by the content.
- Include structured sections:
  1. Clear Title (# Topic)
  2. Overview & Core Concept
  3. Deep Technical Sections (incorporating factual research, architecture, schemas, and code)
  4. Practical Examples, Applications, and Conclusions
- Ensure accurate attribution: incorporate citations for any RAG knowledge base context provided."""


class DocumentAgent(BaseAgent):
    name = "document"
    description = "Formats, generates, summarizes, and exports structured technical reports, documentation, and files."
    role = "Document Generation, Transformation & Formatting"
    allowed_tools = []  # Operates directly on synthesized state and exports files

    def run(self, state: GraphState) -> Dict[str, Any]:
        user_query = state.get("user_query", "")
        research_data = state.get("research_data")
        analysis_data = state.get("analysis_data")
        database_results = state.get("database_results")
        code_results = state.get("code_results")
        rag_context = state.get("rag_context")
        agent_logs = list(state.get("agent_logs") or [])
        agent_history = list(state.get("agent_history") or [])

        logger.info("[Document Agent] Authoring document for request: '%s'", user_query)

        # Assemble inputs from prior agents
        sources_context = []
        if research_data:
            sources_context.append(f"--- RESEARCH FINDINGS ---\n{research_data}")
        if rag_context:
            sources_context.append(f"--- KNOWLEDGE BASE (RAG) ---\n{rag_context[:2000]}")
        if analysis_data:
            sources_context.append(f"--- COMPARATIVE ANALYSIS ---\n{analysis_data}")
        if database_results:
            sources_context.append(f"--- DATABASE FINDINGS ---\n{database_results.get('summary', '')}")
        if code_results:
            sources_context.append(f"--- SOURCE CODE ---\n{code_results.get('response', '')}")

        full_context = "\n\n".join(sources_context) if sources_context else "No prior agent data provided."

        user_prompt = (
            f"Original Request:\n{user_query}\n\n"
            f"Provided Content & Data:\n{full_context}\n\n"
            "Please generate the complete, authoritative, structured technical report or document "
            "adhering to professional Markdown formatting."
        )

        doc_content = llm_service.run_agent_with_tools(
            system_prompt=DOCUMENT_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            tools=None,
            temperature=0.3,
            max_tokens=1800,
        )
        from app.agents.writer import strip_unwanted_metadata
        doc_content = strip_unwanted_metadata(doc_content)

        # Save document artifact to data/generated_reports/ (isolated from user uploaded documents)
        doc_filename = f"report_{uuid.uuid4().hex[:8]}.md"
        save_path = settings.DATA_DIR / "generated_reports" / doc_filename
        try:
            save_path.parent.mkdir(parents=True, exist_ok=True)
            save_path.write_text(doc_content, encoding="utf-8")
            saved_file = str(save_path)
        except Exception as err:
            logger.warning("[Document Agent] Could not save document artifact: %s", err)
            saved_file = None

        doc_results_payload = {
            "document_content": doc_content,
            "filename": doc_filename,
            "saved_path": saved_file,
            "format": "markdown",
            "status": "completed",
        }

        agent_logs.append(
            {
                "agent": self.name,
                "action": f"Generated structured document ({len(doc_content)} chars)",
                "file": doc_filename,
            }
        )

        agent_history.append({"agent": self.name, "status": "completed"})

        return {
            "current_agent": self.name,
            "document_results": doc_results_payload,
            "draft": doc_content,
            "final_report": doc_content,
            "response": doc_content,
            "agent_logs": agent_logs,
            "agent_history": agent_history,
        }


# Singleton callable node for LangGraph
document_agent_node = DocumentAgent()
