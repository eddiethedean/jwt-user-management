"""
Playwright coverage for ``user_management_streamlit`` surfaces not fully asserted elsewhere.

Complements ``test_streamlit_admin_full_journey_browser`` and ``test_user_browser`` with
focused checks: public tabs, inline forgot-password on Login, register, accept-invite
lookup, reset-password tab, account profile save, password change, API docs link,
and non-admin navigation.
"""

from __future__ import annotations

import re
import time
from urllib.parse import parse_qs, urlparse

import pytest
import requests
from playwright.sync_api import expect

from streamlit_nav import (
    _expand_sidebar_if_needed,
    click_sidebar_button,
    click_sidebar_sign_out,
    login_with_email_password,
    open_public_page,
    select_public_go_to,
    wait_streamlit_app,
)


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


def _invite_raw_token(app_urls: dict, admin_credentials: dict, email: str) -> str:
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
@pytest.mark.parametrize(
    ("tab", "heading"),
    [
        ("Login", "Login"),
        ("Register", "Register"),
        ("Accept invite", "Accept invite"),
        ("Reset password", "Forgot password"),
    ],
)
def test_public_go_to_tabs_show_expected_headings(
    page, app_urls, tab: str, heading: str
) -> None:
    open_public_page(page, app_urls["user"], tab)
    page.get_by_role("heading", name=heading).wait_for(timeout=30_000)


@pytest.mark.e2e
def test_login_inline_forgot_password_shows_success_message(
    page, app_urls, admin_credentials
) -> None:
    open_public_page(page, app_urls["user"], "Login")
    page.get_by_role("textbox", name="Email").nth(1).fill(admin_credentials["email"])
    page.get_by_role("button", name="Send reset link").click()
    expect(
        page.get_by_text(re.compile(r"If the account exists.*reset email", re.I))
    ).to_be_visible(timeout=60_000)


@pytest.mark.e2e
def test_register_send_setup_link_shows_success_message(page, app_urls) -> None:
    ts = int(time.time())
    open_public_page(page, app_urls["user"], "Register")
    page.get_by_role("textbox", name="Email").first.fill(f"e2e_cov_reg_{ts}@test.local")
    page.get_by_role("button", name="Send setup link").click()
    expect(
        page.get_by_text(re.compile(r"setup link was generated|setup link", re.I))
    ).to_be_visible(timeout=60_000)


@pytest.mark.e2e
def test_accept_invite_lookup_then_set_password(
    page, app_urls, admin_credentials
) -> None:
    ts = int(time.time())
    email = f"e2e_lookup_{ts}@test.local"
    raw = _invite_raw_token(app_urls, admin_credentials, email)

    open_public_page(page, app_urls["user"], "Accept invite")
    page.get_by_role("textbox", name="Invite token").fill(raw)
    page.get_by_role("button", name="Lookup invite").click()
    expect(page.get_by_role("textbox", name="Email")).to_be_visible(timeout=60_000)

    page.get_by_role("textbox", name="Password").fill("InvitedLookup#9")
    page.get_by_role("button", name="Set password").click()
    expect(page.get_by_text(re.compile(r"Invite accepted", re.I))).to_be_visible(
        timeout=60_000
    )


@pytest.mark.e2e
def test_reset_password_tab_forgot_flow_shows_success_message(
    page, app_urls, admin_credentials
) -> None:
    open_public_page(page, app_urls["user"], "Reset password")
    page.get_by_role("textbox", name="Email").first.fill(admin_credentials["email"])
    page.get_by_role("button", name="Send reset link").first.click()
    expect(
        page.get_by_text(re.compile(r"If the account exists.*reset email", re.I))
    ).to_be_visible(timeout=60_000)


@pytest.mark.e2e
def test_user_changes_password_on_account_page(
    page, app_urls, create_backend_user
) -> None:
    ts = int(time.time())
    email = f"e2e_pwchange_{ts}@test.local"
    old_pw = "OldPw#12345"
    new_pw = "NewPw#67890"
    create_backend_user(email, old_pw)

    login_with_email_password(
        page,
        email=email,
        password=old_pw,
        user_url=app_urls["user"],
        backend_base_url=app_urls["backend"],
    )
    click_sidebar_button(page, "Account")
    page.get_by_role("heading", name="Account").wait_for(timeout=30_000)

    page.get_by_role("textbox", name="Current password").fill(old_pw)
    page.locator('[aria-label="New password"]').fill(new_pw)
    page.locator('[aria-label="Confirm new password"]').fill(new_pw)
    page.get_by_role("button", name="Update password").click()
    expect(
        page.locator('[data-testid="stAlert"]').filter(
            has_text=re.compile(r"Password updated", re.I)
        )
    ).to_be_visible(timeout=60_000)

    click_sidebar_sign_out(page)
    wait_streamlit_app(page)
    select_public_go_to(page, "Login")
    page.get_by_role("textbox", name="Email").first.fill(email)
    page.get_by_role("textbox", name="Password").fill(new_pw)
    page.get_by_role("button", name="Sign in").click(force=True)
    expect(
        page.locator('[data-testid="stMain"]').get_by_text("Signed in as", exact=False)
    ).to_be_visible(timeout=90_000)


@pytest.mark.e2e
def test_admin_account_save_full_name_visible_in_ui(
    page, app_urls, admin_credentials
) -> None:
    ts = int(time.time())
    display = f"E2E Admin Display {ts}"

    login_with_email_password(
        page,
        email=admin_credentials["email"],
        password=admin_credentials["password"],
        user_url=app_urls["user"],
        backend_base_url=app_urls["backend"],
    )
    click_sidebar_button(page, "Account")
    page.get_by_role("heading", name="Account").wait_for(timeout=30_000)

    page.get_by_role("textbox", name="Full name (optional)").fill(display)
    page.locator('[data-testid="stMain"]').get_by_role("button", name="Save").click()
    page.wait_for_timeout(1500)

    app = page.locator('[data-testid="stApp"]')
    expect(app).to_contain_text(display, timeout=60_000)


@pytest.mark.e2e
def test_sidebar_api_docs_link_href(page, app_urls, admin_credentials) -> None:
    login_with_email_password(
        page,
        email=admin_credentials["email"],
        password=admin_credentials["password"],
        user_url=app_urls["user"],
        backend_base_url=app_urls["backend"],
    )
    _expand_sidebar_if_needed(page)

    link = page.locator('[data-testid="stSidebar"]').get_by_role(
        "link", name="API docs"
    )
    href = link.get_attribute("href") or ""
    assert "/docs" in href, f"unexpected API docs href: {href!r}"


@pytest.mark.e2e
def test_non_admin_user_sidebar_has_no_admin_button(
    page, app_urls, create_backend_user
) -> None:
    ts = int(time.time())
    email = f"e2e_plain_{ts}@test.local"
    password = "PlainUser#1"
    create_backend_user(email, password)

    login_with_email_password(
        page,
        email=email,
        password=password,
        user_url=app_urls["user"],
        backend_base_url=app_urls["backend"],
    )
    sb = page.locator('[data-testid="stSidebar"]')
    expect(sb.get_by_role("button", name="Admin")).to_have_count(0)
    expect(sb.get_by_role("button", name="Users")).to_be_visible(timeout=30_000)
