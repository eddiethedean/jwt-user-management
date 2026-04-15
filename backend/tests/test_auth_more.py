from app.core.security import decode_token


def test_token_contains_expected_claims(client, admin_user):
    resp = client.post(
        "/auth/token",
        data={"username": admin_user.email, "password": "password123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    payload = decode_token(token)
    assert payload["sub"] == str(admin_user.id)
    assert payload["email"] == admin_user.email
    assert payload["is_admin"] is True
