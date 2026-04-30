from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote

from starlette.types import ASGIApp, Receive, Scope, Send


@dataclass(frozen=True)
class MockWorkbenchProxy:
    """
    A tiny ASGI proxy that simulates Posit Workbench/RStudio Server request shaping.

    What it simulates:
    - Workbench sets `scope['root_path']` to an external prefix.
    - Incoming `scope['path']` may still contain that prefix (so upstream routing
      would break unless normalized).
    - Some deployments set root_path to `/proxy/<port>/<prefix>` but forward only
      `<prefix>` to the upstream.
    - Occasionally the incoming path is an encoded absolute URL:
        /https%3A//workbench.host/<prefix>//docs
    """

    upstream: ASGIApp
    external_prefix: str
    include_proxy_prefix_in_root_path: bool = False
    proxy_port: int = 55555
    host: str = "workbench.example"
    scheme: str = "https"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") not in {"http", "websocket"}:
            await self.upstream(scope, receive, send)
            return

        prefix = (self.external_prefix or "").rstrip("/")
        root_path = prefix
        if self.include_proxy_prefix_in_root_path:
            root_path = f"/proxy/{self.proxy_port}{prefix}"

        new_scope = dict(scope)
        new_scope["root_path"] = root_path
        await self.upstream(new_scope, receive, send)

    def encoded_absolute_url_path(self, suffix_path: str) -> str:
        """
        Build a request path that looks like Workbench's encoded-absolute-url format.

        Returns a path beginning with '/https%3A//'...
        """
        prefix = (self.external_prefix or "").rstrip("/")
        p = (suffix_path or "").strip()
        if not p.startswith("/"):
            p = "/" + p
        # Double slash after prefix is intentional; it matches the regression tests.
        absolute = f"{self.scheme}://{self.host}{prefix}//{p.lstrip('/')}"
        # Workbench's observed format typically keeps slashes unescaped:
        #   /https%3A//workbench.host/s/...//docs
        # Encode ':' and a few other reserved characters, but keep '/' intact.
        return "/" + quote(absolute, safe="/")

