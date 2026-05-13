from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from fastapi import Request
from fastapi_workbench import (
    external_ui_url,
    external_workbench_url,
    workbench_browser_base,
)

from app.core.config import settings


def _fluxlit_urls(request: Request) -> Any:
    return getattr(request.app.state, "fluxlit_urls", None)


def app_base(request: Request) -> str:
    urls = _fluxlit_urls(request)
    if urls is not None:
        return str(urls.app_base(request)).rstrip("/")
    return workbench_browser_base(
        request, public_base_url=settings.public_base_url or None
    )


def api_base(request: Request) -> str:
    urls = _fluxlit_urls(request)
    if urls is not None:
        return str(urls.api_base(request)).rstrip("/")
    return external_workbench_url(
        request,
        "/api",
        public_base_url=settings.public_base_url or None,
    ).rstrip("/")


def docs_url(request: Request) -> str:
    urls = _fluxlit_urls(request)
    if urls is not None:
        resolved = urls.docs_url(request)
        if resolved:
            return str(resolved)
    return external_workbench_url(
        request,
        "/api/docs",
        public_base_url=settings.public_base_url or None,
    )


def page_url(request: Request, *, page: str, token: str) -> str:
    urls = _fluxlit_urls(request)
    query = {"page": page, "token": token}
    if urls is not None:
        return str(urls.page_url(request, "/", query=query))
    return external_ui_url(
        request,
        f"/?{urlencode(query)}",
        public_base_url=settings.public_base_url or None,
    )


def email_browser_page_url(request: Request, *, page: str, token: str) -> str:
    """
    Public URL for emailed links (invites, self-registration, password reset).

    Uses :func:`fastapi_workbench.external_ui_url` so ``FLUXLIT_PUBLIC_BASE_URL``,
    ``PUBLIC_BASE_URL``, and Workbench ``root_path`` / Connect headers align with
    the browser app root (not the gateway ``/api`` subtree).
    """
    query = urlencode({"page": page, "token": token})
    return external_ui_url(
        request,
        f"/?{query}",
        public_base_url=settings.public_base_url or None,
    )
