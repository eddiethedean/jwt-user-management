"""Workbench-safe absolute URLs for outbound email links (invites, self-registration)."""

from __future__ import annotations

from fastapi import Request
from fastapi_workbench import external_workbench_url

from app.core.config import settings


def external_accept_invite_url(request: Request, *, token: str) -> str:
    """
    Browser URL for accepting an invite or finishing self-registration (same path).

    Uses :func:`fastapi_workbench.external_workbench_url` so ``FLUXLIT_PUBLIC_BASE_URL``,
    ``PUBLIC_BASE_URL``, settings, and Workbench ``root_path`` / Connect headers stay
    consistent with other outbound links.
    """
    return external_workbench_url(
        request,
        f"/invites/accept?token={token}",
        public_base_url=settings.public_base_url or None,
    )
