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


def test_self_registration_disabled_blocks_register(
    app_client, db_engine, monkeypatch
) -> None:
    import app.core.config as config_mod

    monkeypatch.setattr(config_mod._defaults, "SELF_REGISTRATION_ENABLED", False)
    config_mod.refresh_settings()
    csrf, _ = _csrf_from_login_page(app_client)
    r_html = app_client.get("/register", follow_redirects=False)
    assert r_html.status_code in (302, 303)
    assert "/login" in (r_html.headers.get("location") or "")
    r_json = app_client.post(
        "/register",
        data={"email": "new@example.com", "csrf_token": csrf},
        headers={"Accept": "application/json"},
    )
    assert r_json.status_code == 403
    r_login = app_client.get("/login")
    assert r_login.status_code == 200
    assert "/register" not in r_login.text
    monkeypatch.setattr(config_mod._defaults, "SELF_REGISTRATION_ENABLED", True)
    config_mod.refresh_settings()


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
    r = client.post("/invites/accept", json={"token": raw, "password": "longpassword1"})
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
    statuses = [r.status_code if hasattr(r, "status_code") else 500 for r in results]
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


def _csrf_from_admin_page(client: TestClient) -> tuple[str, str]:
    r = client.get("/admin")
    assert r.status_code == 200
    cookie = client.cookies.get("um_csrf_token", "")
    assert cookie
    import re

    m = re.search(r'name="csrf_token" value="([^"]+)"', r.text)
    assert m
    return m.group(1), cookie


def _login_cookie(client: TestClient, *, email: str, password: str) -> None:
    csrf, _ = _csrf_from_login_page(client)
    r = client.post(
        "/login",
        data={"email": email, "password": password, "csrf_token": csrf},
        follow_redirects=False,
    )
    assert r.status_code in (303, 302, 200), r.text


def test_admin_invite_requires_csrf(app_client, db_engine) -> None:
    seed_admin(db_engine=db_engine)
    _login_cookie(app_client, email="admin@example.com", password="admin123")
    r = app_client.post(
        "/admin/invite",
        data={"email": "new@example.com", "grant_admin": "1"},
        headers={"Accept": "application/json"},
    )
    assert r.status_code == 403


def test_admin_invite_lookup_requires_csrf(app_client, db_engine) -> None:
    seed_admin(db_engine=db_engine)
    _login_cookie(app_client, email="admin@example.com", password="admin123")
    r = app_client.post(
        "/admin/invite/lookup",
        data={"email": "new@example.com"},
        headers={"Accept": "application/json"},
    )
    assert r.status_code == 403


def test_admin_invite_form_grant_admin_false_not_admin(app_client, db_engine) -> None:
    seed_admin(db_engine=db_engine)
    _login_cookie(app_client, email="admin@example.com", password="admin123")
    csrf, _ = _csrf_from_admin_page(app_client)
    r = app_client.post(
        "/admin/invite",
        data={
            "email": "new@example.com",
            "grant_admin": "false",
            "csrf_token": csrf,
        },
        headers={"Accept": "application/json"},
    )
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    from app.models import InviteToken

    with Session(db_engine) as s:
        inv = s.exec(
            select(InviteToken).where(InviteToken.email == "new@example.com")
        ).first()
        assert inv is not None
        assert inv.grant_admin is False


def test_non_admin_admin_page_does_not_list_users(app_client, db_engine) -> None:
    seed_user(db_engine=db_engine, email="user@example.com", password="longpassword1")
    seed_user(db_engine=db_engine, email="other@example.com", password="longpassword1")
    _login_cookie(app_client, email="user@example.com", password="longpassword1")
    r = app_client.get("/admin", follow_redirects=False)
    assert r.status_code in (302, 303)
    assert "other@example.com" not in (r.text or "")


def test_non_admin_users_route_redirects_to_account(app_client, db_engine) -> None:
    seed_user(db_engine=db_engine, email="user@example.com", password="longpassword1")
    _login_cookie(app_client, email="user@example.com", password="longpassword1")
    r = app_client.get("/users", follow_redirects=False)
    assert r.status_code in (302, 303)
    assert "/account" in (r.headers.get("location") or "")


def test_admin_users_route_redirects_to_admin(app_client, db_engine) -> None:
    seed_admin(db_engine=db_engine)
    _login_cookie(app_client, email="admin@example.com", password="admin123")
    r = app_client.get("/users", follow_redirects=False)
    assert r.status_code in (302, 303)
    assert "/admin" in (r.headers.get("location") or "")


def test_non_admin_nav_hides_admin_links(app_client, db_engine) -> None:
    seed_user(db_engine=db_engine, email="user@example.com", password="longpassword1")
    _login_cookie(app_client, email="user@example.com", password="longpassword1")
    r = app_client.get("/account")
    assert r.status_code == 200
    assert "Account" in r.text
    assert 'href="' not in r.text or "/admin" not in r.text.split("Account")[0]
    assert "/users" not in r.text


def test_non_admin_login_redirects_to_account(app_client, db_engine) -> None:
    seed_user(db_engine=db_engine, email="user@example.com", password="longpassword1")
    csrf, _ = _csrf_from_login_page(app_client)
    r = app_client.post(
        "/login",
        data={
            "email": "user@example.com",
            "password": "longpassword1",
            "csrf_token": csrf,
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "/account" in (r.headers.get("location") or "")


def test_reset_does_not_consume_token_when_user_deleted(app_client, db_engine) -> None:
    from app.models import PasswordResetToken, User

    from datetime import timedelta

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

    r = app_client.post(
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


def test_logout_invalidates_bearer_token(app_client, db_engine) -> None:
    seed_user(db_engine=db_engine, email="user@example.com", password="longpassword1")
    h = bearer_for(app_client, email="user@example.com", password="longpassword1")
    me = app_client.get("/users/me", headers=h)
    assert me.status_code == 200

    csrf, _ = _csrf_from_login_page(app_client)
    _login_cookie(app_client, email="user@example.com", password="longpassword1")
    csrf, _ = _csrf_from_login_page(app_client)
    out = app_client.post("/logout", data={"csrf_token": csrf}, follow_redirects=False)
    assert out.status_code == 303

    me2 = app_client.get("/users/me", headers=h)
    assert me2.status_code == 401


def test_seed_user_migration_skips_without_credentials() -> None:
    import importlib.util
    from pathlib import Path

    path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "0003_seed_user.py"
    )
    spec = importlib.util.spec_from_file_location("seed_user_mod", path)
    assert spec and spec.loader
    seed_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(seed_mod)

    import os

    os.environ.pop("SEED_USER_EMAIL", None)
    os.environ.pop("SEED_USER_PASSWORD", None)
    assert seed_mod._seed_credentials() is None


def test_seed_migration_requires_opt_in_and_strong_password() -> None:
    import importlib.util
    from pathlib import Path

    path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "0002_seed_admin.py"
    )
    spec = importlib.util.spec_from_file_location("seed_mod", path)
    assert spec and spec.loader
    seed_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(seed_mod)

    import os

    os.environ.pop("SEED_ADMIN_ENABLED", None)
    assert seed_mod._seed_enabled() is False

    os.environ["SEED_ADMIN_ENABLED"] = "1"
    os.environ.pop("SEED_ADMIN_PASSWORD", None)
    try:
        with pytest.raises(RuntimeError, match="SEED_ADMIN_PASSWORD"):
            seed_mod.upgrade()
    finally:
        os.environ.pop("SEED_ADMIN_ENABLED", None)

    try:
        with pytest.raises(RuntimeError, match="too weak"):
            seed_mod._validate_seed_password("passwordpassword")
    finally:
        os.environ.pop("SEED_ADMIN_ENABLED", None)
        os.environ.pop("SEED_ADMIN_PASSWORD", None)


def test_admin_invite_html_does_not_contain_token(app_client, db_engine) -> None:
    seed_admin(db_engine=db_engine)
    _login_cookie(app_client, email="admin@example.com", password="admin123")
    csrf, _ = _csrf_from_admin_page(app_client)
    r = app_client.post(
        "/admin/invite",
        data={
            "email": "html@example.com",
            "csrf_token": csrf,
        },
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert "/invites/accept?token=" not in r.text
    assert "Invite email sent" in r.text


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
