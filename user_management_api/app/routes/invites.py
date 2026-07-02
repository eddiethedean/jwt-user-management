from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.web.html_urls import html_base_path, html_redirect
import app.core.config as app_config
from app.core.audit import (
    log_invite_accept_failed,
    log_invite_accepted,
    log_invite_created,
    require_user_id,
)
from app.core.email_validation import validate_email_format
from app.core.logging import get_logger
from app.core.rate_limit import check_rate_limit
from app.core.security import validate_new_password
from app.db import get_db
from app.invite_email_domains import invite_email_domain_allowed
from app.models import InviteToken, User
from app.routes.deps import admin_from_bearer, bearer_scheme
from app.routes.email_links import external_accept_invite_url
from app.schemas.invites import (
    CreateInviteRequest,
    InspectInviteRequest,
    InviteAcceptRequest,
    InviteLookupRequest,
)
from app.services.directory import lookup_email_async
from app.user_profile import directory_record_to_lookup_dict, new_user_from_invite
from app.services.email import send_invite_email
from app.services.tokens import (
    create_invite_token_atomic,
    invalidate_unused_invite_tokens,
    try_consume_invite_token,
)
from app.web.csrf import issue_csrf_token, set_csrf_cookie, validate_csrf
from app.web.templates import templates


router = APIRouter(prefix="/invites", tags=["invites"])
log = get_logger(__name__)


def _as_utc_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _norm_email(v: str) -> str:
    return (v or "").strip().lower()


def validate_invite_email_for_create(email: str) -> str | None:
    """Return error message or None if invite may proceed (HTML admin preview)."""
    email_n = _norm_email(email)
    if not email_n:
        return "Email is required"
    if not invite_email_domain_allowed(email_n):
        return "Email domain is not allowed for invites"
    return None


def _invite_url(request: Request, token: str) -> str:
    return external_accept_invite_url(request, token=token)


async def invalidate_unused_invites_for_email(
    *, db: AsyncSession, email: str, now: datetime
) -> None:
    await invalidate_unused_invite_tokens(db, email=_norm_email(email), now=now)


async def _ensure_no_existing_user(db: AsyncSession, email: str) -> None:
    existing = (await db.exec(select(User).where(User.email == email))).first()
    if existing:
        raise HTTPException(status_code=409, detail="User already has an account")


@router.post("")
async def create_invite(
    request: Request,
    payload: CreateInviteRequest,
    db: AsyncSession = Depends(get_db),
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    admin = await admin_from_bearer(db=db, creds=creds)
    try:
        email = validate_email_format(payload.email)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if not invite_email_domain_allowed(email):
        raise HTTPException(
            status_code=422,
            detail="email domain is not allowed for invites",
        )

    await _ensure_no_existing_user(db, email)

    if (
        app_config.settings.directory_lookup_url
        and app_config.settings.directory_lookup_required
    ):
        try:
            rec = await lookup_email_async(email)
        except Exception:
            raise HTTPException(status_code=422, detail="directory lookup failed")
        if not rec:
            raise HTTPException(status_code=422, detail="email not found in directory")

    raw = await create_invite_token_atomic(
        db, email=email, grant_admin=payload.grant_admin
    )

    invite_url = external_accept_invite_url(request, token=raw)
    email_sent = False
    try:
        send_invite_email(to_email=email, invite_url=invite_url)
        email_sent = True
    except Exception:
        log.exception("invite_email_send_failed")
    if not email_sent:
        raise HTTPException(status_code=503, detail="Could not send invite email")

    invite_row = (
        await db.exec(
            select(InviteToken).where(
                InviteToken.token_hash == InviteToken.hash_token(raw)
            )
        )
    ).first()
    expires_at = invite_row.expires_at if invite_row else datetime.now(timezone.utc)

    log_invite_created(
        email=email,
        grant_admin=bool(payload.grant_admin),
        actor_email=admin.email,
        method="api_invite",
    )
    return {
        "ok": True,
        "invite_url": invite_url,
        "expires_at": expires_at,
    }


@router.post("/lookup")
async def lookup_invite_email(
    payload: InviteLookupRequest,
    db: AsyncSession = Depends(get_db),
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    await admin_from_bearer(db=db, creds=creds)
    try:
        email = validate_email_format(payload.email)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not app_config.settings.directory_lookup_url:
        return {"ok": True, **directory_record_to_lookup_dict(None)}
    rec = None
    try:
        rec = await lookup_email_async(email)
    except Exception:
        log.warning("invite_directory_preview_lookup_failed", exc_info=True)
    return {"ok": True, **directory_record_to_lookup_dict(rec)}


@router.post("/inspect")
async def inspect_invite_token(
    payload: InspectInviteRequest,
    db: AsyncSession = Depends(get_db),
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    await admin_from_bearer(db=db, creds=creds)
    token_hash = InviteToken.hash_token(payload.token)
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


@router.get("/accept", response_class=HTMLResponse, include_in_schema=False)
async def accept_invite_page(
    request: Request, token: str, db: AsyncSession = Depends(get_db)
) -> HTMLResponse:
    bp = html_base_path(request)
    csrf = issue_csrf_token(request)
    token_hash = InviteToken.hash_token(token)
    invite: Optional[InviteToken] = (
        await db.exec(select(InviteToken).where(InviteToken.token_hash == token_hash))
    ).first()
    if not invite:
        resp = templates.TemplateResponse(
            request,
            "accept_invite.html",
            {
                "request": request,
                "token": token,
                "error": "Invite not found",
                "base_path": bp,
                "csrf_token": csrf,
            },
            status_code=404,
        )
        set_csrf_cookie(resp, request=request)
        return resp
    resp = templates.TemplateResponse(
        request,
        "accept_invite.html",
        {
            "request": request,
            "token": token,
            "invite_email": invite.email,
            "base_path": bp,
            "csrf_token": csrf,
        },
    )
    set_csrf_cookie(resp, request=request)
    return resp


async def _accept(
    *,
    db: AsyncSession,
    token: str,
    password: str,
    full_name: str | None = None,
    country: str | None = None,
    command: str | None = None,
) -> None:
    from app.core.security import hash_password

    token_hash = InviteToken.hash_token(token)
    invite: Optional[InviteToken] = (
        await db.exec(select(InviteToken).where(InviteToken.token_hash == token_hash))
    ).first()
    if not invite:
        log_invite_accept_failed(reason="invite_not_found")
        raise HTTPException(status_code=404, detail="Invite not found")
    now = datetime.now(timezone.utc)
    if invite.used_at is not None:
        log_invite_accept_failed(reason="invite_already_used")
        raise HTTPException(status_code=400, detail="Invite already used")
    if _as_utc_aware(invite.expires_at) < now:
        log_invite_accept_failed(reason="invite_expired")
        raise HTTPException(status_code=400, detail="Invite expired")
    if not invite_email_domain_allowed(invite.email):
        log_invite_accept_failed(reason="domain_not_allowed")
        raise HTTPException(status_code=400, detail="Email domain is not allowed")

    existing = (await db.exec(select(User).where(User.email == invite.email))).first()
    if existing:
        log_invite_accept_failed(reason="user_already_exists")
        raise HTTPException(
            status_code=400,
            detail="An account with this email already exists",
        )

    consumed = await try_consume_invite_token(db, token_hash=token_hash, now=now)
    if consumed != 1:
        log_invite_accept_failed(reason="invite_already_used")
        raise HTTPException(status_code=400, detail="Invite already used")

    dup = (await db.exec(select(User).where(User.email == invite.email))).first()
    if dup:
        log_invite_accept_failed(reason="user_already_exists")
        raise HTTPException(
            status_code=400,
            detail="An account with this email already exists",
        )

    directory_rec = None
    if (
        app_config.settings.directory_lookup_url
        and app_config.settings.invite_accept_directory_enrich
    ):
        try:
            directory_rec = await lookup_email_async(invite.email)
        except Exception:
            directory_rec = None

    allow = app_config.settings.invite_accept_allow_profile_overrides
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
    try:
        await db.commit()
        await db.refresh(user)
    except IntegrityError:
        await db.rollback()
        log_invite_accept_failed(reason="user_already_exists")
        raise HTTPException(
            status_code=400,
            detail="An account with this email already exists",
        )
    log_invite_accepted(
        email=invite.email,
        user_id=require_user_id(user.id),
        grant_admin=bool(invite.grant_admin),
    )


@router.post("/accept-form", response_class=HTMLResponse, include_in_schema=False)
async def accept_invite_form(
    request: Request,
    token: str = Form(...),
    full_name: Optional[str] = Form(default=None),
    password: str = Form(...),
    csrf_token: Optional[str] = Form(default=None),
    db: AsyncSession = Depends(get_db),
) -> Response:
    bp = html_base_path(request)
    validate_csrf(request, form_token=csrf_token)
    check_rate_limit(request, scope="invites_accept")
    try:
        validate_new_password(password)
        await _accept(db=db, token=token, password=password, full_name=full_name)
    except HTTPException as e:
        log_invite_accept_failed(reason=str(e.detail))
        csrf = issue_csrf_token(request)
        token_hash = InviteToken.hash_token(token)
        invite: Optional[InviteToken] = (
            await db.exec(
                select(InviteToken).where(InviteToken.token_hash == token_hash)
            )
        ).first()
        resp = templates.TemplateResponse(
            request,
            "accept_invite.html",
            {
                "request": request,
                "token": token,
                "invite_email": invite.email if invite else "",
                "error": e.detail,
                "base_path": bp,
                "csrf_token": csrf,
            },
            status_code=e.status_code,
        )
        set_csrf_cookie(resp, request=request)
        return resp
    return html_redirect(request, "/login", status_code=303, external=True)


@router.post("/accept")
async def accept_invite_api(
    request: Request,
    payload: InviteAcceptRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    check_rate_limit(request, scope="invites_accept")
    try:
        validate_new_password(payload.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await _accept(
        db=db,
        token=payload.token,
        password=payload.password,
        full_name=payload.full_name,
        country=payload.country,
        command=payload.command,
    )
    return {"ok": True}
