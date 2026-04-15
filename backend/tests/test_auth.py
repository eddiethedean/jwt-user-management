def test_login_token_success(client, normal_user):
    resp = client.post(
        "/auth/token",
        data={"username": normal_user.email, "password": "password123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["token_type"] == "bearer"
    assert isinstance(data["access_token"], str)
    assert len(data["access_token"]) > 20


def test_login_token_bad_password(client, normal_user):
    resp = client.post(
        "/auth/token",
        data={"username": normal_user.email, "password": "wrong"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Incorrect email or password"


def test_login_token_unknown_user(client):
    resp = client.post(
        "/auth/token",
        data={"username": "nope@test.local", "password": "password123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Incorrect email or password"
