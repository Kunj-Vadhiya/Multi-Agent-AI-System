"""
Persistent Checkpointing Service for LangGraph Workflows (Version 6).

Provides SQLite-backed persistence for LangGraph workflow state:
- Survives application restarts.
- Isolates state across unique thread_ids.
- Enables conversation continuation and workflow resumption.
"""

import logging
import os
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from langgraph.checkpoint.sqlite import SqliteSaver

from app.config import settings

logger = logging.getLogger(__name__)

_lock = threading.RLock()
_conn: Optional[sqlite3.Connection] = None
_checkpointer: Optional[SqliteSaver] = None


def get_checkpoint_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    Get or create a thread-safe SQLite connection for checkpointing.

    Args:
        db_path (Optional[str]): Database file path. Defaults to settings.CHECKPOINT_DB_PATH.

    Returns:
        sqlite3.Connection: Active SQLite connection.
    """
    global _conn
    target_path = db_path or settings.CHECKPOINT_DB_PATH

    with _lock:
        if _conn is None:
            # Ensure parent directories exist
            Path(target_path).parent.mkdir(parents=True, exist_ok=True)
            logger.info("Initializing persistent SQLite checkpointer at: '%s'", target_path)
            _conn = sqlite3.connect(target_path, check_same_thread=False)
        return _conn


def get_checkpointer(db_path: Optional[str] = None) -> SqliteSaver:
    """
    Get or initialize the singleton LangGraph SqliteSaver checkpointer.

    Args:
        db_path (Optional[str]): Database file path. Defaults to settings.CHECKPOINT_DB_PATH.

    Returns:
        SqliteSaver: Configured checkpointer instance with tables setup.
    """
    global _checkpointer
    with _lock:
        if _checkpointer is None:
            conn = get_checkpoint_connection(db_path)
            saver = SqliteSaver(conn)
            saver.setup()
            _checkpointer = saver
            logger.info("LangGraph SqliteSaver initialized and schema verified.")
        return _checkpointer


def reset_checkpointer() -> None:
    """
    Close and reset checkpointer and connection (useful for isolated tests).
    """
    global _conn, _checkpointer
    with _lock:
        if _conn is not None:
            try:
                _conn.close()
            except Exception as err:
                logger.warning("Error closing checkpointer connection: %s", err)
            _conn = None
        _checkpointer = None
        logger.info("Checkpointer connection reset.")


def get_thread_state(thread_id: str, checkpointer: Optional[SqliteSaver] = None) -> Optional[Dict[str, Any]]:
    """
    Fetch the latest checkpoint state snapshot for a given thread_id.

    Args:
        thread_id (str): Conversation thread identifier.
        checkpointer (Optional[SqliteSaver]): Checkpointer instance.

    Returns:
        Optional[Dict[str, Any]]: Current state dictionary or None if thread does not exist.
    """
    saver = checkpointer or get_checkpointer()
    config = {"configurable": {"thread_id": thread_id}}
    try:
        snapshot = saver.get_tuple(config)
        if snapshot and snapshot.checkpoint:
            channel_values = snapshot.checkpoint.get("channel_values", {})
            return channel_values
        return None
    except Exception as err:
        logger.warning("Failed to retrieve thread state for '%s': %s", thread_id, err)
        return None


def init_thread_metadata(conn: sqlite3.Connection) -> None:
    """Create thread_metadata table if not present."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS thread_metadata (
            thread_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()


def list_all_threads(db_path: Optional[str] = None) -> list:
    """List all known threads with title, message count, and status."""
    conn = get_checkpoint_connection(db_path)
    with _lock:
        init_thread_metadata(conn)
        cursor = conn.execute(
            """
            SELECT DISTINCT thread_id FROM (
                SELECT thread_id FROM checkpoints
                UNION
                SELECT thread_id FROM thread_metadata
            )
            """
        )
        thread_ids = [row[0] for row in cursor.fetchall()]

        cursor = conn.execute("SELECT thread_id, title, updated_at FROM thread_metadata")
        meta_map = {row[0]: {"title": row[1], "updated_at": row[2]} for row in cursor.fetchall()}

        results = []
        for tid in thread_ids:
            meta = meta_map.get(tid)
            title = meta["title"] if meta else None
            updated_at = meta["updated_at"] if meta else None

            st = get_thread_state(tid)
            msgs = (st.get("messages") or []) if st else []
            msg_count = len(msgs)

            # If title is missing or a default/truncated placeholder, generate a topic title
            if not title or title in ("New Conversation", "New Chat") or title.startswith("Chat ") or title.endswith("..."):
                user_msg = next((m.get("content") for m in msgs if m.get("role") == "user"), None)
                if user_msg:
                    from app.services.topic_service import generate_topic_title
                    title = generate_topic_title(user_msg)
                elif not title:
                    title = f"Chat {tid[:8]}"

                try:
                    conn.execute(
                        "INSERT OR REPLACE INTO thread_metadata (thread_id, title) VALUES (?, ?)",
                        (tid, title),
                    )
                    conn.commit()
                except Exception:
                    pass

            results.append(
                {
                    "thread_id": tid,
                    "title": title,
                    "message_count": msg_count,
                    "updated_at": updated_at or "",
                    "current_agent": st.get("current_agent") if st else None,
                    "workflow_status": st.get("workflow_status", "completed") if st else "completed",
                }
            )

        results.sort(key=lambda x: (x["message_count"] > 0, str(x["updated_at"])), reverse=True)
        return results


def get_thread_title(thread_id: str, db_path: Optional[str] = None) -> Optional[str]:
    """Retrieve title for a thread from thread_metadata."""
    conn = get_checkpoint_connection(db_path)
    with _lock:
        init_thread_metadata(conn)
        cursor = conn.execute("SELECT title FROM thread_metadata WHERE thread_id = ?", (thread_id,))
        row = cursor.fetchone()
        return row[0] if row and row[0] else None


def set_thread_title(thread_id: str, title: str, db_path: Optional[str] = None) -> None:
    """Update title for a thread."""
    conn = get_checkpoint_connection(db_path)
    with _lock:
        init_thread_metadata(conn)
        conn.execute(
            "INSERT OR REPLACE INTO thread_metadata (thread_id, title, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (thread_id, title),
        )
        conn.commit()


def delete_thread_data(thread_id: str, db_path: Optional[str] = None) -> bool:
    """Delete all checkpoints, writes, and metadata for a thread."""
    conn = get_checkpoint_connection(db_path)
    with _lock:
        init_thread_metadata(conn)
        conn.execute("DELETE FROM checkpoints WHERE thread_id = ?", (thread_id,))
        conn.execute("DELETE FROM writes WHERE thread_id = ?", (thread_id,))
        conn.execute("DELETE FROM thread_metadata WHERE thread_id = ?", (thread_id,))
        conn.commit()
        return True

