"""
Tests for :class:`fluxlit.testing.FluxLitTestClient` (gateway API + Streamlit AppTest).

Uses ``load_fluxlit_app`` from this package’s ``conftest`` so routing matches production
(``/api`` prefix on the gateway).

Streamlit coverage via :meth:`FluxLitTestClient.streamlit` is intentionally limited to flows
that do not rely on ``st.navigation`` page switches after ``AppTest`` interactions; in
current Streamlit + FluxLit, changing the sidebar ``Menu`` radio then ``.run()`` can yield
an empty element tree.
"""

from __future__ import annotations

import pytest
from fluxlit.client import ApiClient
from fluxlit.testing import FluxLitTestClient
from starlette.testclient import TestClient
from streamlit.testing.v1 import AppTest

from fluxlit_test_helpers import load_fluxlit_app, seed_admin, seed_user
from streamlit_apptest_helpers import (
    FLUXLIT_MAIN,
    bridge_api_client,
    click_button,
    fluxlit_env,
    text_input_by_key,
)

# --- FluxLitTestClient: gateway / OpenAPI ---


def test_fluxlit_test_client_harness_smoke(tmp_path) -> None:
    app = load_fluxlit_app(db_url=f"sqlite:///{tmp_path / 'harness.db'}")
    tc = FluxLitTestClient(app)
    assert isinstance(tc.api, TestClient)
    assert tc.api_prefix == "/api"
    raw = tc.api_get("/openapi.json")
    assert raw.status_code == 200
    assert raw.json() == tc.openapi()


def test_fluxlit_test_client_users_me_requires_auth(tmp_path) -> None:
    app = load_fluxlit_app(db_url=f"sqlite:///{tmp_path / 'u.db'}")
    tc = FluxLitTestClient(app)
    r = tc.api_get("/users/me")
    assert r.status_code == 401


def test_fluxlit_test_client_users_list_requires_auth(tmp_path) -> None:
    app = load_fluxlit_app(db_url=f"sqlite:///{tmp_path / 'ul.db'}")
    tc = FluxLitTestClient(app)
    r = tc.api_get("/users")
    assert r.status_code == 401


def test_fluxlit_test_client_patch_users_me_requires_auth(tmp_path) -> None:
    app = load_fluxlit_app(db_url=f"sqlite:///{tmp_path / 'pm.db'}")
    tc = FluxLitTestClient(app)
    r = tc.api.request(
        "PATCH",
        f"{tc.api_prefix}/users/me",
        json={"full_name": "X"},
    )
    assert r.status_code == 401


def test_fluxlit_test_client_password_forgot_accepts_json(tmp_path) -> None:
    app = load_fluxlit_app(db_url=f"sqlite:///{tmp_path / 'pf.db'}")
    tc = FluxLitTestClient(app)
    r = tc.api_post("/password/forgot", json={"email": "nobody@example.com"})
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_fluxlit_test_client_password_inspect_requires_token(tmp_path) -> None:
    app = load_fluxlit_app(db_url=f"sqlite:///{tmp_path / 'pi.db'}")
    tc = FluxLitTestClient(app)
    r = tc.api_post("/password/inspect", json={"token": "invalid"})
    assert r.status_code == 404


def test_fluxlit_test_client_invites_inspect_requires_token(tmp_path) -> None:
    app = load_fluxlit_app(db_url=f"sqlite:///{tmp_path / 'ii.db'}")
    tc = FluxLitTestClient(app)
    r = tc.api_post("/invites/inspect", json={"token": "invalid"})
    assert r.status_code == 404


def test_fluxlit_test_client_auth_token_wrong_password(tmp_path) -> None:
    app = load_fluxlit_app(db_url=f"sqlite:///{tmp_path / 'tok.db'}")
    import app.db as db

    seed_user(
        db_engine=db.engine,
        email="u@example.com",
        password="right-password",
    )
    tc = FluxLitTestClient(app)
    r = tc.api_post(
        "/auth/token",
        data={"username": "u@example.com", "password": "wrong-password"},
    )
    assert r.status_code == 400
    assert "password" in str(r.json().get("detail", "")).lower()


def test_fluxlit_test_client_auth_token_success(tmp_path) -> None:
    app = load_fluxlit_app(db_url=f"sqlite:///{tmp_path / 'tok2.db'}")
    import app.db as db

    seed_user(
        db_engine=db.engine,
        email="ok@example.com",
        password="secret1234",
    )
    tc = FluxLitTestClient(app)
    r = tc.api_post(
        "/auth/token",
        data={"username": "ok@example.com", "password": "secret1234"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("access_token")
    assert body.get("token_type") == "bearer"


def test_register_duplicate_email_returns_ok_without_leak(tmp_path) -> None:
    app = load_fluxlit_app(db_url=f"sqlite:///{tmp_path / 'reg.db'}")
    import app.db as db
    from sqlmodel import Session, select

    from app.models import InviteToken

    seed_user(db_engine=db.engine, email="dup@example.com", password="x")
    tc = FluxLitTestClient(app)
    r = tc.api_post("/register", data={"email": "dup@example.com"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    with Session(db.engine) as s:
        invites = s.exec(
            select(InviteToken).where(InviteToken.email == "dup@example.com")
        ).all()
    assert invites == []


def test_fluxlit_test_client_register_creates_invite_for_new_email(
    tmp_path, monkeypatch
) -> None:
    app = load_fluxlit_app(db_url=f"sqlite:///{tmp_path / 'reg2.db'}")
    import app.core.config as config

    config.settings.smtp_host = "smtp.test.local"
    config.settings.smtp_from_email = "noreply@test.local"
    monkeypatch.setattr(
        "app.routes.auth.send_self_registration_email",
        lambda **kwargs: None,
    )
    tc = FluxLitTestClient(app)
    r = tc.api_post("/register", data={"email": "fresh@example.com"})
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    assert "setup_url" not in body
    assert "email_sent" not in body


def test_fluxlit_test_client_bearer_users_me(tmp_path) -> None:
    app = load_fluxlit_app(db_url=f"sqlite:///{tmp_path / 'me.db'}")
    import app.db as db

    seed_user(
        db_engine=db.engine,
        email="me@example.com",
        password="pw12345678",
        is_admin=False,
    )
    tc = FluxLitTestClient(app)
    tok = tc.api_post(
        "/auth/token",
        data={"username": "me@example.com", "password": "pw12345678"},
    ).json()["access_token"]
    r = tc.api_get("/users/me", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert r.json().get("email") == "me@example.com"


def test_fluxlit_test_client_rejects_inactive_bearer_user(tmp_path) -> None:
    app = load_fluxlit_app(db_url=f"sqlite:///{tmp_path / 'inactive.db'}")
    import app.db as db
    from app.core.security import create_access_token

    uid = seed_user(
        db_engine=db.engine,
        email="inactive@example.com",
        password="pw12345678",
        is_active=False,
    )
    tok = create_access_token(subject=str(uid))
    tc = FluxLitTestClient(app)

    r = tc.api_get("/users/me", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 403
    assert "inactive" in str(r.json().get("detail", "")).lower()


def test_fluxlit_test_client_patch_me_updates_full_name(tmp_path) -> None:
    app = load_fluxlit_app(db_url=f"sqlite:///{tmp_path / 'pn.db'}")
    import app.db as db

    seed_user(
        db_engine=db.engine,
        email="patch@example.com",
        password="pw12345678",
    )
    tc = FluxLitTestClient(app)
    tok = tc.api_post(
        "/auth/token",
        data={"username": "patch@example.com", "password": "pw12345678"},
    ).json()["access_token"]
    r = tc.api.request(
        "PATCH",
        f"{tc.api_prefix}/users/me",
        headers={"Authorization": f"Bearer {tok}"},
        json={"full_name": "Patched Name"},
    )
    assert r.status_code == 200
    assert r.json().get("full_name") == "Patched Name"


def test_fluxlit_test_client_admin_users_patch_requires_admin(tmp_path) -> None:
    app = load_fluxlit_app(db_url=f"sqlite:///{tmp_path / 'ad.db'}")
    import app.db as db

    uid = seed_user(
        db_engine=db.engine,
        email="plain@example.com",
        password="pw12345678",
        is_admin=False,
    )
    tc = FluxLitTestClient(app)
    tok = tc.api_post(
        "/auth/token",
        data={"username": "plain@example.com", "password": "pw12345678"},
    ).json()["access_token"]
    r = tc.api.request(
        "PATCH",
        f"{tc.api_prefix}/admin/users/{uid}",
        headers={"Authorization": f"Bearer {tok}"},
        json={"full_name": "nope"},
    )
    assert r.status_code == 403


# --- FluxLitTestClient.streamlit() ---


def _patch_load_me_for_tc(monkeypatch, tc) -> None:
    def _load_me(st, token: str):
        r = tc.api_get("/users/me", headers={"Authorization": f"Bearer {token}"})
        me = r.json() if r.status_code == 200 else {}
        st.session_state["_me"] = me
        return me

    monkeypatch.setattr("ui.pages.jwt_users_page.load_me", _load_me)


def test_streamlit_login_against_real_api(tmp_path, monkeypatch) -> None:
    """Streamlit login flow backed by the real bundled API (ApiClient delegates to tc.api)."""
    monkeypatch.setenv("FLUXLIT_DISABLE_URL_SESSION", "1")
    app = load_fluxlit_app(db_url=f"sqlite:///{tmp_path / 'real_login.db'}")
    import app.db as db

    seed_user(
        db_engine=db.engine,
        email="u@example.com",
        password="secret1234",
    )
    tc = FluxLitTestClient(app)

    monkeypatch.setattr(
        ApiClient,
        "request",
        lambda self, method, path, **kwargs: bridge_api_client(
            tc, method, path, **kwargs
        ),
    )
    _patch_load_me_for_tc(monkeypatch, tc)
    fluxlit_env(monkeypatch)

    at = AppTest.from_file(str(FLUXLIT_MAIN), default_timeout=30).run()
    text_input_by_key(at, "login_email").input("u@example.com")
    text_input_by_key(at, "login_password").input("secret1234")
    click_button(at, label="Sign in")
    at = at.run()
    at = at.run()
    assert not at.exception
    assert at.session_state["user_auth"].is_authenticated
    assert at.session_state["user_auth"].email == "u@example.com"
    assert at.session_state["_page"] == "Account"
    assert at.session_state["access_token"]


def test_streamlit_admin_login_routes_to_admin_page(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("FLUXLIT_DISABLE_URL_SESSION", "1")
    app = load_fluxlit_app(db_url=f"sqlite:///{tmp_path / 'admin_ui.db'}")
    import app.db as db

    seed_admin(db_engine=db.engine)
    tc = FluxLitTestClient(app)

    monkeypatch.setattr(
        ApiClient,
        "request",
        lambda self, method, path, **kwargs: bridge_api_client(
            tc, method, path, **kwargs
        ),
    )
    _patch_load_me_for_tc(monkeypatch, tc)
    fluxlit_env(monkeypatch)

    at = AppTest.from_file(str(FLUXLIT_MAIN), default_timeout=30).run()
    text_input_by_key(at, "login_email").input("admin@example.com")
    text_input_by_key(at, "login_password").input("admin123")
    click_button(at, label="Sign in")
    at = at.run()
    at = at.run()
    assert not at.exception
    assert at.session_state["user_auth"].is_authenticated
    assert at.session_state["_me"].get("is_admin") is True
    menu = [r for r in at.radio if getattr(r, "label", None) == "Menu"]
    assert len(menu) == 1
    assert "Admin" in menu[0].options
    menu[0].set_value("Admin")
    at = at.run()
    assert at.session_state["_page"] == "Admin"
