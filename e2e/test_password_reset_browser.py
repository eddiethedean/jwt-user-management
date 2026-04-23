import hashlib
import sqlite3
import time
from datetime import datetime, timedelta, timezone

import pytest
import requests


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _insert_password_reset_token(*, db_path, email: str, token: str) -> None:
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=30)
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            """
            INSERT INTO passwordresettoken (email, token_hash, created_at, expires_at, used_at)
            VALUES (?, ?, ?, ?, NULL)
            """,
            (email, _sha256(token), now.isoformat(), expires.isoformat()),
        )
        conn.commit()


@pytest.mark.e2e
def test_password_reset_html_form_allows_setting_new_password(
    page, app_urls, e2e_db_path, create_backend_user
):
    email = f"e2e_reset_{int(time.time())}@test.local"
    old_password = "OldPassw0rd!123"
    new_password = "NewPassw0rd!123"
    create_backend_user(email, old_password)

    # Non-enumerating endpoint should return ok regardless.
    r = requests.post(
        f"{app_urls['backend']}/password/forgot",
        json={"email": email},
        timeout=10,
    )
    assert r.ok
    assert r.json().get("ok") is True

    # Insert a deterministic reset token so we can drive the HTML form end-to-end.
    token = f"tok_{int(time.time())}_e2e"
    _insert_password_reset_token(db_path=e2e_db_path, email=email, token=token)

    reset_url = f"{app_urls['backend']}/password/reset?token={token}"
    page.goto(reset_url, wait_until="domcontentloaded")
    page.get_by_role("textbox", name="New password").fill(new_password)
    page.get_by_role("button", name="Reset").click()

    page.get_by_text("Password updated. You can close this page.").wait_for(
        timeout=30_000
    )

    # Verify the new password works via JWT login.
    r2 = requests.post(
        f"{app_urls['backend']}/auth/token",
        data={"username": email, "password": new_password},
        timeout=10,
    )
    assert r2.ok, r2.text


@pytest.mark.e2e
def test_password_reset_html_form_rejects_invalid_token(page, app_urls):
    page.goto(f"{app_urls['backend']}/password/reset?token=not-a-real-token")
    page.get_by_role("textbox", name="New password").fill("NewPassw0rd!123")
    page.get_by_role("button", name="Reset").click()

    # Form re-renders with error string from backend.
    page.get_by_text("Reset token not found").wait_for(timeout=30_000)
