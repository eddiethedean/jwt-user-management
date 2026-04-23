import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.admin_proxy import _filter_out_hop_by_hop, create_admin_proxy_router


def test_filter_out_hop_by_hop_headers():
    headers = [
        ("Connection", "keep-alive"),
        ("Keep-Alive", "timeout=5"),
        ("Content-Type", "text/plain"),
        ("Upgrade", "websocket"),
        ("X-Test", "1"),
    ]
    out = dict(_filter_out_hop_by_hop(headers))
    assert "Content-Type" in out
    assert "X-Test" in out
    assert "Connection" not in out
    assert "Keep-Alive" not in out
    assert "Upgrade" not in out


def test_admin_proxy_returns_502_when_upstream_not_ready():
    app = FastAPI()
    app.include_router(
        create_admin_proxy_router(
            upstream_base_getter=lambda: "http://127.0.0.1:0/admin"
        ),
        prefix="/admin",
    )
    c = TestClient(app)
    r = c.get("/admin/")
    assert r.status_code == 502


def test_admin_proxy_forwards_http_via_injected_client():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("http://127.0.0.1:1234/admin/foo?x=1")
        return httpx.Response(
            200, headers={"Content-Type": "text/plain"}, content=b"ok"
        )

    transport = httpx.MockTransport(handler)
    injected = httpx.AsyncClient(
        transport=transport, follow_redirects=False, timeout=5.0
    )

    app = FastAPI()
    app.include_router(
        create_admin_proxy_router(
            upstream_base_getter=lambda: "http://127.0.0.1:1234/admin",
            client=injected,
        ),
        prefix="/admin",
    )

    c = TestClient(app)
    r = c.get("/admin/foo?x=1")
    assert r.status_code == 200
    assert r.text == "ok"
