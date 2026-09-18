from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

DEFAULT_POSTGRES_HOST = "127.0.0.1"
DEFAULT_POSTGRES_PORT = "5432"
DEFAULT_POSTGRES_DB = "orca"
DEFAULT_POSTGRES_USER = "orca"
DEFAULT_POSTGRES_PASSWORD = "orca"

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_base_database_url() -> str:
    """Retrieve raw database URL from environment or default."""
    url = os.getenv("ORCA_DATABASE_URL") or os.getenv("DATABASE_URL")
    if url:
        return url
    return (
        f"postgresql://{DEFAULT_POSTGRES_USER}:{DEFAULT_POSTGRES_PASSWORD}@"
        f"{DEFAULT_POSTGRES_HOST}:{DEFAULT_POSTGRES_PORT}/{DEFAULT_POSTGRES_DB}"
    )


def get_async_database_url() -> str:
    """Ensure SQLAlchemy asyncpg driver scheme (postgresql+asyncpg://)."""
    raw = get_base_database_url()
    if raw.startswith("postgresql://"):
        return raw.replace("postgresql://", "postgresql+asyncpg://", 1)
    if not raw.startswith("postgresql+asyncpg://"):
        return f"postgresql+asyncpg://{raw}"
    return raw


def get_raw_database_url() -> str:
    """Ensure raw postgresql:// scheme for direct asyncpg / psql connections."""
    raw = get_base_database_url()
    if raw.startswith("postgresql+asyncpg://"):
        return raw.replace("postgresql+asyncpg://", "postgresql://", 1)
    return raw


from sqlalchemy.pool import NullPool


def get_engine(*, force_null_pool: bool = False) -> AsyncEngine:
    global _engine
    use_null = force_null_pool or os.getenv("ORCA_DB_POOL", "").lower() in ("null", "nullpool")
    if use_null:
        return create_async_engine(
            get_async_database_url(),
            poolclass=NullPool,
            echo=os.getenv("SQL_ECHO", "false").lower() in ("1", "true", "yes"),
        )
    if _engine is None:
        url = get_async_database_url()
        _engine = create_async_engine(
            url,
            echo=os.getenv("SQL_ECHO", "false").lower() in ("1", "true", "yes"),
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
        )
    return _engine


def get_session_factory(*, force_null_pool: bool = False) -> async_sessionmaker[AsyncSession]:
    global _session_factory
    use_null = force_null_pool or os.getenv("ORCA_DB_POOL", "").lower() in ("null", "nullpool")
    if use_null:
        return async_sessionmaker(
            bind=get_engine(force_null_pool=True),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for obtaining an async session."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def check_database_health() -> dict[str, Any]:
    """Probe DB connectivity and verify PostGIS / pgvector extensions."""
    import asyncpg
    raw_url = get_raw_database_url()
    try:
        conn = await asyncpg.connect(raw_url)
        try:
            alive = (await conn.fetchval("SELECT 1")) == 1
            ext_rows = await conn.fetch(
                "SELECT extname, extversion FROM pg_extension WHERE extname IN ('postgis', 'vector')"
            )
            extensions = {row["extname"]: row["extversion"] for row in ext_rows}
            return {
                "status": "healthy" if alive else "unhealthy",
                "database": "postgresql",
                "postgis_version": extensions.get("postgis"),
                "pgvector_version": extensions.get("vector"),
                "extensions_ready": "postgis" in extensions and "vector" in extensions,
            }
        finally:
            await conn.close()
    except Exception as exc:
        return {
            "status": "unhealthy",
            "error": str(exc),
            "database": "postgresql",
            "extensions_ready": False,
        }
