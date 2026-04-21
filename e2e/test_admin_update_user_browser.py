import time

import pytest


@pytest.mark.e2e
def test_admin_update_user_permissions(page, app_urls, admin_credentials, create_backend_user, list_backend_users):
    email = f"upd_e2e_{int(time.time())}@test.local"
    create_backend_user(email, "Passw0rd!123")

    users = list_backend_users()
    user = next(u for u in users if u.get("email") == email)
    user_id = int(user["id"])

    # Login to Streamlit admin.
    page.context.clear_cookies()
    page.goto(app_urls["admin"], wait_until="networkidle")
    page.get_by_test_id("stApp").wait_for(timeout=30_000)
    page.get_by_role("textbox", name="Email").first.wait_for(timeout=30_000)
    page.get_by_role("textbox", name="Email").first.fill(admin_credentials["email"])
    page.get_by_role("textbox", name="Password").fill(admin_credentials["password"])
    page.get_by_role("button", name="Sign in").click()
    page.get_by_text("Signed in as").wait_for(timeout=30_000)

    # Update user section.
    page.get_by_role("spinbutton", name="User ID").fill(str(user_id))
    page.get_by_role("textbox", name="Update permissions (comma-separated)").fill("alpha,beta")
    def _set_streamlit_checkbox(label: str, desired: bool) -> None:
        box = page.get_by_test_id("stCheckbox").filter(has_text=label).first
        inp = box.locator(f'input[aria-label="{label}"]')
        # Fallback if Streamlit changes markup: just click container.
        if inp.count() == 0:
            box.click()
            return
        cur = inp.get_attribute("aria-checked")
        cur_bool = True if cur == "true" else False
        if cur_bool != desired:
            box.click()

    _set_streamlit_checkbox("Is admin", True)
    _set_streamlit_checkbox("Is active", True)
    page.get_by_role("button", name="Update user").click()

    # Verify backend data changed.
    deadline = time.time() + 15
    updated = None
    while time.time() < deadline:
        users2 = list_backend_users()
        updated = next(u for u in users2 if u.get("id") == user_id)
        if updated.get("permissions") == ["alpha", "beta"] and updated.get("is_admin") is True:
            break
        time.sleep(0.5)
    assert updated.get("is_admin") is True
    assert updated.get("is_active") is True
    assert updated.get("permissions") == ["alpha", "beta"]

