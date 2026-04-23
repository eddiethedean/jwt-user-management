from __future__ import annotations

import asyncio
from typing import Callable, Iterable, List, Tuple

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
    require_jwt = os.getenv("ADMIN_UI_REQUIRE_JWT", "").lower() in ("1", "true", "yes")

    def _get_client() -> httpx.AsyncClient:
        if client is not None:
            return client
        assert client_getter is not None
        return client_getter()

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
        _admin=Depends(get_current_admin) if require_jwt else None,
    ) -> Response:
        async_client = _get_client()
        upstream_base = upstream_base_getter()
        if ":0/" in upstream_base or upstream_base.endswith(":0/admin"):
            return Response("Admin UI upstream not ready", status_code=502)
        if path:
            upstream_url = f"{upstream_base.rstrip('/')}/{path.lstrip('/')}"
        else:
            # Preserve trailing slash to avoid redirect loops on /admin/.
            upstream_url = (
                upstream_base.rstrip("/") + "/"
                if request.url.path.endswith("/")
                else upstream_base
            )

        body = await request.body()
        headers = _filter_out_hop_by_hop(request.headers.items())

        # Preserve host semantics for Streamlit's internal routing.
        headers.append(("x-forwarded-proto", request.url.scheme))
        headers.append(("x-forwarded-host", request.headers.get("host", "")))

        upstream_req = async_client.build_request(
            method=request.method,
            url=upstream_url,
            params=request.query_params,
            headers=headers,
            content=body,
        )

        upstream_resp = await async_client.send(upstream_req, stream=False)

        resp_headers = _filter_out_hop_by_hop(upstream_resp.headers.items())
        return Response(
            content=upstream_resp.content,
            status_code=upstream_resp.status_code,
            headers=dict(resp_headers),
            media_type=upstream_resp.headers.get("content-type"),
        )

    @router.websocket("/{path:path}")
    async def proxy_ws(path: str, websocket: WebSocket) -> None:
        """
        Websocket proxy for Streamlit runtime.

        Uses the `websockets` library (typically installed via `uvicorn[standard]`).
        """
        await websocket.accept()
        if require_jwt:
            token = websocket.query_params.get("token") or ""
            if not token:
                await websocket.close(code=4401)
                return
            try:
                payload = decode_token(token)
            except JWTError:
                await websocket.close(code=4403)
                return
            user_id = payload.get("sub")
            if user_id is None:
                await websocket.close(code=4403)
                return
            try:
                user_id_int = int(str(user_id))
            except (TypeError, ValueError):
                await websocket.close(code=4403)
                return
            with Session(engine) as db:
                user = db.exec(select(User).where(User.id == user_id_int)).first()
            if not user or (not user.is_active) or (not user.is_admin):
                await websocket.close(code=4403)
                return
        _ = _get_client()  # Ensure client is initialized for lifespan ownership.
        upstream_base = upstream_base_getter()
        if ":0/" in upstream_base or upstream_base.endswith(":0/admin"):
            await websocket.close(code=1011)
            return
        qs = f"?{websocket.url.query}" if websocket.url.query else ""
        upstream_ws_url = upstream_base.replace("http://", "ws://").replace(
            "https://", "wss://"
        )
        upstream_ws_url = (
            f"{upstream_ws_url.rstrip('/')}/{path.lstrip('/')}{qs}"
            if path
            else f"{upstream_ws_url}{qs}"
        )

        try:
            import websockets
        except Exception as e:  # pragma: no cover
            await websocket.close(code=1011)
            raise RuntimeError(
                "websockets client library is required for admin websocket proxy"
            ) from e

        async with websockets.connect(upstream_ws_url) as upstream:

            async def _client_to_upstream() -> None:
                try:
                    while True:
                        msg = await websocket.receive()
                        if "text" in msg and msg["text"] is not None:
                            await upstream.send(msg["text"])
                        elif "bytes" in msg and msg["bytes"] is not None:
                            await upstream.send(msg["bytes"])
                        else:
                            break
                except WebSocketDisconnect:
                    return

            async def _upstream_to_client() -> None:
                try:
                    async for msg in upstream:
                        if isinstance(msg, (bytes, bytearray)):
                            await websocket.send_bytes(bytes(msg))
                        else:
                            await websocket.send_text(str(msg))
                except Exception:
                    return

            await asyncio.gather(_client_to_upstream(), _upstream_to_client())

    return router
