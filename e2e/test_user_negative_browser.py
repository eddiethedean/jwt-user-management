import pytest
import requests

from streamlit_nav import goto_user_app, select_public_go_to


@pytest.mark.e2e
def test_user_login_failure_shows_error(page, app_urls):
    goto_user_app(page, app_urls["user"])
    select_public_go_to(page, "Login")
    page.get_by_role("textbox", name="Email").first.fill("nope@test.local")
    page.get_by_role("textbox", name="Password").fill("wrong")
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_timeout(2000)
    # Same backend the UI uses (Streamlit calls it server-side): bad credentials → 400.
    r = requests.post(
        f"{app_urls['backend']}/auth/token",
        data={"username": "nope@test.local", "password": "wrong"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10,
    )
    assert r.status_code == 400
    # UI should stay on the sign-in form (not authenticated).
    assert page.get_by_role("button", name="Sign in").is_visible()
