from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse

from starlette.requests import Request

from app.core.config import settings


def _origin_from_url(url: str) -> Optional[str]:
    try:
        p = urlparse(url)
    except ValueError:
        return None
    if not p.scheme or not p.netloc:
        return None
    return f"{p.scheme}://{p.netloc}"


def require_same_origin(request: Request) -> None:
    """
    Basic browser CSRF mitigation for HTML form posts.

    If Origin/Referer is present, require it matches PUBLIC_BASE_URL's origin.
    """

    expected = _origin_from_url((settings.public_base_url or "").strip())
    if not expected:
        # If PUBLIC_BASE_URL isn't configured, don't apply strict origin checks.
        return

    origin = request.headers.get("origin")
    referer = request.headers.get("referer")
    presented = _origin_from_url(origin) if origin else _origin_from_url(referer) if referer else None
    if presented and presented != expected:
        # Intentionally raise HTTPException in callers (keeps this helper starlette-only).
        raise ValueError(f"Origin not allowed: {presented}")

