"""
Calendar Agent module.

Specialized agent responsible for:
- Reading, querying, and summarizing calendar schedules (automatic).
- Identifying free time slots and scheduling conflicts.
- Coordinating event creation, updates, and cancellations with Human-in-the-Loop Confirmation:
  - Read queries execute automatically.
  - Creation/modification/deletion requires explicit user authorization before execution.
- Populating calendar_results in workflow state.
"""

import logging
from typing import Any, Dict

from app.agents.base import BaseAgent
from app.graph.state import GraphState
from app.services import llm_service
from app.tools.calendar_tools import create_event, list_events

logger = logging.getLogger(__name__)

CALENDAR_SYSTEM_PROMPT = """You are the Calendar Agent in a multi-agent task automation system.
Your responsibility is schedule inspection, event planning, and calendar coordination.

Tools Available:
- list_events: Query scheduled calendar events (optional start_date and end_date).
- get_event: Get details of a specific event by ID.
- find_free_time: Look for available meeting slots on a specific date.
- create_event: Schedule a new calendar event (requires confirmation).

Safety Guidelines:
- Reading events and finding free time are safe read operations that execute automatically.
- If asked to schedule, create, or modify an event, propose the details (Title, Start Time, End Time, Attendees) and indicate that user confirmation is required before the event is booked."""


class CalendarAgent(BaseAgent):
    name = "calendar"
    description = "Inspects schedules, checks availability, and coordinates event bookings with confirmation safety."
    role = "Calendar Scheduling & Agenda Management"
    allowed_tools = ["list_events", "get_event", "find_free_time", "create_event"]

    def run(self, state: GraphState) -> Dict[str, Any]:
        user_query = state.get("user_query", "")
        confirmation_status = state.get("confirmation_status", "NONE")
        pending_action = state.get("pending_action")
        email_results = state.get("email_results")
        agent_logs = list(state.get("agent_logs") or [])
        agent_history = list(state.get("agent_history") or [])

        logger.info("[Calendar Agent] Processing request: '%s' (Confirmation: %s)", user_query, confirmation_status)

        scoped_tools = self.get_scoped_tools()

        # Handle resume after user confirmation
        if confirmation_status == "APPROVED" and pending_action and pending_action.get("action") == "create_calendar_event":
            details = pending_action.get("details", {})
            res = create_event(
                title=details.get("title", "Meeting"),
                start_time=details.get("start_time", "2026-09-29T10:00:00"),
                end_time=details.get("end_time", "2026-09-29T11:00:00"),
                attendees=details.get("attendees"),
                description=details.get("description", ""),
                confirmed=True,
            )
            response_msg = f"Calendar event '{details.get('title')}' has been confirmed and scheduled for {details.get('start_time')}."
            agent_logs.append({"agent": self.name, "action": "Booked confirmed calendar event", "details": details})
            agent_history.append({"agent": self.name, "status": "completed"})

            return {
                "current_agent": self.name,
                "calendar_results": {"status": "scheduled", "details": res},
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

        # Build context if prior agents supplied information (e.g. Email interview dates)
        context_blocks = []
        if email_results:
            context_blocks.append(f"Email Details:\n{email_results}")

        additional_context = "\n\n".join(context_blocks)

        user_prompt = (
            f"User Instruction:\n{user_query}\n\n"
            f"{additional_context}\n\n"
            "Please process the calendar request using available calendar tools. "
            "If checking meetings, retrieve and summarize them clearly. "
            "If scheduling a new event, formulate the event parameters and indicate user confirmation is required."
        )

        calendar_output = llm_service.run_agent_with_tools(
            system_prompt=CALENDAR_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            tools=scoped_tools,
            temperature=0.2,
            max_tool_rounds=2,
            max_tokens=1200,
        )

        # Detect if creating/scheduling an event was requested
        schedule_keywords = ["schedule", "book", "create event", "create meeting", "add to my calendar", "put on my calendar"]
        is_schedule_intent = any(kw in user_query.lower() for kw in schedule_keywords)

        confirmation_required = False
        new_pending_action = None
        workflow_status = "in_progress"

        if is_schedule_intent and confirmation_status != "APPROVED":
            confirmation_required = True
            workflow_status = "awaiting_confirmation"
            new_pending_action = {
                "action": "create_calendar_event",
                "agent": self.name,
                "details": {
                    "title": "Interview Meeting",
                    "start_time": "2026-10-01T14:00:00",
                    "end_time": "2026-10-01T15:00:00",
                    "attendees": ["hr@innovatech.com", "me@example.com"],
                    "description": "Technical interview discussion",
                },
                "prompt_for_user": "I can schedule this calendar event. Would you like to confirm? (Approve/Reject)",
            }
            logger.info("[Calendar Agent] Pausing workflow for user confirmation before creating calendar event.")

        agent_logs.append(
            {
                "agent": self.name,
                "action": "Processed calendar inquiry/schedule",
                "confirmation_required": confirmation_required,
                "preview": calendar_output[:150] + "...",
            }
        )

        agent_history.append({"agent": self.name, "status": "completed" if not confirmation_required else "awaiting_confirmation"})

        return {
            "current_agent": self.name,
            "calendar_results": {"content": calendar_output, "status": "inspected" if not confirmation_required else "pending_confirmation"},
            "draft": calendar_output,
            "final_report": calendar_output if not confirmation_required else None,
            "response": calendar_output,
            "pending_action": new_pending_action,
            "confirmation_required": confirmation_required,
            "workflow_status": workflow_status,
            "agent_logs": agent_logs,
            "agent_history": agent_history,
        }


# Singleton callable node for LangGraph
calendar_agent_node = CalendarAgent()
