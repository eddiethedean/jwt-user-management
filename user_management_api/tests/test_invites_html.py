from app.core.config import settings


def test_accept_invite_html_page_and_form(client):
    old = settings.admin_api_key
    try:
        settings.admin_api_key = "test-key"

        resp = client.post(
            "/invites",
            headers={"X-Admin-Api-Key": "test-key"},
            json={
                "email": "htmlinvite@test.local",
                "full_name": "Invited",
                "is_admin": False,
                "permissions": [],
            },
        )
        assert resp.status_code == 200
        token = resp.json()["invite_url"].split("token=", 1)[1]

        page = client.get("/invites/accept", params={"token": token})
        assert page.status_code == 200
        assert "Accept invite" in page.text

        submit = client.post(
            "/invites/accept-form",
            data={"token": token, "password": "Pass123!", "full_name": "Accepted"},
        )
        assert submit.status_code == 200
        assert "Invite accepted" in submit.text

        # Now the user should be able to log in with the password set via the HTML form.
        login = client.post(
            "/auth/token",
            data={"username": "htmlinvite@test.local", "password": "Pass123!"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert login.status_code == 200
    finally:
        settings.admin_api_key = old
