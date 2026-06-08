"""Regression tests for subtle session, token, and inspect defects."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fluxlit.testing import FluxLitTestClient
from sqlmodel import Session, select

from fluxlit_test_helpers import (
    bearer_for,
    load_fluxlit_app,
    seed_user,
    seed_unused_invite,
)


@pytest.fixture
def fluxlit_app(tmp_path):
    return load_fluxlit_app(db_url=f"sqlite:///{tmp_path / 'subtle.db'}")


@pytest.fixture
def tc(fluxlit_app):
    return FluxLitTestClient(fluxlit_app)


@pytest.fixture
def db_engine(fluxlit_app):
    import app.db as db

    return db.engine


def test_password_change_returns_new_token_and_invalidates_old(tc, db_engine) -> None:
    seed_user(
        db_engine=db_engine,
        email="pw@example.com",
        password="oldpassword12",
    )
    h = bearer_for(tc, email="pw@example.com", password="oldpassword12")
    old_token = h["Authorization"].removeprefix("Bearer ")

    r = tc.api_post(
        "/users/me/password",
        headers=h,
        json={
            "current_password": "oldpassword12",
            "new_password": "newpassword12",
            "confirm_password": "newpassword12",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("access_token")
    assert body.get("token_type") == "bearer"

    me_old = tc.api_get("/users/me", headers={"Authorization": f"Bearer {old_token}"})
    assert me_old.status_code == 401

    new_h = {"Authorization": f"Bearer {body['access_token']}"}
    me_new = tc.api_get("/users/me", headers=new_h)
    assert me_new.status_code == 200


def test_password_change_rejects_same_password(tc, db_engine) -> None:
    seed_user(
        db_engine=db_engine,
        email="same@example.com",
        password="samepassword12",
    )
    h = bearer_for(tc, email="same@example.com", password="samepassword12")
    r = tc.api_post(
        "/users/me/password",
        headers=h,
        json={
            "current_password": "samepassword12",
            "new_password": "samepassword12",
            "confirm_password": "samepassword12",
        },
    )
    assert r.status_code == 400
    me = tc.api_get("/users/me", headers=h)
    assert me.status_code == 200


def test_forgot_password_no_token_when_smtp_unconfigured(tc, db_engine) -> None:
    from app.models import PasswordResetToken

    seed_user(
        db_engine=db_engine,
        email="user@example.com",
        password="longpassword12",
    )
    import app.core.config as config

    config.settings.smtp_host = ""
    config.settings.smtp_from_email = ""

    r = tc.api_post("/password/forgot", json={"email": "user@example.com"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}

    with Session(db_engine) as s:
        rows = s.exec(
            select(PasswordResetToken).where(
                PasswordResetToken.email == "user@example.com"
            )
        ).all()
    assert rows == []


def test_forgot_password_503_when_smtp_send_fails(tc, db_engine, monkeypatch) -> None:
    seed_user(
        db_engine=db_engine,
        email="fail@example.com",
        password="longpassword12",
    )
    import app.core.config as config

    config.settings.smtp_host = "smtp.test.local"
    config.settings.smtp_from_email = "noreply@test.local"

    def boom(**kwargs):
        raise ConnectionError("smtp down")

    monkeypatch.setattr(
        "app.routes.password_reset.send_password_reset_email",
        boom,
    )

    r = tc.api_post("/password/forgot", json={"email": "fail@example.com"})
    assert r.status_code == 503


def test_invite_inspect_rejects_used_token(tc, db_engine) -> None:
    from app.models import InviteToken

    raw = seed_unused_invite(db_engine=db_engine, email="used@example.com")
    token_hash = InviteToken.hash_token(raw)
    with Session(db_engine) as s:
        inv = s.exec(
            select(InviteToken).where(InviteToken.token_hash == token_hash)
        ).first()
        assert inv is not None
        inv.used_at = datetime.now(timezone.utc)
        s.add(inv)
        s.commit()

    r = tc.api_post("/invites/inspect", json={"token": raw})
    assert r.status_code == 404


def test_password_inspect_rejects_used_token(tc, db_engine) -> None:
    from app.models import PasswordResetToken

    raw = PasswordResetToken.new_raw_token()
    now = datetime.now(timezone.utc)
    rec = PasswordResetToken(
        email="used@example.com",
        token_hash=PasswordResetToken.hash_token(raw),
        created_at=now,
        expires_at=now.replace(year=2099),
        used_at=now,
    )
    with Session(db_engine) as s:
        s.add(rec)
        s.commit()

    r = tc.api_post("/password/inspect", json={"token": raw})
    assert r.status_code == 404
