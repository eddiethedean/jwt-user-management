from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from fastapi_workbench import workbenchify

from .mock_workbench import MockWorkbenchProxy
from .workbench_env import detect_real_workbench


def _wrapped_upstream():
    app = FastAPI()

    @app.get("/ping")
    def ping() -> dict:
        return {"ok": True}

    @app.get("/scope")
    def scope_dump(request: Request) -> dict:
        s = request.scope
        return {
            "root_path": str(s.get("root_path") or ""),
            "path": str(s.get("path") or ""),
        }

    # Wrap the upstream app like a consumer would.
    return workbenchify(app)


def test_workbench_proxy_prefix_embedded_in_path_routes_correctly() -> None:
    if detect_real_workbench():
        # In a real Workbench environment, we run the integration test suite that
        # exercises the true proxy behavior. Keep this unit test for local/dev.
        return
    prefix = "/s/abc/p/proj"
    upstream = _wrapped_upstream()
    proxy = MockWorkbenchProxy(upstream=upstream, external_prefix=prefix)
    client = TestClient(proxy, base_url="http://testserver")

    r = client.get(f"{prefix}/ping")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_workbench_encoded_absolute_url_path_routes_correctly() -> None:
    if detect_real_workbench():
        return
    prefix = "/s/abc/p/proj"
    upstream = _wrapped_upstream()
    proxy = MockWorkbenchProxy(upstream=upstream, external_prefix=prefix)
    client = TestClient(proxy, base_url="http://testserver")

    encoded_path = proxy.encoded_absolute_url_path("/ping")
    r = client.get(encoded_path)
    assert r.status_code == 200


def test_workbench_proxy_root_path_contains_proxy_port_but_forwarded_path_does_not() -> (
    None
):
    if detect_real_workbench():
        return
    prefix = "/s/abc/p/proj"
    upstream = _wrapped_upstream()
    proxy = MockWorkbenchProxy(
        upstream=upstream,
        external_prefix=prefix,
        include_proxy_prefix_in_root_path=True,
        proxy_port=47935,
    )
    client = TestClient(proxy, base_url="http://testserver")

    # The forwarded path contains only the external prefix (no /proxy/<port>).
    r = client.get(f"{prefix}/ping")
    assert r.status_code == 200

    # root_path should be normalized to the forwarded prefix (no /proxy/<port>/...).
    r2 = client.get(f"{prefix}/scope")
    assert r2.status_code == 200
    s = r2.json()
    assert s["root_path"] == prefix
