"""Authenticated navigation, user list, account, and admin screens."""

from __future__ import annotations

from typing import Any, Literal

import httpx
import streamlit as st
from fluxlit.client import ApiClient

from ui.auth_state import AuthState
from ui.http import (
    fluxlit_api_client_kwargs,
    patch_json,
    response_ok,
    safe_json,
    show_http_error,
)
from ui.pages.um_helpers import public_url
from ui.pages.um_profile import load_me

AuthedPage = Literal["Users", "Admin", "Account"]


def _set_page(p: AuthedPage) -> None:
    st.session_state["_page"] = p


def _get_page() -> AuthedPage:
    p = st.session_state.get("_page")
    return p if p in ("Users", "Admin", "Account") else "Users"


def _render_users(st: Any, auth: AuthState) -> None:
    st.subheader("Users")
    if st.button("Refresh users", key="refresh_users"):
        try:
            with ApiClient.for_fluxlit(
                bearer_token=auth.access_token, **fluxlit_api_client_kwargs()
            ) as api:
                r = api.get("/users")
        except httpx.RequestError:
            st.error("Backend request failed (is it running?)")
        else:
            if not response_ok(r):
                show_http_error("Failed to load users", r)
            else:
                data = safe_json(r)
                rows = (
                    data.get("data")
                    if isinstance(data.get("data"), list)
                    else data
                )
                if not isinstance(rows, list):
                    rows = []
                st.session_state["_users_cache"] = rows

    rows = st.session_state.get("_users_cache", [])
    if rows:
        st.dataframe(rows, use_container_width=True)
    else:
        st.info("Click **Refresh users** to load the user list.")


def _render_account(st: Any, auth: AuthState, me: dict[str, Any]) -> None:
    st.subheader("Account")
    st.caption(f"Email: `{me.get('email', '')}`")
    st.caption(f"Country: `{me.get('country', '')}`")
    with st.form("acct_name"):
        full_name = st.text_input(
            "Full name (optional)", value=str(me.get("full_name") or "")
        )
        saved = st.form_submit_button("Save")
    if saved:
        try:
            with ApiClient.for_fluxlit(
                bearer_token=auth.access_token, **fluxlit_api_client_kwargs()
            ) as api:
                resp = api.post("/users/me", json={"full_name": full_name})
        except httpx.RequestError:
            st.error("Backend request failed (is it running?)")
            st.stop()
        if response_ok(resp):
            st.success("Saved")
            st.session_state.pop("_me", None)
            load_me(st, auth.access_token)
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
        try:
            with ApiClient.for_fluxlit(
                bearer_token=auth.access_token, **fluxlit_api_client_kwargs()
            ) as api:
                resp = api.post(
                    "/users/me/password",
                    json={
                        "current_password": cur,
                        "new_password": new,
                        "confirm_password": cfm,
                    },
                )
        except httpx.RequestError:
            st.error("Backend request failed (is it running?)")
            st.stop()
        if response_ok(resp):
            st.success("Password updated")
        else:
            show_http_error("Password update failed", resp)


def _render_admin(
    st: Any, auth: AuthState, *, public_api_base: str
) -> None:
    st.subheader("Admin")
    with st.form("invite_form"):
        invite_email = st.text_input("Invite email")
        grant_admin = st.checkbox("Grant admin privileges", value=False)
        submit = st.form_submit_button("Create invite")
    if submit:
        with ApiClient.for_fluxlit(
            bearer_token=auth.access_token, **fluxlit_api_client_kwargs()
        ) as api:
            with st.spinner("Looking up email…"):
                resp = api.post("/invites/lookup", json={"email": invite_email})
            if not response_ok(resp):
                show_http_error("Could not verify email", resp)
                st.stop()
            with st.spinner("Sending email…"):
                r2 = api.post(
                    "/invites",
                    json={
                        "email": invite_email,
                        "grant_admin": bool(grant_admin),
                    },
                )
        if response_ok(r2):
            j = safe_json(r2)
            st.success("Invite created")
            st.code(
                public_url(
                    str(j.get("invite_url") or ""),
                    public_api_base=public_api_base or "",
                )
            )
        else:
            show_http_error("Invite failed", r2)

    st.divider()
    st.subheader("Manage users")
    with ApiClient.for_fluxlit(
        bearer_token=auth.access_token, **fluxlit_api_client_kwargs()
    ) as api:
        r = api.get("/users")
    rows = safe_json(r) if response_ok(r) else {}
    users = rows.get("data") if isinstance(rows.get("data"), list) else rows
    if not isinstance(users, list):
        users = []
    options = {
        f"{u.get('email', '')} (id={u.get('id')})": u
        for u in users
        if isinstance(u, dict)
    }
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
            with ApiClient.for_fluxlit(
                bearer_token=auth.access_token, **fluxlit_api_client_kwargs()
            ) as api:
                rr = patch_json(
                    api,
                    f"/admin/users/{u.get('id')}",
                    json={
                        "full_name": fn,
                        "is_active": active,
                        "is_admin": admin_flag,
                    },
                )
            if response_ok(rr):
                st.success("Saved")
            else:
                show_http_error("Save failed", rr)

        del_confirm = st.checkbox("Confirm delete", value=False)
        if st.button("Delete user", disabled=not del_confirm):
            user_id = int(u.get("id") or 0)
            with ApiClient.for_fluxlit(
                bearer_token=auth.access_token, **fluxlit_api_client_kwargs()
            ) as api:
                resp_del = api.delete(f"/admin/users/{user_id}")
            if resp_del.status_code < 300:
                st.success("Deleted")
            else:
                show_http_error("Delete failed", resp_del)


def render_authenticated(
    st: Any,
    auth: AuthState,
    me: dict[str, Any],
    *,
    is_admin: bool,
    public_api_base: str,
    docs_href: str,
) -> None:
    st.sidebar.subheader("Navigation")
    st.sidebar.button("Users", on_click=_set_page, args=("Users",))
    st.sidebar.button("Account", on_click=_set_page, args=("Account",))
    if is_admin:
        st.sidebar.button("Admin", on_click=_set_page, args=("Admin",))

    st.sidebar.divider()
    st.sidebar.link_button("API docs", docs_href, use_container_width=True)
    country = str(me.get("country") or "").strip()
    who = f"{auth.email}" + (f" ({country})" if country else "")
    st.sidebar.caption(f"Signed in as `{who}`")
    if st.sidebar.button("Sign out", type="primary", key="sign_out_sidebar"):
        st.session_state["_sign_out_clicked"] = True
        st.rerun()

    st.session_state.pop("_flash_signed_in", None)
    page = _get_page()

    if page == "Users":
        _render_users(st, auth)
    elif page == "Account":
        _render_account(st, auth, me)
    elif page == "Admin":
        if not is_admin:
            st.error("Admin required")
        else:
            _render_admin(st, auth, public_api_base=public_api_base)
