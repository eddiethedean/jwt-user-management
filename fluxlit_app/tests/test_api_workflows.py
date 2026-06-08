"""API workflow tests (admin, invites, password reset) via FluxLitTestClient."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fluxlit.testing import FluxLitTestClient
from sqlmodel import Session, select

from fluxlit_test_helpers import (
    bearer_for,
    load_fluxlit_app,
    seed_admin,
    seed_unused_invite,
    seed_user,
)


@pytest.fixture
def fluxlit_app(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'workflows.db'}"
    return load_fluxlit_app(db_url=db_url)


@pytest.fixture
def tc(fluxlit_app):
    return FluxLitTestClient(fluxlit_app)


@pytest.fixture
def db_engine(fluxlit_app):
    import app.db as db

    return db.engine


def test_auth_token_unknown_user_returns_400(tc) -> None:
    r = tc.api_post(
        "/auth/token",
        data={"username": "missing@example.com", "password": "any"},
    )
    assert r.status_code == 400


def test_auth_token_inactive_user_returns_400(tc, db_engine) -> None:
    seed_user(
        db_engine=db_engine,
        email="sleepy@example.com",
        password="pw12345678",
        is_active=False,
    )
    r = tc.api_post(
        "/auth/token",
        data={"username": "sleepy@example.com", "password": "pw12345678"},
    )
    assert r.status_code == 400


def test_users_list_requires_admin(tc, db_engine) -> None:
    seed_user(
        db_engine=db_engine,
        email="list@example.com",
        password="secret123456",
    )
    h = bearer_for(tc, email="list@example.com", password="secret123456")
    r = tc.api_get("/users", headers=h)
    assert r.status_code == 403


def test_users_list_success_for_admin(tc, db_engine) -> None:
    seed_admin(db_engine=db_engine)
    seed_user(db_engine=db_engine, email="u@example.com", password="pw12345678")
    h = bearer_for(tc, email="admin@example.com", password="admin123")
    r = tc.api_get("/users", headers=h)
    assert r.status_code == 200
    users = r.json()
    assert isinstance(users, list)
    emails = {u["email"] for u in users}
    assert "admin@example.com" in emails
    assert "u@example.com" in emails


def test_invites_accept_creates_user_and_marks_token_used(tc, db_engine) -> None:
    from app.core.security import verify_password
    from app.models import InviteToken, User

    raw = seed_unused_invite(db_engine=db_engine, email="new@example.com")
    r = tc.api_post(
        "/invites/accept",
        json={"token": raw, "password": "longpassword12"},
    )
    assert r.status_code == 200
    assert r.json().get("ok") is True

    with Session(db_engine) as s:
        inv = s.exec(
            select(InviteToken).where(
                InviteToken.token_hash == InviteToken.hash_token(raw)
            )
        ).first()
        assert inv is not None
        assert inv.used_at is not None
        assert isinstance(inv.used_at, datetime)
        u = s.exec(select(User).where(User.email == "new@example.com")).first()
        assert u is not None
        assert verify_password("longpassword12", u.hashed_password)


def test_invites_accept_sets_country_from_directory(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite:///{tmp_path / 'accept.db'}"
    app = load_fluxlit_app(
        db_url=db_url,
        extra_env={"DIRECTORY_LOOKUP_URL": "http://directory.test/ldapEmail"},
    )

    import app.db as db
    import app.services.directory as directory

    raw = seed_unused_invite(db_engine=db.engine, email="user@example.com")

    async def _fake_lookup(email: str):
        return directory.DirectoryEmailRecord(email="user@example.com", country="US")

    import app.routes.invites as invites_routes

    monkeypatch.setattr(invites_routes, "lookup_email_async", _fake_lookup)

    tc = FluxLitTestClient(app)
    r = tc.api_post(
        "/invites/accept",
        json={"token": raw, "password": "longpassword12"},
    )
    assert r.status_code == 200

    h = bearer_for(tc, email="user@example.com", password="longpassword12")
    me = tc.api_get("/users/me", headers=h)
    assert me.status_code == 200
    assert me.json()["country"] == "US"


def test_invites_accept_grant_admin_sets_configured_roles(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path / 'grant.db'}"
    app = load_fluxlit_app(db_url=db_url)

    import app.db as db
    from app.models import User

    raw = seed_unused_invite(
        db_engine=db.engine, email="admin2@example.com", grant_admin=True
    )
    tc = FluxLitTestClient(app)
    r = tc.api_post(
        "/invites/accept",
        json={"token": raw, "password": "longpassword12"},
    )
    assert r.status_code == 200

    with Session(db.engine) as s:
        u = s.exec(select(User).where(User.email == "admin2@example.com")).first()
        assert u is not None
        assert u.is_admin is True


def test_invite_accept_rejects_short_password(tc, db_engine) -> None:
    raw = seed_unused_invite(db_engine=db_engine, email="short@example.com")
    r = tc.api_post(
        "/invites/accept",
        json={"token": raw, "password": "short"},
    )
    assert r.status_code == 400


def test_admin_patch_user_success(tc, db_engine) -> None:
    admin_id = seed_admin(db_engine=db_engine)
    target_id = seed_user(
        db_engine=db_engine,
        email="target@example.com",
        password="pw12345678",
    )
    h = bearer_for(tc, email="admin@example.com", password="admin123")
    r = tc.api.request(
        "PATCH",
        f"{tc.api_prefix}/admin/users/{target_id}",
        headers=h,
        json={"full_name": "Updated Name"},
    )
    assert r.status_code == 200
    assert r.json()["user"]["full_name"] == "Updated Name"
    assert r.json()["user"]["id"] == target_id
    assert admin_id != target_id


def test_admin_patch_user_roles(tc, db_engine) -> None:
    seed_admin(db_engine=db_engine)
    target_id = seed_user(
        db_engine=db_engine,
        email="roles@example.com",
        password="pw12345678",
    )
    h = bearer_for(tc, email="admin@example.com", password="admin123")
    r = tc.api.request(
        "PATCH",
        f"{tc.api_prefix}/admin/users/{target_id}",
        headers=h,
        json={"roles": ["User", "Super"]},
    )
    assert r.status_code == 200
    body = r.json()["user"]
    assert body["roles"] == ["User", "Super"]
    assert body["is_admin"] is True

    r2 = tc.api.request(
        "PATCH",
        f"{tc.api_prefix}/admin/users/{target_id}",
        headers=h,
        json={"roles": ["User"]},
    )
    assert r2.status_code == 200
    assert r2.json()["user"]["roles"] == ["User"]
    assert r2.json()["user"]["is_admin"] is False


def test_admin_cannot_modify_own_role(tc, db_engine) -> None:
    admin_id = seed_admin(db_engine=db_engine)
    h = bearer_for(tc, email="admin@example.com", password="admin123")
    r = tc.api.request(
        "PATCH",
        f"{tc.api_prefix}/admin/users/{admin_id}",
        headers=h,
        json={"is_admin": False},
    )
    assert r.status_code == 400
    assert "own" in str(r.json().get("detail", "")).lower()


def test_admin_delete_user_success(tc, db_engine) -> None:
    seed_admin(db_engine=db_engine)
    target_id = seed_user(
        db_engine=db_engine,
        email="delete@example.com",
        password="pw12345678",
    )
    h = bearer_for(tc, email="admin@example.com", password="admin123")
    r = tc.api.request(
        "DELETE",
        f"{tc.api_prefix}/admin/users/{target_id}",
        headers=h,
    )
    assert r.status_code == 200
    assert r.json().get("ok") is True

    from app.models import User

    with Session(db_engine) as s:
        u = s.exec(select(User).where(User.id == target_id)).first()
        assert u is None


def test_admin_cannot_delete_self(tc, db_engine) -> None:
    admin_id = seed_admin(db_engine=db_engine)
    h = bearer_for(tc, email="admin@example.com", password="admin123")
    r = tc.api.request(
        "DELETE",
        f"{tc.api_prefix}/admin/users/{admin_id}",
        headers=h,
    )
    assert r.status_code == 400
    assert "own" in str(r.json().get("detail", "")).lower()


def test_admin_invite_rejects_domain_not_in_allowlist(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path / 'domains.db'}"
    app = load_fluxlit_app(
        db_url=db_url,
        invite_allowed_email_domains=("allowed.org",),
    )
    import app.db as db

    seed_admin(db_engine=db.engine)
    tc = FluxLitTestClient(app)
    h = bearer_for(tc, email="admin@example.com", password="admin123")

    r_bad = tc.api_post(
        "/invites",
        headers=h,
        json={"email": "u@example.com", "grant_admin": False},
    )
    assert r_bad.status_code == 422

    r_ok = tc.api_post(
        "/invites",
        headers=h,
        json={"email": "u@allowed.org", "grant_admin": False},
    )
    assert r_ok.status_code == 200


def test_password_forgot_is_non_enumerating_for_unknown_email(tc) -> None:
    r = tc.api_post("/password/forgot", json={"email": "missing@example.com"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_password_reset_api_updates_password_and_marks_token_used(
    tc, db_engine
) -> None:
    from app.core.security import verify_password
    from app.models import PasswordResetToken, User

    seed_user(
        db_engine=db_engine,
        email="user@example.com",
        password="oldpw1234567",
        is_admin=False,
    )

    raw = PasswordResetToken.new_raw_token()
    now = datetime.now(timezone.utc)
    rec = PasswordResetToken(
        email="user@example.com",
        token_hash=PasswordResetToken.hash_token(raw),
        created_at=now,
        expires_at=now.replace(year=2099),
        used_at=None,
    )
    with Session(db_engine) as s:
        s.add(rec)
        s.commit()

    r = tc.api_post(
        "/password/reset",
        json={"token": raw, "password": "newpassword12"},
    )
    assert r.status_code == 200
    assert r.json() == {"ok": True}

    with Session(db_engine) as s:
        u = s.exec(select(User).where(User.email == "user@example.com")).first()
        assert u is not None
        assert verify_password("newpassword12", u.hashed_password)
        pr = s.exec(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == PasswordResetToken.hash_token(raw)
            )
        ).first()
        assert pr is not None
        assert pr.used_at is not None


def test_password_reset_rejects_password_shorter_than_min(tc, db_engine) -> None:
    from app.models import PasswordResetToken

    seed_user(
        db_engine=db_engine,
        email="user@example.com",
        password="oldpw1234567",
    )
    raw = PasswordResetToken.new_raw_token()
    now = datetime.now(timezone.utc)
    rec = PasswordResetToken(
        email="user@example.com",
        token_hash=PasswordResetToken.hash_token(raw),
        created_at=now,
        expires_at=now.replace(year=2099),
        used_at=None,
    )
    with Session(db_engine) as s:
        s.add(rec)
        s.commit()

    r = tc.api_post(
        "/password/reset",
        json={"token": raw, "password": "short"},
    )
    assert r.status_code == 400
