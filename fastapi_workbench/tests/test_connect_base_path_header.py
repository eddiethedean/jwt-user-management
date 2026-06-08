from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from fastapi_workbench import base_path


def test_base_path_uses_connect_header_when_workbench_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WORKBENCH_FORCE", "1")
    app = FastAPI()

    @app.get("/bp")
    def bp(request: Request) -> dict:
        return {"bp": base_path(request)}

    client = TestClient(app, base_url="https://connect.example.com")
    r = client.get(
        "/bp",
        headers={
            "rstudio-connect-app-base-url": "https://connect.example.com/content/abc123/"
        },
    )
    assert r.status_code == 200
    assert r.json()["bp"] == "/content/abc123"


def test_base_path_uses_connect_header_when_root_path_set() -> None:
    app = FastAPI()

    @app.get("/bp2")
    def bp2(request: Request) -> dict:
        return {"bp": base_path(request)}

    client = TestClient(
        app, base_url="https://connect.example.com", root_path="/content/abc123"
    )
    r = client.get(
        "/bp2",
        headers={
            "rstudio-connect-app-base-url": "https://connect.example.com/content/ignored/"
        },
    )
    assert r.status_code == 200
    assert r.json()["bp"] == "/content/abc123"


def test_base_path_ignores_connect_header_outside_workbench_scope() -> None:
    app = FastAPI()

    @app.get("/bp3")
    def bp3(request: Request) -> dict:
        return {"bp": base_path(request)}

    client = TestClient(app, base_url="https://evil.example.com")
    r = client.get(
        "/bp3",
        headers={"rstudio-connect-app-base-url": "https://evil.example.com/fake/"},
    )
    assert r.json()["bp"] == ""
