from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from app.admin_web.router import router as admin_router
from app.middleware.base_path import BasePathMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware


def test_admin_login_redirect_and_cookie_path_under_base_path():
    base_path = "/bp"

    app = FastAPI()
    app.add_middleware(
        SessionMiddleware,
        secret_key="test-session-secret-please-change",
        session_cookie="admin_session",
        https_only=False,
        same_site="lax",
        path=f"{base_path}/admin",
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(BasePathMiddleware, base_path=base_path)
    app.include_router(admin_router)

    c = TestClient(app)

    # Not logged in -> redirect includes prefix.
    r = c.get(f"{base_path}/admin/", follow_redirects=False)
    assert r.status_code in (302, 303)
    assert r.headers["location"].startswith(f"{base_path}/admin/login")

    # Login page includes base-path meta (template var is set by router).
    login_page = c.get(f"{base_path}/admin/login")
    assert login_page.status_code == 200
    assert f'<meta name="base-path" content="{base_path}"' in login_page.text
    set_cookie = (login_page.headers.get("set-cookie") or "").lower()
    assert "admin_session=" in set_cookie
    assert f"path={base_path}/admin" in set_cookie
    assert "samesite=lax" in set_cookie

    # Ensure subsequent requests keep working with the prefixed paths.
    r2 = c.get(f"{base_path}/admin/", follow_redirects=False)
    assert r2.status_code in (200, 302, 303)


def test_security_headers_apply_under_base_path():
    base_path = "/bp"

    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(BasePathMiddleware, base_path=base_path)

    @app.get("/admin/health")
    def _admin_health():
        return HTMLResponse("<html>ok</html>")

    c = TestClient(app)
    r = c.get(f"{base_path}/admin/health")
    assert r.status_code == 200
    assert "Content-Security-Policy" in r.headers
