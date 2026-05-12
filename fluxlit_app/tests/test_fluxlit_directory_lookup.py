from __future__ import annotations

import json
from datetime import datetime, timezone

from fluxlit.testing import FluxLitTestClient
from sqlmodel import Session

from conftest import load_fluxlit_app


def _seed_admin(*, db_engine) -> None:
    from app.core.security import hash_password
    from app.models import User

    with Session(db_engine) as s:
        s.add(
            User(
                email="admin@example.com",
                hashed_password=hash_password("admin123"),
                is_admin=True,
                created_at=datetime.now(timezone.utc),
            )
        )
        s.commit()


class _Resp:
    def __init__(self, *, status_code: int, json_data=None):
        self.status_code = status_code
        self._json_data = json_data

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self):
        return self._json_data


def test_register_rejects_email_not_in_directory(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    app = load_fluxlit_app(
        db_url=db_url,
        extra_env={
            "DIRECTORY_LOOKUP_URL": "http://directory.test/ldapEmail",
            "DIRECTORY_LOOKUP_REQUIRED": "true",
        },
    )

    import app.services.directory as directory

    monkeypatch.setattr(directory.httpx, "get", lambda *a, **k: _Resp(status_code=404))

    tc = FluxLitTestClient(app)
    r = tc.api_post(
        "/register",
        data={"email": "nobody@example.com"},
        follow_redirects=False,
    )
    assert r.status_code == 400
    assert "Email not found in directory" in r.text


def test_lookup_parses_country_from_directory_response(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    _ = load_fluxlit_app(
        db_url=db_url,
        extra_env={
            "DIRECTORY_LOOKUP_URL": "http://directory.test/ldapEmail",
            "DIRECTORY_LOOKUP_REQUIRED": "true",
        },
    )

    import app.services.directory as directory

    monkeypatch.setattr(
        directory.httpx,
        "get",
        lambda *a, **k: _Resp(
            status_code=200,
            json_data={"attributes": {"mail": ["user@example.com"], "co": ["US"]}},
        ),
    )

    rec = directory.lookup_email("user@example.com")
    assert rec
    assert rec.country == "US"


def test_lookup_strips_c_prefix_from_country(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    _ = load_fluxlit_app(
        db_url=db_url,
        extra_env={
            "DIRECTORY_LOOKUP_URL": "http://directory.test/ldapEmail",
            "DIRECTORY_LOOKUP_REQUIRED": "true",
        },
    )

    import app.services.directory as directory

    monkeypatch.setattr(
        directory.httpx,
        "get",
        lambda *a, **k: _Resp(
            status_code=200,
            json_data={"attributes": {"mail": ["user@example.com"], "c": ["C=US"]}},
        ),
    )

    rec = directory.lookup_email("user@example.com")
    assert rec
    assert rec.country == "US"


def test_lookup_accepts_json_string_payload(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    _ = load_fluxlit_app(
        db_url=db_url,
        extra_env={
            "DIRECTORY_LOOKUP_URL": "http://directory.test/ldapEmail",
            "DIRECTORY_LOOKUP_REQUIRED": "true",
        },
    )

    import app.services.directory as directory

    payload = {
        "attributes": {
            "mail": ["user@example.com"],
            "co": ["US"],
            "displayName": ["X"],
        },
        "dn": "CN=X",
    }
    monkeypatch.setattr(
        directory.httpx,
        "get",
        lambda *a, **k: _Resp(status_code=200, json_data=json.dumps(payload)),
    )

    rec = directory.lookup_email("user@example.com")
    assert rec
    assert rec.email == "user@example.com"
    assert rec.country == "US"


def test_admin_invite_rejects_email_not_in_directory(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    app = load_fluxlit_app(
        db_url=db_url,
        extra_env={
            "DIRECTORY_LOOKUP_URL": "http://directory.test/ldapEmail",
            "DIRECTORY_LOOKUP_REQUIRED": "true",
        },
    )

    import app.db as db

    _seed_admin(db_engine=db.engine)

    import app.services.directory as directory

    monkeypatch.setattr(directory.httpx, "get", lambda *a, **k: _Resp(status_code=404))

    tc = FluxLitTestClient(app)

    r_token = tc.api_post(
        "/auth/token",
        data={"username": "admin@example.com", "password": "admin123"},
    )
    assert r_token.status_code == 200
    token = r_token.json().get("access_token")
    assert token

    r = tc.api_post(
        "/invites",
        json={"email": "nobody@example.com", "grant_admin": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422
    assert "email not found in directory" in r.text.lower()
