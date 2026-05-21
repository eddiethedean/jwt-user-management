import sys
from pathlib import Path

import pytest

# ruff: noqa: E402

_APP_ROOT = Path(__file__).resolve().parents[1]
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

from user_management_streamlit.user_common.backend_client import validate_backend_url


def test_disallows_backend_url_with_credentials(monkeypatch):
    with pytest.raises(ValueError, match="credentials"):
        validate_backend_url("https://user:pass@example.com")


def test_allows_testserver_for_streamlit_apptests():
    # Streamlit AppTest uses "http://testserver" for mocked requests; it should remain valid.
    validate_backend_url("http://testserver")


def test_rejects_hostname_resolving_to_private_ip(monkeypatch):
    def fake_getaddrinfo(host, port, type=0, **kwargs):  # noqa: ARG001
        # Return a private RFC1918 address as if DNS resolved internally.
        return [(2, 1, 6, "", ("10.0.0.5", port))]

    monkeypatch.setattr(
        "user_management_streamlit.user_common.backend_client.socket.getaddrinfo",
        fake_getaddrinfo,
    )

    with pytest.raises(ValueError, match="resolve to private"):
        validate_backend_url("https://example.com")
