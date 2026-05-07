from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from fastapi_workbench import base_path


def test_base_path_uses_connect_app_base_url_header_when_root_path_missing() -> None:
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
