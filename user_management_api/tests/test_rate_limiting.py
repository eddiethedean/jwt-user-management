from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.rate_limit import InMemoryRateLimitMiddleware, RateLimitRule


def _make_rate_limited_client(*, base_path: str = "") -> TestClient:
    app = FastAPI()
    app.add_middleware(
        InMemoryRateLimitMiddleware,
        enabled=True,
        trust_proxy_headers=False,
        rules={
            ("POST", "/password/forgot"): RateLimitRule(window_seconds=60, max_requests=5),
        },
    )

    @app.post("/password/forgot")
    def _forgot():
        return {"ok": True}

    # Define explicit trailing-slash route to avoid redirect double-counting.
    @app.post("/password/forgot/")
    def _forgot_slash():
        return {"ok": True}

    if base_path:
        from app.middleware.base_path import BasePathMiddleware

        app.add_middleware(BasePathMiddleware, base_path=base_path)
    return TestClient(app)


def test_rate_limit_trips_for_password_forgot():
    c = _make_rate_limited_client()

    for _ in range(5):
        r = c.post("/password/forgot", json={"email": "a@test.local"})
        assert r.status_code == 200

    r6 = c.post("/password/forgot", json={"email": "a@test.local"})
    assert r6.status_code == 429
    assert r6.json()["detail"] == "Too many requests"
    assert int(r6.headers.get("Retry-After", "0")) >= 1


def test_rate_limit_applies_under_base_path():
    c = _make_rate_limited_client(base_path="/bp")

    for _ in range(5):
        r = c.post("/bp/password/forgot", json={"email": "a@test.local"})
        assert r.status_code == 200

    r6 = c.post("/bp/password/forgot", json={"email": "a@test.local"})
    assert r6.status_code == 429


def test_rate_limit_normalizes_trailing_slash():
    c = _make_rate_limited_client()

    for _ in range(5):
        r = c.post("/password/forgot/", json={"email": "a@test.local"})
        assert r.status_code == 200

    r6 = c.post("/password/forgot/", json={"email": "a@test.local"})
    assert r6.status_code == 429


def test_rate_limit_key_uses_xff_when_trust_proxy_headers_enabled():
    app = FastAPI()
    app.add_middleware(
        InMemoryRateLimitMiddleware,
        enabled=True,
        trust_proxy_headers=True,
        rules={
            ("POST", "/password/forgot"): RateLimitRule(window_seconds=60, max_requests=1),
        },
    )

    @app.post("/password/forgot")
    def _forgot():
        return {"ok": True}

    c = TestClient(app)

    r1 = c.post(
        "/password/forgot",
        json={"email": "a@test.local"},
        headers={"X-Forwarded-For": "1.2.3.4"},
    )
    assert r1.status_code == 200

    r2 = c.post(
        "/password/forgot",
        json={"email": "a@test.local"},
        headers={"X-Forwarded-For": "1.2.3.4"},
    )
    assert r2.status_code == 429

    # Different spoofed IP gets a separate bucket (documenting behavior).
    r3 = c.post(
        "/password/forgot",
        json={"email": "a@test.local"},
        headers={"X-Forwarded-For": "5.6.7.8"},
    )
    assert r3.status_code == 200
