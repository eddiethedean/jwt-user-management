from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, Optional, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


@dataclass(frozen=True)
class RateLimitRule:
    window_seconds: int
    max_requests: int


def _first_forwarded_for(xff: str) -> Optional[str]:
    # X-Forwarded-For: client, proxy1, proxy2
    parts = [p.strip() for p in (xff or "").split(",") if p.strip()]
    return parts[0] if parts else None


def _normalize_path(path: str) -> str:
    p = str(path or "")
    if p != "/" and p.endswith("/"):
        p = p[:-1]
    return p or "/"


class InMemoryRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple in-memory rate limiting middleware.

    Notes:
    - Per-process only (not shared across workers).
    - Intended for demo/dev hardening; for production, use a shared store (Redis) or gateway rate limiting.
    """

    def __init__(
        self,
        app,
        *,
        enabled: bool,
        trust_proxy_headers: bool,
        rules: Dict[Tuple[str, str], RateLimitRule],
    ) -> None:
        super().__init__(app)
        self._enabled = enabled
        self._trust_proxy_headers = trust_proxy_headers
        self._rules = rules
        self._hits: Dict[str, Deque[float]] = {}

    def reset(self) -> None:
        self._hits.clear()

    def _client_ip(self, request: Request) -> str:
        if self._trust_proxy_headers:
            xff = request.headers.get("x-forwarded-for")
            ip = _first_forwarded_for(xff or "")
            if ip:
                return ip
        if request.client and request.client.host:
            return request.client.host
        return "unknown"

    def _key(self, request: Request, rule: RateLimitRule) -> str:
        ip = self._client_ip(request)
        path = _normalize_path(request.url.path)
        return f"{ip}:{request.method}:{path}:{rule.window_seconds}:{rule.max_requests}"

    def _allow(self, key: str, rule: RateLimitRule) -> Tuple[bool, int]:
        now = time.time()
        cutoff = now - rule.window_seconds
        q = self._hits.get(key)
        if q is None:
            q = deque()
            self._hits[key] = q
        while q and q[0] <= cutoff:
            q.popleft()
        if len(q) >= rule.max_requests:
            retry_after = (
                int(max(1, (q[0] + rule.window_seconds) - now))
                if q
                else rule.window_seconds
            )
            return False, retry_after
        q.append(now)
        return True, 0

    async def dispatch(self, request: Request, call_next) -> Response:
        if not self._enabled:
            return await call_next(request)

        path = _normalize_path(request.url.path)
        rule = self._rules.get((request.method.upper(), path))
        if not rule:
            return await call_next(request)

        key = self._key(request, rule)
        ok, retry_after = self._allow(key, rule)
        if ok:
            return await call_next(request)

        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests"},
            headers={"Retry-After": str(retry_after)},
        )
