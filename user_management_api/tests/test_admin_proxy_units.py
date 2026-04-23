from __future__ import annotations

from starlette.requests import Request
from starlette.websockets import WebSocket

import httpx
import pytest

from app.admin_proxy import AdminUpstream, HeaderPolicy, ProxyClientProvider


def _make_request(
    *, path: str, scheme: str = "http", headers: list[tuple[bytes, bytes]] | None = None
) -> Request:
    scope = {
        "type": "http",
        "asgi": {"spec_version": "2.3", "version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": scheme,
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": headers or [],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }
    return Request(scope)  # type: ignore[arg-type]


def _make_websocket(
    *, path: str, query_string: str = "", scheme: str = "http"
) -> WebSocket:
    scope = {
        "type": "websocket",
        "asgi": {"spec_version": "2.3", "version": "3.0"},
        "scheme": scheme,
        "path": path,
        "raw_path": path.encode(),
        "query_string": query_string.encode(),
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
        "subprotocols": [],
    }

    async def _receive():  # pragma: no cover
        return {"type": "websocket.connect"}

    async def _send(message):  # pragma: no cover  # noqa: ANN001
        return None

    return WebSocket(scope, _receive, _send)  # type: ignore[arg-type]


def test_admin_upstream_http_url_preserves_trailing_slash_for_root():
    upstream = AdminUpstream(upstream_base_getter=lambda: "http://127.0.0.1:1234/admin")
    req = _make_request(path="/admin/")

    assert upstream.http_url(path="", request=req) == "http://127.0.0.1:1234/admin/"


def test_admin_upstream_http_url_no_trailing_slash_for_root_when_request_has_none():
    upstream = AdminUpstream(upstream_base_getter=lambda: "http://127.0.0.1:1234/admin")
    req = _make_request(path="/admin")

    assert upstream.http_url(path="", request=req) == "http://127.0.0.1:1234/admin"


def test_admin_upstream_ws_url_converts_scheme_and_keeps_query():
    upstream = AdminUpstream(upstream_base_getter=lambda: "http://127.0.0.1:1234/admin")

    ws = _make_websocket(path="/admin/ws", query_string="a=1&b=2")
    assert (
        upstream.ws_url(path="ws", websocket=ws)
        == "ws://127.0.0.1:1234/admin/ws?a=1&b=2"
    )


def test_header_policy_appends_forwarded_headers_and_filters_hop_by_hop():
    req = _make_request(
        path="/admin/",
        headers=[
            (b"connection", b"keep-alive"),
            (b"x-test", b"1"),
            (b"host", b"example.local"),
        ],
    )
    hp = HeaderPolicy()
    headers = dict(hp.request_headers(req))
    assert "connection" not in {k.lower() for k in headers.keys()}
    assert headers["x-forwarded-proto"] in {"http", "https"}
    assert "x-forwarded-host" in headers


def test_proxy_client_provider_prefers_injected_client():
    injected = httpx.AsyncClient()
    provider = ProxyClientProvider(
        client=injected, client_getter=lambda: httpx.AsyncClient()
    )
    assert provider.get() is injected


def test_proxy_client_provider_requires_getter_when_no_client():
    provider = ProxyClientProvider(client=None, client_getter=None)
    with pytest.raises(AssertionError):
        provider.get()
