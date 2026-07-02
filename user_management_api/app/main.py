from pathlib import Path
from typing import Literal, cast

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi_workbench import (
    base_path as wb_base_path,
    merge_public_base_with_mount,
    safe_redirect,
    workbench_browser_base,
)
from app.core.config import settings
from app.core.logging import configure_logging, get_logger, log_http_request
from app.routes.admin import router as admin_router
from app.routes.auth import router as auth_router
from app.routes.invites import router as invites_router
from app.routes.password_reset import router as password_reset_router
from app.routes.users import router as users_router
from app.web.debug_panel import (
    COOKIE_DEBUG_LOG_COOKIE,
    cookie_debug_payload,
    init_cookie_debug,
)
from app.web.ui import include_html_ui

configure_logging(fallback=settings.log_level)
log = get_logger(__name__)

app = FastAPI(title="User Management API")
log.info(
    "Starting User Management API (log_level=%s, http_requests=%s)",
    settings.log_level,
    settings.log_http_requests,
)

_APP_ROOT = Path(__file__).resolve().parent


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    return await log_http_request(
        request,
        call_next,
        enabled=settings.log_http_requests,
    )


@app.middleware("http")
async def csrf_prepare_middleware(request: Request, call_next):
    from app.web.csrf import ensure_csrf_token

    ensure_csrf_token(request)
    return await call_next(request)


@app.middleware("http")
async def cookie_debug_middleware(request: Request, call_next):
    enabled = bool(getattr(settings, "cookie_debug", False))
    init_cookie_debug(request, enabled=enabled)
    if enabled:
        from app.web.debug_panel import add_cookie_debug

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
        from app.web.debug_panel import add_cookie_debug

        set_cookie_hdr = resp.headers.get("set-cookie")
        redacted = "<redacted>" if set_cookie_hdr else None
        add_cookie_debug(
            request,
            "cookie:resp",
            status_code=getattr(resp, "status_code", None),
            set_cookie_present=bool(set_cookie_hdr),
            set_cookie_redacted=redacted,
        )
        # Persist per-request debug logs through redirects by storing them in a cookie.
        payload = cookie_debug_payload(request)
        if payload:
            from app.web.session import auth_cookie_path, auth_cookie_secure

            secure = auth_cookie_secure(request)
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
                path=auth_cookie_path(request),
                domain=settings.auth_cookie_domain or None,
            )
    return resp


app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(invites_router)
app.include_router(password_reset_router)
app.include_router(users_router)

include_html_ui(app)


@app.get("/__meta", include_in_schema=False)
async def meta(request: Request) -> JSONResponse:
    """
    Metadata for HTTP clients (base path and external URL helpers).

    Returns the externally-visible base URL (via fastapi_workbench proxy
    detection) and the normalized base path so UIs can build correct URLs.
    """
    bp = wb_base_path(request)
    pub = workbench_browser_base(
        request, public_base_url=settings.public_base_url or None
    )
    return JSONResponse(
        {
            "ok": True,
            "base_path": bp,
            "external_base": pub,
            "external_api_base": merge_public_base_with_mount(
                request, public_base_url=settings.public_base_url or None
            ),
        }
    )


@app.get("/", include_in_schema=False)
async def root(request: Request) -> Response:
    return safe_redirect(request, "/register", status_code=303)
