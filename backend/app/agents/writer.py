"""
Writer Agent module.

Specialized agent responsible for:
- Synthesizing findings, code, database query results, and schedules into a cohesive final response.
- Producing structured technical reports or concise summaries for action-oriented outputs.
- Incorporating Validator Agent feedback during revision cycles.
- Populating final_report, draft, and response in the workflow state.
"""

import logging
import re
from typing import Any, Dict

from app.agents.base import BaseAgent
from app.graph.state import GraphState
from app.services import llm_service

logger = logging.getLogger(__name__)

WRITER_SYSTEM_PROMPT = """You are an elite AI technical educator, senior software architect, and master explainer.
Your responsibility is to synthesize research, analysis, code, and technical data into an exceptionally thorough, pedagogical, and crystal-clear explanation—matching the depth, clarity, and quality of GPT-4 and senior engineering documentation.

CORE PRINCIPLES:
1. ABSOLUTELY NO BUREAUCRATIC HEADERS:
   - NEVER start with or include metadata blocks such as:
     * "Document ID: ..."
     * "Version: ..."
     * "Author: ..."
     * "Date: ..."
     * "Audience: ..."
     * "Scope: ..."
     * "Status: Draft / For review"
   - Do NOT introduce yourself as "Writer Agent" or reference internal pipeline/graph agents.

2. STRICT RULE ON CODE GENERATION (CRITICAL):
   - When asked to explain a concept or topic (e.g. "Explain XYZ", "What is XYZ", "How does XYZ work", "Guide to XYZ", "Tell me about XYZ"):
     * DO NOT provide code implementations, programming scripts, or code blocks.
     * Focus purely on deep conceptual understanding, architectural breakdowns, text/ASCII workflows, primitives, and comparison tables.
   - ONLY provide code when the user EXPLICITLY asks for code (e.g., "write code", "give code", "show code", "implement in python", "code example", "write a script", "code snippet").

3. THOROUGH, IN-DEPTH, AND PEDAGOGICAL STRUCTURE (When explaining concepts, technologies, or architectures):
   Whenever asked to explain a concept or topic, deliver a comprehensive, multi-section guide:
   - **Engaging Overview & Intuitive Analogy**:
     * Give a crisp definition in plain language.
     * Use a powerful, relatable real-world analogy (e.g., "like USB for AI hardware", "like a postal routing system").
   - **Why Do We Need It? (The Core Problem)**:
     * Explain the pain points "Without It" (fragmented APIs, custom brittle point-to-point glue code, maintainability issues).
     * Contrast with "With It" (standardization, reusability, interoperability).
   - **Detailed Architecture & Components**:
     * Break down every architectural role clearly (e.g. Host, Client, Server).
     * Include ASCII diagrams or structured text flows illustrating how components connect.
   - **Core Building Blocks & Primitives**:
     * Detail the key primitives (e.g. Tools, Resources, Prompts) with practical examples.
     * Provide comparison tables contrasting their purposes, triggers, and side-effects.
   - **Step-by-Step Workflow**:
     * Walk through a concrete scenario from start to finish (User query -> LLM reasoning -> Tool selection -> Client dispatch -> Server execution -> Result formatting).
   - **Protocol & Communication Details**:
     * Detail the transport protocols (e.g. JSON-RPC 2.0, STDIO, Streamable HTTP/SSE).
     * Show sample request/response JSON payloads.
   - **Comparative Analysis & Key Distinctions**:
     * Compare against adjacent technologies (e.g., MCP vs REST vs Function Calling; MCP vs LangChain vs LangGraph) using clear tables.
   - **Advanced Concepts & Security**:
     * Cover advanced features (e.g. sampling, capability negotiation, elicitation).
     * Detail critical security practices (least privilege, input validation, authentication, human approval).
   - **Real-World Use Cases, Interview Revision & Next Steps**:
     * Practical production applications.
     * Core questions to test understanding and recommended project roadmap.

4. FOR EXPLICIT CODE REQUESTS ONLY:
   - When the user explicitly requests code or implementation: present complete, runnable, clean code with syntax highlighting, clear comments, and error handling.

5. CONVERSATIONAL MEMORY & CONTEXT RETENTION:
   - Always remember and maintain continuity with previous conversation turns in the chat history.
   - If the user refers to prior topics, asks follow-up questions, or asks what was discussed earlier, answer accurately using the conversation context.

6. FORMATTING EXCELLENCE:
   - Use clean Markdown with numbered headings (## 1., ## 2.), bullet points, comparison tables, and syntax-highlighted code blocks (only when code was explicitly requested).
   - When images or diagrams are available in research data, embed them using `![Caption](image_url)` followed by `*Source: [Title](source_url)*`.
   - Ensure all explanations are comprehensive and never cut short."""


def strip_unwanted_metadata(text: str) -> str:
    """
    Remove bureaucratic document metadata blocks (e.g., Document ID, Version, Author,
    Audience, Scope, Status) from the output.
    """
    if not text:
        return text

    lines = text.split("\n")
    cleaned_lines = []
    metadata_pattern = re.compile(
        r"^(?:\*{0,2})(?:Document ID|Doc ID|Version|Author|Date|Audience|Scope|Status|Classification)(?:\*{0,2})\s*:\s*.*$",
        re.IGNORECASE,
    )

    in_top_section = True
    for line in lines:
        stripped = line.strip()
        if in_top_section:
            if metadata_pattern.match(stripped):
                continue
            if stripped == "---" and len(cleaned_lines) <= 2:
                continue
            if stripped and not stripped.startswith("#"):
                in_top_section = False
        cleaned_lines.append(line)

    result = "\n".join(cleaned_lines).strip()
    result = re.sub(
        r"^(#+\s+.*?)\s*[-–—]\s*(?:Technical\s+)?Report",
        r"\1",
        result,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    return result


class WriterAgent(BaseAgent):
    name = "writer"
    description = "Synthesizes multi-agent findings, code, and data into a polished final report."
    role = "Synthesis, Technical Writing & Response Formatting"
    allowed_tools = []

    def run(self, state: GraphState) -> Dict[str, Any]:
        user_query = state.get("user_query", "")
        research_data = state.get("research_data")
        analysis_data = state.get("analysis_data")
        database_results = state.get("database_results")
        code_results = state.get("code_results")
        document_results = state.get("document_results")
        email_results = state.get("email_results")
        calendar_results = state.get("calendar_results")
        rag_context = state.get("rag_context")
        validation_feedback = state.get("validation_feedback")
        retry_count = state.get("retry_count", 0)
        agent_logs = list(state.get("agent_logs") or [])
        agent_history = list(state.get("agent_history") or [])

        is_revision = bool(validation_feedback and len(validation_feedback.strip()) > 0)
        logger.info(
            "[Writer Agent] %s for query: '%s' (Revision cycle: %d)",
            "Revising response based on validator feedback" if is_revision else "Synthesizing response",
            user_query,
            retry_count,
        )

        # Assemble available inputs from specialists
        sections = []
        if research_data:
            sections.append(f"--- RESEARCH FINDINGS ---\n{research_data}")
        if rag_context:
            sections.append(f"--- RETRIEVED RAG CONTEXT ---\n{rag_context[:2000]}")
        if analysis_data:
            sections.append(f"--- COMPARATIVE ANALYSIS ---\n{analysis_data}")
        if database_results:
            sections.append(f"--- DATABASE RESULTS ---\n{database_results.get('summary', '')}")
        if code_results:
            sections.append(f"--- CODE ARTIFACTS ---\n{code_results.get('response', '')}")
        if email_results:
            sections.append(f"--- EMAIL RESULTS ---\n{email_results.get('content', '')}")
        if calendar_results:
            sections.append(f"--- CALENDAR RESULTS ---\n{calendar_results.get('content', '')}")
        if document_results:
            sections.append(f"--- DOCUMENT DRAFT ---\n{document_results.get('document_content', '')}")

        feedback_section = (
            f"\n\n--- VALIDATION FEEDBACK FOR MANDATORY REVISION ---\n"
            f"The Validator Agent identified issues with your previous draft:\n{validation_feedback}\n"
            f"You MUST revise your previous response to resolve every identified issue."
            if is_revision
            else ""
        )

        # Assemble conversation history context for full thread continuity
        messages = list(state.get("messages") or [])
        history_blocks = []
        prior_messages = messages[:-1] if messages and messages[-1].get("content") == user_query else messages
        for m in prior_messages:
            if not isinstance(m, dict):
                continue
            role = m.get("role", "user").capitalize()
            content = str(m.get("content", "")).strip()
            if content:
                clean_content = content[:800] + "..." if len(content) > 800 else content
                history_blocks.append(f"{role}: {clean_content}")

        history_section = ""
        if history_blocks:
            history_section = "--- PREVIOUS CONVERSATION CONTEXT (REMEMBER ALL CHATS) ---\n" + "\n\n".join(history_blocks[-6:]) + "\n\n"

        # Check if the query is an in-depth explanation request or a direct/conversational question
        is_in_depth_request = any(k in user_query.lower() for k in [
            "explain", "deep dive", "guide to", "how does", "comprehensive", "in detail", "in-depth", "teach me", "break down"
        ]) and not any(k in user_query.lower() for k in [
            "brief", "short", "in 2 sentences", "in one sentence", "my name", "what did i", "what was", "who was", "summarize in"
        ])

        if is_in_depth_request:
            tone_guidance = (
                "IN-DEPTH EXPLANATION: The user requested a detailed breakdown. "
                "Provide a thorough, well-structured explanation using clear sections, analogies, architecture, and diagrams."
            )
        else:
            tone_guidance = (
                "DIRECT / CONVERSATIONAL ANSWER: The user is asking a direct question or conversational follow-up. "
                "Provide a direct, natural, concise, and helpful answer answering their exact question using the conversation context. "
                "Do NOT output an unsolicited multi-section textbook or giant guide."
            )

        # Check if the user explicitly requested code
        explicit_code_requested = any(k in user_query.lower() for k in [
            "write code", "give code", "show code", "provide code", "implement",
            "python code", "code snippet", "code example", "script for", "in python",
            "in c++", "in java", "in javascript", "in typescript", "in rust", "write a function",
            "code implementation"
        ]) and not any(k in user_query.lower() for k in ["without code", "dont give code", "dont write code", "no code"])

        if explicit_code_requested:
            code_guidance = "CODE INSTRUCTION: The user explicitly requested code. Provide clean, well-commented, runnable code."
        else:
            code_guidance = (
                "CRITICAL CODE RULE: The user did NOT ask for code. "
                "DO NOT provide any code implementations, programming scripts, or code blocks. "
                "Explain everything using concepts, architecture, workflows, diagrams, and comparison tables only."
            )

        combined_input = "\n\n".join(sections) if sections else "No specialist outputs provided."

        user_prompt = (
            f"{history_section}"
            f"Original User Request:\n{user_query}\n\n"
            f"{combined_input}"
            f"{feedback_section}\n\n"
            f"{tone_guidance}\n"
            f"{code_guidance}\n\n"
            "Please generate the authoritative response addressing the user's request with full conversation memory."
        )

        final_report = llm_service.run_agent_with_tools(
            system_prompt=WRITER_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            tools=None,
            temperature=0.3 if is_revision else 0.4,
            max_tokens=3500,
        )
        final_report = strip_unwanted_metadata(final_report)

        agent_logs.append(
            {
                "agent": self.name,
                "action": "Compiled final structured response",
                "is_revision": is_revision,
                "retry_cycle": retry_count,
            }
        )

        agent_history.append({"agent": self.name, "status": "completed"})

        return {
            "current_agent": self.name,
            "draft": final_report,
            "final_report": final_report,
            "response": final_report,
            "final_response": final_report,
            "agent_logs": agent_logs,
            "agent_history": agent_history,
        }


# Singleton callable node for LangGraph
writer_agent_node = WriterAgent()
