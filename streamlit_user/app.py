import os

import requests
import streamlit as st
from dotenv import load_dotenv
from typing import Dict, Optional

load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")


def _post_form(path: str, data: dict) -> requests.Response:
    return requests.post(
        f"{BACKEND_URL}{path}",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10,
    )


def _post_json(
    path: str, params: Optional[Dict] = None, json: Optional[Dict] = None
) -> requests.Response:
    return requests.post(f"{BACKEND_URL}{path}", params=params, json=json, timeout=10)


def _get(path: str, params: Optional[Dict] = None) -> requests.Response:
    return requests.get(f"{BACKEND_URL}{path}", params=params, timeout=10)


st.set_page_config(page_title="User App • Demo", layout="centered")
st.title("User app (demo)")

tab_login, tab_reset = st.tabs(["Login", "Reset password"])

with tab_login:
    st.subheader("Login")
    with st.form("login_form"):
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        submitted = st.form_submit_button("Sign in")

    if submitted:
        resp = _post_form("/auth/token", data={"username": email, "password": password})
        if resp.ok:
            st.session_state["access_token"] = resp.json()["access_token"]
            st.success("Signed in")
        else:
            st.error("Invalid email or password")

    if st.session_state.get("access_token"):
        st.divider()
        st.success("Authenticated session is active.")
        if st.button("Sign out"):
            st.session_state.pop("access_token", None)
            st.rerun()

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
        if resp.ok:
            st.success("Password updated. You can now log in.")
        else:
            st.error(f"Reset failed: {resp.status_code} {resp.text}")
