#!/usr/bin/env python3
"""
Minimal reproduction for rapsqlite SQLAlchemy panic during ORM SELECT.

Observed on Posit Workbench (Python 3.10.4, rapsqlite 0.3.0) when POST /login
runs ``await db.exec(select(User).where(User.email == email))``.

Panic (Rust):
  thread 'tokio-runtime-worker' panicked at src/errors.rs:76:31:
  assertion failed: self.is_char_boundary(n)

Run (requires rapsqlite installed):
  pip install 'rapsqlite[sqlalchemy]==0.3.0' sqlmodel greenlet
  python scripts/rapsqlite_sqlalchemy_login_repro.py
"""

from __future__ import annotations

import asyncio
import os
import tempfile

from sqlmodel import Field, SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str
    hashed_password: str = ""


async def main() -> None:
    db_path = os.path.join(tempfile.gettempdir(), "rapsqlite_repro.db")
    url = f"sqlite+rapsqlite:///{db_path}"
    os.environ.setdefault("DATABASE_URL", url)

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(url, echo=True)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    SessionLocal = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with SessionLocal() as db:
        email_n = "admin@example.com"
        user = (await db.exec(select(User).where(User.email == email_n))).first()
        print("user:", user)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
