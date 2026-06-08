"""Regression tests for subtle audit fixes (roles, cookies, next redirect, SMTP)."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from api_test_helpers import (
    FakeHttpxResponse,
    bearer_for,
    load_wrapped_app,
    seed_admin,
    seed_user,
)


def _csrf_from_login(client: TestClient, *, next_path: str = "") -> str:
    url = "/login"
    if next_path:
        url = f"/login?next={next_path}"
    r = client.get(url)
    assert r.status_code == 200
    m = re.search(r'name="csrf_token" value="([^"]+)"', r.text)
    assert m
    return m.group(1)


def _csrf_from_account(client: TestClient) -> str:
    r = client.get("/account")
    assert r.status_code == 200
    m = re.search(r'name="csrf_token" value="([^"]+)"', r.text)
    assert m
    return m.group(1)


def _login_cookie(
    client: TestClient, *, email: str, password: str, next_path: str = ""
) -> None:
    csrf = _csrf_from_login(client, next_path=next_path)
    data = {"email": email, "password": password, "csrf_token": csrf}
    if next_path:
        data["next_path"] = next_path
    r = client.post("/login", data=data, follow_redirects=False)
    assert r.status_code in (303, 302), r.text


def test_admin_patch_is_admin_syncs_roles(app_client, db_engine) -> None:
    seed_admin(db_engine=db_engine)
    target_id = seed_user(
        db_engine=db_engine,
        email="sync@example.com",
        password="longpassword1",
        is_admin=False,
    )
    h = bearer_for(app_client, email="admin@example.com", password="admin123")

    r = app_client.patch(
        f"/admin/users/{target_id}",
        headers=h,
        json={"is_admin": True},
    )
    assert r.status_code == 200
    body = r.json()["user"]
    assert body["is_admin"] is True
    assert body["roles"] == ["Admin", "Super"]

    r2 = app_client.patch(
        f"/admin/users/{target_id}",
        headers=h,
        json={"is_admin": False},
    )
    assert r2.status_code == 200
    assert r2.json()["user"]["roles"] == ["User"]
    assert r2.json()["user"]["is_admin"] is False


def test_invite_accept_grant_admin_sets_configured_roles(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path / 'grant.db'}"
    app = load_wrapped_app(db_url=db_url)
    import app.db as db
    from api_test_helpers import seed_unused_invite

    from app.models import User

    raw = seed_unused_invite(
        db_engine=db.engine, email="admin2@example.com", grant_admin=True
    )
    client = TestClient(app, base_url="http://testserver")
    r = client.post("/invites/accept", json={"token": raw, "password": "longpassword1"})
    assert r.status_code == 200

    with Session(db.engine) as s:
        u = s.exec(select(User).where(User.email == "admin2@example.com")).first()
        assert u
        assert u.is_admin is True
        assert u.roles == "Admin,Super"


def test_login_next_query_posts_to_intended_path(app_client, db_engine) -> None:
    seed_user(
        db_engine=db_engine,
        email="user@example.com",
        password="longpassword1",
    )
    csrf = _csrf_from_login(app_client, next_path="/account")
    r = app_client.post(
        "/login",
        data={
            "email": "user@example.com",
            "password": "longpassword1",
            "csrf_token": csrf,
            "next_path": "/account",
        },
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    assert "/account" in (r.headers.get("location") or "")


def test_password_change_refreshes_auth_cookie(app_client, db_engine) -> None:
    seed_user(
        db_engine=db_engine,
        email="user@example.com",
        password="longpassword1",
    )
    _login_cookie(app_client, email="user@example.com", password="longpassword1")
    csrf = _csrf_from_account(app_client)
    r = app_client.post(
        "/account/password",
        data={
            "current_password": "longpassword1",
            "new_password": "newpassword1234",
            "confirm_password": "newpassword1234",
            "csrf_token": csrf,
        },
        follow_redirects=False,
    )
    assert r.status_code == 200
    assert "Password updated" in r.text
    r2 = app_client.get("/account", follow_redirects=False)
    assert r2.status_code == 200
    assert "user@example.com" in r2.text


def test_stale_cookie_cleared_on_login_page(app_client, db_engine) -> None:
    seed_user(
        db_engine=db_engine,
        email="user@example.com",
        password="longpassword1",
    )
    _login_cookie(app_client, email="user@example.com", password="longpassword1")
    csrf = _csrf_from_account(app_client)
    app_client.post(
        "/logout",
        data={"csrf_token": csrf},
        follow_redirects=True,
    )
    r = app_client.get("/login")
    assert r.status_code == 200
    assert "user@example.com" not in r.text


def test_register_smtp_failure_returns_503(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite:///{tmp_path / 'smtp-fail.db'}"
    app = load_wrapped_app(db_url=db_url)
    client = TestClient(app, base_url="http://testserver")

    import app.core.config as config

    config.settings.smtp_host = "smtp.test.local"
    config.settings.smtp_from_email = "noreply@test.local"
    monkeypatch.setattr(
        "app.routes.auth.send_self_registration_email",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("smtp down")),
    )

    csrf = _csrf_from_login(client)
    r = client.post(
        "/register",
        data={"email": "nobody@example.com", "csrf_token": csrf},
        headers={"Accept": "application/json"},
        follow_redirects=False,
    )
    assert r.status_code == 503
    assert "could not send" in (r.json().get("detail") or "").lower()


def test_invite_create_smtp_failure_returns_503(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite:///{tmp_path / 'invite-smtp.db'}"
    app = load_wrapped_app(db_url=db_url)
    import app.db as db

    seed_admin(db_engine=db.engine)
    import app.core.config as config

    config.settings.smtp_host = "smtp.test.local"
    config.settings.smtp_from_email = "noreply@test.local"
    monkeypatch.setattr(
        "app.routes.invites.send_invite_email",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("smtp down")),
    )

    client = TestClient(app, base_url="http://testserver")
    h = bearer_for(client, email="admin@example.com", password="admin123")
    r = client.post(
        "/invites",
        json={"email": "new@example.com", "grant_admin": False},
        headers=h,
    )
    assert r.status_code == 503


def test_invite_rejects_missing_directory_when_required(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite:///{tmp_path / 'dir-req.db'}"
    app = load_wrapped_app(
        db_url=db_url,
        enable_directory=True,
        directory_lookup_required=True,
    )
    import app.db as db
    import app.services.directory as directory

    seed_admin(db_engine=db.engine)

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, *args, **kwargs):
            return FakeHttpxResponse(status_code=404)

    monkeypatch.setattr(directory.httpx, "AsyncClient", _Client)

    import app.core.config as config

    assert config.settings.directory_lookup_required is True

    client = TestClient(app, base_url="http://testserver")
    h = bearer_for(client, email="admin@example.com", password="admin123")
    r = client.post(
        "/invites",
        json={"email": "nobody@example.com", "grant_admin": False},
        headers=h,
    )
    assert r.status_code == 422
    assert "directory" in (r.json().get("detail") or "").lower()
