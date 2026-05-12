from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import SQLModel


def _clear_app_modules() -> None:
    SQLModel.metadata.clear()
    import sqlmodel.main as sqlmodel_main

    sqlmodel_main.default_registry.dispose()
    for k in list(sys.modules.keys()):
        if k == "app" or k.startswith("app."):
            sys.modules.pop(k, None)


def _ensure_this_package_app_first() -> None:
    api_root = str((Path(__file__).resolve().parent / "..").resolve())
    _clear_app_modules()
    while api_root in sys.path:
        sys.path.remove(api_root)
    sys.path.insert(0, api_root)


def test_asgi_is_api_only_no_streamlit_mount() -> None:
    """The backend ASGI app must not embed Streamlit; UI runs as ``user_management_ui``."""
    _ensure_this_package_app_first()
    from app.asgi import app as asgi_app

    client = TestClient(asgi_app, base_url="http://testserver")
    assert client.get("/docs").status_code == 200
    assert client.get("/app", follow_redirects=False).status_code == 404
    assert client.get("/app/", follow_redirects=False).status_code == 404
