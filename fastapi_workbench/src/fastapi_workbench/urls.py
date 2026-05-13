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


def workbench_browser_base(
    request: Request, *, public_base_url: str | None = None
) -> str:
    """
    Public origin (and optional path prefix) for URLs users open in a browser.

    Resolution order:

    1. ``FLUXLIT_PUBLIC_BASE_URL`` — FluxLit / gateway often injects this while
       ``PUBLIC_BASE_URL`` in ``.env`` may still be a dev default.
    2. ``public_base_url`` (e.g. from application settings).
    3. ``PUBLIC_BASE_URL`` from the process environment.
    4. :attr:`Request.base_url` (same fallback as :func:`external_base`).
    """
    for candidate in (
        os.getenv("FLUXLIT_PUBLIC_BASE_URL"),
        public_base_url,
        os.getenv("PUBLIC_BASE_URL"),
    ):
        s = (candidate or "").strip().rstrip("/")
        if s:
            return s
    return str(request.base_url).rstrip("/")


def browser_app_mount_path(request: Request) -> str:
    """
    Path prefix for browser UI routes under the public base.

    When a gateway mounts the API under ``.../api``, ASGI ``root_path`` may end
    with ``/api`` while user-facing pages (e.g. Streamlit) live at the parent
    prefix. This returns :func:`base_path` with a trailing ``/api`` removed when
    present so UI links are not built under ``.../api/...``.
    """
    rp = base_path(request).rstrip("/")
    if rp.endswith("/api"):
        return rp[: -len("/api")].rstrip("/")
    return rp


def _join_public_base_and_mount(base: str, mount: str) -> str:
    b = base.rstrip("/")
    m = (mount or "").strip().rstrip("/")
    if not m:
        return b
    if b.endswith(m):
        return b
    return f"{b}{m}" if m.startswith("/") else f"{b}/{m}"


def external_ui_url(
    request: Request,
    path: str,
    *,
    public_base_url: str | None = None,
) -> str:
    """
    Absolute URL for a path under the browser app root (not the API subtree).

    Combines :func:`workbench_browser_base`, :func:`browser_app_mount_path`, and
    ``path`` (which should start with ``/`` and may include a query string).
    """
    p = (path or "").strip()
    if not p.startswith("/"):
        p = "/" + p
    eb = workbench_browser_base(request, public_base_url=public_base_url)
    mount = browser_app_mount_path(request)
    root = _join_public_base_and_mount(eb, mount)
    return root.rstrip("/") + p


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
