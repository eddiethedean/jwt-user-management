from __future__ import annotations

import os

from starlette.requests import Request


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
    root_path = (
        str(request.scope.get("root_path") or "").rstrip("/")
        if include_root_path
        else ""
    )
    p = (path or "").strip()
    if not p.startswith("/"):
        p = "/" + p
    return external_base(request, public_base_url=public_base_url) + (
        root_path + p if root_path else p
    )
