import os
from datetime import datetime, timedelta

import extra_streamlit_components as stx
import jwt
import requests
import streamlit as st
from dotenv import load_dotenv
from typing import Dict, Optional

load_dotenv()

st.set_page_config(page_title="User App • Demo", layout="centered")
st.title("User app (demo)")

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
COOKIE_NAME = os.getenv("USER_COOKIE_NAME", "user-demo-auth")
COOKIE_KEY = os.getenv("USER_COOKIE_KEY", "change-me")
COOKIE_EXPIRY_DAYS = float(os.getenv("USER_COOKIE_EXPIRY_DAYS", "7"))
DISABLE_COOKIES = os.getenv("STREAMLIT_DISABLE_COOKIES", "").lower() in (
    "1",
    "true",
    "yes",
)

cookie_manager = stx.CookieManager()


def _cookie_set(*, username: str, access_token: str) -> None:
    if DISABLE_COOKIES or COOKIE_EXPIRY_DAYS <= 0:
        return
    exp_date = (datetime.now() + timedelta(days=COOKIE_EXPIRY_DAYS)).timestamp()
    token = jwt.encode(
        {"username": username, "access_token": access_token, "exp_date": exp_date},
        COOKIE_KEY,
        algorithm="HS256",
    )
    cookie_manager.set(
        COOKIE_NAME,
        token,
        expires_at=datetime.now() + timedelta(days=COOKIE_EXPIRY_DAYS),
    )


def _cookie_get() -> Optional[Dict]:
    if DISABLE_COOKIES:
        return None
    raw = st.context.cookies.get(COOKIE_NAME)
    if not raw or raw == "deleted":
        return None
    try:
        data = jwt.decode(raw, COOKIE_KEY, algorithms=["HS256"])
    except Exception:
        return None
    exp = data.get("exp_date")
    if not exp or exp <= datetime.now().timestamp():
        return None
    return data


def _cookie_delete() -> None:
    if DISABLE_COOKIES:
        return
    try:
        cookie_manager.delete(COOKIE_NAME)
        # Some browsers / Streamlit contexts may keep the old cookie value for one run.
        # Setting a short-lived sentinel helps ensure we don't immediately restore.
        cookie_manager.set(
            COOKIE_NAME, "deleted", expires_at=datetime.now() - timedelta(days=1)
        )
    except Exception:
        pass


def _post_form(path: str, data: dict) -> Optional[requests.Response]:
    try:
        return requests.post(
            f"{BACKEND_URL}{path}",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
    except requests.RequestException:
        st.error("Backend request failed (is it running?)")
        return None


def _post_json(
    path: str, params: Optional[Dict] = None, json: Optional[Dict] = None
) -> Optional[requests.Response]:
    try:
        return requests.post(
            f"{BACKEND_URL}{path}", params=params, json=json, timeout=10
        )
    except requests.RequestException:
        st.error("Backend request failed (is it running?)")
        return None


def _get(path: str, params: Optional[Dict] = None) -> Optional[requests.Response]:
    try:
        return requests.get(f"{BACKEND_URL}{path}", params=params, timeout=10)
    except requests.RequestException:
        st.error("Backend request failed (is it running?)")
        return None


# Explicit logout flag to prevent immediate cookie restore
if "logout" not in st.session_state:
    st.session_state["logout"] = False

# Restore session from cookie if present
if not st.session_state.get("logout") and "access_token" not in st.session_state:
    saved = _cookie_get()
    if saved and saved.get("access_token"):
        st.session_state["access_token"] = saved["access_token"]
        st.session_state["username"] = saved.get("username")

tab_login, tab_reset = st.tabs(["Login", "Reset password"])

with tab_login:
    st.subheader("Login")
    with st.form("login_form"):
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        submitted = st.form_submit_button("Sign in")

    if submitted:
        resp = _post_form("/auth/token", data={"username": email, "password": password})
        if resp is None:
            st.stop()
        if resp.ok:
            st.session_state["access_token"] = resp.json()["access_token"]
            st.session_state["username"] = email
            _cookie_set(username=email, access_token=st.session_state["access_token"])
            st.success("Signed in")
        else:
            st.error("Invalid email or password")

    if st.session_state.get("access_token"):
        st.divider()
        st.success("Authenticated session is active.")
        if st.session_state.get("username"):
            st.caption(f"Signed in as `{st.session_state['username']}`")
        if st.button("Sign out"):
            st.session_state.pop("access_token", None)
            st.session_state.pop("username", None)
            st.session_state["logout"] = True
            _cookie_delete()
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
