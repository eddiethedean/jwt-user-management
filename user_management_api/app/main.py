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

import logging


app = FastAPI(title="User Management API")
log = logging.getLogger("uvicorn.error")

_APP_ROOT = Path(__file__).resolve().parent
app.mount(
    "/static",
    StaticFiles(directory=str(_APP_ROOT / "web" / "static")),
    name="static",
)


@app.middleware("http")
async def cookie_debug_middleware(request: Request, call_next):
    from app.core.config import settings

    if bool(getattr(settings, "cookie_debug", False)):
        # Debug logging (safe: no token values).
        log.info(
            "cookie:req method=%s path=%s root_path=%r host=%r scheme=%r xf_proto=%r connect_base_url=%r cookie_header_present=%s",
            request.method,
            request.url.path,
            (request.scope.get("root_path") or ""),
            request.headers.get("host"),
            request.url.scheme,
            request.headers.get("x-forwarded-proto"),
            request.headers.get("rstudio-connect-app-base-url"),
            bool(request.headers.get("cookie")),
        )
    resp = await call_next(request)
    if bool(getattr(settings, "cookie_debug", False)):
        set_cookie = resp.headers.get("set-cookie")
        if set_cookie:
            # Log presence + key attributes; do not log token itself.
            log.info("cookie:resp set-cookie=%r", set_cookie)
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
