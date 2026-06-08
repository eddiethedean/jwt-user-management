from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock

from fastapi import HTTPException, Request

from app.core.config import settings

_LOCK = Lock()
_BUCKETS: dict[str, list[float]] = defaultdict(list)
_MAX_BUCKET_KEYS = 50_000


def _client_ip(request: Request) -> str:
    direct = request.client.host if request.client and request.client.host else ""
    trusted = getattr(settings, "rate_limit_trusted_proxies", frozenset())
    if trusted and direct in trusted:
        forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
        if forwarded:
            return forwarded
    if direct:
        return direct
    return "unknown"


def _prune(key: str, *, window_s: float, now: float) -> None:
    cutoff = now - window_s
    _BUCKETS[key] = [t for t in _BUCKETS[key] if t > cutoff]
    if not _BUCKETS[key]:
        _BUCKETS.pop(key, None)


def _evict_if_needed() -> None:
    if len(_BUCKETS) <= _MAX_BUCKET_KEYS:
        return
    # Drop oldest-access buckets (arbitrary but bounded).
    excess = len(_BUCKETS) - _MAX_BUCKET_KEYS
    for key in list(_BUCKETS.keys())[:excess]:
        _BUCKETS.pop(key, None)


def check_rate_limit(
    request: Request,
    *,
    scope: str,
    email: str | None = None,
) -> None:
    """Raise 429 when per-IP (and optional per-email) limits are exceeded."""
    if not getattr(settings, "rate_limit_enabled", True):
        return

    limit = int(getattr(settings, "rate_limit_auth_per_minute", 20))
    window_s = 60.0
    now = time.monotonic()
    keys = [f"{scope}:ip:{_client_ip(request)}"]
    if email:
        keys.append(f"{scope}:email:{email.strip().lower()}")

    with _LOCK:
        for key in keys:
            _prune(key, window_s=window_s, now=now)
            if len(_BUCKETS[key]) >= limit:
                raise HTTPException(
                    status_code=429,
                    detail="Too many requests",
                    headers={"Retry-After": "60"},
                )
        for key in keys:
            _BUCKETS[key].append(now)
        _evict_if_needed()


def reset_rate_limits_for_tests() -> None:
    """Clear in-memory buckets (tests only)."""
    with _LOCK:
        _BUCKETS.clear()
