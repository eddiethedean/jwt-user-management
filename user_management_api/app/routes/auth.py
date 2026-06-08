from __future__ import annotations

import logging
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
from app.core.email_validation import validate_email_format
from app.core.rate_limit import check_rate_limit
from app.core.security import (
    bump_token_version,
    create_access_token,
    decode_token,
    token_extra_claims,
    verify_password,
)
from app.db import get_db
from app.invite_email_domains import invite_email_domain_allowed
from app.models import User
from app.routes.deps import user_from_token
from app.routes.email_links import external_accept_invite_url
from app.services.directory import lookup_email_async
from app.services.email import send_self_registration_email
from app.services.tokens import create_invite_token_atomic
from app.web.csrf import issue_csrf_token, set_csrf_cookie, validate_csrf
from app.web.session import clear_auth_cookie, get_auth_token, set_auth_cookie
from app.web.templates import templates


router = APIRouter(tags=["auth"])
log = logging.getLogger("uvicorn.error")


def _wants_html(request: Request) -> bool:
    accept = (request.headers.get("accept") or "").lower()
    return "text/html" in accept


def _post_login_dest(user: User) -> str:
    if bool(getattr(user, "is_admin", False)):
        return "/admin"
    return "/account"


def _self_registration_enabled() -> bool:
    from app.core.config import settings as live_settings

    return live_settings.self_registration_enabled


def _self_registration_disabled_redirect(request: Request) -> Response:
    return safe_redirect(
        request,
        "/login?msg=Self-registration%20is%20not%20available.",
        status_code=303,
    )


def _self_registration_disabled_response(request: Request) -> Response:
    if _wants_html(request):
        return _self_registration_disabled_redirect(request)
    raise HTTPException(status_code=403, detail="Self-registration is disabled")


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
            rec = await lookup_email_async(email_n)
        except Exception:
            rec = None
        if settings.directory_lookup_required and not rec:
            return False, False, "Email not found in directory"

    if not (settings.smtp_host and settings.smtp_from_email):
        return False, False, "Self-registration email is not configured"

    raw = await create_invite_token_atomic(
        db, email=email_n, grant_admin=False, expires_hours=2
    )

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
) -> Response:
    if not _self_registration_enabled():
        return _self_registration_disabled_redirect(request)
    bp = base_path(request)
    csrf = issue_csrf_token(request)
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
    resp = templates.TemplateResponse(
        request,
        "register.html",
        {
            "request": request,
            "base_path": bp,
            "session_email": session_email,
            "csrf_token": csrf,
        },
    )
    set_csrf_cookie(resp, request=request)
    return resp


@router.post("/register")
async def register_submit(
    request: Request,
    email: str = Form(...),
    csrf_token: Optional[str] = Form(default=None),
    db: AsyncSession = Depends(get_db),
) -> Response:
    if not _self_registration_enabled():
        return _self_registration_disabled_response(request)
    validate_csrf(request, form_token=csrf_token)
    bp = base_path(request)
    try:
        email_n = validate_email_format(email)
    except ValueError as e:
        wants_html = _wants_html(request)
        if wants_html:
            csrf = issue_csrf_token(request)
            resp = templates.TemplateResponse(
                request,
                "register.html",
                {
                    "request": request,
                    "error": str(e),
                    "base_path": bp,
                    "csrf_token": csrf,
                },
                status_code=400,
            )
            set_csrf_cookie(resp, request=request)
            return resp
        raise HTTPException(status_code=400, detail=str(e))

    check_rate_limit(request, scope="register", email=email_n)
    wants_html = _wants_html(request)

    ok, _email_sent, err = await _register_user(request=request, email_n=email_n, db=db)

    if err:
        status = 503 if "not configured" in err.lower() else 400
        if wants_html:
            csrf = issue_csrf_token(request)
            resp = templates.TemplateResponse(
                request,
                "register.html",
                {
                    "request": request,
                    "error": err,
                    "base_path": bp,
                    "csrf_token": csrf,
                },
                status_code=status,
            )
            set_csrf_cookie(resp, request=request)
            return resp
        raise HTTPException(status_code=status, detail=err)

    if wants_html:
        csrf = issue_csrf_token(request)
        resp = templates.TemplateResponse(
            request,
            "login.html",
            {
                "request": request,
                "success": "Check your email for a link to set your password.",
                "base_path": bp,
                "csrf_token": csrf,
            },
        )
        set_csrf_cookie(resp, request=request)
        return resp
    return JSONResponse({"ok": ok})


@router.get("/login", response_class=HTMLResponse, include_in_schema=False)
async def login_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    bp = base_path(request)
    csrf = issue_csrf_token(request)
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
    resp = templates.TemplateResponse(
        request,
        "login.html",
        {
            "request": request,
            "base_path": bp,
            "info": info or None,
            "next": next_path or None,
            "session_email": session_email,
            "csrf_token": csrf,
        },
    )
    set_csrf_cookie(resp, request=request)
    return resp


@router.post("/login", response_class=HTMLResponse, include_in_schema=False)
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    csrf_token: Optional[str] = Form(default=None),
    db: AsyncSession = Depends(get_db),
) -> Response:
    validate_csrf(request, form_token=csrf_token)
    bp = base_path(request)
    try:
        email_n = validate_email_format(email)
    except ValueError:
        csrf = issue_csrf_token(request)
        resp = templates.TemplateResponse(
            request,
            "login.html",
            {
                "request": request,
                "error": "Invalid email or password",
                "base_path": bp,
                "email": (email or "").strip(),
                "csrf_token": csrf,
            },
            status_code=400,
        )
        set_csrf_cookie(resp, request=request)
        return resp
    check_rate_limit(request, scope="auth_login", email=email_n)
    user: Optional[User] = (
        await db.exec(select(User).where(User.email == email_n))
    ).first()
    csrf = issue_csrf_token(request)
    if not user or not verify_password(password, user.hashed_password):
        resp = templates.TemplateResponse(
            request,
            "login.html",
            {
                "request": request,
                "error": "Invalid email or password",
                "base_path": bp,
                "email": email_n,
                "csrf_token": csrf,
            },
            status_code=400,
        )
        set_csrf_cookie(resp, request=request)
        return resp
    if not getattr(user, "is_active", True):
        resp = templates.TemplateResponse(
            request,
            "login.html",
            {
                "request": request,
                "error": "Invalid email or password",
                "base_path": bp,
                "email": email_n,
                "csrf_token": csrf,
            },
            status_code=400,
        )
        set_csrf_cookie(resp, request=request)
        return resp
    token = create_access_token(
        subject=str(user.id),
        extra_claims=token_extra_claims(user),
    )
    dest = _post_login_dest(user)
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
async def logout(
    request: Request,
    csrf_token: Optional[str] = Form(default=None),
    db: AsyncSession = Depends(get_db),
) -> Response:
    validate_csrf(request, form_token=csrf_token)
    cookie_token = get_auth_token(request)
    if cookie_token:
        try:
            user = await user_from_token(db=db, token=cookie_token)
            bump_token_version(user)
            db.add(user)
            await db.commit()
        except HTTPException:
            pass
    resp = safe_external_redirect(request, "/login", status_code=303)
    clear_auth_cookie(resp, request=request)
    return resp


@router.post("/auth/token")
async def token(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        username = validate_email_format(form.username)
    except ValueError:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    check_rate_limit(request, scope="auth_token", email=username)
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
