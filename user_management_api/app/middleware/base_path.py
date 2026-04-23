from __future__ import annotations

from dataclasses import dataclass

from starlette.types import ASGIApp, Receive, Scope, Send
from urllib.parse import unquote, urlparse


def _normalize_prefix(prefix: str) -> str:
    p = (prefix or "").strip()
    if not p:
        return ""
    if not p.startswith("/"):
        p = "/" + p
    # no trailing slash (except root)
    if len(p) > 1 and p.endswith("/"):
        p = p[:-1]
    return p


def _maybe_decode_encoded_absolute_url(scope: Scope) -> Scope:
    """
    Workbench-style proxies may pass an encoded absolute URL as the request path, e.g.
      https%3A//workbench.example/s/<service>/p/<project>/admin

    This normalizes scope["path"] to the real URL path so downstream routing works.
    """
    raw_path = scope.get("path") or ""
    candidate = raw_path.lstrip("/")
    if "http%3a" not in candidate.lower() and "https%3a" not in candidate.lower():
        return scope

    decoded = unquote(candidate)
    if not (decoded.startswith("http://") or decoded.startswith("https://")):
        return scope

    parsed = urlparse(decoded)
    decoded_path = parsed.path or "/"

    # If the decoded path includes an unknown Workbench prefix, try to auto-detect it by
    # locating the first "real" app route and converting everything before it to root_path.
    # This handles cases where the Workbench proxy prefix changes per session/project.
    known_route_prefixes = (
        "/admin",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/auth",
        "/users",
        "/invites",
        "/password",
    )
    root_path_override = ""
    for rp in known_route_prefixes:
        idx = decoded_path.find(rp)
        if idx > 0:
            root_path_override = decoded_path[:idx]
            decoded_path = decoded_path[idx:]
            break

    new_scope = dict(scope)
    if root_path_override:
        new_scope["root_path"] = (scope.get("root_path") or "") + root_path_override
    new_scope["path"] = decoded_path or "/"
    new_scope["query_string"] = (parsed.query or "").encode()
    return new_scope


@dataclass(frozen=True)
class BasePathMiddleware:
    """
    Support deployments where the app is served under an external base path prefix.

    Example external URL:
      https://host/s/<service>/p/<project>/admin

    Configure BASE_PATH=/s/<service>/p/<project>
    so incoming scope["path"] is stripped before routing while scope["root_path"]
    is set for correct redirect/url generation.
    """

    app: ASGIApp
    base_path: str

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        scope = _maybe_decode_encoded_absolute_url(scope)
        prefix = _normalize_prefix(self.base_path)
        if not prefix or scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return

        path = scope.get("path") or ""
        if path == prefix:
            new_path = "/"
        elif path.startswith(prefix + "/"):
            new_path = path[len(prefix) :]
        elif (scope.get("root_path") or "").endswith(prefix):
            # We may have already moved an external prefix into root_path (auto-detected
            # from an encoded absolute URL). In that case, routing should proceed without
            # additional stripping.
            await self.app(scope, receive, send)
            return
        else:
            await self.app(scope, receive, send)
            return

        new_scope = dict(scope)
        new_scope["root_path"] = (scope.get("root_path") or "") + prefix
        new_scope["path"] = new_path or "/"
        await self.app(new_scope, receive, send)
