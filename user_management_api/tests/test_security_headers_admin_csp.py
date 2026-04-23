from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.responses import HTMLResponse

from app.middleware.security_headers import (
    SecurityHeadersMiddleware,
    csp_for_admin,
    csp_for_html_forms,
    should_set_csp,
)


def test_admin_csp_is_streamlit_compatible():
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/admin/health")
    def _admin_health():
        return HTMLResponse("<html>ok</html>")

    c = TestClient(app)
    r = c.get("/admin/health")
    assert r.status_code == 200
    csp = r.headers.get("Content-Security-Policy") or ""
    assert "script-src" in csp
    assert "connect-src" in csp
    assert "ws:" in csp
    assert csp == csp_for_admin()


def test_non_admin_html_csp_stays_strict():
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/password/reset")
    def _pw_reset():
        return HTMLResponse("<html>ok</html>")

    c = TestClient(app)
    r = c.get("/password/reset")
    assert r.status_code == 200
    csp = r.headers.get("Content-Security-Policy") or ""
    assert csp.startswith("default-src 'none'")
    assert csp == csp_for_html_forms()


def test_should_set_csp_skips_json():
    assert should_set_csp("application/json") is False
    assert should_set_csp("application/json; charset=utf-8") is False
    assert should_set_csp("text/html; charset=utf-8") is True
