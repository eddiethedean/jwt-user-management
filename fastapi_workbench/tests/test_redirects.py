from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from starlette.testclient import TestClient

from fastapi_workbench import safe_redirect
from fastapi_workbench.detect import is_workbench_forced


@pytest.fixture
def app() -> FastAPI:
    return FastAPI()


def test_safe_redirect_root_uses_dot_in_workbench_scope(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WORKBENCH_FORCE", "1")

    @app.get("/wb")
    def wb(request: Request):
        return safe_redirect(request, "/")

    c = TestClient(app, root_path="/content/app")
    r = c.get("/wb", follow_redirects=False)
    assert r.status_code in (301, 302, 303, 307, 308)
    assert r.headers["location"] == "."


def test_safe_redirect_rejects_parent_segments_by_default(app: FastAPI) -> None:
    @app.get("/trav")
    def trav(request: Request):
        return safe_redirect(request, "/../admin")

    c = TestClient(app)
    r = c.get("/trav", follow_redirects=False)
    assert r.headers["location"] == "/"


def test_safe_redirect_allows_parent_segments_when_opted_in(app: FastAPI) -> None:
    @app.get("/up")
    def up(request: Request):
        return safe_redirect(request, "../admin", allow_parent_segments=True)

    c = TestClient(app, root_path="/content/app")
    r = c.get("/up", follow_redirects=False)
    assert r.headers["location"] == "../admin"


def test_safe_redirect_depth_aware_from_nested_path(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WORKBENCH_FORCE", "1")

    @app.get("/admin/users/{user_id}")
    def nested(request: Request, user_id: int):
        return safe_redirect(request, "/login")

    c = TestClient(app, root_path="/prefix/app")
    r = c.get("/admin/users/5", follow_redirects=False)
    assert r.headers["location"] == "../../../login"


def test_safe_redirect_not_workbench_with_rs_server_url_only(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RS_SERVER_URL", "http://wb")
    monkeypatch.delenv("WORKBENCH_FORCE", raising=False)

    @app.get("/plain")
    def plain(request: Request):
        return safe_redirect(request, "/login")

    c = TestClient(app)
    r = c.get("/plain", follow_redirects=False)
    assert r.headers["location"] == "/login"


def test_safe_redirect_uses_absolute_when_public_base_set(app: FastAPI) -> None:
    @app.get("/abs")
    def abs_redirect(request: Request):
        return safe_redirect(
            request,
            "/login",
            public_base_url="https://wb.example/prefix",
        )

    c = TestClient(app, root_path="/prefix")
    r = c.get("/abs", follow_redirects=False)
    assert r.headers["location"] == "https://wb.example/prefix/login"


def test_safe_redirect_workbench_forced_env(app: FastAPI, monkeypatch) -> None:
    monkeypatch.setenv("WORKBENCH_FORCE", "1")
    assert is_workbench_forced()

    @app.get("/forced")
    def forced(request: Request):
        return safe_redirect(request, "/")

    c = TestClient(app)
    r = c.get("/forced", follow_redirects=False)
    assert r.headers["location"] == "."
