from streamlit.testing.v1 import AppTest


def test_disallows_backend_url_with_credentials(monkeypatch):
    monkeypatch.setenv("BACKEND_URL", "https://user:pass@example.com")
    monkeypatch.setenv("STREAMLIT_DISABLE_COOKIES", "1")

    at = AppTest.from_file("app.py", default_timeout=30).run()
    assert not at.exception
    assert len(at.error) >= 1
    assert "credentials" in at.error[0].value.lower()

