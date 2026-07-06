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
            db_path = url.rsplit("///", 1)[-1]
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        _engine = create_async_engine(url)
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


async def init_db() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
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
