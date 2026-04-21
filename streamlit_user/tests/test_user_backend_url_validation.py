from streamlit.testing.v1 import AppTest

from app_paths import USER_APP_PY


def test_disallows_backend_url_with_credentials(monkeypatch):
    monkeypatch.setenv("BACKEND_URL", "https://user:pass@example.com")

    at = AppTest.from_file(USER_APP_PY, default_timeout=30).run()
    assert not at.exception
    assert len(at.error) >= 1
    assert "credentials" in at.error[0].value.lower()
