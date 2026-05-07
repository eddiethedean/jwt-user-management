import os
from typing import Dict, Optional

import httpx
import streamlit as st

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover

    def load_dotenv(*args, **kwargs):  # type: ignore
        return False


try:
    from streamlit_user.user_common.auth_state import (  # type: ignore
        get_auth_state,
        login_success,
        logout,
    )
    from streamlit_user.user_common.backend_client import (  # type: ignore
        BackendClient,
        safe_json,
        validate_backend_url,
    )
    from streamlit_user.user_common.ui import show_http_error  # type: ignore
except ModuleNotFoundError:
    # Running from inside `streamlit_user/`
    from user_common.auth_state import get_auth_state, login_success, logout  # type: ignore
    from user_common.backend_client import (  # type: ignore
        BackendClient,
        safe_json,
        validate_backend_url,
    )
    from user_common.ui import show_http_error  # type: ignore

load_dotenv()

st.set_page_config(page_title="User App • Demo", layout="centered")
st.title("User app (demo)")

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8001").rstrip("/")
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


def _post_form(path: str, data: dict) -> Optional[httpx.Response]:
    try:
        return client.post_form(path, data=data)
    except httpx.RequestError:
        st.error("Backend request failed (is it running?)")
        return None


def _post_json(
    path: str, params: Optional[Dict] = None, json: Optional[Dict] = None
) -> Optional[httpx.Response]:
    try:
        return client.post_json(path, params=params, json=json or {})
    except httpx.RequestError:
        st.error("Backend request failed (is it running?)")
        return None


auth = get_auth_state(session_key="user_auth")

# One-run flash messages (survive reruns deterministically).
if st.session_state.pop("_flash_signed_in", False):
    st.success("Signed in")

# Backwards-compatible session keys used by existing tests/E2E.
if auth.is_authenticated:
    st.session_state["jwt"] = auth.access_token
    st.session_state["access_token"] = auth.access_token
    st.session_state["username"] = auth.email
else:
    st.session_state.pop("jwt", None)
    st.session_state.pop("access_token", None)
    st.session_state.pop("username", None)

_render_session_debug()

tab_login, tab_reset = st.tabs(["Login", "Reset password"])

with tab_login:
    if auth.is_authenticated:
        st.info("You're signed in. Use **Sign out** below the tabs.")
    else:
        st.subheader("Login")
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Sign in", key="login_submit"):
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
                    access_token=access_token, email=email, session_key="user_auth"
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
    forgot_email = st.text_input("Email", key="forgot_email")
    if st.button("Send reset link", key="forgot_submit"):
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
    token = st.text_input("Reset token", key="reset_token")
    new_password = st.text_input(
        "New password", type="password", key="reset_new_password"
    )
    if st.button("Reset password", key="reset_submit"):
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
    authed_client = BackendClient(base_url=BACKEND_URL, access_token=auth.access_token)

    # Fetch profile once per session to display extra fields like country.
    me = st.session_state.get("_me")
    if not isinstance(me, dict):
        try:
            r = authed_client.get("/users/me")
        except httpx.RequestError:
            me = {}
        else:
            me = safe_json(r) if r.ok else {}
        st.session_state["_me"] = me

    if auth.email:
        country = ""
        if isinstance(me, dict):
            c = str(me.get("country") or "").strip()
            if c:
                country = f" ({c})"
        st.caption(f"Signed in as `{auth.email}`{country}")

    st.subheader("API demo (user_management_api)")
    st.caption(
        "These calls use `Authorization: Bearer <jwt>` from Streamlit session state."
    )
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Get /users/me", key="me_btn"):
            try:
                r = authed_client.get("/users/me")
            except httpx.RequestError:
                st.error("Backend request failed (is it running?)")
            else:
                if r.ok:
                    st.json(safe_json(r))
                else:
                    show_http_error("Request failed", r)
    with col2:
        if st.button("List /users", key="users_btn"):
            try:
                r = authed_client.get("/users")
            except httpx.RequestError:
                st.error("Backend request failed (is it running?)")
            else:
                if r.ok:
                    st.json(safe_json(r))
                else:
                    show_http_error("Request failed", r)

    if st.button("Sign out", type="primary", key="user_sign_out_main"):
        st.session_state["_sign_out_clicked"] = True
        st.rerun()
