"""
End-to-end Streamlit AppTest coverage for the FluxLit JWT user management UI.

Complements ``test_streamlit_fluxlit_apptest.py`` and ``test_streamlit_fluxlit_more.py`` by
exercising navigation, public flows (register, invite, reset), and authenticated screens.
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from fluxlit.client import ApiClient
import fluxlit.testing as _fluxlit_testing

_REPO = Path(__file__).resolve().parents[2]
_FLUX = _REPO / "fluxlit_app"
_FLUXLIT_MAIN = (
    Path(_fluxlit_testing.__file__).resolve().parent / "streamlit" / "main.py"
)


@pytest.fixture(autouse=True)
def _paths_and_env(tmp_path, monkeypatch):
    for p in (str(_FLUX),):
        if p not in sys.path:
            sys.path.insert(0, p)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/func.db")
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("FLUXLIT_DISABLE_URL_SESSION", "1")
    for k in ("DIRECTORY_LOOKUP_URL", "DIRECTORY_LOOKUP_REQUIRED"):
        monkeypatch.delenv(k, raising=False)
    for mod in (
        "main",
        "fluxlit_gateway",
        "api_backend",
        "paths",
        "streamlit_ui",
        "auth_state",
        "ui_helpers",
    ):
        sys.modules.pop(mod, None)
    for k in list(sys.modules.keys()):
        if k == "ui" or k.startswith("ui."):
            sys.modules.pop(k, None)
    yield


def _fluxlit_env(monkeypatch):
    monkeypatch.setenv("FLUXLIT_APP", "main:app")
    monkeypatch.setenv("FLUXLIT_INTERNAL_API_BASE", "http://testserver/api")
    monkeypatch.setenv("FLUXLIT_API_PREFIX", "/api")


def _text_input_by_key(at: AppTest, key: str):
    matches = [t for t in at.text_input if getattr(t, "key", None) == key]
    if not matches:
        raise AssertionError(f"Text input not found for key={key!r}")
    return matches[0]


def _text_input_by_label_contains(at: AppTest, fragment: str):
    for t in at.text_input:
        lab = getattr(t, "label", None) or ""
        if fragment in lab:
            return t
    raise AssertionError(f"No text_input with label containing {fragment!r}")


def _click_button(at: AppTest, label: str) -> None:
    for b in at.button:
        if getattr(b, "label", None) == label or getattr(b, "value", None) == label:
            b.click()
            return
    raise AssertionError(f"Button not found: {label!r}")


def _set_public_page(at: AppTest, page: str) -> None:
    matches = [r for r in at.radio if getattr(r, "label", None) == "Menu"]
    if not matches:
        raise AssertionError("Public Menu radio not found")
    matches[0].set_value(page)


def _set_authed_page(at: AppTest, page: str) -> None:
    for r in at.radio:
        if getattr(r, "key", None) == "authed_nav_radio":
            r.set_value(page)
            return
    raise AssertionError("authed_nav_radio not found")


def _patch_api_client(monkeypatch, fake_request):
    monkeypatch.setattr(ApiClient, "request", fake_request)


def _run_app() -> AppTest:
    return AppTest.from_file(str(_FLUXLIT_MAIN), default_timeout=30).run()


def test_public_menu_navigate_to_register_shows_register_ui(monkeypatch):
    def fake_request(self, method: str, path: str, **kwargs):
        p = path if path.startswith("/") else f"/{path}"
        if method == "GET" and "/__meta" in p:
            return httpx.Response(200, json={"ok": True, "external_api_base": ""})
        return httpx.Response(200, json={})

    _patch_api_client(monkeypatch, fake_request)
    _fluxlit_env(monkeypatch)

    at = _run_app()
    assert not at.exception
    _set_public_page(at, "Register")
    at = at.run()
    assert not at.exception
    assert any("register" in s.value.lower() for s in at.subheader)


def test_public_menu_navigate_to_accept_invite_shows_ui(monkeypatch):
    def fake_request(self, method: str, path: str, **kwargs):
        p = path if path.startswith("/") else f"/{path}"
        if method == "GET" and "/__meta" in p:
            return httpx.Response(200, json={"ok": True, "external_api_base": ""})
        return httpx.Response(200, json={})

    _patch_api_client(monkeypatch, fake_request)
    _fluxlit_env(monkeypatch)

    at = _run_app()
    _set_public_page(at, "Accept invite")
    at = at.run()
    assert not at.exception
    assert any("accept invite" in s.value.lower() for s in at.subheader)


def test_invite_link_query_prefills_token(monkeypatch):
    def fake_request(self, method: str, path: str, **kwargs):
        p = path if path.startswith("/") else f"/{path}"
        if method == "GET" and "/__meta" in p:
            return httpx.Response(200, json={"ok": True, "external_api_base": ""})
        return httpx.Response(200, json={})

    _patch_api_client(monkeypatch, fake_request)
    _fluxlit_env(monkeypatch)

    at = AppTest.from_file(str(_FLUXLIT_MAIN), default_timeout=30)
    at.query_params["page"] = "Accept invite"
    at.query_params["token"] = "raw-token-xyz"
    at = at.run()

    assert not at.exception
    assert _text_input_by_key(at, "invite_token").value == "raw-token-xyz"


def test_public_menu_navigate_to_reset_password_shows_ui(monkeypatch):
    def fake_request(self, method: str, path: str, **kwargs):
        p = path if path.startswith("/") else f"/{path}"
        if method == "GET" and "/__meta" in p:
            return httpx.Response(200, json={"ok": True, "external_api_base": ""})
        return httpx.Response(200, json={})

    _patch_api_client(monkeypatch, fake_request)
    _fluxlit_env(monkeypatch)

    at = _run_app()
    _set_public_page(at, "Reset password")
    at = at.run()
    assert not at.exception
    assert any("forgot password" in s.value.lower() for s in at.subheader)
    assert any("reset password" in s.value.lower() for s in at.subheader)


def test_reset_link_query_prefills_token(monkeypatch):
    def fake_request(self, method: str, path: str, **kwargs):
        p = path if path.startswith("/") else f"/{path}"
        if method == "GET" and "/__meta" in p:
            return httpx.Response(200, json={"ok": True, "external_api_base": ""})
        return httpx.Response(200, json={})

    _patch_api_client(monkeypatch, fake_request)
    _fluxlit_env(monkeypatch)

    at = AppTest.from_file(str(_FLUXLIT_MAIN), default_timeout=30)
    at.query_params["page"] = "Reset password"
    at.query_params["token"] = "reset-token-abc"
    at = at.run()

    assert not at.exception
    assert _text_input_by_key(at, "reset_token").value == "reset-token-abc"


def test_register_request_setup_link_success(monkeypatch):
    def fake_request(self, method: str, path: str, **kwargs):
        p = path if path.startswith("/") else f"/{path}"
        if method == "GET" and "/__meta" in p:
            return httpx.Response(200, json={"ok": True, "external_api_base": ""})
        if method == "POST" and "/register" in p:
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(404, json={"detail": "unexpected"})

    _patch_api_client(monkeypatch, fake_request)
    _fluxlit_env(monkeypatch)

    at = _run_app()
    _set_public_page(at, "Register")
    at = at.run()
    _text_input_by_key(at, "register_email").input("newuser@example.com")
    _click_button(at, "Request setup link")
    at = at.run()
    assert not at.exception
    assert any("setup link" in s.value.lower() for s in at.success)


def test_register_failure_shows_error(monkeypatch):
    def fake_request(self, method: str, path: str, **kwargs):
        p = path if path.startswith("/") else f"/{path}"
        if method == "GET" and "/__meta" in p:
            return httpx.Response(200, json={"ok": True, "external_api_base": ""})
        if method == "POST" and "/register" in p:
            return httpx.Response(400, json={"detail": "Email already exists"})
        return httpx.Response(404, json={"detail": "unexpected"})

    _patch_api_client(monkeypatch, fake_request)
    _fluxlit_env(monkeypatch)

    at = _run_app()
    _set_public_page(at, "Register")
    at = at.run()
    _text_input_by_key(at, "register_email").input("taken@example.com")
    _click_button(at, "Request setup link")
    at = at.run()
    assert not at.exception
    assert len(at.error) >= 1


def test_accept_invite_lookup_then_accept_success(monkeypatch):
    def fake_request(self, method: str, path: str, **kwargs):
        p = path if path.startswith("/") else f"/{path}"
        if method == "GET" and "/__meta" in p:
            return httpx.Response(200, json={"ok": True, "external_api_base": ""})
        if method == "POST" and "/invites/inspect" in p:
            return httpx.Response(
                200, json={"email": "invited@example.com", "ok": True}
            )
        if method == "POST" and "/invites/accept" in p:
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(404, json={"detail": "unexpected"})

    _patch_api_client(monkeypatch, fake_request)
    _fluxlit_env(monkeypatch)

    at = _run_app()
    _set_public_page(at, "Accept invite")
    at = at.run()
    _text_input_by_key(at, "invite_token").input("raw-token-xyz")
    _click_button(at, "Lookup invite")
    at = at.run()
    assert not at.exception
    assert any("invited@example.com" in c.value for c in at.caption)

    _text_input_by_key(at, "invite_password").input("newpassword1")
    _click_button(at, "Accept invite")
    at = at.run()
    assert not at.exception
    assert any("invite accepted" in s.value.lower() for s in at.success)


def test_accept_invite_lookup_not_found_shows_error(monkeypatch):
    def fake_request(self, method: str, path: str, **kwargs):
        p = path if path.startswith("/") else f"/{path}"
        if method == "GET" and "/__meta" in p:
            return httpx.Response(200, json={"ok": True, "external_api_base": ""})
        if method == "POST" and "/invites/inspect" in p:
            return httpx.Response(404, json={"detail": "bad token"})
        return httpx.Response(404, json={"detail": "unexpected"})

    _patch_api_client(monkeypatch, fake_request)
    _fluxlit_env(monkeypatch)

    at = _run_app()
    _set_public_page(at, "Accept invite")
    at = at.run()
    _text_input_by_key(at, "invite_token").input("bad")
    _click_button(at, "Lookup invite")
    at = at.run()
    assert not at.exception
    assert len(at.error) >= 1


def test_reset_password_forgot_success(monkeypatch):
    def fake_request(self, method: str, path: str, **kwargs):
        p = path if path.startswith("/") else f"/{path}"
        if method == "GET" and "/__meta" in p:
            return httpx.Response(200, json={"ok": True, "external_api_base": ""})
        if method == "POST" and "/password/forgot" in p:
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(404, json={"detail": "unexpected"})

    _patch_api_client(monkeypatch, fake_request)
    _fluxlit_env(monkeypatch)

    at = _run_app()
    _set_public_page(at, "Reset password")
    at = at.run()
    _text_input_by_key(at, "forgot_email").input("user@example.com")
    _click_button(at, "Send reset link")
    at = at.run()
    assert not at.exception
    assert any("reset email has been sent" in s.value.lower() for s in at.success)


def test_reset_password_inspect_then_reset_success(monkeypatch):
    def fake_request(self, method: str, path: str, **kwargs):
        p = path if path.startswith("/") else f"/{path}"
        if method == "GET" and "/__meta" in p:
            return httpx.Response(200, json={"ok": True, "external_api_base": ""})
        if method == "POST" and "/password/inspect" in p:
            return httpx.Response(200, json={"email": "user@example.com", "ok": True})
        if method == "POST" and "/password/reset" in p:
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(404, json={"detail": "unexpected"})

    _patch_api_client(monkeypatch, fake_request)
    _fluxlit_env(monkeypatch)

    at = _run_app()
    _set_public_page(at, "Reset password")
    at = at.run()
    _text_input_by_key(at, "reset_token").input("tok-abc")
    _click_button(at, "Lookup reset link")
    at = at.run()
    assert not at.exception
    assert any("user@example.com" in c.value for c in at.caption)

    _text_input_by_key(at, "reset_new_password").input("brandnewpw1")
    _click_button(at, "Reset password")
    at = at.run()
    assert not at.exception
    assert any("password updated" in s.value.lower() for s in at.success)


def _login(
    at: AppTest, *, email: str, pw: str, country: str, is_admin: bool
) -> AppTest:
    _text_input_by_key(at, "login_email").input(email)
    _text_input_by_key(at, "login_password").input(pw)
    _click_button(at, "Login")
    return at.run()


def test_after_login_non_admin_menu_excludes_admin(monkeypatch):
    def fake_request(self, method: str, path: str, **kwargs):
        p = path if path.startswith("/") else f"/{path}"
        if method == "GET" and "/__meta" in p:
            return httpx.Response(200, json={"ok": True, "external_api_base": ""})
        if method == "POST" and "/auth/token" in p:
            return httpx.Response(
                200, json={"access_token": "tok", "token_type": "bearer"}
            )
        if method == "GET" and "/users/me" in p:
            return httpx.Response(
                200,
                json={
                    "email": "u@test.local",
                    "country": "US",
                    "is_admin": False,
                    "full_name": "Pat",
                },
            )
        return httpx.Response(200, json={})

    _patch_api_client(monkeypatch, fake_request)
    _fluxlit_env(monkeypatch)

    at = _run_app()
    at = _login(at, email="u@test.local", pw="pw", country="US", is_admin=False)
    assert not at.exception
    nav = [r for r in at.radio if getattr(r, "key", None) == "authed_nav_radio"]
    assert len(nav) == 1
    assert "Admin" not in nav[0].options


def test_after_login_admin_menu_includes_admin(monkeypatch):
    def fake_request(self, method: str, path: str, **kwargs):
        p = path if path.startswith("/") else f"/{path}"
        if method == "GET" and "/__meta" in p:
            return httpx.Response(200, json={"ok": True, "external_api_base": ""})
        if method == "POST" and "/auth/token" in p:
            return httpx.Response(
                200, json={"access_token": "adm", "token_type": "bearer"}
            )
        if method == "GET" and "/users/me" in p:
            return httpx.Response(
                200,
                json={
                    "email": "admin@test.local",
                    "country": "CA",
                    "is_admin": True,
                    "full_name": "Root",
                },
            )
        return httpx.Response(200, json={})

    _patch_api_client(monkeypatch, fake_request)
    _fluxlit_env(monkeypatch)

    at = _run_app()
    at = _login(at, email="admin@test.local", pw="pw", country="CA", is_admin=True)
    assert not at.exception
    nav = [r for r in at.radio if getattr(r, "key", None) == "authed_nav_radio"]
    assert "Admin" in nav[0].options


def test_public_menu_navigate_back_to_login(monkeypatch):
    def fake_request(self, method: str, path: str, **kwargs):
        p = path if path.startswith("/") else f"/{path}"
        if method == "GET" and "/__meta" in p:
            return httpx.Response(200, json={"ok": True, "external_api_base": ""})
        return httpx.Response(200, json={})

    _patch_api_client(monkeypatch, fake_request)
    _fluxlit_env(monkeypatch)

    at = _run_app()
    _set_public_page(at, "Register")
    at = at.run()
    _set_public_page(at, "Login")
    at = at.run()
    assert not at.exception
    assert any("login to app" in s.value.lower() for s in at.subheader)


def test_account_save_full_name_success(monkeypatch):
    def fake_request(self, method: str, path: str, **kwargs):
        p = path if path.startswith("/") else f"/{path}"
        if method == "GET" and "/__meta" in p:
            return httpx.Response(200, json={"ok": True, "external_api_base": ""})
        if method == "POST" and "/auth/token" in p:
            return httpx.Response(
                200, json={"access_token": "tok", "token_type": "bearer"}
            )
        if method == "GET" and "/users/me" in p:
            return httpx.Response(
                200,
                json={
                    "email": "acct@test.local",
                    "country": "DE",
                    "is_admin": False,
                    "full_name": "Old",
                },
            )
        if method == "PATCH" and "/users/me" in p:
            return httpx.Response(200, json={"ok": True, "full_name": "New Name"})
        return httpx.Response(404, json={"detail": "unexpected"})

    _patch_api_client(monkeypatch, fake_request)
    _fluxlit_env(monkeypatch)

    at = _run_app()
    at = _login(at, email="acct@test.local", pw="pw", country="DE", is_admin=False)
    _set_authed_page(at, "Account")
    at = at.run()
    assert not at.exception

    _text_input_by_label_contains(at, "Full name (optional)").set_value("New Name")
    _click_button(at, "Save")
    at = at.run()
    assert not at.exception
    assert any("saved" in s.value.lower() for s in at.success)


def test_account_save_full_name_api_error(monkeypatch):
    def fake_request(self, method: str, path: str, **kwargs):
        p = path if path.startswith("/") else f"/{path}"
        if method == "GET" and "/__meta" in p:
            return httpx.Response(200, json={"ok": True, "external_api_base": ""})
        if method == "POST" and "/auth/token" in p:
            return httpx.Response(
                200, json={"access_token": "tok", "token_type": "bearer"}
            )
        if method == "GET" and "/users/me" in p:
            return httpx.Response(
                200,
                json={
                    "email": "e@test.local",
                    "country": "DE",
                    "is_admin": False,
                    "full_name": "X",
                },
            )
        if method == "PATCH" and "/users/me" in p:
            return httpx.Response(400, json={"detail": "not allowed"})
        return httpx.Response(404, json={"detail": "unexpected"})

    _patch_api_client(monkeypatch, fake_request)
    _fluxlit_env(monkeypatch)

    at = _run_app()
    at = _login(at, email="e@test.local", pw="pw", country="DE", is_admin=False)
    _set_authed_page(at, "Account")
    at = at.run()
    _text_input_by_label_contains(at, "Full name (optional)").set_value("Y")
    _click_button(at, "Save")
    at = at.run()
    assert not at.exception
    assert len(at.error) >= 1


def test_account_change_password_success(monkeypatch):
    def fake_request(self, method: str, path: str, **kwargs):
        p = path if path.startswith("/") else f"/{path}"
        if method == "GET" and "/__meta" in p:
            return httpx.Response(200, json={"ok": True, "external_api_base": ""})
        if method == "POST" and "/auth/token" in p:
            return httpx.Response(
                200, json={"access_token": "tok", "token_type": "bearer"}
            )
        if method == "GET" and "/users/me" in p:
            return httpx.Response(
                200,
                json={
                    "email": "pw@test.local",
                    "country": "FR",
                    "is_admin": False,
                    "full_name": "",
                },
            )
        if method == "POST" and "/users/me/password" in p:
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(404, json={"detail": "unexpected"})

    _patch_api_client(monkeypatch, fake_request)
    _fluxlit_env(monkeypatch)

    at = _run_app()
    at = _login(at, email="pw@test.local", pw="oldpw", country="FR", is_admin=False)
    _set_authed_page(at, "Account")
    at = at.run()

    for t in at.text_input:
        lab = getattr(t, "label", None) or ""
        if lab == "Current password":
            t.input("oldpw")
        elif lab == "New password":
            t.input("newpass1234")
        elif lab == "Confirm new password":
            t.input("newpass1234")
    _click_button(at, "Update password")
    at = at.run()
    assert not at.exception
    assert any("password updated" in s.value.lower() for s in at.success)


def test_account_change_password_api_error(monkeypatch):
    def fake_request(self, method: str, path: str, **kwargs):
        p = path if path.startswith("/") else f"/{path}"
        if method == "GET" and "/__meta" in p:
            return httpx.Response(200, json={"ok": True, "external_api_base": ""})
        if method == "POST" and "/auth/token" in p:
            return httpx.Response(
                200, json={"access_token": "tok", "token_type": "bearer"}
            )
        if method == "GET" and "/users/me" in p:
            return httpx.Response(
                200,
                json={
                    "email": "e2@test.local",
                    "country": "FR",
                    "is_admin": False,
                    "full_name": "",
                },
            )
        if method == "POST" and "/users/me/password" in p:
            return httpx.Response(400, json={"detail": "Current password is incorrect"})
        return httpx.Response(404, json={"detail": "unexpected"})

    _patch_api_client(monkeypatch, fake_request)
    _fluxlit_env(monkeypatch)

    at = _run_app()
    at = _login(at, email="e2@test.local", pw="pw", country="FR", is_admin=False)
    _set_authed_page(at, "Account")
    at = at.run()
    for t in at.text_input:
        lab = getattr(t, "label", None) or ""
        if lab == "Current password":
            t.input("wrong")
        elif lab == "New password":
            t.input("newpass1234")
        elif lab == "Confirm new password":
            t.input("newpass1234")
    _click_button(at, "Update password")
    at = at.run()
    assert not at.exception
    assert len(at.error) >= 1


def test_users_refresh_loads_list_and_shows_dataframe(monkeypatch):
    row = {
        "id": 1,
        "email": "a@b.c",
        "full_name": "A",
        "country": "US",
        "is_active": True,
        "is_admin": False,
        "created_at": "2020-01-01T00:00:00",
    }

    def fake_request(self, method: str, path: str, **kwargs):
        p = path if path.startswith("/") else f"/{path}"
        if method == "GET" and "/__meta" in p:
            return httpx.Response(200, json={"ok": True, "external_api_base": ""})
        if method == "POST" and "/auth/token" in p:
            return httpx.Response(
                200, json={"access_token": "tok", "token_type": "bearer"}
            )
        if method == "GET" and "/users/me" in p:
            return httpx.Response(
                200,
                json={
                    "email": "viewer@test.local",
                    "country": "US",
                    "is_admin": False,
                    "full_name": "",
                },
            )
        if method == "GET" and "/users" in p and "/users/me" not in p:
            return httpx.Response(200, json=[row])
        return httpx.Response(404, json={"detail": "unexpected"})

    _patch_api_client(monkeypatch, fake_request)
    _fluxlit_env(monkeypatch)

    at = _run_app()
    at = _login(at, email="viewer@test.local", pw="pw", country="US", is_admin=False)
    _set_authed_page(at, "Users")
    at = at.run()
    _click_button(at, "Refresh users")
    at = at.run()
    assert not at.exception
    assert len(at.dataframe) >= 1


def test_users_refresh_backend_error_shows_message(monkeypatch):
    def fake_request(self, method: str, path: str, **kwargs):
        p = path if path.startswith("/") else f"/{path}"
        if method == "GET" and "/__meta" in p:
            return httpx.Response(200, json={"ok": True, "external_api_base": ""})
        if method == "POST" and "/auth/token" in p:
            return httpx.Response(
                200, json={"access_token": "tok", "token_type": "bearer"}
            )
        if method == "GET" and "/users/me" in p:
            return httpx.Response(
                200,
                json={
                    "email": "v2@test.local",
                    "country": "US",
                    "is_admin": False,
                    "full_name": "",
                },
            )
        if method == "GET" and "/users" in p and "/users/me" not in p:
            return httpx.Response(503, text="down")
        return httpx.Response(404, json={"detail": "unexpected"})

    _patch_api_client(monkeypatch, fake_request)
    _fluxlit_env(monkeypatch)

    at = _run_app()
    at = _login(at, email="v2@test.local", pw="pw", country="US", is_admin=False)
    _set_authed_page(at, "Users")
    at = at.run()
    _click_button(at, "Refresh users")
    at = at.run()
    assert not at.exception
    assert len(at.error) >= 1


def test_admin_create_invite_success(monkeypatch):
    def fake_request(self, method: str, path: str, **kwargs):
        p = path if path.startswith("/") else f"/{path}"
        if method == "GET" and "/__meta" in p:
            return httpx.Response(200, json={"ok": True, "external_api_base": ""})
        if method == "POST" and "/auth/token" in p:
            return httpx.Response(
                200, json={"access_token": "adm", "token_type": "bearer"}
            )
        if method == "GET" and "/users/me" in p:
            return httpx.Response(
                200,
                json={
                    "email": "admin@test.local",
                    "country": "US",
                    "is_admin": True,
                    "full_name": "",
                },
            )
        if method == "POST" and "/invites/lookup" in p:
            return httpx.Response(200, json={"ok": True})
        if method == "POST" and p.rstrip("/").endswith("/invites"):
            return httpx.Response(
                200,
                json={"ok": True, "invite_url": "https://example.com/invite"},
            )
        if method == "GET" and "/users" in p and "/users/me" not in p:
            return httpx.Response(200, json=[])
        return httpx.Response(404, json={"detail": "unexpected"})

    _patch_api_client(monkeypatch, fake_request)
    _fluxlit_env(monkeypatch)

    at = _run_app()
    at = _login(at, email="admin@test.local", pw="pw", country="US", is_admin=True)
    _set_authed_page(at, "Admin")
    at = at.run()
    assert not at.exception

    _text_input_by_label_contains(at, "Invite email").input("invitee@example.com")
    _click_button(at, "Create invite")
    at = at.run()
    assert not at.exception
    assert any("invite created" in s.value.lower() for s in at.success)


def test_admin_invite_lookup_soft_failure_still_creates_invite(monkeypatch):
    """Directory preview may be empty; admin invite should still be attempted."""

    def fake_request(self, method: str, path: str, **kwargs):
        p = path if path.startswith("/") else f"/{path}"
        if method == "GET" and "/__meta" in p:
            return httpx.Response(200, json={"ok": True, "external_api_base": ""})
        if method == "POST" and "/auth/token" in p:
            return httpx.Response(
                200, json={"access_token": "adm", "token_type": "bearer"}
            )
        if method == "GET" and "/users/me" in p:
            return httpx.Response(
                200,
                json={
                    "email": "admin@test.local",
                    "country": "US",
                    "is_admin": True,
                    "full_name": "",
                },
            )
        if method == "POST" and "/invites/lookup" in p:
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "email": "",
                    "country": "",
                    "display_name": "",
                },
            )
        if method == "POST" and p.rstrip("/").endswith("/invites"):
            return httpx.Response(
                200,
                json={"ok": True, "invite_url": "https://example.com/invite"},
            )
        if method == "GET" and "/users" in p and "/users/me" not in p:
            return httpx.Response(200, json=[])
        return httpx.Response(404, json={"detail": "unexpected"})

    _patch_api_client(monkeypatch, fake_request)
    _fluxlit_env(monkeypatch)

    at = _run_app()
    at = _login(at, email="admin@test.local", pw="pw", country="US", is_admin=True)
    _set_authed_page(at, "Admin")
    at = at.run()
    _text_input_by_label_contains(at, "Invite email").input("bad@example.com")
    _click_button(at, "Create invite")
    at = at.run()
    assert not at.exception
    assert any("invite created" in s.value.lower() for s in at.success)
