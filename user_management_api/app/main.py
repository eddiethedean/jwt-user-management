from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app.admin_proxy import create_admin_proxy_router
from app.admin_streamlit import start_streamlit_admin, stop_streamlit_admin
from app.api.routes_auth import router as auth_router
from app.api.routes_invites import router as invites_router
from app.api.routes_password import router as password_router
from app.api.routes_users import router as users_router
from app.core.config import settings
from app.middleware.base_path import BasePathMiddleware
from app.middleware.rate_limit import InMemoryRateLimitMiddleware, RateLimitRule
from app.middleware.security_headers import SecurityHeadersMiddleware


def mount_admin_ui(app: FastAPI) -> None:
    # Serve Streamlit admin UI under /admin (HTTP + websocket reverse proxy).
    def _admin_upstream_base() -> str:
        port = int(getattr(app.state, "admin_ui_port", 0) or 0)
        base_path = (getattr(app.state, "admin_ui_base_path", "") or "").strip("/")
        if base_path:
            return f"http://127.0.0.1:{port}/{base_path}"
        return f"http://127.0.0.1:{port}/admin"

    app.include_router(
        create_admin_proxy_router(
            upstream_base_getter=_admin_upstream_base,
            client_getter=lambda: app.state.admin_proxy_client,
        ),
        prefix="/admin",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.admin_proxy_client = httpx.AsyncClient(
        follow_redirects=False, timeout=30.0
    )
    backend_url = settings.public_base_url.rstrip("/") or "http://127.0.0.1:8000"
    # When served behind an external prefix (e.g. Workbench), Streamlit must be started
    # with a baseUrlPath that includes the prefix so its absolute asset paths resolve.
    base_prefix = (settings.base_path or "").strip("/")
    base_path = f"{base_prefix}/admin" if base_prefix else "admin"
    app.state.admin_ui_base_path = base_path
    ui = start_streamlit_admin(backend_url=backend_url, base_path=base_path)
    app.state.admin_ui_port = ui.port
    try:
        yield
    finally:
        stop_streamlit_admin()
        await app.state.admin_proxy_client.aclose()


app = FastAPI(title="JWT User Management API", lifespan=lifespan)

if settings.base_path or settings.base_path_debug:
    app.add_middleware(BasePathMiddleware, base_path=settings.base_path)
app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(
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


app.include_router(auth_router)
app.include_router(users_router)
app.include_router(invites_router)
app.include_router(password_router)

mount_admin_ui(app)
