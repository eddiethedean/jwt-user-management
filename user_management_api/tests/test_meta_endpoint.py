from __future__ import annotations

from fastapi.testclient import TestClient


def test_meta_endpoint_includes_external_base_and_prefix(tmp_path) -> None:
    """
    /__meta is used by the mounted Streamlit UI to learn the externally-visible
    base URL and prefix behind proxies.
    """

    # Import the wrapped app so it behaves like Workbench runs it.
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
    assert j["external_base"] in {"http://testserver", "https://example.com"}
    # When a connect-style header is provided, external_api_base should include the prefix.
    assert j["external_api_base"].endswith("/prefix/app")

