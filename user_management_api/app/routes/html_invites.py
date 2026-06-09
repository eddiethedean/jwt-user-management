from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

import app.core.config as app_config
from app.core.security import validate_new_password
from app.db import get_db
from app.models import InviteToken
from app.routes.invites import _accept
from app.services.directory import lookup_email
from app.web.html_urls import html_base_path, html_redirect
from app.web.templates import templates


router = APIRouter(prefix="/invites", tags=["html-invites"])


@router.get("/accept", response_class=HTMLResponse, include_in_schema=False)
async def accept_invite_page(
    request: Request, token: str, db: AsyncSession = Depends(get_db)
) -> HTMLResponse:
    bp = html_base_path(request)
    token_hash = InviteToken.hash_token(token)
    invite: Optional[InviteToken] = (
        await db.exec(select(InviteToken).where(InviteToken.token_hash == token_hash))
    ).first()
    if not invite:
        return templates.TemplateResponse(
            request,
            "accept_invite.html",
            {
                "request": request,
                "token": token,
                "error": "Invite not found",
                "base_path": bp,
                "min_password_length": app_config.settings.min_password_length,
                "show_command_field": app_config.settings.user_command_field_enabled,
            },
            status_code=404,
        )

    display_name = ""
    country = ""
    command = ""
    if (
        app_config.settings.directory_lookup_url
        and app_config.settings.invite_accept_directory_enrich
    ):
        try:
            rec = lookup_email(invite.email)
            if rec:
                display_name = getattr(rec, "display_name", "") or ""
                country = getattr(rec, "country", "") or ""
                command = getattr(rec, "command", "") or ""
        except Exception:
            pass

    return templates.TemplateResponse(
        request,
        "accept_invite.html",
        {
            "request": request,
            "token": token,
            "invite_email": invite.email,
            "display_name": display_name,
            "country": country,
            "command": command,
            "base_path": bp,
            "min_password_length": app_config.settings.min_password_length,
            "show_command_field": app_config.settings.user_command_field_enabled,
        },
    )


@router.post("/accept-form", response_class=HTMLResponse, include_in_schema=False)
async def accept_invite_form(
    request: Request,
    token: str = Form(...),
    full_name: Optional[str] = Form(default=None),
    country: Optional[str] = Form(default=None),
    command: Optional[str] = Form(default=None),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
) -> Response:
    bp = html_base_path(request)
    ctx_extra = {
        "min_password_length": app_config.settings.min_password_length,
        "show_command_field": app_config.settings.user_command_field_enabled,
    }
    try:
        validate_new_password(password)
        await _accept(
            db=db,
            token=token,
            password=password,
            full_name=full_name,
            country=country,
            command=command if app_config.settings.user_command_field_enabled else None,
        )
    except HTTPException as e:
        token_hash = InviteToken.hash_token(token)
        invite: Optional[InviteToken] = (
            await db.exec(
                select(InviteToken).where(InviteToken.token_hash == token_hash)
            )
        ).first()
        return templates.TemplateResponse(
            request,
            "accept_invite.html",
            {
                "request": request,
                "token": token,
                "invite_email": invite.email if invite else "",
                "error": e.detail,
                "base_path": bp,
                **ctx_extra,
            },
            status_code=e.status_code,
        )
    except ValueError as e:
        token_hash = InviteToken.hash_token(token)
        invite: Optional[InviteToken] = (
            await db.exec(
                select(InviteToken).where(InviteToken.token_hash == token_hash)
            )
        ).first()
        return templates.TemplateResponse(
            request,
            "accept_invite.html",
            {
                "request": request,
                "token": token,
                "invite_email": invite.email if invite else "",
                "error": str(e),
                "base_path": bp,
                **ctx_extra,
            },
            status_code=400,
        )

    return html_redirect(request, "/login", status_code=303, external=True)
