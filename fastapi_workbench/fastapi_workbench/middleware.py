from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from urllib.parse import unquote, urlparse

from starlette.types import ASGIApp, Receive, Scope, Send

from .detect import should_normalize, workbench_mode


def _debug_enabled() -> bool:
    return os.getenv("WORKBENCH_DEBUG", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
        "on",
    }


log = logging.getLogger("uvicorn.error")


@dataclass(frozen=True)
class WorkbenchPathMiddleware:
    """
    ASGI wrapper that normalizes Workbench/RStudio Server oddities around path
    prefixes (root_path) so Starlette/FastAPI routing matches correctly.

    Features (can be toggled):
    - Decode Workbench's occasional "absolute URL encoded as a path" format:
        /https%3A//workbench.../s/.../p/.../docs
    - Strip scope['root_path'] (or best matching suffix) from scope['path'].
    """

    app: ASGIApp
    mode: str = "auto"
    decode_absolute_url_path: bool = True
    strip_root_path_from_path: bool = True

    def _maybe_decode_absolute_url_path(self, scope: Scope) -> Scope:
        if not self.decode_absolute_url_path:
            return scope
        raw_path = str(scope.get("path") or "")
        candidate = raw_path.lstrip("/")
        lowered = candidate.lower()
        if not (
            lowered.startswith("http%3a")
            or lowered.startswith("https%3a")
            or lowered.startswith("http://")
            or lowered.startswith("https://")
        ):
            return scope

        decoded = unquote(candidate)
        if not (decoded.startswith("http://") or decoded.startswith("https://")):
            return scope

        parsed = urlparse(decoded)
        decoded_path = parsed.path or "/"
        while "//" in decoded_path:
            decoded_path = decoded_path.replace("//", "/")

        new_scope = dict(scope)
        new_scope["path"] = decoded_path
        new_scope["raw_path"] = decoded_path.encode()
        new_scope["query_string"] = (parsed.query or "").encode()
        return new_scope

    def _strip_root_path_from_path(self, scope: Scope) -> Scope:
        if not self.strip_root_path_from_path:
            return scope
        rp = str(scope.get("root_path") or "").rstrip("/")
        if not rp:
            return scope
        path = str(scope.get("path") or "")

        new_path = path
        new_root_path = rp
        if path == rp:
            new_path = "/"
        elif path.startswith(rp + "/"):
            new_path = path[len(rp) :] or "/"
        else:
            rp_parts = [p for p in rp.split("/") if p]
            for i in range(len(rp_parts)):
                suffix = "/" + "/".join(rp_parts[i:])
                if path == suffix:
                    new_path = "/"
                    new_root_path = suffix.rstrip("/")
                    break
                if path.startswith(suffix + "/"):
                    new_path = path[len(suffix) :] or "/"
                    new_root_path = suffix.rstrip("/")
                    break

        if new_path == path and new_root_path == rp:
            return scope
        new_scope = dict(scope)
        new_scope["path"] = new_path
        new_scope["raw_path"] = new_path.encode()
        new_scope["root_path"] = new_root_path
        return new_scope

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return

        mode = workbench_mode(self.mode)
        if not should_normalize(scope=scope, mode=mode):
            await self.app(scope, receive, send)
            return

        debug = _debug_enabled()
        if debug:
            log.warning(
                "Workbench middleware incoming: method=%r root_path=%r path=%r raw_path=%r query_string=%r",
                scope.get("method"),
                scope.get("root_path"),
                scope.get("path"),
                scope.get("raw_path"),
                (scope.get("query_string") or b"").decode(errors="replace"),
            )

        s1 = self._maybe_decode_absolute_url_path(scope)
        s2 = self._strip_root_path_from_path(s1)
        if debug and s2 is not scope:
            log.warning(
                "Workbench middleware normalized: root_path=%r path=%r (was root_path=%r path=%r)",
                s2.get("root_path"),
                s2.get("path"),
                scope.get("root_path"),
                scope.get("path"),
            )
        await self.app(s2, receive, send)


def workbenchify(
    app: ASGIApp,
    *,
    mode: str = "auto",
    decode_absolute_url_path: bool = True,
    strip_root_path_from_path: bool = True,
) -> ASGIApp:
    """
    Wrap an ASGI app (FastAPI/Starlette) with Workbench path normalization.

    Usage:
        from fastapi_workbench import workbenchify
        app = workbenchify(app)
    """
    return WorkbenchPathMiddleware(
        app,
        mode=mode,
        decode_absolute_url_path=decode_absolute_url_path,
        strip_root_path_from_path=strip_root_path_from_path,
    )

