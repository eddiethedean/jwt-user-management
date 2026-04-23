from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional, Tuple

import httpx
import os

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from starlette.responses import Response

from jose import JWTError
from sqlmodel import Session, select

from app.api.deps import get_current_admin
from app.core.security import decode_token
from app.db.session import engine
from app.models.user import User


HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


def _filter_out_hop_by_hop(headers: Iterable[Tuple[str, str]]) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    for k, v in headers:
        if k.lower() in HOP_BY_HOP_HEADERS:
            continue
        out.append((k, v))
    return out


@dataclass(frozen=True)
class HeaderPolicy:
    def request_headers(self, request: Request) -> List[Tuple[str, str]]:
        headers = _filter_out_hop_by_hop(request.headers.items())
        # Preserve host semantics for Streamlit's internal routing.
        headers.append(("x-forwarded-proto", request.url.scheme))
        headers.append(("x-forwarded-host", request.headers.get("host", "")))
        return headers

    def response_headers(
        self, upstream_headers: Iterable[Tuple[str, str]]
    ) -> dict[str, str]:
        return dict(_filter_out_hop_by_hop(upstream_headers))


@dataclass(frozen=True)
class ProxyClientProvider:
    client: Optional[httpx.AsyncClient] = None
    client_getter: Optional[Callable[[], httpx.AsyncClient]] = None

    def get(self) -> httpx.AsyncClient:
        if self.client is not None:
            return self.client
        assert self.client_getter is not None
        return self.client_getter()


@dataclass(frozen=True)
class AdminUpstream:
    upstream_base_getter: Callable[[], str]

    def base(self) -> str:
        return self.upstream_base_getter()

    def is_ready(self) -> bool:
        base = self.base()
        return not (":0/" in base or base.endswith(":0/admin"))

    def http_url(self, *, path: str, request: Request) -> str:
        upstream_base = self.base()
        if path:
            return f"{upstream_base.rstrip('/')}/{path.lstrip('/')}"
        # Preserve trailing slash to avoid redirect loops on /admin/.
        return (
            upstream_base.rstrip("/") + "/"
            if request.url.path.endswith("/")
            else upstream_base
        )

    def ws_url(self, *, path: str, websocket: WebSocket) -> str:
        upstream_base = self.base()
        qs = f"?{websocket.url.query}" if websocket.url.query else ""
        upstream_ws_url = upstream_base.replace("http://", "ws://").replace(
            "https://", "wss://"
        )
        if path:
            return f"{upstream_ws_url.rstrip('/')}/{path.lstrip('/')}{qs}"
        return f"{upstream_ws_url}{qs}"


@dataclass(frozen=True)
class AdminAuthGate:
    enabled: bool

    def http_dep(self):
        return Depends(get_current_admin) if self.enabled else None

    def validate_ws(self, token: str) -> bool:
        if not self.enabled:
            return True
        token = (token or "").strip()
        if not token:
            return False
        try:
            payload = decode_token(token)
        except JWTError:
            return False
        user_id = payload.get("sub")
        if user_id is None:
            return False
        try:
            user_id_int = int(str(user_id))
        except (TypeError, ValueError):
            return False
        with Session(engine) as db:
            user = db.exec(select(User).where(User.id == user_id_int)).first()
        return bool(user and user.is_active and user.is_admin)


def create_admin_proxy_router(
    *,
    upstream_base_getter: Callable[[], str],
    client: httpx.AsyncClient | None = None,
    client_getter: Callable[[], httpx.AsyncClient] | None = None,
) -> APIRouter:
    """
    Reverse proxy router for Streamlit admin UI.

    The getter should return the Streamlit baseUrlPath, e.g. `http://127.0.0.1:1234/admin`.
    """
    router = APIRouter()

    if client is None and client_getter is None:
        client = httpx.AsyncClient(follow_redirects=False, timeout=30.0)
    auth_gate = AdminAuthGate(
        enabled=os.getenv("ADMIN_UI_REQUIRE_JWT", "").lower() in ("1", "true", "yes")
    )
    client_provider = ProxyClientProvider(client=client, client_getter=client_getter)
    upstream = AdminUpstream(upstream_base_getter=upstream_base_getter)
    header_policy = HeaderPolicy()

    @router.get("/{path:path}")
    @router.head("/{path:path}")
    @router.post("/{path:path}")
    @router.put("/{path:path}")
    @router.patch("/{path:path}")
    @router.delete("/{path:path}")
    @router.options("/{path:path}")
    async def proxy_http(
        path: str,
        request: Request,
        _admin=auth_gate.http_dep(),
    ) -> Response:
        async_client = client_provider.get()
        if not upstream.is_ready():
            return Response("Admin UI upstream not ready", status_code=502)
        upstream_url = upstream.http_url(path=path, request=request)

        body = await request.body()
        headers = header_policy.request_headers(request)

        upstream_req = async_client.build_request(
            method=request.method,
            url=upstream_url,
            params=request.query_params,
            headers=headers,
            content=body,
        )

        upstream_resp = await async_client.send(upstream_req, stream=False)

        resp_headers = header_policy.response_headers(upstream_resp.headers.items())
        return Response(
            content=upstream_resp.content,
            status_code=upstream_resp.status_code,
            headers=resp_headers,
            media_type=upstream_resp.headers.get("content-type"),
        )

    @router.websocket("/{path:path}")
    async def proxy_ws(path: str, websocket: WebSocket) -> None:
        """
        Websocket proxy for Streamlit runtime.

        Uses the `websockets` library (typically installed via `uvicorn[standard]`).
        """
        await websocket.accept()
        if auth_gate.enabled:
            token = websocket.query_params.get("token") or ""
            if not token:
                await websocket.close(code=4401)
                return
            if not auth_gate.validate_ws(token):
                await websocket.close(code=4403)
                return
        _ = (
            client_provider.get()
        )  # Ensure client is initialized for lifespan ownership.
        if not upstream.is_ready():
            await websocket.close(code=1011)
            return
        upstream_ws_url = upstream.ws_url(path=path, websocket=websocket)

        try:
            import websockets
        except Exception as e:  # pragma: no cover
            await websocket.close(code=1011)
            raise RuntimeError(
                "websockets client library is required for admin websocket proxy"
            ) from e

        async with websockets.connect(upstream_ws_url) as upstream_ws:

            async def _client_to_upstream() -> None:
                try:
                    while True:
                        msg = await websocket.receive()
                        if "text" in msg and msg["text"] is not None:
                            await upstream_ws.send(msg["text"])
                        elif "bytes" in msg and msg["bytes"] is not None:
                            await upstream_ws.send(msg["bytes"])
                        else:
                            break
                except WebSocketDisconnect:
                    return

            async def _upstream_to_client() -> None:
                try:
                    async for msg in upstream_ws:
                        if isinstance(msg, (bytes, bytearray)):
                            await websocket.send_bytes(bytes(msg))
                        else:
                            await websocket.send_text(str(msg))
                except Exception:
                    return

            await asyncio.gather(_client_to_upstream(), _upstream_to_client())

    return router
