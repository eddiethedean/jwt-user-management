from __future__ import annotations

import ssl
from collections.abc import AsyncGenerator, Generator

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import Session, create_engine
from sqlmodel.ext.asyncio.session import AsyncSession

import app.core.config as app_config


def _is_postgres_url(url: str) -> bool:
    return url.startswith("postgresql://") or url.startswith("postgres://")


connect_args: dict = {}
if app_config.settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    app_config.settings.database_url, echo=False, connect_args=connect_args
)


def _async_db_url(url: str) -> str:
    """
    Keep DATABASE_URL as a sync URL for Alembic/tests (sqlite:///...),
    but use aiosqlite or asyncpg for the async app engine.
    """
    if url.startswith("sqlite+rapsqlite://"):
        return url.replace("sqlite+rapsqlite://", "sqlite+aiosqlite://", 1)
    if url.startswith("sqlite://") and "+aiosqlite" not in url:
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    if _is_postgres_url(url):
        if not app_config.settings.postgres_async_enabled:
            raise RuntimeError(
                "POSTGRES_ASYNC_ENABLED is False but DATABASE_URL is PostgreSQL; "
                "the app requires asyncpg. Set POSTGRES_ASYNC_ENABLED=True or use SQLite."
            )
        if url.startswith("postgresql://") and "+asyncpg" not in url:
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if url.startswith("postgres://") and "+asyncpg" not in url:
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


def _async_connect_args(url: str) -> dict:
    if url.startswith("sqlite"):
        return {}
    if not (_is_postgres_url(url) and app_config.settings.postgres_async_enabled):
        return {}
    if app_config.settings.postgres_ssl_relaxed and "sslmode=require" in url:
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        return {"ssl": ssl_ctx}
    return {}


def _clean_async_postgres_url(url: str) -> str:
    if not app_config.settings.postgres_ssl_relaxed:
        return url
    return url.replace("?sslmode=require", "").replace("&sslmode=require", "")


def _build_async_engine() -> AsyncEngine:
    url = app_config.settings.database_url
    async_url = _clean_async_postgres_url(_async_db_url(url))
    return create_async_engine(
        async_url,
        echo=False,
        connect_args=_async_connect_args(url),
    )


async_engine: AsyncEngine = _build_async_engine()
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


def get_sync_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
