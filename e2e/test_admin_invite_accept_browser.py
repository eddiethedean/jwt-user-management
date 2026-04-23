import time

import pytest


@pytest.mark.e2e
def test_admin_send_invite_then_accept_html(
    page, app_urls, admin_credentials, list_backend_users
):
    """
    End-to-end flow:
    - Admin logs into Streamlit admin
    - Sends an invite (backend returns invite_url)
    - Browser opens the backend HTML accept-invite page
    - Submits password
    - Confirms success and that the user is created in backend
    """
    invited_email = f"inv_e2e_{int(time.time())}@test.local"

    # Login to Streamlit admin.
    page.context.clear_cookies()
    page.goto(app_urls["admin"], wait_until="networkidle")
    page.get_by_test_id("stApp").wait_for(timeout=30_000)
    page.get_by_role("textbox", name="Email").first.wait_for(timeout=30_000)
    page.get_by_role("textbox", name="Email").first.fill(admin_credentials["email"])
    page.get_by_role("textbox", name="Password").fill(admin_credentials["password"])
    page.get_by_role("button", name="Sign in").click()
    page.get_by_text("Signed in as").wait_for(timeout=30_000)

    # Send invite via Streamlit form.
    page.get_by_role("textbox", name="Email").first.fill(invited_email)
    page.get_by_role("textbox", name="Full name").fill("Invited E2E")
    page.get_by_role("textbox", name="Invite permissions (comma-separated)").fill(
        "invited,e2e"
    )
    page.get_by_role("button", name="Send invite").click()

    page.get_by_text("Invite sent").wait_for(timeout=30_000)

    # The invite URL is rendered in a code block; grab it from the DOM.
    code = page.locator("pre").filter(has_text="/invites/accept?token=").first
    invite_url = code.inner_text().strip()
    assert "/invites/accept?token=" in invite_url

    # Accept invite through backend HTML form using the exact URL returned.
    page.goto(invite_url, wait_until="domcontentloaded")
    page.get_by_role("textbox", name="Full name (optional)").fill("Invited E2E")
    page.get_by_role("textbox", name="Password").fill("InvitedPass!123")
    page.get_by_role("button", name="Accept").click()

    # The HTML form returns the same template with either success or error text.
    success = page.get_by_text("Invite accepted. You can close this page.")
    try:
        success.wait_for(timeout=10_000)
    except Exception:
        # Try generic error message (red paragraph)
        err_p = page.locator("p").first
        err_text = (err_p.inner_text() or "").strip()
        raise AssertionError(f"Invite accept did not succeed. Page text: {err_text!r}")

    # Verify backend has user.
    users = list_backend_users()
    assert any(u.get("email") == invited_email for u in users)
