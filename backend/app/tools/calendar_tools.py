"""
Calendar tools for Calendar Agent and MCP Server.

Provides safe calendar scheduling:
- Read: list_events, get_event, find_free_time
- Write: create_event, update_event, delete_event (enforces confirmation before persisting changes)
- Persistent local store in data/calendar.json with sample scheduled events.
"""

import json
import logging
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings

logger = logging.getLogger(__name__)

_calendar_lock = threading.Lock()

INITIAL_SAMPLE_EVENTS = [
    {
        "id": "evt_001",
        "title": "Daily Multi-Agent Engineering Standup",
        "start_time": "2026-09-29T09:30:00",
        "end_time": "2026-09-29T10:00:00",
        "attendees": ["team@initech.com", "me@example.com"],
        "description": "Daily sync on agent components and MCP tools.",
    },
    {
        "id": "evt_002",
        "title": "Architecture Deep Dive: MCP and Checkpointing",
        "start_time": "2026-09-29T14:00:00",
        "end_time": "2026-09-29T15:30:00",
        "attendees": ["lead@initech.com", "me@example.com"],
        "description": "Reviewing SQLite checkpointer and specialized agent registry.",
    },
    {
        "id": "evt_003",
        "title": "Client Technical Demo: RAG + LangGraph",
        "start_time": "2026-09-30T11:00:00",
        "end_time": "2026-09-30T12:00:00",
        "attendees": ["client@acme.com", "me@example.com"],
        "description": "Demonstrating hybrid document search and persistent workflow continuation.",
    },
]


def _get_storage_path(custom_path: Optional[str] = None) -> Path:
    target = Path(custom_path or settings.CALENDAR_STORAGE_PATH)
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def _load_events(storage_path: Optional[str] = None) -> List[Dict[str, Any]]:
    path = _get_storage_path(storage_path)
    if not path.exists():
        _save_events(INITIAL_SAMPLE_EVENTS, storage_path)
        return list(INITIAL_SAMPLE_EVENTS)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return list(data)
    except Exception as err:
        logger.warning("Error reading calendar.json (%s), restoring sample events.", err)
        return list(INITIAL_SAMPLE_EVENTS)


def _save_events(events: List[Dict[str, Any]], storage_path: Optional[str] = None) -> None:
    path = _get_storage_path(storage_path)
    path.write_text(json.dumps(events, indent=2), encoding="utf-8")


def list_events(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    storage_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    List calendar events within an optional date range.

    Args:
        start_date: Optional ISO date string filter (e.g. '2026-09-29').
        end_date: Optional ISO date string filter.

    Returns:
        Dict with 'count' and 'events' list.
    """
    with _calendar_lock:
        all_events = _load_events(storage_path)

    filtered = []
    for evt in all_events:
        st = evt.get("start_time", "")
        if start_date and st < start_date:
            continue
        if end_date and st > end_date:
            continue
        filtered.append(evt)

    logger.info("[Calendar Tool] Found %d events (filter: %s to %s)", len(filtered), start_date, end_date)
    return {"count": len(filtered), "events": filtered}


def get_event(event_id: str, storage_path: Optional[str] = None) -> Dict[str, Any]:
    """Fetch event details by event_id."""
    with _calendar_lock:
        all_events = _load_events(storage_path)

    for evt in all_events:
        if evt.get("id") == event_id:
            return {"event": evt}
    return {"error": f"Event '{event_id}' not found."}


def find_free_time(
    date: str,
    duration_minutes: int = 30,
    storage_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Suggest open time slots on a given date (assuming working hours 09:00 - 17:00).
    """
    target_date = date.strip()[:10]
    day_events = list_events(start_date=f"{target_date}T00:00:00", end_date=f"{target_date}T23:59:59", storage_path=storage_path)["events"]

    busy_slots = [(e["start_time"][11:16], e["end_time"][11:16]) for e in day_events]
    standard_slots = ["10:00", "11:30", "13:00", "14:30", "16:00"]
    free_slots = []

    for slot in standard_slots:
        is_busy = any(start <= slot < end for start, end in busy_slots)
        if not is_busy:
            free_slots.append(f"{target_date}T{slot}:00")

    return {
        "date": target_date,
        "duration_minutes": duration_minutes,
        "available_slots": free_slots,
    }


def create_event(
    title: str,
    start_time: str,
    end_time: str,
    attendees: Optional[List[str]] = None,
    description: str = "",
    confirmed: bool = False,
    storage_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Schedule a new calendar event.
    Requires explicit user confirmation (confirmed=True) before persisting to calendar.
    """
    if not confirmed:
        logger.warning("[Calendar Tool] create_event attempted without confirmation for '%s'", title)
        return {
            "status": "requires_confirmation",
            "action": "create_calendar_event",
            "confirmation_required": True,
            "details": {
                "title": title.strip(),
                "start_time": start_time.strip(),
                "end_time": end_time.strip(),
                "attendees": attendees or [],
                "description": description.strip(),
            },
            "prompt_for_user": (
                f"Please confirm scheduling this calendar event:\n"
                f"- Title: {title.strip()}\n"
                f"- Start Time: {start_time.strip()}\n"
                f"- End Time: {end_time.strip()}\n"
                f"- Attendees: {', '.join(attendees or ['Me'])}\n\n"
                f"Confirm creating this event? (Approve/Reject)"
            ),
        }

    new_evt = {
        "id": f"evt_{uuid.uuid4().hex[:8]}",
        "title": title.strip(),
        "start_time": start_time.strip(),
        "end_time": end_time.strip(),
        "attendees": attendees or ["me@example.com"],
        "description": description.strip(),
    }

    with _calendar_lock:
        all_events = _load_events(storage_path)
        all_events.append(new_evt)
        _save_events(all_events, storage_path)

    logger.info("[Calendar Tool] Event created with ID '%s': %s", new_evt["id"], title)
    return {
        "status": "event_created",
        "confirmation_status": "APPROVED",
        "message": f"Calendar event '{title}' scheduled successfully.",
        "event": new_evt,
    }


def update_event(
    event_id: str,
    title: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    confirmed: bool = False,
    storage_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Update an existing calendar event with confirmation."""
    if not confirmed:
        return {
            "status": "requires_confirmation",
            "action": "update_calendar_event",
            "confirmation_required": True,
            "details": {"event_id": event_id, "title": title, "start_time": start_time, "end_time": end_time},
            "prompt_for_user": f"Confirm updating event '{event_id}' with new parameters? (Approve/Reject)",
        }

    with _calendar_lock:
        all_events = _load_events(storage_path)
        found = False
        for e in all_events:
            if e.get("id") == event_id:
                if title:
                    e["title"] = title.strip()
                if start_time:
                    e["start_time"] = start_time.strip()
                if end_time:
                    e["end_time"] = end_time.strip()
                found = True
                _save_events(all_events, storage_path)
                return {"status": "event_updated", "event": e}

    return {"error": f"Event '{event_id}' not found."}


def delete_event(
    event_id: str,
    confirmed: bool = False,
    storage_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Delete an event from the calendar with confirmation."""
    if not confirmed:
        return {
            "status": "requires_confirmation",
            "action": "delete_calendar_event",
            "confirmation_required": True,
            "details": {"event_id": event_id},
            "prompt_for_user": f"Confirm permanent deletion of event '{event_id}'? (Approve/Reject)",
        }

    with _calendar_lock:
        all_events = _load_events(storage_path)
        new_events = [e for e in all_events if e.get("id") != event_id]
        if len(new_events) == len(all_events):
            return {"error": f"Event '{event_id}' not found."}
        _save_events(new_events, storage_path)

    return {"status": "event_deleted", "event_id": event_id}
