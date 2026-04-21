"""Unit tests for BackendClient and URL validation (no network)."""

from __future__ import annotations

import os

import pytest

from streamlit_common.backend_client import (
    BackendClient,
    safe_json,
    validate_admin_requires_https,
    validate_backend_url,
    validate_streamlit_test_mode_backend,
)


class _R:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def test_safe_json_dict_roundtrip():
    r = _R({"a": 1})
    assert safe_json(r) == {"a": 1}


def test_safe_json_list_wraps_in_data():
    r = _R([1, 2])
    assert safe_json(r) == {"data": [1, 2]}


def test_safe_json_invalid_returns_empty():
    class Bad:
        def json(self):
            raise ValueError("nope")

    assert safe_json(Bad()) == {}


def test_backend_client_url_joins_path():
    c = BackendClient(base_url="http://localhost:8000/")
    assert c._url("/users/me") == "http://localhost:8000/users/me"


def test_backend_client_headers_bearer_and_admin_key():
    c = BackendClient(
        base_url="http://x",
        admin_api_key="secret",
        access_token="jwt",
    )
    h = c._headers()
    assert h["Authorization"] == "Bearer jwt"
    assert h["X-Admin-Api-Key"] == "secret"


def test_backend_client_headers_minimal():
    c = BackendClient(base_url="http://x")
    assert c._headers() == {}


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8000",
        "https://example.com",
        "http://127.0.0.1:1",
    ],
)
def test_validate_backend_url_accepts_common_dev_urls(url):
    validate_backend_url(url)


def test_validate_backend_url_rejects_credentials():
    with pytest.raises(ValueError, match="credentials"):
        validate_backend_url("https://user:pass@example.com/")


def test_validate_backend_url_rejects_bad_scheme():
    with pytest.raises(ValueError, match="http"):
        validate_backend_url("ftp://example.com")


def test_validate_admin_requires_https_blocks_public_http_with_key():
    with pytest.raises(ValueError, match="https"):
        validate_admin_requires_https("http://api.example.com", admin_api_key="k")


def test_validate_admin_https_allows_localhost_with_key():
    validate_admin_requires_https("http://localhost:8000", admin_api_key="k")
    validate_admin_requires_https("http://127.0.0.1:8000", admin_api_key="k")
    validate_admin_requires_https("http://testserver", admin_api_key="k")


def test_validate_admin_https_noop_without_key():
    validate_admin_requires_https("http://insecure.example.com", admin_api_key="")


def test_validate_streamlit_test_mode_enforced(monkeypatch):
    monkeypatch.setenv("STREAMLIT_TEST_MODE", "1")
    validate_streamlit_test_mode_backend("http://testserver")
    validate_streamlit_test_mode_backend("http://testserver/")
    with pytest.raises(ValueError, match="STREAMLIT_TEST_MODE"):
        validate_streamlit_test_mode_backend("http://localhost:8000")


def test_validate_streamlit_test_mode_off_allows_any(monkeypatch):
    monkeypatch.delenv("STREAMLIT_TEST_MODE", raising=False)
    validate_streamlit_test_mode_backend("http://localhost:8000")
    monkeypatch.setenv("STREAMLIT_TEST_MODE", "0")
    validate_streamlit_test_mode_backend("http://anything")
