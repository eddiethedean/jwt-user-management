from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.workbench_adapter import WorkbenchPathAdapter


def _client(*, root_path: str) -> TestClient:
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

    @app.get("/admin")
    def admin() -> dict:
        return {"ok": True}

    wrapped = WorkbenchPathAdapter(app)
    return TestClient(wrapped, base_url="http://testserver", root_path=root_path)


def test_strips_root_path_prefix_for_routing() -> None:
    bp = "/s/e886e3c9ab5a7e147ea97/p/a693b2fa"
    client = _client(root_path=bp)

    # Incoming requests include the prefix in the path (Workbench behavior).
    r = client.get(f"{bp}/ping")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_strips_root_path_for_admin_route() -> None:
    bp = "/s/e886e3c9ab5a7e147ea97/p/a693b2fa"
    client = _client(root_path=bp)

    r = client.get(f"{bp}/admin")
    assert r.status_code == 200


def test_decodes_encoded_absolute_url_path_and_strips_prefix() -> None:
    bp = "/s/e886e3c9ab5a7266e1f45/p/a5ca0047"
    client = _client(root_path=bp)

    encoded = "/https%3A//workbench.socom.mil" + bp + "//ping"
    r = client.get(encoded)
    assert r.status_code == 200


def test_strips_suffix_of_root_path_when_proxy_prefix_stripped_upstream() -> None:
    # External root_path includes /proxy/<port>/..., but upstream forwards only the
    # /s/.../p/... portion in the incoming path.
    root_path = "/proxy/47935/s/e886e3c9ab5a7e147ea97/p/1f5bf0be"
    forwarded_prefix = "/s/e886e3c9ab5a7e147ea97/p/1f5bf0be"
    client = _client(root_path=root_path)

    r = client.get(f"{forwarded_prefix}/ping")
    assert r.status_code == 200

    # Adapter should also normalize scope['root_path'] so redirects/templates don't
    # emit /proxy/<port>/... URLs that Workbench can't route.
    r2 = client.get(f"{forwarded_prefix}/scope")
    assert r2.status_code == 200
    s = r2.json()
    assert s["root_path"] == forwarded_prefix
