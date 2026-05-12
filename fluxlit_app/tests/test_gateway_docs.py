from __future__ import annotations

from fluxlit.testing import FluxLitTestClient

from conftest import load_fluxlit_app


def test_openapi_docs_served_under_api_prefix(tmp_path) -> None:
    """OpenAPI docs should be reachable (same expectation as the API-only ASGI smoke test)."""
    app = load_fluxlit_app(db_url=f"sqlite:///{tmp_path / 'g.db'}")
    tc = FluxLitTestClient(app)
    tc.assert_docs_available()
