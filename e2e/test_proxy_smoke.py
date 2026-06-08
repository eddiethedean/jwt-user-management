"""Smoke tests for Connect-like proxy mode (``E2E_USE_PROXY=1``)."""

import os

import pytest
import requests


def _proxy_enabled() -> bool:
    return os.getenv("E2E_USE_PROXY", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
        "on",
    }


@pytest.mark.e2e
def test_backend_docs_reachable_through_proxy(app_urls):
    if not _proxy_enabled():
        pytest.skip("Set E2E_USE_PROXY=1 to run proxy smoke tests")
    assert app_urls.get("proxy_enabled") is True
    r = requests.get(f"{app_urls['backend']}/docs", timeout=10)
    assert r.status_code == 200
