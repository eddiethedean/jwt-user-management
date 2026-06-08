import httpx

from apptest_helpers import (
    FakeHttpxResponse,
    click_button,
    new_app_test,
    set_public_page,
    text_input_by_key,
)


def test_login_success_sets_session(monkeypatch):
    def fake_post(url, data=None, headers=None, timeout=None, params=None, json=None):
        if url.endswith("/auth/token"):
            return FakeHttpxResponse(
                ok=True, json_data={"access_token": "tok", "token_type": "bearer"}
            )
        return FakeHttpxResponse(ok=True, json_data={"ok": True})

    monkeypatch.setattr(httpx, "post", fake_post)

    def fake_get(url, params=None, headers=None, timeout=None):
        if url.endswith("/users/me"):
            return FakeHttpxResponse(ok=True, json_data={"country": "US"})
        return FakeHttpxResponse(ok=True, json_data={})

    monkeypatch.setattr(httpx, "get", fake_get)

    at = new_app_test().run()
    assert not at.exception

    text_input_by_key(at, "login_email").input("user@test.local")
    text_input_by_key(at, "login_password").input("pw")
    click_button(at, "Sign in")
    at.run()
    assert not at.exception

    assert "user_auth" in at.session_state
    auth = at.session_state["user_auth"]
    assert auth.is_authenticated
    assert auth.access_token == "tok"
    assert any("signed in" in s.value.lower() for s in at.success)
    assert any("(US)" in c.value for c in at.caption)


def test_forgot_password_shows_non_enumerating_message(monkeypatch):
    def fake_post(url, data=None, headers=None, timeout=None, params=None, json=None):
        if url.endswith("/password/forgot"):
            assert json == {"email": "user@test.local"}
            return FakeHttpxResponse(ok=True, json_data={"ok": True})
        return FakeHttpxResponse(ok=False, status_code=500, text="unexpected")

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeHttpxResponse(ok=True, json_data={}))

    at = new_app_test().run()
    set_public_page(at, "Reset password")
    at.run()

    text_input_by_key(at, "forgot_email").input("user@test.local")
    click_button(at, "Send reset link")
    at.run()

    assert any("reset email has been sent" in s.value.lower() for s in at.success)


def test_login_backend_request_exception_is_shown(monkeypatch):
    def boom(*args, **kwargs):
        raise httpx.TimeoutException("nope")

    monkeypatch.setattr(httpx, "post", boom)
    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeHttpxResponse(ok=True, json_data={}))

    at = new_app_test().run()
    text_input_by_key(at, "login_email").input("user@test.local")
    text_input_by_key(at, "login_password").input("pw")
    click_button(at, "Sign in")
    at.run()

    assert len(at.error) >= 1
    assert "Backend request failed" in at.error[0].value
