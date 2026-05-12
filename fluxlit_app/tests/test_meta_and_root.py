from __future__ import annotations

from fluxlit.testing import FluxLitTestClient
from starlette.testclient import TestClient

from conftest import load_fluxlit_app
from ui.pages.um_helpers import api_docs_link


def test_meta_gateway_returns_shape(tmp_path, monkeypatch) -> None:
    """``/__meta`` via FluxLit gateway (used by Streamlit ``client``)."""
    db_url = f"sqlite:///{tmp_path / 'm.db'}"
    app = load_fluxlit_app(
        db_url=db_url,
        extra_env={"FLUXLIT_ROOT_PATH": "/prefix/app"},
    )
    tc = FluxLitTestClient(app).with_root_path("/prefix/app")

    r = tc.api_get("/__meta")
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] is True
    assert j["base_path"] == "/prefix/app"
    assert str(j["external_app_base"]).endswith("/prefix/app")
    assert str(j["external_api_base"]).endswith("/api")


def test_meta_inner_fastapi_matches_workbench_header(tmp_path, monkeypatch) -> None:
    """Inner FastAPI ``/__meta`` uses ASGI root_path / FluxLit public URL helpers."""
    db_url = f"sqlite:///{tmp_path / 'm2.db'}"
    app = load_fluxlit_app(
        db_url=db_url,
        extra_env={"FLUXLIT_ROOT_PATH": "/prefix/app"},
    )
    client = TestClient(app.api, base_url="http://testserver", root_path="/prefix/app")

    r = client.get("/__meta")
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] is True
    assert j["base_path"] == "/prefix/app"
    assert j["external_app_base"].endswith("/prefix/app")
    assert j["external_api_base"].endswith("/prefix/app/api")


def test_api_root_json(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://testserver")
    app = load_fluxlit_app(db_url=f"sqlite:///{tmp_path / 'r.db'}")
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
