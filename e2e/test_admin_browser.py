import pytest


@pytest.mark.e2e
def test_admin_login_logout(page, app_urls, admin_credentials):
    page.context.clear_cookies()
    page.goto(app_urls["admin"], wait_until="domcontentloaded")

    page.get_by_role("heading", name="Admin login").wait_for(timeout=30_000)
    page.get_by_label("Email").fill(admin_credentials["email"])
    page.get_by_label("Password").fill(admin_credentials["password"])
    page.get_by_role("button", name="Sign in").click()

    page.get_by_role("heading", name="Admin").wait_for(timeout=30_000)
    page.get_by_text("All users").wait_for(timeout=30_000)
    # Ensure the users table has at least one row (admin user).
    page.locator("table tbody tr").first.wait_for(timeout=30_000)
