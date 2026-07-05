"""SQLite persistence for discovered/scored ideas -- the durable record the
HITL dashboard (Milestone 4) will read from and update.
"""

import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path

from .config import get_settings
from .models import AnalyzedIdea

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ideas (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    source_url TEXT NOT NULL,
    score INTEGER,
    reasoning TEXT,
    status TEXT NOT NULL,
    discovered_at TEXT NOT NULL
)
"""


@contextmanager
def _connect():
    settings = get_settings()
    db_path = Path(settings.database_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(_SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def save_idea(idea: AnalyzedIdea) -> str:
    """Persists `idea`, returns the generated id."""
    idea_id = uuid.uuid4().hex
    with _connect() as conn:
        conn.execute(
            "INSERT INTO ideas (id, title, description, source_url, score, reasoning, status, discovered_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                idea_id,
                idea.title,
                idea.description,
                idea.source_url,
                idea.score,
                idea.reasoning,
                idea.status,
                idea.discovered_at,
            ),
        )
    return idea_id


def list_ideas(status: str | None = None) -> list[sqlite3.Row]:
    """Returns stored ideas, optionally filtered by status, newest first."""
    with _connect() as conn:
        if status:
            cursor = conn.execute(
                "SELECT * FROM ideas WHERE status = ? ORDER BY discovered_at DESC", (status,)
            )
        else:
            cursor = conn.execute("SELECT * FROM ideas ORDER BY discovered_at DESC")
        return cursor.fetchall()
