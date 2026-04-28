from fastapi import FastAPI
from pathlib import Path
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse
from starlette.requests import Request

from app.api.routes_auth import router as auth_router
from app.api.routes_invites import router as invites_router
from app.api.routes_password import router as password_router
from app.api.routes_users import router as users_router
from app.core.config import settings
from app.middleware.base_path import BasePathMiddleware
from app.middleware.rate_limit import InMemoryRateLimitMiddleware, RateLimitRule
from app.middleware.security_headers import SecurityHeadersMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles
from app.admin_web.router import router as admin_web_router
from app.admin_web.api import router as admin_web_api_router


_API_ROOT = "/api"

# Root container app. We mount the actual backend under /api so Workbench URLs
# become .../api/docs and .../api/admin/ (avoiding Workbench-level /admin handling).
#
# IMPORTANT: Workbench can place an absolute URL into the ASGI `scope["path"]`.
# BasePathMiddleware must run on the *root* app so decoding/normalization happens
# before mount routing.
app = FastAPI(title="JWT User Management API (root)")

# Workbench can route /docs to the app but send /openapi.json elsewhere if the
# proxy/prefix mapping differs. We provide a docs-local openapi endpoint so the
# Swagger UI fetch stays under /docs/*.
api = FastAPI(title="JWT User Management API", docs_url=None)

_env = (settings.environment or "prod").lower()
_cookie_path = (settings.base_path or "").rstrip("/") + f"{_API_ROOT}/admin"
if not _cookie_path.startswith("/"):
    _cookie_path = "/" + _cookie_path
api.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    session_cookie="admin_session",
    https_only=(_env != "dev"),
    same_site="lax",
    path=_cookie_path,
)
api.add_middleware(SecurityHeadersMiddleware)

api.add_middleware(
    InMemoryRateLimitMiddleware,
    enabled=settings.rate_limit_enabled,
    trust_proxy_headers=settings.rate_limit_trust_proxy_headers,
    rules={
        ("POST", "/auth/token"): RateLimitRule(window_seconds=60, max_requests=20),
        ("POST", "/password/forgot"): RateLimitRule(window_seconds=60, max_requests=5),
        ("POST", "/password/reset"): RateLimitRule(window_seconds=60, max_requests=10),
        ("POST", "/invites/accept"): RateLimitRule(window_seconds=60, max_requests=10),
    },
)

if settings.base_path or settings.base_path_debug:
    # Add BasePathMiddleware last so it executes first.
    app.add_middleware(BasePathMiddleware, base_path=settings.base_path)


api.include_router(auth_router)
api.include_router(users_router)
api.include_router(invites_router)
api.include_router(password_router)

api.include_router(admin_web_router)
api.include_router(admin_web_api_router)
_STATIC_DIR = Path(__file__).resolve().parent / "static"
api.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

# Mount the backend under /api.
app.mount(_API_ROOT, api)


@api.get("/docs", include_in_schema=False)
def docs(request: Request) -> HTMLResponse:
    # Use a relative OpenAPI URL so the browser fetch goes to /docs/openapi.json
    # under the same proxy mapping as /docs.
    return get_swagger_ui_html(
        openapi_url="openapi.json",
        title=f"{api.title} - Swagger UI",
    )


@api.get("/docs/openapi.json", include_in_schema=False)
def docs_openapi() -> dict:
    return api.openapi()
