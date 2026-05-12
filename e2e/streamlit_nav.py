"""Helpers for driving the Streamlit ``user_management_ui`` app in Playwright."""

from __future__ import annotations

import time
from typing import Optional

import requests
from playwright.sync_api import Page, expect


def wait_streamlit_app(page: Page, *, timeout_ms: int = 60_000) -> None:
    page.get_by_test_id("stApp").wait_for(timeout=timeout_ms)


def _wait_streamlit_script_ready(page: Page, *, timeout_ms: int = 120_000) -> None:
    """
    The initial HTML shell is not the running app. Wait until the Python script
    has rendered interactive widgets (login is the default public view).
    """
    page.wait_for_function(
        """() => {
          const app = document.querySelector('[data-testid="stApp"]');
          if (!app) return false;
          const buttons = Array.from(app.querySelectorAll('button'));
          return buttons.some((b) => (b.innerText || '').trim() === 'Sign in');
        }""",
        timeout=timeout_ms,
    )


def _expand_sidebar_if_needed(page: Page) -> None:
    """Streamlit may start with the sidebar collapsed on smaller viewports."""
    for sel in (
        '[data-testid="collapsedControl"]',
        '[data-testid="stSidebarCollapsedControl"]',
        'button[aria-label="Open sidebar"]',
    ):
        btn = page.locator(sel)
        if btn.count() == 0:
            continue
        try:
            if btn.first.is_visible():
                btn.first.click(timeout=3_000)
                page.wait_for_timeout(300)
                return
        except Exception:
            continue


def goto_user_app(page: Page, user_url: str) -> None:
    page.context.clear_cookies()
    page.set_viewport_size({"width": 1440, "height": 900})
    page.goto(user_url, wait_until="domcontentloaded")
    wait_streamlit_app(page)
    _wait_streamlit_script_ready(page)
    _expand_sidebar_if_needed(page)


_GO_TO_OPTIONS = ("Login", "Register", "Accept invite", "Reset password")


def select_public_go_to(page: Page, option: str) -> None:
    """
    Sidebar radio **Go to**: ``Login`` | ``Register`` | ``Accept invite`` | ``Reset password``.
    """
    _expand_sidebar_if_needed(page)
    sidebar = page.locator('[data-testid="stSidebar"]')
    sidebar.wait_for(state="attached", timeout=15_000)

    idx = _GO_TO_OPTIONS.index(option)

    # Streamlit renders ``st.radio`` as native ``<input type="radio">`` in order of options.
    radios = sidebar.locator('input[type="radio"]')
    # Native radios can sit in an overflow-hidden sidebar; JS click is reliable.
    if radios.count() >= len(_GO_TO_OPTIONS):
        radios.nth(idx).evaluate("el => el.click()")
        page.wait_for_timeout(200)
        return

    radio = sidebar.get_by_role("radio", name=option, exact=True)
    if radio.count():
        radio.first.click(timeout=15_000)
        return
    tab = sidebar.get_by_role("tab", name=option)
    if tab.count():
        tab.first.click(timeout=15_000)
        return
    lbl = sidebar.locator("label").filter(has_text=option)
    if lbl.count():
        lbl.first.click(timeout=15_000)
        return
    global_radio = page.get_by_role("radio", name=option, exact=True)
    if global_radio.count():
        global_radio.first.click(timeout=15_000)
        return
    sidebar.get_by_text(option, exact=False).first.click(timeout=15_000, force=True)


def click_sidebar_button(page: Page, name: str, *, timeout_ms: int = 30_000) -> None:
    _expand_sidebar_if_needed(page)
    btn = page.locator('[data-testid="stSidebar"]').get_by_role("button", name=name)
    btn.first.click(timeout=timeout_ms)


def login_with_email_password(
    page: Page,
    *,
    email: str,
    password: str,
    user_url: str,
    backend_base_url: str,
) -> None:
    tok = requests.post(
        f"{backend_base_url.rstrip('/')}/auth/token",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10,
    )
    assert tok.status_code == 200, f"login API failed: {tok.status_code} {tok.text}"

    goto_user_app(page, user_url)
    select_public_go_to(page, "Login")
    page.get_by_role("textbox", name="Email").first.fill(email)
    page.get_by_role("textbox", name="Password").fill(password)
    page.get_by_role("button", name="Sign in").click(force=True)
    page.wait_for_timeout(800)
    _expand_sidebar_if_needed(page)
    deadline = time.time() + 120.0
    while time.time() < deadline:
        sb = page.locator('[data-testid="stSidebar"]')
        if sb.get_by_role("button", name="Users").count() > 0:
            return
        page.wait_for_timeout(500)
    snippet = page.evaluate(
        """() => (document.querySelector('[data-testid="stApp"]')?.innerText || '').slice(0, 1200)"""
    )
    raise AssertionError(
        "Streamlit did not reach authenticated navigation after successful /auth/token. "
        f"stApp text snippet:\n{snippet!r}"
    )


def expect_authenticated(page: Page, *, email: Optional[str] = None) -> None:
    page.locator('[data-testid="stSidebar"]').get_by_role(
        "button", name="Users"
    ).wait_for(timeout=30_000)
    if email:
        expect(page.get_by_text(email, exact=False)).to_be_visible(timeout=30_000)
