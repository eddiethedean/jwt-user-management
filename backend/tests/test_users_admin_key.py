from app.core.config import settings


def test_list_users_requires_admin_or_key(client, admin_user):
    # No JWT and no admin key -> forbidden
    resp = client.get("/users")
    assert resp.status_code in (401, 403)


def test_list_users_with_admin_api_key(client, admin_user):
    # Configure admin key for this test
    old = settings.admin_api_key
    try:
        settings.admin_api_key = "test-key"
        resp = client.get("/users", headers={"X-Admin-Api-Key": "test-key"})
        assert resp.status_code == 200
        users = resp.json()
        assert isinstance(users, list)
        assert any(u["email"] == admin_user.email for u in users)
    finally:
        settings.admin_api_key = old


def test_admin_api_key_header_but_not_configured_is_forbidden(client):
    old = settings.admin_api_key
    try:
        settings.admin_api_key = None
        resp = client.get("/users", headers={"X-Admin-Api-Key": "anything"})
        assert resp.status_code == 403
    finally:
        settings.admin_api_key = old


def test_admin_api_key_whitespace_is_rejected(client):
    old = settings.admin_api_key
    try:
        settings.admin_api_key = "test-key"
        resp = client.get("/users", headers={"X-Admin-Api-Key": "   "})
        assert resp.status_code == 401
    finally:
        settings.admin_api_key = old


def test_admin_key_precedence_over_missing_admin_jwt(client, normal_user):
    # If a valid admin key is present, it should authorize even if bearer token is non-admin.
    old = settings.admin_api_key
    try:
        settings.admin_api_key = "test-key"
        login = client.post(
            "/auth/token",
            data={"username": normal_user.email, "password": "password123"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert login.status_code == 200
        token = login.json()["access_token"]

        r = client.get(
            "/users",
            headers={"Authorization": f"Bearer {token}", "X-Admin-Api-Key": "test-key"},
        )
        assert r.status_code == 200
    finally:
        settings.admin_api_key = old


def test_create_user_with_admin_api_key(client, admin_user):
    old = settings.admin_api_key
    try:
        settings.admin_api_key = "test-key"
        resp = client.post(
            "/users",
            headers={"X-Admin-Api-Key": "test-key"},
            json={
                "email": "new@test.local",
                "full_name": "New User",
                "password": "TempPass123!",
                "is_admin": False,
                "permissions": ["foo:bar"],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["email"] == "new@test.local"
        assert body["permissions"] == ["foo:bar"]
    finally:
        settings.admin_api_key = old


def test_update_user_with_admin_api_key(client, admin_user):
    old = settings.admin_api_key
    try:
        settings.admin_api_key = "test-key"
        created = client.post(
            "/users",
            headers={"X-Admin-Api-Key": "test-key"},
            json={"email": "perm@test.local", "password": "x", "permissions": []},
        ).json()
        user_id = created["id"]
        resp = client.patch(
            f"/users/{user_id}",
            headers={"X-Admin-Api-Key": "test-key"},
            json={"permissions": ["users:read"], "is_admin": True, "is_active": True},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["permissions"] == ["users:read"]
        assert body["is_admin"] is True
        assert body["is_active"] is True
    finally:
        settings.admin_api_key = old
