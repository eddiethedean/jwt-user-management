"""Invite and password-reset token lifecycle helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models import InviteToken, PasswordResetToken


async def _execute_sql(
    db: AsyncSession, statement: str, params: dict | None = None
) -> int:
    conn = await db.connection()
    result = await conn.execute(text(statement), params or {})
    return int(result.rowcount or 0)


async def invalidate_unused_invite_tokens(
    db: AsyncSession, *, email: str, now: datetime
) -> None:
    await _execute_sql(
        db,
        "UPDATE invite_tokens SET used_at = :now "
        "WHERE email = :email AND used_at IS NULL",
        {"now": now, "email": email},
    )


async def invalidate_unused_reset_tokens(
    db: AsyncSession, *, email: str, now: datetime
) -> None:
    await _execute_sql(
        db,
        "UPDATE password_reset_tokens SET used_at = :now "
        "WHERE email = :email AND used_at IS NULL",
        {"now": now, "email": email},
    )


async def try_consume_invite_token(
    db: AsyncSession, *, token_hash: str, now: datetime
) -> int:
    """Atomically mark an invite used. Returns number of rows updated (0 or 1)."""
    return await _execute_sql(
        db,
        "UPDATE invite_tokens SET used_at = :now "
        "WHERE token_hash = :token_hash AND used_at IS NULL",
        {"now": now, "token_hash": token_hash},
    )


async def try_consume_reset_token(
    db: AsyncSession, *, token_hash: str, now: datetime
) -> int:
    """Atomically mark a reset token used. Returns number of rows updated (0 or 1)."""
    return await _execute_sql(
        db,
        "UPDATE password_reset_tokens SET used_at = :now "
        "WHERE token_hash = :token_hash AND used_at IS NULL",
        {"now": now, "token_hash": token_hash},
    )


async def create_reset_token_atomic(
    db: AsyncSession, *, email: str, now: datetime | None = None
) -> str:
    """Invalidate prior reset tokens and create a new one in a serialized transaction."""
    now = now or datetime.now(timezone.utc)
    await _execute_sql(db, "BEGIN IMMEDIATE")
    await invalidate_unused_reset_tokens(db, email=email, now=now)
    raw = PasswordResetToken.new_raw_token()
    rec = PasswordResetToken(
        email=email,
        token_hash=PasswordResetToken.hash_token(raw),
        created_at=now,
        expires_at=now + timedelta(hours=2),
        used_at=None,
    )
    db.add(rec)
    await db.commit()
    return raw


async def create_invite_token_atomic(
    db: AsyncSession,
    *,
    email: str,
    grant_admin: bool,
    now: datetime | None = None,
    expires_days: int = 7,
    expires_hours: int | None = None,
) -> str:
    """Invalidate prior invite tokens and create a new one in a serialized transaction."""
    now = now or datetime.now(timezone.utc)
    if expires_hours is not None:
        expires_at = now + timedelta(hours=expires_hours)
    else:
        expires_at = now + timedelta(days=expires_days)
    await _execute_sql(db, "BEGIN IMMEDIATE")
    await invalidate_unused_invite_tokens(db, email=email, now=now)
    raw = InviteToken.new_raw_token()
    invite = InviteToken(
        email=email,
        token_hash=InviteToken.hash_token(raw),
        created_at=now,
        expires_at=expires_at,
        used_at=None,
        grant_admin=grant_admin,
    )
    db.add(invite)
    await db.commit()
    return raw
