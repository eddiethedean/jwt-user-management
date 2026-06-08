from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from urllib.parse import unquote, urlparse

from starlette.types import ASGIApp, Receive, Scope, Send

from .detect import should_normalize, workbench_mode
from .path_safety import encode_raw_path, redact_scope_for_log

_PROXY_PREFIX = re.compile(r"^/proxy/\d+(?P<rest>/.*)$")


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
        new_scope["raw_path"] = encode_raw_path(decoded_path)
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
            m = _PROXY_PREFIX.match(rp)
            if m:
                rest = (m.group("rest") or "").rstrip("/")
                if rest and (path == rest or path.startswith(rest + "/")):
                    if path == rest:
                        new_path = "/"
                    else:
                        new_path = path[len(rest) :] or "/"
                    new_root_path = rest

        if new_path == path and new_root_path == rp:
            return scope
        new_scope = dict(scope)
        new_scope["path"] = new_path
        new_scope["raw_path"] = encode_raw_path(new_path)
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
            redacted = redact_scope_for_log(scope)
            log.warning(
                "Workbench middleware incoming: method=%r root_path=%r path=%r "
                "raw_path=%r query_string=%r",
                redacted["method"],
                redacted["root_path"],
                redacted["path"],
                redacted["raw_path"],
                redacted["query_string"],
            )

        s1 = self._maybe_decode_absolute_url_path(scope)
        s2 = self._strip_root_path_from_path(s1)
        if debug and s2 is not scope:
            before = redact_scope_for_log(scope)
            after = redact_scope_for_log(s2)
            log.warning(
                "Workbench middleware normalized: root_path=%r path=%r "
                "(was root_path=%r path=%r)",
                after["root_path"],
                after["path"],
                before["root_path"],
                before["path"],
            )
        await self.app(s2, receive, send)


def workbenchify(
    app: ASGIApp,
    *,
    mode: str = "auto",
    decode_absolute_url_path: bool = True,
    strip_root_path_from_path: bool = True,
) -> ASGIApp:
    return WorkbenchPathMiddleware(
        app,
        mode=mode,
        decode_absolute_url_path=decode_absolute_url_path,
        strip_root_path_from_path=strip_root_path_from_path,
    )
