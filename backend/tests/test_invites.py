from app.core.config import settings


def test_invite_create_and_accept_flow(client):
    old = settings.admin_api_key
    try:
        settings.admin_api_key = "test-key"

        # Create invite
        resp = client.post(
            "/invites",
            headers={"X-Admin-Api-Key": "test-key"},
            json={
                "email": "invitee@test.local",
                "full_name": "Invited User",
                "is_admin": True,
                "permissions": ["a", "b"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        invite_url = data["invite_url"]
        assert "token=" in invite_url
        token = invite_url.split("token=", 1)[1]

        # Accept invite
        accept = client.post(
            "/invites/accept",
            params={
                "token": token,
                "password": "NewPass123!",
                "full_name": "Accepted Name",
            },
        )
        assert accept.status_code == 200
        assert accept.json()["ok"] is True

        # Now the user should be able to log in
        login = client.post(
            "/auth/token",
            data={"username": "invitee@test.local", "password": "NewPass123!"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert login.status_code == 200
    finally:
        settings.admin_api_key = old
