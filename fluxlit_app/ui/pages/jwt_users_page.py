"""
JWT users Streamlit UI (FluxLit ``discover_pages`` pattern).

Navigation and pages mirror ``user_management_api`` HTML UI:
guest → Sign in (+ Register when enabled); admin → Admin + Account;
non-admin → Account only. Accept-invite and reset-password are deep-link pages.
"""

from __future__ import annotations

from typing import Literal, Optional, cast

import httpx
from fluxlit import FluxLit

from ui.auth_state import SESSION_KEY, get_auth_state, login_success, logout
from ui.branding import render_brand, self_registration_enabled
from ui.pages.um_helpers import (
    api_docs_link,
    dbg,
    render_debug_logs,
    render_session_debug,
)
from ui.pages.um_profile import load_me
from ui.pages.um_screens_authed import render_authenticated
from ui.pages.um_screens_public import (
    render_accept_invite,
    render_login,
    render_register,
    render_reset_password,
)
from ui.theme import apply_um_theme
from ui.url_session_bridge import (
    apply_hydrated_auth,
    clear_url_session,
    get_url_store,
    persist_url_session_narrow,
    run_url_session_ensure,
    run_url_session_hydrate,
    url_session_enabled,
)

PublicPage = Literal["Sign in", "Register"]
DeepLinkPage = Literal["Accept invite", "Reset password"]


def _query_param_first(st, key: str) -> str:
    raw = st.query_params.get(key)
    if raw is None:
        return ""
    if isinstance(raw, list):
        return str(raw[0]) if raw else ""
    return str(raw)


def _apply_public_link_params(st) -> DeepLinkPage | None:
    page_raw = _query_param_first(st, "page")
    token = _query_param_first(st, "token")
    deep_pages = {"Accept invite", "Reset password"}
    if page_raw not in deep_pages:
        return None
    page = cast(DeepLinkPage, page_raw)
    if not token:
        return page
    marker = f"{page}:{token}"
    if st.session_state.get("_public_link_marker") == marker:
        return page
    if page == "Accept invite":
        st.session_state["invite_token"] = token
    elif page == "Reset password":
        st.session_state["reset_token"] = token
    st.session_state["_public_link_marker"] = marker
    return page


def register(app: FluxLit) -> None:
    url_session_param = app.settings.url_session_query_param

    @app.page("/", title="User Management")
    def jwt_users_home(st, client) -> None:  # noqa: ANN001
        apply_um_theme()
        render_brand(st)

        if "_debug_logs" not in st.session_state:
            st.session_state["_debug_logs"] = []

        dbg("FluxLit UI: using injected ApiClient for /api")

        url_store = get_url_store(st)
        if url_session_enabled():
            run_url_session_hydrate(st, url_store, param=url_session_param)
            apply_hydrated_auth(
                st, session_key=SESSION_KEY, login_success=login_success
            )

        if st.session_state.pop("_sign_out_clicked", False):
            if url_session_enabled():
                clear_url_session(st, url_store, param=url_session_param)
            logout(session_key=SESSION_KEY)
            st.rerun()

        if "_external_api_base" not in st.session_state:
            try:
                r_meta = client.get("/__meta")
                dbg(f"meta status={r_meta.status_code}")
                if r_meta.status_code < 300:
                    j = r_meta.json()
                    ext_api = str(j.get("external_api_base") or "").rstrip("/")
                    if ext_api:
                        st.session_state["_external_api_base"] = ext_api
            except Exception as e:
                dbg(f"meta fetch failed: {e!r}")

        public_api_base = str(st.session_state.get("_external_api_base") or "").rstrip(
            "/"
        )
        dbg(f"PUBLIC_API_BASE={public_api_base!r}")

        def _post_form(path: str, data: dict) -> Optional[httpx.Response]:
            try:
                return client.post(path, data=data)
            except httpx.RequestError:
                st.error("Backend request failed (is it running?)")
                return None

        def _post_json_pub(
            path: str, json: Optional[dict] = None
        ) -> Optional[httpx.Response]:
            try:
                return client.post(path, json=json or {})
            except httpx.RequestError:
                st.error("Backend request failed (is it running?)")
                return None

        if st.session_state.pop("_flash_signed_in", False):
            st.success("Signed in")

        auth = get_auth_state(session_key=SESSION_KEY)
        if auth.is_authenticated:
            st.session_state["jwt"] = auth.access_token
            st.session_state["access_token"] = auth.access_token
            st.session_state["username"] = auth.email
        else:
            st.session_state.pop("jwt", None)
            st.session_state.pop("access_token", None)
            st.session_state.pop("username", None)

        if url_session_enabled():
            run_url_session_ensure(st, url_store, auth, param=url_session_param)

        render_session_debug()
        render_debug_logs()

        docs_link = api_docs_link(public_api_base)

        if auth.is_authenticated:
            me = load_me(st, auth.access_token)
            render_authenticated(
                st,
                auth,
                me,
                is_admin=bool(me.get("is_admin")),
                public_api_base=public_api_base,
                docs_href=docs_link,
            )
        else:
            deep_page = _apply_public_link_params(st)

            if deep_page == "Accept invite":
                st.sidebar.caption("Invite link")
                st.sidebar.link_button("API docs", docs_link, use_container_width=True)
                render_accept_invite(st, post_json_pub=_post_json_pub)
            elif deep_page == "Reset password":
                st.sidebar.caption("Password reset")
                st.sidebar.link_button("API docs", docs_link, use_container_width=True)
                render_reset_password(st, post_json_pub=_post_json_pub)
            else:
                public_opts: list[PublicPage] = ["Sign in"]
                if self_registration_enabled():
                    public_opts.append("Register")

                st.sidebar.subheader("Navigation")
                if (
                    "public_page_nav" not in st.session_state
                    or st.session_state["public_page_nav"] not in public_opts
                ):
                    st.session_state["public_page_nav"] = "Sign in"
                nav_raw = st.sidebar.radio(
                    "Menu",
                    options=public_opts,
                    key="public_page_nav",
                )
                public_page: PublicPage = (
                    nav_raw if nav_raw in public_opts else "Sign in"
                )

                st.sidebar.divider()
                st.sidebar.link_button("API docs", docs_link, use_container_width=True)

                def _go_register() -> None:
                    st.session_state["public_page_nav"] = "Register"

                def _load_me_for_login(token: str):
                    return load_me(st, token)

                if public_page == "Sign in":
                    render_login(
                        st,
                        post_form=_post_form,
                        post_json_pub=_post_json_pub,
                        load_me_fn=_load_me_for_login,
                        on_register=_go_register if self_registration_enabled() else None,
                    )
                else:
                    render_register(st, post_form=_post_form)

        if url_session_enabled():
            persist_url_session_narrow(st, url_store, auth, param=url_session_param)
