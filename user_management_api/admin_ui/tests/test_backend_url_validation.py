import sys
from pathlib import Path

import pytest

# ruff: noqa: E402

_ADMIN_UI_ROOT = Path(__file__).resolve().parents[1]
if str(_ADMIN_UI_ROOT) not in sys.path:
    sys.path.insert(0, str(_ADMIN_UI_ROOT))

from admin_common.backend_client import (
    validate_admin_requires_https,
    validate_backend_url,
)


def test_requires_https_for_non_local_when_admin_key_set(monkeypatch):
    with pytest.raises(ValueError, match="https://"):
        validate_admin_requires_https("http://example.com", admin_api_key="test-key")


def test_disallows_backend_url_with_credentials(monkeypatch):
    with pytest.raises(ValueError, match="credentials"):
        validate_backend_url("https://user:pass@example.com")


def test_allows_testserver_for_streamlit_apptests():
    validate_backend_url("http://testserver")


def test_rejects_hostname_resolving_to_private_ip(monkeypatch):
    def fake_getaddrinfo(host, port, type=0, **kwargs):  # noqa: ARG001
        return [(2, 1, 6, "", ("192.168.1.10", port))]

    monkeypatch.setattr(
        "admin_common.backend_client.socket.getaddrinfo", fake_getaddrinfo
    )

    with pytest.raises(ValueError, match="resolve to private"):
        validate_backend_url("https://example.com")
