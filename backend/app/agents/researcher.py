"""
Research Agent module.

Specialized agent responsible for:
- Gathering factual, verifiable, and up-to-date information.
- Querying internal knowledge base via RAG retrieval (VectorStore).
- Calling external MCP tools (web_search, calculator).
- Returning structured research findings with verifiable sources and confidence levels.
"""

import json
import logging
from typing import Any, Dict, List

from app.agents.base import BaseAgent
from app.graph.state import GraphState
from app.rag.pipeline import get_rag_pipeline
from app.services import llm_service

logger = logging.getLogger(__name__)

RESEARCHER_SYSTEM_PROMPT = """You are the Research Agent in a multi-agent task automation system.
Your responsibility is to gather factual, verifiable, in-depth, and up-to-date information addressing the user request.

Available Information Sources:
1. Internal Knowledge Base (RAG): If authentic internal documents are provided, cite sources accurately using [Document: filename, Page: X]. Do NOT fabricate sources.
2. Web Search Tool: Use web_search to find authoritative technical documentation, official specifications, architecture standards, and code patterns.
3. Image Search Tool: Use search_images to find diagrams, illustrations, architecture charts, and authentic images from Wikimedia Commons, Wikipedia, and media repositories whenever the user asks for images, visuals, diagrams, illustrations, or pictures. Always include the resulting image URLs, titles, and source platform links!
4. Calculator Tool: Use calculator for any mathematical operations or numeric calculations.

Output Instructions:
Conduct targeted searches as needed, then return a deep, structured technical briefing:
- Core definitions, origins, and purpose (why this exists, problems solved)
- Architectural details, components, and communication protocols/transports
- Core primitives, building blocks, and code/API structures
- Verified sources and references
- Confidence level (high, medium, or low) based on source reliability
Do NOT provide speculative opinions—strictly present verifiable evidence."""


class ResearchAgent(BaseAgent):
    name = "research"
    description = "Conducts web research, image/diagram search, and internal RAG knowledge base retrieval to gather factual data."
    role = "Information Retrieval & Fact Verification"
    allowed_tools = ["web_search", "calculator", "search_images"]

    def run(self, state: GraphState) -> Dict[str, Any]:
        user_query = state.get("user_query", "")
        plan = state.get("plan") or []
        agent_logs = list(state.get("agent_logs") or [])
        agent_history = list(state.get("agent_history") or [])

        logger.info("[Research Agent] Executing research for query: '%s'", user_query)

        # 1. Query Internal Knowledge Base via RAG Pipeline
        rag_pipeline = get_rag_pipeline()
        rag_retrieval = rag_pipeline.retrieve(user_query)
        retrieved_chunks = rag_retrieval.get("chunks", [])
        rag_context = rag_retrieval.get("context", "")

        # 2. Scoped MCP Tools
        scoped_tools = self.get_scoped_tools()

        plan_context = "\n".join(plan) if plan else "Gather all relevant factual findings."
        rag_prompt_section = (
            f"\n\n--- INTERNAL KNOWLEDGE BASE CONTEXT (RAG) ---\n{rag_context}"
            if rag_context
            else "\n\n--- INTERNAL KNOWLEDGE BASE (RAG) ---\nNo matching internal documents found."
        )

        wants_images = any(
            w in user_query.lower()
            for w in ["image", "images", "iamge", "iamges", "diagram", "diagrams", "photo", "photos", "picture", "pictures", "visual", "visuals", "chart", "charts", "illustration", "illustrations"]
        )
        image_instruction = (
            "\n\nNOTE: The user explicitly requested images, diagrams, or visual aids. "
            "You MUST invoke the `search_images` tool to find relevant diagrams, charts, and illustrations, "
            "and include the image URLs and source platform links in your output."
            if wants_images
            else ""
        )

        user_prompt = (
            f"User Query: {user_query}\n\n"
            f"Supervisor Plan:\n{plan_context}"
            f"{rag_prompt_section}"
            f"{image_instruction}\n\n"
            "Gather factual research using internal document context and web_search/search_images/calculator tools. "
            "Cite all sources accurately and return clear factual findings."
        )


        research_text = llm_service.run_agent_with_tools(
            system_prompt=RESEARCHER_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            tools=scoped_tools,
            temperature=0.2,
            max_tool_rounds=2,
            max_tokens=2200,
        )

        # Compile structured research object
        sources = []
        for chunk in retrieved_chunks:
            meta = chunk.get("metadata", {})
            sources.append(f"{meta.get('filename')} (Page {meta.get('page')})")

        structured_results = {
            "summary": research_text,
            "sources": sources,
            "rag_chunks_found": len(retrieved_chunks),
            "confidence": "high" if sources else "medium",
        }

        agent_logs.append(
            {
                "agent": self.name,
                "action": "Conducted research via RAG and web search",
                "sources_count": len(sources),
                "preview": research_text[:150] + "...",
            }
        )

        agent_history.append({"agent": self.name, "status": "completed"})

        return {
            "current_agent": self.name,
            "research_data": research_text,
            "research_results": structured_results,
            "rag_context": rag_context if retrieved_chunks else None,
            "retrieved_documents": retrieved_chunks if retrieved_chunks else None,
            "agent_logs": agent_logs,
            "agent_history": agent_history,
        }


# Singleton callable node for LangGraph
research_agent_node = ResearchAgent()
