"""
Email tools for Email Agent and MCP Server.

Provides safe email management:
- search_emails(query, folder)
- get_email(email_id)
- draft_email(recipient, subject, body) -> Safe draft creation without sending
- send_email(recipient, subject, body, confirmed) -> Requires explicit confirmation before sending
- Persistent local store in data/emails.json with sample messages.
"""

import imaplib
import json
import logging
import re
import smtplib
import threading
import uuid
from datetime import datetime
from email import message_from_bytes
from email.header import decode_header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings

logger = logging.getLogger(__name__)

_email_lock = threading.Lock()
_live_email_cache: Dict[str, Dict[str, Any]] = {}
_cached_imap_emails: List[Dict[str, Any]] = []
_last_imap_fetch_time: float = 0.0
_IMAP_CACHE_TTL: float = 30.0

INITIAL_SAMPLE_EMAILS = [
    {
        "id": "email_001",
        "sender": "hr@innovatech.com",
        "recipient": "me@example.com",
        "subject": "Invitation: Technical Interview for Senior AI Engineer",
        "date": "2026-09-27T10:30:00",
        "folder": "inbox",
        "body": "Hi there, We would like to invite you for an interview regarding the Senior AI Engineer role on Thursday, Oct 1 at 2:00 PM EST. Please confirm your availability.",
    },
    {
        "id": "email_002",
        "sender": "prof.smith@university.edu",
        "recipient": "me@example.com",
        "subject": "CS890 Final Project Milestone Submission",
        "date": "2026-09-26T14:15:00",
        "folder": "inbox",
        "body": "Reminder: The multi-agent task automation project milestone report is due this Friday at 11:59 PM. Please make sure to include full validation tests.",
    },
    {
        "id": "email_003",
        "sender": "team-lead@initech.com",
        "recipient": "me@example.com",
        "subject": "Sprint Planning and Architecture Review",
        "date": "2026-09-28T09:00:00",
        "folder": "inbox",
        "body": "Team, our quarterly architecture review will be held tomorrow at 3:00 PM. Please prepare your service dependency diagrams.",
    },
]


def _get_storage_path(custom_path: Optional[str] = None) -> Path:
    target = Path(custom_path or settings.EMAIL_STORAGE_PATH)
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def _load_emails(storage_path: Optional[str] = None) -> List[Dict[str, Any]]:
    path = _get_storage_path(storage_path)
    if not path.exists():
        _save_emails(INITIAL_SAMPLE_EMAILS, storage_path)
        return list(INITIAL_SAMPLE_EMAILS)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return list(data)
    except Exception as err:
        logger.warning("Error reading emails.json (%s), restoring sample emails.", err)
        return list(INITIAL_SAMPLE_EMAILS)


def _save_emails(emails: List[Dict[str, Any]], storage_path: Optional[str] = None) -> None:
    path = _get_storage_path(storage_path)
    path.write_text(json.dumps(emails, indent=2), encoding="utf-8")


def _decode_header_str(val: str) -> str:
    """Decode RFC 2047 encoded email headers into clean unicode strings."""
    if not val:
        return ""
    try:
        parts = decode_header(val)
        out = ""
        for s, enc in parts:
            if isinstance(s, bytes):
                out += s.decode(enc or "utf-8", errors="ignore")
            else:
                out += str(s)
        return out.strip()
    except Exception:
        return str(val)


def _extract_body_from_email_message(msg: Any) -> str:
    """Extract plain text or clean text body from an email Message object."""
    body = ""
    try:
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                cdispo = str(part.get("Content-Disposition") or "")
                if ctype == "text/plain" and "attachment" not in cdispo:
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        body = payload.decode(charset, errors="ignore")
                        break
            if not body:
                # Fallback to HTML text extraction if plain text is empty
                for part in msg.walk():
                    if part.get_content_type() == "text/html":
                        payload = part.get_payload(decode=True)
                        if payload:
                            raw_html = payload.decode("utf-8", errors="ignore")
                            clean_text = re.sub(r"<[^>]+>", " ", raw_html)
                            body = " ".join(clean_text.split())
                            break
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                body = payload.decode("utf-8", errors="ignore")
    except Exception as e:
        logger.warning("[Email Tool] Error parsing email body: %s", e)
    return body.strip()


_EMAIL_STOP_WORDS = {
    "what", "whats", "what's", "is", "are", "my", "recent", "latest", "new", "all",
    "email", "emails", "mail", "mails", "says", "say", "from", "section", "inbox",
    "received", "check", "show", "get", "tell", "me", "the", "a", "an", "do", "does",
    "please", "there", "any", "read", "unread", "looking", "for"
}


def _fetch_live_imap_emails(limit: int = 5, search_query: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetch live emails directly from Gmail/IMAP inbox with memory caching."""
    global _cached_imap_emails, _last_imap_fetch_time
    import time

    now = time.time()
    tokens = re.findall(r"[a-zA-Z0-9]+", (search_query or "").lower())
    meaningful_keywords = [t for t in tokens if t not in _EMAIL_STOP_WORDS]
    is_general_query = not meaningful_keywords or any(t in ("recent", "latest", "inbox", "last", "new") for t in tokens)

    # Return cached live inbox if within TTL (instant response)
    if is_general_query and _cached_imap_emails and (now - _last_imap_fetch_time) < _IMAP_CACHE_TTL:
        return _cached_imap_emails[:limit]

    host = settings.IMAP_HOST
    port = settings.IMAP_PORT
    user = settings.IMAP_USER
    password = settings.IMAP_PASSWORD

    if not host or not user or not password:
        return []

    try:
        mail = imaplib.IMAP4_SSL(host, port)
        mail.login(user, password)
        mail.select("inbox")
        status, messages = mail.search(None, "ALL")
        if status != "OK" or not messages or not messages[0]:
            try:
                mail.close()
                mail.logout()
            except Exception:
                pass
            return []

        mail_ids = messages[0].split()
        # Fetch only necessary emails (top 'limit' for general query, or pool of 8 for keyword filtering)
        pool_size = limit if is_general_query else min(10, max(limit, 8))
        recent_ids = mail_ids[-pool_size:] if len(mail_ids) > pool_size else mail_ids
        recent_ids.reverse()  # Newest first

        results = []
        for mid in recent_ids:
            res, data = mail.fetch(mid, "(RFC822)")
            if res != "OK":
                continue
            for part in data:
                if isinstance(part, tuple):
                    msg = message_from_bytes(part[1])
                    subj = _decode_header_str(msg.get("Subject", ""))
                    sender = _decode_header_str(msg.get("From", ""))
                    to_addr = _decode_header_str(msg.get("To", ""))
                    date_str = msg.get("Date", "")
                    body_text = _extract_body_from_email_message(msg)

                    cached_obj = {
                        "id": f"imap_{mid.decode('utf-8', errors='ignore')}",
                        "sender": sender,
                        "recipient": to_addr,
                        "subject": subj,
                        "date": date_str,
                        "folder": "inbox",
                        "body": body_text[:300],
                        "preview": body_text[:250],
                        "full_body": body_text,
                    }
                    _live_email_cache[cached_obj["id"]] = cached_obj

                    # Compact summary for LLM context to prevent token overflows
                    results.append({
                        "id": cached_obj["id"],
                        "sender": sender,
                        "recipient": to_addr,
                        "subject": subj,
                        "date": date_str,
                        "preview": body_text[:250],
                        "body": body_text[:300],
                    })

        try:
            mail.close()
            mail.logout()
        except Exception:
            pass

        if results and is_general_query:
            _cached_imap_emails = list(results)
            _last_imap_fetch_time = now
            return results[:limit]

        if meaningful_keywords:
            filtered = []
            for em in results:
                searchable = f"{em.get('sender', '')} {em.get('subject', '')} {em.get('preview', '')} {em.get('body', '')}".lower()
                if any(kw in searchable for kw in meaningful_keywords):
                    filtered.append(em)
            return filtered[:limit] if filtered else []

        return results[:limit]
    except Exception as err:
        logger.warning("[Email Tool] Could not fetch live IMAP emails: %s", err)
        return []


def search_emails(
    query: str,
    folder: Optional[str] = None,
    storage_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Search emails across sender, subject, and body.
    Connects to live IMAP (Gmail) if credentials are configured in .env; otherwise falls back to local store.

    Args:
        query: Search term (or 'recent' / '' for latest emails).
        folder: Optional folder filter ('inbox', 'drafts', 'sent').

    Returns:
        Dict with 'query', 'count', and 'emails' list.
    """
    q = query.strip().lower()

    # Normalize folder name; treat 'mails', 'mail', 'all', or None as inbox
    raw_folder = (folder or "inbox").strip().lower()
    target_folder = "inbox" if raw_folder in ("inbox", "mail", "mails", "received", "all", "") else raw_folder

    # Check if live IMAP credentials are configured
    imap_configured = bool(settings.IMAP_HOST and settings.IMAP_USER and settings.IMAP_PASSWORD)

    if target_folder == "inbox" and imap_configured:
        live_emails = _fetch_live_imap_emails(limit=5, search_query=query)
        logger.info("[Email Tool] Live IMAP search for '%s' returned %d emails", q, len(live_emails))
        return {"query": query, "count": len(live_emails), "emails": live_emails, "source": "live_gmail"}

    # Fallback to local store (only if IMAP not configured)
    with _email_lock:
        all_emails = _load_emails(storage_path)

    matches = []
    for em in all_emails:
        if folder and em.get("folder", "").lower() != folder.lower():
            continue
        text_content = f"{em.get('sender', '')} {em.get('subject', '')} {em.get('body', '')}".lower()
        if not q or q in ("recent", "latest", "new", "all") or q in text_content:
            matches.append(em)

    logger.info("[Email Tool] Local search for '%s' returned %d emails", q, len(matches))
    return {"query": query, "count": len(matches), "emails": matches, "source": "local_store"}


def get_email(email_id: str, storage_path: Optional[str] = None) -> Dict[str, Any]:
    """Get full details of a specific email by id."""
    # Check live email cache first
    if email_id in _live_email_cache:
        cached = _live_email_cache[email_id]
        return {"email": {
            "id": cached.get("id"),
            "sender": cached.get("sender"),
            "recipient": cached.get("recipient"),
            "subject": cached.get("subject"),
            "date": cached.get("date"),
            "body": (cached.get("body") or cached.get("preview") or "")[:500],
        }}

    # Check local store
    with _email_lock:
        all_emails = _load_emails(storage_path)

    for em in all_emails:
        if em.get("id") == email_id:
            compact = dict(em)
            if "body" in compact and len(compact["body"]) > 500:
                compact["body"] = compact["body"][:500]
            return {"email": compact}

    # If it is an IMAP id, fetch directly from IMAP
    if email_id.startswith("imap_"):
        mid = email_id.replace("imap_", "").strip()
        host = settings.IMAP_HOST
        port = settings.IMAP_PORT
        user = settings.IMAP_USER
        password = settings.IMAP_PASSWORD
        if host and user and password:
            try:
                mail = imaplib.IMAP4_SSL(host, port)
                mail.login(user, password)
                mail.select("inbox")
                res, data = mail.fetch(mid.encode("utf-8"), "(RFC822)")
                if res == "OK":
                    for part in data:
                        if isinstance(part, tuple):
                            msg = message_from_bytes(part[1])
                            subj = _decode_header_str(msg.get("Subject", ""))
                            sender = _decode_header_str(msg.get("From", ""))
                            to_addr = _decode_header_str(msg.get("To", ""))
                            date_str = msg.get("Date", "")
                            body_text = _extract_body_from_email_message(msg)
                            email_obj = {
                                "id": email_id,
                                "sender": sender,
                                "recipient": to_addr,
                                "subject": subj,
                                "date": date_str,
                                "folder": "inbox",
                                "body": body_text[:500],
                            }
                            _live_email_cache[email_id] = email_obj
                            try:
                                mail.close()
                                mail.logout()
                            except Exception:
                                pass
                            return {"email": email_obj}
                try:
                    mail.close()
                    mail.logout()
                except Exception:
                    pass
            except Exception as err:
                logger.warning("[Email Tool] Could not fetch IMAP email '%s': %s", email_id, err)

    return {"error": f"Email with ID '{email_id}' not found."}


def draft_email(
    recipient: str,
    subject: str,
    body: str,
    storage_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a new email draft in the drafts folder (safe read/write, does not send).
    """
    draft = {
        "id": f"draft_{uuid.uuid4().hex[:8]}",
        "sender": "me@example.com",
        "recipient": recipient.strip(),
        "subject": subject.strip(),
        "date": datetime.now().isoformat(),
        "folder": "drafts",
        "body": body.strip(),
    }

    with _email_lock:
        all_emails = _load_emails(storage_path)
        all_emails.append(draft)
        _save_emails(all_emails, storage_path)

    logger.info("[Email Tool] Created draft ID '%s' to %s", draft["id"], recipient)
    return {
        "status": "draft_created",
        "message": "Draft created successfully. It will NOT be sent until explicitly authorized.",
        "draft": draft,
    }


def _dispatch_smtp_email(recipient: str, subject: str, body: str) -> Dict[str, Any]:
    """
    Dispatch an email over live SMTP if credentials are configured in environment.
    Supports STARTTLS (port 587) and SSL (port 465).
    """
    host = settings.SMTP_HOST
    port = settings.SMTP_PORT
    user = settings.SMTP_USER
    password = settings.SMTP_PASSWORD
    from_email = settings.SMTP_FROM_EMAIL or user

    if not host or not user or not password:
        logger.info("[SMTP] No credentials configured. Recording to persistent local store.")
        return {
            "delivered_live": False,
            "configured": False,
            "notice": "SMTP credentials not configured in backend/.env; email saved to outbox store.",
        }

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = recipient

    # Attach text payload
    text_part = MIMEText(body, "plain", "utf-8")
    msg.attach(text_part)

    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=15) as server:
                server.login(user, password)
                server.sendmail(from_email, [recipient], msg.as_string())
        else:
            with smtplib.SMTP(host, port, timeout=15) as server:
                if settings.SMTP_USE_TLS:
                    server.starttls()
                server.login(user, password)
                server.sendmail(from_email, [recipient], msg.as_string())

        logger.info("[SMTP] Email successfully dispatched via %s:%s to %s", host, port, recipient)
        return {
            "delivered_live": True,
            "configured": True,
            "host": host,
            "port": port,
            "from": from_email,
        }
    except Exception as err:
        logger.error("[SMTP] Failed to deliver email via SMTP: %s", err)
        return {
            "delivered_live": False,
            "configured": True,
            "error": str(err),
            "notice": f"SMTP dispatch failed: {err}",
        }


def send_email(
    recipient: str,
    subject: str,
    body: str,
    confirmed: bool = False,
    storage_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Send an email. Requires explicit user confirmation (confirmed=True).
    If confirmed=False, returns confirmation requirement payload to pause workflow.
    When confirmed=True, sends via live SMTP (if configured in .env) and saves to persistent store.
    """
    if not confirmed:
        logger.warning("[Email Tool] send_email attempted without confirmation for %s", recipient)
        return {
            "status": "requires_confirmation",
            "action": "send_email",
            "confirmation_required": True,
            "details": {
                "recipient": recipient.strip(),
                "subject": subject.strip(),
                "body": body.strip(),
            },
            "prompt_for_user": (
                f"Please confirm sending the following email:\n"
                f"- To: {recipient.strip()}\n"
                f"- Subject: {subject.strip()}\n"
                f"- Body Preview: {body.strip()[:160]}...\n\n"
                f"Confirm sending this email? (Approve/Reject)"
            ),
        }

    # Action confirmed by user -> attempt live SMTP delivery + persistent recording
    smtp_result = _dispatch_smtp_email(
        recipient=recipient.strip(),
        subject=subject.strip(),
        body=body.strip(),
    )

    from_addr = settings.SMTP_FROM_EMAIL or "me@example.com"
    sent_msg = {
        "id": f"sent_{uuid.uuid4().hex[:8]}",
        "sender": from_addr,
        "recipient": recipient.strip(),
        "subject": subject.strip(),
        "date": datetime.now().isoformat(),
        "folder": "sent",
        "body": body.strip(),
        "delivery": smtp_result,
    }

    with _email_lock:
        all_emails = _load_emails(storage_path)
        all_emails.append(sent_msg)
        _save_emails(all_emails, storage_path)

    if smtp_result.get("delivered_live"):
        msg = f"Email successfully dispatched to {recipient.strip()} via SMTP ({settings.SMTP_HOST})."
    elif smtp_result.get("configured") and "error" in smtp_result:
        msg = f"Email confirmed and recorded in outbox, but SMTP server reported: {smtp_result['error']}. Check your SMTP credentials in backend/.env."
    else:
        msg = f"Email confirmed and stored in outbox. (To deliver live over the internet to real inboxes, configure SMTP_HOST, SMTP_USER, and SMTP_PASSWORD in backend/.env)"

    logger.info("[Email Tool] %s (ID: %s)", msg, sent_msg["id"])
    return {
        "status": "sent",
        "confirmation_status": "APPROVED",
        "message": msg,
        "email": sent_msg,
        "delivered_live": smtp_result.get("delivered_live", False),
    }
