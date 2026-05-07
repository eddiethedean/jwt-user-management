from __future__ import annotations

import os
from urllib.parse import urlparse

from starlette.requests import Request


def base_path(request: Request) -> str:
    """
    Return the normalized mount prefix for this request (Workbench root_path).

    - If the app is mounted at the domain root, returns \"\".
    - If mounted under a prefix, returns that prefix without a trailing slash.
    """
    rp = str(request.scope.get("root_path") or "").rstrip("/")
    if rp:
        return rp

    # Posit Connect: Connect provides the application base URL via this header.
    # Example value: "https://connect.example.com/content/<guid>/".
    # We derive the mount prefix from the path component.
    base = (request.headers.get("rstudio-connect-app-base-url") or "").strip()
    if base:
        try:
            p = urlparse(base)
        except Exception:
            p = None
        if p and p.path:
            return str(p.path).rstrip("/")

    return ""


def external_base(request: Request, public_base_url: str | None = None) -> str:
    base = (public_base_url or os.getenv("PUBLIC_BASE_URL") or "").strip().rstrip("/")
    return base if base else str(request.base_url).rstrip("/")


def external_url(
    request: Request,
    path: str,
    *,
    include_root_path: bool = True,
    public_base_url: str | None = None,
) -> str:
    root_path = base_path(request) if include_root_path else ""
    p = (path or "").strip()
    if not p.startswith("/"):
        p = "/" + p
    return external_base(request, public_base_url=public_base_url) + (
        root_path + p if root_path else p
    )
