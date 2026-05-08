from __future__ import annotations

import importlib.util

from fastapi.testclient import TestClient


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

    from app.asgi import app as asgi_app  # import inside test to evaluate mount

    client = TestClient(asgi_app, base_url="http://testserver")

    # FastAPI should still serve docs.
    r_docs = client.get("/docs")
    assert r_docs.status_code == 200

    # Streamlit may respond with 200 or a redirect to a trailing-slash path.
    r = client.get("/app", follow_redirects=False)
    assert r.status_code in {200, 301, 302, 307, 308}

