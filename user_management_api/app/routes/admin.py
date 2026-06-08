from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Path, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import text
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from fastapi_workbench import (
    base_path,
    safe_external_redirect,
    safe_redirect,
)
from app.core.config import settings
from app.core.email_validation import validate_email_format
from app.core.roles import (
    apply_user_roles,
    display_user_roles,
    effective_user_roles,
    normalize_selected_roles,
)
from app.db import get_db
from app.invite_email_domains import invite_email_domain_allowed
from app.models import User
from app.routes.deps import admin_from_bearer, bearer_scheme, user_from_token
from app.routes.email_links import external_accept_invite_url
from app.schemas.admin import AdminUpdateUserRequest
from app.services.directory import lookup_email_async
from app.services.email import send_invite_email
from app.services.tokens import create_invite_token_atomic
from app.web.csrf import issue_csrf_token, set_csrf_cookie, validate_csrf
from app.web.session import get_auth_token
from app.web.templates import templates


router = APIRouter(tags=["admin"])
log = logging.getLogger("uvicorn.error")


def _norm_email(v: str) -> str:
    return (v or "").strip().lower()


def _form_checkbox(value: Optional[str]) -> bool:
    """Parse HTML checkbox values; never use bool() on form strings."""
    return (value or "").strip().lower() in ("1", "on", "true")


@router.post("/admin/invite/lookup", response_class=Response, include_in_schema=False)
async def admin_invite_lookup(
    request: Request,
    token: Optional[str] = Form(default=None),
    email: str = Form(default=""),
    csrf_token: Optional[str] = Form(default=None),
    db: AsyncSession = Depends(get_db),
) -> Response:
    wants_json = "application/json" in (request.headers.get("accept") or "").lower()
    if not wants_json:
        return safe_redirect(request, "/admin", status_code=303)

    validate_csrf(request, form_token=csrf_token)
    cookie_token = get_auth_token(request)
    active_token = cookie_token or token
    if not active_token:
        return JSONResponse(
            {"ok": False, "error": "Not authenticated"}, status_code=401
        )

    _ = await user_from_token(db=db, token=active_token, require_admin=True)

    email_n = _norm_email(email)
    if not email_n:
        return JSONResponse(
            {"ok": False, "error": "Email is required"}, status_code=400
        )

    if not settings.directory_lookup_url:
        return JSONResponse({"ok": True})

    try:
        rec = await lookup_email_async(email_n)
    except Exception:
        return JSONResponse(
            {"ok": False, "error": "Directory lookup failed"},
            status_code=400,
        )

    if settings.directory_lookup_required and not rec:
        return JSONResponse(
            {"ok": False, "error": "Email not found in directory"},
            status_code=400,
        )

    return JSONResponse(
        {
            "ok": True,
            "email": getattr(rec, "email", "") if rec else "",
            "country": getattr(rec, "country", "") if rec else "",
        },
    )


@router.patch("/admin/users/{user_id}")
async def admin_api_update_user(
    user_id: int,
    payload: AdminUpdateUserRequest,
    db: AsyncSession = Depends(get_db),
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    admin = await admin_from_bearer(db=db, creds=creds)
    user = (await db.exec(select(User).where(User.id == user_id))).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    fields_set = payload.model_fields_set

    current_roles = effective_user_roles(user, settings.user_roles)

    if user.id == admin.id:
        if "is_active" in fields_set and payload.is_active != bool(user.is_active):
            raise HTTPException(
                status_code=400,
                detail="You can’t modify your own role/status here",
            )
        if "is_admin" in fields_set and payload.is_admin != bool(user.is_admin):
            raise HTTPException(
                status_code=400,
                detail="You can’t modify your own role/status here",
            )
        if "roles" in fields_set:
            next_roles = normalize_selected_roles(
                payload.roles or [], settings.user_roles
            )
            if next_roles != current_roles:
                raise HTTPException(
                    status_code=400,
                    detail="You can’t modify your own role/status here",
                )

    if "full_name" in fields_set:
        fn = str(payload.full_name or "").strip() or None
        user.full_name = fn
    if "is_active" in fields_set and payload.is_active is not None:
        user.is_active = payload.is_active
    if "roles" in fields_set:
        apply_user_roles(
            user,
            payload.roles or [],
            allowed_roles=settings.user_roles,
            admin_roles=settings.admin_roles,
        )
    elif "is_admin" in fields_set and payload.is_admin is not None:
        user.is_admin = payload.is_admin

    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {
        "ok": True,
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "country": user.country,
            "is_active": user.is_active,
            "is_admin": user.is_admin,
            "roles": display_user_roles(user, settings.user_roles),
            "created_at": user.created_at.isoformat(),
        },
    }


@router.delete("/admin/users/{user_id}")
async def admin_api_delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    admin = await admin_from_bearer(db=db, creds=creds)
    if admin.id == user_id:
        raise HTTPException(status_code=400, detail="You can’t delete your own account")
    user = (await db.exec(select(User).where(User.id == user_id))).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await db.delete(user)
    await db.commit()
    return {"ok": True}


@router.get("/admin", response_class=HTMLResponse, include_in_schema=False)
async def admin_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Response:
    bp = base_path(request)
    token = get_auth_token(request)
    if not token:
        return safe_redirect(
            request,
            "/login?msg=Please%20log%20in%20to%20view%20Admin.&next=/admin",
            status_code=303,
        )
    user = await user_from_token(db=db, token=token)
    if not getattr(user, "is_admin", False):
        return safe_redirect(
            request,
            "/account?msg=You%20don%E2%80%99t%20have%20admin%20privileges%20for%20this%20app.",
            status_code=303,
        )

    users = (await db.exec(select(User).order_by(text("id")))).all()
    csrf = issue_csrf_token(request)
    resp = templates.TemplateResponse(
        request,
        "admin.html",
        {
            "request": request,
            "users": users,
            "email": user.email,
            "session_email": user.email,
            "token": token,
            "base_path": bp,
            "invite_sent": False,
            "invite_error": None,
            "invite_email": "",
            "invite_grant_admin": False,
            "csrf_token": csrf,
        },
    )
    set_csrf_cookie(resp, request=request)
    return resp


@router.post("/admin/open", response_class=HTMLResponse, include_in_schema=False)
async def open_admin_from_page(
    request: Request,
    return_to: str = Form(...),
    csrf_token: Optional[str] = Form(default=None),
    db: AsyncSession = Depends(get_db),
) -> Response:
    validate_csrf(request, form_token=csrf_token)
    bp = base_path(request)
    token = get_auth_token(request)
    if not token:
        return safe_redirect(request, "/login", status_code=303)

    user = await user_from_token(db=db, token=token)
    if getattr(user, "is_admin", False):
        return safe_redirect(request, "../admin", status_code=303)

    msg = "You don’t have admin privileges for this app."
    if return_to == "token":
        redacted = f"{token[:8]}…{token[-4:]}" if len(token) > 16 else "<redacted>"
        return templates.TemplateResponse(
            request,
            "token.html",
            {
                "request": request,
                "token": redacted,
                "email": user.email,
                "session_email": user.email,
                "admin_error": msg,
                "base_path": bp,
            },
            status_code=403,
        )

    return safe_redirect(
        request,
        "/account?msg=You%20don%E2%80%99t%20have%20admin%20privileges%20for%20this%20app.",
        status_code=303,
    )


@router.post("/admin/invite", response_class=HTMLResponse, include_in_schema=False)
async def admin_invite_submit(
    request: Request,
    token: Optional[str] = Form(default=None),
    email: str = Form(default=""),
    grant_admin: Optional[str] = Form(default=None),
    csrf_token: Optional[str] = Form(default=None),
    db: AsyncSession = Depends(get_db),
) -> Response:
    validate_csrf(request, form_token=csrf_token)
    bp = base_path(request)
    wants_json = "application/json" in (request.headers.get("accept") or "").lower()
    cookie_token = get_auth_token(request)
    make_admin = _form_checkbox(grant_admin)
    active_token = cookie_token or token
    if not active_token:
        if wants_json:
            return JSONResponse(
                {"ok": False, "error": "Not authenticated"},
                status_code=401,
            )
        return safe_redirect(
            request,
            "/login?msg=Please%20log%20in%20to%20view%20Admin.&next=/admin",
            status_code=303,
        )
    admin_user = await user_from_token(db=db, token=active_token, require_admin=True)

    try:
        email_n = validate_email_format(email)
    except ValueError as e:
        err = str(e)
        if wants_json:
            return JSONResponse({"ok": False, "error": err}, status_code=400)
        users = (await db.exec(select(User).order_by(text("id")))).all()
        csrf = issue_csrf_token(request)
        resp = templates.TemplateResponse(
            request,
            "admin.html",
            {
                "request": request,
                "users": users,
                "email": admin_user.email,
                "session_email": admin_user.email,
                "token": active_token,
                "base_path": bp,
                "invite_sent": False,
                "invite_error": err,
                "invite_email": "",
                "invite_grant_admin": make_admin,
                "csrf_token": csrf,
            },
            status_code=400,
        )
        set_csrf_cookie(resp, request=request)
        return resp

    if not email_n:
        err = "Email is required."
        if wants_json:
            return JSONResponse({"ok": False, "error": err}, status_code=400)
        users = (await db.exec(select(User).order_by(text("id")))).all()
        return templates.TemplateResponse(
            request,
            "admin.html",
            {
                "request": request,
                "users": users,
                "email": admin_user.email,
                "session_email": admin_user.email,
                "token": active_token,
                "base_path": bp,
                "invite_sent": False,
                "invite_error": err,
                "invite_email": "",
                "invite_grant_admin": make_admin,
            },
            status_code=400,
        )

    if not invite_email_domain_allowed(email_n):
        err = "Email domain is not allowed for invites."
        if wants_json:
            return JSONResponse({"ok": False, "error": err}, status_code=422)
        users = (await db.exec(select(User).order_by(text("id")))).all()
        return templates.TemplateResponse(
            request,
            "admin.html",
            {
                "request": request,
                "users": users,
                "email": admin_user.email,
                "session_email": admin_user.email,
                "token": active_token,
                "base_path": bp,
                "invite_sent": False,
                "invite_error": err,
                "invite_email": email_n,
                "invite_grant_admin": make_admin,
            },
            status_code=422,
        )

    existing_user = (await db.exec(select(User).where(User.email == email_n))).first()
    if existing_user:
        err = "User already has an account."
        if wants_json:
            return JSONResponse({"ok": False, "error": err}, status_code=409)
        users = (await db.exec(select(User).order_by(text("id")))).all()
        return templates.TemplateResponse(
            request,
            "admin.html",
            {
                "request": request,
                "users": users,
                "email": admin_user.email,
                "session_email": admin_user.email,
                "token": active_token,
                "base_path": bp,
                "invite_sent": False,
                "invite_error": err,
                "invite_email": email_n,
                "invite_grant_admin": make_admin,
            },
            status_code=409,
        )

    if settings.directory_lookup_url:
        rec = None
        try:
            rec = await lookup_email_async(email_n)
        except Exception:
            rec = None
        if settings.directory_lookup_required and not rec:
            err = "Email not found in directory."
            if wants_json:
                return JSONResponse({"ok": False, "error": err}, status_code=400)
            users = (await db.exec(select(User).order_by(text("id")))).all()
            return templates.TemplateResponse(
                request,
                "admin.html",
                {
                    "request": request,
                    "users": users,
                    "email": admin_user.email,
                    "session_email": admin_user.email,
                    "token": active_token,
                    "base_path": bp,
                    "invite_sent": False,
                    "invite_error": err,
                    "invite_email": email_n,
                    "invite_grant_admin": make_admin,
                },
                status_code=400,
            )

    raw = await create_invite_token_atomic(db, email=email_n, grant_admin=make_admin)

    invite_url = external_accept_invite_url(request, token=raw)
    try:
        send_invite_email(to_email=email_n, invite_url=invite_url)
    except Exception:
        log.exception("invite_email_send_failed")

    if wants_json:
        return JSONResponse({"ok": True})

    users = (await db.exec(select(User).order_by(text("id")))).all()
    csrf = issue_csrf_token(request)
    resp = templates.TemplateResponse(
        request,
        "admin.html",
        {
            "request": request,
            "users": users,
            "email": admin_user.email,
            "token": active_token,
            "base_path": bp,
            "invite_sent": True,
            "invite_error": None,
            "invite_email": email_n,
            "invite_grant_admin": make_admin,
            "csrf_token": csrf,
        },
    )
    set_csrf_cookie(resp, request=request)
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
    bp = base_path(request)
    token = get_auth_token(request)
    if not token:
        return safe_redirect(request, "/login", status_code=303)
    admin_user = await user_from_token(db=db, token=token, require_admin=True)

    user = (await db.exec(select(User).where(User.id == user_id))).first()
    if not user:
        return templates.TemplateResponse(
            request,
            "admin_user_edit.html",
            {
                "request": request,
                "base_path": bp,
                "admin_email": admin_user.email,
                "session_email": admin_user.email,
                "is_self": bool(admin_user.id == user_id),
                "error": "User not found",
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

    csrf = issue_csrf_token(request)
    resp = templates.TemplateResponse(
        request,
        "admin_user_edit.html",
        {
            "request": request,
            "base_path": bp,
            "admin_email": admin_user.email,
            "session_email": admin_user.email,
            "is_self": bool(admin_user.id == user_id),
            "user": user,
            "csrf_token": csrf,
        },
    )
    set_csrf_cookie(resp, request=request)
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
    roles: list[str] = Form(default=[]),
    is_active: Optional[str] = Form(default=None),
    csrf_token: Optional[str] = Form(default=None),
    db: AsyncSession = Depends(get_db),
) -> Response:
    validate_csrf(request, form_token=csrf_token)
    token = get_auth_token(request)
    if not token:
        return safe_redirect(request, "/login", status_code=303)
    admin = await user_from_token(db=db, token=token, require_admin=True)

    user = (await db.exec(select(User).where(User.id == user_id))).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    new_active = _form_checkbox(is_active)
    current_roles = effective_user_roles(user, settings.user_roles)
    next_roles = normalize_selected_roles(roles, settings.user_roles)
    if user.id == admin.id:
        if new_active != bool(user.is_active) or next_roles != current_roles:
            raise HTTPException(
                status_code=400,
                detail="You can’t modify your own role/status here",
            )

    user.full_name = (full_name or "").strip() or None
    user.is_active = new_active
    apply_user_roles(
        user,
        roles,
        allowed_roles=settings.user_roles,
        admin_roles=settings.admin_roles,
    )
    db.add(user)
    await db.commit()

    return safe_redirect(request, "../" + str(user_id), status_code=303)


@router.post(
    "/admin/users/{user_id}/delete",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def admin_user_delete(
    request: Request,
    user_id: int = Path(..., ge=1),
    confirm: Optional[str] = Form(default=None),
    csrf_token: Optional[str] = Form(default=None),
    db: AsyncSession = Depends(get_db),
) -> Response:
    validate_csrf(request, form_token=csrf_token)
    bp = base_path(request)
    token = get_auth_token(request)
    if not token:
        return safe_redirect(request, "/login", status_code=303)
    admin_user = await user_from_token(db=db, token=token, require_admin=True)

    if admin_user.id == user_id:
        return templates.TemplateResponse(
            request,
            "admin_user_edit.html",
            {
                "request": request,
                "base_path": bp,
                "admin_email": admin_user.email,
                "session_email": admin_user.email,
                "user": admin_user,
                "is_self": True,
                "error": "You can’t delete your own account.",
            },
            status_code=400,
        )

    user = (await db.exec(select(User).where(User.id == user_id))).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not confirm:
        return templates.TemplateResponse(
            request,
            "admin_user_edit.html",
            {
                "request": request,
                "base_path": bp,
                "admin_email": admin_user.email,
                "session_email": admin_user.email,
                "user": user,
                "is_self": bool(admin_user.id == user_id),
                "error": "Please confirm deletion.",
            },
            status_code=400,
        )

    await db.delete(user)
    await db.commit()
    return safe_external_redirect(request, "/admin", status_code=303)
