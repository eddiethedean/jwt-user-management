from __future__ import annotations

from fluxlit.testing import FluxLitTestClient
from starlette.testclient import TestClient

from conftest import load_fluxlit_app


def test_meta_gateway_returns_shape(tmp_path, monkeypatch) -> None:
    """``/__meta`` via FluxLit gateway (used by Streamlit ``client``)."""
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://testserver")
    db_url = f"sqlite:///{tmp_path / 'm.db'}"
    app = load_fluxlit_app(db_url=db_url)
    tc = FluxLitTestClient(app)

    r = tc.api_get(
        "/__meta",
        headers={"rstudio-connect-app-base-url": "https://example.com/prefix/app/"},
    )
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] is True
    assert isinstance(j["base_path"], str)
    assert j["external_base"]
    assert j["external_api_base"]


def test_meta_inner_fastapi_matches_workbench_header(tmp_path, monkeypatch) -> None:
    """Inner FastAPI ``/__meta`` with Workbench-style base URL header."""
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://testserver")
    db_url = f"sqlite:///{tmp_path / 'm2.db'}"
    app = load_fluxlit_app(db_url=db_url)
    client = TestClient(app.api, base_url="http://testserver")

    r = client.get(
        "/__meta",
        headers={"rstudio-connect-app-base-url": "https://example.com/prefix/app/"},
    )
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] is True
    assert j["base_path"] == "/prefix/app"
    eb = str(j["external_base"] or "")
    assert eb.startswith("http://")
    assert str(j["external_api_base"] or "").startswith(eb)
    assert j["external_api_base"].endswith("/prefix/app")


def test_api_root_json(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://testserver")
    app = load_fluxlit_app(db_url=f"sqlite:///{tmp_path / 'r.db'}")
    tc = FluxLitTestClient(app)
    r = tc.api_get("/")
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] is True
    assert j["service"] == "jwt_users_api"
    assert j["docs"] == "/api/docs"
