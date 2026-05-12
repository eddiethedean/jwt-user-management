"""
JWT users Streamlit UI (FluxLit ``discover_pages`` pattern).

https://fluxlit.readthedocs.io/en/stable/quickstart.html#project-layout
"""

from __future__ import annotations

from typing import Literal, Optional

import httpx
from fluxlit import FluxLit

from ui.auth_state import SESSION_KEY, get_auth_state, login_success, logout
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
from ui.url_session_bridge import (
    apply_hydrated_auth,
    clear_url_session,
    get_url_store,
    persist_url_session_narrow,
    run_url_session_ensure,
    run_url_session_hydrate,
    url_session_enabled,
)

PublicPage = Literal["Login", "Register", "Accept invite", "Reset password"]


def register(app: FluxLit) -> None:
    url_session_param = app.settings.url_session_query_param

    @app.page("/", title="User Management")
    def jwt_users_home(st, client) -> None:  # noqa: ANN001
        st.title("User Management")

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
            st.sidebar.subheader("Navigation")
            _public_nav: tuple[PublicPage, ...] = (
                "Login",
                "Register",
                "Accept invite",
                "Reset password",
            )
            if (
                "public_page_nav" not in st.session_state
                or st.session_state["public_page_nav"] not in _public_nav
            ):
                st.session_state["public_page_nav"] = "Login"
            nav_raw = st.sidebar.radio(
                "Menu",
                options=list(_public_nav),
                key="public_page_nav",
            )
            public_page: PublicPage = nav_raw if nav_raw in _public_nav else "Login"

            st.sidebar.divider()
            st.sidebar.link_button("API docs", docs_link, use_container_width=True)

            def _load_me_for_login(token: str):
                return load_me(st, token)

            if public_page == "Login":
                render_login(st, post_form=_post_form, load_me_fn=_load_me_for_login)
            elif public_page == "Register":
                render_register(st, post_form=_post_form)
            elif public_page == "Accept invite":
                render_accept_invite(st, post_json_pub=_post_json_pub)
            else:
                render_reset_password(st, post_json_pub=_post_json_pub)

        if url_session_enabled():
            persist_url_session_narrow(st, url_store, auth, param=url_session_param)
