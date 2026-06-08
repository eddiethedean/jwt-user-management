"""Auth, invite accept, and admin contract tests for the standalone API."""

from __future__ import annotations


from sqlmodel import Session, select

from api_test_helpers import (
    bearer_for,
    load_wrapped_app,
    seed_admin,
    seed_unused_invite,
    seed_user,
)


def test_auth_token_wrong_password_returns_400(app_client, db_engine) -> None:
    seed_user(
        db_engine=db_engine,
        email="u@example.com",
        password="right-password",
    )
    r = app_client.post(
        "/auth/token",
        data={"username": "u@example.com", "password": "wrong-password"},
    )
    assert r.status_code == 400
    assert "password" in str(r.json().get("detail", "")).lower()


def test_auth_token_unknown_user_returns_400(app_client) -> None:
    r = app_client.post(
        "/auth/token",
        data={"username": "missing@example.com", "password": "any"},
    )
    assert r.status_code == 400


def test_auth_token_inactive_user_returns_400(app_client, db_engine) -> None:
    seed_user(
        db_engine=db_engine,
        email="sleepy@example.com",
        password="pw",
        is_active=False,
    )
    r = app_client.post(
        "/auth/token",
        data={"username": "sleepy@example.com", "password": "pw"},
    )
    assert r.status_code == 400


def test_users_me_success_for_active_user(app_client, db_engine) -> None:
    seed_user(
        db_engine=db_engine,
        email="me@example.com",
        password="secret1234",
        is_admin=False,
    )
    h = bearer_for(app_client, email="me@example.com", password="secret1234")
    r = app_client.get("/users/me", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "me@example.com"
    assert body["is_admin"] is False


def test_users_list_requires_admin(app_client, db_engine) -> None:
    seed_user(
        db_engine=db_engine,
        email="list@example.com",
        password="secret123456",
    )
    h = bearer_for(app_client, email="list@example.com", password="secret123456")
    r = app_client.get("/users", headers=h)
    assert r.status_code == 403


def test_users_list_success_for_admin(app_client, db_engine) -> None:
    seed_admin(db_engine=db_engine)
    h = bearer_for(app_client, email="admin@example.com", password="admin123")
    r = app_client.get("/users", headers=h)
    assert r.status_code == 200
    users = r.json()
    assert isinstance(users, list)
    assert any(u.get("email") == "admin@example.com" for u in users)


def test_invites_accept_creates_user_and_marks_token_used(
    app_client, db_engine
) -> None:
    from app.models import InviteToken, User

    raw = seed_unused_invite(db_engine=db_engine, email="new@example.com")
    r = app_client.post(
        "/invites/accept", json={"token": raw, "password": "longpassword1"}
    )
    assert r.status_code == 200
    assert r.json().get("ok") is True

    with Session(db_engine) as s:
        inv = s.exec(
            select(InviteToken).where(
                InviteToken.token_hash == InviteToken.hash_token(raw)
            )
        ).first()
        assert inv
        assert inv.used_at is not None
        u = s.exec(select(User).where(User.email == "new@example.com")).first()
        assert u
        from app.core.security import verify_password

        assert verify_password("longpassword1", u.hashed_password)


def test_invites_accept_sets_country_from_directory(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite:///{tmp_path / 'accept.db'}"
    from fastapi.testclient import TestClient

    app = load_wrapped_app(db_url=db_url, enable_directory=True)

    import app.db as db
    import app.services.directory as directory

    raw = seed_unused_invite(db_engine=db.engine, email="user@example.com")

    async def _fake_lookup(email: str):
        return directory.DirectoryEmailRecord(email="user@example.com", country="US")

    import app.routes.invites as invites_routes

    monkeypatch.setattr(invites_routes, "lookup_email_async", _fake_lookup)

    client = TestClient(app, base_url="http://testserver")
    r = client.post("/invites/accept", json={"token": raw, "password": "longpassword1"})
    assert r.status_code == 200

    h = bearer_for(client, email="user@example.com", password="longpassword1")
    me = client.get("/users/me", headers=h)
    assert me.status_code == 200
    assert me.json()["country"] == "US"


def test_invites_accept_grant_admin(tmp_path) -> None:
    from fastapi.testclient import TestClient

    db_url = f"sqlite:///{tmp_path / 'grant.db'}"
    app = load_wrapped_app(db_url=db_url)

    import app.db as db
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


def test_admin_patch_user_success(app_client, db_engine) -> None:
    admin_id = seed_admin(db_engine=db_engine)
    target_id = seed_user(
        db_engine=db_engine,
        email="target@example.com",
        password="pw",
    )
    h = bearer_for(app_client, email="admin@example.com", password="admin123")
    r = app_client.patch(
        f"/admin/users/{target_id}",
        headers=h,
        json={"full_name": "Updated Name"},
    )
    assert r.status_code == 200
    assert r.json()["user"]["full_name"] == "Updated Name"
    assert r.json()["user"]["id"] == target_id
    assert admin_id != target_id


def test_admin_patch_user_roles(app_client, db_engine) -> None:
    seed_admin(db_engine=db_engine)
    target_id = seed_user(
        db_engine=db_engine,
        email="roles@example.com",
        password="pw",
    )
    h = bearer_for(app_client, email="admin@example.com", password="admin123")
    r = app_client.patch(
        f"/admin/users/{target_id}",
        headers=h,
        json={"roles": ["User", "Super"]},
    )
    assert r.status_code == 200
    body = r.json()["user"]
    assert body["roles"] == ["User", "Super"]
    assert body["is_admin"] is True

    r2 = app_client.patch(
        f"/admin/users/{target_id}",
        headers=h,
        json={"roles": ["User"]},
    )
    assert r2.status_code == 200
    assert r2.json()["user"]["roles"] == ["User"]
    assert r2.json()["user"]["is_admin"] is False


def test_admin_cannot_modify_own_role(app_client, db_engine) -> None:
    admin_id = seed_admin(db_engine=db_engine)
    h = bearer_for(app_client, email="admin@example.com", password="admin123")
    r = app_client.patch(
        f"/admin/users/{admin_id}",
        headers=h,
        json={"is_admin": False},
    )
    assert r.status_code == 400
    assert "own" in str(r.json().get("detail", "")).lower()


def test_admin_delete_user_success(app_client, db_engine) -> None:
    seed_admin(db_engine=db_engine)
    target_id = seed_user(
        db_engine=db_engine,
        email="delete@example.com",
        password="pw",
    )
    h = bearer_for(app_client, email="admin@example.com", password="admin123")
    r = app_client.delete(f"/admin/users/{target_id}", headers=h)
    assert r.status_code == 200
    assert r.json().get("ok") is True

    from app.models import User

    with Session(db_engine) as s:
        u = s.exec(select(User).where(User.id == target_id)).first()
        assert u is None


def test_admin_cannot_delete_self(app_client, db_engine) -> None:
    admin_id = seed_admin(db_engine=db_engine)
    h = bearer_for(app_client, email="admin@example.com", password="admin123")
    r = app_client.delete(f"/admin/users/{admin_id}", headers=h)
    assert r.status_code == 400
    assert "own" in str(r.json().get("detail", "")).lower()


def test_non_admin_cannot_patch_users(app_client, db_engine) -> None:
    seed_user(
        db_engine=db_engine,
        email="plain@example.com",
        password="pw12345678",
    )
    target_id = seed_user(
        db_engine=db_engine,
        email="victim@example.com",
        password="pw",
    )
    h = bearer_for(app_client, email="plain@example.com", password="pw12345678")
    r = app_client.patch(
        f"/admin/users/{target_id}",
        headers=h,
        json={"full_name": "nope"},
    )
    assert r.status_code == 403
