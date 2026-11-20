"""
Email Agent module.

Specialized agent responsible for:
- Reading, searching, and summarizing emails.
- Drafting professional email communications (safe, automatic).
- Handling sending operations with strict Human-in-the-Loop Confirmation:
  - DRAFT is generated automatically.
  - SEND is held until explicit user approval (confirmation_required).
- Populating email_results in workflow state.
"""

import logging
import re
from typing import Any, Dict

from app.agents.base import BaseAgent
from app.graph.state import GraphState
from app.services import llm_service
from app.tools.email_tools import draft_email, send_email

logger = logging.getLogger(__name__)

EMAIL_SYSTEM_PROMPT = """You are the Email Agent in a multi-agent task automation system.
Your responsibility is searching, reading, drafting, and managing email communications.

Tools Available:
- search_emails: Search inbox or folders for keywords, senders, or subjects. Call search_emails(query='recent', folder='inbox') to inspect the latest received emails.
- get_email: Retrieve full content and metadata of a specific email by ID.
- draft_email: Save a proposed email into drafts.
- send_email: Dispatch an email. Note: sending requires confirmation!

Guidelines:
1. When the user asks what recent emails say, or to check, list, or read their received inbox:
   - Call search_emails(query='recent', folder='inbox') to fetch the latest emails.
   - Summarize the email clearly: Sender, Subject, Received Time/Date, and the key message content.
   - Do NOT try to dispatch or send an email when the user is only asking to read or inspect their emails!
2. When the user explicitly asks to compose or send an email:
   - Format cleanly with To, Subject, and Body."""


class EmailAgent(BaseAgent):
    name = "email"
    description = "Searches, reads, drafts, and coordinates email communications with authorization safety."
    role = "Email Management & Communication"
    allowed_tools = ["search_emails", "get_email", "draft_email", "send_email"]

    def run(self, state: GraphState) -> Dict[str, Any]:
        user_query = state.get("user_query", "")
        confirmation_status = state.get("confirmation_status", "NONE")
        pending_action = state.get("pending_action")
        analysis_data = state.get("analysis_data")
        calendar_results = state.get("calendar_results")
        agent_logs = list(state.get("agent_logs") or [])
        agent_history = list(state.get("agent_history") or [])

        logger.info("[Email Agent] Processing request: '%s' (Confirmation: %s)", user_query, confirmation_status)

        scoped_tools = self.get_scoped_tools()

        # Handle resume after user confirmation
        if confirmation_status == "APPROVED" and pending_action and pending_action.get("action") == "send_email":
            details = pending_action.get("details", {})
            recip = details.get("recipient") or pending_action.get("recipient", "")
            subj = details.get("subject") or pending_action.get("subject", "")
            body = details.get("body") or pending_action.get("body", "")
            res = send_email(
                recipient=recip,
                subject=subj,
                body=body,
                confirmed=True,
            )
            response_msg = res.get("message") or f"Email has been confirmed and sent to {recip}."
            agent_logs.append({"agent": self.name, "action": "Sent confirmed email", "details": res})
            agent_history.append({"agent": self.name, "status": "completed"})

            return {
                "current_agent": self.name,
                "email_results": {"status": "sent", "details": res},
                "pending_action": None,
                "confirmation_required": False,
                "confirmation_status": "NONE",
                "draft": response_msg,
                "final_report": response_msg,
                "response": response_msg,
                "workflow_status": "completed",
                "agent_logs": agent_logs,
                "agent_history": agent_history,
            }

        # Build context if prior agents supplied information (e.g. Calendar summary)
        context_blocks = []
        if analysis_data:
            context_blocks.append(f"Analysis Summary to Email:\n{analysis_data}")
        if calendar_results:
            context_blocks.append(f"Schedule Data:\n{calendar_results}")

        additional_context = "\n\n".join(context_blocks)

        # Detect if user is asking to read, inspect, or search inbox/emails
        is_read_inquiry = any(k in user_query.lower() for k in [
            "what", "what's", "whats", "show", "read", "check", "find", "search", "list", "get", "recent", "latest", "inbox", "received", "says", "tell me"
        ])

        if is_read_inquiry:
            user_prompt = (
                f"User Instruction:\n{user_query}\n\n"
                f"{additional_context}\n\n"
                "Please inspect the user's received inbox by calling search_emails(query='recent', folder='inbox'). "
                "Then present a clear, neatly formatted summary of the latest email received, including:\n"
                "- **From / Sender**\n"
                "- **Subject**\n"
                "- **Date / Time**\n"
                "- **Email Summary / Key Content**\n"
                "- **Action Required (if any)**\n\n"
                "Do NOT draft or send any email. Provide an informative direct answer."
            )
        else:
            user_prompt = (
                f"User Instruction:\n{user_query}\n\n"
                f"{additional_context}\n\n"
                "Please process the email instruction. Format clearly with To, Subject, and Body."
            )

        email_output = llm_service.run_agent_with_tools(
            system_prompt=EMAIL_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            tools=scoped_tools,
            temperature=0.3,
            max_tool_rounds=2,
            max_tokens=1200,
        )

        # Determine if confirmation to send should be presented
        email_matches = re.findall(r"[\w\.-]+@[\w\.-]+\.\w+", user_query)
        is_explicit_send = any(re.search(r"\b" + re.escape(w) + r"\b", user_query.lower()) for w in ["send", "write", "dispatch", "compose", "forward"])
        has_specific_recipient = bool(email_matches)
        is_explicit_draft_only = any(k in user_query.lower() for k in ["save as draft", "only draft", "just draft", "dont send", "do not send"])
        should_offer_send = (is_explicit_send or has_specific_recipient) and not is_read_inquiry and not is_explicit_draft_only

        target_recipient = None
        target_subject = None
        clean_body = email_output.strip()

        if should_offer_send:
            target_recipient = email_matches[0] if email_matches else None
            if not target_recipient:
                to_match = re.search(r"To:\s*([\w\.-]+@[\w\.-]+\.\w+)", email_output, re.IGNORECASE)
                if to_match:
                    target_recipient = to_match.group(1).strip()
            if not target_recipient:
                target_recipient = "me@example.com"

            subj_match = re.search(r"subject\s*[:'\"=]\s*['\"]?([^'\"\n]+)['\"]?", user_query, re.IGNORECASE)
            if subj_match:
                target_subject = subj_match.group(1).strip()
            else:
                subj_out = re.search(r"Subject:\s*(.+)", email_output, re.IGNORECASE)
                target_subject = subj_out.group(1).strip() if subj_out else "Testing Multi-Agent AI"

            body_match = re.search(r"Body:\s*(?:```(?:code|text|markdown)?\s*)?([\s\S]+?)(?:```|$)", email_output, re.IGNORECASE)
            if body_match:
                clean_body = body_match.group(1).strip()

        confirmation_required = False
        new_pending_action = None
        workflow_status = "in_progress"

        if should_offer_send and confirmation_status != "APPROVED":
            confirmation_required = True
            workflow_status = "awaiting_confirmation"
            new_pending_action = {
                "action": "send_email",
                "agent": self.name,
                "recipient": target_recipient,
                "subject": target_subject,
                "details": {
                    "recipient": target_recipient,
                    "subject": target_subject,
                    "body": clean_body,
                },
                "prompt_for_user": f"Send this email to {target_recipient} with subject '{target_subject}'? (Approve/Reject)",
            }
            logger.info("[Email Agent] Prepared send_email confirmation card for %s.", target_recipient)

        agent_logs.append(
            {
                "agent": self.name,
                "action": "Processed email operation",
                "recipient": target_recipient,
                "confirmation_required": confirmation_required,
                "preview": email_output[:150] + "...",
            }
        )

        agent_history.append({"agent": self.name, "status": "completed" if not confirmation_required else "awaiting_confirmation"})

        return {
            "current_agent": self.name,
            "email_results": {
                "content": email_output,
                "recipient": target_recipient,
                "subject": target_subject,
                "status": "read" if is_read_inquiry else ("drafted" if not confirmation_required else "pending_confirmation"),
            },
            "draft": None if is_read_inquiry else email_output,
            "final_report": email_output,
            "response": email_output,
            "pending_action": new_pending_action,
            "confirmation_required": confirmation_required,
            "workflow_status": workflow_status,
            "agent_logs": agent_logs,
            "agent_history": agent_history,
        }


# Singleton callable node for LangGraph
email_agent_node = EmailAgent()
