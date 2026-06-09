from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.auth.jwt_principal import (
    access_token_extra_claims_for_user,
    principal_from_request,
)
from app.core.security import (
    create_access_token,
    verify_password,
)
from app.db import get_db
from app.models import User
from app.services.self_registration import register_email_for_setup
import app.core.config as app_config
from app.web.csrf import issue_csrf_token, set_csrf_cookie, verify_csrf
from app.web.html_urls import html_ctx, html_redirect
from app.web.session import clear_auth_cookie, set_auth_cookie
from app.web.templates import templates


router = APIRouter(tags=["html-auth"])


def _norm_email(v: str) -> str:
    return (v or "").strip().lower()


def _wants_json(request: Request) -> bool:
    return "application/json" in (request.headers.get("accept") or "").lower()


def _session_email(request: Request) -> str | None:
    principal = principal_from_request(request)
    return principal.email if principal else None


@router.get("/register", response_class=HTMLResponse, include_in_schema=False)
async def register_page(
    request: Request, db: AsyncSession = Depends(get_db)
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "register.html",
        html_ctx(request, session_email=_session_email(request)),
    )


@router.get("/login", response_class=HTMLResponse, include_in_schema=False)
async def login_page(
    request: Request, db: AsyncSession = Depends(get_db)
) -> HTMLResponse:
    csrf = issue_csrf_token(request)
    resp = templates.TemplateResponse(
        request,
        "login.html",
        html_ctx(
            request,
            info=(request.query_params.get("msg") or "").strip() or None,
            next=(request.query_params.get("next") or "").strip() or None,
            session_email=_session_email(request),
            csrf_token=csrf,
        ),
    )
    set_csrf_cookie(resp, request)
    return resp


@router.post("/login", response_class=HTMLResponse, include_in_schema=False)
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next_path: str = Form(default=""),
    db: AsyncSession = Depends(get_db),
) -> Response:
    email_n = _norm_email(email)
    user: Optional[User] = (
        await db.exec(select(User).where(User.email == email_n))
    ).first()
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse(
            request,
            "login.html",
            html_ctx(request, error="Invalid email or password", email=email_n),
            status_code=400,
        )
    if not getattr(user, "is_active", True):
        return templates.TemplateResponse(
            request,
            "login.html",
            html_ctx(
                request,
                error="Your account has been disabled. Contact your admin.",
                email=email_n,
            ),
            status_code=403,
        )
    token = create_access_token(
        subject=str(user.id),
        extra_claims={
            **access_token_extra_claims_for_user(user),
        },
    )
    dest = (next_path or "").strip() or ("/admin" if user.is_admin else "/account")
    if not dest.startswith("/"):
        dest = "/" + dest
    resp = html_redirect(request, dest, status_code=303)
    set_auth_cookie(resp, request=request, token=token)
    set_csrf_cookie(resp, request)
    return resp


@router.post("/logout", include_in_schema=False)
async def logout(
    request: Request,
    csrf_token: str = Form(default=""),
) -> Response:
    verify_csrf(request, csrf_token)
    resp = html_redirect(request, "/login", status_code=303, external=True)
    clear_auth_cookie(resp, request=request)
    return resp


def _expose_setup_url() -> bool:
    import app.core.config as app_config

    return bool(getattr(app_config._defaults, "EXPOSE_SETUP_URLS_IN_RESPONSE", False))


async def register_handler(
    *,
    request: Request,
    email: str,
    db: AsyncSession,
) -> Response | dict:
    """Shared by API and HTML ``POST /register`` handlers."""
    result = await register_email_for_setup(request=request, email=email, db=db)
    if not result.ok:
        if _wants_json(request):
            return JSONResponse(
                {"ok": False, "error": result.error or "Registration failed"},
                status_code=400,
            )
        return templates.TemplateResponse(
            request,
            "register.html",
            html_ctx(request, error=result.error),
            status_code=400,
        )

    if _wants_json(request):
        body: dict = {"ok": True, "email_sent": result.email_sent}
        if (
            app_config.settings.smtp_host
            and app_config.settings.smtp_from_email
            and not result.email_sent
        ):
            return JSONResponse(
                {"detail": "Could not send registration email"},
                status_code=503,
            )
        if _expose_setup_url():
            body["setup_url"] = result.setup_url
        return body

    return templates.TemplateResponse(
        request,
        "login.html",
        html_ctx(
            request,
            success="Check your email for a link to set your password.",
        ),
    )
