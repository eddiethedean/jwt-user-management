from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        resp = await call_next(request)

        # Baseline hardening headers (safe defaults for this app).
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault(
            "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
        )

        path = request.url.path or "/"
        content_type = (resp.headers.get("content-type") or "").lower()

        # For JSON responses, CSP is irrelevant and can cause confusion with some clients.
        if content_type.startswith("application/json"):
            return resp

        if path.startswith("/admin"):
            # Streamlit uses JS bundles + websocket connections under the same origin.
            resp.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: blob:; "
                "font-src 'self' data:; "
                "connect-src 'self' ws: wss:; "
                "base-uri 'self'; "
                "frame-ancestors 'none'; "
                "object-src 'none'",
            )
            return resp

        # HTML endpoints render inline styles in templates; allow only what's needed.
        resp.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; "
            "style-src 'unsafe-inline'; "
            "img-src 'self' data:; "
            "form-action 'self'; "
            "base-uri 'none'; "
            "frame-ancestors 'none'",
        )
        return resp
