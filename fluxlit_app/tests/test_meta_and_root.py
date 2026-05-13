from __future__ import annotations

from fluxlit.gateway import build_gateway
from fluxlit.testing import FluxLitTestClient
from starlette.testclient import TestClient

from conftest import load_fluxlit_app
from ui.pages.um_helpers import api_docs_link


def test_meta_gateway_returns_shape(tmp_path) -> None:
    """``/__meta`` via FluxLit gateway (used by Streamlit ``client``)."""
    db_url = f"sqlite:///{tmp_path / 'm.db'}"
    app = load_fluxlit_app(
        db_url=db_url,
        extra_env={"FLUXLIT_ROOT_PATH": "/prefix/app"},
        public_base_url="",
    )
    gateway = build_gateway(
        app.api,
        "http://127.0.0.1:9",
        api_prefix="/api",
        access_log=app.settings.enable_gateway_access_log,
        proxy_settings=app.settings,
        root_mount="/prefix/app",
    )
    client = TestClient(gateway, root_path="/prefix/app")

    r = client.get("/api/__meta")
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] is True
    assert j["base_path"] == "/prefix/app"
    assert str(j["external_app_base"]).endswith("/prefix/app")
    assert str(j["external_api_base"]).endswith("/api")


def test_meta_inner_fastapi_matches_workbench_header(tmp_path) -> None:
    """Inner FastAPI ``/__meta`` uses ASGI root_path / FluxLit public URL helpers."""
    db_url = f"sqlite:///{tmp_path / 'm2.db'}"
    app = load_fluxlit_app(
        db_url=db_url,
        extra_env={"FLUXLIT_ROOT_PATH": "/prefix/app"},
        public_base_url="",
    )
    client = TestClient(app.api, base_url="http://testserver", root_path="/prefix/app")

    r = client.get("/__meta")
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] is True
    assert j["base_path"] == "/prefix/app"
    assert j["external_app_base"].endswith("/prefix/app")
    assert j["external_api_base"].endswith("/prefix/app/api")


def test_api_root_json(tmp_path) -> None:
    app = load_fluxlit_app(
        db_url=f"sqlite:///{tmp_path / 'r.db'}",
        public_base_url="http://testserver",
    )
    tc = FluxLitTestClient(app)
    r = tc.api_get("/")
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] is True
    assert j["service"] == "jwt_users_api"
    assert str(j["docs"]).endswith("/api/docs")


def test_api_docs_link_uses_api_base() -> None:
    assert api_docs_link("https://example.com/prefix/app/api") == (
        "https://example.com/prefix/app/api/docs"
    )
    assert api_docs_link("") == "/api/docs"
