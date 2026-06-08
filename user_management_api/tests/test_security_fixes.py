"""Regression tests for security and correctness fixes."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from api_test_helpers import (
    FakeHttpxResponse,
    bearer_for,
    load_wrapped_app,
    seed_admin,
    seed_unused_invite,
    seed_user,
)


def _csrf_from_login_page(client: TestClient) -> tuple[str, str]:
    r = client.get("/login")
    assert r.status_code == 200
    cookie = client.cookies.get("um_csrf_token", "")
    assert cookie
    import re

    m = re.search(r'name="csrf_token" value="([^"]+)"', r.text)
    assert m
    return m.group(1), cookie


def test_forgot_form_never_returns_reset_url(app_client, db_engine) -> None:
    seed_user(db_engine=db_engine, email="user@example.com", password="pw")
    csrf, _ = _csrf_from_login_page(app_client)
    r = app_client.post(
        "/password/forgot-form",
        data={"email": "user@example.com", "csrf_token": csrf},
    )
    assert r.status_code == 200
    assert "reset?token=" not in r.text
    assert "/password/reset?token=" not in r.text


def test_create_invite_rejects_string_grant_admin(app_client, db_engine) -> None:
    seed_admin(db_engine=db_engine)
    h = bearer_for(app_client, email="admin@example.com", password="admin123")
    r = app_client.post(
        "/invites",
        headers=h,
        json={"email": "new@example.com", "grant_admin": "false"},
    )
    assert r.status_code == 422


def test_admin_patch_rejects_string_is_active(app_client, db_engine) -> None:
    admin_id = seed_admin(db_engine=db_engine)
    target_id = seed_user(
        db_engine=db_engine,
        email="inactive@example.com",
        password="pw",
        is_active=False,
    )
    h = bearer_for(app_client, email="admin@example.com", password="admin123")
    r = app_client.patch(
        f"/admin/users/{target_id}",
        headers=h,
        json={"is_active": "false"},
    )
    assert r.status_code == 422
    assert admin_id != target_id


def test_inspect_requires_admin(app_client, db_engine) -> None:
    raw = seed_unused_invite(db_engine=db_engine, email="inv@example.com")
    r = app_client.post("/invites/inspect", json={"token": raw})
    assert r.status_code == 401
    seed_admin(db_engine=db_engine)
    h = bearer_for(app_client, email="admin@example.com", password="admin123")
    r2 = app_client.post("/invites/inspect", headers=h, json={"token": raw})
    assert r2.status_code == 200


def test_register_json_same_response_existing_user(app_client, db_engine) -> None:
    seed_user(db_engine=db_engine, email="exists@example.com", password="longpassword1")
    csrf, _ = _csrf_from_login_page(app_client)
    r_existing = app_client.post(
        "/register",
        data={"email": "exists@example.com", "csrf_token": csrf},
        headers={"Accept": "application/json"},
    )
    assert r_existing.status_code == 200
    assert r_existing.json() == {"ok": True}
    assert "email_sent" not in r_existing.json()


def test_invite_rejects_existing_user(app_client, db_engine) -> None:
    seed_admin(db_engine=db_engine)
    seed_user(db_engine=db_engine, email="taken@example.com", password="pw")
    h = bearer_for(app_client, email="admin@example.com", password="admin123")
    r = app_client.post(
        "/invites",
        headers=h,
        json={"email": "taken@example.com", "grant_admin": False},
    )
    assert r.status_code == 409


def test_invite_rejects_email_with_newline(app_client, db_engine) -> None:
    seed_admin(db_engine=db_engine)
    h = bearer_for(app_client, email="admin@example.com", password="admin123")
    r = app_client.post(
        "/invites",
        headers=h,
        json={"email": "bad@example.com\nBcc: evil@evil.com", "grant_admin": False},
    )
    assert r.status_code == 422


def test_accept_ignores_directory_email_mismatch(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite:///{tmp_path / 'mismatch.db'}"
    app = load_wrapped_app(db_url=db_url, enable_directory=True)
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

    client = TestClient(app, base_url="http://testserver")
    r = client.post(
        "/invites/accept", json={"token": raw, "password": "longpassword1"}
    )
    assert r.status_code == 200
    h = bearer_for(client, email="user@example.com", password="longpassword1")
    me = client.get("/users/me", headers=h)
    assert me.json().get("country") in (None, "")


def test_concurrent_invite_accept_one_wins(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path / 'race.db'}"
    app = load_wrapped_app(db_url=db_url)
    import app.db as db

    raw1 = seed_unused_invite(db_engine=db.engine, email="race@example.com")
    raw2 = seed_unused_invite(db_engine=db.engine, email="race@example.com")
    client = TestClient(app, base_url="http://testserver")

    async def accept(token: str):
        from httpx import ASGITransport, AsyncClient

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            return await ac.post(
                "/invites/accept",
                json={"token": token, "password": "longpassword1"},
            )

    async def run_both():
        return await asyncio.gather(accept(raw1), accept(raw2), return_exceptions=True)

    results = asyncio.run(run_both())
    statuses = [
        r.status_code if hasattr(r, "status_code") else 500 for r in results
    ]
    assert 200 in statuses
    assert 400 in statuses


def test_consume_token_used_at_is_datetime(app_client, db_engine) -> None:
    from app.models import InviteToken

    raw = seed_unused_invite(db_engine=db_engine, email="dt@example.com")
    r = app_client.post(
        "/invites/accept", json={"token": raw, "password": "longpassword1"}
    )
    assert r.status_code == 200
    with Session(db_engine) as s:
        inv = s.exec(
            select(InviteToken).where(
                InviteToken.token_hash == InviteToken.hash_token(raw)
            )
        ).first()
        assert inv
        assert isinstance(inv.used_at, datetime)


def test_rate_limit_returns_429(app_client, db_engine, monkeypatch) -> None:
    import app.core.config as config

    config.settings.rate_limit_enabled = True
    config.settings.rate_limit_auth_per_minute = 2
    from app.core.rate_limit import reset_rate_limits_for_tests

    reset_rate_limits_for_tests()
    for _ in range(2):
        app_client.post(
            "/auth/token",
            data={"username": "nobody@example.com", "password": "wrong"},
        )
    r = app_client.post(
        "/auth/token",
        data={"username": "nobody@example.com", "password": "wrong"},
    )
    assert r.status_code == 429
    reset_rate_limits_for_tests()


def test_csrf_blocks_post_without_token(app_client) -> None:
    r = app_client.post(
        "/password/forgot-form",
        data={"email": "a@example.com"},
    )
    assert r.status_code == 403


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
