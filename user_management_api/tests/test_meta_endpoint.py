from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
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
    """Resolve ``app`` from this API tree (repo may contain another ``app`` package)."""
    api_root = str((Path(__file__).resolve().parent / "..").resolve())
    _clear_app_modules()
    while api_root in sys.path:
        sys.path.remove(api_root)
    sys.path.insert(0, api_root)


def test_meta_endpoint_includes_external_base_and_prefix(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    /__meta is used by the Streamlit UI (``user_management_ui``) to learn the externally-visible
    base URL and prefix behind proxies.
    """

    # Other tests (e.g. ``start_app``) may mutate ``os.environ``; parallel runs make that visible.
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)

    for k in list(os.environ):
        if k.startswith("FLUXLIT_"):
            monkeypatch.delenv(k, raising=False)

    # Import the wrapped app so it behaves like Workbench runs it.
    _ensure_this_package_app_first()
    from app.asgi import app

    client = TestClient(app, base_url="http://testserver")

    r = client.get(
        "/__meta",
        headers={"rstudio-connect-app-base-url": "https://example.com/prefix/app/"},
    )
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] is True
    assert j["base_path"] == "/prefix/app"
    eb = str(j["external_base"] or "").rstrip("/")
    api_b = str(j["external_api_base"] or "").rstrip("/")
    assert eb.startswith(("http://", "https://"))
    assert api_b.startswith(eb)
    assert api_b.endswith("/prefix/app")
