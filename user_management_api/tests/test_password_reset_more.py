from datetime import datetime, timedelta, timezone

from sqlmodel import select

from app.api.routes_password import _hash_token
from app.models.password_reset import PasswordResetToken


def test_forgot_password_inactive_user_is_non_enumerating(
    client, normal_user, db_session
):
    # Mark user inactive
    normal_user.is_active = False
    db_session.add(normal_user)
    db_session.commit()

    r = client.post("/password/forgot", json={"email": normal_user.email})
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_reset_password_token_not_found(client):
    r = client.post("/password/reset", json={"token": "nope", "password": "X"})
    assert r.status_code == 404


def test_reset_password_user_not_found(client, db_session):
    token = "tok-user-missing"
    prt = PasswordResetToken(
        email="missing@test.local",
        token_hash=_hash_token(token),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    db_session.add(prt)
    db_session.commit()

    r = client.post("/password/reset", json={"token": token, "password": "NewPass123!"})
    assert r.status_code == 404


def test_reset_password_marks_token_used(client, normal_user, db_session):
    token = "tok-mark-used"
    prt = PasswordResetToken(
        email=normal_user.email,
        token_hash=_hash_token(token),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    db_session.add(prt)
    db_session.commit()

    r = client.post("/password/reset", json={"token": token, "password": "NewPass123!"})
    assert r.status_code == 200

    used = db_session.exec(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == _hash_token(token)
        )
    ).first()
    assert used is not None
    assert used.used_at is not None
