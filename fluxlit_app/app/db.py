from __future__ import annotations

from collections.abc import AsyncGenerator, Generator

import sqlite3

import rapsqlite.sqlalchemy as rapsqlalchemy
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import Session, create_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings

# SQLAlchemy's SQLite base dialect expects the DBAPI module to expose sqlite_version_info.
# rapsqlite's dialect module doesn't provide it, so we bridge it from stdlib sqlite3.
if not hasattr(rapsqlalchemy._RapsqliteDialectModule, "sqlite_version_info"):
    rapsqlalchemy._RapsqliteDialectModule.sqlite_version_info = (
        sqlite3.sqlite_version_info
    )  # type: ignore[attr-defined]
if not hasattr(rapsqlalchemy._RapsqliteDialectModule, "sqlite_version"):
    rapsqlalchemy._RapsqliteDialectModule.sqlite_version = sqlite3.sqlite_version  # type: ignore[attr-defined]


connect_args: dict = {}
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(settings.database_url, echo=False, connect_args=connect_args)


def _async_db_url(url: str) -> str:
    """
    Keep DATABASE_URL as a sync URL for Alembic/tests (sqlite:///...),
    but use rapsqlite for the async app engine.
    """
    if url.startswith("sqlite://") and "+rapsqlite" not in url:
        return url.replace("sqlite://", "sqlite+rapsqlite://", 1)
    return url


async_engine: AsyncEngine = create_async_engine(
    _async_db_url(settings.database_url),
    echo=False,
    connect_args={},  # async sqlite drivers don't use check_same_thread
)
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
