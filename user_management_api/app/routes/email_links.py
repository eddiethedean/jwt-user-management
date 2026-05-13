"""Workbench-safe absolute URLs for outbound email links (invites, self-registration)."""

from __future__ import annotations

from urllib.parse import urlencode

from fastapi import Request
from fastapi_workbench import external_ui_url, external_workbench_url

from app.core.config import settings


def _ui_public_base() -> str | None:
    b = (settings.ui_public_base_url or "").strip().rstrip("/")
    return b or None


def external_accept_invite_url(request: Request, *, token: str) -> str:
    """
    Browser URL for accepting an invite or finishing self-registration (same path).

    When ``UI_PUBLIC_BASE_URL`` is set (Streamlit UI in Option A), uses the same
    ``/?page=...&token=...`` pattern as FluxLit so emailed links open the UI.

    Otherwise uses :func:`fastapi_workbench.external_workbench_url` for API-style
    paths and Workbench/Connect-aware bases.
    """
    ui = _ui_public_base()
    if ui:
        q = urlencode({"page": "Accept invite", "token": token})
        return external_ui_url(request, f"/?{q}", public_base_url=ui)
    return external_workbench_url(
        request,
        f"/invites/accept?token={token}",
        public_base_url=settings.public_base_url or None,
    )


def external_password_reset_url(request: Request, *, token: str) -> str:
    """Public URL for password reset emails (Streamlit query params or API path)."""
    ui = _ui_public_base()
    if ui:
        q = urlencode({"page": "Reset password", "token": token})
        return external_ui_url(request, f"/?{q}", public_base_url=ui)
    return external_workbench_url(
        request,
        f"/password/reset?token={token}",
        public_base_url=settings.public_base_url or None,
    )
