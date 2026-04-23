from datetime import datetime, timedelta, timezone

from sqlmodel import select

from app.models.password_reset import PasswordResetToken


def test_forgot_password_is_non_enumerating(client):
    # Unknown email should still return ok=True
    r = client.post("/password/forgot", json={"email": "nope@test.local"})
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_reset_password_flow(client, normal_user, db_session):
    # Request reset (creates token record)
    r = client.post("/password/forgot", json={"email": normal_user.email})
    assert r.status_code == 200
    assert r.json()["ok"] is True

    prt = db_session.exec(
        select(PasswordResetToken).where(PasswordResetToken.email == normal_user.email)
    ).first()
    assert prt is not None

    # We can't recover the raw token from the hash; simulate by creating one directly
    # by inserting a known hash.
    from app.api.routes_password import _hash_token

    token = "known-token"
    prt2 = PasswordResetToken(
        email=normal_user.email,
        token_hash=_hash_token(token),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    db_session.add(prt2)
    db_session.commit()

    # Reset password
    r2 = client.post(
        "/password/reset", json={"token": token, "password": "NewPass123!"}
    )
    assert r2.status_code == 200
    assert r2.json()["ok"] is True

    # Token cannot be reused
    r3 = client.post(
        "/password/reset", json={"token": token, "password": "NewPass123!"}
    )
    assert r3.status_code == 400

    # New password works for login
    login = client.post(
        "/auth/token",
        data={"username": normal_user.email, "password": "NewPass123!"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert login.status_code == 200


def test_reset_password_expired_token_rejected(client, normal_user, db_session):
    from app.api.routes_password import _hash_token

    token = "expired-token"
    prt = PasswordResetToken(
        email=normal_user.email,
        token_hash=_hash_token(token),
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    db_session.add(prt)
    db_session.commit()

    r = client.post("/password/reset", json={"token": token, "password": "NewPass123!"})
    assert r.status_code == 400
