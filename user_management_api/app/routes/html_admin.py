from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Sequence

from fastapi import APIRouter, Depends, Form, HTTPException, Path, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from sqlalchemy import text
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

import app.core.config as app_config
from app.core.audit import (
    log_admin_access_denied,
    log_admin_user_deleted,
    log_admin_user_updated,
    log_invite_created,
    require_user_id,
)
from app.core.logging import get_logger
from app.auth.jwt_principal import (
    JwtPrincipal,
    load_user_by_id,
    require_cookie_principal,
)
from app.models import InviteToken, User
from app.routes.invites import _invite_url, validate_invite_email_for_create
from app.db import get_db
from app.services.email import send_invite_email
from app.web.csrf import set_csrf_cookie, verify_csrf
from app.web.html_deps import require_admin_cookie_principal
from app.web.html_urls import html_base_path, html_ctx, html_redirect
from app.web.session import get_auth_token
from app.web.templates import templates


router = APIRouter(tags=["html-admin"])
log = get_logger(__name__)


def _norm_email(v: str) -> str:
    return (v or "").strip().lower()


def _admin_ctx(
    *,
    request: Request,
    users: Sequence[User],
    principal: JwtPrincipal,
    token: str,
    **extra: Any,
) -> dict[str, Any]:
    email = principal.email or ""
    return html_ctx(
        request,
        users=users,
        email=email,
        session_email=email,
        token=token,
        show_command_field=app_config.settings.user_command_field_enabled,
        csrf_token=request.state.csrf_token,
        **extra,
    )


@router.post("/admin/invite/lookup", response_class=Response, include_in_schema=False)
async def admin_invite_lookup(
    request: Request,
    email: str = Form(default=""),
    csrf_token: str = Form(default=""),
    db: AsyncSession = Depends(get_db),
) -> Response:
    verify_csrf(request, csrf_token)
    wants_json = "application/json" in (request.headers.get("accept") or "").lower()
    if not wants_json:
        return html_redirect(request, "/admin", status_code=303)

    if not get_auth_token(request):
        return JSONResponse(
            {"ok": False, "error": "Not authenticated"}, status_code=401
        )

    _ = require_admin_cookie_principal(request)

    email_n = _norm_email(email)
    if not email_n:
        return JSONResponse(
            {"ok": False, "error": "Email is required"}, status_code=400
        )

    err = validate_invite_email_for_create(email_n)
    if err:
        return JSONResponse({"ok": False, "error": err}, status_code=400)

    if not app_config.settings.directory_lookup_url:
        return JSONResponse({"ok": True})

    from app.services.directory import lookup_email

    try:
        rec = lookup_email(email_n)
    except Exception:
        return JSONResponse(
            {"ok": False, "error": "Directory lookup failed"},
            status_code=400,
        )

    return JSONResponse(
        {
            "ok": True,
            "email": getattr(rec, "email", "") if rec else "",
            "country": getattr(rec, "country", "") if rec else "",
            "command": getattr(rec, "command", "") if rec else "",
        },
    )


@router.get("/admin", response_class=HTMLResponse, include_in_schema=False)
async def admin_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Response:
    bp = html_base_path(request)
    token = get_auth_token(request)
    if not token:
        return html_redirect(
            request,
            "/login?msg=Please%20log%20in%20to%20view%20Admin.&next=/admin",
            status_code=303,
        )
    principal = require_cookie_principal(request)
    if not principal.is_admin:
        log_admin_access_denied(
            email=principal.email,
            user_id=principal.user_id,
            path=request.url.path,
        )
        return templates.TemplateResponse(
            request,
            "users.html",
            {
                "request": request,
                "users": [],
                "email": principal.email or "",
                "session_email": principal.email or "",
                "is_admin": False,
                "admin_error": "You don't have admin privileges for this app.",
                "base_path": bp,
            },
            status_code=403,
        )

    users = (await db.exec(select(User).order_by(text("id")))).all()
    resp = templates.TemplateResponse(
        request,
        "admin.html",
        _admin_ctx(
            request=request,
            users=users,
            principal=principal,
            token=token,
            invite_url=None,
            invite_error=None,
            invite_email="",
            invite_grant_admin=False,
        ),
    )
    set_csrf_cookie(resp, request)
    return resp


@router.post("/admin/open", response_class=HTMLResponse, include_in_schema=False)
async def open_admin_from_page(
    request: Request,
    return_to: str = Form(...),
    csrf_token: str = Form(default=""),
    db: AsyncSession = Depends(get_db),
) -> Response:
    verify_csrf(request, csrf_token)
    bp = html_base_path(request)
    token = get_auth_token(request)
    if not token:
        return html_redirect(request, "/login", status_code=303)

    principal = require_cookie_principal(request)
    if principal.is_admin:
        return html_redirect(request, "/admin", status_code=303)

    msg = "You don't have admin privileges for this app."
    if return_to == "token":
        return templates.TemplateResponse(
            request,
            "token.html",
            {
                "request": request,
                "token": token,
                "email": principal.email or "",
                "session_email": principal.email or "",
                "admin_error": msg,
                "base_path": bp,
            },
            status_code=403,
        )

    return templates.TemplateResponse(
        request,
        "users.html",
        {
            "request": request,
            "users": [],
            "email": principal.email or "",
            "is_admin": False,
            "admin_error": msg,
            "base_path": bp,
        },
        status_code=403,
    )


@router.post("/admin/invite", response_class=HTMLResponse, include_in_schema=False)
async def admin_invite_submit(
    request: Request,
    email: str = Form(default=""),
    grant_admin: Optional[str] = Form(default=None),
    csrf_token: str = Form(default=""),
    db: AsyncSession = Depends(get_db),
) -> Response:
    verify_csrf(request, csrf_token)
    wants_json = "application/json" in (request.headers.get("accept") or "").lower()
    token = get_auth_token(request)
    if not token:
        if wants_json:
            return JSONResponse(
                {"ok": False, "error": "Not authenticated"},
                status_code=401,
            )
        return html_redirect(
            request,
            "/login?msg=Please%20log%20in%20to%20view%20Admin.&next=/admin",
            status_code=303,
        )
    principal = require_admin_cookie_principal(request)

    email_n = _norm_email(email)
    if not email_n:
        if wants_json:
            return JSONResponse(
                {"ok": False, "error": "Email is required"},
                status_code=400,
            )
        users = (await db.exec(select(User).order_by(text("id")))).all()
        resp = templates.TemplateResponse(
            request,
            "admin.html",
            _admin_ctx(
                request=request,
                users=users,
                principal=principal,
                token=token,
                invite_url=None,
                invite_error="Email is required.",
                invite_email="",
                invite_grant_admin=bool(grant_admin),
            ),
            status_code=400,
        )
        set_csrf_cookie(resp, request)
        return resp

    err = validate_invite_email_for_create(email_n)
    if err:
        if wants_json:
            return JSONResponse({"ok": False, "error": err}, status_code=400)
        users = (await db.exec(select(User).order_by(text("id")))).all()
        resp = templates.TemplateResponse(
            request,
            "admin.html",
            _admin_ctx(
                request=request,
                users=users,
                principal=principal,
                token=token,
                invite_url=None,
                invite_error=err + ".",
                invite_email=email_n,
                invite_grant_admin=bool(grant_admin),
            ),
            status_code=400,
        )
        set_csrf_cookie(resp, request)
        return resp

    make_admin = bool(grant_admin)
    now = datetime.now(timezone.utc)
    from app.routes.invites import invalidate_unused_invites_for_email

    await invalidate_unused_invites_for_email(db=db, email=email_n, now=now)
    raw = InviteToken.new_raw_token()
    invite = InviteToken(
        email=email_n,
        token_hash=InviteToken.hash_token(raw),
        created_at=now,
        expires_at=now + timedelta(days=7),
        used_at=None,
        grant_admin=make_admin,
    )
    db.add(invite)
    await db.commit()

    invite_url = _invite_url(request, raw)
    try:
        send_invite_email(to_email=email_n, invite_url=invite_url)
    except Exception:
        log.exception("invite_email_send_failed")

    log_invite_created(
        email=email_n,
        grant_admin=make_admin,
        actor_email=principal.email,
        method="html_admin",
    )

    if wants_json:
        return JSONResponse({"ok": True, "invite_url": invite_url})

    users = (await db.exec(select(User).order_by(text("id")))).all()
    resp = templates.TemplateResponse(
        request,
        "admin.html",
        _admin_ctx(
            request=request,
            users=users,
            principal=principal,
            token=token,
            invite_url=invite_url,
            invite_error=None,
            invite_email=email_n,
            invite_grant_admin=make_admin,
        ),
    )
    set_csrf_cookie(resp, request)
    return resp


@router.get(
    "/admin/users/{user_id}",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def admin_user_edit_page(
    request: Request,
    user_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
) -> Response:
    bp = html_base_path(request)
    token = get_auth_token(request)
    if not token:
        return html_redirect(request, "/login", status_code=303)
    principal = require_admin_cookie_principal(request)

    user = (await db.exec(select(User).where(User.id == user_id))).first()
    admin_email = principal.email or ""
    if not user:
        resp = templates.TemplateResponse(
            request,
            "admin_user_edit.html",
            {
                "request": request,
                "base_path": bp,
                "admin_email": admin_email,
                "session_email": admin_email,
                "is_self": bool(principal.user_id == user_id),
                "show_command_field": app_config.settings.user_command_field_enabled,
                "error": "User not found",
                "csrf_token": request.state.csrf_token,
                "user": {
                    "id": user_id,
                    "email": "",
                    "created_at": "",
                    "is_admin": False,
                    "is_active": False,
                },
            },
            status_code=404,
        )
        set_csrf_cookie(resp, request)
        return resp

    resp = templates.TemplateResponse(
        request,
        "admin_user_edit.html",
        {
            "request": request,
            "base_path": bp,
            "admin_email": admin_email,
            "session_email": admin_email,
            "is_self": bool(principal.user_id == user_id),
            "show_command_field": app_config.settings.user_command_field_enabled,
            "csrf_token": request.state.csrf_token,
            "user": user,
        },
    )
    set_csrf_cookie(resp, request)
    return resp


@router.post(
    "/admin/users/{user_id}/update",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def admin_user_update(
    request: Request,
    user_id: int = Path(..., ge=1),
    full_name: Optional[str] = Form(default=None),
    country: Optional[str] = Form(default=None),
    command: Optional[str] = Form(default=None),
    is_admin: Optional[str] = Form(default=None),
    is_active: Optional[str] = Form(default=None),
    csrf_token: str = Form(default=""),
    db: AsyncSession = Depends(get_db),
) -> Response:
    verify_csrf(request, csrf_token)
    token = get_auth_token(request)
    if not token:
        return html_redirect(request, "/login", status_code=303)
    principal = require_admin_cookie_principal(request)

    user = (await db.exec(select(User).where(User.id == user_id))).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if principal.user_id == user_id:
        if bool(is_admin) != bool(user.is_admin) or bool(is_active) != bool(
            user.is_active
        ):
            bp = html_base_path(request)
            admin_email = principal.email or ""
            resp = templates.TemplateResponse(
                request,
                "admin_user_edit.html",
                {
                    "request": request,
                    "base_path": bp,
                    "admin_email": admin_email,
                    "session_email": admin_email,
                    "is_self": True,
                    "show_command_field": app_config.settings.user_command_field_enabled,
                    "csrf_token": request.state.csrf_token,
                    "user": user,
                    "error": "You can't modify your own admin or active status here.",
                },
                status_code=400,
            )
            set_csrf_cookie(resp, request)
            return resp
    else:
        user.is_admin = bool(is_admin)
        user.is_active = bool(is_active)

    user.full_name = (full_name or "").strip() or None
    user.country = (country or "").strip() or None
    if app_config.settings.user_command_field_enabled:
        user.command = (command or "").strip() or None
    db.add(user)
    await db.commit()
    log_admin_user_updated(
        actor_email=principal.email or "",
        actor_id=principal.user_id,
        target_user_id=require_user_id(user.id),
        target_email=user.email,
        fields="full_name,country,command,is_admin,is_active",
        method="html_admin",
    )

    return html_redirect(request, f"/admin/users/{user_id}", status_code=303)


@router.post(
    "/admin/users/{user_id}/delete",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def admin_user_delete(
    request: Request,
    user_id: int = Path(..., ge=1),
    confirm: Optional[str] = Form(default=None),
    csrf_token: str = Form(default=""),
    db: AsyncSession = Depends(get_db),
) -> Response:
    verify_csrf(request, csrf_token)
    bp = html_base_path(request)
    token = get_auth_token(request)
    if not token:
        return html_redirect(request, "/login", status_code=303)
    principal = require_admin_cookie_principal(request)
    admin_user = await load_user_by_id(db=db, user_id=principal.user_id)

    if principal.user_id == user_id:
        resp = templates.TemplateResponse(
            request,
            "admin_user_edit.html",
            {
                "request": request,
                "base_path": bp,
                "admin_email": principal.email or admin_user.email,
                "session_email": principal.email or admin_user.email,
                "user": admin_user,
                "is_self": True,
                "show_command_field": app_config.settings.user_command_field_enabled,
                "csrf_token": request.state.csrf_token,
                "error": "You can't delete your own account.",
            },
            status_code=400,
        )
        set_csrf_cookie(resp, request)
        return resp

    user = (await db.exec(select(User).where(User.id == user_id))).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not confirm:
        resp = templates.TemplateResponse(
            request,
            "admin_user_edit.html",
            {
                "request": request,
                "base_path": bp,
                "admin_email": principal.email or admin_user.email,
                "session_email": principal.email or admin_user.email,
                "user": user,
                "is_self": False,
                "show_command_field": app_config.settings.user_command_field_enabled,
                "csrf_token": request.state.csrf_token,
                "error": "Please confirm deletion.",
            },
            status_code=400,
        )
        set_csrf_cookie(resp, request)
        return resp

    target_email = user.email
    await db.delete(user)
    await db.commit()
    log_admin_user_deleted(
        actor_email=principal.email or admin_user.email,
        actor_id=principal.user_id,
        target_user_id=user_id,
        target_email=target_email,
        method="html_admin",
    )
    return html_redirect(request, "/admin", status_code=303, external=True)
