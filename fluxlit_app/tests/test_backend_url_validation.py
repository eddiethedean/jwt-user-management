"""Tests for ``ui.backend_url.validate_backend_url``."""

from __future__ import annotations

import pytest

from ui.backend_url import validate_backend_url


def test_disallows_backend_url_with_credentials(monkeypatch):
    with pytest.raises(ValueError, match="credentials"):
        validate_backend_url("https://user:pass@example.com")


def test_allows_testserver_for_streamlit_apptests():
    validate_backend_url("http://testserver")


def test_rejects_hostname_resolving_to_private_ip(monkeypatch):
    def fake_getaddrinfo(host, port, type=0, **kwargs):  # noqa: ARG001
        return [(2, 1, 6, "", ("10.0.0.5", port))]

    monkeypatch.setattr("ui.backend_url.socket.getaddrinfo", fake_getaddrinfo)

    with pytest.raises(ValueError, match="resolve to private"):
        validate_backend_url("https://example.com")
