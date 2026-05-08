from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response, JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from fastapi_workbench import (
    base_path,
    external_url,
    safe_external_redirect,
    safe_redirect,
)
from app.core.config import settings
from app.core.security import (
    create_access_token,
    decode_token,
    verify_password,
)
from app.db import get_db
from app.models import InviteToken, User
from app.services.directory import lookup_email
from app.services.email import send_self_registration_email
from app.web.session import clear_auth_cookie, get_auth_token, set_auth_cookie
from app.web.templates import templates


router = APIRouter(tags=["auth"])


def _norm_email(v: str) -> str:
    return (v or "").strip().lower()


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


@router.post("/register", response_class=HTMLResponse, include_in_schema=False)
async def register_submit(
    request: Request,
    email: str = Form(...),
    db: AsyncSession = Depends(get_db),
) -> Response:
    bp = base_path(request)
    wants_json = "application/json" in (request.headers.get("accept") or "").lower()
    email_n = _norm_email(email)
    if not email_n:
        if wants_json:
            return JSONResponse(
                {"ok": False, "error": "Email is required"}, status_code=400
            )
        return templates.TemplateResponse(
            request,
            "register.html",
            {
                "request": request,
                "error": "Email is required",
                "base_path": bp,
            },
            status_code=400,
        )

    existing: Optional[User] = (
        await db.exec(select(User).where(User.email == email_n))
    ).first()
    if existing:
        if wants_json:
            return JSONResponse(
                {"ok": False, "error": "Email already exists"}, status_code=400
            )
        return templates.TemplateResponse(
            request,
            "register.html",
            {"request": request, "error": "Email already exists", "base_path": bp},
            status_code=400,
        )

    # Optional directory-backed validation for self-registration email.
    if settings.directory_lookup_url:
        rec = None
        try:
            rec = lookup_email(email_n)
        except Exception:
            rec = None
        if settings.directory_lookup_required and not rec:
            if wants_json:
                return JSONResponse(
                    {"ok": False, "error": "Email not found in directory"},
                    status_code=400,
                )
            return templates.TemplateResponse(
                request,
                "register.html",
                {
                    "request": request,
                    "error": "Email not found in directory.",
                    "base_path": bp,
                },
                status_code=400,
            )

    try:
        raw = InviteToken.new_raw_token()
        token_hash = InviteToken.hash_token(raw)
        now = datetime.now(timezone.utc)
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

        setup_url = external_url(
            request,
            f"/invites/accept?token={raw}",
            public_base_url=settings.public_base_url,
        )
        send_self_registration_email(to_email=email_n, setup_url=setup_url)
    except Exception:
        # Email should not block successful registration.
        pass
    if wants_json:
        return JSONResponse({"ok": True})
    return templates.TemplateResponse(
        request,
        "login.html",
        {
            "request": request,
            "success": "Check your email for a link to set your password.",
            "base_path": bp,
        },
    )


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
) -> HTMLResponse:
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
        extra_claims={"country": user.country}
        if getattr(user, "country", None)
        else None,
    )
    dest = "/admin" if bool(getattr(user, "is_admin", False)) else "/users"
    resp = safe_redirect(request, dest, status_code=303)
    set_auth_cookie(resp, request=request, token=token)
    return resp


@router.post("/logout", include_in_schema=False)
async def logout(request: Request) -> Response:
    resp = safe_external_redirect(
        request,
        "/login",
        status_code=303,
    )
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
        extra_claims={"country": user.country}
        if getattr(user, "country", None)
        else None,
    )
    return {"access_token": access_token, "token_type": "bearer"}
