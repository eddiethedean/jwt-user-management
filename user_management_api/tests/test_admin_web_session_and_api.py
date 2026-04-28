import re


def _extract_csrf(html: str) -> str:
    m = re.search(r'<meta name="csrf-token" content="([^"]+)"', html)
    assert m, "csrf meta tag not found"
    return m.group(1)


def test_admin_index_redirects_to_login(client):
    r = client.get("/admin/", follow_redirects=False)
    assert r.status_code in (302, 303)
    assert r.headers["location"].endswith("/admin/login")


def test_admin_login_sets_session_and_allows_index(client, admin_user):
    # Prime CSRF token in session by visiting login page.
    r0 = client.get("/admin/login")
    assert r0.status_code == 200
    csrf = _extract_csrf(r0.text)

    r = client.post(
        "/admin/login",
        data={"csrf_token": csrf, "email": admin_user.email, "password": "password123"},
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    assert r.headers["location"].endswith("/admin/")

    r2 = client.get("/admin/")
    assert r2.status_code == 200
    assert "Users" in r2.text


def test_admin_api_requires_session(client, admin_user):
    r = client.get("/admin/api/users")
    assert r.status_code == 401


def test_admin_api_requires_csrf_on_state_change(client, admin_user):
    # Login
    r0 = client.get("/admin/login")
    csrf_login = _extract_csrf(r0.text)
    r = client.post(
        "/admin/login",
        data={
            "csrf_token": csrf_login,
            "email": admin_user.email,
            "password": "password123",
        },
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)

    # CSRF token from admin page
    page = client.get("/admin/")
    csrf = _extract_csrf(page.text)

    # POST without CSRF
    r2 = client.post("/admin/api/invites", json={"email": "x@test.local"})
    assert r2.status_code == 403

    # POST with CSRF
    r3 = client.post(
        "/admin/api/invites",
        json={
            "email": "x@test.local",
            "full_name": None,
            "is_admin": False,
            "permissions": [],
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert r3.status_code == 200
    assert r3.json()["ok"] is True


def test_admin_logout_requires_csrf(client, admin_user):
    r0 = client.get("/admin/login")
    csrf_login = _extract_csrf(r0.text)
    r = client.post(
        "/admin/login",
        data={
            "csrf_token": csrf_login,
            "email": admin_user.email,
            "password": "password123",
        },
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    page = client.get("/admin/")
    csrf = _extract_csrf(page.text)

    r2 = client.post("/admin/logout", json={})
    assert r2.status_code == 403

    r3 = client.post("/admin/logout", json={}, headers={"X-CSRF-Token": csrf})
    assert r3.status_code == 200
    assert r3.json()["ok"] is True


def test_admin_login_requires_csrf(client, admin_user):
    r = client.post(
        "/admin/login",
        data={"email": admin_user.email, "password": "password123"},
        follow_redirects=False,
    )
    # Missing csrf_token field is a request validation error.
    assert r.status_code == 422


def test_admin_patch_requires_csrf_and_does_not_leak_password_hash(
    client, admin_user, normal_user
):
    r0 = client.get("/admin/login")
    csrf_login = _extract_csrf(r0.text)
    r = client.post(
        "/admin/login",
        data={
            "csrf_token": csrf_login,
            "email": admin_user.email,
            "password": "password123",
        },
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)

    page = client.get("/admin/")
    csrf = _extract_csrf(page.text)

    # PATCH without CSRF
    r2 = client.patch(f"/admin/api/users/{normal_user.id}", json={"is_admin": True})
    assert r2.status_code == 403

    # PATCH with CSRF
    r3 = client.patch(
        f"/admin/api/users/{normal_user.id}",
        json={"is_admin": True},
        headers={"X-CSRF-Token": csrf},
    )
    assert r3.status_code == 200
    body = r3.json()
    assert body["ok"] is True
    assert "hashed_password" not in body.get("user", {})


def test_admin_login_rejects_non_admin_user(client, admin_user, normal_user):
    r0 = client.get("/admin/login")
    csrf_login = _extract_csrf(r0.text)
    r = client.post(
        "/admin/login",
        data={
            "csrf_token": csrf_login,
            "email": normal_user.email,
            "password": "password123",
        },
        follow_redirects=False,
    )
    assert r.status_code == 400
    assert "Invalid email or password" in r.text

    # Still not authenticated.
    r2 = client.get("/admin/api/users")
    assert r2.status_code == 401


def test_admin_login_rejects_inactive_admin(client, admin_user, db_session):
    admin_user.is_active = False
    db_session.add(admin_user)
    db_session.commit()

    r0 = client.get("/admin/login")
    csrf_login = _extract_csrf(r0.text)
    r = client.post(
        "/admin/login",
        data={
            "csrf_token": csrf_login,
            "email": admin_user.email,
            "password": "password123",
        },
        follow_redirects=False,
    )
    assert r.status_code == 400


def test_admin_api_rejects_session_user_id_wrong_type():
    from fastapi import FastAPI
    from starlette.requests import Request
    from fastapi.testclient import TestClient

    from app.admin_web.api import router as admin_api_router
    from app.api.deps import get_db
    from app.middleware.security_headers import SecurityHeadersMiddleware
    from starlette.middleware.sessions import SessionMiddleware

    app = FastAPI()
    app.add_middleware(
        SessionMiddleware, secret_key="test-session-secret-please-change"
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.include_router(admin_api_router)

    @app.get("/_set_bad_session")
    def _set_bad_session(request: Request):
        request.session["admin_user_id"] = "abc"
        return {"ok": True}

    def override_get_db():
        yield None

    app.dependency_overrides[get_db] = override_get_db

    c = TestClient(app)
    assert c.get("/_set_bad_session").status_code == 200
    r = c.get("/admin/api/users")
    assert r.status_code == 401


#
# Note: BASE_PATH/prefix-handling tests were removed when we switched to a
# "plain FastAPI" experiment without BasePathMiddleware.
