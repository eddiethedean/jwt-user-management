from __future__ import annotations

from dataclasses import dataclass

from starlette.types import ASGIApp, Receive, Scope, Send


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
        prefix = _normalize_prefix(self.base_path)
        if not prefix or scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return

        path = scope.get("path") or ""
        if path == prefix:
            new_path = "/"
        elif path.startswith(prefix + "/"):
            new_path = path[len(prefix) :]
        else:
            await self.app(scope, receive, send)
            return

        new_scope = dict(scope)
        new_scope["root_path"] = (scope.get("root_path") or "") + prefix
        new_scope["path"] = new_path or "/"
        await self.app(new_scope, receive, send)
