"""Invite and password-reset token lifecycle helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models import InviteToken, PasswordResetToken


def _db_now(now: datetime) -> str:
    """Bound parameter for rapsqlite (no native datetime bind support)."""
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


async def create_reset_token_atomic(
    db: AsyncSession, *, email: str, now: datetime | None = None
) -> str:
    """Invalidate prior reset tokens and create a new one in a serialized transaction."""
    now = now or datetime.now(timezone.utc)
    await db.execute(text("BEGIN IMMEDIATE"))
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
    await db.execute(text("BEGIN IMMEDIATE"))
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
