"""
Database connection utility for Student Claw.

Provides a single async SQLAlchemy engine + session factory for the entire
backend (FastAPI request handlers, the Telegram bot process, and the Celery
embedding workers all import from here).

Usage (FastAPI dependency):

    from app.database.connection import get_session

    @router.get("/projects")
    async def list_projects(session: AsyncSession = Depends(get_session)):
        ...

Usage (standalone, e.g. bot handler or worker):

    from app.database.connection import session_scope

    async with session_scope() as session:
        session.add(obj)
        # commit happens automatically on clean exit
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# DATABASE_URL must use the asyncpg driver, e.g.:
#   postgresql+asyncpg://user:password@localhost:5432/student_claw
#
# If a plain "postgresql://" URL is supplied (common with managed providers
# like Supabase/RDS), we transparently upgrade it to the asyncpg driver.
_RAW_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/student_claw",
)


def _normalize_async_url(url: str) -> str:
    """Ensure the URL targets the asyncpg driver."""
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):  # Heroku-style legacy scheme
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


DATABASE_URL: str = _normalize_async_url(_RAW_DATABASE_URL)

# SQL echo for local debugging — set DB_ECHO=true to log all emitted SQL.
_ECHO = os.getenv("DB_ECHO", "false").lower() in {"1", "true", "yes"}

# Pool tuning. Defaults are conservative and suitable for a small deployment;
# override via env vars for horizontal scaling of the API backend.
_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))
_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "20"))
_POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))
_POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "1800"))  # recycle every 30 min

# ---------------------------------------------------------------------------
# Engine & session factory (module-level singletons)
# ---------------------------------------------------------------------------
engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=_ECHO,
    pool_pre_ping=True,        # transparently recover from stale connections
    pool_size=_POOL_SIZE,
    max_overflow=_MAX_OVERFLOW,
    pool_timeout=_POOL_TIMEOUT,
    pool_recycle=_POOL_RECYCLE,
)

# expire_on_commit=False keeps ORM objects usable after commit (important when
# returning them out of a session_scope block or serializing in a response).
AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields a request-scoped session.

    The session is rolled back and closed automatically when the request
    finishes. Commit explicitly inside your handler when you mutate state.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession, None]:
    """
    Standalone transactional scope for non-FastAPI contexts (bot handlers,
    Celery workers, scripts).

    Commits on clean exit, rolls back on exception, always closes.
    """
    session = AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def dispose_engine() -> None:
    """
    Dispose of the connection pool. Call from FastAPI's shutdown event and on
    graceful bot/worker shutdown to release sockets cleanly.
    """
    await engine.dispose()
