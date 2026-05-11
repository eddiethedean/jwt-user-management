from __future__ import annotations

import importlib.util
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


def test_asgi_mounts_streamlit_under_app_if_available() -> None:
    """
    Validate that our ASGI entrypoint mounts the Streamlit UI at /app.

    This is conditional: it only applies when Streamlit's experimental ASGI
    integration is available in the environment (Streamlit >= 1.53 with
    the Starlette extras).
    """

    streamlit_available = (
        importlib.util.find_spec("streamlit") is not None
        and importlib.util.find_spec("streamlit.starlette") is not None
    )
    if not streamlit_available:
        return

    _ensure_this_package_app_first()
    from app.asgi import app as asgi_app  # import inside test to evaluate mount

    client = TestClient(asgi_app, base_url="http://testserver")

    # FastAPI should still serve docs.
    r_docs = client.get("/docs")
    assert r_docs.status_code == 200

    # Mounts do not match the bare `/app` path; they match `/app/` and deeper.
    # `/app/` should respond with a page or a redirect (depending on Streamlit).
    r = client.get("/app/", follow_redirects=False)
    assert r.status_code in {200, 301, 302, 307, 308}
