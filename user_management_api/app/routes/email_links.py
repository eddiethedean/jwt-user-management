"""Workbench-safe absolute URLs for outbound email links (invites, self-registration)."""

from __future__ import annotations

from fastapi import Request
from fastapi_workbench import external_url

from app.core.config import settings


def external_accept_invite_url(request: Request, *, token: str) -> str:
    """
    Browser URL for accepting an invite or finishing self-registration (same path).

    Uses :func:`fastapi_workbench.external_url` with ``PUBLIC_BASE_URL`` and
    ``root_path`` / Connect headers so links match admin invite emails.
    """
    return external_url(
        request,
        f"/invites/accept?token={token}",
        public_base_url=settings.public_base_url,
    )
