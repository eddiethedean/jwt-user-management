from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from starlette.testclient import TestClient

from fastapi_workbench import (
    browser_app_mount_path,
    external_ui_url,
    external_workbench_url,
    merge_public_base_with_mount,
    workbench_browser_base,
)


@pytest.fixture
def app() -> FastAPI:
    return FastAPI()


def test_workbench_browser_base_prefers_fluxlit_over_settings_env(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    @app.get("/b")
    def b(request: Request) -> dict:
        return {
            "base": workbench_browser_base(
                request, public_base_url="http://127.0.0.1:1"
            )
        }

    monkeypatch.setenv("FLUXLIT_PUBLIC_BASE_URL", "https://workbench.example/app")
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)
    c = TestClient(app)
    r = c.get("/b")
    assert r.status_code == 200
    assert r.json()["base"] == "https://workbench.example/app"


def test_workbench_browser_base_uses_public_env_when_no_fluxlit(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    @app.get("/b2")
    def b2(request: Request) -> dict:
        return {"base": workbench_browser_base(request, public_base_url=None)}

    monkeypatch.delenv("FLUXLIT_PUBLIC_BASE_URL", raising=False)
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://public.example")
    c = TestClient(app)
    r = c.get("/b2")
    assert r.json()["base"] == "https://public.example"


def test_browser_app_mount_path_strips_trailing_api_prefix(app: FastAPI) -> None:
    @app.get("/m")
    def m(request: Request) -> dict:
        return {"m": browser_app_mount_path(request)}

    c = TestClient(app, root_path="/api")
    r = c.get("/m")
    assert r.json()["m"] == ""


def test_browser_app_mount_path_strips_api_after_workbench_prefix(app: FastAPI) -> None:
    @app.get("/m2")
    def m2(request: Request) -> dict:
        return {"m": browser_app_mount_path(request)}

    c = TestClient(app, root_path="/content/abc/api")
    r = c.get("/m2")
    assert r.json()["m"] == "/content/abc"


def test_external_workbench_url_skips_duplicate_root_path(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    @app.get("/ew")
    def ew(request: Request) -> dict:
        return {
            "url": external_workbench_url(
                request,
                "/invites/accept?token=t",
                public_base_url="https://workbench.example/prefix/app",
            )
        }

    monkeypatch.delenv("FLUXLIT_PUBLIC_BASE_URL", raising=False)
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)
    c = TestClient(app, base_url="http://internal", root_path="/prefix/app")
    r = c.get("/ew")
    assert r.status_code == 200
    assert r.json()["url"] == (
        "https://workbench.example/prefix/app/invites/accept?token=t"
    )


def test_merge_public_base_with_mount(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    @app.get("/m")
    def m(request: Request) -> dict:
        return {
            "merged": merge_public_base_with_mount(
                request, public_base_url="https://wb.example"
            )
        }

    monkeypatch.delenv("FLUXLIT_PUBLIC_BASE_URL", raising=False)
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)
    c = TestClient(app, base_url="https://wb.example", root_path="/p1")
    r = c.get("/m")
    assert r.json()["merged"] == "https://wb.example/p1"


def test_external_ui_url_no_duplicate_mount(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    @app.get("/u")
    def u(request: Request) -> dict:
        return {
            "url": external_ui_url(
                request,
                "/?page=Accept+invite&token=x",
                public_base_url="https://workbench.example/prefix/app",
            )
        }

    monkeypatch.delenv("FLUXLIT_PUBLIC_BASE_URL", raising=False)
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)
    c = TestClient(app, base_url="http://internal", root_path="/prefix/app")
    r = c.get("/u")
    assert r.status_code == 200
    assert r.json()["url"] == (
        "https://workbench.example/prefix/app/?page=Accept+invite&token=x"
    )
    assert "/prefix/app/prefix/app" not in r.json()["url"]


def test_package_version_matches_release() -> None:
    import fastapi_workbench as fb

    assert fb.__version__ == "0.3.1"
