import os
import sys
from pathlib import Path

import requests
import streamlit as st
from dotenv import load_dotenv

APP_ROOT = Path(__file__).resolve().parent
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from admin_common.auth_state import (
    get_auth_state,
    login_success,
    logout,
    require_admin_from_me,
)
from admin_common.backend_client import (
    BackendClient,
    safe_json,
    validate_admin_requires_https,
    validate_backend_url,
    validate_streamlit_test_mode_backend,
)
from admin_common.ui import show_http_error

load_dotenv()

st.set_page_config(page_title="Admin • User Management", layout="wide")
st.title("User management")

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
ADMIN_API_KEY = os.getenv("BACKEND_ADMIN_API_KEY", "")
DEBUG = os.getenv("DEBUG", "").lower() in ("1", "true", "yes")


def _render_session_debug() -> None:
    if not DEBUG:
        return
    st.sidebar.caption("Session (debug)")
    a = get_auth_state(session_key="admin_auth")
    st.sidebar.json(
        {"authenticated": a.is_authenticated, "email": a.email or "(none)"}
    )


try:
    validate_backend_url(BACKEND_URL)
    validate_admin_requires_https(BACKEND_URL, admin_api_key=ADMIN_API_KEY)
    validate_streamlit_test_mode_backend(BACKEND_URL)
except ValueError as e:
    st.error(str(e))
    st.stop()

if st.session_state.pop("_admin_sign_out_clicked", False):
    logout(session_key="admin_auth")
    st.rerun()

auth = get_auth_state(session_key="admin_auth")

if st.session_state.pop("_flash_admin_signed_in", False):
    st.success("Signed in")

if auth.is_authenticated:
    st.session_state["access_token"] = auth.access_token
    st.session_state["username"] = auth.email
else:
    st.session_state.pop("access_token", None)
    st.session_state.pop("username", None)

_render_session_debug()


def _client_for_current() -> BackendClient:
    return BackendClient(
        base_url=BACKEND_URL,
        admin_api_key=ADMIN_API_KEY,
        access_token=auth.access_token,
    )


def _verify_admin() -> bool:
    """
    Verify the current auth token corresponds to an admin user.
    Clears session auth if the token is invalid or the user is not an admin so the
    sign-in form is not stuck behind a stale JWT.
    """
    if not auth.is_authenticated:
        return False
    c = _client_for_current()
    try:
        r = c.get("/users/me")
    except requests.RequestException:
        st.error("Backend request failed (is it running?)")
        st.stop()
    if not r.ok:
        show_http_error("Failed to verify session", r)
        logout(session_key="admin_auth")
        return False
    ok, msg = require_admin_from_me(safe_json(r))
    if not ok:
        if msg:
            st.error(msg)
        logout(session_key="admin_auth")
        return False
    return True


is_admin = _verify_admin()

if not auth.is_authenticated or not is_admin:
    st.subheader("Admin sign in")
    with st.form("admin_login_form"):
        email = st.text_input("Email", key="admin_login_email")
        password = st.text_input("Password", type="password", key="admin_login_password")
        submitted = st.form_submit_button("Sign in")

    if submitted:
        c = BackendClient(base_url=BACKEND_URL)
        try:
            r = c.post_form("/auth/token", data={"username": email, "password": password})
        except requests.RequestException:
            st.error("Backend request failed (is it running?)")
            st.stop()
        if not r.ok:
            show_http_error("Invalid email or password", r)
            st.stop()

        data = safe_json(r)
        token = str(data.get("access_token") or "")
        if not token:
            show_http_error("Login failed", r)
            st.stop()

        login_success(
            access_token=token,
            email=email,
            session_key="admin_auth",
        )
        st.session_state["_flash_admin_signed_in"] = True
        st.rerun()

    st.stop()

st.sidebar.write(f"Signed in as **{auth.email or 'admin'}**")
if st.sidebar.button("Sign out", type="primary", key="admin_sign_out"):
    st.session_state["_admin_sign_out_clicked"] = True
    st.rerun()

if not ADMIN_API_KEY:
    st.warning(
        "Set `BACKEND_ADMIN_API_KEY` in `user_management_api/admin_ui/.env` to enable admin API calls."
    )
    st.stop()

client = _client_for_current()

col1, col2 = st.columns([2, 1], gap="large")

with col1:
    st.subheader("Users")
    try:
        resp = client.get("/users")
    except requests.RequestException:
        st.error("Backend request failed (is it running?)")
        st.stop()
    if not resp.ok:
        show_http_error("Failed to load users", resp)
        st.stop()
    users = safe_json(resp).get("data")
    if isinstance(users, list):
        desired_keys = [
            "id",
            "email",
            "full_name",
            "is_active",
            "is_admin",
            "email_verified",
            "permissions",
            "created_at",
        ]
        rows = [
            {k: u.get(k) for k in desired_keys}
            for u in users
            if isinstance(u, dict)
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.caption("No users to display.")

    st.divider()
    st.subheader("Update permissions / flags")
    with st.form("update_user_form"):
        user_id = st.number_input("User ID", min_value=1, step=1)
        permissions = st.text_input("Update permissions (comma-separated)", value="")
        is_admin_flag = st.checkbox("Is admin", value=False)
        is_active_flag = st.checkbox("Is active", value=True)
        submitted = st.form_submit_button("Update user")
    if submitted:
        payload = {
            "permissions": [p.strip() for p in permissions.split(",") if p.strip()],
            "is_admin": is_admin_flag,
            "is_active": is_active_flag,
        }
        try:
            r = client.patch_json(f"/users/{int(user_id)}", json=payload)
        except requests.RequestException:
            st.error("Backend request failed (is it running?)")
            st.stop()
        if r.ok:
            st.success("Updated")
            st.rerun()
        else:
            show_http_error("Update failed", r)

with col2:
    st.subheader("Add user (send invite email)")
    with st.form("add_user"):
        email = st.text_input("Email", key="admin_invite_email")
        full_name = st.text_input("Full name", key="admin_invite_full_name")
        new_is_admin = st.checkbox("Admin", value=False)
        perms = st.text_input("Invite permissions (comma-separated)")
        submitted = st.form_submit_button("Send invite")
    if submitted:
        payload = {
            "email": email,
            "full_name": full_name or None,
            "is_admin": new_is_admin,
            "permissions": [p.strip() for p in perms.split(",") if p.strip()],
        }
        try:
            r = client.post_json("/invites", json=payload)
        except requests.RequestException:
            st.error("Backend request failed (is it running?)")
            st.stop()
        if r.ok:
            data = safe_json(r)
            st.success("Invite sent")
            st.code(str(data.get("invite_url") or ""), language="text")
        else:
            show_http_error("Invite failed", r)
