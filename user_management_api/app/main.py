from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from fastapi_workbench import safe_redirect
from app.routes.admin import router as admin_router
from app.routes.account import router as account_router
from app.routes.auth import router as auth_router
from app.routes.password_reset import router as password_reset_router
from app.routes.invites import router as invites_router
from app.routes.users import router as users_router

from typing import Literal, cast

from app.web.debug_panel import (
    COOKIE_DEBUG_LOG_COOKIE,
    cookie_debug_payload,
    init_cookie_debug,
)

app = FastAPI(title="User Management API")

_APP_ROOT = Path(__file__).resolve().parent
app.mount(
    "/static",
    StaticFiles(directory=str(_APP_ROOT / "web" / "static")),
    name="static",
)


@app.middleware("http")
async def cookie_debug_middleware(request: Request, call_next):
    from app.core.config import settings

    enabled = bool(getattr(settings, "cookie_debug", False))
    init_cookie_debug(request, enabled=enabled)
    if enabled:
        from app.web.debug_panel import add_cookie_debug

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
        )
    resp = await call_next(request)
    if enabled:
        from app.web.debug_panel import add_cookie_debug

        add_cookie_debug(
            request,
            "cookie:resp",
            status_code=getattr(resp, "status_code", None),
            set_cookie_header=resp.headers.get("set-cookie"),
        )
        # Persist per-request debug logs through redirects by storing them in a cookie.
        payload = cookie_debug_payload(request)
        if payload:
            from app.web.session import _is_https, cookie_path

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


app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(account_router)
app.include_router(invites_router)
app.include_router(password_reset_router)
app.include_router(users_router)


@app.get("/", include_in_schema=False)
async def root(request: Request) -> Response:
    return safe_redirect(request, "/register", status_code=302)
