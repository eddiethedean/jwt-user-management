from app.core.security import create_access_token


def test_me_rejects_invalid_subject(client, normal_user):
    token = create_access_token(
        subject="not-an-int", extra_claims={"email": "x", "is_admin": False}
    )
    r = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_me_rejects_expired_token(client, normal_user):
    from app.core import config as config_mod

    old = config_mod.settings.jwt_expires_minutes
    try:
        config_mod.settings.jwt_expires_minutes = -1
        token = create_access_token(
            subject=str(normal_user.id),
            extra_claims={"email": normal_user.email, "is_admin": False},
        )
    finally:
        config_mod.settings.jwt_expires_minutes = old

    r = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_me_rejects_garbage_token(client, normal_user):
    r = client.get("/users/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert r.status_code == 401


def test_me_rejects_token_missing_exp(client, normal_user):
    from jose import jwt
    from app.core.config import settings

    token = jwt.encode({"sub": str(normal_user.id)}, settings.jwt_secret, algorithm="HS256")
    r = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
