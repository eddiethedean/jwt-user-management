"""Browser URLs for outbound email links (FluxLit UI query-param pages)."""

from __future__ import annotations

from fastapi import Request

from app.routes.public_urls import email_browser_page_url


def external_accept_invite_url(request: Request, *, token: str) -> str:
    return email_browser_page_url(request, page="Accept invite", token=token)


def external_password_reset_url(request: Request, *, token: str) -> str:
    return email_browser_page_url(request, page="Reset password", token=token)
