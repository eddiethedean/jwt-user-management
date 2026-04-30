from __future__ import annotations

import os
from urllib.parse import urljoin

from starlette.requests import Request


def external_base(request: Request, public_base_url: str | None = None) -> str:
    """
    Return an external browser-routable scheme://host base URL (no trailing slash).

    Precedence:
    - explicit `public_base_url`
    - env `PUBLIC_BASE_URL`
    - request.base_url (best-effort; may be internal behind some proxies)
    """
    base = (public_base_url or os.getenv("PUBLIC_BASE_URL") or "").strip().rstrip("/")
    if base:
        return base
    return str(request.base_url).rstrip("/")


def external_url(
    request: Request,
    path: str,
    *,
    include_root_path: bool = True,
    public_base_url: str | None = None,
) -> str:
    """
    Build an external URL for a path, optionally including request.scope['root_path'].

    - `path` may be absolute ('/login') or relative ('login'); we normalize it.
    - If include_root_path is True, prepends `scope['root_path']` (without trailing '/').
    """
    root_path = str(request.scope.get("root_path") or "").rstrip("/") if include_root_path else ""
    p = (path or "").strip()
    if not p.startswith("/"):
        p = "/" + p
    full_path = f"{root_path}{p}" if root_path else p
    return external_base(request, public_base_url=public_base_url) + full_path

