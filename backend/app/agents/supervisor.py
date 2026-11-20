"""
Supervisor Agent module.

Coordinates the multi-agent task automation system:
- Dynamically analyzes user queries and formulates multi-agent execution plans.
- Selects from available specialized agents:
  Research, Analysis, Coding, Database, Document, Email, Calendar, Writer, Validator.
- Determines task dependencies and execution order.
- Detects operations requiring Human-in-the-Loop Confirmation and pauses when needed.
- Evaluates intermediate agent outputs and routes through state handoffs.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from app.agents.registry import AVAILABLE_AGENTS, get_agent_descriptions
from app.graph.state import GraphState
from app.services import llm_service

logger = logging.getLogger(__name__)

SUPERVISOR_PLANNER_PROMPT = f"""You are the Supervisor Agent of an advanced multi-agent system.
Your responsibility is to analyze the user's request and construct a dynamic execution plan.

Available Specialized Agents:
{get_agent_descriptions()}
- 'writer': Synthesizes outputs into a polished final report when needed.
- 'validator': Audits the final draft/output before completion.

Instructions:
1. Identify the user's intent.
2. Select the optimal sequence of specialized agents to accomplish the goal.
3. Define dependencies between agents (e.g. analysis requires research or database).
4. Detect if any destructive or external write action (sending email, booking meeting, database write) requires confirmation.

Respond strictly with a JSON object following this schema:
{{
  "intent": "short_intent_slug",
  "agents": ["agent1", "agent2", ...],
  "dependencies": {{"agent2": ["agent1"]}},
  "requires_confirmation": false,
  "plan": [
    "1. Descriptive step for agent 1",
    "2. Descriptive step for agent 2"
  ]
}}
"""

CONVERSATIONAL_CAPABILITIES_RESPONSE = (
    "I am your Multi-Agent AI Task Automation Assistant. I dynamically coordinate specialized agents to assist you with:\n\n"
    "• 🔍 **Research Agent**: Live web searches and RAG knowledge retrieval from your uploaded documents.\n"
    "• 📊 **Analysis Agent**: Quantitative data analysis, trend evaluation, and decision trade-offs.\n"
    "• 💻 **Coding Agent**: Python script execution, bug fixing, and API architecture.\n"
    "• 🗄️ **Database Agent**: Inspecting schemas, running SQL queries, and analyzing database tables.\n"
    "• 📄 **Document Agent**: Generating structured Markdown and PDF reports.\n"
    "• ✉️ **Email Agent**: Reading, searching, drafting, and organizing emails.\n"
    "• 📅 **Calendar Agent**: Checking schedules and coordinating calendar events.\n"
    "• ✍️ **Writer Agent**: Synthesizing polished, comprehensive final reports.\n"
    "• 🛡️ **Validator Agent**: Quality auditing and factual verification.\n\n"
    "What would you like to work on today?"
)


def get_conversational_response(user_query: str) -> Optional[str]:
    """
    Fast-path detection and response for common conversational inquiries,
    greetings, pleasantries, system identity questions, and casual remarks.
    Bypasses the heavy multi-agent pipeline to respond in under 5ms.
    """
    if not user_query or not user_query.strip():
        return "Hello! How can I help you today?"

    cleaned = user_query.strip().lower()
    # Normalize punctuation and extra spaces
    normalized = re.sub(r"[^\w\s]", " ", cleaned)
    normalized = " ".join(normalized.split())

    if not normalized:
        return "Hello! How can I help you today?"

    words = normalized.split()

    # If the message contains explicit actionable task instructions, it should not be treated as a pure conversational greeting
    task_action_words = {
        "research", "analyze", "analysis", "compare", "database", "sql", "postgres",
        "sqlite", "table", "schema", "code", "python", "script", "endpoint", "fastapi",
        "email", "mail", "inbox", "calendar", "meeting", "schedule", "document", "pdf",
        "report", "calculate", "bug", "debug", "query", "select", "insert", "delete"
    }

    # If task action words are present, check if it's more than just a passing greeting
    if any(w in task_action_words for w in words):
        # Exception: "what can you do with database" or "how do you work" is asking about capabilities
        if not any(phrase in normalized for phrase in ["what can you do", "who are you", "what are your capabilities", "how do you work", "help"]):
            return None

    # 1. 'wassup' / 'what's up' / 'whats up' / 'sup' / 'wazzup' (supporting repeated chars like wassuuup)
    collapsed_norm = re.sub(r"(.)\1+", r"\1", normalized)
    if (
        any(phrase in normalized for phrase in ["wassup", "what s up", "whats up", "what up", "sup bro", "yo wassup", "wazup", "wazzup"])
        or any(phrase in collapsed_norm for phrase in ["wasup", "what s up", "whats up", "what up", "sup bro", "yo wasup", "wazup"])
        or normalized in ("sup", "wassup", "wazup")
        or collapsed_norm in ("sup", "wasup", "wazup")
    ):
        return "Not much! Just here and ready to help you out. What task or project are we tackling today?"

    # 2. Identity and System Capabilities
    identity_queries = [
        "who are you", "what are you", "what can you do", "what can you help me with",
        "what are your capabilities", "tell me about yourself", "introduce yourself",
        "what agents do you have", "how does this work", "how do you work", "what do you do",
        "help me", "help"
    ]
    if any(iq == normalized or normalized.startswith(iq) or f" {iq} " in f" {normalized} " for iq in identity_queries):
        return CONVERSATIONAL_CAPABILITIES_RESPONSE

    # 3. Well-being inquiries: 'how are you', 'how are you doing', 'how's it going', etc.
    wellbeing_queries = [
        "how are you", "how are you doing", "how is it going", "how s it going",
        "how are things", "how do you do", "how is everything", "how s everything"
    ]
    if any(wq in normalized for wq in wellbeing_queries):
        return "I'm doing great, thank you for asking! I'm fully ready to help you with research, code, databases, emails, or analysis. What can I do for you today?"

    # 4. Time of day greetings
    if "good morning" in normalized:
        return "Good morning! Hope you have a wonderful and productive day ahead. How can I assist you today?"
    if "good afternoon" in normalized:
        return "Good afternoon! How can I assist you with your tasks today?"
    if "good evening" in normalized:
        return "Good evening! How can I help you tonight?"
    if "good night" in normalized:
        return "Good night! Rest well, and feel free to reach out whenever you need assistance."

    # 5. Core greetings: 'hey', 'heyy', 'hi', 'hiii', 'hello', 'hellooo', 'yo', 'howdy', etc.
    def is_greeting_word(word: str) -> bool:
        collapsed = re.sub(r"(.)\1+", r"\1", word)
        if collapsed in {"hey", "hi", "helo", "hello", "yo", "sup", "hlo", "hlw", "howdy", "hiya", "heya", "hola", "greetings", "wasup", "wazup"}:
            return True
        return bool(re.match(r"^(hey+|hi+|hello+|helo+|yo+|sup+|hlo+|hlw+|howdy|heya+|hiya+|hola+|greetings?|wa+s+u+p+|wa+z+u+p+)$", word, re.I))

    # Check if first word is a greeting and message is short (<= 6 words) or greeting combo
    if words and is_greeting_word(words[0]):
        remaining_words = [
            w for w in words[1:]
            if not is_greeting_word(w)
            and w not in {"there", "friend", "buddy", "bro", "man", "assistant", "agent", "bot", "all", "team", "everyone"}
        ]
        # If no other meaningful task words, or only casual words
        if not remaining_words or len(remaining_words) <= 2:
            return "Hello! How can I help you today? Feel free to ask a question or let me know what task you'd like to work on."

    # Also check if query is purely greetings like "hey hey", "heyy there", "hello there", "hi friend"
    if all(is_greeting_word(w) or w in {"there", "friend", "buddy", "bro", "man", "assistant", "bot"} for w in words):
        return "Hello! How can I help you today? Feel free to ask a question or let me know what task you'd like to work on."

    # 6. Gratitude
    gratitude_phrases = ["thanks", "thank you", "thx", "appreciate it", "thank you so much", "thanks a lot", "many thanks"]
    if any(gp == normalized or normalized.startswith(gp) or normalized.endswith(gp) for gp in gratitude_phrases) and len(words) <= 6:
        return "You're very welcome! Let me know if there's anything else I can do for you."

    # 7. Farewells
    farewell_phrases = ["bye", "goodbye", "see you", "cya", "take care", "have a nice day", "have a good day", "talk to you later"]
    if any(fp in normalized for fp in farewell_phrases) and len(words) <= 6:
        return "Goodbye! Have a great day ahead, and feel free to reach out whenever you need assistance."

    # 8. Acknowledgments
    ack_phrases = {"ok", "okay", "cool", "great", "awesome", "nice", "sounds good", "got it", "understood", "perfect", "alright", "yep", "yeah"}
    if normalized in ack_phrases or (len(words) <= 3 and any(w in ack_phrases for w in words) and not any(w in task_action_words for w in words)):
        return "Sounds good! Let me know whenever you're ready to start a task."

    return None


def plan_dynamic_workflow(user_query: str) -> Dict[str, Any]:
    """
    Formulate a dynamic multi-agent execution plan using LLM structured generation
    with resilient rule-based heuristic fallback.
    """
    # Fast-path check for conversational queries (greetings, wassup, identity, etc.)
    quick_resp = get_conversational_response(user_query)
    if quick_resp:
        return {
            "intent": "conversational",
            "agents": [],
            "dependencies": {},
            "requires_confirmation": False,
            "plan": ["Direct conversational response"],
            "direct_response": quick_resp,
        }

    q_lower = user_query.lower()

    # Rule-based heuristics for common patterns
    heuristic_plan: Optional[Dict[str, Any]] = None

    if any(k in q_lower for k in ["interview", "find emails", "search emails"]) and any(k in q_lower for k in ["schedule", "calendar"]):
        heuristic_plan = {
            "intent": "email_to_calendar",
            "agents": ["email", "analysis", "calendar"],
            "dependencies": {"analysis": ["email"], "calendar": ["analysis"]},
            "requires_confirmation": True,
            "plan": [
                "1. Email Agent searches for interview details",
                "2. Analysis Agent extracts dates and times",
                "3. Calendar Agent coordinates interview scheduling",
            ],
        }
    elif any(k in q_lower for k in ["calendar", "meeting", "schedule", "events"]) and any(k in q_lower for k in ["email", "draft", "mail"]):
        requires_send = any(k in q_lower for k in ["send", "email me the summary", "email me"])
        heuristic_plan = {
            "intent": "schedule_and_email",
            "agents": ["calendar", "analysis", "email"],
            "dependencies": {"analysis": ["calendar"], "email": ["analysis"]},
            "requires_confirmation": requires_send,
            "plan": [
                "1. Calendar Agent checks meetings and availability",
                "2. Analysis Agent summarizes schedule data",
                "3. Email Agent drafts/sends meeting summary",
            ],
        }
    elif any(k in q_lower for k in ["fastapi", "code", "python", "endpoint", "function", "bug", "script"]) and any(k in q_lower for k in ["database", "sql", "postgres", "sqlite", "table", "schema"]):
        heuristic_plan = {
            "intent": "code_and_database",
            "agents": ["coding", "database", "coding"],
            "dependencies": {"database": ["coding"]},
            "requires_confirmation": False,
            "plan": [
                "1. Coding Agent drafts initial API architecture",
                "2. Database Agent inspects schema and queries",
                "3. Coding Agent finalizes integrated code",
            ],
        }
    elif any(k in q_lower for k in ["sql", "database", "table", "customers", "orders", "query"]):
        heuristic_plan = {
            "intent": "database_analysis",
            "agents": ["database", "analysis", "writer"],
            "dependencies": {"analysis": ["database"], "writer": ["analysis"]},
            "requires_confirmation": False,
            "plan": [
                "1. Database Agent inspects tables and executes queries",
                "2. Analysis Agent interprets records and trends",
                "3. Writer Agent compiles clear findings report",
            ],
        }
    elif any(k in q_lower for k in [
        "recent email", "latest email", "read email", "check email", "search email",
        "my email", "my emails", "recent mail", "latest mail", "inbox", "mails section",
        "mail section", "emails section", "check inbox", "my inbox", "recent messages"
    ]) or (any(k in q_lower for k in ["email", "emails", "mail", "inbox"]) and any(k in q_lower for k in ["recent", "latest", "what", "whats", "what's", "show", "read", "check", "find", "search", "list", "get", "received", "says"])):
        heuristic_plan = {
            "intent": "read_emails",
            "agents": ["email"],
            "dependencies": {},
            "requires_confirmation": False,
            "plan": [
                "1. Email Agent searches and fetches latest emails from inbox"
            ],
        }
    elif any(k in q_lower for k in ["send an email", "send email", "draft an email", "draft email", "write an email", "email to", "send a mail", "draft a mail", "compose email"]):
        is_send = any(k in q_lower for k in ["send an email", "send email", "send a mail", "send this email"])
        heuristic_plan = {
            "intent": "email_management",
            "agents": ["email"],
            "dependencies": {},
            "requires_confirmation": is_send,
            "plan": [
                "1. Email Agent prepares draft or requests confirmation to send email"
            ],
        }
    elif any(k in q_lower for k in ["schedule a meeting", "create event", "calendar event", "book a meeting", "schedule meeting", "find free time", "check my schedule"]):
        is_create = any(k in q_lower for k in ["schedule a meeting", "create event", "book a meeting", "schedule meeting"])
        heuristic_plan = {
            "intent": "calendar_management",
            "agents": ["calendar"],
            "dependencies": {},
            "requires_confirmation": is_create,
            "plan": [
                "1. Calendar Agent manages calendar event and schedule"
            ],
        }
    elif any(k in q_lower for k in ["report", "technical report", "document", "pdf", "markdown"]) and any(k in q_lower for k in ["research", "rag", "find", "explain"]):
        heuristic_plan = {
            "intent": "research_and_document",
            "agents": ["research", "analysis", "document"],
            "dependencies": {"analysis": ["research"], "document": ["analysis"]},
            "requires_confirmation": False,
            "plan": [
                "1. Research Agent gathers factual data from web and RAG",
                "2. Analysis Agent evaluates patterns and trade-offs",
                "3. Document Agent formats and exports publication report",
            ],
        }
    elif any(k in q_lower for k in ["image", "images", "iamge", "iamges", "diagram", "diagrams", "photo", "picture", "visual", "illustration", "chart"]):
        heuristic_plan = {
            "intent": "visual_research_and_synthesis",
            "agents": ["research", "writer"],
            "dependencies": {"writer": ["research"]},
            "requires_confirmation": False,
            "plan": [
                "1. Research Agent gathers factual data and searches for diagrams, illustrations, and authentic images",
                "2. Writer Agent synthesizes comprehensive explanation complete with visual media and platform links",
            ],
        }
    elif any(k in q_lower for k in [
        "write code", "generate code", "give code", "show code", "implement code",
        "write a python", "write python", "write in c", "write c", "in python",
        "in java", "in cpp", "in c++", "in javascript", "in rust", "in go",
        "in typescript", "debug", "fix bug", "refactor code", "write a class",
        "write a function", "write a script", "leetcode", "palindrome script"
    ]):
        heuristic_plan = {
            "intent": "code_generation",
            "agents": ["coding"],
            "dependencies": {},
            "requires_confirmation": False,
            "plan": [
                "1. Coding Agent generates, reviews, and validates the requested code implementation"
            ],
        }
    elif any(k in q_lower for k in ["calculate", "evaluate", "math", "sqrt", "% of"]) or re.search(r"\d+\s*[\+\-\*\/\^%]\s*\d+", q_lower):
        heuristic_plan = {
            "intent": "calculation",
            "agents": ["research"],
            "dependencies": {},
            "requires_confirmation": False,
            "plan": [
                "1. Research Agent performs calculation using tool execution"
            ],
        }
    elif any(k in q_lower for k in ["explain", "deep dive", "guide to", "how it works", "tell me about", "teach me"]):
        needs_live_search = any(k in q_lower for k in ["latest", "recent", "news", "today", "current", "search", "lookup"])
        heuristic_plan = {
            "intent": "in_depth_explanation",
            "agents": ["research", "writer"] if needs_live_search else ["writer"],
            "dependencies": {"writer": ["research"]} if needs_live_search else {},
            "requires_confirmation": False,
            "plan": [
                "1. Research Agent gathers live factual documentation" if needs_live_search else "1. Writer Agent compiles comprehensive, deep technical explanation",
                "2. Writer Agent compiles comprehensive explanation" if needs_live_search else "2. Final quality check",
            ][:2 if needs_live_search else 1],
        }
    elif any(k in q_lower for k in [
        "tell me a joke", "tell a joke", "write a poem", "what is", "why is", "how does", "summarize",
        "who was", "what did", "repeat that", "what was", "my name", "what do i", "earlier", "previous",
        "you mentioned", "tell me more"
    ]):
        heuristic_plan = {
            "intent": "direct_answer",
            "agents": ["writer"],
            "dependencies": {},
            "requires_confirmation": False,
            "plan": [
                "1. Writer Agent generates direct clear response using conversation context"
            ],
        }

    if heuristic_plan:
        return heuristic_plan

    # Attempt LLM dynamic planning
    try:
        user_prompt = f"User Request: {user_query}\n\nGenerate the dynamic multi-agent execution plan."
        raw_result = llm_service.run_structured_json(
            system_prompt=SUPERVISOR_PLANNER_PROMPT,
            user_prompt=user_prompt,
            temperature=0.1,
            max_tokens=600,
        )

        agents = list(raw_result.get("agents") or [])
        valid_agents = [a for a in agents if a in AVAILABLE_AGENTS or a in ("writer", "validator")]
        if valid_agents:
            return {
                "intent": raw_result.get("intent", "general_task"),
                "agents": valid_agents,
                "dependencies": raw_result.get("dependencies", {}),
                "requires_confirmation": bool(raw_result.get("requires_confirmation", False)),
                "plan": raw_result.get("plan", [f"Execute task via {', '.join(valid_agents)}"]),
            }
    except Exception as err:
        logger.warning("[Supervisor Planner] LLM dynamic planning fallback (%s)", err)

    if heuristic_plan:
        return heuristic_plan

    # Default fallback: research -> writer (fast 2-agent execution)
    return {
        "intent": "general_research",
        "agents": ["research", "writer"],
        "dependencies": {"writer": ["research"]},
        "requires_confirmation": False,
        "plan": [
            "1. Gather factual data and background documentation",
            "2. Synthesize findings into structured technical response",
        ],
    }


def supervisor_node(state: GraphState) -> Dict[str, Any]:
    """
    Supervisor node assessing workflow state, tracking execution history,
    and dynamically routing to the next appropriate specialist.
    """
    iteration = state.get("iteration_count", 0) + 1
    user_query = state.get("user_query", "")
    agent_logs = list(state.get("agent_logs") or [])
    agent_history = list(state.get("agent_history") or [])
    execution_plan = state.get("execution_plan")
    final_report = state.get("final_report") or state.get("response")
    validation_result = state.get("validation_result")
    confirmation_required = state.get("confirmation_required", False)
    confirmation_status = state.get("confirmation_status", "NONE")

    logger.info(
        "Supervisor evaluating cycle %d | Query: '%s' | Executed agents: %s | Confirmation required: %s",
        iteration,
        user_query[:60],
        [h.get("agent") for h in agent_history],
        confirmation_required,
    )

    # 0. Fast-Path for Conversational Inquiries (Cycle 1)
    if iteration == 1 and not execution_plan:
        quick_resp = get_conversational_response(user_query)
        if quick_resp:
            logger.info("[Supervisor Fast-Path] Instant response for conversational query: '%s'", user_query)
            agent_logs.append(
                {
                    "agent": "supervisor",
                    "action": "Immediate direct response provided for conversational inquiry.",
                }
            )
            return {
                "current_agent": "supervisor",
                "current_task": "Conversational response",
                "next_agent": "FINISH",
                "response": quick_resp,
                "final_response": quick_resp,
                "final_report": quick_resp,
                "plan": ["Direct conversational response"],
                "tasks": ["Direct conversational response"],
                "execution_plan": {
                    "intent": "conversational",
                    "agents": [],
                    "dependencies": {},
                    "requires_confirmation": False,
                    "plan": ["Direct conversational response"],
                    "direct_response": quick_resp,
                },
                "workflow_status": "completed",
                "iteration_count": iteration,
                "agent_logs": agent_logs,
            }

    # 1. Human-in-the-Loop Confirmation Pause
    if confirmation_required and confirmation_status not in ("APPROVED", "REJECTED"):
        logger.info("[Supervisor] External side effect requires confirmation. Pausing workflow.")
        agent_logs.append(
            {
                "agent": "supervisor",
                "action": "Workflow paused awaiting explicit user confirmation.",
            }
        )
        return {
            "current_agent": "supervisor",
            "next_agent": "FINISH",
            "workflow_status": "awaiting_confirmation",
            "iteration_count": iteration,
            "agent_logs": agent_logs,
        }

    # 2. Safety loop limit
    if iteration >= 10:
        logger.warning("[Supervisor] Reached safety iteration limit (%d). Routing to FINISH.", iteration)
        return {
            "current_agent": "supervisor",
            "next_agent": "FINISH",
            "workflow_status": "completed",
            "iteration_count": iteration,
            "agent_logs": agent_logs,
        }

    # 3. Dynamic Plan Formulation (Cycle 1)
    if not execution_plan:
        plan_dict = plan_dynamic_workflow(user_query)
        scheduled_agents = plan_dict.get("agents", [])

        # If conversational or no specialized agents required, complete immediately
        if not scheduled_agents or plan_dict.get("intent") == "conversational":
            quick_resp = (
                plan_dict.get("direct_response")
                or state.get("response")
                or state.get("final_report")
                or "Hello! How can I assist you today?"
            )
            agent_logs.append(
                {
                    "agent": "supervisor",
                    "action": f"Direct response provided for intent '{plan_dict.get('intent', 'conversational')}'",
                    "plan": plan_dict.get("plan", ["Direct response"]),
                }
            )
            return {
                "current_agent": "supervisor",
                "current_task": "Conversational response",
                "next_agent": "FINISH",
                "response": quick_resp,
                "final_response": quick_resp,
                "final_report": quick_resp,
                "plan": plan_dict.get("plan", ["Direct conversational response"]),
                "tasks": plan_dict.get("plan", ["Direct conversational response"]),
                "execution_plan": plan_dict,
                "workflow_status": "completed",
                "iteration_count": iteration,
                "agent_logs": agent_logs,
            }

        first_agent = scheduled_agents[0]

        logger.info(
            "[Supervisor] Formulated dynamic plan: %s | Intent: %s | First agent: %s",
            plan_dict["plan"],
            plan_dict["intent"],
            first_agent,
        )

        agent_logs.append(
            {
                "agent": "supervisor",
                "action": f"Formulated dynamic plan with intent '{plan_dict['intent']}'",
                "plan": plan_dict["plan"],
                "agents": scheduled_agents,
            }
        )

        return {
            "current_agent": "supervisor",
            "current_task": plan_dict["plan"][0] if plan_dict.get("plan") else "Initial task",
            "execution_plan": plan_dict,
            "plan": plan_dict["plan"],
            "tasks": plan_dict["plan"],
            "next_agent": first_agent,
            "iteration_count": iteration,
            "workflow_status": "in_progress",
            "agent_logs": agent_logs,
        }

    # 4. Determine next pending agent in dynamic plan
    scheduled_agents = execution_plan.get("agents", [])
    if not scheduled_agents or execution_plan.get("intent") == "conversational":
        quick_resp = (
            execution_plan.get("direct_response")
            or state.get("response")
            or state.get("final_report")
            or "Hello! How can I assist you today?"
        )
        return {
            "current_agent": "supervisor",
            "current_task": "Workflow complete",
            "next_agent": "FINISH",
            "response": quick_resp,
            "final_response": quick_resp,
            "final_report": quick_resp,
            "workflow_status": "completed",
            "iteration_count": iteration,
            "agent_logs": agent_logs,
        }

    executed_agent_names = [h.get("agent") for h in agent_history if h.get("status") == "completed"]

    next_agent_to_run = None
    for idx, agent_name in enumerate(scheduled_agents):
        # Allow multi-occurrence agents (e.g. coding -> database -> coding) by counting occurrences
        scheduled_occurrences = scheduled_agents[: idx + 1].count(agent_name)
        executed_occurrences = executed_agent_names.count(agent_name)
        if executed_occurrences < scheduled_occurrences:
            next_agent_to_run = agent_name
            break

    if next_agent_to_run:
        logger.info("[Supervisor] Routing to next scheduled specialist: '%s'", next_agent_to_run)
        step_desc = f"Execute {next_agent_to_run}"
        plan_steps = execution_plan.get("plan", [])
        if len(executed_agent_names) < len(plan_steps):
            step_desc = plan_steps[len(executed_agent_names)]

        return {
            "current_agent": "supervisor",
            "current_task": step_desc,
            "next_agent": next_agent_to_run,
            "iteration_count": iteration,
            "agent_logs": agent_logs,
        }

    # 5. All scheduled specialists complete: route to writer/validator
    if not final_report:
        last_draft = (
            state.get("draft")
            or (state.get("code_results") or {}).get("response")
            or (state.get("database_results") or {}).get("summary")
            or (state.get("calendar_results") or {}).get("content")
            or (state.get("email_results") or {}).get("content")
            or (state.get("document_results") or {}).get("document_content")
        )
        if last_draft and "writer" not in scheduled_agents and "document" not in scheduled_agents:
            logger.info("[Supervisor] Specialist output complete. Finalizing response directly without extra synthesis cycle.")
            agent_logs.append({
                "agent": "supervisor",
                "action": "Specialist completed requested output directly without re-synthesis",
            })
            return {
                "current_agent": "supervisor",
                "current_task": "Workflow complete",
                "next_agent": "FINISH",
                "response": last_draft,
                "final_response": last_draft,
                "final_report": last_draft,
                "workflow_status": "completed",
                "iteration_count": iteration,
                "agent_logs": agent_logs,
            }

        logger.info("[Supervisor] Specialists complete. Routing to Writer to finalize response.")
        return {
            "current_agent": "supervisor",
            "current_task": "Synthesize final response",
            "next_agent": "writer",
            "iteration_count": iteration,
            "agent_logs": agent_logs,
        }

    # Workflow is complete
    logger.info("[Supervisor] All tasks and reports validated. Terminating to FINISH.")
    return {
        "current_agent": "supervisor",
        "current_task": "Workflow complete",
        "next_agent": "FINISH",
        "workflow_status": "completed",
        "iteration_count": iteration,
        "agent_logs": agent_logs,
    }
