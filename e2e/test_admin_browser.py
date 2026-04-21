import pytest
import time
from ._debug import dump_page


@pytest.mark.e2e
def test_admin_login_logout(page, app_urls, admin_credentials):
    page.context.clear_cookies()
    page.goto(app_urls["admin"], wait_until="networkidle")
    page.get_by_test_id("stApp").wait_for(timeout=30_000)

    # Backend auth: Email/Password fields.
    try:
        page.get_by_role("textbox", name="Email").first.wait_for(timeout=30_000)
    except Exception:
        dump_page(page, name="admin_login_missing_email")
        raise
    page.get_by_role("textbox", name="Email").first.fill(admin_credentials["email"])
    page.get_by_role("textbox", name="Password").fill(admin_credentials["password"])
    page.get_by_role("button", name="Sign in").click()

    # Logged-in sidebar text
    page.get_by_text("Signed in as").wait_for(timeout=30_000)

    # Sanity: users section exists
    page.get_by_text("Users").wait_for(timeout=30_000)

    # Logout
    page.get_by_role("button", name="Sign out").click()
    page.get_by_role("textbox", name="Email").first.wait_for(timeout=30_000)

