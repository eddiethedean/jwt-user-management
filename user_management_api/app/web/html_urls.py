"""Workbench-safe URL helpers for the HTML UI (templates and redirects)."""

from __future__ import annotations

from typing import Any

from fastapi import Request
from starlette.responses import Response

from fastapi_workbench import base_path, safe_external_redirect, safe_redirect


def html_base_path(request: Request) -> str:
    """Mount prefix for template links and form actions."""
    return base_path(request)


def html_ctx(request: Request, **extra: Any) -> dict[str, Any]:
    """Standard Jinja context keys for HTML pages behind a Workbench prefix."""
    return {"request": request, "base_path": html_base_path(request), **extra}


def html_redirect(
    request: Request,
    path: str,
    *,
    status_code: int = 303,
    external: bool = False,
) -> Response:
    """Redirect that respects Workbench ``root_path`` (relative or absolute)."""
    dest = (path or "").strip() or "/"
    if external:
        return safe_external_redirect(request, dest, status_code=status_code)
    return safe_redirect(request, dest, status_code=status_code)
