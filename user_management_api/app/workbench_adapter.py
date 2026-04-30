from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import unquote, urlparse

from starlette.types import ASGIApp, Receive, Scope, Send


@dataclass(frozen=True)
class WorkbenchPathAdapter:
    """
    Posit Workbench / RStudio Server sometimes forwards requests with the external
    prefix embedded in the incoming path (e.g. /s/<service>/p/<project>/docs), even
    when the server sets scope['root_path'].

    Starlette/FastAPI routing matches on scope['path'], so we strip scope['root_path']
    from scope['path'] when present, and decode Workbench's occasional "absolute URL
    encoded as a path" format:

      /https%3A//workbench.../s/.../p/.../docs
    """

    app: ASGIApp

    def _maybe_decode_absolute_url_path(self, scope: Scope) -> Scope:
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
        rp = str(scope.get("root_path") or "").rstrip("/")
        if not rp:
            return scope
        path = str(scope.get("path") or "")

        # Prefer stripping the full root_path when it is present.
        new_path = path
        if path == rp:
            new_path = "/"
        elif path.startswith(rp + "/"):
            new_path = path[len(rp) :] or "/"
        else:
            # Some Workbench deployments include an external /proxy/<port> prefix in
            # root_path but strip it before forwarding to the upstream. In that case,
            # the incoming path starts with a suffix of root_path (e.g. root_path is
            # /proxy/<port>/s/.../p/... but path is /s/.../p/.../docs). Strip the
            # longest suffix of root_path that matches the beginning of path.
            rp_parts = [p for p in rp.split("/") if p]
            path_norm = path
            # try suffixes from longest to shortest (must include leading '/')
            for i in range(len(rp_parts)):
                suffix = "/" + "/".join(rp_parts[i:])
                if path_norm == suffix:
                    new_path = "/"
                    break
                if path_norm.startswith(suffix + "/"):
                    new_path = path_norm[len(suffix) :] or "/"
                    break
        if new_path == path:
            return scope
        new_scope = dict(scope)
        new_scope["path"] = new_path
        new_scope["raw_path"] = new_path.encode()
        return new_scope

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return

        scope = self._maybe_decode_absolute_url_path(scope)
        scope = self._strip_root_path_from_path(scope)
        await self.app(scope, receive, send)
