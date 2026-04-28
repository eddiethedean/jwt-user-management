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


def test_accept_invite_html_form_action_includes_base_path():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.routes_invites import router as invites_router
    from app.middleware.base_path import BasePathMiddleware
    from app.middleware.security_headers import SecurityHeadersMiddleware

    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(BasePathMiddleware, base_path="/bp")
    app.include_router(invites_router)
    c = TestClient(app)

    page = c.get("/bp/invites/accept", params={"token": "x"})
    assert page.status_code == 200
    assert 'action="/bp/invites/accept-form"' in page.text
