import pytest

from streamlit_nav import goto_user_app, select_public_go_to


@pytest.mark.e2e
def test_user_login_failure_shows_error(page, app_urls):
    goto_user_app(page, app_urls["user"])
    select_public_go_to(page, "Login")
    page.get_by_role("textbox", name="Email").first.fill("nope@test.local")
    page.get_by_role("textbox", name="Password").fill("wrong")
    page.get_by_role("button", name="Sign in").click()
    page.get_by_text("Invalid email or password", exact=False).wait_for(
        state="visible", timeout=10_000
    )
    assert page.get_by_role("button", name="Sign in").is_visible()
