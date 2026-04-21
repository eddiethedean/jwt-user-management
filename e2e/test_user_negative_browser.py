import pytest


@pytest.mark.e2e
def test_user_login_failure_shows_error(page, app_urls):
    page.context.clear_cookies()
    page.goto(app_urls["user"], wait_until="networkidle")
    page.get_by_test_id("stApp").wait_for(timeout=30_000)
    page.get_by_role("tab", name="Login").click()
    page.get_by_role("textbox", name="Email").first.fill("nope@test.local")
    page.get_by_role("textbox", name="Password").fill("wrong")
    page.get_by_role("button", name="Sign in").click()

    page.get_by_text("Invalid email or password").wait_for(timeout=30_000)

