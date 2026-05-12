from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.security import hash_password, validate_new_password
from app.db import get_db
from app.models import InviteToken, User
from app.routes.deps import admin_from_bearer, bearer_scheme
from app.routes.public_urls import page_url
from app.services.directory import lookup_email
from app.services.email import send_invite_email


router = APIRouter(prefix="/invites", tags=["invites"])


def _norm_email(v: str) -> str:
    return (v or "").strip().lower()


def _invite_url(request: Request, token: str) -> str:
    return page_url(request, page="Accept invite", token=token)


def _as_utc_aware(dt: datetime) -> datetime:
    """
    SQLite commonly returns naive datetimes even when we store timezone-aware values.
    Treat naive DB timestamps as UTC to keep comparisons consistent.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


async def _require_admin(
    db: AsyncSession, creds: Optional[HTTPAuthorizationCredentials]
) -> User:
    return await admin_from_bearer(db=db, creds=creds)


@router.post("")
async def create_invite(
    request: Request,
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    await _require_admin(db, creds)
    email = _norm_email(str(payload.get("email") or ""))
    grant_admin = bool(payload.get("grant_admin") or False)
    if not email:
        raise HTTPException(status_code=422, detail="email is required")

    if settings.directory_lookup_url:
        try:
            rec = lookup_email(email)
        except Exception:
            rec = None
        if settings.directory_lookup_required and not rec:
            raise HTTPException(status_code=422, detail="email not found in directory")

    raw = InviteToken.new_raw_token()
    token_hash = InviteToken.hash_token(raw)
    now = datetime.now(timezone.utc)
    invite = InviteToken(
        email=email,
        token_hash=token_hash,
        created_at=now,
        expires_at=now + timedelta(days=7),
        used_at=None,
        grant_admin=grant_admin,
    )
    db.add(invite)
    await db.commit()

    invite_url = _invite_url(request, raw)
    try:
        send_invite_email(to_email=email, invite_url=invite_url)
    except Exception:
        # Email should not break invite creation.
        pass

    return {
        "ok": True,
        "invite_url": invite_url,
        "expires_at": invite.expires_at,
    }


@router.post("/lookup")
async def lookup_invite_email(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    await _require_admin(db, creds)
    email = _norm_email(str(payload.get("email") or ""))
    if not email:
        raise HTTPException(status_code=422, detail="email is required")
    if not settings.directory_lookup_url:
        return {"ok": True}
    try:
        rec = lookup_email(email)
    except Exception:
        raise HTTPException(status_code=400, detail="Directory lookup failed")
    if settings.directory_lookup_required and not rec:
        raise HTTPException(status_code=422, detail="email not found in directory")
    return {
        "ok": True,
        "email": rec.email if rec else "",
        "country": rec.country if rec else "",
        "display_name": rec.display_name if rec else "",
    }


@router.post("/inspect")
async def inspect_invite_token(
    payload: dict = Body(...), db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Helper endpoint for non-HTML clients (e.g. Streamlit) to display the
    email bound to an invite token, matching the HTML accept page behavior.
    """
    token = str(payload.get("token") or "")
    if not token:
        raise HTTPException(status_code=422, detail="token is required")

    token_hash = InviteToken.hash_token(token)
    invite: Optional[InviteToken] = (
        await db.exec(select(InviteToken).where(InviteToken.token_hash == token_hash))
    ).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    return {
        "ok": True,
        "email": invite.email,
        "expires_at": invite.expires_at,
        "used_at": invite.used_at,
        "grant_admin": bool(invite.grant_admin),
    }


async def _accept(
    *, db: AsyncSession, token: str, password: str, full_name: str | None = None
) -> None:
    token_hash = InviteToken.hash_token(token)
    invite: Optional[InviteToken] = (
        await db.exec(select(InviteToken).where(InviteToken.token_hash == token_hash))
    ).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    now = datetime.now(timezone.utc)
    if invite.used_at is not None:
        raise HTTPException(status_code=400, detail="Invite already used")
    if _as_utc_aware(invite.expires_at) < now:
        raise HTTPException(status_code=400, detail="Invite expired")

    user = (await db.exec(select(User).where(User.email == invite.email))).first()
    if user:
        user.hashed_password = hash_password(password)
        user.is_admin = bool(user.is_admin or invite.grant_admin)
        if full_name is not None:
            fn = full_name.strip()
            if fn:
                user.full_name = fn
        if settings.directory_lookup_url:
            try:
                rec = lookup_email(invite.email)
            except Exception:
                rec = None
            if rec and rec.country and not user.country:
                user.country = rec.country
    else:
        fn = (full_name or "").strip() or None
        country = None
        if settings.directory_lookup_url:
            try:
                rec = lookup_email(invite.email)
            except Exception:
                rec = None
            if rec and rec.country:
                country = rec.country
        user = User(
            email=invite.email,
            full_name=fn,
            country=country,
            hashed_password=hash_password(password),
            is_admin=bool(invite.grant_admin),
        )
        db.add(user)
    invite.used_at = now
    db.add(invite)
    await db.commit()


@router.post("/accept")
async def accept_invite_api(
    payload: dict = Body(...), db: AsyncSession = Depends(get_db)
) -> dict:
    token = str(payload.get("token") or "")
    password = str(payload.get("password") or "")
    full_name = payload.get("full_name")
    full_name_s = None if full_name is None else str(full_name)
    if not token or not password:
        raise HTTPException(status_code=422, detail="token and password are required")
    try:
        validate_new_password(password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await _accept(db=db, token=token, password=password, full_name=full_name_s)
    return {"ok": True}
