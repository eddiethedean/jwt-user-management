"""
Playwright: ``user_management_api`` + ``user_management_ui`` together.

Admin signs in via Streamlit and exercises the main authenticated areas (Users,
Account, Admin) plus logged-out public flows (Register, Accept invite, Reset password).
"""

from __future__ import annotations

import re
import time

import pytest
import requests
from playwright.sync_api import expect

from streamlit_nav import (
    click_sidebar_button,
    login_with_email_password,
    select_public_go_to,
    wait_streamlit_app,
    _expand_sidebar_if_needed,
)


def _click_sign_out(page) -> None:
    btn = page.locator('[data-testid="stSidebar"]').get_by_role(
        "button", name="Sign out"
    )
    btn.click(timeout=30_000)
    page.wait_for_timeout(500)


def _admin_token(app_urls: dict, admin_credentials: dict) -> str:
    r = requests.post(
        f"{app_urls['backend']}/auth/token",
        data={
            "username": admin_credentials["email"],
            "password": admin_credentials["password"],
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10,
    )
    r.raise_for_status()
    return str(r.json()["access_token"])


def _create_invite_raw_token(
    app_urls: dict, admin_credentials: dict, email: str
) -> str:
    from urllib.parse import parse_qs, urlparse

    tok = _admin_token(app_urls, admin_credentials)
    inv = requests.post(
        f"{app_urls['backend']}/invites",
        json={"email": email, "grant_admin": False},
        headers={"Authorization": f"Bearer {tok}"},
        timeout=10,
    )
    inv.raise_for_status()
    invite_url = str(inv.json().get("invite_url") or "")
    raw = (parse_qs(urlparse(invite_url).query).get("token") or [""])[0]
    if not raw:
        raise RuntimeError(f"missing token in invite_url={invite_url!r}")
    return raw


@pytest.mark.e2e
def test_admin_streamlit_full_journey_with_api(
    page, app_urls, admin_credentials, create_backend_user
) -> None:
    """
    Admin: login → Users (refresh list) → Account → Admin (create invite) →
    sign out → public Register / Accept invite / Reset password smoke →
    accept invite as new user → login as new user → Admin (edit other user).
    """
    ts = int(time.time())
    peer_email = f"e2e_peer_{ts}@test.local"
    create_backend_user(peer_email, "PeerUser#1")
    invitee_email = f"e2e_invitee_{ts}@test.local"
    raw_token = _create_invite_raw_token(app_urls, admin_credentials, invitee_email)

    # --- Admin login ---
    login_with_email_password(
        page,
        email=admin_credentials["email"],
        password=admin_credentials["password"],
        user_url=app_urls["user"],
        backend_base_url=app_urls["backend"],
    )

    # --- Users page ---
    click_sidebar_button(page, "Users")
    page.get_by_role("heading", name="Users").wait_for(timeout=30_000)
    page.get_by_role("button", name="Refresh users").click()
    app = page.locator('[data-testid="stApp"]')
    expect(app).to_contain_text("admin@example.com", timeout=60_000)
    expect(app).to_contain_text(peer_email, timeout=60_000)

    # --- Account page ---
    click_sidebar_button(page, "Account")
    page.get_by_role("heading", name="Account").wait_for(timeout=30_000)
    expect(page.get_by_text(re.compile(r"Change password", re.I))).to_be_visible(
        timeout=30_000
    )

    # --- Admin: create another invite from UI ---
    click_sidebar_button(page, "Admin")
    page.get_by_role("heading", name="Admin").wait_for(timeout=30_000)
    ui_invite_email = f"e2e_ui_inv_{ts}@test.local"
    page.get_by_role("textbox", name="Invite email").fill(ui_invite_email)
    page.get_by_role("button", name="Create invite").click()
    deadline = time.time() + 120.0
    while time.time() < deadline:
        body = page.locator('[data-testid="stApp"]').inner_text()
        if "Invite created" in body:
            break
        if "Could not verify" in body or "Invite failed" in body:
            pytest.fail(f"invite UI error:\n{body[:2000]}")
        page.wait_for_timeout(400)
    else:
        pytest.fail(
            "Timed out waiting for Invite created.\n"
            + page.locator('[data-testid="stApp"]').inner_text()[:2000]
        )

    # --- Admin: edit non-admin user (Streamlit selectbox) ---
    page.get_by_role("heading", name="Manage users").wait_for(timeout=30_000)
    page.locator('[data-testid="stSelectbox"]').first.click()
    page.get_by_role("option", name=re.compile(re.escape(peer_email))).click(
        force=True, timeout=30_000
    )
    page.get_by_role("textbox", name="Full name").fill("E2E Peer")
    page.get_by_role("button", name="Save user").click()
    expect(page.get_by_text("Saved")).to_be_visible(timeout=60_000)

    # --- Sign out ---
    _click_sign_out(page)
    wait_streamlit_app(page)
    select_public_go_to(page, "Login")

    # --- Public: Register ---
    select_public_go_to(page, "Register")
    page.get_by_role("heading", name="Register").wait_for(timeout=30_000)
    page.get_by_role("textbox", name="Email").first.fill(f"e2e_reg_{ts}@test.local")
    page.get_by_role("button", name="Send setup link").click()
    expect(
        page.get_by_text(re.compile(r"setup link was generated", re.I))
    ).to_be_visible(timeout=60_000)

    # --- Public: Accept invite (token from API) ---
    select_public_go_to(page, "Accept invite")
    page.get_by_role("heading", name="Accept invite").wait_for(timeout=30_000)
    page.get_by_role("textbox", name="Invite token").fill(raw_token)
    page.get_by_role("textbox", name="Password").fill("InvitedUser#2")
    page.get_by_role("button", name="Set password").click()
    expect(page.get_by_text(re.compile(r"Invite accepted", re.I))).to_be_visible(
        timeout=60_000
    )

    # --- Public: Reset password (forgot + inspect happy path via API token) ---
    select_public_go_to(page, "Reset password")
    page.get_by_role("heading", name="Forgot password").wait_for(timeout=30_000)
    page.get_by_role("textbox", name="Email").first.fill(invitee_email)
    page.get_by_role("button", name="Send reset link").click()
    expect(
        page.get_by_text(re.compile(r"If the account exists.*reset email", re.I))
    ).to_be_visible(timeout=60_000)

    # --- Login as invited user (accepted above) ---
    login_with_email_password(
        page,
        email=invitee_email,
        password="InvitedUser#2",
        user_url=app_urls["user"],
        backend_base_url=app_urls["backend"],
    )
    expect(page.locator('[data-testid="stApp"]')).to_contain_text(
        invitee_email, timeout=30_000
    )

    # Invited user should not see Admin in sidebar (not granted admin).
    _expand_sidebar_if_needed(page)
    expect(
        page.locator('[data-testid="stSidebar"]').get_by_role("button", name="Admin")
    ).to_have_count(0)
