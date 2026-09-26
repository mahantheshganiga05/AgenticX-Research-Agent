"""Persistent history storage for research sessions using SQLite.

Saves complete research session results including question, answer, sources,
tool activity, steps used, status, and latency metrics without requiring external database services.
"""

import json
import logging
import os
import sqlite3
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("agenticx.history")


def get_default_db_path() -> Path:
    """Resolve the SQLite database path based on the environment.

    In serverless environments like Vercel or AWS Lambda, the deployment directory (/var/task)
    is strictly read-only, so runtime file writes must use the ephemeral /tmp directory.
    In local development, the repository's ./data/history.db path is preserved.
    """
    if os.getenv("SQLITE_DB_PATH"):
        return Path(os.environ["SQLITE_DB_PATH"])
    if os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        return Path(tempfile.gettempdir()) / "data" / "history.db"
    return Path(__file__).resolve().parent.parent.parent / "data" / "history.db"


DB_PATH = get_default_db_path()


class HistoryStore:
    """Manages SQLite persistent storage for research sessions."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self._ensure_db()

    def _get_connection(self) -> sqlite3.Connection:
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as oe:
            logger.warning(f"Could not create database directory {self.db_path.parent}: {oe}")
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_db(self) -> None:
        """Create the research history table if it doesn't already exist."""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS research_history (
                        id TEXT PRIMARY KEY,
                        question TEXT NOT NULL,
                        answer TEXT NOT NULL,
                        sources_json TEXT NOT NULL,
                        tool_history_json TEXT NOT NULL,
                        steps_used INTEGER NOT NULL,
                        max_steps INTEGER NOT NULL,
                        status TEXT NOT NULL,
                        timing_json TEXT,
                        created_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_history_created_at
                    ON research_history (created_at DESC)
                    """
                )
                conn.commit()
        except Exception as e:
            logger.warning(f"Could not initialize research history database table: {e}")

    def save_session(
        self,
        question: str,
        answer: str,
        sources: list[Any],
        tool_history: list[Any],
        steps_used: int,
        max_steps: int,
        status: str,
        timing: Optional[dict[str, Any]] = None,
    ) -> str:
        """Persist a completed research session. Returns the unique history ID."""
        session_id = f"hist_{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        # Helper to serialize Pydantic models or dicts
        def serialize_item(item: Any) -> Any:
            if hasattr(item, "model_dump"):
                return item.model_dump()
            if hasattr(item, "dict"):
                return item.dict()
            return item

        sources_serialized = [serialize_item(s) for s in (sources or [])]
        tools_serialized = [serialize_item(t) for t in (tool_history or [])]
        timing_serialized = serialize_item(timing) if timing else {}

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO research_history (
                    id, question, answer, sources_json, tool_history_json,
                    steps_used, max_steps, status, timing_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    question,
                    answer,
                    json.dumps(sources_serialized),
                    json.dumps(tools_serialized),
                    steps_used,
                    max_steps,
                    str(status),
                    json.dumps(timing_serialized),
                    now_iso,
                ),
            )
            conn.commit()

        return session_id

    def list_sessions(self, limit: int = 50) -> list[dict[str, Any]]:
        """Retrieve recent research sessions for the history list view."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT id, question, answer, sources_json, steps_used, max_steps, status, timing_json, created_at
                    FROM research_history
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                )
                rows = cursor.fetchall()
        except Exception as e:
            logger.warning(f"Could not list research sessions from SQLite: {e}")
            return []

        results = []
        for r in rows:
            sources = json.loads(r["sources_json"] or "[]")
            timing = json.loads(r["timing_json"] or "{}")

            # Clean answer preview (strip headers/links for a neat summary snippet)
            clean_answer = (r["answer"] or "").strip()
            preview = clean_answer[:220] + ("..." if len(clean_answer) > 220 else "")

            results.append({
                "id": r["id"],
                "question": r["question"],
                "answer_preview": preview,
                "status": r["status"],
                "source_count": len(sources),
                "steps_used": r["steps_used"],
                "max_steps": r["max_steps"],
                "total_time": timing.get("total_time", 0.0) if isinstance(timing, dict) else 0.0,
                "created_at": r["created_at"],
            })
        return results

    def get_session(self, session_id: str) -> Optional[dict[str, Any]]:
        """Retrieve the complete session data by ID."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT id, question, answer, sources_json, tool_history_json,
                           steps_used, max_steps, status, timing_json, created_at
                    FROM research_history
                    WHERE id = ?
                    """,
                    (session_id,),
                )
                row = cursor.fetchone()
        except Exception as e:
            logger.warning(f"Could not retrieve research session {session_id} from SQLite: {e}")
            return None

        if not row:
            return None

        return {
            "id": row["id"],
            "question": row["question"],
            "answer": row["answer"],
            "sources": json.loads(row["sources_json"] or "[]"),
            "tool_history": json.loads(row["tool_history_json"] or "[]"),
            "steps_used": row["steps_used"],
            "max_steps": row["max_steps"],
            "status": row["status"],
            "timing": json.loads(row["timing_json"] or "{}"),
            "created_at": row["created_at"],
        }

    def delete_session(self, session_id: str) -> bool:
        """Delete a session from history."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("DELETE FROM research_history WHERE id = ?", (session_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.warning(f"Could not delete research session {session_id} from SQLite: {e}")
            return False

    def clear_all(self) -> None:
        """Clear all stored sessions."""
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM research_history")
                conn.commit()
        except Exception as e:
            logger.warning(f"Could not clear research sessions from SQLite: {e}")


# Singleton instance
history_store = HistoryStore()
