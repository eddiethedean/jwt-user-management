import time

import pytest


def _click_sign_out(page) -> None:
    """
    Streamlit reruns can detach/recreate the button; retry a few times.
    """
    deadline = time.time() + 15
    last_err = None
    while time.time() < deadline:
        try:
            btn = page.get_by_role("button", name="Sign out")
            btn.wait_for(timeout=5_000)
            btn.click(force=True, timeout=5_000)
            return
        except Exception as e:  # noqa: BLE001
            last_err = e
            page.wait_for_timeout(250)
    raise AssertionError(f"Could not click Sign out button: {last_err}")


@pytest.mark.e2e
def test_user_login_and_logout(page, app_urls, create_backend_user):
    page.context.clear_cookies()
    email = f"e2e_{int(time.time())}@test.local"
    password = "Passw0rd!123"
    create_backend_user(email, password)

    page.goto(app_urls["user"], wait_until="networkidle")
    page.get_by_test_id("stApp").wait_for(timeout=30_000)

    # Login tab
    page.get_by_role("tab", name="Login").click()
    page.get_by_role("textbox", name="Email").first.fill(email)
    page.get_by_role("textbox", name="Password").fill(password)
    page.get_by_role("button", name="Sign in").click()

    page.get_by_text("Authenticated session is active.").wait_for(timeout=90_000)
    page.get_by_text(email, exact=True).wait_for(timeout=30_000)

    # Logout
    _click_sign_out(page)
    page.get_by_role("tab", name="Login").wait_for(timeout=30_000)
    # Allow rerun.
    deadline = time.time() + 30
    while time.time() < deadline:
        if page.get_by_text("Authenticated session is active.").count() == 0:
            break
        page.wait_for_timeout(250)
    assert page.get_by_text("Authenticated session is active.").count() == 0


@pytest.mark.e2e
def test_user_login_not_persisted_across_refresh(page, app_urls, create_backend_user):
    """
    Auth lives in Streamlit session state only: a full reload starts a new session
    and the user must sign in again.
    """
    page.context.clear_cookies()
    email = f"e2e_nopersist_{int(time.time())}@test.local"
    password = "Passw0rd!123"
    create_backend_user(email, password)

    page.goto(app_urls["user"], wait_until="networkidle")
    page.get_by_test_id("stApp").wait_for(timeout=30_000)

    page.get_by_role("tab", name="Login").click()
    page.get_by_role("textbox", name="Email").first.fill(email)
    page.get_by_role("textbox", name="Password").fill(password)
    page.get_by_role("button", name="Sign in").click()

    page.get_by_text("Authenticated session is active.").wait_for(timeout=90_000)
    page.get_by_text(email, exact=True).wait_for(timeout=30_000)

    page.reload(wait_until="networkidle")
    page.get_by_test_id("stApp").wait_for(timeout=30_000)

    deadline = time.time() + 45
    while time.time() < deadline:
        if page.get_by_text("Authenticated session is active.").count() == 0:
            break
        page.wait_for_timeout(300)
    assert page.get_by_text("Authenticated session is active.").count() == 0
    page.get_by_role("tab", name="Login").wait_for(timeout=30_000)


@pytest.mark.e2e
def test_user_logout_persists_across_refresh(page, app_urls, create_backend_user):
    """
    After logout, a browser refresh must not show an authenticated UI.
    """
    page.context.clear_cookies()
    email = f"e2e_refresh_{int(time.time())}@test.local"
    password = "Passw0rd!123"
    create_backend_user(email, password)

    page.goto(app_urls["user"], wait_until="networkidle")
    page.get_by_test_id("stApp").wait_for(timeout=30_000)

    # Login
    page.get_by_role("tab", name="Login").click()
    page.get_by_role("textbox", name="Email").first.fill(email)
    page.get_by_role("textbox", name="Password").fill(password)
    page.get_by_role("button", name="Sign in").click()

    page.get_by_text("Authenticated session is active.").wait_for(timeout=90_000)

    # Logout
    _click_sign_out(page)

    # Wait until logged-out UI (no authenticated banner).
    deadline = time.time() + 30
    while time.time() < deadline:
        if page.get_by_text("Authenticated session is active.").count() == 0:
            break
        page.wait_for_timeout(250)
    assert page.get_by_text("Authenticated session is active.").count() == 0

    # Refresh: must remain logged out.
    def _assert_logged_out_ui() -> None:
        page.get_by_test_id("stApp").wait_for(timeout=30_000)
        page.get_by_role("tab", name="Login").wait_for(timeout=30_000)
        assert page.get_by_text("Authenticated session is active.").count() == 0
        assert page.get_by_text("You're signed in. Use").count() == 0

    for _ in range(3):
        page.reload(wait_until="networkidle")
        deadline = time.time() + 20
        while time.time() < deadline:
            if (
                page.get_by_text("Authenticated session is active.").count() == 0
                and page.get_by_text("You're signed in. Use").count() == 0
            ):
                break
            page.wait_for_timeout(250)
        _assert_logged_out_ui()
