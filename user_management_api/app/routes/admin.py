from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Path, Query, Request
from fastapi.responses import HTMLResponse, Response, JSONResponse
from sqlalchemy import text
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from fastapi_workbench import base_path, external_url, safe_external_redirect, safe_redirect
from app.core.config import settings
from app.core.security import create_access_token, decode_token, verify_password
from app.db import get_db
from app.models import InviteToken, User
from app.services.directory import lookup_email
from app.services.email import send_invite_email
from app.web.session import get_auth_token, set_auth_cookie
from app.web.templates import templates


router = APIRouter(tags=["admin"])
log = logging.getLogger("uvicorn.error")

ADMIN_EMAIL = (os.getenv("SEED_ADMIN_EMAIL") or "admin@example.com").strip().lower()


def _norm_email(v: str) -> str:
    return (v or "").strip().lower()


def _invite_url(request: Request, token: str) -> str:
    return external_url(
        request,
        f"/invites/accept?token={token}",
        public_base_url=settings.public_base_url,
    )


async def _require_user(*, db: AsyncSession, token: str) -> User:
    try:
        payload: dict[str, Any] = decode_token(token)
        user_id = int(payload.get("sub") or 0)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = (await db.exec(select(User).where(User.id == user_id))).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user


async def _require_admin_user(*, db: AsyncSession, token: str) -> User:
    user = await _require_user(db=db, token=token)
    if not getattr(user, "is_admin", False):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@router.get("/admin", response_class=HTMLResponse, include_in_schema=False)
async def admin_page(
    request: Request,
    token: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> Response:
    bp = base_path(request)
    cookie_token = get_auth_token(request)
    if token:
        # If we were given a token via URL (legacy/demo mode), promote it into the
        # HttpOnly cookie and clean up the URL. If the user is not an admin, keep
        # them on the users page with a friendly message.
        user = await _require_user(db=db, token=token)
        resp = safe_redirect(request, "/admin", status_code=303)
        set_auth_cookie(resp, request=request, token=token)
        if not getattr(user, "is_admin", False):
            users = (await db.exec(select(User).order_by(text("id")))).all()
            return templates.TemplateResponse(
                request,
                "users.html",
                {
                    "request": request,
                    "users": users,
                    "email": user.email,
                    "session_email": user.email,
                    "is_admin": False,
                    "admin_error": "You don’t have admin privileges for this app.",
                    "base_path": bp,
                },
                status_code=403,
            )
        return resp

    token = cookie_token
    if not token:
        # No separate admin login page: send everyone to the normal login.
        return safe_redirect(
            request,
            "/login?msg=Please%20log%20in%20to%20view%20Admin.&next=/admin",
            status_code=303,
        )
    user = await _require_user(db=db, token=token)
    if not getattr(user, "is_admin", False):
        users = (await db.exec(select(User).order_by(text("id")))).all()
        return templates.TemplateResponse(
            request,
            "users.html",
            {
                "request": request,
                "users": users,
                "email": user.email,
                "session_email": user.email,
                "is_admin": False,
                "admin_error": "You don’t have admin privileges for this app.",
                "base_path": bp,
            },
            status_code=403,
        )

    users = (await db.exec(select(User).order_by(text("id")))).all()
    return templates.TemplateResponse(
        request,
        "admin.html",
        {
            "request": request,
            "users": users,
            "email": user.email,
            "session_email": user.email,
            "token": token,
            "base_path": bp,
            "invite_url": None,
            "invite_error": None,
            "invite_email": "",
            "invite_grant_admin": False,
        },
    )


@router.post("/admin/open", response_class=HTMLResponse, include_in_schema=False)
async def open_admin_from_page(
    request: Request,
    return_to: str = Form(...),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Used by "Open admin page" buttons so we can render a friendly message and keep
    the user on their current page if they are not an admin.
    """
    bp = base_path(request)
    token = get_auth_token(request)
    if not token:
        return safe_redirect(request, "/login", status_code=303)

    user = await _require_user(db=db, token=token)
    if getattr(user, "is_admin", False):
        # We are at /admin/open, so use a relative redirect.
        return safe_redirect(request, "../admin", status_code=303)

    msg = "You don’t have admin privileges for this app."
    if return_to == "token":
        return templates.TemplateResponse(
            request,
            "token.html",
            {
                "request": request,
                "token": token,
                "email": user.email,
                "session_email": user.email,
                "admin_error": msg,
                "base_path": bp,
            },
            status_code=403,
        )

    users = (await db.exec(select(User).order_by(text("id")))).all()
    return templates.TemplateResponse(
        request,
        "users.html",
        {
            "request": request,
            "users": users,
            "email": user.email,
            "is_admin": False,
            "admin_error": msg,
            "base_path": bp,
        },
        status_code=403,
    )


@router.post("/admin/invite", response_class=HTMLResponse, include_in_schema=False)
async def admin_invite_submit(
    request: Request,
    token: Optional[str] = Form(default=None),
    email: str = Form(...),
    grant_admin: Optional[str] = Form(default=None),
    db: AsyncSession = Depends(get_db),
) -> Response:
    bp = base_path(request)
    wants_json = "application/json" in (request.headers.get("accept") or "").lower()
    cookie_token = get_auth_token(request)
    active_token = cookie_token or token
    if not active_token:
        if wants_json:
            raise HTTPException(status_code=401, detail="Missing authentication token")
        return safe_redirect(
            request,
            "/login?msg=Please%20log%20in%20to%20view%20Admin.&next=/admin",
            status_code=303,
        )
    admin_user = await _require_admin_user(db=db, token=active_token)

    email_n = _norm_email(email)
    if not email_n:
        if wants_json:
            raise HTTPException(status_code=422, detail="email is required")
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
                "invite_url": None,
                "invite_error": "Email is required.",
                "invite_email": "",
                "invite_grant_admin": bool(grant_admin),
            },
            status_code=400,
        )

    # Optional directory-backed validation.
    if settings.directory_lookup_url:
        rec = None
        try:
            rec = lookup_email(email_n)
        except Exception:
            rec = None
        if settings.directory_lookup_required and not rec:
            if wants_json:
                raise HTTPException(status_code=422, detail="email not found in directory")
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
                    "invite_url": None,
                    "invite_error": "Email not found in directory.",
                    "invite_email": email_n,
                    "invite_grant_admin": bool(grant_admin),
                },
                status_code=400,
            )

    make_admin = bool(grant_admin)
    raw = InviteToken.new_raw_token()
    token_hash = InviteToken.hash_token(raw)
    now = datetime.now(timezone.utc)
    invite = InviteToken(
        email=email_n,
        token_hash=token_hash,
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
        pass

    if wants_json:
        return JSONResponse({"ok": True, "invite_url": invite_url})

    users = (await db.exec(select(User).order_by(text("id")))).all()
    return templates.TemplateResponse(
        request,
        "admin.html",
        {
            "request": request,
            "users": users,
            "email": admin_user.email,
            "token": active_token,
            "base_path": bp,
            "invite_url": invite_url,
            "invite_error": None,
            "invite_email": email_n,
            "invite_grant_admin": make_admin,
        },
    )


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
    admin_user = await _require_admin_user(db=db, token=token)

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

    return templates.TemplateResponse(
        request,
        "admin_user_edit.html",
        {
            "request": request,
            "base_path": bp,
            "admin_email": admin_user.email,
            "session_email": admin_user.email,
            "is_self": bool(admin_user.id == user_id),
            "user": user,
        },
    )


@router.post(
    "/admin/users/{user_id}/update",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def admin_user_update(
    request: Request,
    user_id: int = Path(..., ge=1),
    full_name: Optional[str] = Form(default=None),
    is_admin: Optional[str] = Form(default=None),
    is_active: Optional[str] = Form(default=None),
    db: AsyncSession = Depends(get_db),
) -> Response:
    token = get_auth_token(request)
    if not token:
        return safe_redirect(request, "/login", status_code=303)
    _ = await _require_admin_user(db=db, token=token)

    user = (await db.exec(select(User).where(User.id == user_id))).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    fn = (full_name or "").strip() or None
    user.full_name = fn
    user.is_admin = bool(is_admin)
    user.is_active = bool(is_active)
    db.add(user)
    await db.commit()

    # We are at /admin/users/<id>/update so redirect back relatively.
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
    db: AsyncSession = Depends(get_db),
) -> Response:
    bp = base_path(request)
    token = get_auth_token(request)
    if not token:
        return safe_redirect(request, "/login", status_code=303)
    admin_user = await _require_admin_user(db=db, token=token)

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
    # Use an external URL so redirect works from nested paths like /admin/users/<id>/delete.
    return safe_external_redirect(request, "/admin", status_code=303)
