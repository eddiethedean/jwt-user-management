from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


def should_set_csp(content_type: str) -> bool:
    return not (content_type or "").lower().startswith("application/json")


def csp_for_admin() -> str:
    # HTML/JS admin UI: external static JS/CSS + same-origin fetch.
    return (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'self' data: blob:; "
        "font-src 'self' data:; "
        "connect-src 'self'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'; "
        "object-src 'none'"
    )


def csp_for_html_forms() -> str:
    # HTML endpoints load a small shared CSS file from /static.
    return (
        "default-src 'none'; "
        "style-src 'self'; "
        "img-src 'self' data:; "
        "form-action 'self'; "
        "base-uri 'none'; "
        "frame-ancestors 'none'"
    )


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

        if not should_set_csp(content_type):
            return resp

        if path.startswith("/admin"):
            resp.headers.setdefault("Content-Security-Policy", csp_for_admin())
            return resp

        resp.headers.setdefault("Content-Security-Policy", csp_for_html_forms())
        return resp
