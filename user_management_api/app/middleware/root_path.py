from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from urllib.parse import unquote, urlparse

from starlette.types import ASGIApp, Receive, Scope, Send


log = logging.getLogger("uvicorn.error")


def _debug_enabled() -> bool:
    return os.getenv("BASE_PATH_DEBUG", "").lower() in ("1", "true", "yes")


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
            "/invites",
        )
        hits = [p.find(rp) for rp in known if p.find(rp) >= 0]
        if not hits:
            return "", p
        idx = min(hits)
        # If the first known route is already at the start of the path, we have no
        # external prefix to infer.
        if idx == 0:
            return "", p
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

        # Auto-detect Workbench prefix when BASE_PATH isn't configured by locating the
        # first known route and moving everything before it into root_path.
        root_path_override = ""
        decoded_path_for_detect = decoded_path
        known = (
            "/admin",
            "/docs",
            "/openapi.json",
            "/redoc",
            "/register",
            "/login",
            "/users",
            "/auth",
            "/invites",
        )
        hits = [decoded_path_for_detect.find(rp) for rp in known if decoded_path_for_detect.find(rp) >= 0]
        if hits:
            idx = min(hits)
            if idx > 0:
                root_path_override = decoded_path_for_detect[:idx]
                decoded_path_for_detect = decoded_path_for_detect[idx:] or "/"

        new_scope = dict(scope)
        if root_path_override:
            new_scope["root_path"] = (
                new_scope.get("root_path") or ""
            ) + root_path_override
            decoded_path = decoded_path_for_detect
        new_scope["path"] = decoded_path
        new_scope["raw_path"] = decoded_path.encode()
        if parsed.query is not None:
            new_scope["query_string"] = (parsed.query or "").encode()
        if _debug_enabled():
            log.warning(
                "Decoded absolute URL path from Workbench proxy: raw_path=%r decoded_url=%r parsed_path=%r parsed_query=%r root_path_override=%r final_root_path=%r final_path=%r",
                raw_path,
                decoded,
                parsed.path,
                parsed.query,
                root_path_override,
                new_scope.get("root_path") or "",
                new_scope.get("path") or "",
            )
        return new_scope

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        debug = _debug_enabled()
        if scope.get("type") not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return

        if debug:
            log.warning(
                "Incoming scope: type=%s method=%r scheme=%r root_path=%r path=%r raw_path=%r query_string=%r",
                scope.get("type"),
                scope.get("method"),
                scope.get("scheme"),
                scope.get("root_path"),
                scope.get("path"),
                scope.get("raw_path"),
                (scope.get("query_string") or b"").decode(errors="replace"),
            )

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

        # Always apply BASE_PATH to root_path for correct redirects/link generation,
        # even when the proxy has already stripped the prefix from the incoming path.
        existing_rp = str(scope.get("root_path") or "").rstrip("/")
        if not (scope.get("root_path") or "").endswith(bp):
            scope = dict(scope)
            scope["root_path"] = f"{existing_rp}{bp}" if existing_rp else bp

        # Strip BASE_PATH from the incoming path only when it is present in the path.
        # This allows routing to work both when the proxy preserves the prefix and when
        # it strips it upstream.
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

        if debug:
            log.warning(
                "BASE_PATH applied: prefix=%r old_root_path=%r old_path=%r new_root_path=%r new_path=%r",
                bp,
                existing_rp,
                path,
                scope.get("root_path") or "",
                scope.get("path") or "",
            )

        await self.app(scope, receive, send)
