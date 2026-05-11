"""Cookie debug middleware (same behavior as ``user_management_api`` standalone app)."""

from __future__ import annotations

from typing import Literal, cast

from fastapi import FastAPI, Request
from fastapi.responses import Response


def attach_cookie_debug_middleware(api: FastAPI) -> None:
    @api.middleware("http")
    async def cookie_debug_middleware(request: Request, call_next):
        from app.core.config import settings
        from app.web.debug_panel import (
            COOKIE_DEBUG_LOG_COOKIE,
            add_cookie_debug,
            cookie_debug_payload,
            init_cookie_debug,
        )
        from app.web.session import _is_https, cookie_path

        enabled = bool(getattr(settings, "cookie_debug", False))
        init_cookie_debug(request, enabled=enabled)
        if enabled:
            cookie_header = request.headers.get("cookie") or ""
            cookie_names: list[str] = []
            if cookie_header:
                for part in cookie_header.split(";"):
                    k = (part.split("=", 1)[0] or "").strip()
                    if k:
                        cookie_names.append(k)

            add_cookie_debug(
                request,
                "cookie:req",
                method=request.method,
                path=request.url.path,
                root_path=(request.scope.get("root_path") or ""),
                host=request.headers.get("host"),
                scheme=request.url.scheme,
                xf_proto=request.headers.get("x-forwarded-proto"),
                connect_base_url=request.headers.get("rstudio-connect-app-base-url"),
                cookie_header_present=bool(request.headers.get("cookie")),
                cookie_names=cookie_names,
            )
        resp = await call_next(request)
        if enabled:
            add_cookie_debug(
                request,
                "cookie:resp",
                status_code=getattr(resp, "status_code", None),
                set_cookie_header=resp.headers.get("set-cookie"),
            )
            payload = cookie_debug_payload(request)
            if payload:
                secure = (
                    _is_https(request)
                    if settings.auth_cookie_secure is None
                    else settings.auth_cookie_secure
                )
                samesite = cast(
                    Literal["lax", "strict", "none"],
                    (settings.auth_cookie_samesite or "lax").lower(),
                )
                if samesite == "none" and not secure:
                    secure = True

                resp.set_cookie(
                    key=COOKIE_DEBUG_LOG_COOKIE,
                    value=payload,
                    httponly=True,
                    secure=secure,
                    samesite=samesite,
                    path=cookie_path(request),
                    domain=settings.auth_cookie_domain or None,
                )
        return resp
