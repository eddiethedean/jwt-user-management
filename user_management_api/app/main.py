from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes_auth import router as auth_router
from app.api.routes_invites import router as invites_router
from app.api.routes_password import router as password_router
from app.api.routes_users import router as users_router
from app.core.config import settings
from app.admin_proxy import create_admin_proxy_router
from app.admin_streamlit import start_streamlit_admin, stop_streamlit_admin
from app.middleware.rate_limit import InMemoryRateLimitMiddleware, RateLimitRule
from app.middleware.security_headers import SecurityHeadersMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start Streamlit admin UI as an internal subprocess.
    backend_url = settings.public_base_url.rstrip("/") or "http://127.0.0.1:8000"
    ui = start_streamlit_admin(backend_url=backend_url, base_path="admin")
    app.state.admin_ui_port = ui.port
    try:
        yield
    finally:
        stop_streamlit_admin()


app = FastAPI(title="JWT User Management API", lifespan=lifespan)

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


# Serve Streamlit admin UI under /admin (HTTP + websocket reverse proxy).
def _admin_upstream_base() -> str:
    port = int(getattr(app.state, "admin_ui_port", 0) or 0)
    return f"http://127.0.0.1:{port}/admin"


app.include_router(
    create_admin_proxy_router(upstream_base_getter=_admin_upstream_base),
    prefix="/admin",
)
