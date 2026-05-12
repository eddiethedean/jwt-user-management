"""Unauthenticated flows: login, register, invite, password reset."""

from __future__ import annotations

from typing import Any, Callable, Optional

import httpx
import streamlit as st

from ui.auth_state import SESSION_KEY, login_success
from ui.http import response_ok, safe_json, show_http_error


def render_login(
    st: Any,
    *,
    post_form: Callable[[str, dict], Optional[httpx.Response]],
    load_me_fn: Callable[[str], dict[str, Any]],
) -> None:
    with st.form("login_form"):
        st.subheader("Login to App")

        username = st.text_input("Username", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")

        submit_button = st.form_submit_button("Login")

    if submit_button:
        username = str(username or "").strip()
        password = str(password or "")
        resp = post_form(
            "/auth/token", data={"username": username, "password": password}
        )
        if resp is None:
            st.stop()
        if response_ok(resp):
            data = safe_json(resp)
            access_token = str(data.get("access_token") or "")
            if not access_token:
                show_http_error("Login failed", resp)
                st.stop()
            login_success(
                access_token=access_token,
                email=username,
                session_key=SESSION_KEY,
            )
            st.session_state["_flash_signed_in"] = True
            st.session_state["_page"] = (
                "Admin"
                if bool(load_me_fn(access_token).get("is_admin"))
                else "Users"
            )
            st.rerun()
        else:
            show_http_error("Invalid username or password", resp)


def render_register(
    st: Any,
    *,
    post_form: Callable[[str, dict], Optional[httpx.Response]],
) -> None:
    st.subheader("Register")
    st.caption(
        "Enter your email to request an invite link. If directory lookup is "
        "enabled, it must validate your email."
    )
    reg_email = st.text_input("Email", key="register_email")
    if st.button("Request setup link", key="register_submit"):
        resp = post_form("/register", data={"email": reg_email})
        if resp is None:
            st.stop()
        if response_ok(resp):
            st.success("If allowed, a setup link was generated/sent.")
        else:
            show_http_error("Registration failed", resp)


def render_accept_invite(
    st: Any,
    *,
    post_json_pub: Callable[..., Optional[httpx.Response]],
) -> None:
    st.subheader("Accept invite")
    st.caption("Set a password to activate your account.")
    invite_token = st.text_input("Invite token", key="invite_token")
    if st.button("Lookup invite", key="invite_lookup"):
        resp = post_json_pub("/invites/inspect", json={"token": invite_token})
        if resp is None:
            st.stop()
        if response_ok(resp):
            st.session_state["_invite_info"] = safe_json(resp)
        else:
            show_http_error("Invite not found", resp)
            st.session_state.pop("_invite_info", None)

    inv = st.session_state.get("_invite_info", {})
    if isinstance(inv, dict) and inv.get("email"):
        st.caption(f"Email: `{inv.get('email', '')}`")
        st.caption("This invite is tied to this email address.")

    invite_name = st.text_input("Full name (optional)", key="invite_full_name")
    invite_password = st.text_input("Password", type="password", key="invite_password")
    if st.button("Accept invite", key="invite_submit"):
        resp = post_json_pub(
            "/invites/accept",
            json={
                "token": invite_token,
                "password": invite_password,
                "full_name": invite_name,
            },
        )
        if resp is None:
            st.stop()
        if response_ok(resp):
            st.success("Invite accepted. You can now sign in.")
        else:
            show_http_error("Invite accept failed", resp)


def render_reset_password(
    st: Any,
    *,
    post_json_pub: Callable[..., Optional[httpx.Response]],
) -> None:
    st.subheader("Forgot password")
    st.caption(
        "Enter your email and we’ll send you a reset link (if the account exists)."
    )
    forgot_email = st.text_input("Email", key="forgot_email")
    if st.button("Send reset link", key="forgot_submit"):
        resp = post_json_pub("/password/forgot", json={"email": forgot_email})
        if resp is None:
            st.stop()
        if response_ok(resp):
            st.success("If the account exists, a reset email has been sent.")
        else:
            st.error(f"Reset request failed: {resp.status_code} {resp.text}")

    st.divider()
    st.subheader("Reset password")
    st.caption("Choose a new password for your account.")
    token = st.text_input("Reset token", key="reset_token")
    if st.button("Lookup reset link", key="reset_lookup"):
        resp = post_json_pub("/password/inspect", json={"token": token})
        if resp is None:
            st.stop()
        if response_ok(resp):
            st.session_state["_reset_info"] = safe_json(resp)
        else:
            show_http_error("Reset link not found", resp)
            st.session_state.pop("_reset_info", None)

    ri = st.session_state.get("_reset_info", {})
    if isinstance(ri, dict) and ri.get("email"):
        st.caption(f"Email: `{ri.get('email', '')}`")
        st.caption("This reset link is tied to this email address.")

    new_password = st.text_input(
        "New password", type="password", key="reset_new_password"
    )
    if st.button("Reset password", key="reset_submit"):
        resp = post_json_pub(
            "/password/reset", json={"token": token, "password": new_password}
        )
        if resp is None:
            st.stop()
        if response_ok(resp):
            st.success("Password updated. You can now log in.")
        else:
            st.error(f"Reset failed: {resp.status_code} {resp.text}")
