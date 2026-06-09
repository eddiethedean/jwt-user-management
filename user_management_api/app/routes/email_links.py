"""Workbench-safe absolute URLs for outbound email links (invites, self-registration)."""

from __future__ import annotations

from fastapi import Request
from fastapi_workbench import external_workbench_url

from app.core.config import settings


def external_accept_invite_url(request: Request, *, token: str) -> str:
    """Browser URL for accepting an invite or finishing self-registration."""
    return external_workbench_url(
        request,
        f"/invites/accept?token={token}",
        public_base_url=settings.public_base_url or None,
    )


def external_password_reset_url(request: Request, *, token: str) -> str:
    """Browser URL for the password reset page."""
    return external_workbench_url(
        request,
        f"/password/reset?token={token}",
        public_base_url=settings.public_base_url or None,
    )
