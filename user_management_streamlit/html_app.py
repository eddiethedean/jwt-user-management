"""
Standalone FastAPI app for the legacy cookie-auth HTML UI.

Uses ``user_management_api`` for DB/models/config and serves templates/static from
``user_management_streamlit/web/``.

Run (from repo root or this directory, with API deps installed)::

    cd user_management_streamlit
    cp .env.example .env   # or symlink user_management_api/.env
    uvicorn html_app:app --reload --host 127.0.0.1 --port 8503

Requires the same ``DATABASE_URL`` / ``JWT_SECRET`` as ``user_management_api`` and
``alembic upgrade head`` applied there.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Literal, cast

_ROOT = Path(__file__).resolve().parent
_REPO = _ROOT.parent
_API_PKG = _REPO / "user_management_api"
_WORKBENCH_SRC = _REPO / "fastapi_workbench" / "src"


def _anchor_sqlite_url(url: str, *, base_dir: Path) -> str:
    """Resolve ``sqlite:///./…`` relative to the API package (not process cwd)."""
    prefix = "sqlite:///./"
    if url.startswith(prefix):
        db_file = (base_dir / url[len(prefix) :]).resolve()
        return f"sqlite:///{db_file}"
    return url


for p in (str(_WORKBENCH_SRC), str(_API_PKG), str(_REPO)):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover

    def load_dotenv(*_a, **_k):  # type: ignore
        return False


load_dotenv(_API_PKG / ".env")
load_dotenv(_ROOT / ".env")
_db_url = os.getenv("DATABASE_URL", "sqlite:///./app.db")
os.environ["DATABASE_URL"] = _anchor_sqlite_url(_db_url, base_dir=_API_PKG)

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.responses import Response  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from fastapi_workbench import safe_redirect  # noqa: E402

from user_management_streamlit.html_routes.account import router as account_router  # noqa: E402
from user_management_streamlit.html_routes.admin import router as admin_router  # noqa: E402
from user_management_streamlit.html_routes.auth import router as auth_router  # noqa: E402
from user_management_streamlit.html_routes.invites import router as invites_router  # noqa: E402
from user_management_streamlit.html_routes.password_reset import (  # noqa: E402
    router as password_reset_router,
)
from user_management_streamlit.html_routes.users import router as users_router  # noqa: E402
from user_management_streamlit.web.debug_panel import (  # noqa: E402
    COOKIE_DEBUG_LOG_COOKIE,
    cookie_debug_payload,
    init_cookie_debug,
)

app = FastAPI(title="User Management HTML UI")

app.mount(
    "/static",
    StaticFiles(directory=str(_ROOT / "web" / "static")),
    name="static",
)


@app.middleware("http")
async def cookie_debug_middleware(request: Request, call_next):
    from app.core.config import settings

    enabled = bool(getattr(settings, "cookie_debug", False))
    init_cookie_debug(request, enabled=enabled)
    if enabled:
        from user_management_streamlit.web.debug_panel import add_cookie_debug

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
        from user_management_streamlit.web.debug_panel import add_cookie_debug

        add_cookie_debug(
            request,
            "cookie:resp",
            status_code=getattr(resp, "status_code", None),
            set_cookie_header=resp.headers.get("set-cookie"),
        )
        payload = cookie_debug_payload(request)
        if payload:
            from user_management_streamlit.web.session import _is_https, cookie_path

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
