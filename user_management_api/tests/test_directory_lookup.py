from __future__ import annotations

import json
import re

from fastapi.testclient import TestClient

from api_test_helpers import (
    FakeHttpxResponse,
    bearer_for,
    load_wrapped_app,
    seed_admin,
    seed_unused_invite,
)


def _fake_directory_response(*args, **kwargs):
    return FakeHttpxResponse(
        status_code=200,
        json_data={"attributes": {"mail": ["user@example.com"], "co": ["US"]}},
    )


class _FakeSyncClient:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, *args, **kwargs):
        return _fake_directory_response()


def test_register_creates_setup_token(tmp_path, monkeypatch) -> None:
    """Registration requires SMTP and does not return raw setup tokens."""
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    app = load_wrapped_app(db_url=db_url, enable_directory=True)
    client = TestClient(app, base_url="http://testserver")

    import app.core.config as config

    config.settings.smtp_host = "smtp.test.local"
    config.settings.smtp_from_email = "noreply@test.local"
    monkeypatch.setattr(
        "app.routes.auth.send_self_registration_email",
        lambda **kwargs: None,
    )

    login = client.get("/login")
    m = re.search(r'name="csrf_token" value="([^"]+)"', login.text)
    assert m
    r = client.post(
        "/register",
        data={"email": "nobody@example.com", "csrf_token": m.group(1)},
        headers={"Accept": "application/json"},
        follow_redirects=False,
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True
    assert "setup_url" not in data
    assert "email_sent" not in data


def test_lookup_parses_country_from_directory_response(
    tmp_path, monkeypatch
) -> None:
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    load_wrapped_app(db_url=db_url, enable_directory=True)

    import app.services.directory as directory

    monkeypatch.setattr(directory.httpx, "Client", _FakeSyncClient)

    rec = directory.lookup_email("user@example.com")
    assert rec
    assert rec.country == "US"


def test_lookup_strips_c_prefix_from_country(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    load_wrapped_app(db_url=db_url, enable_directory=True)

    import app.services.directory as directory

    class _Client:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, *args, **kwargs):
            return FakeHttpxResponse(
                status_code=200,
                json_data={
                    "attributes": {"mail": ["user@example.com"], "c": ["C=US"]}
                },
            )

    monkeypatch.setattr(directory.httpx, "Client", _Client)

    rec = directory.lookup_email("user@example.com")
    assert rec
    assert rec.country == "US"


def test_lookup_accepts_json_string_payload(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    load_wrapped_app(db_url=db_url, enable_directory=True)

    import app.services.directory as directory

    payload = {
        "attributes": {
            "mail": ["user@example.com"],
            "co": ["US"],
            "displayName": ["X"],
        },
        "dn": "CN=X",
    }

    class _Client:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, *args, **kwargs):
            return FakeHttpxResponse(status_code=200, json_data=json.dumps(payload))

    monkeypatch.setattr(directory.httpx, "Client", _Client)

    rec = directory.lookup_email("user@example.com")
    assert rec
    assert rec.email == "user@example.com"
    assert rec.country == "US"


def test_invites_accept_succeeds_when_directory_returns_404(
    tmp_path, monkeypatch
) -> None:
    """Directory 404 on accept must not block user creation."""
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    app = load_wrapped_app(db_url=db_url, enable_directory=True)

    import app.db as db
    import app.services.directory as directory

    raw = seed_unused_invite(db_engine=db.engine, email="nobody@example.com")

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, *args, **kwargs):
            return FakeHttpxResponse(status_code=404)

    monkeypatch.setattr(directory.httpx, "AsyncClient", _Client)

    client = TestClient(app, base_url="http://testserver")
    r = client.post(
        "/invites/accept", json={"token": raw, "password": "longpassword1"}
    )
    assert r.status_code == 200
    assert r.json().get("ok") is True

    h = bearer_for(client, email="nobody@example.com", password="longpassword1")
    me = client.get("/users/me", headers=h)
    assert me.status_code == 200
    assert me.json()["email"] == "nobody@example.com"


def test_admin_invite_succeeds(tmp_path) -> None:
    """Invite creation does not call directory."""
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    app = load_wrapped_app(db_url=db_url, enable_directory=True)

    import app.db as db

    seed_admin(db_engine=db.engine)

    client = TestClient(app, base_url="http://testserver")
    h = bearer_for(client, email="admin@example.com", password="admin123")
    r = client.post(
        "/invites",
        json={"email": "nobody@example.com", "grant_admin": False},
        headers=h,
    )
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_admin_invite_rejects_domain_not_in_allowlist(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    app = load_wrapped_app(
        db_url=db_url,
        enable_directory=False,
        invite_allowed_email_domains=("allowed.org",),
    )

    import app.db as db

    seed_admin(db_engine=db.engine)

    client = TestClient(app, base_url="http://testserver")
    h = bearer_for(client, email="admin@example.com", password="admin123")

    r_bad = client.post(
        "/invites",
        json={"email": "u@example.com", "grant_admin": False},
        headers=h,
    )
    assert r_bad.status_code == 422

    r_ok = client.post(
        "/invites",
        json={"email": "u@allowed.org", "grant_admin": False},
        headers=h,
    )
    assert r_ok.status_code == 200


def test_register_rejects_domain_not_in_allowlist(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    app = load_wrapped_app(
        db_url=db_url,
        enable_directory=False,
        invite_allowed_email_domains=("corp.com",),
    )
    client = TestClient(app, base_url="http://testserver")
    login = client.get("/login")
    m = re.search(r'name="csrf_token" value="([^"]+)"', login.text)
    assert m
    r = client.post(
        "/register",
        data={"email": "x@example.com", "csrf_token": m.group(1)},
        headers={"Accept": "application/json"},
        follow_redirects=False,
    )
    assert r.status_code == 400
    assert "domain" in (r.json().get("detail") or "").lower()
