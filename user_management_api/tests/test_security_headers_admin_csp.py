from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.responses import HTMLResponse

from app.middleware.security_headers import (
    SecurityHeadersMiddleware,
    csp_for_admin,
    csp_for_html_forms,
    should_set_csp,
)


def _parse_csp(csp: str) -> dict[str, str]:
    parts = [p.strip() for p in (csp or "").split(";") if p.strip()]
    out: dict[str, str] = {}
    for p in parts:
        if " " in p:
            k, v = p.split(" ", 1)
            out[k.strip()] = v.strip()
        else:
            out[p] = ""
    return out


def _assert_no_unsafe(d: dict[str, str]) -> None:
    v = " ".join(d.values())
    assert "'unsafe-inline'" not in v
    assert "'unsafe-eval'" not in v


def test_admin_csp_allows_static_js_and_fetch():
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/admin/health")
    def _admin_health():
        return HTMLResponse("<html>ok</html>")

    c = TestClient(app)
    r = c.get("/admin/health")
    assert r.status_code == 200
    csp = r.headers.get("Content-Security-Policy") or ""
    d = _parse_csp(csp)
    assert d == _parse_csp(csp_for_admin())
    assert "script-src" in d
    assert "connect-src" in d
    _assert_no_unsafe(d)


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
    d = _parse_csp(csp)
    assert d.get("default-src") == "'none'"
    assert d == _parse_csp(csp_for_html_forms())
    # Non-admin form pages load CSS from /static (no inline styles needed).
    assert d.get("style-src") == "'self'"


def test_should_set_csp_skips_json():
    assert should_set_csp("application/json") is False
    assert should_set_csp("application/json; charset=utf-8") is False
    assert should_set_csp("text/html; charset=utf-8") is True
