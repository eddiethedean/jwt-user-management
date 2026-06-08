"""Invite and password-reset token lifecycle helpers."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession


def _db_now(now: datetime) -> str:
    return now.isoformat()


async def invalidate_unused_invite_tokens(
    db: AsyncSession, *, email: str, now: datetime
) -> None:
    await db.execute(
        text(
            "UPDATE invite_tokens SET used_at = :now "
            "WHERE email = :email AND used_at IS NULL"
        ),
        {"now": _db_now(now), "email": email},
    )


async def invalidate_unused_reset_tokens(
    db: AsyncSession, *, email: str, now: datetime
) -> None:
    await db.execute(
        text(
            "UPDATE password_reset_tokens SET used_at = :now "
            "WHERE email = :email AND used_at IS NULL"
        ),
        {"now": _db_now(now), "email": email},
    )


async def try_consume_invite_token(
    db: AsyncSession, *, token_hash: str, now: datetime
) -> int:
    """Atomically mark an invite used. Returns number of rows updated (0 or 1)."""
    result = await db.execute(
        text(
            "UPDATE invite_tokens SET used_at = :now "
            "WHERE token_hash = :token_hash AND used_at IS NULL"
        ),
        {"now": _db_now(now), "token_hash": token_hash},
    )
    return int(result.rowcount or 0)


async def try_consume_reset_token(
    db: AsyncSession, *, token_hash: str, now: datetime
) -> int:
    """Atomically mark a reset token used. Returns number of rows updated (0 or 1)."""
    result = await db.execute(
        text(
            "UPDATE password_reset_tokens SET used_at = :now "
            "WHERE token_hash = :token_hash AND used_at IS NULL"
        ),
        {"now": _db_now(now), "token_hash": token_hash},
    )
    return int(result.rowcount or 0)
