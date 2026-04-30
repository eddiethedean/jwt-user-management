from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import unquote, urlparse

from starlette.types import ASGIApp, Receive, Scope, Send


@dataclass(frozen=True)
class RootPathMiddleware:
    """
    Support deployments behind a reverse proxy that serves the app under a stable
    external prefix (e.g. Workbench URLs like /s/<service>/p/<project>).

    - Sets/extends scope['root_path'] so redirects and templates generate correct URLs.
    - Strips BASE_PATH from the incoming scope['path'] so routing still works.
    - Decodes Workbench-style proxies that pass an absolute URL (encoded) as the path.
    """

    app: ASGIApp
    base_path: str

    def _autodetect_prefix(self, path: str) -> tuple[str, str]:
        """
        If BASE_PATH isn't configured, try to infer a stable external prefix by locating
        the first known route in the incoming path and treating everything before it
        as the external root_path.
        """
        p = (path or "").strip() or "/"
        while "//" in p:
            p = p.replace("//", "/")
        known = (
            "/docs",
            "/openapi.json",
            "/redoc",
            "/admin",
            "/register",
            "/login",
            "/users",
            "/auth",
        )
        for rp in known:
            idx = p.find(rp)
            if idx > 0:
                return p[:idx].rstrip("/"), p[idx:] or "/"
        return "", p

    def _normalize_prefix(self, v: str) -> str:
        p = (v or "").strip()
        if not p:
            return ""
        if not p.startswith("/"):
            p = "/" + p
        if len(p) > 1 and p.endswith("/"):
            p = p[:-1]
        return p

    def _maybe_decode_workbench_absolute_url(self, scope: Scope) -> Scope:
        """
        Workbench-style proxies may pass an absolute URL as the request path, either:
        - percent-encoded: https%3A//workbench.../s/.../p/.../docs
        - already decoded: https://workbench.../s/.../p/.../docs
        """
        raw_path = str(scope.get("path") or "")
        candidate = raw_path.lstrip("/")
        lowered = candidate.lower()
        is_encoded = ("http%3a" in lowered) or ("https%3a" in lowered)
        is_decoded = lowered.startswith("http://") or lowered.startswith("https://")
        if not is_encoded and not is_decoded:
            return scope

        decoded = unquote(candidate) if is_encoded else candidate
        if not (decoded.startswith("http://") or decoded.startswith("https://")):
            return scope

        parsed = urlparse(decoded)
        decoded_path = parsed.path or "/"
        while "//" in decoded_path:
            decoded_path = decoded_path.replace("//", "/")

        new_scope = dict(scope)
        new_scope["path"] = decoded_path
        new_scope["raw_path"] = decoded_path.encode()
        if parsed.query is not None:
            new_scope["query_string"] = (parsed.query or "").encode()
        return new_scope

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return

        scope = self._maybe_decode_workbench_absolute_url(scope)

        bp = self._normalize_prefix(self.base_path)
        if not bp:
            # Attempt best-effort prefix autodetection for Workbench-style deployments.
            path = str(scope.get("path") or "")
            inferred_prefix, inferred_path = self._autodetect_prefix(path)
            if inferred_prefix:
                scope = dict(scope)
                scope["path"] = inferred_path or "/"
                scope["raw_path"] = (scope["path"] or "/").encode()
                existing = str(scope.get("root_path") or "").rstrip("/")
                scope["root_path"] = (
                    f"{existing}{inferred_prefix}" if existing else inferred_prefix
                )
            await self.app(scope, receive, send)
            return

        # Strip BASE_PATH from the incoming path (so /s/.../p/.../docs routes to /docs).
        path = str(scope.get("path") or "")
        new_path = path
        if path == bp:
            new_path = "/"
        elif path.startswith(bp + "/"):
            new_path = path[len(bp) :]
        if new_path != path:
            scope = dict(scope)
            scope["path"] = new_path or "/"
            scope["raw_path"] = (scope["path"] or "/").encode()

        existing = str(scope.get("root_path") or "").rstrip("/")
        if not (scope.get("root_path") or "").endswith(bp):
            scope = dict(scope)
            scope["root_path"] = f"{existing}{bp}" if existing else bp

        await self.app(scope, receive, send)
