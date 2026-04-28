import pytest


@pytest.mark.e2e
def test_admin_login_logout(page, app_urls, admin_credentials):
    page.context.clear_cookies()
    page.goto(app_urls["admin"], wait_until="domcontentloaded")

    page.get_by_role("heading", name="Admin sign in").wait_for(timeout=30_000)
    page.get_by_label("Email").fill(admin_credentials["email"])
    page.get_by_label("Password").fill(admin_credentials["password"])
    page.get_by_role("button", name="Sign in").click()

    page.get_by_text("Users").wait_for(timeout=30_000)
    # Wait for users to load successfully (no error shown) and at least one row present.
    page.locator("#usersTable tbody tr").first.wait_for(timeout=30_000)
    assert page.locator("#usersError").is_hidden()

    # Refresh
    page.get_by_role("button", name="Refresh").click()
    page.locator("#usersTable tbody tr").first.wait_for(timeout=30_000)
    assert page.locator("#usersError").is_hidden()

    # Logout
    page.get_by_role("button", name="Sign out").click()
    page.get_by_role("heading", name="Admin sign in").wait_for(timeout=30_000)
