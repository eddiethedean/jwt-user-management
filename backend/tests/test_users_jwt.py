from fastapi.testclient import TestClient


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post(
        "/auth/token",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


def test_me_requires_token(client, normal_user):
    resp = client.get("/users/me")
    assert resp.status_code == 401


def test_me_with_token(client, normal_user):
    token = _login(client, normal_user.email, "password123")
    resp = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == normal_user.email


def test_admin_endpoints_require_admin(client, normal_user):
    token = _login(client, normal_user.email, "password123")
    resp = client.get("/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
