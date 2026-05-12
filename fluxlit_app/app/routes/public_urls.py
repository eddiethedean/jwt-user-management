from __future__ import annotations

from typing import Any

from fastapi import Request

from app.core.config import settings


def _request_origin(request: Request) -> str:
    url = request.url
    return f"{url.scheme}://{url.netloc}".rstrip("/")


def _join_url(base: str, *parts: str) -> str:
    out = base.rstrip("/")
    for part in parts:
        if not part:
            continue
        p = part if part.startswith("/") else f"/{part}"
        out = f"{out}{p}"
    return out


def _fallback_app_base(request: Request) -> str:
    public = (settings.public_base_url or "").strip()
    if public:
        return public.rstrip("/")
    root_path = str(request.scope.get("root_path") or "").rstrip("/")
    return (
        _join_url(_request_origin(request), root_path)
        if root_path
        else _request_origin(request)
    )


def _fluxlit_urls(request: Request) -> Any:
    return getattr(request.app.state, "fluxlit_urls", None)


def app_base(request: Request) -> str:
    urls = _fluxlit_urls(request)
    if urls is not None:
        return str(urls.app_base(request)).rstrip("/")
    return _fallback_app_base(request)


def api_base(request: Request) -> str:
    urls = _fluxlit_urls(request)
    if urls is not None:
        return str(urls.api_base(request)).rstrip("/")
    return _join_url(app_base(request), "/api")


def docs_url(request: Request) -> str:
    urls = _fluxlit_urls(request)
    if urls is not None:
        resolved = urls.docs_url(request)
        if resolved:
            return str(resolved)
    return _join_url(api_base(request), "/docs")


def page_url(request: Request, *, page: str, token: str) -> str:
    urls = _fluxlit_urls(request)
    query = {"page": page, "token": token}
    if urls is not None:
        return str(urls.page_url(request, "/", query=query))
    from urllib.parse import urlencode

    return f"{_join_url(app_base(request), '/')}?{urlencode(query)}"
