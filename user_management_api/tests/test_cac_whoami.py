from __future__ import annotations

from fastapi.testclient import TestClient

from app.asgi import app


def test_cac_whoami_requires_credentials() -> None:
    c = TestClient(app, base_url="http://testserver")
    r = c.get("/auth/cac/whoami")
    assert r.status_code == 401


def test_cac_whoami_accepts_forwarded_headers() -> None:
    c = TestClient(app, base_url="http://testserver")
    r = c.get(
        "/auth/cac/whoami",
        headers={
            "X-SSL-Client-Verify": "SUCCESS",
            "X-SSL-Client-S-DN": "CN=DOE.JOHN.1234567890,OU=PKI,OU=DoD,O=U.S. Government,C=US",
            "X-SSL-Client-I-DN": "CN=DoD Root CA 3,OU=PKI,OU=DoD,O=U.S. Government,C=US",
            "X-SSL-Client-Serial": "01AB23CD",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["cac"]["source"] == "headers"
    assert data["cac"]["subject_dn"].startswith("CN=")

