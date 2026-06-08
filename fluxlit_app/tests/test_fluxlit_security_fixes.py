"""Regression tests for security and correctness fixes (parity with user_management_api)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fluxlit.testing import FluxLitTestClient
from sqlmodel import Session, select

from fluxlit_test_helpers import (
    FakeHttpxResponse,
    bearer_for,
    load_fluxlit_app,
    seed_admin,
    seed_unused_invite,
    seed_user,
)


@pytest.fixture
def fluxlit_app(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'sec.db'}"
    return load_fluxlit_app(db_url=db_url)


@pytest.fixture
def tc(fluxlit_app):
    return FluxLitTestClient(fluxlit_app)


@pytest.fixture
def db_engine(fluxlit_app):
    import app.db as db

    return db.engine


def test_create_invite_rejects_string_grant_admin(tc, db_engine) -> None:
    seed_admin(db_engine=db_engine)
    h = bearer_for(tc, email="admin@example.com", password="admin123")
    r = tc.api_post(
        "/invites",
        headers=h,
        json={"email": "new@example.com", "grant_admin": "false"},
    )
    assert r.status_code == 422


def test_admin_patch_rejects_string_is_active(tc, db_engine) -> None:
    seed_admin(db_engine=db_engine)
    target_id = seed_user(
        db_engine=db_engine,
        email="inactive@example.com",
        password="pw",
        is_active=False,
    )
    h = bearer_for(tc, email="admin@example.com", password="admin123")
    r = tc.api.request(
        "PATCH",
        f"{tc.api_prefix}/admin/users/{target_id}",
        headers=h,
        json={"is_active": "false"},
    )
    assert r.status_code == 422


def test_invite_rejects_existing_user(tc, db_engine) -> None:
    seed_admin(db_engine=db_engine)
    seed_user(db_engine=db_engine, email="taken@example.com", password="pw")
    h = bearer_for(tc, email="admin@example.com", password="admin123")
    r = tc.api_post(
        "/invites",
        headers=h,
        json={"email": "taken@example.com", "grant_admin": False},
    )
    assert r.status_code == 409


def test_invite_rejects_email_with_newline(tc, db_engine) -> None:
    seed_admin(db_engine=db_engine)
    h = bearer_for(tc, email="admin@example.com", password="admin123")
    r = tc.api_post(
        "/invites",
        headers=h,
        json={"email": "bad@example.com\nBcc: evil@evil.com", "grant_admin": False},
    )
    assert r.status_code == 422


def test_accept_ignores_directory_email_mismatch(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite:///{tmp_path / 'mismatch.db'}"
    app = load_fluxlit_app(
        db_url=db_url,
        extra_env={
            "DIRECTORY_LOOKUP_URL": "http://directory.test/ldapEmail",
            "DIRECTORY_LOOKUP_REQUIRED": "true",
        },
    )
    import app.db as db
    import app.services.directory as directory

    raw = seed_unused_invite(db_engine=db.engine, email="user@example.com")

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, *args, **kwargs):
            return FakeHttpxResponse(
                status_code=200,
                json_data={
                    "attributes": {
                        "mail": ["other@example.com"],
                        "co": ["US"],
                    }
                },
            )

    monkeypatch.setattr(directory.httpx, "AsyncClient", _FakeAsyncClient)

    tc = FluxLitTestClient(app)
    r = tc.api_post("/invites/accept", json={"token": raw, "password": "longpassword1"})
    assert r.status_code == 200
    h = bearer_for(tc, email="user@example.com", password="longpassword1")
    me = tc.api_get("/users/me", headers=h)
    assert me.json().get("country") in (None, "")


def test_concurrent_invite_accept_one_wins(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path / 'race.db'}"
    fluxlit = load_fluxlit_app(db_url=db_url)
    import app.db as db

    raw1 = seed_unused_invite(db_engine=db.engine, email="race@example.com")
    raw2 = seed_unused_invite(db_engine=db.engine, email="race@example.com")

    async def accept(token: str):
        from httpx import ASGITransport, AsyncClient

        transport = ASGITransport(app=fluxlit.api)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            return await ac.post(
                "/invites/accept",
                json={"token": token, "password": "longpassword1"},
            )

    async def run_both():
        return await asyncio.gather(accept(raw1), accept(raw2), return_exceptions=True)

    results = asyncio.run(run_both())
    statuses = [r.status_code if hasattr(r, "status_code") else 500 for r in results]
    assert 200 in statuses
    assert 400 in statuses


def test_rate_limit_returns_429(tc, db_engine, monkeypatch) -> None:
    import app.core.config as config
    from app.core.rate_limit import reset_rate_limits_for_tests

    config.settings.rate_limit_enabled = True
    config.settings.rate_limit_auth_per_minute = 2
    reset_rate_limits_for_tests()
    for _ in range(2):
        tc.api_post(
            "/auth/token",
            data={"username": "nobody@example.com", "password": "wrong"},
        )
    r = tc.api_post(
        "/auth/token",
        data={"username": "nobody@example.com", "password": "wrong"},
    )
    assert r.status_code == 429
    reset_rate_limits_for_tests()


def test_reset_does_not_consume_token_when_user_deleted(tc, db_engine) -> None:
    from app.models import PasswordResetToken, User

    uid = seed_user(
        db_engine=db_engine, email="gone@example.com", password="longpassword1"
    )

    raw_token = PasswordResetToken.new_raw_token()
    now = datetime.now(timezone.utc)
    rec = PasswordResetToken(
        email="gone@example.com",
        token_hash=PasswordResetToken.hash_token(raw_token),
        created_at=now,
        expires_at=now + timedelta(hours=2),
        used_at=None,
    )
    with Session(db_engine) as s:
        s.add(rec)
        u = s.get(User, uid)
        assert u
        s.delete(u)
        s.commit()

    r = tc.api_post(
        "/password/reset",
        json={"token": raw_token, "password": "anotherlongpass"},
    )
    assert r.status_code == 400
    with Session(db_engine) as s:
        row = s.exec(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash
                == PasswordResetToken.hash_token(raw_token)
            )
        ).first()
        assert row is not None
        assert row.used_at is None


def test_self_registration_disabled_blocks_register(tc, monkeypatch) -> None:
    import app.core.config as config_mod

    monkeypatch.setattr(config_mod._defaults, "SELF_REGISTRATION_ENABLED", False)
    config_mod.refresh_settings()
    r = tc.api_post("/register", data={"email": "new@example.com"})
    assert r.status_code == 403
    monkeypatch.setattr(config_mod._defaults, "SELF_REGISTRATION_ENABLED", True)
    config_mod.refresh_settings()


def test_admin_patch_is_admin_syncs_roles(tc, db_engine) -> None:
    seed_admin(db_engine=db_engine)
    target_id = seed_user(
        db_engine=db_engine,
        email="sync@example.com",
        password="longpassword1",
        is_admin=False,
    )
    h = bearer_for(tc, email="admin@example.com", password="admin123")

    r = tc.api.request(
        "PATCH",
        f"{tc.api_prefix}/admin/users/{target_id}",
        headers=h,
        json={"is_admin": True},
    )
    assert r.status_code == 200
    body = r.json()["user"]
    assert body["is_admin"] is True
    assert body["roles"] == ["Admin", "Super"]

    r2 = tc.api.request(
        "PATCH",
        f"{tc.api_prefix}/admin/users/{target_id}",
        headers=h,
        json={"is_admin": False},
    )
    assert r2.status_code == 200
    assert r2.json()["user"]["roles"] == ["User"]
    assert r2.json()["user"]["is_admin"] is False


def test_smtp_no_fallback_without_flag(monkeypatch) -> None:
    import app.core.config as config
    from app.services import email as email_mod
    from email.message import EmailMessage

    config.settings.smtp_host = "smtp.test"
    config.settings.smtp_port = 587
    config.settings.smtp_use_tls = True
    config.settings.smtp_username = "user"
    config.settings.smtp_password = "pass"
    config.settings.smtp_allow_legacy_port25_fallback = False

    def boom(*a, **k):
        raise ConnectionRefusedError()

    monkeypatch.setattr(email_mod.smtplib, "SMTP", boom)
    msg = EmailMessage()
    msg["From"] = "a@b.com"
    msg["To"] = "c@d.com"
    msg.set_content("hi")
    with pytest.raises(ConnectionRefusedError):
        email_mod._send_via_smtp(msg)
