import pytest

from app.core.config import settings


def _admin_headers() -> dict:
    return {"X-Admin-Api-Key": "test-key"}


@pytest.fixture()
def admin_key():
    old = settings.admin_api_key
    settings.admin_api_key = "test-key"
    try:
        yield
    finally:
        settings.admin_api_key = old


def test_create_user_duplicate_email_conflict(client, admin_key):
    r1 = client.post(
        "/users",
        headers=_admin_headers(),
        json={"email": "dup@test.local", "password": "x", "permissions": []},
    )
    assert r1.status_code == 200
    r2 = client.post(
        "/users",
        headers=_admin_headers(),
        json={"email": "dup@test.local", "password": "x", "permissions": []},
    )
    assert r2.status_code == 409


def test_create_user_invalid_admin_key_rejected(client, admin_key):
    r = client.post(
        "/users",
        headers={"X-Admin-Api-Key": "wrong"},
        json={"email": "nope@test.local", "password": "x", "permissions": []},
    )
    assert r.status_code == 401


def test_update_user_not_found(client, admin_key):
    r = client.patch("/users/9999", headers=_admin_headers(), json={"is_active": False})
    assert r.status_code == 404


def test_deactivate_user_sets_inactive(client, admin_key):
    created = client.post(
        "/users",
        headers=_admin_headers(),
        json={"email": "to-deactivate@test.local", "password": "x", "permissions": []},
    ).json()
    user_id = created["id"]

    r = client.delete(f"/users/{user_id}", headers=_admin_headers())
    assert r.status_code == 200
    assert r.json()["ok"] is True

    # user should no longer be able to login
    login = client.post(
        "/auth/token",
        data={"username": "to-deactivate@test.local", "password": "x"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert login.status_code == 400
