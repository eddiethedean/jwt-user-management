from __future__ import annotations

from dataclasses import dataclass

from starlette.types import ASGIApp, Receive, Scope, Send


@dataclass(frozen=True)
class RootPathMiddleware:
    """
    Minimal support for deployments behind a reverse proxy that serves the app under
    a stable external prefix (e.g. Workbench URLs like /s/<service>/p/<project>).

    This middleware does NOT rewrite the request path; it only sets/extends
    scope['root_path'] so redirects and templates can generate correct URLs.
    """

    app: ASGIApp
    base_path: str

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return

        bp = (self.base_path or "").strip()
        if not bp:
            await self.app(scope, receive, send)
            return

        if not bp.startswith("/"):
            bp = "/" + bp
        if len(bp) > 1 and bp.endswith("/"):
            bp = bp[:-1]

        existing = str(scope.get("root_path") or "")
        if existing.endswith(bp):
            await self.app(scope, receive, send)
            return

        new_scope = dict(scope)
        new_scope["root_path"] = (existing.rstrip("/") + bp) if existing else bp
        await self.app(new_scope, receive, send)
