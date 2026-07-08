"""Async engine/session management.

SQLite (via aiosqlite) today; the URL comes from settings so Postgres is a
connection-string change. `init_db()` is idempotent and safe to call at
every process start.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from ..config import get_settings
from .models import Base

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine, _session_factory
    if _engine is None:
        settings = get_settings()
        url = settings.database_url
        if url.startswith("sqlite"):
            # Ensure the data directory exists before SQLite touches the file.
            # Use data_dir directly rather than re-parsing the URL: a POSIX
            # absolute data_dir yields a four-slash URL (sqlite:////app/...)
            # where rsplit("///") strips the leading slash and turns the path
            # relative — observed live as a container crash-loop.
            Path(settings.data_dir).mkdir(parents=True, exist_ok=True)
        _engine = create_async_engine(url)
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


# Columns added after a table first shipped. `create_all` only creates
# missing *tables*, never alters existing ones — without this, a database
# created before these columns existed fails at the first query that
# references them. SQLite ADD COLUMN is cheap and idempotent-by-check here;
# a real migration tool (Alembic) replaces this the moment the schema story
# gets more complicated than additive nullable columns.
_ADDITIVE_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "runs": [("source", "VARCHAR(20) DEFAULT 'operator'"), ("keyword", "TEXT")],
    "ideas": [("ptp_number", "INTEGER")],
    "builds": [("deploy_url", "TEXT")],
}


def _apply_additive_columns(sync_conn) -> None:
    from sqlalchemy import text

    for table, columns in _ADDITIVE_COLUMNS.items():
        rows = sync_conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
        if not rows:  # table doesn't exist yet; create_all handles it
            continue
        existing = {row[1] for row in rows}
        for name, ddl in columns:
            if name not in existing:
                sync_conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


async def init_db() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        if engine.url.get_backend_name().startswith("sqlite"):
            await conn.run_sync(_apply_additive_columns)
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def session() -> AsyncIterator[AsyncSession]:
    get_engine()
    assert _session_factory is not None
    async with _session_factory() as s:
        yield s


async def dispose_engine() -> None:
    """Reset engine state — used by tests and clean shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
