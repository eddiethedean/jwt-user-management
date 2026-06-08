from __future__ import annotations

import os
from urllib.parse import urlparse

from starlette.requests import Request

from .detect import is_workbench_forced, is_workbench_scope
from .path_safety import (
    join_public_base_and_mount,
    path_segments,
    public_base_includes_mount,
    safe_url_path,
)


def base_path(request: Request) -> str:
    """
    Return the normalized mount prefix for this request (Workbench root_path).

    - If the app is mounted at the domain root, returns \"\".
    - If mounted under a prefix, returns that prefix without a trailing slash.
    """
    rp = str(request.scope.get("root_path") or "").rstrip("/")
    if rp:
        return rp

    if not is_workbench_scope(request.scope) and not is_workbench_forced():
        return ""

    base = (request.headers.get("rstudio-connect-app-base-url") or "").strip()
    if base:
        try:
            p = urlparse(base)
        except Exception:
            p = None
        if p and p.path:
            header_path = str(p.path).rstrip("/")
            if p.netloc:
                req_base = urlparse(str(request.base_url))
                if req_base.netloc and p.netloc != req_base.netloc:
                    return ""
            return header_path

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
    if not rp:
        return ""
    parts = path_segments(rp)
    if parts and parts[-1].lower() == "api":
        parent = "/" + "/".join(parts[:-1]) if len(parts) > 1 else ""
        return parent.rstrip("/")
    return rp


def merge_public_base_with_mount(
    request: Request, *, public_base_url: str | None = None
) -> str:
    """
    ``workbench_browser_base`` plus :func:`base_path`, without duplicating a trailing
    mount segment (e.g. when ``PUBLIC_BASE_URL`` already includes the Workbench prefix).
    """
    pub = workbench_browser_base(request, public_base_url=public_base_url)
    return join_public_base_and_mount(pub, base_path(request)).rstrip("/")


def external_workbench_url(
    request: Request,
    path: str,
    *,
    public_base_url: str | None = None,
    include_root_path: bool | None = None,
) -> str:
    """
    Like :func:`external_url` but resolves the public host via :func:`workbench_browser_base`.

    When ``include_root_path`` is ``None`` (default), it is ``False`` if the resolved
    public base already ends with :func:`base_path` (full browser URL in env), else
    ``True`` so Workbench/Connect mounts are applied once.
    """
    wb = workbench_browser_base(request, public_base_url=public_base_url)
    if include_root_path is None:
        bp = base_path(request).rstrip("/")
        inc = not public_base_includes_mount(wb, bp)
    else:
        inc = include_root_path
    return external_url(request, path, public_base_url=wb, include_root_path=inc)


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
    p = safe_url_path(path)
    eb = workbench_browser_base(request, public_base_url=public_base_url)
    mount = browser_app_mount_path(request)
    root = join_public_base_and_mount(eb, mount)
    return root.rstrip("/") + p


def external_url(
    request: Request,
    path: str,
    *,
    include_root_path: bool = True,
    public_base_url: str | None = None,
) -> str:
    root_path = base_path(request) if include_root_path else ""
    p = safe_url_path(path)
    return external_base(request, public_base_url=public_base_url) + (
        root_path + p if root_path else p
    )
