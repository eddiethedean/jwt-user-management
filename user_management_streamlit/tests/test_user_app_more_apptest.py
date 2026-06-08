import httpx

from apptest_helpers import (
    FakeHttpxResponse,
    click_button,
    new_app_test,
    set_public_page,
    text_input_by_key,
)


def test_login_invalid_credentials_shows_error(monkeypatch):
    def fake_post(url, data=None, headers=None, timeout=None, params=None, json=None):
        if url.endswith("/auth/token"):
            return FakeHttpxResponse(
                ok=False,
                status_code=400,
                json_data={"detail": "Incorrect email or password"},
            )
        return FakeHttpxResponse(ok=True, json_data={"ok": True})

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeHttpxResponse(ok=True, json_data={}))

    at = new_app_test().run()
    text_input_by_key(at, "login_email").input("bad@test.local")
    text_input_by_key(at, "login_password").input("wrong")
    click_button(at, "Sign in")
    at.run()

    assert not at.exception
    assert len(at.error) >= 1
    assert "invalid email or password" in at.error[0].value.lower()
    if "user_auth" in at.session_state:
        assert not at.session_state["user_auth"].is_authenticated


def test_sign_out_clears_auth_state(monkeypatch):
    def fake_post(url, data=None, headers=None, timeout=None, params=None, json=None):
        if url.endswith("/auth/token"):
            return FakeHttpxResponse(
                ok=True, json_data={"access_token": "tok", "token_type": "bearer"}
            )
        return FakeHttpxResponse(ok=True, json_data={"ok": True})

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeHttpxResponse(ok=True, json_data={}))

    at = new_app_test().run()
    text_input_by_key(at, "login_email").input("user@test.local")
    text_input_by_key(at, "login_password").input("pw")
    click_button(at, "Sign in")
    at.run()
    assert "user_auth" in at.session_state
    assert at.session_state["user_auth"].is_authenticated

    click_button(at, "Sign out")
    at.run()
    if "user_auth" in at.session_state:
        assert not at.session_state["user_auth"].is_authenticated
    assert "access_token" not in at.session_state


def test_forgot_password_shows_error_when_backend_fails(monkeypatch):
    def fake_post(url, data=None, headers=None, timeout=None, params=None, json=None):
        if url.endswith("/password/forgot"):
            return FakeHttpxResponse(
                ok=False, status_code=503, text="service unavailable"
            )
        return FakeHttpxResponse(ok=True, json_data={"ok": True})

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeHttpxResponse(ok=True, json_data={}))

    at = new_app_test().run()
    set_public_page(at, "Reset password")
    at.run()
    text_input_by_key(at, "forgot_email").input("user@test.local")
    click_button(at, "Send reset link")
    at.run()

    assert len(at.error) >= 1
    assert "failed" in at.error[0].value.lower()
