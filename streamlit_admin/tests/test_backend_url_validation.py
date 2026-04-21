import os

from streamlit.testing.v1 import AppTest

from helpers import ADMIN_APP_PY


def test_requires_https_for_non_local_when_admin_key_set(monkeypatch):
    monkeypatch.setenv("STREAMLIT_TEST_MODE", "1")
    monkeypatch.setenv("BACKEND_ADMIN_API_KEY", "test-key")
    monkeypatch.setenv("BACKEND_URL", "http://example.com")

    at = AppTest.from_file(ADMIN_APP_PY, default_timeout=30).run()
    assert not at.exception
    assert len(at.error) >= 1
    assert "https://" in at.error[0].value.lower()


def test_disallows_backend_url_with_credentials(monkeypatch):
    monkeypatch.setenv("STREAMLIT_TEST_MODE", "1")
    monkeypatch.setenv("BACKEND_ADMIN_API_KEY", "test-key")
    monkeypatch.setenv("BACKEND_URL", "https://user:pass@example.com")

    at = AppTest.from_file(ADMIN_APP_PY, default_timeout=30).run()
    assert not at.exception
    assert len(at.error) >= 1
    assert "credentials" in at.error[0].value.lower()

