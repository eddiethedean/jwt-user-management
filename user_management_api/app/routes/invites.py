from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import update
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.sql.expression import col

import app.core.config as app_config
from app.core.security import hash_password, validate_new_password
from app.db import get_db
from app.invite_email_domains import invite_email_domain_allowed
from app.models import InviteToken, User
from app.routes.deps import (
    admin_from_bearer,
    admin_principal_from_bearer,
    bearer_scheme,
)
from app.routes.email_links import external_accept_invite_url
from app.services.directory import lookup_email
from app.services.email import send_invite_email
from app.user_profile import (
    apply_profile_fields_to_user,
    directory_record_to_lookup_dict,
    enrich_user_from_directory,
    new_user_from_invite,
)


router = APIRouter(prefix="/invites", tags=["invites"])
log = logging.getLogger("uvicorn.error")


def _norm_email(v: str) -> str:
    return (v or "").strip().lower()


def _invite_url(request: Request, token: str) -> str:
    return external_accept_invite_url(request, token=token)


def _as_utc_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def validate_invite_email_for_create(email: str) -> str | None:
    """Return error message or None if invite may proceed."""
    email_n = _norm_email(email)
    if not email_n:
        return "Email is required"
    if not invite_email_domain_allowed(email_n):
        return "Email domain is not allowed for invites"
    if app_config.settings.directory_lookup_url:
        rec = None
        try:
            rec = lookup_email(email_n)
        except Exception:
            if app_config.settings.directory_lookup_required:
                return "Directory lookup failed"
            return None
        if app_config.settings.directory_lookup_required and not rec:
            return "Email not found in directory"
    return None


async def invalidate_unused_invites_for_email(
    *, db: AsyncSession, email: str, now: datetime
) -> None:
    email_n = _norm_email(email)
    invites = (
        await db.exec(
            select(InviteToken).where(
                InviteToken.email == email_n,
                col(InviteToken.used_at).is_(None),
            )
        )
    ).all()
    for inv in invites:
        inv.used_at = now
        db.add(inv)


async def _claim_invite_token(
    *, db: AsyncSession, token_hash: str, now: datetime
) -> InviteToken:
    stmt = (
        update(InviteToken)
        .where(
            col(InviteToken.token_hash) == token_hash,
            col(InviteToken.used_at).is_(None),
        )
        .values(used_at=now)
    )
    conn = await db.connection()
    result = await conn.execute(stmt)
    if result.rowcount != 1:
        existing = (
            await db.exec(
                select(InviteToken).where(InviteToken.token_hash == token_hash)
            )
        ).first()
        if not existing:
            raise HTTPException(status_code=404, detail="Invite not found")
        if existing.used_at is not None:
            raise HTTPException(status_code=400, detail="Invite already used")
        if _as_utc_aware(existing.expires_at) < now:
            raise HTTPException(status_code=400, detail="Invite expired")
        raise HTTPException(status_code=400, detail="Invite already used")
    invite = (
        await db.exec(select(InviteToken).where(InviteToken.token_hash == token_hash))
    ).first()
    assert invite is not None
    if _as_utc_aware(invite.expires_at) < now:
        raise HTTPException(status_code=400, detail="Invite expired")
    return invite


@router.post("")
async def create_invite(
    request: Request,
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    admin_principal_from_bearer(creds)
    email = _norm_email(str(payload.get("email") or ""))
    grant_admin = bool(payload.get("grant_admin") or False)
    err = validate_invite_email_for_create(email)
    if err:
        raise HTTPException(status_code=422, detail=err)

    now = datetime.now(timezone.utc)
    await invalidate_unused_invites_for_email(db=db, email=email, now=now)
    raw = InviteToken.new_raw_token()
    token_hash = InviteToken.hash_token(raw)
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
        log.exception("invite_email_send_failed")

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
    await admin_from_bearer(db=db, creds=creds)
    email = _norm_email(str(payload.get("email") or ""))
    if not email:
        raise HTTPException(status_code=422, detail="email is required")
    if not app_config.settings.directory_lookup_url:
        empty = directory_record_to_lookup_dict(None)
        return {"ok": True, **empty}
    rec = None
    try:
        rec = lookup_email(email)
    except Exception:
        log.warning("invite_directory_preview_lookup_failed", exc_info=True)
    fields = directory_record_to_lookup_dict(rec)
    return {"ok": True, **fields}


@router.post("/inspect")
async def inspect_invite_token(
    payload: dict = Body(...), db: AsyncSession = Depends(get_db)
) -> dict:
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
    *,
    db: AsyncSession,
    token: str,
    password: str,
    full_name: str | None = None,
    country: str | None = None,
    command: str | None = None,
) -> None:
    token_hash = InviteToken.hash_token(token)
    now = datetime.now(timezone.utc)
    invite = await _claim_invite_token(db=db, token_hash=token_hash, now=now)

    directory_rec = None
    if (
        app_config.settings.directory_lookup_url
        and app_config.settings.invite_accept_directory_enrich
    ):
        try:
            directory_rec = lookup_email(invite.email)
        except Exception:
            directory_rec = None

    allow = app_config.settings.invite_accept_allow_profile_overrides
    user = (await db.exec(select(User).where(User.email == invite.email))).first()
    if user:
        user.hashed_password = hash_password(password)
        user.is_admin = bool(user.is_admin or invite.grant_admin)
        apply_profile_fields_to_user(
            user,
            full_name=full_name,
            country=country,
            command=command,
            allow_overrides=allow,
        )
        if app_config.settings.invite_accept_directory_enrich:
            enrich_user_from_directory(user, directory_rec, fill_missing_only=True)
    else:
        user = new_user_from_invite(
            email=invite.email,
            password_hash=hash_password(password),
            is_admin=bool(invite.grant_admin),
            full_name=full_name if allow else None,
            country=country if allow else None,
            command=command if allow else None,
            directory_rec=directory_rec,
        )
        db.add(user)

    db.add(user)
    await db.commit()


@router.post("/accept")
async def accept_invite_api(
    payload: dict = Body(...), db: AsyncSession = Depends(get_db)
) -> dict:
    token = str(payload.get("token") or "")
    password = str(payload.get("password") or "")
    full_name = payload.get("full_name")
    country = payload.get("country")
    command = payload.get("command")
    full_name_s = None if full_name is None else str(full_name)
    country_s = None if country is None else str(country)
    command_s = None if command is None else str(command)
    if not token or not password:
        raise HTTPException(status_code=422, detail="token and password are required")
    try:
        validate_new_password(password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await _accept(
        db=db,
        token=token,
        password=password,
        full_name=full_name_s,
        country=country_s,
        command=command_s,
    )
    return {"ok": True}
