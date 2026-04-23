from __future__ import annotations

from typing import Optional, Protocol


class _HasReset(Protocol):
    def reset(self) -> None: ...


def _get_rate_limiter(app) -> Optional[_HasReset]:
    # The middleware stack is nested: wrapper.app.app.... until the endpoint router.
    cur = getattr(app, "middleware_stack", None)
    while cur is not None:
        if cur.__class__.__name__ == "InMemoryRateLimitMiddleware":
            return cur
        cur = getattr(cur, "app", None)
    return None


def test_rate_limit_trips_for_password_forgot(client):
    # Force middleware stack creation.
    client.post("/password/forgot", json={"email": "a@test.local"})

    from app.main import app

    limiter = _get_rate_limiter(app)
    assert limiter is not None
    limiter.reset()

    # Limit is 5/min; 6th should be 429.
    for _ in range(5):
        r = client.post("/password/forgot", json={"email": "a@test.local"})
        assert r.status_code == 200

    r6 = client.post("/password/forgot", json={"email": "a@test.local"})
    assert r6.status_code == 429
    assert r6.json()["detail"] == "Too many requests"
    assert int(r6.headers.get("Retry-After", "0")) >= 1
