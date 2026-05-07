import os
from typing import Dict, Optional, Literal

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
st.title("User Management")

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


Page = Literal["Users", "Admin", "Account"]


def _set_page(p: Page) -> None:
    st.session_state["_page"] = p


def _get_page() -> Page:
    p = st.session_state.get("_page")
    return p if p in ("Users", "Admin", "Account") else "Users"


def _authed_client() -> BackendClient:
    return BackendClient(base_url=BACKEND_URL, access_token=auth.access_token)


def _load_me() -> dict:
    me = st.session_state.get("_me")
    if isinstance(me, dict):
        return me
    try:
        r = _authed_client().get("/users/me")
    except httpx.RequestError:
        me = {}
    else:
        me = safe_json(r) if r.ok else {}
    st.session_state["_me"] = me
    return me

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
        st.info("You're signed in. Use **Sign out** in the sidebar.")
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
                st.session_state["_page"] = "Admin" if bool(_load_me().get("is_admin")) else "Users"
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
    me = _load_me()
    is_admin = bool(me.get("is_admin"))
    st.sidebar.subheader("Navigation")
    st.sidebar.button("Users", on_click=_set_page, args=("Users",))
    st.sidebar.button("Account", on_click=_set_page, args=("Account",))
    if is_admin:
        st.sidebar.button("Admin", on_click=_set_page, args=("Admin",))

    st.sidebar.divider()
    country = str(me.get("country") or "").strip()
    who = f"{auth.email}" + (f" ({country})" if country else "")
    st.sidebar.caption(f"Signed in as `{who}`")
    if st.sidebar.button("Sign out", type="primary", key="sign_out_sidebar"):
        st.session_state["_sign_out_clicked"] = True
        st.rerun()

    st.session_state.pop("_flash_signed_in", None)
    page = _get_page()

    if page == "Users":
        st.subheader("Users")
        if st.button("Refresh users", key="refresh_users"):
            try:
                r = _authed_client().get("/users")
            except httpx.RequestError:
                st.error("Backend request failed (is it running?)")
            else:
                if not r.ok:
                    show_http_error("Failed to load users", r)
                else:
                    data = safe_json(r)
                    rows = (
                        data.get("data") if isinstance(data.get("data"), list) else data
                    )
                    if not isinstance(rows, list):
                        rows = []
                    st.session_state["_users_cache"] = rows

        rows = st.session_state.get("_users_cache", [])
        if rows:
            st.dataframe(rows, use_container_width=True)
        else:
            st.info("Click **Refresh users** to load the user list.")

    elif page == "Account":
        st.subheader("Account")
        st.caption(f"Email: `{me.get('email','')}`")
        st.caption(f"Country: `{me.get('country','')}`")
        with st.form("acct_name"):
            full_name = st.text_input("Full name (optional)", value=str(me.get("full_name") or ""))
            saved = st.form_submit_button("Save")
        if saved:
            resp = _post_json("/users/me", json={"full_name": full_name})
            if resp is None:
                st.stop()
            if resp.ok:
                st.success("Saved")
                st.session_state.pop("_me", None)
                _load_me()
            else:
                show_http_error("Save failed", resp)

        st.divider()
        st.subheader("Change password")
        with st.form("acct_pw"):
            cur = st.text_input("Current password", type="password")
            new = st.text_input("New password", type="password")
            cfm = st.text_input("Confirm new password", type="password")
            ok = st.form_submit_button("Update password")
        if ok:
            resp = _post_json(
                "/users/me/password",
                json={"current_password": cur, "new_password": new, "confirm_password": cfm},
            )
            if resp is None:
                st.stop()
            if resp.ok:
                st.success("Password updated")
            else:
                show_http_error("Password update failed", resp)

    elif page == "Admin":
        if not is_admin:
            st.error("Admin required")
        else:
            st.subheader("Admin")
            with st.form("invite_form"):
                invite_email = st.text_input("Invite email")
                grant_admin = st.checkbox("Grant admin privileges", value=False)
                submit = st.form_submit_button("Create invite")
            if submit:
                with st.spinner("Looking up email…"):
                    resp = _post_json("/invites/lookup", json={"email": invite_email})
                if resp is None:
                    st.stop()
                if not resp.ok:
                    show_http_error("Could not verify email", resp)
                    st.stop()
                with st.spinner("Sending email…"):
                    r2 = _post_json(
                        "/invites",
                        json={"email": invite_email, "grant_admin": bool(grant_admin)},
                    )
                if r2 is None:
                    st.stop()
                if r2.ok:
                    j = safe_json(r2)
                    st.success("Invite created")
                    st.code(str(j.get("invite_url") or ""))
                else:
                    show_http_error("Invite failed", r2)

            st.divider()
            st.subheader("Manage users")
            r = _authed_client().get("/users")
            rows = safe_json(r) if r.ok else {}
            users = rows.get("data") if isinstance(rows.get("data"), list) else rows
            if not isinstance(users, list):
                users = []
            options = {f"{u.get('email','')} (id={u.get('id')})": u for u in users if isinstance(u, dict)}
            sel = st.selectbox("Select user", options=list(options.keys()))
            u = options.get(sel) if sel else None
            if isinstance(u, dict):
                st.caption(f"User id: `{u.get('id')}`")
                with st.form("edit_user"):
                    fn = st.text_input("Full name", value=str(u.get("full_name") or ""))
                    active = st.checkbox("Active", value=bool(u.get("is_active")))
                    admin_flag = st.checkbox("Admin", value=bool(u.get("is_admin")))
                    save_u = st.form_submit_button("Save user")
                if save_u:
                    rr = _authed_client().patch_json(
                        f"/admin/users/{u.get('id')}",
                        json={"full_name": fn, "is_active": active, "is_admin": admin_flag},
                    )
                    if rr.ok:
                        st.success("Saved")
                    else:
                        show_http_error("Save failed", rr)

                del_confirm = st.checkbox("Confirm delete", value=False)
                if st.button("Delete user", disabled=not del_confirm):
                    user_id = int(u.get("id") or 0)
                    resp_del = httpx.delete(
                        f"{BACKEND_URL}/admin/users/{user_id}",
                        headers={"Authorization": f"Bearer {auth.access_token}"},
                        timeout=10,
                    )
                    if resp_del.status_code < 300:
                        st.success("Deleted")
                    else:
                        show_http_error("Delete failed", resp_del)
