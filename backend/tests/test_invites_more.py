from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlmodel import select

from app.core.config import settings
from app.models.invite import InviteToken


@pytest.fixture()
def admin_key():
    old = settings.admin_api_key
    settings.admin_api_key = "test-key"
    try:
        yield
    finally:
        settings.admin_api_key = old


def test_invite_accept_cannot_be_reused(client, admin_key, db_session):
    resp = client.post(
        "/invites",
        headers={"X-Admin-Api-Key": "test-key"},
        json={
            "email": "reuse@test.local",
            "full_name": None,
            "is_admin": False,
            "permissions": [],
        },
    )
    token = resp.json()["invite_url"].split("token=", 1)[1]

    r1 = client.post("/invites/accept", json={"token": token, "password": "P@ssw0rd!"})
    assert r1.status_code == 200

    r2 = client.post("/invites/accept", json={"token": token, "password": "P@ssw0rd!"})
    assert r2.status_code == 400
    assert r2.json()["detail"] == "Invite already used"


def test_invite_accept_expired_rejected(client, admin_key, db_session):
    # Create invite
    resp = client.post(
        "/invites",
        headers={"X-Admin-Api-Key": "test-key"},
        json={
            "email": "expired@test.local",
            "full_name": None,
            "is_admin": False,
            "permissions": [],
        },
    )
    token = resp.json()["invite_url"].split("token=", 1)[1]

    # Force expiry in DB
    inv = db_session.exec(select(InviteToken).order_by(text("id DESC"))).first()
    assert inv is not None
    inv.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    db_session.add(inv)
    db_session.commit()

    r = client.post("/invites/accept", json={"token": token, "password": "P@ssw0rd!"})
    assert r.status_code == 400
    assert r.json()["detail"] == "Invite expired"
