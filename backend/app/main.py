from fastapi import FastAPI

from app.api.routes_auth import router as auth_router
from app.api.routes_invites import router as invites_router
from app.api.routes_password import router as password_router
from app.api.routes_users import router as users_router
from app.core.config import settings
from app.middleware.rate_limit import InMemoryRateLimitMiddleware, RateLimitRule
from app.middleware.security_headers import SecurityHeadersMiddleware


app = FastAPI(title="JWT User Management API")

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
