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

from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
from fluxlit.client import ApiClient
from fluxlit.testing import FluxLitTestClient
from sqlmodel import Session
from starlette.testclient import TestClient

from conftest import load_fluxlit_app

_FLUX_APP_ROOT = Path(__file__).resolve().parents[1]


def _seed_user(
    *,
    db_engine,
    email: str,
    password: str,
    is_admin: bool = False,
    is_active: bool = True,
) -> int:
    from app.core.security import hash_password
    from app.models import User

    with Session(db_engine) as s:
        u = User(
            email=email,
            hashed_password=hash_password(password),
            is_admin=is_admin,
            is_active=is_active,
            created_at=datetime.now(timezone.utc),
        )
        s.add(u)
        s.commit()
        s.refresh(u)
        return int(u.id or 0)


def _text_input_by_key(at, key: str):
    matches = [t for t in at.text_input if getattr(t, "key", None) == key]
    if not matches:
        raise AssertionError(f"Text input not found for key={key!r}")
    return matches[0]


def _click_button(at, label: str) -> None:
    for b in at.button:
        if getattr(b, "label", None) == label or getattr(b, "value", None) == label:
            b.click()
            return
    raise AssertionError(f"Button not found: {label!r}")


@pytest.fixture
def _patch_api_client(monkeypatch):
    def _install(handler):
        monkeypatch.setattr(ApiClient, "request", handler)

    return _install


# --- FluxLitTestClient: gateway / OpenAPI ---


def test_fluxlit_test_client_api_is_starlette_test_client(tmp_path) -> None:
    app = load_fluxlit_app(db_url=f"sqlite:///{tmp_path / 'tc.db'}")
    tc = FluxLitTestClient(app)
    assert isinstance(tc.api, TestClient)


def test_fluxlit_test_client_api_prefix_default(tmp_path) -> None:
    app = load_fluxlit_app(db_url=f"sqlite:///{tmp_path / 'pfx.db'}")
    tc = FluxLitTestClient(app)
    assert tc.api_prefix == "/api"


def test_fluxlit_test_client_openapi_has_service_title(tmp_path) -> None:
    app = load_fluxlit_app(db_url=f"sqlite:///{tmp_path / 'ti.db'}")
    tc = FluxLitTestClient(app)
    info = tc.openapi().get("info") or {}
    assert isinstance(info, dict)
    assert "title" in info


def test_fluxlit_test_client_openapi_lists_user_routes(tmp_path) -> None:
    app = load_fluxlit_app(db_url=f"sqlite:///{tmp_path / 'o.db'}")
    tc = FluxLitTestClient(app)
    spec = tc.openapi()
    paths = spec.get("paths") or {}
    assert isinstance(paths, dict)
    assert any("/users/me" in p for p in paths)
    assert any("/auth/token" in p for p in paths)


def test_fluxlit_test_client_openapi_method_matches_raw_get(tmp_path) -> None:
    app = load_fluxlit_app(db_url=f"sqlite:///{tmp_path / 'o2.db'}")
    tc = FluxLitTestClient(app)
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

    _seed_user(
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

    _seed_user(
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


def test_fluxlit_test_client_register_rejects_duplicate_email(tmp_path) -> None:
    app = load_fluxlit_app(db_url=f"sqlite:///{tmp_path / 'reg.db'}")
    import app.db as db

    _seed_user(db_engine=db.engine, email="dup@example.com", password="x")
    tc = FluxLitTestClient(app)
    r = tc.api_post("/register", data={"email": "dup@example.com"})
    assert r.status_code == 400


def test_fluxlit_test_client_register_creates_invite_for_new_email(tmp_path) -> None:
    app = load_fluxlit_app(db_url=f"sqlite:///{tmp_path / 'reg2.db'}")
    tc = FluxLitTestClient(app)
    r = tc.api_post("/register", data={"email": "fresh@example.com"})
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    assert body.get("setup_url")
    assert "/?page=Accept+invite&token=" in body["setup_url"]
    assert body.get("email_sent") is False


def test_fluxlit_test_client_bearer_users_me(tmp_path) -> None:
    app = load_fluxlit_app(db_url=f"sqlite:///{tmp_path / 'me.db'}")
    import app.db as db

    _seed_user(
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

    uid = _seed_user(
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

    _seed_user(
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

    uid = _seed_user(
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


def test_fluxlit_streamlit_smoke_via_test_client(
    tmp_path, monkeypatch, _patch_api_client
):
    monkeypatch.setenv("FLUXLIT_DISABLE_URL_SESSION", "1")
    _patch_api_client(
        lambda *a, **k: httpx.Response(200, json={"ok": True, "external_api_base": ""})
    )
    app = load_fluxlit_app(db_url=f"sqlite:///{tmp_path / 'st.db'}")
    tc = FluxLitTestClient(app)
    at = tc.streamlit(
        target="main:app",
        internal_api_base="http://testserver/api",
        extra_sys_path=_FLUX_APP_ROOT,
    )
    assert not at.exception
    assert any("user management" in t.value.lower() for t in at.title)


def test_fluxlit_streamlit_internal_api_base_wiring_via_test_client(
    tmp_path, monkeypatch, _patch_api_client
):
    monkeypatch.setenv("FLUXLIT_DISABLE_URL_SESSION", "1")
    _patch_api_client(
        lambda *a, **k: httpx.Response(200, json={"ok": True, "external_api_base": ""})
    )
    app = load_fluxlit_app(db_url=f"sqlite:///{tmp_path / 'stib.db'}")
    tc = FluxLitTestClient(app)
    at = tc.streamlit(
        target="main:app",
        internal_api_base="http://127.0.0.1:59999/api",
        extra_sys_path=_FLUX_APP_ROOT,
    )
    assert not at.exception


def test_fluxlit_streamlit_invalid_login_shows_error_via_test_client(
    tmp_path, monkeypatch, _patch_api_client
):
    monkeypatch.setenv("FLUXLIT_DISABLE_URL_SESSION", "1")

    def handler(self, method: str, path: str, **kwargs):
        p = path if path.startswith("/") else f"/{path}"
        if method == "GET" and "/__meta" in p:
            return httpx.Response(200, json={"ok": True, "external_api_base": ""})
        if method == "POST" and "/auth/token" in p:
            return httpx.Response(401, json={"detail": "nope"})
        return httpx.Response(200, json={})

    _patch_api_client(handler)
    app = load_fluxlit_app(db_url=f"sqlite:///{tmp_path / 'st8.db'}")
    tc = FluxLitTestClient(app)
    at = tc.streamlit(
        target="main:app",
        internal_api_base="http://testserver/api",
        extra_sys_path=_FLUX_APP_ROOT,
    )

    _text_input_by_key(at, "login_email").input("bad@test.local")
    _text_input_by_key(at, "login_password").input("pw")
    _click_button(at, "Login")
    at = at.run()
    assert not at.exception
    assert len(at.error) >= 1
