from __future__ import annotations

from fluxlit.testing import FluxLitTestClient

from conftest import load_fluxlit_app


def test_openapi_docs_served_under_api_prefix(tmp_path) -> None:
    """Parity with ``test_streamlit_mount``’s expectation that API docs are reachable."""
    app = load_fluxlit_app(db_url=f"sqlite:///{tmp_path / 'g.db'}")
    tc = FluxLitTestClient(app)
    r = tc.api_get("/docs")
    assert r.status_code == 200
