from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from fastapi_workbench import (
    base_path,
    safe_external_redirect,
    safe_redirect,
)
from app.core.config import settings
from app.core.security import (
    create_access_token,
    decode_token,
    token_extra_claims,
    verify_password,
)
from app.db import get_db
from app.invite_email_domains import invite_email_domain_allowed
from app.models import InviteToken, User
from app.routes.email_links import external_accept_invite_url
from app.services.directory import lookup_email
from app.services.email import send_self_registration_email
from app.services.tokens import invalidate_unused_invite_tokens
from app.web.session import clear_auth_cookie, get_auth_token, set_auth_cookie
from app.web.templates import templates


router = APIRouter(tags=["auth"])
log = logging.getLogger("uvicorn.error")


def _norm_email(v: str) -> str:
    return (v or "").strip().lower()


def _wants_html(request: Request) -> bool:
    accept = (request.headers.get("accept") or "").lower()
    return "text/html" in accept


async def _register_user(
    *,
    request: Request,
    email_n: str,
    db: AsyncSession,
) -> tuple[bool, bool, Optional[str]]:
    """
    Create a self-registration invite and send email.
    Returns (ok, email_sent, error_message).
    """
    if not email_n:
        return False, False, "Email is required"

    existing: Optional[User] = (
        await db.exec(select(User).where(User.email == email_n))
    ).first()
    if existing:
        return True, False, None

    if not invite_email_domain_allowed(email_n):
        return False, False, "Email domain is not allowed for registration"

    if settings.directory_lookup_url:
        rec = None
        try:
            rec = lookup_email(email_n)
        except Exception:
            rec = None
        if settings.directory_lookup_required and not rec:
            return False, False, "Email not found in directory"

    if not (settings.smtp_host and settings.smtp_from_email):
        return False, False, "Self-registration email is not configured"

    raw = InviteToken.new_raw_token()
    token_hash = InviteToken.hash_token(raw)
    now = datetime.now(timezone.utc)
    await invalidate_unused_invite_tokens(db, email=email_n, now=now)
    invite = InviteToken(
        email=email_n,
        token_hash=token_hash,
        created_at=now,
        expires_at=now + timedelta(hours=2),
        used_at=None,
        grant_admin=False,
    )
    db.add(invite)
    await db.commit()

    setup_url = external_accept_invite_url(request, token=raw)
    email_sent = False
    try:
        send_self_registration_email(to_email=email_n, setup_url=setup_url)
        email_sent = True
    except Exception:
        log.exception("self_registration_email_send_failed")

    return True, email_sent, None


@router.get("/register", response_class=HTMLResponse, include_in_schema=False)
async def register_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    bp = base_path(request)
    session_email = None
    cookie_token = get_auth_token(request)
    if cookie_token:
        try:
            payload = decode_token(cookie_token)
            user_id = int(payload.get("sub") or 0)
            user = (await db.exec(select(User).where(User.id == user_id))).first()
            session_email = user.email if user else None
        except Exception:
            session_email = None
    return templates.TemplateResponse(
        request,
        "register.html",
        {"request": request, "base_path": bp, "session_email": session_email},
    )


@router.post("/register")
async def register_submit(
    request: Request,
    email: str = Form(...),
    db: AsyncSession = Depends(get_db),
) -> Response:
    bp = base_path(request)
    email_n = _norm_email(email)
    wants_html = _wants_html(request)

    ok, email_sent, err = await _register_user(
        request=request, email_n=email_n, db=db
    )

    if err:
        status = 503 if "not configured" in err.lower() else 400
        if wants_html:
            return templates.TemplateResponse(
                request,
                "register.html",
                {"request": request, "error": err, "base_path": bp},
                status_code=status,
            )
        raise HTTPException(status_code=status, detail=err)

    if wants_html:
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "request": request,
                "success": "Check your email for a link to set your password.",
                "base_path": bp,
            },
        )
    return JSONResponse({"ok": ok, "email_sent": email_sent})


@router.get("/login", response_class=HTMLResponse, include_in_schema=False)
async def login_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    bp = base_path(request)
    info = (request.query_params.get("msg") or "").strip()
    next_path = (request.query_params.get("next") or "").strip()
    session_email = None
    cookie_token = get_auth_token(request)
    if cookie_token:
        try:
            payload = decode_token(cookie_token)
            user_id = int(payload.get("sub") or 0)
            user = (await db.exec(select(User).where(User.id == user_id))).first()
            session_email = user.email if user else None
        except Exception:
            session_email = None
    return templates.TemplateResponse(
        request,
        "login.html",
        {
            "request": request,
            "base_path": bp,
            "info": info or None,
            "next": next_path or None,
            "session_email": session_email,
        },
    )


@router.post("/login", response_class=HTMLResponse, include_in_schema=False)
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
) -> Response:
    bp = base_path(request)
    email_n = _norm_email(email)
    user: Optional[User] = (
        await db.exec(select(User).where(User.email == email_n))
    ).first()
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "request": request,
                "error": "Invalid email or password",
                "base_path": bp,
                "email": email_n,
            },
            status_code=400,
        )
    if not getattr(user, "is_active", True):
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "request": request,
                "error": "Your account has been disabled. Contact your admin.",
                "base_path": bp,
                "email": email_n,
            },
            status_code=403,
        )
    token = create_access_token(
        subject=str(user.id),
        extra_claims=token_extra_claims(user),
    )
    dest = "/admin" if bool(getattr(user, "is_admin", False)) else "/users"
    if bool(getattr(settings, "cookie_debug", False)):
        resp = HTMLResponse(content="", status_code=200)
        set_auth_cookie(resp, request=request, token=token)
        logs = getattr(request.state, "cookie_debug_logs", None)
        if not isinstance(logs, list):
            logs = []
        logs.append("cookie:set_cookie_header | value=<redacted>")
        body = templates.get_template("debug_redirect.html").render(
            {
                "request": request,
                "base_path": bp,
                "dest": bp + dest,
                "cookie_debug_logs": logs,
            }
        )
        resp.body = body.encode("utf-8")
        resp.headers["content-length"] = str(len(resp.body))
        return resp

    resp = safe_redirect(request, dest, status_code=303)
    set_auth_cookie(resp, request=request, token=token)
    return resp


@router.post("/logout", include_in_schema=False)
async def logout(request: Request) -> Response:
    resp = safe_external_redirect(request, "/login", status_code=303)
    clear_auth_cookie(resp, request=request)
    return resp


@router.post("/auth/token")
async def token(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> dict:
    username = _norm_email(form.username)
    user: Optional[User] = (
        await db.exec(select(User).where(User.email == username))
    ).first()
    if (
        not user
        or not getattr(user, "is_active", True)
        or not verify_password(form.password, user.hashed_password)
    ):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    access_token = create_access_token(
        subject=str(user.id),
        extra_claims=token_extra_claims(user),
    )
    return {"access_token": access_token, "token_type": "bearer"}
