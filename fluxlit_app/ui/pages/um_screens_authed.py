"""Authenticated screens matching ``user_management_api`` HTML (Account, Admin, edit user)."""

from __future__ import annotations

import html
from datetime import datetime
from typing import Any, Literal

import httpx
import pandas as pd
import streamlit as st
from fluxlit.client import ApiClient

from ui.auth_state import AuthState
from ui.branding import configured_user_roles, render_session_pill
from ui.http import (
    fluxlit_api_client_kwargs,
    patch_json,
    response_ok,
    safe_json,
    show_http_error,
)
from ui.pages.um_profile import load_me

AuthedPage = Literal["Admin", "Account"]


def _fmt_dt(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d")
    s = str(val)
    return s[:10] if len(s) >= 10 else s


def _get_page() -> AuthedPage:
    p = st.session_state.get("_page")
    return p if p in ("Admin", "Account") else "Account"


def _role_labels(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(r) for r in raw if str(r).strip()]
    if isinstance(raw, str) and raw.strip():
        return [r.strip() for r in raw.split(",") if r.strip()]
    return []


def _render_account(st: Any, auth: AuthState, me: dict[str, Any]) -> None:
    is_admin = bool(me.get("is_admin"))
    welcome = str(me.get("full_name") or "").strip()
    st.markdown(
        '<p class="um-cardHint">'
        + (
            "Your personal settings. Use <strong>Admin</strong> in the menu to manage other accounts."
            if is_admin
            else "This is your home page. Update your name and password here."
        )
        + "</p>",
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        st.subheader(f"Welcome{', ' + welcome if welcome else ''}")

        roles = _role_labels(me.get("roles"))
        if not roles and me.get("is_admin"):
            roles = ["Admin"]
        elif not roles:
            roles = ["User"]

        uid = html.escape(str(me.get("id", "")))
        em = html.escape(str(me.get("email", "")))
        fn_disp = html.escape(str(me.get("full_name") or ""))
        country_e = html.escape(str(me.get("country") or ""))
        status_e = html.escape("Active" if me.get("is_active", True) else "Disabled")
        roles_e = html.escape(", ".join(roles))
        created = html.escape(_fmt_dt(me.get("created_at")))

        st.markdown("#### Profile")
        kv_extra = ""
        if country_e:
            kv_extra = (
                f"<div class='um-kvKey'>Country</div><div class='um-kvVal'>{country_e}</div>"
            )
        st.markdown(
            f"""
<div class="um-kvGrid" aria-label="Account details">
  <div class="um-kvKey">Email</div><div class="um-kvVal"><code>{em}</code></div>
  <div class="um-kvKey">Name</div><div class="um-kvVal">{fn_disp or "—"}</div>
  {kv_extra}
  <div class="um-kvKey">Status</div><div class="um-kvVal">{status_e}</div>
  <div class="um-kvKey">Roles</div><div class="um-kvVal">{roles_e}</div>
  <div class="um-kvKey">Member since</div><div class="um-kvVal">{created or "—"}</div>
</div>
""",
            unsafe_allow_html=True,
        )

        with st.form("acct_name"):
            full_name = st.text_input(
                "Display name",
                value=str(me.get("full_name") or ""),
                placeholder="e.g. Jane Doe",
            )
            saved = st.form_submit_button("Save name")
        if saved:
            try:
                with ApiClient.for_fluxlit(
                    bearer_token=auth.access_token, **fluxlit_api_client_kwargs()
                ) as api:
                    resp = patch_json(api, "/users/me", json={"full_name": full_name})
            except httpx.RequestError:
                st.error("Backend request failed (is it running?)")
                st.stop()
            if response_ok(resp):
                st.success("Saved")
                st.session_state.pop("_me", None)
                load_me(st, auth.access_token)
                st.rerun()
            else:
                show_http_error("Save failed", resp)

        st.divider()
        st.subheader("Password")
        st.markdown(
            '<p class="um-cardHint">Change the password you use to sign in.</p>',
            unsafe_allow_html=True,
        )
        with st.form("acct_pw"):
            cur = st.text_input("Current password", type="password")
            new = st.text_input("New password", type="password", placeholder="At least 12 characters")
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


def _load_users(auth: AuthState) -> list[dict[str, Any]]:
    try:
        with ApiClient.for_fluxlit(
            bearer_token=auth.access_token, **fluxlit_api_client_kwargs()
        ) as api:
            r = api.get("/users")
    except httpx.RequestError:
        st.error("Backend request failed (is it running?)")
        return []
    if not response_ok(r):
        show_http_error("Failed to load users", r)
        return []
    data = safe_json(r)
    users = data.get("data") if isinstance(data.get("data"), list) else data
    if not isinstance(users, list):
        return []
    return [u for u in users if isinstance(u, dict)]


def _render_admin_list(st: Any, auth: AuthState) -> None:
    _admin_flash = st.session_state.pop("_admin_flash", None)
    if isinstance(_admin_flash, str) and _admin_flash:
        st.success(_admin_flash)

    st.subheader("Admin")

    with st.expander("Invite user", expanded=True):
        st.markdown(
            '<p class="um-cardHint">Generate a one-time link to set a password.</p>',
            unsafe_allow_html=True,
        )
        with st.form("invite_form"):
            invite_email = st.text_input(
                "Email", placeholder="name@example.com", key="admin_invite_email"
            )
            grant_admin = st.checkbox(
                "Grant admin privileges",
                value=False,
                help="Allows access to the Admin page.",
            )
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
                lu = safe_json(resp)
                if isinstance(lu, dict):
                    em = str(lu.get("email") or "").strip()
                    ctry = str(lu.get("country") or "").strip()
                    dn = str(lu.get("display_name") or "").strip()
                    if em or ctry or dn:
                        parts: list[str] = []
                        if dn:
                            parts.append(f"Directory name: **{dn}**")
                        if em:
                            parts.append(f"Directory email: `{em}`")
                        if ctry:
                            parts.append(f"LDAP country: **{ctry}**")
                        st.info(" · ".join(parts))
                with st.spinner("Sending email…"):
                    r2 = api.post(
                        "/invites",
                        json={
                            "email": invite_email,
                            "grant_admin": bool(grant_admin),
                        },
                    )
            if response_ok(r2):
                st.success("Invite email sent.")
            else:
                show_http_error("Invite failed", r2)

    st.divider()
    users = _load_users(auth)
    head_l, head_r = st.columns([3, 1])
    with head_l:
        st.markdown("### All users")
    with head_r:
        st.markdown(
            f'<p class="um-muted" style="text-align:right;margin:0;">{len(users)} total</p>',
            unsafe_allow_html=True,
        )
    st.caption("Select a row to edit that user.")

    if not users:
        st.info("No users returned from the API.")
        return

    display_cols = [
        "id",
        "email",
        "full_name",
        "country",
        "is_active",
        "roles",
        "created_at",
    ]
    table_rows = []
    for raw in users:
        roles = _role_labels(raw.get("roles"))
        if not roles:
            roles = ["Admin"] if raw.get("is_admin") else ["User"]
        table_rows.append(
            {
                "id": raw.get("id"),
                "email": raw.get("email"),
                "full_name": raw.get("full_name"),
                "country": raw.get("country"),
                "is_active": "Active" if raw.get("is_active", True) else "Inactive",
                "roles": ", ".join(roles),
                "created_at": _fmt_dt(raw.get("created_at")),
            }
        )

    df = pd.DataFrame(table_rows, columns=display_cols)

    _table_gen_key = "_admin_users_table_gen"
    _gen = int(st.session_state.get(_table_gen_key, 0))
    _table_key = f"fluxlit_admin_users_{_gen}"

    event = st.dataframe(
        df,
        key=_table_key,
        on_select="rerun",
        selection_mode="single-row",
        use_container_width=True,
        hide_index=True,
    )

    sel_block = (
        event.get("selection", {})
        if isinstance(event, dict)
        else getattr(event, "selection", {}) or {}
    )
    row_ixs = sel_block.get("rows", []) if isinstance(sel_block, dict) else []
    if row_ixs:
        idx = int(row_ixs[0])
        if 0 <= idx < len(users):
            st.session_state["_edit_user_id"] = int(users[idx].get("id") or 0)
            st.session_state["_admin_view"] = "edit"
            st.rerun()


def _render_admin_edit(st: Any, auth: AuthState, me: dict[str, Any]) -> None:
    user_id = int(st.session_state.get("_edit_user_id") or 0)
    if st.button("← Back to user list", key="admin_edit_back"):
        st.session_state["_admin_view"] = "list"
        st.session_state.pop("_edit_user_id", None)
        st.rerun()

    users = _load_users(auth)
    u = next((x for x in users if int(x.get("id") or 0) == user_id), None)
    if not isinstance(u, dict):
        st.error("User not found")
        return

    is_self = int(me.get("id") or 0) == user_id
    st.subheader("Edit user")

    uid = html.escape(str(u.get("id", "")))
    em = html.escape(str(u.get("email", "")))
    created = html.escape(_fmt_dt(u.get("created_at")))
    st.markdown(
        f"""
<div class="um-kvGrid" aria-label="User details">
  <div class="um-kvKey">ID</div><div class="um-kvVal"><code>{uid}</code></div>
  <div class="um-kvKey">Email</div><div class="um-kvVal"><code>{em}</code></div>
  <div class="um-kvKey">Created</div><div class="um-kvVal">{created or "—"}</div>
</div>
""",
        unsafe_allow_html=True,
    )

    role_options = list(configured_user_roles()) or ["Admin", "User", "Super"]
    current_roles = _role_labels(u.get("roles"))
    if not current_roles and u.get("is_admin"):
        current_roles = [r for r in role_options if r in ("Admin", "Super")]

    with st.form("edit_user"):
        st.markdown("#### Access")
        fn = st.text_input("Full name (optional)", value=str(u.get("full_name") or ""))
        active = st.checkbox(
            "Active",
            value=bool(u.get("is_active")),
            disabled=is_self,
            help="Inactive users can't sign in." if not is_self else None,
        )
        selected_roles = st.multiselect(
            "Roles",
            options=role_options,
            default=[r for r in current_roles if r in role_options],
            disabled=is_self,
        )
        save_u = st.form_submit_button("Save changes")
    if save_u:
        payload: dict[str, Any] = {"full_name": fn, "is_active": active, "roles": selected_roles}
        with ApiClient.for_fluxlit(
            bearer_token=auth.access_token, **fluxlit_api_client_kwargs()
        ) as api:
            rr = patch_json(api, f"/admin/users/{user_id}", json=payload)
        if response_ok(rr):
            st.session_state["_admin_flash"] = "Saved"
            st.session_state["_admin_view"] = "list"
            st.session_state.pop("_edit_user_id", None)
            st.rerun()
        else:
            show_http_error("Save failed", rr)

    st.divider()
    st.markdown("#### Danger zone")
    if is_self:
        st.info("You can't delete your own account.")
    else:
        st.warning("Deleting a user is permanent.")
        del_confirm = st.checkbox("I understand this will permanently delete the account")
        if st.button("Delete user", disabled=not del_confirm):
            with ApiClient.for_fluxlit(
                bearer_token=auth.access_token, **fluxlit_api_client_kwargs()
            ) as api:
                resp_del = api.delete(f"/admin/users/{user_id}")
            if resp_del.status_code < 300:
                st.session_state["_admin_flash"] = "Deleted"
                st.session_state["_admin_view"] = "list"
                st.session_state.pop("_edit_user_id", None)
                st.rerun()
            else:
                show_http_error("Delete failed", resp_del)


def _render_admin(st: Any, auth: AuthState, me: dict[str, Any]) -> None:
    view = st.session_state.get("_admin_view", "list")
    if view == "edit" and st.session_state.get("_edit_user_id"):
        _render_admin_edit(st, auth, me)
    else:
        st.session_state["_admin_view"] = "list"
        _render_admin_list(st, auth)


def render_authenticated(
    st: Any,
    auth: AuthState,
    me: dict[str, Any],
    *,
    is_admin: bool,
    public_api_base: str,
    docs_href: str,
) -> None:
    render_session_pill(st, email=str(auth.email or ""))

    st.sidebar.subheader("Navigation")
    opts: list[AuthedPage] = ["Account"]
    if is_admin:
        opts.append("Admin")

    cur = _get_page()
    if cur not in opts:
        st.session_state["_page"] = "Account" if not is_admin else "Admin"
        cur = st.session_state["_page"]

    if (
        "authed_nav_radio" not in st.session_state
        or st.session_state["authed_nav_radio"] not in opts
    ):
        st.session_state["authed_nav_radio"] = cur

    selected = st.sidebar.radio("Menu", options=opts, key="authed_nav_radio")
    st.session_state["_page"] = selected

    st.sidebar.divider()
    st.sidebar.link_button("API docs", docs_href, use_container_width=True)
    if st.sidebar.button("Log out", type="primary", key="sign_out_sidebar"):
        st.session_state["_sign_out_clicked"] = True
        st.rerun()

    st.session_state.pop("_flash_signed_in", None)
    page = selected

    if page == "Account":
        _render_account(st, auth, me)
    elif page == "Admin":
        if not is_admin:
            st.error("Admin required")
        else:
            _render_admin(st, auth, me)
