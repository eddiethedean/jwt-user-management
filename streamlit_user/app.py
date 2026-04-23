import os
import sys
from pathlib import Path

import requests
import streamlit as st
from dotenv import load_dotenv
from typing import Dict, Optional

# ruff: noqa: E402

# Ensure this app directory is importable.
APP_ROOT = Path(__file__).resolve().parent
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from user_common.auth_state import get_auth_state, login_success, logout
from user_common.backend_client import BackendClient, safe_json, validate_backend_url
from user_common.ui import show_http_error

load_dotenv()

st.set_page_config(page_title="User App • Demo", layout="centered")
st.title("User app (demo)")

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
DEBUG = os.getenv("DEBUG", "").lower() in ("1", "true", "yes")


def _render_session_debug() -> None:
    if not DEBUG:
        return
    st.sidebar.caption("Session (debug)")
    a = get_auth_state(session_key="user_auth")
    st.sidebar.json({"authenticated": a.is_authenticated, "email": a.email or "(none)"})


try:
    validate_backend_url(BACKEND_URL)
except ValueError as e:
    st.error(str(e))
    st.stop()

client = BackendClient(base_url=BACKEND_URL)

if st.session_state.pop("_sign_out_clicked", False):
    logout(session_key="user_auth")
    st.rerun()


def _post_form(path: str, data: dict) -> Optional[requests.Response]:
    try:
        return client.post_form(path, data=data)
    except requests.RequestException:
        st.error("Backend request failed (is it running?)")
        return None


def _post_json(
    path: str, params: Optional[Dict] = None, json: Optional[Dict] = None
) -> Optional[requests.Response]:
    try:
        return client.post_json(path, params=params, json=json or {})
    except requests.RequestException:
        st.error("Backend request failed (is it running?)")
        return None


auth = get_auth_state(session_key="user_auth")

# One-run flash messages (survive reruns deterministically).
if st.session_state.pop("_flash_signed_in", False):
    st.success("Signed in")

# Backwards-compatible session keys used by existing tests/E2E.
if auth.is_authenticated:
    st.session_state["access_token"] = auth.access_token
    st.session_state["username"] = auth.email
else:
    st.session_state.pop("access_token", None)
    st.session_state.pop("username", None)

_render_session_debug()

tab_login, tab_reset = st.tabs(["Login", "Reset password"])

with tab_login:
    if auth.is_authenticated:
        st.info("You're signed in. Use **Sign out** below the tabs.")
    else:
        st.subheader("Login")
        with st.form("login_form"):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Sign in")

        if submitted:
            resp = _post_form(
                "/auth/token", data={"username": email, "password": password}
            )
            if resp is None:
                st.stop()
            if resp.ok:
                data = safe_json(resp)
                access_token = str(data.get("access_token") or "")
                if not access_token:
                    show_http_error("Login failed", resp)
                    st.stop()
                login_success(
                    access_token=access_token,
                    email=email,
                    session_key="user_auth",
                )
                st.session_state["_flash_signed_in"] = True
                st.rerun()
            else:
                show_http_error("Invalid email or password", resp)

with tab_reset:
    st.subheader("Forgot password")
    st.caption(
        "Enter your email and we’ll send you a reset link (if the account exists)."
    )
    with st.form("forgot_form"):
        forgot_email = st.text_input("Email", key="forgot_email")
        forgot_submit = st.form_submit_button("Send reset link")

    if forgot_submit:
        resp = _post_json("/password/forgot", json={"email": forgot_email})
        if resp is None:
            st.stop()
        if resp.ok:
            st.success("If the account exists, a reset email has been sent.")
            st.info(
                f"For local dev you can open: {BACKEND_URL}/password/reset?token=<token-from-email>"
            )
        else:
            st.error(f"Reset request failed: {resp.status_code} {resp.text}")

    st.divider()
    st.subheader("Reset using token (demo)")
    st.caption(
        "If you have a reset token (from email), you can reset here without leaving Streamlit."
    )
    with st.form("reset_form"):
        token = st.text_input("Reset token", key="reset_token")
        new_password = st.text_input(
            "New password", type="password", key="reset_new_password"
        )
        reset_submit = st.form_submit_button("Reset password")

    if reset_submit:
        resp = _post_json(
            "/password/reset", json={"token": token, "password": new_password}
        )
        if resp is None:
            st.stop()
        if resp.ok:
            st.success("Password updated. You can now log in.")
        else:
            st.error(f"Reset failed: {resp.status_code} {resp.text}")

if auth.is_authenticated:
    st.divider()
    st.success("Authenticated session is active.")
    if auth.email:
        st.caption(f"Signed in as `{auth.email}`")
    if st.button("Sign out", type="primary", key="user_sign_out_main"):
        st.session_state["_sign_out_clicked"] = True
        st.rerun()
